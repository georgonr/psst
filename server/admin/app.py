"""PSST admin — správa členov a nahlásení na https://<APP_DOMAIN>/admin (DECISIONS D56, D87, D88).

- prihlásenie výhradne cez MAS (OIDC authorization code + PKCE), prístup len pre účty s admin právom v MAS
- registrácia je otvorená (MAS + hCaptcha, D88) — pozvánky ani registračné tokeny už nie sú
- blokovanie = MAS lock/unlock (+ príznak locked v Synapse, ako scripts/members.sh)
- nové heslo = MAS admin API set-password, náhodné dočasné heslo sa ukáže raz (D70); relácie člena ostávajú
- admin tokeny/tajomstvá len v kontajneri (súbory zo server/secrets), nikdy v prehliadači
- nahlásenia (D87): správy/miestnosti/používatelia z tabuliek Synapse (read-only, bez obsahu správ), stav vybavené,
  akcie zablokovať člena a zmazať obsah (Synapse admin API), všetko do auditného logu
- session na serveri (cookie len náhodné ID), CSRF token, rate limiting, audit log (JSON lines)
"""
import asyncio
import base64
import datetime as dt
import hashlib
import html
import json
import os
import secrets
import sqlite3
import time
import urllib.parse
from collections import defaultdict, deque

import asyncpg
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response

APP_DOMAIN = os.environ["APP_DOMAIN"]
SERVER_NAME = os.environ["SERVER_NAME"]   # Matrix server_name: user IDs are @name:<SERVER_NAME>
MAS_PUBLIC = os.environ["MAS_PUBLIC_BASE"].rstrip("/")          # https://chat.psst.pro/auth
MAS_INTERNAL = os.environ.get("MAS_INTERNAL", "http://mas:8080").rstrip("/") + os.environ.get("AUTH_PREFIX", "")
MAS_ADMIN = os.environ.get("MAS_ADMIN_API", "http://mas:8081/api/admin/v1")
SYNAPSE = os.environ.get("SYNAPSE_INTERNAL", "http://synapse:8008")
CLIENT_ID = os.environ["ADMIN_CLIENT_ID"]
CLIENT_SECRET = open("/secrets/admin_client_secret").read().strip()
SYNAPSE_ADMIN_TOKEN_FILE = "/secrets/admin_token"
# Nahlásenia (D87): read-only rola vidí v DB synapse len tabuľky nahlásení a stĺpce metadát (deploy.sh), nie obsah
SYN_DSN = "postgresql://psst_admin_ro:{}@postgres/synapse".format(open("/secrets/admin_db_password").read().strip())
DATA = os.environ.get("ADMIN_DATA", "/data")
PROTECTED = {u.strip() for u in os.environ.get("ADMIN_PROTECTED_USERS", "geo,psstadmin").split(",") if u.strip()}
SERVICE_USERS = {"psstadmin"}
REDIRECT_URI = f"https://{APP_DOMAIN}/admin/callback"
SESSION_TTL = 30 * 60        # absolútna platnosť session
SESSION_IDLE = 15 * 60       # nečinnosť
ADMIN_RECHECK = 5 * 60       # admin právo overiť znova
COOKIE = "psst_admin"

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
SESSIONS: dict[str, dict] = {}
PENDING: dict[str, dict] = {}   # OIDC state -> {verifier, nonce, ts}
HITS: dict[str, deque] = defaultdict(deque)
_admin_token = {"value": None, "exp": 0}
_syn_pool = None


# ------------------------------------------------------------------ infra
def now() -> float:
    return time.time()


def audit(user: str, ip: str, action: str, **details):
    rec = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "user": user, "ip": ip,
           "action": action, **details}
    with open(os.path.join(DATA, "audit.log"), "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def notes_db():
    c = sqlite3.connect(os.path.join(DATA, "notes.sqlite"))
    c.execute("create table if not exists notes (token_id text primary key, note text, created_by text, created_at text)")
    # stav nahlásení (D87): Synapse stav nemá → vybavené/nevybavené + posledná akcia správcu
    c.execute("create table if not exists report_state (kind text, rid integer, status text, by text, at text, "
              "action text, primary key (kind, rid))")
    return c


def client_ip(req: Request) -> str:
    return req.headers.get("x-real-ip") or (req.client.host if req.client else "?")


def rate_limited(key: str, limit: int, window: int = 60) -> bool:
    q = HITS[key]
    t = now()
    while q and q[0] < t - window:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(t)
    return False


async def syn_pool():
    global _syn_pool
    if _syn_pool is None:
        _syn_pool = await asyncpg.create_pool(SYN_DSN, min_size=1, max_size=2)
    return _syn_pool


async def mas_admin_token() -> str:
    if _admin_token["value"] and _admin_token["exp"] > now() + 30:
        return _admin_token["value"]
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{MAS_INTERNAL}/oauth2/token", auth=(CLIENT_ID, CLIENT_SECRET),
                         data={"grant_type": "client_credentials", "scope": "urn:mas:admin"})
        r.raise_for_status()
        j = r.json()
    _admin_token.update(value=j["access_token"], exp=now() + int(j.get("expires_in", 300)))
    return _admin_token["value"]


