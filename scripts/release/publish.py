#!/usr/bin/env python3
"""PSST: publish finished artifacts into dist/<platform>/ according to the naming convention (BUILD.md, D54).

    publish.py <platform> <build> <YYYYMMDD> --note "what changed" <file> [<file> ...]

- every file must already be named psst-<platform>-<YYYYMMDD>-b<build>[-<abi>].<ext>
- everything currently in dist/<platform>/ is moved (never deleted) to dist/archive/<platform>/
- the new files are moved into dist/<platform>/, SHA256SUMS is rewritten
- dist/LATEST.md is regenerated from dist/latest.json (one section per platform)
- refuses build number 0 (local/dev build) and a build number not higher than the current one
"""
import argparse
import datetime
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"
STATE = DIST / "latest.json"
ORDER = ["android", "ios", "windows", "macos", "web"]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def render(state: dict) -> str:
    out = ["# PSST — aktuálne artefakty", "",
           "Generuje `scripts/release/publish.py` (konvencia: BUILD.md → Verzovanie). Staršie verzie: `dist/archive/<platforma>/`.", ""]
    for plat in sorted(state, key=lambda k: (ORDER.index(k) if k in ORDER else 99, k)):
        e = state[plat]
        d = e["date"]
        out += [f"## {plat}", "",
                f"- **build b{e['build']}**, {d[:4]}-{d[4:6]}-{d[6:]} (adresár `dist/{e['dir']}/`)",
                f"- zmena oproti predošlému: {e['note']}", "",
                "| súbor | SHA-256 |", "|---|---|"]
        out += [f"| `{f['name']}` | `{f['sha256']}` |" for f in e["files"]]
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("platform")
    ap.add_argument("build", type=int)
    ap.add_argument("date")
    ap.add_argument("--note", required=True)
    ap.add_argument("--dir", help="dist subdirectory (default: platform; e.g. 'desktop' for windows+macos)")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()

    if a.build <= 0:
        sys.exit("build number must be > 0 (local/dev builds are not published)")
    if not re.fullmatch(r"20\d{6}", a.date):
        sys.exit(f"date must be YYYYMMDD, got {a.date}")
    pat = re.compile(rf"^psst-{re.escape(a.platform)}-{a.date}-b{a.build}(-[a-z0-9_]+)?\.[a-z0-9.]+$")
    files = [Path(f) for f in a.files]
    for f in files:
        if not f.is_file():
            sys.exit(f"missing {f}")
        if not pat.match(f.name):
            sys.exit(f"{f.name} does not match psst-{a.platform}-{a.date}-b{a.build}[-abi].ext")

    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    prev = state.get(a.platform)
    if prev and a.build < prev["build"]:
        sys.exit(f"build b{a.build} is older than the published b{prev['build']}")
    if prev and a.build == prev["build"] and prev["date"] != a.date:
        sys.exit(f"build number b{a.build} already published with another date ({prev['date']})")

    sub = a.dir or a.platform
    target = DIST / sub
    archive = DIST / "archive" / a.platform
    target.mkdir(parents=True, exist_ok=True)
    archive.mkdir(parents=True, exist_ok=True)
    # Archive this platform's current files (in a shared dir like desktop/, only this platform's).
    for old in sorted(target.iterdir()):
        if old.name in ("SHA256SUMS",) or old.name.startswith("."):
            continue
        other = re.match(r"^psst-([a-z]+)-\d{8}-b\d+", old.name)
        if sub != a.platform and other and other.group(1) != a.platform:
            continue   # current file of another platform in a shared dir (desktop/: macos + windows)
        if old.name in {f.name for f in files}:
            continue
        dest = archive / old.name
        if dest.exists():
            dest = archive / f"{old.name}.{datetime.datetime.now():%Y%m%d%H%M%S}"
        shutil.move(str(old), str(dest))
        print(f"archived  {old.name} -> dist/archive/{a.platform}/")

    entries = []
    for f in files:
        dest = target / f.name
        if f.resolve() != dest.resolve():
            shutil.move(str(f), str(dest))
        entries.append({"name": f.name, "sha256": sha256(dest)})
        print(f"published dist/{sub}/{f.name}")

    state[a.platform] = {"build": a.build, "date": a.date, "note": a.note, "dir": sub, "files": entries}
    STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False))
    # tracked copy for the CI check of the download page (scripts/release/check-download-page.py, D59)
    (ROOT / "release").mkdir(exist_ok=True)
    # D110: merge only this platform — a fresh local dist/ (another machine) must not drop the other platforms' entries
    tracked_path = ROOT / "release" / "latest.json"
    tracked = json.loads(tracked_path.read_text()) if tracked_path.exists() else {}
    tracked[a.platform] = state[a.platform]
    tracked_path.write_text(json.dumps(tracked, indent=1, ensure_ascii=False) + "\n")
    # SHA256SUMS covers every current file in the directory
    sums = []
    for plat, e in state.items():
        if e["dir"] == sub:
            sums += [f"{x['sha256']}  {x['name']}" for x in e["files"]]
    (target / "SHA256SUMS").write_text("\n".join(sorted(sums, key=lambda l: l.split()[1])) + "\n")
    (DIST / "LATEST.md").write_text(render(state))
    print("updated   dist/LATEST.md")


if __name__ == "__main__":
    main()
