#!/usr/bin/env python3
"""PSST: inspect a `uiautomator dump` XML file.

Sub-commands:
  texts  <dump.xml>                      print all visible texts / content descriptions
  has    <dump.xml> <text>               exit 0 if a node with exactly this text (or content-desc) exists
  tap    <dump.xml> <text>               print "x y" centre of the first node whose text/content-desc equals <text>
  check  <dump.xml> <label>              check the psst homeserver-lock rules; print violations, exit 1 if any
"""
import re
import sys
import xml.etree.ElementTree as ET

# Anything that would let the user pick / type another homeserver.
FORBIDDEN = [
    (re.compile(r"change (account provider|server|homeserver)", re.I), "server change UI"),
    (re.compile(r"\baccount provider\b", re.I), "account provider selection UI"),
    (re.compile(r"sign in manually", re.I), "manual sign-in (free server choice)"),
    (re.compile(r"^other$", re.I), "'Other' server option"),
    (re.compile(r"\bmatrix\.org\b", re.I), "matrix.org offered"),
    (re.compile(r"element\.io", re.I), "element.io host shown"),
    (re.compile(r"homeserver url|server url|enter.*server", re.I), "server address input"),
]
# Informational / error texts that mention "account provider" but offer no way to pick another server
# (seen live: CI has no reachable chat.macet.eu, and the QR-login screen explains a server capability).
INFO_ALLOW = re.compile(
    r"couldn.t reach this account provider|only available if your account provider supports it|"
    r"about to sign in to chat\.macet\.eu",
    re.I,
)
# Not a lock violation, but reported for branding review.
BRANDING_WARN = re.compile(r"\belement\b", re.I)
DOMAIN = re.compile(r"^(https?://)?[a-z0-9-]+(\.[a-z0-9-]+)+/?$", re.I)


def nodes(path):
    root = ET.parse(path).getroot()
    for n in root.iter("node"):
        yield n


def label(n):
    return [v for v in (n.get("text", ""), n.get("content-desc", "")) if v]


def centre(bounds):
    x1, y1, x2, y2 = map(int, re.findall(r"\d+", bounds))
    return (x1 + x2) // 2, (y1 + y2) // 2


def main():
    cmd, path = sys.argv[1], sys.argv[2]
    if cmd == "texts":
        for n in nodes(path):
            for v in label(n):
                print(v)
        return 0
    if cmd in ("has", "tap"):
        wanted = sys.argv[3]
        for n in nodes(path):
            if wanted in label(n):
                if cmd == "tap":
                    print(*centre(n.get("bounds")))
                return 0
        return 1
    if cmd == "check":
        name = sys.argv[3]
        violations, warnings = [], []
        for n in nodes(path):
            for v in label(n):
                for rx, why in FORBIDDEN:
                    if rx.search(v) and not INFO_ALLOW.search(v):
                        violations.append(f"{name}: {why}: {v!r}")
                if BRANDING_WARN.search(v):
                    warnings.append(f"{name}: text mentions Element: {v!r}")
            cls = n.get("class", "")
            if "EditText" in cls:
                txt = n.get("text", "") + " " + n.get("hint", "")
                if DOMAIN.match(n.get("text", "").strip()) or re.search(r"server", txt, re.I):
                    violations.append(f"{name}: editable server field: {txt.strip()!r}")
        for w in warnings:
            print("WARN " + w)
        for v in violations:
            print("VIOLATION " + v)
        return 1 if violations else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
