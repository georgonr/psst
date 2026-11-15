#!/usr/bin/env python3
"""PSST: fail if https://app.macet.eu/download is behind the latest published build (D59).

  check-download-page.py [manifest.json]

manifest: dist/latest.json (local, default when it exists) or release/latest.json (tracked in git, used in CI).
For android, windows and macos: the page must show the same build with the same SHA-256, or a newer build.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = "https://app.macet.eu/download/latest.json"
# dist/latest.json has several files per platform; the page carries one of them
PAGE_FILE = {"android": "-arm64.apk", "windows": ".msi", "macos": ".dmg"}


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else (ROOT / "dist/latest.json" if (ROOT / "dist/latest.json").exists() else ROOT / "release/latest.json")
    local = json.loads(src.read_text())
    page = json.loads(subprocess.run(["curl", "-fsSL", "--max-time", "30", PAGE], check=True, capture_output=True).stdout)
    bad = 0
    for plat, suffix in PAGE_FILE.items():
        e = local.get(plat)
        if not e:
            continue
        f = next((x for x in e["files"] if x["name"].endswith(suffix)), None)
        p = page.get(plat)
        if not f:
            continue
        if not p:
            print(f"BEHIND  {plat}: page has nothing, latest is b{e['build']} ({f['name']})")
            bad += 1
        elif p["build"] < e["build"]:
            print(f"BEHIND  {plat}: page b{p['build']}, latest b{e['build']} ({f['name']})")
            bad += 1
        elif p["build"] == e["build"] and p["sha256"] != f["sha256"]:
            print(f"MISMATCH {plat} b{e['build']}: page {p['sha256'][:16]}… local {f['sha256'][:16]}…")
            bad += 1
        else:
            print(f"OK      {plat}: page b{p['build']} ({p['file']})" + ("" if p["build"] == e["build"] else f" — newer than {src.name} b{e['build']}"))
    print(f"compared {src} with {PAGE}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
