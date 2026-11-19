#!/usr/bin/env python3
"""
PSST — doplnkový test lokálneho stacku: verejný kanál a súbory.

Spúšťať po smoke_test.py (potrebuje server/secrets/admin_token):
    ~/.local/psst-venv/bin/python tests/server/extra_test.py

- vytvorí pozývací token cez scripts/new-invite.sh a zaregistruje dana + erik
  (heslá uloží do .local-test-accounts.json v koreni repa — gitignored, len lokálny stack),
- dana vytvorí verejný kanál (#kanal) a publikuje ho do adresára,
- adresár NIE je dostupný bez prihlásenia, erik kanál nájde v adresári a pripojí sa cez alias,
- dana pošle do kanála šifrovaný súbor (m.file, E2EE príloha), erik ho stiahne a dešifruje,
- to isté v E2EE DM dana → erik (obrázok m.image).
Domény *.psst.pro sa mapujú na 127.0.0.1 len v tomto procese.
"""
import asyncio
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import requests
import urllib3

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "server"
DOMAIN = os.environ.get("MATRIX_DOMAIN", "chat.psst.pro")
SN = os.environ.get("SERVER_NAME", "psst.pro")   # Matrix server_name (user IDs), D85
BASE = f"https://{DOMAIN}"

_orig = socket.getaddrinfo
socket.getaddrinfo = lambda h, *a, **k: _orig("127.0.0.1" if h in (DOMAIN, "app.psst.pro", "call.psst.pro") else h, *a, **k)
urllib3.disable_warnings()
S = requests.Session()
S.verify = False
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} — {detail}", flush=True)
    return ok


def register(user, password, token=None):
    # PSST: účty spravuje MAS — testovací účet sa vytvorí cez mas-cli (registráciu tokenom overuje register-test.mjs)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from masuser import ensure_user
    return ensure_user(S, BASE, user, password)


