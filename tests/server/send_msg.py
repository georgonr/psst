#!/usr/bin/env python3
"""Pošle E2EE textovú správu ako <user> do všetkých jeho miestností s názvom <room_name>.
Čaká na súbor <ready> (iný klient je pripravený), potom zapíše text do <expect>.
    send_msg.py <user> <room_name> <ready_file> <expect_file> [text]
Heslo berie z .local-test-accounts.json. Domény *.macet.eu → 127.0.0.1 len v tomto procese."""
import asyncio, json, os, secrets, socket, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
_o = socket.getaddrinfo
socket.getaddrinfo = lambda h, *a, **k: _o("127.0.0.1" if str(h).endswith("macet.eu") else h, *a, **k)

async def main(user, room_name, ready, expect, text=None):
    from nio import AsyncClient, AsyncClientConfig
    pw = json.loads((ROOT / ".local-test-accounts.json").read_text())[user]
    text = text or f"PSST live test {secrets.token_hex(4)} 🔒"
    for _ in range(600):
        if Path(ready).exists():
            break
        time.sleep(1)
    c = AsyncClient("https://chat.macet.eu", f"@{user}:chat.macet.eu", store_path=tempfile.mkdtemp(),
                    config=AsyncClientConfig(encryption_enabled=True), ssl=False)
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