async def mas(method: str, path: str, **kw):
    tok = await mas_admin_token()
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.request(method, MAS_ADMIN + path, headers={"Authorization": f"Bearer {tok}"}, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"MAS {method} {path}: {r.status_code} {r.text[:300]}")
    return r.json() if r.content else {}


async def mas_all(path: str):
    out, url = [], path + ("&" if "?" in path else "?") + "page[first]=100"
    for _ in range(50):
        j = await mas("GET", url)
        out += j.get("data", [])
        nxt = j.get("links", {}).get("next")
        if not nxt or not j.get("data"):
            break
        url = nxt.split("/api/admin/v1", 1)[1]
    return out


async def synapse_admin(method: str, path: str, **kw):
    tok = open(SYNAPSE_ADMIN_TOKEN_FILE).read().strip()
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.request(method, SYNAPSE + path, headers={"Authorization": f"Bearer {tok}"}, **kw)
    r.raise_for_status()
    return r.json() if r.content else {}


# ------------------------------------------------------------------ session / security
def get_session(req: Request):
    sid = req.cookies.get(COOKIE)
    s = SESSIONS.get(sid or "")
    if not s:
        return None
    t = now()
    if t - s["created"] > SESSION_TTL or t - s["last"] > SESSION_IDLE:
        SESSIONS.pop(sid, None)
        return None
    s["last"] = t
    return s


def set_cookie(resp: Response, value: str, max_age: int, path="/admin"):
    resp.set_cookie(COOKIE, value, max_age=max_age, path=path, secure=True, httponly=True, samesite="strict")


SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                               "form-action 'self' " + MAS_PUBLIC.split("/auth")[0] + "; frame-ancestors 'none'; base-uri 'none'",
    "X-Frame-Options": "DENY",
    "Cache-Control": "no-store",
    "Referrer-Policy": "same-origin",   # s "no-referrer" posiela prehliadač pri formulároch Origin: null
    "X-Content-Type-Options": "nosniff",
}


@app.middleware("http")
async def guard(req: Request, call_next):
    ip = client_ip(req)
    limit = 20 if req.method == "POST" else 120
    if rate_limited(f"{ip}:{req.method}", limit) or (req.url.path.endswith(("/login", "/callback")) and rate_limited(f"{ip}:login", 10)):
        audit("-", ip, "rate_limited", path=req.url.path)
        return PlainTextResponse("Príliš veľa požiadaviek, skúste o minútu.", status_code=429, headers=SECURITY_HEADERS)
    if req.method == "POST":
        origin = req.headers.get("origin") or ""
        if origin != f"https://{APP_DOMAIN}":
            audit("-", ip, "csrf_origin_rejected", origin=origin, path=req.url.path)
            return PlainTextResponse("Neplatný pôvod požiadavky.", status_code=403, headers=SECURITY_HEADERS)
    resp = await call_next(req)
    for k, v in SECURITY_HEADERS.items():
        resp.headers.setdefault(k, v)
    return resp


async def is_admin_sub(sub: str) -> tuple[bool, str]:
    u = (await mas("GET", f"/users/{sub}"))["data"]["attributes"]
    ok = bool(u.get("admin")) and not u.get("locked_at") and not u.get("deactivated_at") and u["username"] not in SERVICE_USERS
    return ok, u["username"]


async def require_admin(req: Request):
    s = get_session(req)
    if not s:
        return None, RedirectResponse("/admin/login", status_code=303)
    if now() - s["checked"] > ADMIN_RECHECK:
        ok, _ = await is_admin_sub(s["sub"])
        if not ok:
            SESSIONS.pop(req.cookies.get(COOKIE), None)
            return None, deny(req, s["user"])
        s["checked"] = now()
    return s, None


def deny(req: Request, user: str):
    audit(user, client_ip(req), "forbidden", path=req.url.path)
    return HTMLResponse(page("Prístup zamietnutý", f"<p>Účet <b>{esc(user)}</b> nemá prístup k administrácii psst.</p>"
                             f'<p><a href="https://{APP_DOMAIN}/">Späť do psst</a></p>'), status_code=403)


async def check_csrf(req: Request, s: dict) -> dict | None:
    form = dict(await req.form())
    if not secrets.compare_digest(form.get("csrf", ""), s["csrf"]):
        audit(s["user"], client_ip(req), "csrf_token_rejected", path=req.url.path)
        return None
    return form


# ------------------------------------------------------------------ OIDC login (MAS)
@app.get("/admin/login")
async def login(req: Request):
    state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    for k in [k for k, v in PENDING.items() if now() - v["ts"] > 600]:
        PENDING.pop(k, None)
    PENDING[state] = {"verifier": verifier, "nonce": nonce, "ts": now()}
    q = urllib.parse.urlencode({"response_type": "code", "client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI,
                                "scope": "openid", "state": state, "nonce": nonce,
                                "code_challenge": challenge, "code_challenge_method": "S256"})
    return RedirectResponse(f"{MAS_PUBLIC}/authorize?{q}", status_code=303)


