#!/usr/bin/env python3
"""PSST download page https://<APP_DOMAIN>/download — server side (DECISIONS D59).

Runs as the dedicated user `psst-dl`, either as the forced command of its SSH key (CI and local build scripts):

    ssh psst-dl@<server> put <platform> <file name> <sha256> <build> <YYYYMMDD> <note-base64>  < file
    ssh psst-dl@<server> signed macos <build> <sha256>     (D69: build is Developer ID-signed + notarized)
    ssh psst-dl@<server> status
    ssh psst-dl@<server> render

or directly on the server: `sudo -u psst-dl scripts/downloads.py render`.

put: stores the file only if the SHA-256 of what was received matches, refuses an older build, then atomically
updates latest.json and index.html and deletes the previous file of that platform (only current versions stay).
"""
import datetime as dt
import hashlib
import html
import json
import os
import re
import shlex
import sys
import tempfile

ROOT = os.environ.get("PSST_DOWNLOADS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "downloads"))
ROOT = os.path.abspath(ROOT)
FILES = os.path.join(ROOT, "files")
STATE = os.path.join(ROOT, "latest.json")
APP_DOMAIN = os.environ.get("APP_DOMAIN", "app.psst.pro")
PLATFORMS = {
    "android": {"name": "Android", "ext": "apk", "pattern": r"psst-android-(\d{8})-b(\d+)-arm64\.apk"},
    "windows": {"name": "Windows", "ext": "msi", "pattern": r"psst-windows-(\d{8})-b(\d+)\.msi"},
    "macos": {"name": "macOS", "ext": "dmg", "pattern": r"psst-macos-(\d{8})-b(\d+)\.dmg"},
}
MAX_SIZE = 1024 * 1024 * 1024


def die(msg, code=1):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(code)


def load():
    try:
        with open(STATE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def write_atomic(path, data: bytes, mode=0o644):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def human(n):
    if n >= 1024 * 1024:
        return f"{n / 1024 / 1024:.1f} MB"
    return f"{n / 1024:.0f} KB"


# ------------------------------------------------------------------ page
LOGO = ('<svg viewBox="0 0 64 64" width="44" height="44" aria-hidden="true"><rect width="64" height="64" rx="14" fill="#0b0f17"/>'
        '<rect x="12" y="14" width="7" height="36" rx="3.5" fill="#1aa3e0"/><rect x="23" y="20" width="7" height="24" rx="3.5" fill="#e6e8eb"/>'
        '<rect x="34" y="25" width="7" height="14" rx="3.5" fill="#8a919c"/><rect x="45" y="29" width="7" height="6" rx="3" fill="#5b616b"/></svg>')

HOWTO = {
    "android": ("Open the downloaded file. If Android asks, allow your browser to <b>install unknown apps</b> "
                "(Settings → Apps → Special access → Install unknown apps), then tap <b>Install</b>. "
                "New versions install over the old one; your chats stay."),
    "windows": ("Run the installer. If Windows SmartScreen shows <i>“Windows protected your PC”</i>, click "
                "<b>More info</b> → <b>Run anyway</b>."),
    # signed + notarized build (CI ran `signed macos …` after notarization and stapling were verified)
    "macos": "Open the DMG and drag <b>psst</b> to Applications, then open it from Applications.",
}

# D83: dialogs a new member can meet when installing the APK from the browser (Chrome / Samsung Internet, Android 14).
# psst declares no SMS, notification-listener or accessibility access (checked in CI), so Play Protect does not block it.
ANDROID_STEPS = """<div class="warn" lang="sk"><b>Inštalácia na Androide – hlásenia, ktoré môžete vidieť</b>
<ol><li><i>„Tento typ súboru môže poškodiť zariadenie“</i> (prehliadač) → <b>Napriek tomu stiahnuť</b>.</li>
<li><i>„Z bezpečnostných dôvodov nie je v telefóne povolená inštalácia neznámych aplikácií z tohto zdroja“</i> →
<b>Nastavenia</b> → zapnite <b>Povoliť z tohto zdroja</b> → späť.</li>
<li><i>„Skenovať aplikáciu pomocou Play Protect?“</i> alebo <i>„Odoslať aplikáciu na bezpečnostnú kontrolu?“</i> →
<b>Skenovať aplikáciu</b> / <b>Odoslať</b>, potom <b>Inštalovať</b>. Play Protect psst ešte nemusí poznať – je to v poriadku.</li>
<li>Samsung: <i>„Zablokované Automatickým blokovaním“</i> → Nastavenia → Zabezpečenie a súkromie →
<b>Automatické blokovanie</b> dočasne vypnite, nainštalujte a znova zapnite.</li>
<li>Ak sa objaví <i>„Aplikácia bola zablokovaná na ochranu zariadenia“</i>, ťuknite na <b>OK</b>, Play Protect
nevypínajte a dajte vedieť správcovi.</li></ol></div>
<div class="warn" lang="en"><b>Installing on Android – messages you may see</b>
<ol><li><i>“This type of file can harm your device”</i> (browser) → <b>Download anyway</b>.</li>
<li><i>“For your security, your phone is not allowed to install unknown apps from this source”</i> → <b>Settings</b> →
turn on <b>Allow from this source</b> → back.</li>
<li><i>“Scan app with Play Protect?”</i> or <i>“Send app for a security check?”</i> → <b>Scan app</b> / <b>Send</b>,
then <b>Install</b>. Play Protect may not know psst yet – that is fine.</li>
<li>Samsung: <i>“Blocked by Auto Blocker”</i> → Settings → Security and privacy → turn <b>Auto Blocker</b> off for the
install, then back on.</li>
<li>If you see <i>“App blocked to protect your device”</i>, tap <b>OK</b>, keep Play Protect on and tell the
administrator.</li></ol></div>"""

# D69: until the macOS build is signed with a Developer ID certificate and notarized by Apple, Gatekeeper blocks it
# ("Move to Trash"). Shown only while latest.json has no "signed": true for macOS — the next signed build removes it.
MACOS_UNSIGNED = """<div class="warn" lang="sk"><b>Táto verzia pre macOS ešte nie je podpísaná ani notarizovaná Apple</b>, preto ju
macOS pri prvom spustení zablokuje (hlásenie <i>„psst“ nie je možné otvoriť</i> s tlačidlom <i>Presunúť do koša</i>).
Aplikácia je v poriadku — skontrolovať ju môžete podľa SHA-256 vyššie. Ako ju otvoriť:
<ol><li>Otvorte stiahnutý DMG a presuňte <b>psst</b> do priečinka <b>Aplikácie</b>.</li>
<li>Spustite psst z Aplikácií. Keď sa objaví hlásenie, kliknite na <b>Hotovo</b> (nie <i>Presunúť do koša</i>).</li>
<li>Otvorte <b>Systémové nastavenia → Súkromie a bezpečnosť</b>, posuňte sa nadol do časti <b>Bezpečnosť</b>
a pri texte <i>„psst“ bola zablokovaná…</i> kliknite na <b>Napriek tomu otvoriť</b> (Open Anyway). Potvrďte heslom alebo Touch ID.</li>
<li>Spustite psst znova a v okne zvoľte <b>Otvoriť</b>. Ďalej sa už otvára normálne.</li></ol>
Na macOS 14 a starších stačí namiesto krokov 2–4 kliknúť na psst pravým tlačidlom (Control + klik) → <b>Otvoriť</b> → <b>Otvoriť</b>;
na macOS 15 a novších táto cesta už nefunguje, použite Systémové nastavenia. Po stiahnutí novej verzie môže byť potrebné
postup zopakovať. Keď bude aplikácia podpísaná, tento postup odpadne.</div>"""

CSS = """
:root{--bg:#f5f7fa;--card:#fff;--fg:#11151c;--mut:#5f6773;--acc:#0f86c6;--accfg:#fff;--bd:#e2e6eb;--code:#eef1f5}
@media (prefers-color-scheme:dark){:root{--bg:#0b0f17;--card:#141a24;--fg:#e8ebef;--mut:#9aa3ae;--acc:#1aa3e0;--accfg:#04121b;--bd:#232b37;--code:#0f141c}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,Inter,sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:28px 16px 48px}
header{display:flex;align-items:center;gap:14px;margin-bottom:8px}header h1{font-size:28px;margin:0;letter-spacing:-.02em}
.lead{color:var(--mut);margin:4px 0 26px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:16px;padding:20px;display:flex;flex-direction:column;gap:10px}
.card h2{margin:0;font-size:20px}.meta{color:var(--mut);font-size:14px}
.btn{display:inline-block;text-align:center;background:var(--acc);color:var(--accfg);text-decoration:none;font-weight:600;
padding:12px 16px;border-radius:12px}.btn:hover{filter:brightness(1.07)}
.sha{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--code);padding:8px;border-radius:8px;word-break:break-all;color:var(--mut)}
.how{font-size:14px;color:var(--fg)}.soon{color:var(--mut);font-weight:600}
.warn{font-size:14px;background:var(--code);border-left:4px solid #d08a00;padding:10px 12px;border-radius:8px}
.warn ol{margin:6px 0;padding-left:20px}.warn li{margin:3px 0}
footer{margin-top:28px;color:var(--mut);font-size:14px}a{color:var(--acc)}
"""


def render(state):
    cards = []
    for key in ("android", "windows", "macos"):
        p = PLATFORMS[key]
        e = state.get(key)
        if not e:
            cards.append(f'<section class="card"><h2>{p["name"]}</h2><p class="soon">Not available yet</p></section>')
            continue
        d = e["date"]
        cards.append(
            f'<section class="card" id="{key}"><h2>{p["name"]}</h2>'
            f'<div class="meta">Build <b>b{e["build"]}</b> · {d[:4]}-{d[4:6]}-{d[6:]} · {human(e["size"])}</div>'
            f'<a class="btn" href="files/{html.escape(e["file"])}" download>Download for {p["name"]}</a>'
            f'<div class="meta">{html.escape(e["file"])}</div>'
            f'<div class="sha" title="SHA-256">SHA-256: {e["sha256"]}</div>'
            f'<div class="how">{HOWTO[key]}</div>'
            + (ANDROID_STEPS if key == "android" else "")
            + (MACOS_UNSIGNED if key == "macos" and not e.get("signed") else "")
            + '</section>')
    cards.append('<section class="card" id="ios"><h2>iPhone &amp; iPad</h2><p class="soon">Coming soon</p>'
                 '<div class="how">The iOS app is on its way to TestFlight.</div></section>')
    updated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Download psst</title>
<meta name="description" content="Download the psst private messenger for Android, Windows and macOS.">
<style>{CSS}</style></head><body><div class="wrap">
<header>{LOGO}<h1>Download psst</h1></header>
<p class="lead">Private, end-to-end encrypted messenger. Pick your platform — always the latest version.
Prefer the browser? <a href="https://{APP_DOMAIN}/">Open psst on the web</a>.</p>
<div class="grid">{''.join(cards)}</div>
<footer>Updated {updated} · <a href="latest.json">latest.json</a> ·
<a href="https://{APP_DOMAIN}/privacy.html">Privacy</a> · <a href="https://{APP_DOMAIN}/terms.html">Terms</a> ·
<a href="https://github.com/georgonr/psst">Source code (AGPL-3.0)</a></footer>
</div></body></html>"""


def save_and_render(state):
    write_atomic(STATE, (json.dumps(state, indent=1, sort_keys=True) + "\n").encode())
    write_atomic(os.path.join(ROOT, "index.html"), render(state).encode())


# ------------------------------------------------------------------ commands
def cmd_put(platform, name, sha, build, date, note_b64=""):
    import base64
    if platform not in PLATFORMS:
        die(f"unknown platform {platform}")
    m = re.fullmatch(PLATFORMS[platform]["pattern"], name)
    if not m:
        die(f"file name {name} does not follow psst-{platform}-<YYYYMMDD>-b<N>…")
    if m.group(1) != date or m.group(2) != str(int(build)):
        die("build/date do not match the file name")
    if not re.fullmatch(r"[0-9a-f]{64}", sha):
        die("sha256 must be 64 hex chars")
    note = base64.b64decode(note_b64).decode()[:300] if note_b64 else ""
    state = load()
    prev = state.get(platform)
    if prev and int(build) < prev["build"]:
        die(f"b{build} is older than the published b{prev['build']}")
    os.makedirs(FILES, exist_ok=True)
    h, size = hashlib.sha256(), 0
    fd, tmp = tempfile.mkstemp(dir=FILES, prefix=".upload-")
    try:
        with os.fdopen(fd, "wb") as f:
            while True:
                chunk = sys.stdin.buffer.read(1 << 20)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_SIZE:
                    die("file too large")
                h.update(chunk)
                f.write(chunk)
        if h.hexdigest() != sha:
            die(f"SHA-256 mismatch: received {h.hexdigest()}, expected {sha}")
        os.chmod(tmp, 0o644)
        os.replace(tmp, os.path.join(FILES, name))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    state[platform] = {"file": name, "sha256": sha, "build": int(build), "date": date, "size": size, "note": note,
                       "uploaded": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    save_and_render(state)
    # keep only current files
    current = {e["file"] for e in state.values()}
    for f in os.listdir(FILES):
        if not f.startswith(".") and f not in current:
            os.unlink(os.path.join(FILES, f))
            print(f"removed old {f}")
    print(f"published {platform} b{build}: https://{APP_DOMAIN}/download/files/{name}")


def cmd_signed(platform, build, sha):
    """D69: CI marks the published macOS build as Developer ID-signed + notarized (after verifying it), which drops
    the "how to open an unsigned app" note from the page. Only the exact published build/SHA-256 can be marked."""
    if platform != "macos":
        die("only macos builds can be marked as signed")
    state = load()
    e = state.get(platform)
    if not e or e["build"] != int(build) or e["sha256"] != sha:
        die(f"published {platform} is not b{build} with sha256 {sha}")
    e["signed"] = True
    save_and_render(state)
    print(f"marked {platform} b{build} as signed + notarized")


def main(argv):
    if argv and argv[0] == "ssh":   # forced command of the upload key
        argv = shlex.split(os.environ.get("SSH_ORIGINAL_COMMAND", ""))
    if not argv:
        die("usage: put|signed|status|render")
    cmd, rest = argv[0], argv[1:]
    if cmd == "put" and len(rest) in (5, 6):
        cmd_put(*rest)
    elif cmd == "signed" and len(rest) == 3:
        cmd_signed(*rest)
    elif cmd == "status":
        print(json.dumps(load(), indent=1, sort_keys=True))
    elif cmd == "render":
        os.makedirs(FILES, exist_ok=True)
        save_and_render(load())
        print("rendered")
    else:
        die(f"unknown command: {' '.join(argv)[:80]}")


if __name__ == "__main__":
    main(sys.argv[1:])
