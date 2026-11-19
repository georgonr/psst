#!/usr/bin/env python3
"""PSST (DECISIONS.md D84): server side of the Android message-search release check (scripts/android/search-gate.sh).

Run with the psst test venv (matrix-nio with E2EE): ~/.local/psst-venv/bin/python -I scripts/android/search_check.py

  setup    <workdir>   two fresh test accounts qa-sg<hex>a (the phone) and qa-sg<hex>b (the partner, nio with E2EE);
                       the partner creates an ENCRYPTED room and invites the phone account, which joins it
                       (server-side session, logged out again). Writes <workdir>/accounts.json (chmod 600) and
                       <workdir>/room.json.
  seed     <workdir>   waits until the phone account has a device (the app signed in), then the partner sends the
                       corpus encrypted to it. Writes <workdir>/expected.json: query → expected number of results,
                       computed from the corpus texts with the index's rules (ASCII folding, every word a prefix).
  send     <workdir> <text>   the partner sends one more encrypted message (prints its tag).
  teardown <workdir>   deletes the room (purge) and deactivates both accounts.

Only qa-* accounts are ever created or touched. Passwords are random, live only in <workdir>/accounts.json and are
never printed. The Synapse admin token stays on the server (the purge runs there with `curl` over ssh).
"""
import asyncio
import json
import os
import re
import secrets
import ssl
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

import certifi
import requests
from nio import AsyncClient, AsyncClientConfig, RoomCreateResponse, RoomSendResponse

HS = "chat.psst.pro"
SN = os.environ.get("SERVER_NAME", "psst.pro")   # Matrix server_name (user IDs), D85
BASE = f"https://{HS}"
SSH = os.environ.get("PSST_SSH", "psst")

# The corpus: Slovak sentences with diacritics. Every message carries its tag "(sgNN)" so the phone side can count
# distinct results in the UI. Expected counts are computed below, never typed in by hand.
CORPUS = [
    "Pošli mi prosím číslo účtu (sg01)",
    "Číslo domu je dvanásť (sg02)",
    "Šťastný nový rok celej rodine (sg03)",
    "Ďakujem, to bolo šťastné riešenie (sg04)",
    "Zajtra obed o dvanástej (sg05)",
    "Kde je moje číslo objednávky? (sg06)",
    "Žltý kôň skáče cez plot (sg07)",
    "Bez zhody: jablko a hruška (sg08)",
]
# Queries typed on the phone: no diacritics, and word beginnings.
QUERIES = ["cislo", "stastn", "ob", "zlty kon", "dvanast"]


def fold(s: str) -> str:
    """tantivy's AsciiFoldingFilter for the letters used here: strip combining marks, lowercase."""
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)).lower()


def words(s: str) -> list[str]:
    return [w for w in re.split(r"[^0-9a-z]+", fold(s)) if w]


def expected_count(query: str) -> int:
    q = words(query)
    return sum(1 for m in CORPUS if all(any(w.startswith(p) for w in words(m)) for p in q))


def ssh(cmd: str) -> str:
    return subprocess.run(["ssh", SSH, cmd], check=True, capture_output=True, text=True).stdout


def mas(*args: str) -> None:
    quoted = " ".join("'" + a.replace("'", "'\\''") + "'" for a in args)
    ssh(f"cd /opt/psst/server && sudo docker compose exec -T mas mas-cli manage {quoted} --config /config/config.yaml"
        " >/dev/null 2>&1")


def login(user: str, pw: str, device: str) -> dict:
    r = requests.post(f"{BASE}/_matrix/client/v3/login", timeout=30, json={
        "type": "m.login.password", "identifier": {"type": "m.id.user", "user": user}, "password": pw,
        "initial_device_display_name": device})
    r.raise_for_status()
    return r.json()


def load(work: Path, name: str) -> dict:
    return json.loads((work / name).read_text())


async def partner(work: Path) -> AsyncClient:
    acc = load(work, "accounts.json")
    store = work / "nio-store"
    store.mkdir(exist_ok=True)
    c = AsyncClient(BASE, f"@{acc['b'][0]}:{SN}", store_path=str(store),
                    config=AsyncClientConfig(encryption_enabled=True, store_sync_tokens=True),
                    ssl=ssl.create_default_context(cafile=certifi.where()))
    if (work / "nio-session.json").exists():
        s = load(work, "nio-session.json")
        c.restore_login(s["user_id"], s["device_id"], s["access_token"])
    else:
        r = await c.login(acc["b"][1], device_name="psst search check")
        (work / "nio-session.json").write_text(json.dumps(
            {"user_id": r.user_id, "device_id": r.device_id, "access_token": r.access_token}))
        os.chmod(work / "nio-session.json", 0o600)
    await c.sync(timeout=3000, full_state=True)
    if c.should_upload_keys:
        await c.keys_upload()
    return c