@app.get("/admin/callback")
async def callback(req: Request, code: str = "", state: str = "", error: str = ""):
    ip = client_ip(req)
    p = PENDING.pop(state, None)
    if error or not code or not p or now() - p["ts"] > 600:
        audit("-", ip, "login_failed", reason=error or "invalid_state")
        return HTMLResponse(page("Prihlásenie zlyhalo", '<p>Prihlásenie sa nepodarilo. <a href="/admin/login">Skúsiť znova</a></p>'), status_code=400)
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{MAS_INTERNAL}/oauth2/token", auth=(CLIENT_ID, CLIENT_SECRET),
                         data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI,
                               "code_verifier": p["verifier"]})
    if r.status_code != 200:
        audit("-", ip, "login_failed", reason=f"token {r.status_code}")
        return HTMLResponse(page("Prihlásenie zlyhalo", '<p><a href="/admin/login">Skúsiť znova</a></p>'), status_code=400)
    tok = r.json()
    # id_token prišiel priamo z MAS (server-to-server, autentifikovaný klient) → stačí overiť obsah
    claims = json.loads(base64.urlsafe_b64decode(tok["id_token"].split(".")[1] + "=="))
    if claims.get("nonce") != p["nonce"] or claims.get("aud") not in (CLIENT_ID, [CLIENT_ID]) or claims.get("exp", 0) < now():
        audit("-", ip, "login_failed", reason="id_token claims")
        return HTMLResponse(page("Prihlásenie zlyhalo", '<p><a href="/admin/login">Skúsiť znova</a></p>'), status_code=400)
    ok, username = await is_admin_sub(claims["sub"])
    # prístupový token klienta nepotrebujeme — hneď ho zneplatníme
    async with httpx.AsyncClient(timeout=10) as c:
        await c.post(f"{MAS_INTERNAL}/oauth2/revoke", auth=(CLIENT_ID, CLIENT_SECRET), data={"token": tok["access_token"]})
    if not ok:
        return deny(req, username)
    sid = secrets.token_urlsafe(32)
    SESSIONS[sid] = {"sub": claims["sub"], "user": username, "created": now(), "last": now(), "checked": now(),
                     "csrf": secrets.token_urlsafe(32)}
    audit(username, ip, "login")
    resp = RedirectResponse("/admin", status_code=303)
    set_cookie(resp, sid, SESSION_TTL)
    return resp


@app.post("/admin/logout")
async def logout(req: Request):
    s = get_session(req)
    if s and await check_csrf(req, s) is not None:
        audit(s["user"], client_ip(req), "logout")
        SESSIONS.pop(req.cookies.get(COOKIE), None)
    resp = HTMLResponse(page("Odhlásené", '<p>Boli ste odhlásený. <a href="/admin/login">Prihlásiť znova</a></p>'))
    set_cookie(resp, "", 0)
    return resp


# ------------------------------------------------------------------ data
def parse_ts(v):
    return dt.datetime.fromisoformat(v.replace("Z", "+00:00")) if v else None


def fmt(ts, with_time=True):
    if not ts:
        return "—"
    if isinstance(ts, (int, float)):
        ts = dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc)
    loc = ts.astimezone(dt.timezone(dt.timedelta(hours=1)))  # SEČ
    return loc.strftime("%-d. %-m. %Y %H:%M" if with_time else "%-d. %-m. %Y")


def esc(v) -> str:
    return html.escape(str(v), quote=True)


CSS = """
:root{--bg:#f6f7f9;--card:#fff;--fg:#1b1d22;--mut:#6b7280;--acc:#0b7cc1;--bd:#e3e6ea;--red:#c0392b;--grn:#1e8e3e}
@media (prefers-color-scheme:dark){:root{--bg:#101215;--card:#1a1d22;--fg:#e8eaed;--mut:#9aa0a6;--acc:#4fb3f0;--bd:#2c3036;--red:#ef6b5e;--grn:#5bc27a}}
*{box-sizing:border-box}body{margin:0;font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--fg)}
header{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:var(--card);border-bottom:1px solid var(--bd)}
header b{font-size:17px}main{max-width:1100px;margin:0 auto;padding:16px}
section{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:16px;margin-bottom:16px}
h2{margin:0 0 12px;font-size:18px}label{display:block;font-size:13px;color:var(--mut);margin-bottom:4px}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end}.row>div{flex:1 1 140px}
input{width:100%;padding:9px 10px;border:1px solid var(--bd);border-radius:8px;background:var(--bg);color:var(--fg);font:inherit}
button{padding:9px 14px;border:0;border-radius:8px;background:var(--acc);color:#fff;font:inherit;cursor:pointer}
button.sec{background:transparent;color:var(--acc);border:1px solid var(--acc)}button.danger{background:transparent;color:var(--red);border:1px solid var(--red)}
.tbl{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--bd);vertical-align:top}
th{color:var(--mut);font-weight:600;font-size:12px;text-transform:uppercase}code{font:600 15px ui-monospace,Menlo,monospace}
.badge{display:inline-block;padding:2px 8px;border-radius:99px;font-size:12px;border:1px solid var(--bd)}
.free{color:var(--grn);border-color:var(--grn)}.used{color:var(--mut)}.expired,.revoked,.locked{color:var(--red);border-color:var(--red)}
.ok{border-left:4px solid var(--grn)}.msg{white-space:pre-wrap;background:var(--bg);padding:10px;border-radius:8px;border:1px solid var(--bd)}
.mut{color:var(--mut);font-size:13px}form.inline{display:inline}
details summary{cursor:pointer;color:var(--mut);margin-top:10px}
@media (max-width:640px){.tbl table,.tbl tbody,.tbl tr,.tbl td{display:block;width:100%}.tbl tr:first-child{display:none}
.tbl tr{border:1px solid var(--bd);border-radius:10px;padding:8px 10px;margin-bottom:10px}
.tbl td{border:0;padding:3px 0;display:flex;gap:10px}.tbl td::before{content:attr(data-l);color:var(--mut);font-size:12px;min-width:92px}
.tbl td:empty{display:none}.hide-sm{display:none!important}}
"""


