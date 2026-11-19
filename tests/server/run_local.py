#!/usr/bin/env python3
"""Run smoke_test.py against a local stack without editing /etc/hosts.

Maps MATRIX/APP/CALL domains to 127.0.0.1 inside this Python process only
(socket.getaddrinfo patch), so TLS SNI and nginx server_name still match.
Usage: ~/.local/psst-venv/bin/python tests/server/run_local.py
"""
import os, runpy, socket, sys
from pathlib import Path

HOSTS = {os.environ.get(k, d) for k, d in (("MATRIX_DOMAIN", "chat.psst.pro"),
                                           ("APP_DOMAIN", "app.psst.pro"),
                                           ("CALL_DOMAIN", "call.psst.pro"),
                                           ("AUTH_DOMAIN", "chat.psst.pro"),
                                           ("TURN_DOMAIN", "call.psst.pro"),
                                           ("SERVER_NAME", "psst.pro"),
                                           ("WWW_DOMAIN", "www.psst.pro"))}
_orig = socket.getaddrinfo

def _gai(host, *a, **kw):
    if isinstance(host, bytes):
        host = host.decode()
    return _orig("127.0.0.1" if host in HOSTS else host, *a, **kw)

socket.getaddrinfo = _gai
here = Path(__file__).resolve().parent
sys.argv = [str(here / "smoke_test.py")] + sys.argv[1:]
runpy.run_path(str(here / "smoke_test.py"), run_name="__main__")
