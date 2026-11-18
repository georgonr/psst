#!/usr/bin/env python3
"""psst — úvodná stránka (DECISIONS D82): vygeneruje sk/index.html a en/index.html z jednej šablóny.

    python3 server/www/build.py

Stránka je statická, bez externých zdrojov (písmo, obrázky, CSS aj JS sú z vlastného servera), bez cookies a
analytiky. Jazyk: koreň (/) vyberie podľa uloženej voľby alebo jazyka prehliadača (assets/lang.js); voľba sa pamätá
v localStorage prehliadača (nič sa neposiela na server).
Minimálna verzia: logo, nadpis, jedna veta, dve tlačidlá, platformy, prepínač SK/EN, pätička. Texty len pravdivé
(obsah šifrovaný medzi zariadeniami; žiadna anonymita) — DECISIONS D82.
"""
import html
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = "https://psst.macet.eu"
DOWNLOAD = "https://app.macet.eu/download/"
LOGIN = "https://app.macet.eu/"

T = {
    "sk": {
        "lang": "sk",
        "title": "psst — súkromné správy a hovory",
        "desc": "Bezpečný komunikátor na správy a hovory, šifrovaný medzi zariadeniami, na vlastnom serveri a s prístupom len na pozvánku.",
        "h1": "Súkromné správy a hovory.",
        "lead": "Bezpečný komunikátor na správy a hovory, šifrovaný medzi zariadeniami, na vlastnom serveri a s prístupom len na pozvánku.",
        "dl": "Stiahnuť aplikáciu",
        "login": "Prihlásiť sa",
        "platforms": "Android · Windows · macOS · web",
        "platforms_label": "Platformy",
    },
    "en": {
        "lang": "en",
        "title": "psst — private messages and calls",
        "desc": "A secure messenger for messages and calls, encrypted between devices, on our own server and by invitation only.",
        "h1": "Private messages and calls.",
        "lead": "A secure messenger for messages and calls, encrypted between devices, on our own server and by invitation only.",
        "dl": "Download the app",
        "login": "Sign in",
        "platforms": "Android · Windows · macOS · web",
        "platforms_label": "Platforms",
    },
}


def page(t):
    e = html.escape
    lang = t["lang"]
    cur = f"{SITE}/{lang}/"
    langs = (f'<a href="/sk/" hreflang="sk" lang="sk" data-lang="sk"{" aria-current=\"true\"" if lang == "sk" else ""}>SK</a>'
             f'<a href="/en/" hreflang="en" lang="en" data-lang="en"{" aria-current=\"true\"" if lang == "en" else ""}>EN</a>')
    return f'''<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(t["title"])}</title>
<meta name="description" content="{e(t["desc"])}">
<meta name="theme-color" content="#0b0f17">
<meta name="color-scheme" content="dark">
<link rel="canonical" href="{cur}">
<link rel="alternate" hreflang="sk" href="{SITE}/sk/">
<link rel="alternate" hreflang="en" href="{SITE}/en/">
<link rel="alternate" hreflang="x-default" href="{SITE}/">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/assets/img/icon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="/assets/img/icon-180.png">
<link rel="manifest" href="/site.webmanifest">
<meta property="og:type" content="website">
<meta property="og:site_name" content="psst">
<meta property="og:title" content="{e(t["title"])}">
<meta property="og:description" content="{e(t["desc"])}">
<meta property="og:url" content="{cur}">
<meta property="og:image" content="{SITE}/assets/img/og-{lang}.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="{"sk_SK" if lang == "sk" else "en_US"}">
<meta name="twitter:card" content="summary_large_image">
<link rel="preload" href="/assets/fonts/inter-latin-700-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/site.css">
<script src="/assets/lang.js" defer></script>
</head>
<body class="min">
<nav class="lang" aria-label="Jazyk / Language">{langs}</nav>
<main class="hero">
<img class="logo" src="/assets/logo.svg" alt="psst" width="64" height="64">
<h1>{e(t["h1"])}</h1>
<p class="lead">{e(t["lead"])}</p>
<div class="cta"><a class="btn primary" href="{DOWNLOAD}">{e(t["dl"])}</a><a class="btn ghost" href="{LOGIN}">{e(t["login"])}</a></div>
<p class="plat" aria-label="{e(t["platforms_label"])}">{e(t["platforms"])}</p>
</main>
<footer>Powered by GG &amp; TT</footer>
</body>
</html>
'''


ROOT = '''<!doctype html>
<html lang="sk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>psst</title>
<meta name="description" content="psst — súkromné správy a hovory / private messages and calls.">
<meta name="color-scheme" content="dark">
<link rel="alternate" hreflang="sk" href="https://psst.macet.eu/sk/">
<link rel="alternate" hreflang="en" href="https://psst.macet.eu/en/">
<link rel="alternate" hreflang="x-default" href="https://psst.macet.eu/">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/site.css">
<script src="/assets/lang.js"></script>
</head>
<body>
<main class="wrap final solo">
<img class="solo-logo" src="/assets/logo.svg" alt="psst" width="72" height="72">
__MSG__
<div class="cta"><a class="btn primary" href="/sk/" hreflang="sk" lang="sk">Slovenčina</a><a class="btn ghost" href="/en/" hreflang="en" lang="en">English</a></div>
</main>
</body>
</html>
'''

NOT_FOUND = (ROOT.replace('<title>psst</title>', '<title>psst – 404</title>')
             .replace('<script src="/assets/lang.js"></script>\n', '')
             .replace('<meta name="description"', '<meta name="robots" content="noindex">\n<meta name="description"')
             .replace('__MSG__', '<p class="sub"><span lang="sk">Táto stránka neexistuje.</span> <span lang="en">This page does not exist.</span></p>'))
ROOT = ROOT.replace('__MSG__\n', '')

if __name__ == "__main__":
    for code, t in T.items():
        os.makedirs(os.path.join(HERE, code), exist_ok=True)
        with open(os.path.join(HERE, code, "index.html"), "w", encoding="utf-8") as f:
            f.write(page(t))
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as f:
        f.write(ROOT)
    with open(os.path.join(HERE, "404.html"), "w", encoding="utf-8") as f:
        f.write(NOT_FOUND)
    print("ok: index.html, 404.html, sk/index.html, en/index.html")