def page(title, body, user=None, csrf=None):
    top = ""
    if user:
        top = (f'<form class="inline" method="post" action="/admin/logout"><input type="hidden" name="csrf" value="{esc(csrf)}">'
               f'<span class="mut">{esc(user)}</span> <button class="sec">Odhlásiť</button></form>')
    return (f'<!doctype html><html lang="sk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="robots" content="noindex"><title>{esc(title)} · psst admin</title><style>{CSS}</style></head><body>'
            f'<header><b>psst · správa</b>{top}</header><main>{body}</main></body></html>')


@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/", response_class=HTMLResponse)
async def index(req: Request):
    s, r = await require_admin(req)
    if r:
        return r
    users = await mas_all("/users")
    try:
        syn = {u["name"]: u for u in (await synapse_admin("GET", "/_synapse/admin/v2/users?limit=1000&guests=false&deactivated=true&locked=true"))["users"]}
    except Exception:
        syn = {}

    out = []
    flash = s.pop("pw_flash", None)   # nové heslo: zobrazí sa len raz, nikde sa neukladá
    if flash:
        out.append(f'<section class="ok" id="pwreset"><h2>Nové heslo pre {esc(flash["name"])}</h2>'
                   f'<p>Dočasné heslo: <code id="newpw">{esc(flash["pw"])}</code> '
                   f'<button class="sec" onclick="cp(\'newpw\',this)">Kopírovať</button></p>'
                   f'<p>Heslo sa zobrazuje <b>iba teraz</b> — po obnovení stránky ho už neuvidíte. Odovzdajte ho členovi bezpečne '
                   f'(osobne alebo telefonicky, nie do verejnej miestnosti). Po prihlásení si ho má hneď zmeniť v Nastaveniach účtu '
                   f'(<a href="{esc(MAS_PUBLIC)}/account">{esc(MAS_PUBLIC.split("://", 1)[-1])}/account</a>).</p>'
                   f'<p class="mut">Doterajšie heslo už neplatí. Zariadenia, na ktorých je člen prihlásený, ostávajú prihlásené.</p></section>')
    try:
        out.append(reports_section(await load_reports(), s["csrf"]))
    except Exception as e:  # noqa: BLE001
        audit(s["user"], client_ip(req), "reports_load_failed", error=str(e)[:300])
        out.append('<section id="reports"><h2>Nahlásenia</h2><p class="mut">Nahlásenia sa nepodarilo načítať.</p></section>')
    rows, gone = [], []
    for u in sorted(users, key=lambda x: x["attributes"].get("created_at") or ""):
        a = u["attributes"]
        name = a["username"]
        if name in SERVICE_USERS:
            continue
        sy = syn.get(f"@{name}:{SERVER_NAME}", {})
        if a.get("deactivated_at"):
            st, cls = "deaktivovaný", "revoked"
        elif a.get("locked_at"):
            st, cls = "zablokovaný", "locked"
        else:
            st, cls = "aktívny", "free"
        btn = ""
        if name not in PROTECTED and not a.get("admin") and not a.get("deactivated_at"):
            btn = (f'<form class="inline" method="post" action="/admin/users/{esc(u["id"])}/password" '
                   f'onsubmit="return confirm(\'Nastaviť nové heslo pre {esc(name)}? Doterajšie heslo prestane platiť, prihlásené zariadenia ostanú prihlásené.\')">'
                   f'<input type="hidden" name="csrf" value="{esc(s["csrf"])}"><button class="sec">Nastaviť nové heslo</button></form> ')
            if a.get("locked_at"):
                btn += (f'<form class="inline" method="post" action="/admin/users/{esc(u["id"])}/unlock"><input type="hidden" name="csrf" value="{esc(s["csrf"])}">'
                       f'<button class="sec">Odblokovať</button></form>')
            else:
                btn += (f'<form class="inline" method="post" action="/admin/users/{esc(u["id"])}/lock" onsubmit="return confirm(\'Zablokovať {esc(name)}?\')">'
                       f'<input type="hidden" name="csrf" value="{esc(s["csrf"])}"><button class="danger">Zablokovať</button></form>')
        (gone if a.get("deactivated_at") else rows).append(
            f'<tr><td data-l="Meno"><b>{esc(name)}</b>{" <span class=mut>(admin)</span>" if a.get("admin") else ""}</td>'
            f'<td data-l="Registrácia">{fmt(parse_ts(a.get("created_at")))}</td>'
            f'<td data-l="Posledná aktivita">{fmt(sy.get("last_seen_ts"))}</td><td data-l="Stav"><span class="badge {cls}">{st}</span></td><td>{btn}</td></tr>')
    head = '<tr><th>Meno</th><th>Registrácia</th><th>Posledná aktivita</th><th>Stav</th><th></th></tr>'
    folded = (f'<details><summary>Deaktivované účty ({len(gone)})</summary><div class="tbl"><table>{head}{"".join(gone)}</table></div></details>'
              if gone else "")
    out.append(f'<section><h2>Členovia</h2><div class="tbl"><table>{head}{"".join(rows)}</table></div>{folded}'
               '<p class="mut">Zablokovanie je vratné: účet sa nedá použiť ani prihlásiť, správy a miestnosti ostávajú. '
               'Nové heslo: vygeneruje sa dočasné heslo a zobrazí sa raz; prihlásené zariadenia člena ostávajú prihlásené.</p></section>')
    out.append("""<script>function cp(id,b){navigator.clipboard.writeText(document.getElementById(id).innerText).then(()=>{const t=b.innerText;b.innerText='Skopírované';setTimeout(()=>b.innerText=t,1500)})}</script>""")
    return HTMLResponse(page("Správa", "".join(out), s["user"], s["csrf"]))


