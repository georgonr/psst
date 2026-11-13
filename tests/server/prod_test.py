#!/usr/bin/env python3
"""
PSST — test NAOSTRO proti produkcii (skutočné DNS a Let's Encrypt certifikát, žiadne mapovanie domén).

    ~/.local/psst-venv/bin/python -I tests/server/prod_test.py <accounts.json>

<accounts.json> (chmod 600, MIMO repa) = {"a": ["user", "heslo"], "b": ["user", "heslo"]} — testovacie účty
vytvorené vopred cez `ssh psst … mas-cli manage register-user` (heslá sa do repa ani logu nepíšu).

Overí:
- prihlásenie oboch účtov cez MAS compat /login,
- E2EE DM: šifrovaná správa a→b, na serveri len m.room.encrypted, b dešifruje,
- skupina (súkromná, šifrovaná): správa a→b,
- verejný kanál: publikovaný v adresári, adresár bez prihlásenia nedostupný, b sa pripojí cez alias,
- šifrovaný súbor v kanáli: na serveri len zašifrovaný blob, b stiahne a dešifruje (SHA-256 zhoda),
- federácia zvonka nedostupná (federation/key API 404, .well-known/matrix/server 404, port 8448 zavretý),
- verejná registrácia zamietnutá (Synapse /register, guest), MAS registrácia vyžaduje token.
"""
import asyncio
import hashlib
import json
import os
import secrets
import socket
import sys
from pathlib import Path

import requests

DOMAIN = os.environ.get("MATRIX_DOMAIN", "chat.macet.eu")
BASE = f"https://{DOMAIN}"
S = requests.Session()   # S.verify = True — produkčný certifikát musí byť platný
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), str(detail)[:160]))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} — {str(detail)[:160]}", flush=True)
    return ok


def compat_login(user, pw):
    r = S.post(f"{BASE}/_matrix/client/v3/login", json={
        "type": "m.login.password", "identifier": {"type": "m.id.user", "user": user}, "password": pw}, timeout=20)
    return r


async def wait_text(client, room_id, text, rounds=20):
    from nio import RoomMessageText
    for _ in range(rounds):
        sr = await client.sync(timeout=2000)
        room = sr.rooms.join.get(room_id) if hasattr(sr, "rooms") else None
        for ev in (room.timeline.events if room else []):
            if isinstance(ev, RoomMessageText) and ev.body == text:
                return ev
    return None


