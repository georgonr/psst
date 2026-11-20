#!/usr/bin/env python3
"""PSST (D88, D89): značka psst a texty na stránkach MAS.

D89 — značka: serverové preklady (translations/*.json: app.name / app.human_name = „psst“ → titulok karty, „Matrix
ID“ → „meno účtu“) a šablóny base.html + app.html (tmavá téma Compound `cpd-theme-dark`, favicon psst, logo psst nad
obsahom, titulok „psst – <nadpis stránky>“). Šablóny a serverové preklady sa renderujú na serveri → bez problému s
cache. Frontend (React) preklady: „Confirm your Matrix ID“ → meno účtu, „matrix-authentication-service“ → psst.

D88 — súhlas s Podmienkami vrátane potvrdenia veku 18+:

MAS (natívne, branding.tos_uri) pridá do registrácie povinné políčko „I agree to the Terms and Conditions“. Potvrdenie
veku samostatne nastaviť nejde, preto ho dávame do textu toho istého políčka. Formulár je React; preklady sú
skompilované v assets/<jazyk>-<hash>.js a manifest.json k nim drží SRI hash (integrity). Skript:

  1. skopíruje assets + manifest.json z image MAS (adresár <src>, ktorý pripraví deploy.sh cez `docker cp`),
  2. v každom jazyku nahradí text políčka (sk po slovensky, ostatné jazyky po anglicky) a v sk aj hlášky hCaptcha,
  3. upravené súbory zapíše pod NOVÝM menom (…-p<tag>.js) — MAS posiela assets s `Cache-Control: immutable,
     max-age=1 rok`, prehliadač so starou verziou v cache by inak pri novom SRI hashi súbor odmietol (Chrome si to
     zapamätá aj pre import()) a stránky MAS by ukazovali surové kľúče prekladov. Premenuje sa aj každý súbor, ktorý
     na premenovaný súbor odkazuje (mapa jazykov v mountIsland, vstupné body…), až po manifest. Pôvodné súbory ostanú
     bez zmeny (aj .br/.gz), aby rozbehnuté stránky so starými odkazmi fungovali,
  4. v manifeste nastaví nové mená a prepočíta integrity.

Výsledok <out>/assets, <out>/manifest.json, <out>/templates a <out>/translations sa read-only pripoja do kontajnera
MAS (compose.yml) na predvolené cesty /usr/local/share/mas-cli/…. Pri novej verzii
MAS sa všetko zopakuje z nového image; ak sa kľúč nenájde, skript zlyhá (deploy.sh to ohlási).

  python3 scripts/mas-assets.py <src> <out>
"""
import base64
import hashlib
import json
import os
import re
import shutil
import sys

TERMS = {
    "sk": "Mám aspoň 18 rokov a súhlasím s <a>Podmienkami používania</a>",
    "*": "I am at least 18 years old and I agree to the <a>Terms and Conditions</a>",
}
SK_EXTRA = {
    "captcha_incomplete": "Pred pokračovaním dokončite overenie hCaptcha",
    "captcha_loading": "Overenie hCaptcha sa ešte načítava, chvíľu počkajte",
}
# D89: zmazanie účtu pýta potvrdenie „Matrix ID“ → meno účtu (vo formáte @meno:psst.pro)
FRONT_KEYS = {
    "sk": {"mxid_label": "Potvrďte meno svojho účtu ({{ mxid }})",
           "mxid_mismatch": "Hodnota sa nezhoduje s menom vášho účtu"},
    "*": {"mxid_label": "Confirm your account name ({{ mxid }})",
          "mxid_mismatch": "This value does not match your account name"},
}
NAME_REPLACE = {"matrix-authentication-service": "psst", "Matrix Authentication Service": "psst",
                # dialóg zmazania účtu: žargón „(MXID)“ preč; psst nepoužíva identity server → bod by nebol pravdivý
                "your username (MXID)": "your username",
                "<item>You will be removed from the identity server, and no one will be able to find you with your "
                "email or phone number</item>": ""}
SERVER_MXID = {"sk": "Meno účtu", "en": "Account name"}

# D89: šablóny — tmavá téma, favicon a logo psst, titulok „psst – <nadpis>“ (nadpis h1 stránky; SPA účtu ho mení)
LOGO_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" aria-hidden="true"><rect width="64" '
            'height="64" rx="14" fill="#0b0f17"/><rect x="12" y="14" width="7" height="36" rx="3.5" fill="#1aa3e0"/>'
            '<rect x="23" y="20" width="7" height="24" rx="3.5" fill="#e6e8eb"/><rect x="34" y="25" width="7" '
            'height="14" rx="3.5" fill="#8a919c"/><rect x="45" y="29" width="7" height="6" rx="3" fill="#5b616b"/></svg>')