# ------------------------------------------------------------------ nahlásenia (D87)
# Zdroj: tabuľky Synapse event_reports (správa), room_reports (miestnosť), user_reports (používateľ). Admin vidí len
# kto, koho/čo, kedy a dôvod, ktorý nahlasovateľ sám napísal — obsah šifrovaných (ani iných) správ sa nečíta.
KIND_LABEL = {"event": "správa", "room": "miestnosť", "user": "používateľ"}
REDACT_REASON = "Odstránené správcom psst po nahlásení / Removed by the psst administrator after a report"


def local_name(mxid: str | None) -> str | None:
    if mxid and mxid.startswith("@") and mxid.endswith(":" + SERVER_NAME):
        return mxid[1:].rsplit(":", 1)[0]
    return None


def report_reason(row) -> str:
    reason = (row["reason"] or "").strip()
    if not reason and row.get("content"):
        try:
            reason = str(json.loads(row["content"]).get("reason") or "").strip()
        except Exception:  # noqa: BLE001
            pass
    return reason[:1000]


async def load_reports() -> list[dict]:
    q = await syn_pool()
    async with q.acquire() as c:
        ev = await c.fetch(
            "select r.id, r.received_ts, r.room_id, r.event_id, r.user_id, r.reason, r.content, "
            "e.sender, e.type as etype, e.origin_server_ts, s.name as room_name, s.encryption, "
            "(select count(*) from redactions x where x.redacts = r.event_id) as redacted "
            "from event_reports r left join events e using (event_id) left join room_stats_state s on s.room_id = r.room_id "
            "order by r.received_ts desc limit 500")
        rr = await c.fetch(
            "select r.id, r.received_ts, r.room_id, r.user_id, r.reason, s.name as room_name, s.encryption, k.creator, "
            "(k.room_id is not null) as room_exists "
            "from room_reports r left join room_stats_state s on s.room_id = r.room_id left join rooms k on k.room_id = r.room_id "
            "order by r.received_ts desc limit 500")
        ur = await c.fetch("select id, received_ts, target_user_id, user_id, reason from user_reports "
                           "order by received_ts desc limit 500")
    out = []
    for r in ev:
        r = dict(r)
        out.append({"kind": "event", "id": r["id"], "ts": r["received_ts"], "reporter": r["user_id"],
                    "reason": report_reason(r), "room_id": r["room_id"], "room_name": r["room_name"],
                    "event_id": r["event_id"], "target": r["sender"], "etype": r["etype"],
                    "encrypted": r["etype"] == "m.room.encrypted" or bool(r["encryption"]),
                    "gone": r["sender"] is None or bool(r["redacted"])})
    for r in rr:
        r = dict(r)
        out.append({"kind": "room", "id": r["id"], "ts": r["received_ts"], "reporter": r["user_id"],
                    "reason": report_reason(r), "room_id": r["room_id"], "room_name": r["room_name"],
                    "target": r["creator"], "encrypted": bool(r["encryption"]), "gone": not r["room_exists"]})
    for r in ur:
        r = dict(r)
        out.append({"kind": "user", "id": r["id"], "ts": r["received_ts"], "reporter": r["user_id"],
                    "reason": report_reason(r), "target": r["target_user_id"], "gone": False})
    with notes_db() as db:
        st = {(k, i): (status, by, at, action) for k, i, status, by, at, action in
              db.execute("select kind, rid, status, by, at, action from report_state").fetchall()}
    for r in out:
        status, by, at, action = st.get((r["kind"], r["id"]), ("open", None, None, None))
        r.update(status=status, by=by, at=at, action=action)
    out.sort(key=lambda r: (r["status"] != "open", -r["ts"]))
    return out


