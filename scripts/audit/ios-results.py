#!/usr/bin/env python3
"""PSST: iOS audit artifact (ios-result.txt + partner.json) → JSON list {id, status, note} for matrix.py.

  scripts/audit/ios-results.py <artifact-dir> <out.json>

The XCUITest prints PSST-AUDIT|id|status|note. Delivery of reactions, edits, redactions and images is confirmed from
what the Element Web partner actually received (partner.json); cells the simulator cannot exercise get "na".
"""
import json
import sys
from pathlib import Path

src, out = Path(sys.argv[1]), sys.argv[2]
res = {}
for line in (src / "ios-result.txt").read_text().splitlines():
    parts = line.strip().split("|", 3)
    if len(parts) == 4 and parts[0] == "PSST-AUDIT" and parts[1] != "done":
        res[parts[1]] = {"id": parts[1], "status": parts[2], "note": parts[3]}

partner = json.loads((src / "partner.json").read_text()) if (src / "partner.json").exists() else {"events": {}}
ev = list(partner.get("events", {}).values())


def seen(pred):
    return any(pred(e) for e in ev)


checks = {
    "reaction": (lambda e: e["type"] == "m.reaction", "partner (web) dostal m.reaction z iOS"),
    "edit": (lambda e: (e.get("rel") or {}).get("rel_type") == "m.replace", "partner dostal úpravu (m.replace) z iOS"),
    "delete": (lambda e: e["type"] == "m.room.redaction", "partner dostal zmazanie (redaction) z iOS"),
    "reply": (lambda e: "m.in_reply_to" in (e.get("rel") or {}), "partner dostal odpoveď (m.in_reply_to) z iOS"),
    "image": (lambda e: e.get("msgtype") == "m.image", "partner dostal obrázok (m.image) z iOS"),
}
for cid, (pred, note) in checks.items():
    if seen(pred):
        res[cid] = {"id": cid, "status": "ok", "note": note}
    elif cid in res and res[cid]["status"] == "ok":
        res[cid] = {"id": cid, "status": "fail", "note": res[cid]["note"] + "; partner udalosť nedostal"}

v = partner.get("verification", {})
if v.get("webVerified"):
    res["verify_emoji"] = {"id": "verify_emoji", "status": "ok",
                           "note": "iOS (overené zariadenie) overil nové webové prihlásenie toho istého účtu cez emoji; web relácia je cross-signed"}

NA = {
    "notif_open": "nepodpísaný build v simulátore nemá APNs; notifikácie sa dajú overiť len na zariadení (TestFlight)",
    "notif_background": "simulátor bez APNs (nepodpísaný build)",
    "notif_closed": "simulátor bez APNs (nepodpísaný build)",
    "notif_lock": "simulátor bez APNs (nepodpísaný build)",
    "call_voice": "simulátor nemá mikrofón; tlačidlo hovoru existuje (call_button)",
    "call_video": "simulátor nemá kameru ani mikrofón",
    "call_group": "simulátor nemá kameru ani mikrofón",
    "screenshare": "simulátor — nedá sa overiť",
    "call_udp_blocked": "simulátor bez médií — nedá sa overiť",
    "qr_login": "skenovanie QR potrebuje kameru (simulátor ju nemá)",
    "verify_qr": "skenovanie QR potrebuje kameru",
    "voice": "simulátor nemá mikrofón",
    "file": "systémový výber súborov mimo procesu appky — v simulátore neovládnuteľný cez XCUITest",
    "video": "systémový výber médií mimo procesu appky",
    "admin": "admin stránka je webová (testovaná v stĺpci Web)",
    "update_check": "iOS aktualizácie rieši TestFlight/App Store, appka vlastnú kontrolu nemá (zámerne)",
    "download_page": "stránka ukazuje iOS „Coming soon“ — build čaká na zmluvu v App Store Connect",
}
for cid, note in NA.items():
    res.setdefault(cid, {"id": cid, "status": "na", "note": note})

Path(out).write_text(json.dumps(list(res.values()), ensure_ascii=False, indent=1))
print(json.dumps({k: v["status"] for k, v in res.items()}, ensure_ascii=False))
