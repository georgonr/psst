#!/usr/bin/env bash
# PSST (D91): patched mas-cli for server/mas/Dockerfile — GitHub release "mas-<tag>" of georgonr/psst, checked against
# the SHA-256 pinned in git (mas/mas-cli.sha256). Idempotent: does nothing if the local binary already matches.
#   scripts/fetch-mas.sh
set -euo pipefail
cd "$(dirname "$0")/.."
TAG="$(sed -n 's/^# tag: //p' mas/mas-cli.sha256)"
[ -n "$TAG" ] || { echo "mas/mas-cli.sha256: missing '# tag:' line" >&2; exit 1; }
want="$(grep -v '^#' mas/mas-cli.sha256 | awk '{print $1}' | head -1)"
have="$( [ -f mas/mas-cli ] && sha256sum mas/mas-cli | awk '{print $1}' || true)"
if [ "$have" != "$want" ]; then
  tmp="$(mktemp)"
  curl -fsSL "https://github.com/${PSST_REPO:-georgonr/psst}/releases/download/mas-${TAG}/mas-cli" -o "$tmp"
  [ "$(sha256sum "$tmp" | awk '{print $1}')" = "$want" ] || { rm -f "$tmp"; echo "mas-cli: SHA-256 mismatch" >&2; exit 1; }
  install -m 0755 "$tmp" mas/mas-cli; rm -f "$tmp"
fi
echo "mas-cli ${TAG} OK"
