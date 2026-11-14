#!/usr/bin/env python3
"""PSST server smoke test (bod 7) — beží v CI proti stacku z server/compose.yml + compose.test.yml.

Predpoklady:
  * stack beží (./deploy.sh --no-letsencrypt), domény chat./app./call.macet.eu → 127.0.0.1 v /etc/hosts
  * pip install "matrix-nio[e2e]==0.26.0" requests  (Olm/Megolm cez vodozemac)
  * env COMPOSE_FILE=compose.yml:compose.test.yml (pre server/scripts/*)

Výstup: PASS/FAIL tabuľka na stdout, JSON do $SMOKE_RESULTS (default tests/server/results.json),
Markdown do $GITHUB_STEP_SUMMARY. Exit kód 1 pri akomkoľvek FAIL.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DOMAIN = os.environ.get("MATRIX_DOMAIN", "chat.macet.eu")
APP_DOMAIN = os.environ.get("APP_DOMAIN", "app.macet.eu")
CALL_DOMAIN = os.environ.get("CALL_DOMAIN", "call.macet.eu")
BASE = os.environ.get("SMOKE_BASE", f"https://{DOMAIN}")
DIRECT = os.environ.get("SMOKE_DIRECT", "http://127.0.0.1:8008")  # Synapse loopback (ako cez SSH tunel)
SFU_URL = f"wss://{DOMAIN}/livekit/sfu"
REPO = Path(__file__).resolve().parents[2]
SERVER = REPO / "server"

S = requests.Session()
S.verify = False  # self-signed certifikát v CI

RESULTS: list[dict] = []
CTX: dict = {}


def check(cid: str, title: str):
    def deco(fn):
        def run():
            t0 = time.time()
            try:
                detail = fn() or ""
                status = "PASS"
            except SkipCheck as e:
                status, detail = "SKIP", str(e)
            except Exception as e:  # noqa: BLE001
                status = "FAIL"
                detail = f"{type(e).__name__}: {e}"
                traceback.print_exc()
            RESULTS.append({"id": cid, "title": title, "status": status,
                            "detail": str(detail)[:500], "seconds": round(time.time() - t0, 1)})
            print(f"[{status}] {cid} {title} — {detail}", flush=True)
        run.cid = cid
        return run
    return deco


class SkipCheck(Exception):
    pass


def need(*keys):
    for k in keys:
        if k not in CTX:
            raise SkipCheck(f"chýba predpoklad '{k}' (predchádzajúci check zlyhal)")


def expect(cond, msg):
    if not cond:
        raise AssertionError(msg)


def req(method, url, retries=10, **kw):
    """HTTP s opakovaním pri 429 (rate limit registrácie/loginu)."""
    for _ in range(retries):
        r = S.request(method, url, timeout=30, **kw)
        if r.status_code != 429:
            return r
        wait = (r.json().get("retry_after_ms", 2000) / 1000) + 0.5
        time.sleep(min(wait, 30))
    return r


def run_script(*args) -> str:
    p = subprocess.run(list(args), cwd=SERVER, capture_output=True, text=True, timeout=180)
    sys.stderr.write(p.stderr)
    if p.returncode != 0:
        raise RuntimeError(f"{args[0]} exit {p.returncode}: {p.stderr[-400:]}")
    return p.stdout.strip()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def register(username, password, token=None, dummy_without_token=False):
    """Registrácia cez bežné client API (UIA). Vráti finálnu odpoveď."""
    url = f"{BASE}/_matrix/client/v3/register"
    body = {"username": username, "password": password, "initial_device_display_name": "psst-smoke"}
    r = req("POST", url, json=body)
    if r.status_code != 401:
        return r
    j = r.json()
    session = j.get("session")
    CTX.setdefault("flows_seen", j.get("flows"))
    if token is None:
        if dummy_without_token:
            return req("POST", url, json={**body, "auth": {"type": "m.login.dummy", "session": session}})
        return r
    r = req("POST", url, json={**body, "auth": {"type": "m.login.registration_token",
                                                "token": token, "session": session}})
    # ak by flow obsahoval ďalší krok (m.login.dummy), dokončíme ho
    for _ in range(3):
        if r.status_code != 401:
            break
        j = r.json()
        done = set(j.get("completed", []))
        if "m.login.registration_token" not in done:
            break
        nxt = None
        for flow in j.get("flows", []):
            stages = flow["stages"]
            if all(s in stages for s in done):
                rest = [s for s in stages if s not in done]
                if rest:
                    nxt = rest[0]
                    break
        if nxt != "m.login.dummy":
            break
        r = req("POST", url, json={**body, "auth": {"type": "m.login.dummy", "session": session}})
    return r


# ----------------------------------------------------------------------------- 1. Synapse + admin
@check("1.1", "Synapse health (loopback 127.0.0.1:8008) + client API cez nginx")
def c_health():
    for _ in range(60):
        try:
            if S.get(f"{DIRECT}/health", timeout=5).text.strip() == "OK":
                break
        except requests.RequestException:
            pass
        time.sleep(2)
    else:
        raise AssertionError("Synapse /health neodpovedá OK")
    r = S.get(f"{BASE}/_matrix/client/versions", timeout=10)
    expect(r.status_code == 200 and "versions" in r.json(), f"/versions cez nginx: {r.status_code}")
    return f"Synapse OK, spec verzie: {', '.join(r.json()['versions'][-3:])}"


def mas_cli(*args) -> str:
    """mas-cli manage … v MAS kontajneri (stdout+stderr — MAS loguje výsledky na stderr)."""
    p = subprocess.run(["docker", "compose", "exec", "-T", "mas", "mas-cli", "manage", *args,
                        "--config", "/config/config.yaml"], cwd=SERVER, capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise RuntimeError(f"mas-cli {args[0]}: {p.stderr[-300:]}")
    return p.stdout + p.stderr


def compat_login(user, password):
    r = req("POST", f"{BASE}/_matrix/client/v3/login", json={
        "type": "m.login.password", "identifier": {"type": "m.id.user", "user": user}, "password": password,
        "initial_device_display_name": "psst-smoke"})
    expect(r.status_code == 200 and "access_token" in r.json(), f"login {user}: {r.status_code} {r.text[:200]}")
    return r.json()


@check("1.2", "Synapse admin token cez MAS (scripts/members.sh)")
def c_admin():
    run_script("./scripts/members.sh", "list")
    tok = (SERVER / "secrets" / "admin_token").read_text().strip()
    r = S.get(f"{DIRECT}/_synapse/admin/v1/server_version", headers=auth(tok), timeout=10)
    expect(r.status_code == 200, f"admin API s MAS tokenom: {r.status_code} {r.text[:200]}")
    CTX["admin_token"] = tok
    return "servisný admin token (MAS compat, admin scope) funguje"


@check("1.3", "pozývacie tokeny v MAS (scripts/members.sh invite)")
def c_tokens():
    CTX["tok_single"] = run_script("./scripts/members.sh", "invite", "1", "1").splitlines()[-1]
    CTX["tok_multi"] = run_script("./scripts/members.sh", "invite", "3", "1").splitlines()[-1]
    expect(all(len(CTX[k]) >= 8 for k in ("tok_single", "tok_multi")), f"tokeny: {CTX['tok_single']}, {CTX['tok_multi']}")
    (SERVER.parent / ".local-test-tokens.json").write_text(json.dumps({k: CTX[k] for k in ("tok_single", "tok_multi")}))
    return "2 tokeny vytvorené (1× a 3× použiteľný) — registráciu nimi overuje scripts/web/register-test.mjs"


@check("1.4", "admin API je z internetu blokované, z loopbacku dostupné")
def c_admin_blocked():
    need("admin_token")
    r = S.get(f"{BASE}/_synapse/admin/v1/server_version", headers=auth(CTX["admin_token"]), timeout=10)
    expect(r.status_code == 404, f"nginx /_synapse/admin vrátil {r.status_code}")
    r2 = S.get(f"{DIRECT}/_synapse/admin/v1/server_version", headers=auth(CTX["admin_token"]), timeout=10)
    expect(r2.status_code == 200, f"loopback admin API {r2.status_code}")
    return f"verejne 404, loopback 200 (Synapse {r2.json().get('server_version')})"


# ----------------------------------------------------------------------------- 2. registrácia (MAS)
@check("2.1", "registrácia mimo MAS nie je možná; MAS ponúka registráciu (prompt=create) s tokenom")
def c_reg_no_token():
    r = req("POST", f"{BASE}/_matrix/client/v3/register", json={"username": "eve", "password": "Passw0rd-x1"})
    expect("access_token" not in r.text and r.status_code in (400, 401, 403, 404, 405), f"Synapse /register: {r.status_code} {r.text[:150]}")
    r2 = req("POST", f"{BASE}/_matrix/client/v3/register?kind=guest", json={})
    expect("access_token" not in r2.text, f"guest registrácia prešla: {r2.text[:150]}")
    # MAS môže byť na vlastnej subdoméne aj na ceste (chat…/auth/, D42) → adresu berieme z auth_metadata
    meta = S.get(f"{BASE}/_matrix/client/v1/auth_metadata", timeout=10).json()
    expect(meta.get("issuer", "").startswith("https://"), f"auth_metadata issuer: {meta.get('issuer')}")
    expect("create" in meta.get("prompt_values_supported", []), f"prompt=create chýba: {meta.get('prompt_values_supported')}")
    d = S.get(meta["issuer"].rstrip("/") + "/.well-known/openid-configuration", timeout=10).json()
    expect(d.get("issuer") == meta["issuer"], f"discovery issuer {d.get('issuer')} != {meta['issuer']}")
    return f"Synapse /register {r.status_code}, guest {r2.status_code}, MAS issuer {meta['issuer']}, prompt=create"


@check("2.3", "účty alice, bob, carol (mas-cli) + prihlásenie cez MAS compat /login")
def c_reg_ok():
    users = {}
    pw = {u: "Passw0rd-" + secrets.token_hex(6) for u in ("alice", "bob", "carol")}
    for u in pw:
        try:
            mas_cli("register-user", "--yes", u, "--password", pw[u], "--ignore-password-complexity")
        except RuntimeError as e:
            if "already exists" not in str(e):
                raise
            mas_cli("set-password", u, pw[u], "--ignore-complexity")
        users[u] = compat_login(u, pw[u])
    CTX["users"] = users
    CTX["passwords"] = pw
    return "prihlásení: " + ", ".join(v["user_id"] for v in users.values())


# ----------------------------------------------------------------------------- 3. federácia vypnutá
def tcp_open(host, port):
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except OSError:
        return False


@check("3.1", "federácia vypnutá (žiadny listener, endpointy 404, port 8448 zatvorený)")
def c_federation():
    out = []
    for url in (f"{BASE}/_matrix/federation/v1/version", f"{BASE}/_matrix/key/v2/server",
                f"{BASE}/.well-known/matrix/server",
                f"{DIRECT}/_matrix/federation/v1/version", f"{DIRECT}/_matrix/key/v2/server",
                f"{DIRECT}/_matrix/federation/v1/query/profile?user_id=@alice:{DOMAIN}"):
        r = S.get(url, timeout=10)
        expect(r.status_code in (400, 401, 403, 404), f"{url} → {r.status_code} {r.text[:120]}")
        out.append(r.status_code)
    expect(not tcp_open("127.0.0.1", 8448), "port 8448 je otvorený na hostiteľovi")
    # federačné API nie je ani na internom openid listeneri (len /openid/userinfo)
    p = subprocess.run(["docker", "compose", "exec", "-T", "synapse", "curl", "-s", "-o", "/dev/null",
                        "-w", "%{http_code}", "http://localhost:8009/_matrix/federation/v1/version"],
                       cwd=SERVER, capture_output=True, text=True, timeout=60)
    expect(p.stdout.strip() in ("404", "400"), f"openid listener /version → {p.stdout}")
    return f"HTTP {out}, 8448 zatvorený, openid listener /version {p.stdout.strip()}"


# ----------------------------------------------------------------------------- 4. + 5. E2EE (matrix-nio)
async def e2ee_scenario():
    from nio import (AsyncClient, AsyncClientConfig, MegolmEvent, RoomMessageText,
                     RoomPreset, RoomSendResponse, JoinResponse, RoomCreateResponse, LoginResponse)

    tmp = Path(tempfile.mkdtemp(prefix="psst-nio-"))
    clients = {}
    received: dict[str, list] = {}
    pending: dict[str, list] = {}

    def on_event(name):
        async def cb(room, event):
            if isinstance(event, MegolmEvent):
                pending[name].append(event)
            elif isinstance(event, RoomMessageText):
                received[name].append((room.room_id, event))
        return cb

    for name in ("alice", "bob", "carol"):
        store = tmp / name
        store.mkdir()
        c = AsyncClient(BASE, f"@{name}:{DOMAIN}", store_path=str(store),
                        config=AsyncClientConfig(encryption_enabled=True, store_sync_tokens=False), ssl=False)
        resp = await c.login(CTX["passwords"][name], device_name=f"psst-smoke-{name}")
        if not isinstance(resp, LoginResponse):
            raise AssertionError(f"login {name}: {resp}")
        received[name] = []
        pending[name] = []
        c.add_event_callback(on_event(name), (RoomMessageText, MegolmEvent))
        clients[name] = c

    async def settle(c):
        await c.sync(timeout=500)
        if c.should_upload_keys:
            await c.keys_upload()
        if c.should_query_keys:
            await c.keys_query()
        if c.should_claim_keys:
            await c.keys_claim(c.get_users_for_key_claiming())

    async def settle_all():
        for c in clients.values():
            await settle(c)

    async def until(pred, what, timeout=60):
        t0 = time.time()
        while time.time() - t0 < timeout:
            await settle_all()
            if pred():
                return
            await asyncio.sleep(0.5)
        raise AssertionError(f"timeout: {what}")

    def retry_pending(name):
        c = clients[name]
        for ev in list(pending[name]):
            try:
                dec = c.decrypt_event(ev)
            except Exception:  # noqa: BLE001
                continue
            if isinstance(dec, RoomMessageText):
                received[name].append((ev.room_id, dec))
                pending[name].remove(ev)

    def got(name, room_id, body):
        retry_pending(name)
        return any(rid == room_id and ev.body == body for rid, ev in received[name])

    def got_event(name, room_id, body):
        for rid, ev in received[name]:
            if rid == room_id and ev.body == body:
                return ev
        return None

    alice, bob, carol = clients["alice"], clients["bob"], clients["carol"]
    await settle_all()
    for n, c in clients.items():
        await settle(c)

    out = {}
    try:
        # ---------------------------------------------------- 4. šifrovaný DM alice ↔ bob
        r = await alice.room_create(is_direct=True, invite=[bob.user_id], preset=RoomPreset.trusted_private_chat,
                                    initial_state=[{"type": "m.room.encryption", "state_key": "",
                                                    "content": {"algorithm": "m.megolm.v1.aes-sha2"}}])
        if not isinstance(r, RoomCreateResponse):
            raise AssertionError(f"room_create DM: {r}")
        dm = r.room_id
        CTX["dm_room"] = dm
        await until(lambda: dm in bob.invited_rooms, "bob dostane pozvánku do DM")
        jr = await bob.join(dm)
        if not isinstance(jr, JoinResponse):
            raise AssertionError(f"bob join: {jr}")
        await until(lambda: dm in alice.rooms and bob.user_id in alice.rooms[dm].users, "bob v DM")
        expect(alice.rooms[dm].encrypted, "DM nie je šifrovaná")
        await until(lambda: bool(alice.device_store.active_user_devices(bob.user_id) and
                                 list(alice.device_store.active_user_devices(bob.user_id))),
                    "alice pozná bobove zariadenia")
        text = f"PSST tajná správa {secrets.token_hex(6)} 🔒"
        sr = await alice.room_send(dm, "m.room.message", {"msgtype": "m.text", "body": text},
                                   ignore_unverified_devices=True)
        if not isinstance(sr, RoomSendResponse):
            raise AssertionError(f"room_send: {sr}")
        await until(lambda: got("bob", dm, text), "bob dešifruje správu", timeout=90)
        ev = got_event("bob", dm, text)
        expect(ev.decrypted, "udalosť nebola dešifrovaná (nie je E2EE)")
        # server vidí len šifrovaný obsah
        raw = S.get(f"{BASE}/_matrix/client/v3/rooms/{dm}/event/{sr.event_id}",
                    headers=auth(alice.access_token), timeout=10).json()
        expect(raw.get("type") == "m.room.encrypted", f"na serveri je typ {raw.get('type')}")
        expect(raw["content"].get("algorithm") == "m.megolm.v1.aes-sha2", f"algoritmus {raw['content']}")
        expect(text not in json.dumps(raw, ensure_ascii=False), "plaintext je na serveri!")
        out["dm"] = (f"DM {dm}: bob dešifroval '{text}' (server: m.room.encrypted / "
                     f"{raw['content']['algorithm']}, plaintext nie je na serveri)")

        # ---------------------------------------------------- 5. skupinová miestnosť (3 účastníci)
        r = await alice.room_create(name="PSST smoke skupina", invite=[bob.user_id, carol.user_id],
                                    preset=RoomPreset.private_chat)
        if not isinstance(r, RoomCreateResponse):
            raise AssertionError(f"room_create group: {r}")
        grp = r.room_id
        CTX["group_room"] = grp
        await until(lambda: grp in bob.invited_rooms and grp in carol.invited_rooms, "pozvánky do skupiny")
        for c in (bob, carol):
            jr = await c.join(grp)
            if not isinstance(jr, JoinResponse):
                raise AssertionError(f"{c.user_id} join: {jr}")
        await until(lambda: grp in alice.rooms and {bob.user_id, carol.user_id} <= set(alice.rooms[grp].users),
                    "všetci v skupine")
        # šifrovanie musí byť zapnuté serverovým defaultom (encryption_enabled_by_default_for_room_type: all)
        expect(alice.rooms[grp].encrypted, "skupina nie je šifrovaná serverovým defaultom")
        await until(lambda: all(list(alice.device_store.active_user_devices(u))
                                for u in (bob.user_id, carol.user_id)), "alice pozná zariadenia")
        g1 = f"Ahoj skupina {secrets.token_hex(4)}"
        sr = await alice.room_send(grp, "m.room.message", {"msgtype": "m.text", "body": g1},
                                   ignore_unverified_devices=True)
        if not isinstance(sr, RoomSendResponse):
            raise AssertionError(f"group send: {sr}")
        await until(lambda: got("bob", grp, g1) and got("carol", grp, g1), "bob+carol dešifrujú", timeout=90)
        await until(lambda: all(list(carol.device_store.active_user_devices(u))
                                for u in (alice.user_id, bob.user_id)), "carol pozná zariadenia")
        g2 = f"Carol odpovedá {secrets.token_hex(4)}"
        sr = await carol.room_send(grp, "m.room.message", {"msgtype": "m.text", "body": g2},
                                   ignore_unverified_devices=True)
        if not isinstance(sr, RoomSendResponse):
            raise AssertionError(f"carol send: {sr}")
        await until(lambda: got("alice", grp, g2) and got("bob", grp, g2), "alice+bob dešifrujú", timeout=90)
        expect(all(got_event(n, grp, b).decrypted for n, b in (("bob", g1), ("carol", g1), ("alice", g2))),
               "nie všetky skupinové správy boli E2EE")
        out["group"] = f"skupina {grp} (3 účastníci, šifrovaná defaultom): 2 správy dešifrované všetkými"
        CTX["alice_device"] = alice.device_id
    finally:
        for c in clients.values():
            await c.close()
    return out


E2EE_RESULT: dict = {}
E2EE_ERROR: list = []


def run_e2ee_once():
    if E2EE_RESULT or E2EE_ERROR:
        return
    need("users", "passwords")
    try:
        E2EE_RESULT.update(asyncio.run(e2ee_scenario()))
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        E2EE_ERROR.append(f"{type(e).__name__}: {e}")


@check("4.1", "E2EE DM: alice → bob, m.megolm.v1.aes-sha2, bob dešifruje plaintext (matrix-nio[e2e] + vodozemac)")
def c_e2ee_dm():
    run_e2ee_once()
    if "dm" in E2EE_RESULT:
        return E2EE_RESULT["dm"]
    raise AssertionError(E2EE_ERROR[0] if E2EE_ERROR else "neznáma chyba")


@check("5.1", "skupinová miestnosť (alice, bob, carol): E2EE správy oboma smermi")
def c_group():
    run_e2ee_once()
    if "group" in E2EE_RESULT:
        return E2EE_RESULT["group"]
    if "dm" not in E2EE_RESULT:
        raise SkipCheck("E2EE DM zlyhal")
    raise AssertionError(E2EE_ERROR[0] if E2EE_ERROR else "neznáma chyba")


# ----------------------------------------------------------------------------- 6. well-known + MatrixRTC
@check("6.1", ".well-known/matrix/client cez nginx (m.homeserver + rtc_foci + CORS)")
def c_wellknown():
    r = S.get(f"{BASE}/.well-known/matrix/client", timeout=10)
    expect(r.status_code == 200, f"HTTP {r.status_code}")
    j = r.json()
    expect(j["m.homeserver"]["base_url"] == BASE, f"base_url {j}")
    foci = j.get("org.matrix.msc4143.rtc_foci")
    expect(foci == [{"type": "livekit", "livekit_service_url": f"{BASE}/livekit/jwt"}], f"rtc_foci {foci}")
    expect(r.headers.get("Access-Control-Allow-Origin") == "*", "chýba CORS")
    expect("application/json" in r.headers.get("Content-Type", ""), "Content-Type nie je JSON")
    return json.dumps(j)


@check("6.2", "MatrixRTC transports (/_matrix/client/v1/rtc/transports + unstable MSC4143)")
def c_transports():
    need("users")
    tok = CTX["users"]["alice"]["access_token"]
    r = S.get(f"{BASE}/_matrix/client/v1/rtc/transports", headers=auth(tok), timeout=10)
    expect(r.status_code == 200, f"stable {r.status_code} {r.text[:200]}")
    types = [t.get("type") for t in r.json().get("rtc_transports", r.json().get("transports", []))]
    expect("m.livekit" in json.dumps(r.json()), f"m.livekit chýba: {r.text}")
    r2 = S.get(f"{BASE}/_matrix/client/unstable/org.matrix.msc4143/rtc/transports", headers=auth(tok), timeout=10)
    expect(r2.status_code == 200, f"unstable {r2.status_code}")
    return f"stable: {types or r.text[:200]}; unstable HTTP {r2.status_code}"


@check("6.3", "lk-jwt-service /healthz + LiveKit SFU cez nginx")
def c_lk_health():
    r = S.get(f"{BASE}/livekit/jwt/healthz", timeout=10)
    expect(r.status_code == 200, f"jwt healthz {r.status_code}")
    r2 = S.get(f"{BASE}/livekit/sfu/", timeout=10)
    expect(r2.status_code == 200 and r2.text.strip() == "OK", f"livekit {r2.status_code} {r2.text[:80]}")
    return "jwt /healthz 200, livekit 'OK'"


def jwt_claims(tok):
    p = tok.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))


def lk_validate(jwt):
    r = S.get(f"{BASE}/livekit/sfu/rtc/validate", params={"access_token": jwt}, timeout=15)
    if r.status_code == 404:
        r = S.get(f"{BASE}/livekit/sfu/rtc/v1/validate", params={"access_token": jwt}, timeout=15)
    return r


@check("6.4", "MatrixRTC legacy: OpenID → /livekit/jwt/sfu/get + /get_token → LiveKit token platný")
def c_rtc_legacy():
    need("users", "dm_room")
    a = CTX["users"]["alice"]
    ot = S.post(f"{BASE}/_matrix/client/v3/user/{a['user_id']}/openid/request_token",
                headers=auth(a["access_token"]), json={}, timeout=10).json()
    expect("access_token" in ot and ot.get("matrix_server_name") == DOMAIN, f"openid {ot}")
    r = S.post(f"{BASE}/livekit/jwt/sfu/get", json={"room": CTX["dm_room"], "openid_token": ot,
                                                    "device_id": a["device_id"]}, timeout=30)
    expect(r.status_code == 200, f"/sfu/get {r.status_code} {r.text[:300]}")
    j = r.json()
    expect(j.get("url") == SFU_URL and j.get("jwt"), f"/sfu/get {j}")
    r2 = S.post(f"{BASE}/livekit/jwt/get_token", json={
        "room_id": CTX["dm_room"], "slot_id": "m.call#ROOM", "openid_token": ot,
        "member": {"id": "psst-smoke-member", "claimed_user_id": a["user_id"],
                   "claimed_device_id": a["device_id"]}}, timeout=30)
    expect(r2.status_code == 200 and r2.json().get("jwt"), f"/get_token {r2.status_code} {r2.text[:300]}")
    v = lk_validate(r2.json()["jwt"])
    expect(v.status_code == 200, f"LiveKit validate {v.status_code} {v.text[:200]}")
    claims = jwt_claims(r2.json()["jwt"])
    return f"sfu/get+get_token OK, LiveKit room={claims.get('video', {}).get('room')}, validate 200"


@check("6.5", "MatrixRTC cez C-S API: /_matrix/client/v1/rtc/livekit/get_token (Synapse → lk-jwt AS proxy)")
def c_rtc_cs():
    need("users", "dm_room")
    a, c = CTX["users"]["alice"], CTX["users"]["carol"]
    body = {"url": SFU_URL, "room_id": CTX["dm_room"], "slot_id": "m.call#room", "member_id": "psst-smoke-cs"}
    r = S.post(f"{BASE}/_matrix/client/v1/rtc/livekit/get_token", headers=auth(a["access_token"]),
               json=body, timeout=30)
    expect(r.status_code == 200 and r.json().get("jwt"), f"alice {r.status_code} {r.text[:300]}")
    v = lk_validate(r.json()["jwt"])
    expect(v.status_code == 200, f"LiveKit validate {v.status_code} {v.text[:200]}")
    r2 = S.post(f"{BASE}/_matrix/client/v1/rtc/livekit/get_token", headers=auth(c["access_token"]),
                json=body, timeout=30)
    expect(r2.status_code == 403, f"carol (nie je členom DM) dostala {r2.status_code}")
    return "alice (člen) 200 + validate 200, carol (nečlen) 403"


@check("6.6", "všetky kontajnery healthy (postgres, synapse, livekit, lk-jwt-service, element-call, nginx)")
def c_containers():
    p = subprocess.run(["docker", "compose", "ps", "--format", "json"], cwd=SERVER,
                       capture_output=True, text=True, timeout=60)
    rows = [json.loads(line) for line in p.stdout.splitlines() if line.strip().startswith("{")]
    if not rows and p.stdout.strip().startswith("["):
        rows = json.loads(p.stdout)
    st = {r["Service"]: (r.get("Health") or r.get("State")) for r in rows}
    want = ["postgres", "synapse", "livekit", "lk-jwt-service", "element-call", "nginx"]
    bad = {s: st.get(s) for s in want if st.get(s) != "healthy"}
    expect(not bad, f"nie sú healthy: {bad}")
    return ", ".join(f"{s}={st[s]}" for s in want)


# ----------------------------------------------------------------------------- 7. web vhosts
@check("7.1", "app.macet.eu (PSST web): index + config.json, cache a bezpečnostné hlavičky")
def c_app():
    r = S.get(f"https://{APP_DOMAIN}/", timeout=10)
    expect(r.status_code == 200 and "<html" in r.text.lower(), f"index {r.status_code}")
    expect("frame-ancestors" in r.headers.get("Content-Security-Policy", ""), "chýba CSP")
    expect(r.headers.get("X-Content-Type-Options") == "nosniff", "chýba nosniff")
    expect("max-age" in r.headers.get("Strict-Transport-Security", ""), "chýba HSTS")
    c = S.get(f"https://{APP_DOMAIN}/config.json", timeout=10)
    expect(c.status_code == 200, f"config.json {c.status_code}")
    expect(c.json()["default_server_config"]["m.homeserver"]["base_url"] == BASE, "config.json base_url")
    expect("no-cache" in c.headers.get("Cache-Control", ""), f"config.json cache {c.headers.get('Cache-Control')}")
    return f"index 200, config.json no-cache, CSP '{r.headers.get('Content-Security-Policy')}'"


@check("7.2", "call.macet.eu (Element Call v0.28.2) + presmerovanie HTTP→HTTPS")
def c_call():
    r = S.get(f"https://{CALL_DOMAIN}/", timeout=10)
    expect(r.status_code == 200 and "<html" in r.text.lower(), f"EC index {r.status_code}")
    c = S.get(f"https://{CALL_DOMAIN}/config.json", timeout=10)
    expect(c.status_code == 200 and c.json()["default_server_config"]["m.homeserver"]["base_url"] == BASE,
           f"EC config {c.status_code} {c.text[:200]}")
    h = requests.get(f"http://{DOMAIN}/.well-known/matrix/client", allow_redirects=False, timeout=10)
    expect(h.status_code == 301 and h.headers["Location"].startswith("https://"), f"http {h.status_code}")
    a = requests.get(f"http://{DOMAIN}/.well-known/acme-challenge/nonexistent", allow_redirects=False, timeout=10)
    expect(a.status_code == 404, f"ACME webroot {a.status_code}")
    return "EC index + config.json OK, HTTP 301 → HTTPS, ACME webroot obsluhovaný na :80"


def main():
    checks = [c_health, c_admin, c_tokens, c_admin_blocked, c_reg_no_token, c_reg_ok,
              c_federation, c_e2ee_dm, c_group, c_wellknown, c_transports, c_lk_health, c_rtc_legacy,
              c_rtc_cs, c_containers, c_app, c_call]
    only = os.environ.get("SMOKE_ONLY")
    for c in checks:
        if only and c.cid not in only.split(","):
            continue
        c()

    n_fail = sum(r["status"] == "FAIL" for r in RESULTS)
    n_pass = sum(r["status"] == "PASS" for r in RESULTS)
    n_skip = sum(r["status"] == "SKIP" for r in RESULTS)
    verdict = "PASS" if n_fail == 0 and n_skip == 0 else "FAIL"

    print("\n" + "=" * 100)
    print(f"PSST SERVER SMOKE TEST: {verdict}  ({n_pass} pass, {n_fail} fail, {n_skip} skip)")
    print("=" * 100)
    for r in RESULTS:
        print(f"  {r['status']:4}  {r['id']:4}  {r['title']}")
    print("=" * 100)

    out = Path(os.environ.get("SMOKE_RESULTS", REPO / "tests/server/results.json"))
    out.write_text(json.dumps({"verdict": verdict, "results": RESULTS}, indent=2, ensure_ascii=False))
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ, "a", encoding="utf-8") as f:
            f.write(f"## PSST server smoke test: **{verdict}** ({n_pass} pass, {n_fail} fail, {n_skip} skip)\n\n")
            f.write("| # | kontrola | výsledok | detail |\n|---|---|---|---|\n")
            for r in RESULTS:
                d = r["detail"].replace("|", "\\|").replace("\n", " ")
                f.write(f"| {r['id']} | {r['title']} | {r['status']} | {d} |\n")
    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