async def main():
    from nio import (AsyncClient, AsyncClientConfig, RoomMessageFile, RoomMessageImage,
                     RoomEncryptedFile, RoomEncryptedImage, UploadResponse, RoomCreateResponse,
                     RoomVisibility, RoomPreset, JoinResponse)
    from nio.crypto.attachments import decrypt_attachment

    acc_file = ROOT / ".local-test-accounts.json"
    accounts = json.loads(acc_file.read_text()) if acc_file.exists() else {}
    token = None
    for u in ("dana", "erik"):
        accounts.setdefault(u, "psst-" + secrets.token_urlsafe(12))
        j = register(u, accounts[u], token)
        check(f"účet/login {u} (MAS)", "access_token" in j, j.get("user_id"))
    acc_file.write_text(json.dumps(accounts, indent=2))
    os.chmod(acc_file, 0o600)

    tmp = Path(tempfile.mkdtemp(prefix="psst-extra-"))
    cfg = AsyncClientConfig(store_sync_tokens=True, encryption_enabled=True)
    cl = {}
    for u in ("dana", "erik"):
        c = AsyncClient(BASE, f"@{u}:{SN}", store_path=str(tmp), config=cfg, ssl=False)
        await c.login(accounts[u], device_name=f"extra-{u}")
        await c.sync(timeout=3000, full_state=True)
        if c.should_upload_keys:
            await c.keys_upload()
        cl[u] = c
    dana, erik = cl["dana"], cl["erik"]

    # ---------------- verejný kanál ----------------
    alias = "kanal" + secrets.token_hex(2)
    r = await dana.room_create(name="Kanál PSST", alias=alias, visibility=RoomVisibility.public,
                               preset=RoomPreset.public_chat, topic="verejný kanál servera")
    check("kanál: vytvorenie verejnej miestnosti + publikovanie do adresára", isinstance(r, RoomCreateResponse), getattr(r, "room_id", r))
    room = r.room_id
    anon = S.get(f"{BASE}/_matrix/client/v3/publicRooms")
    check("kanál: adresár bez prihlásenia nedostupný", anon.status_code in (401, 403), f"HTTP {anon.status_code}")
    pr = S.get(f"{BASE}/_matrix/client/v3/publicRooms", headers={"Authorization": f"Bearer {erik.access_token}"}).json()
    found = [x for x in pr.get("chunk", []) if x["room_id"] == room]
    check("kanál: erik ho vidí v adresári (prihlásený)", bool(found), f"{len(pr.get('chunk', []))} kanálov, alias #{alias}:{SN}")
    j = await erik.join(f"#{alias}:{SN}")
    check("kanál: erik sa pripojil cez alias", isinstance(j, JoinResponse), getattr(j, "room_id", j))

    for c in (dana, erik):
        await c.sync(timeout=3000)
    await dana.keys_query() if dana.should_query_keys else None

    # ---------------- súbor v kanáli + v DM ----------------
    async def send_file(room_id, data, name, mimetype, msgtype):
        resp, keys = await dana.upload(lambda *_: data, content_type="application/octet-stream",
                                       filename=name, encrypt=True, filesize=len(data))
        assert isinstance(resp, UploadResponse), resp
        content = {"msgtype": msgtype, "body": name, "info": {"size": len(data), "mimetype": mimetype},
                   "file": {"url": resp.content_uri, **keys}}
        await dana.room_send(room_id, "m.room.message", content, ignore_unverified_devices=True)
        return resp.content_uri

    async def receive_file(room_id, want_hash, kinds):
        for _ in range(15):
            sr = await erik.sync(timeout=2000)
            for ev in sr.rooms.join.get(room_id, type("x", (), {"timeline": type("t", (), {"events": []})()})).timeline.events:
                if isinstance(ev, kinds):
                    dl = await erik.download(ev.url)
                    plain = decrypt_attachment(dl.body, ev.key["k"], ev.hashes["sha256"], ev.iv)
                    return hashlib.sha256(plain).hexdigest() == want_hash, ev
        return False, None

    data = os.urandom(200_000) + "PSST súbor 📎".encode()
    h = hashlib.sha256(data).hexdigest()
    uri = await send_file(room, data, "dokument.bin", "application/octet-stream", "m.file")
    raw = S.get(f"{BASE}/_matrix/client/v1/media/download/{DOMAIN}/{uri.rsplit('/', 1)[1]}",
                headers={"Authorization": f"Bearer {erik.access_token}"}).content
    check("súbor: na serveri je len zašifrovaný blob", hashlib.sha256(raw).hexdigest() != h and len(raw) == len(data), f"{len(raw)} B")
    ok, ev = await receive_file(room, h, (RoomEncryptedFile,))
    check("súbor v kanáli: erik stiahol a dešifroval (SHA-256 zhoda)", ok, getattr(ev, "body", None))

    dm = await dana.room_create(is_direct=True, invite=[erik.user_id], preset=RoomPreset.trusted_private_chat,
                                initial_state=[{"type": "m.room.encryption", "state_key": "",
                                                "content": {"algorithm": "m.megolm.v1.aes-sha2"}}])
    await erik.sync(timeout=2000)
    await erik.join(dm.room_id)
    for c in (dana, erik):
        await c.sync(timeout=3000)
    png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                        "1f15c4890000000d49444154789c6360f8cf000000040001f5b8f7a20000000049454e44ae426082")
    await send_file(dm.room_id, png, "obrazok.png", "image/png", "m.image")
    ok, ev = await receive_file(dm.room_id, hashlib.sha256(png).hexdigest(), (RoomEncryptedImage,))
    check("obrázok v E2EE DM: erik dešifroval (SHA-256 zhoda)", ok, getattr(ev, "body", None))

    for c in cl.values():
        await c.close()
    fails = [r for r in RESULTS if not r[1]]
    print(f"\nPSST EXTRA TEST: {'PASS' if not fails else 'FAIL'}  ({len(RESULTS) - len(fails)} pass, {len(fails)} fail)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
