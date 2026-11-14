#!/usr/bin/env python3
"""Minimal App Store Connect API client (JWT with an API key). Key stays outside the repo.

Usage:  asc.py GET  /v1/bundleIds?filter[identifier]=eu.macet.psst
        asc.py POST /v1/bundleIds '{"data": {...}}'
        asc.py PATCH /v1/apps/ID '{"data": {...}}'
Env:    ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_FILE (default ~/psst-keys/AuthKey_<KEY_ID>.p8)
"""
import json
import os
import sys
import time

import jwt
import requests

KEY_ID = os.environ.get("ASC_KEY_ID", "U4SWSW9CRM")
ISSUER = os.environ.get("ASC_ISSUER_ID", "012f177d-1289-4736-b5a4-99b8f387e4b4")
KEY_FILE = os.environ.get("ASC_KEY_FILE", os.path.expanduser(f"~/psst-keys/AuthKey_{KEY_ID}.p8"))
BASE = "https://api.appstoreconnect.apple.com"


def token() -> str:
    now = int(time.time())
    return jwt.encode({"iss": ISSUER, "iat": now, "exp": now + 1100, "aud": "appstoreconnect-v1"},
                      open(KEY_FILE).read(), algorithm="ES256", headers={"kid": KEY_ID, "typ": "JWT"})


def call(method: str, path: str, body=None):
    url = path if path.startswith("http") else BASE + path
    r = requests.request(method, url, headers={"Authorization": f"Bearer {token()}"},
                         json=body, timeout=60)
    try:
        data = r.json()
    except ValueError:
        data = {"status": r.status_code, "text": r.text[:2000]}
    return r.status_code, data


def get_all(path: str):
    """GET with pagination; returns list of data items."""
    out, url = [], path
    while url:
        code, d = call("GET", url)
        if code != 200:
            raise SystemExit(f"{code} {json.dumps(d)[:2000]}")
        out += d.get("data", [])
        url = d.get("links", {}).get("next")
    return out


if __name__ == "__main__":
    m, p = sys.argv[1].upper(), sys.argv[2]
    b = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
    code, d = call(m, p, b)
    print(code)
    print(json.dumps(d, indent=1, ensure_ascii=False))
    sys.exit(0 if code < 400 else 1)