BRAND_HEAD = (
    '\n    <meta name="theme-color" content="#101317">'
    '\n    <link rel="icon" href="https://psst.pro/favicon.svg" type="image/svg+xml">'
    '\n    <link rel="icon" href="https://psst.pro/assets/img/icon-32.png" sizes="32x32" type="image/png">'
    '\n    <link rel="apple-touch-icon" href="https://psst.pro/assets/img/icon-180.png">'
    '\n    <style>html.cpd-theme-dark,html.cpd-theme-dark body{background:var(--cpd-color-bg-canvas-default,#101317);'
    'color-scheme:dark}.psst-brand{display:flex;align-items:center;justify-content:center;gap:10px;'
    'padding:24px 0 8px;font:600 24px/1 Inter,system-ui,sans-serif;letter-spacing:.5px;'
    'color:var(--cpd-color-text-primary,#ebeef2)}.psst-brand svg{width:40px;height:40px}</style>'
    '\n    <script>(function(){var n="psst";function t(){var h=document.querySelector("h1");'
    'var s=h&&h.textContent.replace(/\\s+/g," ").trim();var v=s&&s!==n?n+" \\u2013 "+s:n;'
    'if(document.title!==v)document.title=v;}document.addEventListener("DOMContentLoaded",t);'
    'new MutationObserver(t).observe(document.documentElement,{childList:true,subtree:true,characterData:true});'
    '})();</script>')
BRAND_BAR = '\n    <div class="psst-brand">' + LOGO_SVG + '<span>psst</span></div>'
TEMPLATE_PATCHES = {
    "base.html": [
        ('<html lang="{{ lang }}">', '<html lang="{{ lang }}" class="cpd-theme-dark">'),
        ('<title>{% block title %}{{ _("app.name") }}{% endblock title %}</title>',
         '<title>{% block title %}{{ _("app.name") }}{% endblock title %}</title>' + BRAND_HEAD),
        ('<div class="layout-container{% if consent_page is defined %} consent{% endif %}">',
         '<div class="layout-container{% if consent_page is defined %} consent{% endif %}">' + BRAND_BAR),
    ],
    "app.html": [
        ('<html lang="{{ lang }}">', '<html lang="{{ lang }}" class="cpd-theme-dark">'),
        ('<title>{{ _("app.name") }}</title>', '<title>{{ _("app.name") }}</title>' + BRAND_HEAD),
        ('<body>', '<body>' + BRAND_BAR),
    ],
}
GENERATED = re.compile(r"-p[0-9a-f]{8}\.(js|css)$")


def set_key(text: str, key: str, value: str) -> tuple[str, int]:
    assert '"' not in value and "'" not in value and "\\" not in value and "`" not in value
    return re.subn(r'("%s":")((?:[^"\\]|\\.)*)(")' % re.escape(key), lambda m: m.group(1) + value + m.group(3), text)


def sync(src: str, dst: str) -> None:
    """Obsah <src> do <dst> NA MIESTE (adresár je bind-mount bežiaceho kontajnera — nový inode by MAS nevidel)."""
    os.makedirs(dst, mode=0o755, exist_ok=True)
    want = set()
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        os.makedirs(os.path.join(dst, rel), mode=0o755, exist_ok=True)
        for f in files:
            r = os.path.normpath(os.path.join(rel, f))
            want.add(r)
            a, b = os.path.join(src, r), os.path.join(dst, r)
            if not os.path.exists(b) or open(a, "rb").read() != open(b, "rb").read():
                with open(a, "rb") as fa, open(b, "wb") as fb:
                    fb.write(fa.read())
            os.chmod(b, 0o644)
    for root, dirs, files in os.walk(dst, topdown=False):
        for f in files:
            r = os.path.normpath(os.path.join(os.path.relpath(root, dst), f))
            if r not in want and not GENERATED.search(f):   # staršie generácie nechať (rozbehnuté stránky)
                os.remove(os.path.join(root, f))


def sri(data: bytes) -> str:
    return "sha384-" + base64.b64encode(hashlib.sha384(data).digest()).decode()


def walk_strings(o, fn):
    if isinstance(o, dict):
        return {k: walk_strings(v, fn) for k, v in o.items()}
    if isinstance(o, list):
        return [walk_strings(v, fn) for v in o]
    return fn(o) if isinstance(o, str) else o


