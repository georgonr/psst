#!/usr/bin/env python3
"""PSST (D88): texty registračného formulára MAS — súhlas s Podmienkami vrátane potvrdenia veku 18+.

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

Výsledok <out>/assets a <out>/manifest.json sa read-only pripoja do kontajnera MAS (compose.yml). Pri novej verzii
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
            if r not in want:
                os.remove(os.path.join(root, f))


def sri(data: bytes) -> str:
    return "sha384-" + base64.b64encode(hashlib.sha384(data).digest()).decode()


def main(src: str, out: str) -> None:
    tmp = out + ".new"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    adir = os.path.join(tmp, "assets")
    shutil.copytree(os.path.join(src, "assets"), adir)
    manifest = json.load(open(os.path.join(src, "manifest.json")))
    tag = "p" + hashlib.sha256(json.dumps([TERMS, SK_EXTRA], sort_keys=True).encode()).hexdigest()[:8]
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
    print(f"mas-assets: upravených jazykov {patched}, nových súborov {len(renamed)} (-{tag})")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