async def main():
    from nio import (AsyncClient, AsyncClientConfig, RoomEncryptedFile, UploadResponse, RoomCreateResponse,
                     RoomVisibility, RoomPreset, JoinResponse)
    from nio.crypto.attachments import decrypt_attachment

    acc = json.loads(Path(sys.argv[1]).read_text())
    (ua, pa), (ub, pb) = acc["a"], acc["b"]

    # ---------------- externé kontroly (bez účtu) ----------------
    r = S.get(f"{BASE}/_matrix/client/versions", timeout=10)
    check("TLS: platný certifikát + client API", r.ok, f"HTTP {r.status_code}")
    for path in ("/_matrix/federation/v1/version", "/_matrix/key/v2/server", "/.well-known/matrix/server"):
        code = S.get(BASE + path, timeout=10).status_code
        check(f"federácia: {path} nedostupné", code == 404, f"HTTP {code}")
    s = socket.socket(); s.settimeout(5)
    try:
        open8448 = s.connect_ex((socket.gethostbyname(DOMAIN), 8448)) == 0
    finally:
        s.close()
    check("federácia: port 8448 zvonka zatvorený", not open8448, "open" if open8448 else "closed/filtered")
    code = S.get(f"{BASE}/_synapse/admin/v1/server_version", timeout=10).status_code
    check("admin API zvonka nedostupné", code == 404, f"HTTP {code}")
    r = S.post(f"{BASE}/_matrix/client/v3/register", json={"username": "eve" + secrets.token_hex(3), "password": "Passw0rd-x1-long"}, timeout=10)
    check("verejná registrácia cez Synapse zamietnutá", r.status_code in (401, 403, 404), f"HTTP {r.status_code} {r.text[:80]}")
    r = S.post(f"{BASE}/_matrix/client/v3/register?kind=guest", json={}, timeout=10)
    check("hosťovský účet zamietnutý", r.status_code in (401, 403, 404), f"HTTP {r.status_code}")
    meta = S.get(f"{BASE}/_matrix/client/v1/auth_metadata", timeout=10).json()
    check("MAS issuer = https://chat.macet.eu/auth/", meta.get("issuer") == f"{BASE}/auth/", meta.get("issuer"))
    reg = S.get(f"{BASE}/auth/register", timeout=10, allow_redirects=True)
    check("MAS registrácia: formulár vyžaduje pozývací token", "token" in reg.text.lower(), f"HTTP {reg.status_code}")
    r = compat_login("eve-neexistuje", "zle-heslo-123456")
    check("prihlásenie s nesprávnym heslom zamietnuté", r.status_code == 403, f"HTTP {r.status_code}")

    # ---------------- účty ----------------
    for u, p in ((ua, pa), (ub, pb)):
        r = compat_login(u, p)
        check(f"login {u} (MAS compat)", r.ok and "access_token" in r.json(), f"HTTP {r.status_code}")

    store = Path(os.environ.get("PSST_NIO_STORE", "/tmp")) / f"psst-prod-{secrets.token_hex(3)}"
    store.mkdir(parents=True)
    cfg = AsyncClientConfig(store_sync_tokens=True, encryption_enabled=True)
    import ssl, certifi   # aiohttp bez certifi nevidí CA (Python z python.org) → nio by donekonečna opakoval
    tls = ssl.create_default_context(cafile=certifi.where())
    a = AsyncClient(BASE, f"@{ua}:{DOMAIN}", store_path=str(store), config=cfg, ssl=tls)
    b = AsyncClient(BASE, f"@{ub}:{DOMAIN}", store_path=str(store), config=cfg, ssl=tls)
    for c, p in ((a, pa), (b, pb)):
        await c.login(p, device_name="prod-test")
        await c.sync(timeout=3000, full_state=True)
        if c.should_upload_keys:
            await c.keys_upload()

    async def settle():
        for c in (a, b):
            await c.sync(timeout=2000)
            if c.should_query_keys:
                await c.keys_query()

    # ---------------- E2EE DM ----------------
    dm = await a.room_create(is_direct=True, invite=[b.user_id], preset=RoomPreset.trusted_private_chat,
                             initial_state=[{"type": "m.room.encryption", "state_key": "",
                                             "content": {"algorithm": "m.megolm.v1.aes-sha2"}}])
    await b.sync(timeout=2000); await b.join(dm.room_id); await settle(); await settle()
    txt = "PSST šifrovaná správa " + secrets.token_hex(4)
    await a.room_send(dm.room_id, "m.room.message", {"msgtype": "m.text", "body": txt}, ignore_unverified_devices=True)
    ev = await wait_text(b, dm.room_id, txt)
    check("E2EE DM: b prijal a dešifroval správu", ev is not None, txt)
    raw = S.get(f"{BASE}/_matrix/client/v3/rooms/{dm.room_id}/messages?dir=b&limit=5",
                headers={"Authorization": f"Bearer {b.access_token}"}, timeout=10).json()
    types = {e["type"] for e in raw.get("chunk", []) if e.get("sender") == a.user_id and e["type"].startswith("m.room.")}
    check("E2EE DM: na serveri len m.room.encrypted", "m.room.encrypted" in types and "m.room.message" not in types, types)

    # ---------------- skupina ----------------
    grp = await a.room_create(name="PSST test skupina", invite=[b.user_id], preset=RoomPreset.private_chat,
                              initial_state=[{"type": "m.room.encryption", "state_key": "",
                                              "content": {"algorithm": "m.megolm.v1.aes-sha2"}}])
    check("skupina: vytvorená (šifrovaná, súkromná)", isinstance(grp, RoomCreateResponse), getattr(grp, "room_id", grp))
    await b.sync(timeout=2000); await b.join(grp.room_id); await settle(); await settle()
    txt = "PSST skupina " + secrets.token_hex(4)
    await a.room_send(grp.room_id, "m.room.message", {"msgtype": "m.text", "body": txt}, ignore_unverified_devices=True)
    ev = await wait_text(b, grp.room_id, txt)
    check("skupina: b prijal a dešifroval správu", ev is not None, txt)

    # ---------------- verejný kanál ----------------
    alias = "testkanal" + secrets.token_hex(2)
    r = await a.room_create(name="PSST test kanál", alias=alias, visibility=RoomVisibility.public,
                            preset=RoomPreset.public_chat, topic="test — po teste sa odstráni z adresára")
    check("kanál: vytvorený a publikovaný", isinstance(r, RoomCreateResponse), getattr(r, "room_id", r))
    chan = r.room_id
    anon = S.get(f"{BASE}/_matrix/client/v3/publicRooms", timeout=10)
    check("kanál: adresár bez prihlásenia nedostupný", anon.status_code in (401, 403), f"HTTP {anon.status_code}")
    pr = S.get(f"{BASE}/_matrix/client/v3/publicRooms", headers={"Authorization": f"Bearer {b.access_token}"}, timeout=10).json()
    check("kanál: b ho vidí v adresári", any(x["room_id"] == chan for x in pr.get("chunk", [])), f"#{alias}:{DOMAIN}")
    j = await b.join(f"#{alias}:{DOMAIN}")
    check("kanál: b sa pripojil cez alias", isinstance(j, JoinResponse), getattr(j, "room_id", j))
    await settle(); await settle()

    # ---------------- šifrovaný súbor v kanáli ----------------
    data = os.urandom(300_000) + "PSST súbor".encode()
    h = hashlib.sha256(data).hexdigest()
    resp, keys = await a.upload(lambda *_: data, content_type="application/octet-stream", filename="dokument.bin",
                                encrypt=True, filesize=len(data))
    check("súbor: upload", isinstance(resp, UploadResponse), getattr(resp, "content_uri", resp))
    await a.room_send(chan, "m.room.message", {"msgtype": "m.file", "body": "dokument.bin",
                      "info": {"size": len(data), "mimetype": "application/octet-stream"},
                      "file": {"url": resp.content_uri, **keys}}, ignore_unverified_devices=True)
    blob = S.get(f"{BASE}/_matrix/client/v1/media/download/{DOMAIN}/{resp.content_uri.rsplit('/', 1)[1]}",
                 headers={"Authorization": f"Bearer {b.access_token}"}, timeout=30).content
    check("súbor: na serveri len zašifrovaný blob", hashlib.sha256(blob).hexdigest() != h and len(blob) == len(data), f"{len(blob)} B")
    got = False
    for _ in range(15):
        sr = await b.sync(timeout=2000)
        room = sr.rooms.join.get(chan)
        for ev in (room.timeline.events if room else []):
            if isinstance(ev, RoomEncryptedFile):
                dl = await b.download(ev.url)
                got = hashlib.sha256(decrypt_attachment(dl.body, ev.key["k"], ev.hashes["sha256"], ev.iv)).hexdigest() == h
        if got:
            break
    check("súbor: b stiahol a dešifroval (SHA-256 zhoda)", got, h[:16])

    # kanál po teste odstrániť z adresára (nech nezavadzia skutočným členom)
    S.put(f"{BASE}/_matrix/client/v3/directory/list/room/{chan}", json={"visibility": "private"},
          headers={"Authorization": f"Bearer {a.access_token}"}, timeout=10)
    for c in (a, b):
        await c.logout(); await c.close()

    fails = [x for x in RESULTS if not x[1]]
    print(f"\nPSST PROD TEST: {'PASS' if not fails else 'FAIL'}  ({len(RESULTS) - len(fails)} pass, {len(fails)} fail)")
    out = os.environ.get("PSST_RESULTS")
    if out:
        Path(out).write_text(json.dumps([{"name": n, "ok": o, "detail": d} for n, o, d in RESULTS], ensure_ascii=False, indent=1))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
