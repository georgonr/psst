#!/usr/bin/env python3
"""Produkcia: qa-sender vytvorí E2EE DM s príjemcom a pošle správu (test push notifikácií).
   prod_push_send.py <recipient-localpart> [invite|message <room_id>|call <room_id>]"""
import asyncio, json, os, secrets, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
HS = "https://chat.macet.eu"
SENDER = os.environ.get("PSST_SENDER", "qa-ring")

async def main(rcpt, mode="invite", room=None):
    from nio import AsyncClient, AsyncClientConfig, RoomPreset
    pw = json.loads((ROOT / ".prod-test-accounts.json").read_text())[SENDER]
    store = ROOT / ".prod-nio-store"; store.mkdir(exist_ok=True)
    c = AsyncClient(HS, "@" + SENDER + ":chat.macet.eu", store_path=str(store), config=AsyncClientConfig(encryption_enabled=True),
                    ssl=__import__("ssl").create_default_context(cafile=__import__("certifi").where()))
    sess = store / "session.json"
    if sess.exists():
        s = json.loads(sess.read_text()); c.restore_login(s["user_id"], s["device_id"], s["access_token"])
    else:
        import requests  # nio pri 429 ticho čaká; prihlásenie spravíme priamo a výsledok uložíme
        r = requests.post(HS + "/_matrix/client/v3/login", json={"type": "m.login.password", "identifier": {"type": "m.id.user", "user": SENDER}, "password": pw, "initial_device_display_name": "push-test"}, timeout=30)
        print("login", r.status_code, r.text[:120] if r.status_code != 200 else "", file=sys.stderr); r.raise_for_status()
        j = r.json(); sess.write_text(json.dumps(j)); c.restore_login(j["user_id"], j["device_id"], j["access_token"])
    print('logged in', file=sys.stderr)
    c.next_batch = None  # vždy úplná synchronizácia — miestna cache nemusí poznať práve vytvorené miestnosti
    c.loaded_sync_token = None
    r = await c.sync(timeout=3000, full_state=True); print('synced', type(r).__name__, file=sys.stderr)
    if c.should_upload_keys: await c.keys_upload()
    if mode == "invite":
        r = await c.room_create(is_direct=True, invite=[f"@{rcpt}:chat.macet.eu"], preset=RoomPreset.trusted_private_chat, name="PSST test")
        print("ROOM", r.room_id)
    elif mode == "message":
        await c.sync(timeout=3000)
        if c.should_query_keys: await c.keys_query()
        text = "PSST test " + secrets.token_hex(3)
        await c.room_send(room, "m.room.message", {"msgtype": "m.text", "body": text}, ignore_unverified_devices=True)
        print("SENT", text)
    elif mode == "call":
        # MatrixRTC zvonenie: m.rtc.notification (ring) — klient ho zobrazí ako prichádzajúci hovor
        # 1) členstvo v hovore (ako Element Call), 2) zvonenie odkazujúce na toto členstvo
        dev = c.device_id
        member = {"application": "m.call", "call_id": "", "device_id": dev, "expires": 14400000,
                  "foci_preferred": [{"livekit_alias": room, "livekit_service_url": HS + "/livekit/jwt", "type": "livekit",
                                      "url": "wss://chat.macet.eu/livekit/sfu"}],
                  "focus_active": {"focus_selection": "multi_sfu", "type": "livekit"}, "m.call.intent": "video",
                  "membershipID": f"{c.user_id}:{dev}", "scope": "m.room"}
        r = await c.room_put_state(room, "org.matrix.msc3401.call.member", member, state_key=f"_{c.user_id}_{dev}_m.call")
        print("MEMBER", getattr(r, "event_id", r))
        now = int(time.time() * 1000)
        content = {"notification_type": "ring", "sender_ts": now, "lifetime": 30000, "m.call.intent": "video",
                   "m.mentions": {"user_ids": [f"@{rcpt}:chat.macet.eu"], "room": True},
                   "m.relates_to": {"rel_type": "m.reference", "event_id": r.event_id}}
        r = await c.room_send(room, "org.matrix.msc4075.rtc.notification", content, ignore_unverified_devices=True)
        print("RING", getattr(r, "event_id", r))
        await asyncio.sleep(float(os.environ.get("PSST_CALL_HOLD", "25")))
        await c.room_put_state(room, "org.matrix.msc3401.call.member", {}, state_key=f"_{c.user_id}_{dev}_m.call")
        print("HUNG UP")
    await c.close()
asyncio.run(asyncio.wait_for(main(*sys.argv[1:]), 90))