async def find_report(kind: str, rid: int) -> dict | None:
    return next((r for r in await load_reports() if r["kind"] == kind and r["id"] == rid), None)


def set_report_state(kind, rid, status, user, action=None):
    with notes_db() as db:
        prev = db.execute("select action from report_state where kind=? and rid=?", (kind, rid)).fetchone()
        acts = "; ".join(x for x in [prev[0] if prev else None, action] if x) or None
        db.execute("insert or replace into report_state values (?,?,?,?,?,?)",
                   (kind, rid, status, user, dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), acts))


def who(mxid: str | None) -> str:
    if not mxid:
        return "—"
    n = local_name(mxid)
    return esc(n) if n else esc(mxid)


def reports_section(reports: list[dict], csrf: str) -> str:
    open_n = sum(1 for r in reports if r["status"] == "open")
    rows, done = [], []
    for r in reports:
        k = r["kind"]
        if k == "event":
            what = (f'správa od <b>{who(r["target"])}</b> v miestnosti {esc(r["room_name"] or r["room_id"])}'
                    f'<br><span class="mut">{"šifrovaná — obsah nevidno" if r["encrypted"] else "nešifrovaná miestnosť"}'
                    f'{" · už zmazaná" if r["gone"] else ""}</span>')
        elif k == "room":
            what = (f'miestnosť <b>{esc(r["room_name"] or "(bez názvu)")}</b><br><span class="mut">{esc(r["room_id"])}'
                    f'{" · tvorca " + who(r["target"]) if r["target"] else ""}{" · už zmazaná" if r["gone"] else ""}</span>')
        else:
            what = f'používateľ <b>{who(r["target"])}</b>'
        hidden = (f'<input type="hidden" name="csrf" value="{esc(csrf)}">')
        base = f'/admin/reports/{k}/{r["id"]}'
        btn = []
        tname = local_name(r["target"])
        if tname and tname not in PROTECTED and tname not in SERVICE_USERS:
            btn.append(f'<form class="inline" method="post" action="{base}/block" onsubmit="return confirm(\'Zablokovať {esc(tname)}?\')">'
                       f'{hidden}<button class="danger">Zablokovať {"tvorcu" if k == "room" else "člena"}</button></form>')
        if not r["gone"]:
            label = {"event": "Zmazať správu", "room": "Zmazať miestnosť", "user": "Zmazať jeho správy"}[k]
            warn_txt = {"event": "Zmazať nahlásenú správu pre všetkých?",
                        "room": "Zmazať miestnosť aj s celou históriou? Všetci členovia z nej budú odstránení.",
                        "user": "Zmazať VŠETKY správy tohto člena vo všetkých jeho miestnostiach?"}[k]
            if k != "user" or (tname and tname not in PROTECTED):
                btn.append(f'<form class="inline" method="post" action="{base}/delete" onsubmit="return confirm(\'{warn_txt}\')">'
                           f'{hidden}<button class="danger">{label}</button></form>')
        if r["status"] == "open":
            btn.append(f'<form class="inline" method="post" action="{base}/resolve">{hidden}<button class="sec">Vybavené</button></form>')
        else:
            btn.append(f'<form class="inline" method="post" action="{base}/reopen">{hidden}<button class="sec">Znova otvoriť</button></form>')
        state = ('<span class="badge revoked">nevybavené</span>' if r["status"] == "open" else
                 f'<span class="badge free">vybavené</span><br><span class="mut">{esc(r["by"] or "")} {fmt(parse_ts(r["at"]))}</span>')
        if r["action"]:
            state += f'<br><span class="mut">{esc(r["action"])}</span>'
        row = (f'<tr><td data-l="Kedy">{fmt(r["ts"])}</td><td data-l="Typ">{KIND_LABEL[k]}</td>'
               f'<td data-l="Nahlásil">{who(r["reporter"])}</td><td data-l="Koho / čo">{what}</td>'
               f'<td data-l="Dôvod">{esc(r["reason"]) or "<span class=mut>(bez dôvodu)</span>"}</td>'
               f'<td data-l="Stav">{state}</td><td>{" ".join(btn)}</td></tr>')
        (rows if r["status"] == "open" else done).append(row)
    head = '<tr><th>Kedy</th><th>Typ</th><th>Nahlásil</th><th>Koho / čo</th><th>Dôvod</th><th>Stav</th><th></th></tr>'
    body = (f'<div class="tbl"><table>{head}{"".join(rows)}</table></div>' if rows else '<p class="mut">Žiadne nevybavené nahlásenia.</p>')
    folded = (f'<details><summary>Vybavené ({len(done)})</summary><div class="tbl"><table>{head}{"".join(done)}</table></div></details>'
              if done else "")
    return (f'<section id="reports"><h2>Nahlásenia{f" ({open_n} nevybavené)" if open_n else ""}</h2>{body}{folded}'
            '<p class="mut">Nahlásené správy, miestnosti a používatelia z aplikácií. Obsah šifrovaných správ správca nevidí, '
            'len dôvod, ktorý nahlasovateľ sám napísal. Zmazanie správy pošle do miestnosti označenie „odstránené správcom“; '
            'zmazanie miestnosti ju odstráni aj s históriou. Každá akcia sa zapíše do auditného logu.</p></section>')