def patch_server(src: str, tmp: str) -> int:
    """D89: šablóny a serverové preklady (renderujú sa na serveri, cache prehliadača ich neovplyvní)."""
    tdir, trdir = os.path.join(tmp, "templates"), os.path.join(tmp, "translations")
    shutil.copytree(os.path.join(src, "templates"), tdir)
    shutil.copytree(os.path.join(src, "translations"), trdir)
    for name, pairs in TEMPLATE_PATCHES.items():
        path = os.path.join(tdir, name)
        text = open(path, encoding="utf-8").read()
        for old, new in pairs:
            if text.count(old) != 1:
                sys.exit(f"mas-assets: šablóna {name}: „{old[:50]}“ nájdené {text.count(old)}×")
            text = text.replace(old, new)
        open(path, "w", encoding="utf-8").write(text)
    n = 0
    for f in sorted(os.listdir(trdir)):
        if not f.endswith(".json"):
            continue
        lang = f[:-5]
        path = os.path.join(trdir, f)
        d = json.load(open(path, encoding="utf-8"))

        def fix(v: str) -> str:
            for a, b in NAME_REPLACE.items():
                v = v.replace(a, b)
            return v
        d = walk_strings(d, fix)
        app = d.setdefault("app", {})
        app["name"] = "psst"
        app["human_name"] = "psst"
        if lang in SERVER_MXID:
            d.setdefault("common", {})["mxid"] = SERVER_MXID[lang]
        json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        n += 1
    if n == 0:
        sys.exit("mas-assets: žiadne serverové preklady")
    return n


def main(src: str, out: str) -> None:
    tmp = out + ".new"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    adir = os.path.join(tmp, "assets")
    shutil.copytree(os.path.join(src, "assets"), adir)
    manifest = json.load(open(os.path.join(src, "manifest.json")))
    tag = "p" + hashlib.sha256(json.dumps([TERMS, SK_EXTRA, FRONT_KEYS, NAME_REPLACE], sort_keys=True).encode()).hexdigest()[:8]
    n_server = patch_server(src, tmp)
    content: dict[str, str] = {}      # basename -> nový obsah (len zmenené súbory)
    patched = 0
    for name, entry in manifest.items():
        if not name.startswith("locales/") or not name.endswith(".json"):
            continue
        lang = name[len("locales/"):-len(".json")]
        text = open(os.path.join(adir, entry["file"]), encoding="utf-8").read()
        text, n = set_key(text, "terms_of_service", TERMS.get(lang, TERMS["*"]))
        if n != 1:
            sys.exit(f"mas-assets: {entry['file']}: kľúč terms_of_service nájdený {n}×")
        if lang == "sk":
            for k, v in SK_EXTRA.items():
                text, n = set_key(text, k, v)
                if n != 1:
                    sys.exit(f"mas-assets: {entry['file']}: kľúč {k} nájdený {n}×")
        for k, v in FRONT_KEYS.get(lang, FRONT_KEYS["*"]).items():
            text, n = set_key(text, k, v)
            if n != 1 and lang in ("en", "sk"):
                sys.exit(f"mas-assets: {entry['file']}: kľúč {k} nájdený {n}×")
        for a, b in NAME_REPLACE.items():
            text = text.replace(a, b)
        content[entry["file"]] = text
        patched += 1
    if patched == 0:
        sys.exit("mas-assets: v manifeste nie sú žiadne jazyky")

    # uzáver: každý .js/.css, ktorý odkazuje na premenovaný súbor, sa tiež mení → aj on dostane nové meno
    files = {f: open(os.path.join(adir, f), encoding="utf-8").read()
             for f in os.listdir(adir) if f.endswith((".js", ".css"))}
    renamed = set(content)
    while True:
        more = {f for f, t in files.items() if f not in renamed and any(r in t for r in renamed)}
        if not more:
            break
        renamed |= more
    new_name = {f: f[: f.rindex(".")] + "-" + tag + f[f.rindex("."):] for f in renamed}
    for f in renamed:
        t = content.get(f, files[f])
        for old in sorted(new_name, key=len, reverse=True):
            t = t.replace(old, new_name[old])
        data = t.encode("utf-8")
        with open(os.path.join(adir, new_name[f]), "wb") as fh:
            fh.write(data)
    for entry in manifest.values():
        f = entry.get("file")
        if f in new_name:
            entry["file"] = new_name[f]
            entry["integrity"] = sri(open(os.path.join(adir, new_name[f]), "rb").read())
        for key in ("css", "assets"):
            if entry.get(key):
                entry[key] = [new_name.get(x, x) for x in entry[key]]
    json.dump(manifest, open(os.path.join(tmp, "manifest.json"), "w"), separators=(",", ":"))
    for root, dirs, fs in os.walk(tmp):
        os.chmod(root, 0o755)
        for f in fs:
            os.chmod(os.path.join(root, f), 0o644)
    sync(tmp, out)
    shutil.rmtree(tmp)
    print(f"mas-assets: upravených jazykov {patched}, nových súborov {len(renamed)} (-{tag}), "
          f"serverových prekladov {n_server}, šablóny {', '.join(TEMPLATE_PATCHES)}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
