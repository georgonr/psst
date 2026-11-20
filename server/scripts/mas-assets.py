#!/usr/bin/env python3
"""PSST (D88): texty registračného formulára MAS — súhlas s Podmienkami vrátane potvrdenia veku 18+.

MAS (natívne, branding.tos_uri) pridá do registrácie povinné políčko „I agree to the Terms and Conditions“. Potvrdenie
veku samostatne nastaviť nejde, preto ho dávame do textu toho istého políčka. Formulár je React; preklady sú
skompilované v assets/<jazyk>-<hash>.js a manifest.json k nim drží SRI hash (integrity). Skript:

  1. skopíruje assets + manifest.json z image MAS (adresár <src>, ktorý pripraví deploy.sh cez `docker cp`),
  2. v každom jazyku nahradí text políčka (sk po slovensky, ostatné jazyky po anglicky) a v sk aj hlášky hCaptcha,
  3. zmaže predkomprimované .br/.gz upravených súborov (MAS by inak poslal starý obsah) a prepočíta integrity.

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


def main(src: str, out: str) -> None:
    tmp = out + ".new"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    shutil.copytree(os.path.join(src, "assets"), os.path.join(tmp, "assets"))
    manifest = json.load(open(os.path.join(src, "manifest.json")))
    patched = 0
    for name, entry in manifest.items():
        if not name.startswith("locales/") or not name.endswith(".json"):
            continue
        lang = name[len("locales/"):-len(".json")]
        path = os.path.join(tmp, "assets", entry["file"])
        text = open(path, encoding="utf-8").read()
        text, n = set_key(text, "terms_of_service", TERMS.get(lang, TERMS["*"]))
        if n != 1:
            sys.exit(f"mas-assets: {entry['file']}: kľúč terms_of_service nájdený {n}×")
        if lang == "sk":
            for k, v in SK_EXTRA.items():
                text, n = set_key(text, k, v)
                if n != 1:
                    sys.exit(f"mas-assets: {entry['file']}: kľúč {k} nájdený {n}×")
        data = text.encode("utf-8")
        open(path, "wb").write(data)
        for ext in (".br", ".gz"):
            if os.path.exists(path + ext):
                os.remove(path + ext)
        entry["integrity"] = "sha384-" + base64.b64encode(hashlib.sha384(data).digest()).decode()
        patched += 1
    if patched == 0:
        sys.exit("mas-assets: v manifeste nie sú žiadne jazyky")
    json.dump(manifest, open(os.path.join(tmp, "manifest.json"), "w"), separators=(",", ":"))
    for root, dirs, files in os.walk(tmp):
        os.chmod(root, 0o755)
        for f in files:
            os.chmod(os.path.join(root, f), 0o644)
    sync(tmp, out)
    shutil.rmtree(tmp)
    print(f"mas-assets: upravených jazykov {patched}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
