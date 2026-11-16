"""PSST verification wake-up (DECISIONS D68).

Matrix never pushes to-device messages, so a phone whose app is closed does not learn that another device of the
same user asks to be verified. nginx mirrors every
    PUT /_matrix/client/*/sendToDevice/m.key.verification.request/<txn>
to this service (the client's request itself goes to Synapse unchanged). For each mirrored request we:

  1. validate the caller's access token with Synapse (/account/whoami) → user id + requesting device,
  2. keep only targets that are the caller's own user (self-verification; never wake other people),
  3. read the user's pushers through the Synapse admin API (token stays on the server),
  4. send one high-priority push through our Sygnal to every psst Android pusher except the requesting device,
     with the marker room id !psst-verification:<domain>. The psst Android app shows
     "Žiadosť o overenie — otvorte psst" for it (no message content, nothing else is fetched).

At most one wake per user per WAKE_INTERVAL seconds. Stdlib only.
"""
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SYNAPSE = os.environ.get("SYNAPSE_URL", "http://synapse:8008")
SYGNAL = os.environ.get("SYGNAL_URL", "http://sygnal:5000")
DOMAIN = os.environ["MATRIX_DOMAIN"]
APP_IDS = set(os.environ.get("WAKE_APP_IDS", "eu.macet.psst").split())
TOKEN_FILE = os.environ.get("ADMIN_TOKEN_FILE", "/secrets/admin_token")
WAKE_INTERVAL = int(os.environ.get("WAKE_INTERVAL", "20"))
MARKER_ROOM = f"!psst-verification:{DOMAIN}"
MARKER_EVENT = "$psst_verification_request_" + "0" * 17  # 43 chars like a v4 event id

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("psst-wake")
_last: dict[str, float] = {}
_lock = threading.Lock()


def _call(method, url, token=None, body=None, timeout=10):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token if token.startswith("Bearer ") else f"Bearer {token}"
    req = urllib.request.Request(url, method=method, headers=headers,
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def wake(auth_header: str, body: bytes):
    try:
        who = _call("GET", f"{SYNAPSE}/_matrix/client/v3/account/whoami", auth_header)
    except urllib.error.HTTPError as e:
        log.info("whoami rejected (%s) — ignored", e.code)
        return
    user, req_device = who["user_id"], who.get("device_id")
    try:
        messages = json.loads(body or b"{}").get("messages", {})
    except ValueError:
        return
    targets = messages.get(user)
    if not targets:
        return  # request to another user (verifying someone else) — never wake other people
    with _lock:
        now = time.monotonic()
        if now - _last.get(user, 0) < WAKE_INTERVAL:
            log.info("wake for %s skipped (rate limit)", _short(user))
            return
        _last[user] = now
    admin = open(TOKEN_FILE).read().strip()
    pushers = _call("GET", f"{SYNAPSE}/_synapse/admin/v1/users/{urllib.parse.quote(user)}/pushers", admin).get("pushers", [])
    devices = []
    for p in pushers:
        if p.get("kind") != "http" or p.get("app_id") not in APP_IDS:
            continue
        if req_device and p.get("device_id") == req_device:
            continue
        if "*" not in targets and p.get("device_id") and p["device_id"] not in targets:
            continue
        data = {k: v for k, v in (p.get("data") or {}).items() if k != "url"}
        devices.append({"app_id": p["app_id"], "pushkey": p["pushkey"], "pushkey_ts": p.get("ts", 0), "data": data})
    if not devices:
        log.info("wake for %s: no psst Android pusher", _short(user))
        return
    note = {"notification": {
        "event_id": MARKER_EVENT, "room_id": MARKER_ROOM, "type": "m.key.verification.request",
        "sender": user, "prio": "high", "counts": {"unread": 0}, "devices": devices}}
    try:
        res = _call("POST", f"{SYGNAL}/_matrix/push/v1/notify", body=note)
        log.info("wake for %s: %d device(s), rejected=%d", _short(user), len(devices), len(res.get("rejected", [])))
    except Exception as e:  # noqa: BLE001 — best effort, the verification itself is unaffected
        log.warning("wake for %s failed: %s", _short(user), e)


def _short(user: str) -> str:
    # logs: no full user ids
    return user[:4] + "…"


class Handler(BaseHTTPRequestHandler):
    def do_PUT(self):
        length = min(int(self.headers.get("Content-Length") or 0), 65536)
        body = self.rfile.read(length)
        auth = self.headers.get("Authorization", "")
        self.send_response(204)
        self.end_headers()
        if auth and "/sendToDevice/m.key.verification.request/" in self.path:
            threading.Thread(target=self._safe, args=(auth, body), daemon=True).start()

    do_POST = do_PUT

    def do_GET(self):
        self.send_response(200 if self.path == "/healthz" else 404)
        self.end_headers()

    @staticmethod
    def _safe(auth, body):
        try:
            wake(auth, body)
        except Exception as e:  # noqa: BLE001
            log.warning("wake error: %s", e)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    log.info("psst-wake listening on :8080 (apps: %s)", " ".join(sorted(APP_IDS)))
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
