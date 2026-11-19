#!/usr/bin/env python3
"""MAS: dynamická registrácia OIDC klientov psst (web, desktop, Android, iOS) musí prejsť politikou MAS;
cudzí klient s nesúvisiacou schémou musí byť odmietnutý. Lokálny stack (domény → 127.0.0.1)."""
import socket, sys, requests, urllib3
urllib3.disable_warnings(); _o = socket.getaddrinfo
socket.getaddrinfo = lambda h, *a, **k: _o("127.0.0.1" if str(h).endswith("psst.pro") else h, *a, **k)
S = requests.Session(); S.verify = False
reg = S.get("https://chat.psst.pro/auth/.well-known/openid-configuration").json()["registration_endpoint"]
base = {"client_uri": "https://app.psst.pro", "logo_uri": "https://app.psst.pro/vector-icons/512.png",
        "tos_uri": "https://app.psst.pro/terms.html", "policy_uri": "https://app.psst.pro/privacy.html",
        "token_endpoint_auth_method": "none", "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"]}
cases = [  # (popis, metadáta, očakávaný HTTP kód)
    ("web app.psst.pro", {**base, "application_type": "web", "redirect_uris": ["https://app.psst.pro/"]}, 201),
    ("desktop pro.psst.app:/vector/webapp/", {**base, "application_type": "native", "redirect_uris": ["pro.psst.app:/vector/webapp/"]}, 201),
    ("android pro.psst.app:/", {**base, "application_type": "native", "redirect_uris": ["pro.psst.app:/"]}, 201),
    ("ios pro.psst.app:/oauth/callback", {**base, "application_type": "native", "redirect_uris": ["pro.psst.app:/oauth/callback"]}, 201),
    ("cudzí klient (odmietnuť)", {**base, "client_uri": "https://evil.example", "application_type": "native", "redirect_uris": ["com.evil:/cb"]}, 400),
]
fails = 0
for name, meta, want in cases:
    code = S.post(reg, json={**meta, "client_name": "psst " + name}).status_code
    ok = code == want; fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}: HTTP {code} (očakávané {want})")
print(f"\n{len(cases) - fails}/{len(cases)} checks passed")
sys.exit(1 if fails else 0)
