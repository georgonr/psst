#!/usr/bin/env python3
"""Produkcia: qa-sender vytvorí E2EE DM s príjemcom a pošle správu (test push notifikácií).
   prod_push_send.py <recipient-localpart> [invite|message <room_id>|call <room_id>]"""
import asyncio, json, secrets, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
HS = "https://chat.macet.eu"

async def main(rcpt, mode="invite", room=None):
    from nio import AsyncClient, AsyncClientConfig, RoomPreset
    pw = json.loads((ROOT / ".prod-test-accounts.json").read_text())["qa-sender"]
    store = ROOT / ".prod-nio-store"; store.mkdir(exist_ok=True)
    c = AsyncClient(HS, "@qa-sender:chat.macet.eu", store_path=str(store), config=AsyncClientConfig(encryption_enabled=True),
                    ssl=__import__("ssl").create_default_context(cafile=__import__("certifi").where()))
    sess = store / "session.json"
    if sess.exists():
        s = json.loads(sess.read_text()); c.restore_login(s["user_id"], s["device_id"], s["access_token"])
    else:
        import requests  # nio pri 429 ticho čaká; prihlásenie spravíme priamo a výsledok uložíme
        r = requests.post(HS + "/_matrix/client/v3/login", json={"type": "m.login.password", "identifier": {"type": "m.id.user", "user": "qa-sender"}, "password": pw, "initial_device_display_name": "push-test"}, timeout=30)
        print("login", r.status_code, r.text[:120] if r.status_code != 200 else "", file=sys.stderr); r.raise_for_status()
        j = r.json(); sess.write_text(json.dumps(j)); c.restore_login(j["user_id"], j["device_id"], j["access_token"])
    print('logged in', file=sys.stderr)
    r = await c.sync(timeout=3000, full_state=True); print('synced', type(r).__name__, file=sys.stderr)
    if c.should_upload_keys: await c.keys_upload()
    if mode == "invite":
        r = await c.room_create(is_direct=True, invite=[f"@{rcpt}:chat.macet.eu"], preset=RoomPreset.trusted_private_chat, name="FCM test")
        print("ROOM", r.room_id)
    elif mode == "message":
        await c.sync(timeout=3000)
        if c.should_query_keys: await c.keys_query()
        text = "FCM test " + secrets.token_hex(3)
        await c.room_send(room, "m.room.message", {"msgtype": "m.text", "body": text}, ignore_unverified_devices=True)
        print("SENT", text)
    elif mode == "call":
        # MatrixRTC zvonenie: m.rtc.notification (ring) — klient ho zobrazí ako prichádzajúci hovor
        now = int(time.time() * 1000)
        content = {"notification_type": "ring", "sender_ts": now, "lifetime": 30000,
                   "m.mentions": {"user_ids": [f"@{rcpt}:chat.macet.eu"], "room": True},
                   "m.relates_to": {"rel_type": "m.reference", "event_id": "$" + secrets.token_urlsafe(32)}}
        r = await c.room_send(room, "org.matrix.msc4075.rtc.notification", content, ignore_unverified_devices=True)
        print("RING", getattr(r, "event_id", r))
    await c.close()
asyncio.run(asyncio.wait_for(main(*sys.argv[1:]), 90))
