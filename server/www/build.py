#!/usr/bin/env python3
"""psst — úvodná stránka (DECISIONS D82): vygeneruje sk/index.html a en/index.html z jednej šablóny.

    python3 server/www/build.py

Stránka je statická, bez externých zdrojov (písmo, obrázky, CSS aj JS sú z vlastného servera), bez cookies a
analytiky. Jazyk: koreň (/) vyberie podľa uloženej voľby alebo jazyka prehliadača (assets/lang.js); voľba sa pamätá
v localStorage prehliadača (nič sa neposiela na server).
Texty: len pravdivé tvrdenia (obsah šifrovaný medzi zariadeniami; metadáta server vidí) — DECISIONS D82.
"""
import html
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = "https://psst.macet.eu"
DOWNLOAD = "https://app.macet.eu/download/"
LOGIN = "https://app.macet.eu/"

ICONS = {
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "call": '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/>',
    "group": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7"/><path d="M18 14a6.5 6.5 0 0 1 3.5 6"/>',
    "file": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 14l2 2 4-4"/>',
    "server": '<rect x="3" y="4" width="18" height="7" rx="2"/><rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 7.5h.01M7 16.5h.01"/>',
    "invite": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
}

T = {
    "sk": {
        "lang": "sk",
        "title": "psst — súkromné správy a hovory",
        "desc": "psst je súkromný messenger pre rodinu, priateľov a malé tímy. Správy, súbory aj hovory sú šifrované medzi zariadeniami. Prístup len na pozvánku.",
        "skip": "Preskočiť na obsah",
        "h1": 'Súkromné správy a hovory. <span>Len pre vašich ľudí.</span>',
        "lead": "psst je messenger pre rodinu, priateľov a malé tímy. Čo si píšete, posielate a hovoríte, je šifrované medzi vašimi zariadeniami – server to nevie prečítať.",
        "dl": "Stiahnuť aplikáciu",
        "login": "Prihlásiť sa",
        "shot_desk": "Aplikácia psst na počítači: rodinná skupina s fotkou a správami",
        "shot_phone": "Aplikácia psst v telefóne: rozhovor dvoch ľudí",
        "feat_h": "Čo psst vie",
        "feat_sub": "Všetko, čo od messengera čakáte, bez reklám a bez cudzích cloudových služieb na vaše správy.",
        "features": [
            ("lock", "Šifrované správy", "Správa sa zašifruje už vo vašom zariadení. Prečítať ju viete len vy a ten, komu píšete."),
            ("call", "Hlasové a video hovory", "Volajte vo dvojici aj v skupine. Aj hovory sú šifrované medzi zariadeniami."),
            ("group", "Skupiny", "Rodina, partia, kolegovia – každý svoju konverzáciu, s odpoveďami, reakciami a zmienkami."),
            ("file", "Súbory a fotky", "Pošlite fotku, video, dokument alebo hlasovú správu. Šifrovane, rovnako ako text."),
            ("server", "Vlastný server", "Správy a súbory sú uložené na našom vlastnom serveri, nie v cloude cudzej firmy."),
            ("invite", "Len na pozvánku", "Účet si vytvorí len ten, kto dostane pozvánku od správcu. Nikto cudzí sa nezaregistruje sám."),
        ],
        "honest_h": "Čo server vidí a čo nie",
        "honest_no_h": "Nevie prečítať",
        "honest_no": ["obsah správ a súborov", "obsah hlasových a video hovorov", "fotky, videá a hlasové správy"],
        "honest_yes_h": "Vidí, ako každý messenger",
        "honest_yes": ["kto s kým a kedy komunikuje", "názvy a členov skupín", "že sa vaše zariadenie pripája – to vidí aj sieť, cez ktorú ste pripojení"],
        "honest_note": "Upozornenia do telefónu doručuje Google alebo Apple – bez obsahu správ.",
        "plat_h": "Kde psst beží",
        "plat_sub": "Na telefóne aj na počítači, rozhovory sa synchronizujú medzi zariadeniami.",
        "platforms": ["Android", "Windows", "macOS", "Web v prehliadači"],
        "soon": "iPhone pripravujeme",
        "invite_h": "Prístup je len na pozvánku",
        "invite_p": "Pozvánku dáva správca psst. Ak ju máte, stiahnite si aplikáciu a pri vytváraní účtu zadajte kód z pozvánky.",
        "other": ("en", "EN", "English"),
        "this_label": "SK",
    },
    "en": {
        "lang": "en",
        "title": "psst — private messages and calls",
        "desc": "psst is a private messenger for family, friends and small teams. Messages, files and calls are encrypted between devices. Invitation only.",
        "skip": "Skip to content",
        "h1": 'Private messages and calls. <span>Just for your people.</span>',
        "lead": "psst is a messenger for family, friends and small teams. What you write, send and say is encrypted between your devices – the server can't read it.",
        "dl": "Download the app",
        "login": "Sign in",
        "shot_desk": "The psst app on a computer: a family group with a photo and messages",
        "shot_phone": "The psst app on a phone: a conversation between two people",
        "feat_h": "What psst does",
        "feat_sub": "Everything you expect from a messenger, without ads and without someone else's cloud holding your messages.",
        "features": [
            ("lock", "Encrypted messages", "A message is encrypted on your device. Only you and the person you write to can read it."),
            ("call", "Voice and video calls", "Call one person or a whole group. Calls are encrypted between devices too."),
            ("group", "Groups", "Family, friends, colleagues – each with their own conversation, with replies, reactions and mentions."),
            ("file", "Files and photos", "Send a photo, video, document or voice message. Encrypted, just like text."),
            ("server", "Our own server", "Messages and files are stored on our own server, not in another company's cloud."),
            ("invite", "Invitation only", "Only people invited by the administrator can create an account. Strangers can't sign up on their own."),
        ],
        "honest_h": "What the server can and can't see",
        "honest_no_h": "It can't read",
        "honest_no": ["the content of messages and files", "the content of voice and video calls", "photos, videos and voice messages"],
        "honest_yes_h": "It can see, like any messenger",
        "honest_yes": ["who talks to whom, and when", "group names and members", "that your device connects – the network you use can see that too"],
        "honest_note": "Phone notifications are delivered by Google or Apple – without message content.",
        "plat_h": "Where psst runs",
        "plat_sub": "On your phone and your computer; conversations stay in sync across devices.",
        "platforms": ["Android", "Windows", "macOS", "Web browser"],
        "soon": "iPhone coming soon",
        "invite_h": "Access is by invitation only",
        "invite_p": "Invitations come from the psst administrator. If you have one, download the app and enter the invitation code when you create your account.",
        "other": ("sk", "SK", "Slovenčina"),
        "this_label": "EN",
    },
}