async def report_action(req: Request, kind: str, rid: int, what: str):
    s, r = await require_admin(req)
    if r:
        return r
    if await check_csrf(req, s) is None:
        return PlainTextResponse("Neplatný CSRF token.", status_code=403)
    if kind not in KIND_LABEL:
        return PlainTextResponse("Neznámy typ.", status_code=404)
    rep = await find_report(kind, rid)
    if not rep:
        return PlainTextResponse("Nahlásenie neexistuje.", status_code=404)
    ip = client_ip(req)
    detail = {"report": f"{kind}/{rid}", "reporter": rep["reporter"], "target": rep.get("target"),
              "room_id": rep.get("room_id"), "event_id": rep.get("event_id")}
    if what == "resolve":
        set_report_state(kind, rid, "done", s["user"])
        audit(s["user"], ip, "report_resolve", **detail)
    elif what == "reopen":
        set_report_state(kind, rid, "open", s["user"])
        audit(s["user"], ip, "report_reopen", **detail)
    elif what == "block":
        name = local_name(rep.get("target"))
        if not name or name in PROTECTED or name in SERVICE_USERS or name == s["user"]:
            audit(s["user"], ip, "report_block_refused", **detail)
            return PlainTextResponse("Tento účet sa nedá zablokovať.", status_code=403)
        u = (await mas("GET", f"/users/by-username/{urllib.parse.quote(name)}"))["data"]
        if u["attributes"].get("admin"):
            audit(s["user"], ip, "report_block_refused", **detail)
            return PlainTextResponse("Admin účet sa nedá zablokovať.", status_code=403)
        await mas("POST", f"/users/{u['id']}/lock")
        try:
            await synapse_admin("PUT", f"/_synapse/admin/v2/users/@{name}:{SERVER_NAME}", json={"locked": True})
        except Exception as e:  # noqa: BLE001
            audit(s["user"], ip, "synapse_lock_failed", target=name, error=str(e)[:200])
        set_report_state(kind, rid, "done", s["user"], f"zablokovaný {name}")
        audit(s["user"], ip, "report_block", **detail)
    elif what == "delete":
        if kind == "event":
            sender, room, ts = rep["target"], rep["room_id"], None
            async with (await syn_pool()).acquire() as c:
                row = await c.fetchrow("select origin_server_ts from events where event_id = $1", rep["event_id"])
                ts = row["origin_server_ts"] if row else None
                same = await c.fetchval(
                    "select count(*) from events where sender = $1 and room_id = $2 and origin_server_ts = $3 "
                    "and type in ('m.room.message', 'm.room.encrypted')", sender, room, ts) if ts else 0
            if not sender or not ts or not local_name(sender):
                return PlainTextResponse("Správa už neexistuje alebo nie je z tohto servera.", status_code=409)
            if same != 1:
                audit(s["user"], ip, "report_delete_ambiguous", **detail)
                return PlainTextResponse("Správu sa nepodarilo jednoznačne určiť; nič sa nezmazalo.", status_code=409)
            # Synapse admin API: redakcia udalostí odosielateľa v miestnosti v presnom čase (limit 1 = len táto správa)
            j = await synapse_admin("POST", f"/_synapse/admin/v1/user/{urllib.parse.quote(sender)}/redact",
                                    json={"rooms": [room], "before_ts": ts, "after_ts": ts, "limit": 1, "reason": REDACT_REASON})
            status = await wait_redaction(j.get("redact_id"))
            act = "správa zmazaná" if status == "complete" else f"zmazanie správy: {status}"
        elif kind == "room":
            await synapse_admin("DELETE", f"/_synapse/admin/v2/rooms/{urllib.parse.quote(rep['room_id'])}",
                                json={"block": False, "purge": True, "message": REDACT_REASON})
            act = "miestnosť zmazaná"
        else:
            name = local_name(rep["target"])
            if not name or name in PROTECTED or name in SERVICE_USERS:
                return PlainTextResponse("Správy tohto účtu sa nedajú takto zmazať.", status_code=403)
            j = await synapse_admin("POST", f"/_synapse/admin/v1/user/{urllib.parse.quote(rep['target'])}/redact",
                                    json={"rooms": [], "reason": REDACT_REASON})
            status = await wait_redaction(j.get("redact_id"))
            act = f"správy {name} zmazané" if status == "complete" else f"zmazanie správ {name}: {status}"
        set_report_state(kind, rid, "done", s["user"], act)
        audit(s["user"], ip, f"report_delete_{kind}", result=act, **detail)
    else:
        return PlainTextResponse("Neznáma akcia.", status_code=404)
    return RedirectResponse("/admin#reports", status_code=303)


