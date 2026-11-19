#!/usr/bin/env python3
"""Pošle E2EE textovú správu ako <user> do všetkých jeho miestností s názvom <room_name>.
Čaká na súbor <ready> (iný klient je pripravený), potom zapíše text do <expect>.
    send_msg.py <user> <room_name> <ready_file> <expect_file> [text]
Heslo berie z .local-test-accounts.json. Domény *.psst.pro → 127.0.0.1 len v tomto procese.
PSST_PROD=1: produkcia (skutočné DNS a certifikát), heslá z PSST_ACCOUNTS ({"a": [user, heslo], …}, mimo repa)."""
import asyncio, json, os, secrets, socket, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
PROD = os.environ.get("PSST_PROD") == "1"
if not PROD:
    _o = socket.getaddrinfo
    socket.getaddrinfo = lambda h, *a, **k: _o("127.0.0.1" if str(h).endswith("psst.pro") else h, *a, **k)

async def main(user, room_name, ready, expect, text=None):
    from nio import AsyncClient, AsyncClientConfig
    if PROD:
        import ssl, certifi
        pw = {u: p for u, p in json.loads(Path(os.environ["PSST_ACCOUNTS"]).read_text()).values()}[user]
        tls = ssl.create_default_context(cafile=certifi.where())
    else:
        pw = json.loads((ROOT / ".local-test-accounts.json").read_text())[user]
        tls = False
    text = text or f"PSST live test {secrets.token_hex(4)} 🔒"
    for _ in range(600):
        if Path(ready).exists():
            break
        time.sleep(1)
    c = AsyncClient("https://chat.psst.pro", f"@{user}:psst.pro", store_path=tempfile.mkdtemp(),
                    config=AsyncClientConfig(encryption_enabled=True), ssl=tls)
    await c.login(pw, device_name=f"send-{user}")
    await c.sync(timeout=3000, full_state=True)
    if c.should_upload_keys:
        await c.keys_upload()
    await asyncio.sleep(3)
    await c.keys_query()
    rooms = [r for r in c.rooms.values() if r.display_name == room_name or r.name == room_name]
    for r in rooms:
        await c.room_send(r.room_id, "m.room.message", {"msgtype": "m.text", "body": text},
                          ignore_unverified_devices=True)
    Path(expect).write_text(text)
    print(f"sent to {len(rooms)} room(s): {text}")
    await c.close()

asyncio.run(main(*sys.argv[1:]))