def page(t):
    e = html.escape
    o_code, o_label, o_name = t["other"]
    feats = "\n".join(
        f'<li><div class="ico" aria-hidden="true"><svg viewBox="0 0 24 24">{ICONS[i]}</svg></div><h3>{e(h)}</h3><p>{e(p)}</p></li>'
        for i, h, p in t["features"])
    plats = "".join(f"<li>{e(p)}</li>" for p in t["platforms"]) + f'<li class="soon">{e(t["soon"])}</li>'
    no = "".join(f"<li>{e(x)}</li>" for x in t["honest_no"])
    yes = "".join(f"<li>{e(x)}</li>" for x in t["honest_yes"])
    lang = t["lang"]
    cur = f"{SITE}/{lang}/"
    cta = f'''<div class="cta"><a class="btn primary" href="{DOWNLOAD}">{e(t["dl"])}</a><a class="btn ghost" href="{LOGIN}">{e(t["login"])}</a></div>'''
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
<body>
<a class="skip" href="#main">{e(t["skip"])}</a>
<div class="wrap">
<header class="top">
<a class="brand" href="/{lang}/" aria-label="psst"><img src="/assets/logo.svg" alt="" width="36" height="36">psst</a>
<nav class="lang" aria-label="{e("Jazyk / Language")}">{langs}</nav>
</header>
<main id="main">
<div class="hero">
<div>
<h1>{t["h1"]}</h1>
<p class="lead">{e(t["lead"])}</p>
{cta}
</div>
<div class="shots">
<img class="desk" src="/assets/img/shot-desktop-{lang}.jpg" width="1280" height="900" alt="{e(t["shot_desk"])}" fetchpriority="high">
<img class="phone" src="/assets/img/shot-phone-{lang}.jpg" width="540" height="1200" alt="{e(t["shot_phone"])}" loading="lazy">
</div>
</div>
<section aria-labelledby="f-h">
<h2 id="f-h">{e(t["feat_h"])}</h2>
<p class="sub">{e(t["feat_sub"])}</p>
<ul class="features">
{feats}
</ul>
</section>
</main>
</div>
<section class="honest" aria-labelledby="h-h">
<div class="wrap">
<h2 id="h-h">{e(t["honest_h"])}</h2>
<div class="cols">
<div class="box"><h3>{e(t["honest_no_h"])}</h3><ul>{no}</ul></div>
<div class="box"><h3>{e(t["honest_yes_h"])}</h3><ul>{yes}</ul></div>
</div>
<p class="sub note">{e(t["honest_note"])}</p>
</div>
</section>
<div class="wrap">
<section aria-labelledby="p-h">
<h2 id="p-h">{e(t["plat_h"])}</h2>
<p class="sub">{e(t["plat_sub"])}</p>
<ul class="platforms">{plats}</ul>
</section>
<section class="final" aria-labelledby="i-h">
<h2 id="i-h">{e(t["invite_h"])}</h2>
<p class="sub">{e(t["invite_p"])}</p>
{cta}
</section>
</div>
<footer><div class="wrap">Powered by GG &amp; TT</div></footer>
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
