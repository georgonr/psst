#!/usr/bin/env bash
# PSST: download a "Web + Desktop" CI run and publish it into dist/ by the naming convention (BUILD.md "Verzovanie").
#
#   PSST_NOTE="what changed" scripts/release/fetch-web-desktop.sh <run-id> [--release]
#
#   dist/desktop/psst-macos-<YYYYMMDD>-b<N>.dmg|.zip, psst-windows-<YYYYMMDD>-b<N>.msi|-setup.exe
#   dist/web/psst-web-<YYYYMMDD>-b<N>.tar.gz
#   older files → dist/archive/<platform>/, dist/LATEST.md updated.
#   --release  also creates GitHub release web-b<N> with psst-web.tar.gz (server: sudo scripts/fetch-web.sh)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REPO="${PSST_REPO:-georgonr/psst}"
RUN="${1:?usage: $0 <run-id> [--release]}"; REL="${2:-}"
[ -n "${PSST_NOTE:-}" ] || { echo "set PSST_NOTE=\"what changed\""; exit 1; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
for n in psst-web-dist psst-desktop-macos psst-desktop-windows; do
  for i in 1 2 3 4; do gh run download "$RUN" -R "$REPO" -n "$n" -D "$TMP/$n" && break; rm -rf "${TMP:?}/$n"; sleep 5; done
done
WEB="$(ls "$TMP"/psst-web-dist/psst-web-*-b*.tar.gz)"
N="$(basename "$WEB" | sed -E 's/^psst-web-[0-9]{8}-b([0-9]+)\.tar\.gz$/\1/')"
D="$(basename "$WEB" | sed -E 's/^psst-web-([0-9]{8})-b.*/\1/')"
PUB="python3 $ROOT/scripts/release/publish.py"
$PUB web "$N" "$D" --note "$PSST_NOTE" "$WEB"
$PUB macos "$N" "$D" --dir desktop --note "$PSST_NOTE" "$TMP"/psst-desktop-macos/psst-macos-*
$PUB windows "$N" "$D" --dir desktop --note "$PSST_NOTE" "$TMP"/psst-desktop-windows/psst-windows-*
if [ "$REL" = "--release" ]; then
  cp "$ROOT/dist/web/$(basename "$WEB")" "$TMP/psst-web.tar.gz"
  gh release create "web-b$N" -R "$REPO" --title "PSST web b$N ($D)" --notes "$PSST_NOTE" \
    "$TMP/psst-web.tar.gz" "$ROOT/dist/web/$(basename "$WEB")"
  echo "release web-b$N created — on the server: cd /opt/psst/server && sudo scripts/fetch-web.sh"
fi
