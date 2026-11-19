#!/usr/bin/env python3
"""Pripraví dvoch používateľov (felix, gita) a spoločné miestnosti pre test hovorov:
1:1 DM (E2EE) a skupinovú miestnosť. Výstup: JSON s room_id do stdout. Heslá do .local-test-accounts.json."""
import json, os, secrets, socket, subprocess, sys
from pathlib import Path
import requests, urllib3
ROOT = Path(__file__).resolve().parents[2]
_o = socket.getaddrinfo
socket.getaddrinfo = lambda h, *a, **k: _o("127.0.0.1" if str(h).endswith("psst.pro") else h, *a, **k)
urllib3.disable_warnings(); S = requests.Session(); S.verify = False
B = "https://chat.psst.pro/_matrix/client/v3"
acc_f = ROOT / ".local-test-accounts.json"; acc = json.loads(acc_f.read_text())
sys.path.insert(0, str(Path(__file__).resolve().parent))
from masuser import ensure_user
SFX = sys.argv[1] if len(sys.argv) > 1 else ""
USERS = (f"felix{SFX}", f"gita{SFX}")
T = {}
for u in USERS:
    acc.setdefault(u, "psst-" + secrets.token_hex(8))
    T[u] = ensure_user(S, "https://chat.psst.pro", u, acc[u])["access_token"]
acc_f.write_text(json.dumps(acc, indent=2)); os.chmod(acc_f, 0o600)
H = lambda u: {"Authorization": f"Bearer {T[u]}"}
dm = S.post(f"{B}/createRoom", headers=H(USERS[0]), json={"is_direct": True, "preset": "trusted_private_chat", "invite": [f"@{USERS[1]}:psst.pro"], "name": "Hovor 1:1"}).json()["room_id"]
grp = S.post(f"{B}/createRoom", headers=H(USERS[0]), json={"preset": "private_chat", "invite": [f"@{USERS[1]}:psst.pro"], "name": "Skupinový hovor"}).json()["room_id"]
for r in (dm, grp):
    S.post(f"{B}/rooms/{r}/join", headers=H(USERS[1]), json={})
print(json.dumps({"dm": dm, "group": grp, "users": USERS, "passwords": [acc[u] for u in USERS]}))