async def wait_redaction(redact_id: str | None, seconds: int = 20) -> str:
    if not redact_id:
        return "neznámy stav"
    for _ in range(seconds * 2):
        j = await synapse_admin("GET", f"/_synapse/admin/v1/user/redact_status/{urllib.parse.quote(redact_id)}")
        if j.get("status") == "complete":
            return "complete" if not j.get("failed_redactions") else "čiastočne zlyhalo"
        if j.get("status") == "failed":
            return "zlyhalo"
        await asyncio.sleep(0.5)
    return "beží na pozadí"


@app.post("/admin/reports/{kind}/{rid}/{what}")
async def report_post(req: Request, kind: str, rid: int, what: str):
    if what not in ("resolve", "reopen", "block", "delete"):
        return PlainTextResponse("Neznáma akcia.", status_code=404)
    return await report_action(req, kind, rid, what)


async def set_lock(req: Request, uid: str, lock: bool):
    s, r = await require_admin(req)
    if r:
        return r
    if await check_csrf(req, s) is None:
        return PlainTextResponse("Neplatný CSRF token.", status_code=403)
    u = (await mas("GET", f"/users/{uid}"))["data"]["attributes"]
    name = u["username"]
    if name in PROTECTED or u.get("admin") or name == s["user"]:
        audit(s["user"], client_ip(req), "lock_refused", target=name)
        return PlainTextResponse(f"Účet {name} sa nedá zablokovať.", status_code=403)
    await mas("POST", f"/users/{uid}/{'lock' if lock else 'unlock'}")
    try:  # rovnako ako scripts/members.sh: príznak locked aj v Synapse
        await synapse_admin("PUT", f"/_synapse/admin/v2/users/@{name}:{SERVER_NAME}", json={"locked": lock})
    except Exception as e:  # noqa: BLE001
        audit(s["user"], client_ip(req), "synapse_lock_failed", target=name, error=str(e)[:200])
    audit(s["user"], client_ip(req), "user_lock" if lock else "user_unlock", target=name)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/users/{uid}/lock")
async def lock_user(req: Request, uid: str):
    return await set_lock(req, uid, True)


@app.post("/admin/users/{uid}/unlock")
async def unlock_user(req: Request, uid: str):
    return await set_lock(req, uid, False)


PW_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"   # bez l/1/o/0/i — čitateľné aj na telefóne


def temp_password() -> str:
    # 4 skupiny po 4 znaky z 31 znakov ≈ 79 bitov náhody, napr. "k7mq-x3pr-9tbn-w4hz"
    return "-".join("".join(secrets.choice(PW_ALPHABET) for _ in range(4)) for _ in range(4))


@app.post("/admin/users/{uid}/password")
async def reset_password(req: Request, uid: str):
    s, r = await require_admin(req)
    if r:
        return r
    if await check_csrf(req, s) is None:
        return PlainTextResponse("Neplatný CSRF token.", status_code=403)
    u = (await mas("GET", f"/users/{uid}"))["data"]["attributes"]
    name = u["username"]
    # rovnaké pravidlá ako pri blokovaní: chránené účty, admini (vrátane servisného) a vlastný účet nie
    if name in PROTECTED or name in SERVICE_USERS or u.get("admin") or name == s["user"] or u.get("deactivated_at"):
        audit(s["user"], client_ip(req), "password_reset_refused", target=name)
        return PlainTextResponse(f"Účtu {name} sa nedá nastaviť nové heslo.", status_code=403)
    pw = temp_password()
    # relácie člena sa zámerne neukončujú (D70) — MAS set-password ich nechá platné
    await mas("POST", f"/users/{uid}/set-password", json={"password": pw, "skip_password_check": True})
    audit(s["user"], client_ip(req), "user_password_reset", target=name)   # nikdy nie samotné heslo
    s["pw_flash"] = {"name": name, "pw": pw}
    return RedirectResponse("/admin#pwreset", status_code=303)


@app.get("/admin/healthz")
async def healthz():
    return PlainTextResponse("ok")


@app.exception_handler(Exception)
async def oops(req: Request, exc: Exception):
    audit("-", client_ip(req), "error", path=req.url.path, error=str(exc)[:300])
    return HTMLResponse(page("Chyba", '<p>Niečo sa nepodarilo. Skúste znova o chvíľu. <a href="/admin">Späť</a></p>'), status_code=500)


async def _gc():
    while True:
        await asyncio.sleep(60)
        t = now()
        for k in [k for k, v in SESSIONS.items() if t - v["created"] > SESSION_TTL or t - v["last"] > SESSION_IDLE]:
            SESSIONS.pop(k, None)
        for k in [k for k, q in HITS.items() if not q or q[-1] < t - 120]:
            HITS.pop(k, None)


@app.on_event("startup")
async def _start():
    os.makedirs(DATA, exist_ok=True)
    asyncio.create_task(_gc())
