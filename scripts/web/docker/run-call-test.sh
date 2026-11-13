#!/usr/bin/env bash
# Spustí scripts/web/call-test.mjs v Linux kontajneri (Playwright) pripojenom do Docker siete "psst".
# Testovací (self-signed) certifikát servera sa pridá do NSS dôvery Chromia — WebRTC overuje TLS
# certifikát TURN servera aj s --ignore-certificate-errors, preto test TURN/TLS na macOS nejde inak.
#   scripts/web/docker/run-call-test.sh <out-dir> <roomId> <label> <u1> <p1> <u2> <p2>   (env PSST_RELAY_ONLY=1)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="$1"; shift
mkdir -p "$OUT"
docker run --rm --network psst --ipc=host \
  -e PSST_RELAY_ONLY="${PSST_RELAY_ONLY:-0}" -e PSST_HOST_IP=172.30.0.10 \
  -v "$ROOT/scripts/web:/work:ro" -v "$OUT:/out" \
  -v "$ROOT/server/data/certbot/conf/live/psst/fullchain.pem:/ca.pem:ro" \
  mcr.microsoft.com/playwright:v1.64.1-noble bash -c '
    set -e
    apt-get update -qq >/dev/null && apt-get install -y -qq libnss3-tools >/dev/null
    mkdir -p $HOME/.pki/nssdb && certutil -d sql:$HOME/.pki/nssdb -N --empty-password
    certutil -d sql:$HOME/.pki/nssdb -A -t "C,," -n psst-test -i /ca.pem
    mkdir -p /tmp/t && cd /tmp/t && cp /work/*.mjs . && npm init -y >/dev/null && npm i -s playwright@1.64.1 >/dev/null
    node call-test.mjs /out "$@"
  ' _ "$@"
