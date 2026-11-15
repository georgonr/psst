"""PSST admin — správa pozvánok a členov na https://<APP_DOMAIN>/admin (DECISIONS D56).

- prihlásenie výhradne cez MAS (OIDC authorization code + PKCE), prístup len pre účty s admin právom v MAS
- pozvánky = registračné tokeny MAS (tie isté, ktoré vyžaduje registrácia v appkách), cez MAS admin API
- blokovanie = MAS lock/unlock (+ príznak locked v Synapse, ako scripts/members.sh)
- admin tokeny/tajomstvá len v kontajneri (súbory zo server/secrets), nikdy v prehliadači
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
MATRIX_DOMAIN = os.environ["MATRIX_DOMAIN"]
MAS_PUBLIC = os.environ["MAS_PUBLIC_BASE"].rstrip("/")          # https://chat.macet.eu/auth
MAS_INTERNAL = os.environ.get("MAS_INTERNAL", "http://mas:8080").rstrip("/") + os.environ.get("AUTH_PREFIX", "")
MAS_ADMIN = os.environ.get("MAS_ADMIN_API", "http://mas:8081/api/admin/v1")
SYNAPSE = os.environ.get("SYNAPSE_INTERNAL", "http://synapse:8008")
CLIENT_ID = os.environ["ADMIN_CLIENT_ID"]
CLIENT_SECRET = open("/secrets/admin_client_secret").read().strip()
SYNAPSE_ADMIN_TOKEN_FILE = "/secrets/admin_token"
DB_DSN = "postgresql://psst_admin_ro:{}@postgres/mas".format(open("/secrets/admin_db_password").read().strip())
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
_pool = None


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


async def pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=3)
    return _pool


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


def token_state(a):
    t = dt.datetime.now(dt.timezone.utc)
    if a.get("revoked_at"):
        return "zrušená", "revoked"
    limit = a.get("usage_limit")
    if limit is not None and a.get("times_used", 0) >= limit:
        return "použitá", "used"
    exp = parse_ts(a.get("expires_at"))
    if exp and exp < t:
        return "prepadnutá", "expired"
    return "voľná", "free"


async def registrations():
    """token_id -> [(username, completed_at)] a username -> token"""
    rows = await (await pool()).fetch(
        "select r.username, r.completed_at, t.user_registration_token_id::text as tid, t.token "
        "from user_registrations r join user_registration_tokens t using (user_registration_token_id) "
        "where r.completed_at is not null order by r.completed_at")
    by_token, by_user = defaultdict(list), {}
    for r in rows:
        by_token[r["tid"]].append((r["username"], r["completed_at"]))
        by_user[r["username"]] = r["token"]
    return by_token, by_user


def ulid_to_uuid(ulid: str) -> str:
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    n = 0
    for ch in ulid.upper():
        n = n * 32 + alphabet.index(ch)
    h = f"{n:032x}"
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


# ------------------------------------------------------------------ pages
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


def invite_text(code, expires):
    until = expires.astimezone(dt.timezone(dt.timedelta(hours=1))).strftime("%-d. %-m.") if expires else "odvolania"
    return (f"Pozvánka do psst: stiahni appku, klikni Create an account a zadaj kód {code}. Platí do {until}\n"
            f"Web: https://{APP_DOMAIN}")


@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/", response_class=HTMLResponse)
async def index(req: Request, created: str = ""):
    s, r = await require_admin(req)
    if r:
        return r
    tokens = await mas_all("/user-registration-tokens")
    users = await mas_all("/users")
    by_token, by_user = await registrations()
    with notes_db() as db:
        notes = dict(db.execute("select token_id, note from notes").fetchall())
    try:
        syn = {u["name"]: u for u in (await synapse_admin("GET", "/_synapse/admin/v2/users?limit=1000&guests=false&deactivated=true&locked=true"))["users"]}
    except Exception:
        syn = {}

    out = []
    if created:
        t = next((x for x in tokens if x["id"] == created), None)
        if t:
            a = t["attributes"]
            msg = invite_text(a["token"], parse_ts(a.get("expires_at")))
            out.append(f'<section class="ok"><h2>Pozvánka vytvorená</h2><p>Kód: <code id="code">{esc(a["token"])}</code> '
                       f'<button class="sec" onclick="cp(\'code\',this)">Kopírovať kód</button></p>'
                       f'<div class="msg" id="msg">{esc(msg)}</div><p><button onclick="cp(\'msg\',this)">Kopírovať text na poslanie</button></p></section>')
    out.append(f'''<section><h2>Nová pozvánka</h2><form method="post" action="/admin/invites"><input type="hidden" name="csrf" value="{esc(s["csrf"])}">
<div class="row"><div><label>Počet použití</label><input name="uses" type="number" min="1" max="100" value="1" required></div>
<div><label>Platnosť (dni)</label><input name="days" type="number" min="1" max="365" value="7" required></div>
<div style="flex:2 1 220px"><label>Pre koho (poznámka)</label><input name="note" maxlength="120" placeholder="napr. Jana"></div>
<div style="flex:0 0 auto"><button>Nová pozvánka</button></div></div></form></section>''')

    rows = []
    for t in sorted(tokens, key=lambda x: x["attributes"].get("created_at") or "", reverse=True):
        a = t["attributes"]
        label, cls = token_state(a)
        regs = by_token.get(ulid_to_uuid(t["id"]), [])
        who = ", ".join(f"{esc(u)}" for u, _ in regs) or "—"
        limit = a.get("usage_limit")
        btn = ""
        if cls == "free":
            btn = (f'<form class="inline" method="post" action="/admin/invites/{esc(t["id"])}/revoke" onsubmit="return confirm(\'Zrušiť pozvánku?\')">'
                   f'<input type="hidden" name="csrf" value="{esc(s["csrf"])}"><button class="danger">Zrušiť</button></form>')
        rows.append(f'<tr><td data-l="Kód"><code>{esc(a["token"])}</code></td><td data-l="Pre koho">{esc(notes.get(t["id"], ""))}</td>'
                    f'<td data-l="Vytvorená">{fmt(parse_ts(a.get("created_at")))}</td><td data-l="Platí do">{fmt(parse_ts(a.get("expires_at")), False)}</td>'
                    f'<td data-l="Použitá">{a.get("times_used", 0)}/{limit if limit is not None else "∞"}</td><td data-l="Stav"><span class="badge {cls}">{label}</span></td>'
                    f'<td data-l="Zaregistrovaný">{who}</td><td>{btn}</td></tr>')
    out.append('<section><h2>Pozvánky</h2><div class="tbl"><table><tr><th>Kód</th><th>Pre koho</th><th>Vytvorená</th>'
               '<th>Platí do</th><th>Použitá</th><th>Stav</th><th>Zaregistrovaný</th><th></th></tr>'
               + "".join(rows) + "</table></div></section>")

    rows, gone = [], []
    for u in sorted(users, key=lambda x: x["attributes"].get("created_at") or ""):
        a = u["attributes"]
        name = a["username"]
        if name in SERVICE_USERS:
            continue
        sy = syn.get(f"@{name}:{MATRIX_DOMAIN}", {})
        if a.get("deactivated_at"):
            st, cls = "deaktivovaný", "revoked"
        elif a.get("locked_at"):
            st, cls = "zablokovaný", "locked"
        else:
            st, cls = "aktívny", "free"
        btn = ""
        if name not in PROTECTED and not a.get("admin") and not a.get("deactivated_at"):
            if a.get("locked_at"):
                btn = (f'<form class="inline" method="post" action="/admin/users/{esc(u["id"])}/unlock"><input type="hidden" name="csrf" value="{esc(s["csrf"])}">'
                       f'<button class="sec">Odblokovať</button></form>')
            else:
                btn = (f'<form class="inline" method="post" action="/admin/users/{esc(u["id"])}/lock" onsubmit="return confirm(\'Zablokovať {esc(name)}?\')">'
                       f'<input type="hidden" name="csrf" value="{esc(s["csrf"])}"><button class="danger">Zablokovať</button></form>')
        (gone if a.get("deactivated_at") else rows).append(
            f'<tr><td data-l="Meno"><b>{esc(name)}</b>{" <span class=mut>(admin)</span>" if a.get("admin") else ""}</td>'
            f'<td data-l="Registrácia">{fmt(parse_ts(a.get("created_at")))}</td><td data-l="Pozvánka">{esc(by_user.get(name, "—"))}</td>'
            f'<td data-l="Posledná aktivita">{fmt(sy.get("last_seen_ts"))}</td><td data-l="Stav"><span class="badge {cls}">{st}</span></td><td>{btn}</td></tr>')
    head = '<tr><th>Meno</th><th>Registrácia</th><th>Pozvánka</th><th>Posledná aktivita</th><th>Stav</th><th></th></tr>'
    folded = (f'<details><summary>Deaktivované účty ({len(gone)})</summary><div class="tbl"><table>{head}{"".join(gone)}</table></div></details>'
              if gone else "")
    out.append(f'<section><h2>Členovia</h2><div class="tbl"><table>{head}{"".join(rows)}</table></div>{folded}'
               '<p class="mut">Zablokovanie je vratné: účet sa nedá použiť ani prihlásiť, správy a miestnosti ostávajú.</p></section>')
    out.append("""<script>function cp(id,b){navigator.clipboard.writeText(document.getElementById(id).innerText).then(()=>{const t=b.innerText;b.innerText='Skopírované';setTimeout(()=>b.innerText=t,1500)})}</script>""")
    return HTMLResponse(page("Správa", "".join(out), s["user"], s["csrf"]))


ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


@app.post("/admin/invites")
async def create_invite(req: Request):
    s, r = await require_admin(req)
    if r:
        return r
    form = await check_csrf(req, s)
    if form is None:
        return PlainTextResponse("Neplatný CSRF token.", status_code=403)
    try:
        uses = max(1, min(100, int(form.get("uses", 1))))
        days = max(1, min(365, int(form.get("days", 7))))
    except ValueError:
        return PlainTextResponse("Neplatné hodnoty.", status_code=400)
    note = str(form.get("note", ""))[:120].strip()
    code = "".join(secrets.choice(ALPHABET) for _ in range(4)) + "-" + "".join(secrets.choice(ALPHABET) for _ in range(4))
    expires = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=days)).replace(microsecond=0)
    j = await mas("POST", "/user-registration-tokens",
                  json={"token": code, "usage_limit": uses, "expires_at": expires.isoformat().replace("+00:00", "Z")})
    tid = j["data"]["id"]
    with notes_db() as db:
        db.execute("insert or replace into notes values (?,?,?,?)", (tid, note, s["user"], dt.datetime.now(dt.timezone.utc).isoformat()))
    audit(s["user"], client_ip(req), "invite_create", token_id=tid, code=code, uses=uses, days=days, note=note)
    return RedirectResponse(f"/admin?created={tid}", status_code=303)


@app.post("/admin/invites/{tid}/revoke")
async def revoke_invite(req: Request, tid: str):
    s, r = await require_admin(req)
    if r:
        return r
    if await check_csrf(req, s) is None:
        return PlainTextResponse("Neplatný CSRF token.", status_code=403)
    await mas("POST", f"/user-registration-tokens/{tid}/revoke")
    audit(s["user"], client_ip(req), "invite_revoke", token_id=tid)
    return RedirectResponse("/admin", status_code=303)


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
        await synapse_admin("PUT", f"/_synapse/admin/v2/users/@{name}:{MATRIX_DOMAIN}", json={"locked": lock})
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