async def setup(work: Path) -> None:
    work.mkdir(parents=True, exist_ok=True)
    tag = secrets.token_hex(3)
    acc = {"a": [f"qa-sg{tag}a", secrets.token_urlsafe(18)], "b": [f"qa-sg{tag}b", secrets.token_urlsafe(18)]}
    for u, pw in acc.values():
        assert re.fullmatch(r"qa-[a-z0-9-]+", u)
        mas("register-user", "--yes", u, "--password", pw, "--display-name", u, "--ignore-password-complexity")
    (work / "accounts.json").write_text(json.dumps(acc))
    os.chmod(work / "accounts.json", 0o600)
    c = await partner(work)
    a_id = f"@{acc['a'][0]}:{SN}"
    r = await c.room_create(name="psst search check", is_direct=True, invite=[a_id], initial_state=[
        {"type": "m.room.encryption", "state_key": "", "content": {"algorithm": "m.megolm.v1.aes-sha2"}}])
    assert isinstance(r, RoomCreateResponse), r
    room = r.room_id
    # the phone account joins server-side, so the room is already in its list when the app signs in
    s = login(acc["a"][0], acc["a"][1], "psst search check (join)")
    h = {"Authorization": f"Bearer {s['access_token']}"}
    requests.post(f"{BASE}/_matrix/client/v3/join/{requests.utils.quote(room)}", headers=h, json={},
                  timeout=30).raise_for_status()
    requests.post(f"{BASE}/_matrix/client/v3/logout", headers=h, json={}, timeout=30)
    enc = requests.get(f"{BASE}/_matrix/client/v3/rooms/{requests.utils.quote(room)}/state/m.room.encryption/",
                       headers={"Authorization": f"Bearer {c.access_token}"}, timeout=30)
    assert enc.ok and enc.json().get("algorithm") == "m.megolm.v1.aes-sha2", "room is not encrypted"
    (work / "room.json").write_text(json.dumps({"room_id": room, "encrypted": True}))
    await c.close()
    print(f"setup: phone account {acc['a'][0]}, encrypted room ready")


async def wait_for_phone_device(c: AsyncClient, user_id: str, timeout: int = 600) -> None:
    end = time.time() + timeout
    while time.time() < end:
        resp = requests.post(f"{BASE}/_matrix/client/v3/keys/query", timeout=30,
                             headers={"Authorization": f"Bearer {c.access_token}"},
                             json={"device_keys": {user_id: []}})
        if resp.ok and resp.json().get("device_keys", {}).get(user_id):
            return
        await asyncio.sleep(3)
    raise SystemExit("seed: the phone account never got a device with keys (did the app sign in?)")


async def seed(work: Path) -> None:
    acc, room = load(work, "accounts.json"), load(work, "room.json")["room_id"]
    c = await partner(work)
    a_id = f"@{acc['a'][0]}:{SN}"
    await wait_for_phone_device(c, a_id)
    await c.sync(timeout=3000)
    c.users_for_key_query.add(a_id)
    await c.keys_query()
    for text in CORPUS:
        r = await c.room_send(room, "m.room.message", {"msgtype": "m.text", "body": text},
                              ignore_unverified_devices=True)
        assert isinstance(r, RoomSendResponse), r
    await c.close()
    exp = {q: expected_count(q) for q in QUERIES}
    (work / "expected.json").write_text(json.dumps(exp, ensure_ascii=False))
    print("seed: sent", len(CORPUS), "encrypted messages; expected", json.dumps(exp, ensure_ascii=False))


async def send(work: Path, text: str) -> None:
    room = load(work, "room.json")["room_id"]
    c = await partner(work)
    await c.keys_query() if c.should_query_keys else None
    r = await c.room_send(room, "m.room.message", {"msgtype": "m.text", "body": text}, ignore_unverified_devices=True)
    assert isinstance(r, RoomSendResponse), r
    await c.close()
    print("sent")


def teardown(work: Path) -> None:
    acc = load(work, "accounts.json") if (work / "accounts.json").exists() else {}
    if (work / "room.json").exists():
        room = load(work, "room.json")["room_id"]
        # room version 12 ids have no server part ("!<hash>"), older ones end in ":chat.psst.pro"
        assert re.fullmatch(r"![A-Za-z0-9._~-]+(:" + re.escape(SN) + ")?", room), room
        ssh("cd /opt/psst/server && tok=$(sudo cat secrets/admin_token) && curl -s -o /dev/null -X DELETE "
            "-H \"Authorization: Bearer $tok\" -H 'Content-Type: application/json' "
            "-d '{\"purge\": true, \"block\": false}' "
            f"'http://127.0.0.1:8008/_synapse/admin/v2/rooms/{requests.utils.quote(room)}'")
    for u, _ in acc.values():
        assert re.fullmatch(r"qa-[a-z0-9-]+", u)
        ssh(f"cd /opt/psst/server && sudo scripts/members.sh block {u} --deactivate >/dev/null 2>&1 || true")
    print("teardown: room deleted, test accounts deactivated:", " ".join(u for u, _ in acc.values()))


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, work = sys.argv[1], Path(sys.argv[2])
    if cmd == "setup":
        asyncio.run(setup(work))
    elif cmd == "seed":
        asyncio.run(seed(work))
    elif cmd == "send":
        asyncio.run(send(work, sys.argv[3]))
    elif cmd == "teardown":
        teardown(work)
    elif cmd == "expected":
        print(json.dumps({q: expected_count(q) for q in QUERIES}, ensure_ascii=False))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
