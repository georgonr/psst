#!/usr/bin/env bash
# PSST: publish one build on https://app.psst.pro/download (D59) and verify it over HTTPS.
#
#   scripts/release/upload-download.sh <android|windows|macos> <file> ["what changed"]
#
# - file must follow the naming convention (BUILD.md): psst-<platform>-<YYYYMMDD>-b<N>[-arm64].<apk|msi|dmg>
# - upload over SSH as psst-dl (key restricted to server/scripts/downloads.py; it checks SHA-256, refuses older
#   builds, updates the page and deletes the previous file of the platform)
# - then downloads the file from the public URL and compares SHA-256; any mismatch → exit 1 (build fails)
#
# Key: $PSST_DL_KEY (CI: from secret) or ~/psst-keys/psst-dl-upload. Host: $PSST_DL_HOST (default 204.168.160.131).
set -euo pipefail
PLATFORM="${1:?platform}"; FILE="${2:?file}"; NOTE="${3:-}"
HOST="${PSST_DL_HOST:-204.168.160.131}"
KEY="${PSST_DL_KEY:-$HOME/psst-keys/psst-dl-upload}"
BASE="${PSST_DL_BASE:-https://app.psst.pro/download}"
KNOWN="${PSST_DL_KNOWN_HOSTS:-}"
die() { echo "ERROR: $*" >&2; exit 1; }
[ -f "$FILE" ] || die "missing $FILE"
[ -f "$KEY" ] || die "missing upload key $KEY"
NAME="$(basename "$FILE")"
[[ "$NAME" =~ ^psst-$PLATFORM-([0-9]{8})-b([0-9]+)(-arm64)?\.(apk|msi|dmg)$ ]] || die "$NAME does not follow the naming convention"
DATE="${BASH_REMATCH[1]}"; BUILD="${BASH_REMATCH[2]}"
sha() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }
SHA="$(sha "$FILE")"
SSH_OPTS=(-i "$KEY" -o IdentitiesOnly=yes -o BatchMode=yes -o ServerAliveInterval=30)
if [ -n "$KNOWN" ]; then SSH_OPTS+=(-o UserKnownHostsFile="$KNOWN" -o StrictHostKeyChecking=yes)
else SSH_OPTS+=(-o StrictHostKeyChecking=accept-new); fi
NOTE_B64="$(printf '%s' "$NOTE" | base64 | tr -d '\n')"

echo "==> uploading $NAME ($(du -h "$FILE" | cut -f1), sha256 $SHA) to $BASE"
for i in 1 2 3; do
  if ssh "${SSH_OPTS[@]}" "psst-dl@$HOST" put "$PLATFORM" "$NAME" "$SHA" "$BUILD" "$DATE" "${NOTE_B64:-}" < "$FILE"; then break; fi
  [ "$i" = 3 ] && die "upload failed"
  echo "upload attempt $i failed, retrying"; sleep 10
done

echo "==> verifying over HTTPS"
TMP="$(mktemp)"; trap 'rm -f "$TMP"' EXIT
curl -fsSL --retry 3 -o "$TMP" "$BASE/files/$NAME" || die "download of $BASE/files/$NAME failed"
GOT="$(sha "$TMP")"
[ "$GOT" = "$SHA" ] || die "SHA-256 mismatch after upload: page serves $GOT, build is $SHA"
PAGE_BUILD="$(curl -fsSL "$BASE/latest.json" | python3 -c "import json,sys; e=json.load(sys.stdin).get('$PLATFORM',{}); print(e.get('build'), e.get('sha256'))")"
[ "$PAGE_BUILD" = "$BUILD $SHA" ] || die "latest.json shows '$PAGE_BUILD', expected '$BUILD $SHA'"
curl -fsSL "$BASE/" | grep -q "$NAME" || die "download page does not list $NAME"
echo "OK: $BASE/ serves $PLATFORM b$BUILD ($NAME), SHA-256 verified"
