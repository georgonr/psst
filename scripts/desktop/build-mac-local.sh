#!/usr/bin/env bash
# PSST (D110): signed + notarized macOS desktop build ON THIS MAC (same steps as web-desktop.yml → desktop-mac), for
# releases made without GitHub Actions. Needs: Command Line Tools (codesign, notarytool, stapler), pnpm, the web build
# in <psst-web>/apps/web/webapp (built with the same build number), keys in ~/psst-keys (never printed).
#
#   scripts/desktop/build-mac-local.sh <psst-web dir> <build number> <YYYYMMDD>
# Output: dist/desktop/psst-macos-<date>-b<N>.{dmg,zip} (+ verification log in dist/desktop/verify-b<N>.txt)
set -euo pipefail
WEB="$(cd "$1" && pwd)"; N="$2"; D="$3"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
KEYS="${PSST_KEYS_DIR:-$HOME/psst-keys}"
TEAM=MHV67VMY8T; KEY_ID=U4SWSW9CRM
ISSUER="$(python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import re; print(re.search(r"ASC_ISSUER_ID\", \"([^\"]+)", open(sys.argv[1] + "/asc.py").read()).group(1))' "$ROOT/scripts/ios")"
[ -f "$WEB/apps/web/webapp/config.json" ] || { echo "web build missing in $WEB/apps/web/webapp"; exit 2; }
TMP="$(mktemp -d)"; KC="$TMP/psst-sign.keychain-db"; KCP="$(uuidgen)"
cleanup() { security delete-keychain "$KC" 2>/dev/null || true; rm -rf "$TMP"; }
trap cleanup EXIT

security create-keychain -p "$KCP" "$KC"
security set-keychain-settings -lut 21600 "$KC"
security unlock-keychain -p "$KCP" "$KC"
security import "$KEYS/macos-devid/devid.p12" -k "$KC" -P "$(cat "$KEYS/macos-devid/p12.pass")" -T /usr/bin/codesign -T /usr/bin/security >/dev/null
security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$KCP" "$KC" >/dev/null
OLD_KCS="$(security list-keychains -d user | tr -d '"')"
security list-keychains -d user -s "$KC" $OLD_KCS
trap 'security list-keychains -d user -s $OLD_KCS; cleanup' EXIT
ID="$(security find-identity -v -p codesigning "$KC" | grep -o '"Developer ID Application: [^"]*('"$TEAM"')"' | head -1 | tr -d '"')"
[ -n "$ID" ] || { echo "Developer ID identity not found"; exit 1; }
echo "signing identity: $ID"

cd "$WEB/apps/desktop"
grep -q "supportedArchitectures" ../../pnpm-workspace.yaml || cat >> ../../pnpm-workspace.yaml <<EOF
supportedArchitectures:
  os: [current]
  cpu: [x64, arm64]
EOF
pnpm install --frozen-lockfile --filter element-desktop >/dev/null
# the web build goes into apps/desktop/webapp first (as web-desktop.yml does); without it asar-webapp packs an EMPTY
# archive and the app shows nothing (b39 was built that way — never published)
rm -rf webapp webapp.asar && cp -R ../web/webapp webapp
cmp webapp/config.json ../web/psst/config.json
grep -q -- "-b$N " webapp/version || { echo "web build in apps/web/webapp is not b$N: $(cat webapp/version)"; exit 2; }
pnpm run asar-webapp >/dev/null
[ "$(stat -f %z webapp.asar)" -gt 10000000 ] || { echo "webapp.asar too small: $(stat -f %z webapp.asar) bytes"; exit 2; }
node_modules/.bin/asar extract-file webapp.asar config.json && cmp config.json ../web/psst/config.json && rm config.json
export CSC_LINK="$KEYS/macos-devid/devid.p12" CSC_KEY_PASSWORD="$(cat "$KEYS/macos-devid/p12.pass")" CSC_IDENTITY_AUTO_DISCOVERY=true
export APPLE_TEAM_ID="$TEAM" APPLE_API_KEY="$KEYS/AuthKey_$KEY_ID.p8" APPLE_API_KEY_ID="$KEY_ID" APPLE_API_ISSUER="$ISSUER"
rm -rf dist
# never the Nx cache: webapp.asar is not an Nx input, a cached build would ship the previous (or an empty) webapp
NX_SKIP_NX_CACHE=true NX_DAEMON=false pnpm run build --universal --publish never -m dmg zip -c.buildVersion="$N" -c.extraMetadata.psstBuild="$N" -c.extraMetadata.psstBuildDate="$D"
unset CSC_KEY_PASSWORD

DMG="$(ls dist/psst-*.dmg)"
codesign --force --timestamp --keychain "$KC" --sign "$ID" "$DMG"
xcrun notarytool submit "$DMG" --key "$APPLE_API_KEY" --key-id "$KEY_ID" --issuer "$ISSUER" --wait --timeout 90m --output-format json > "$TMP/notary.json"
STATUS="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['status'])" "$TMP/notary.json")"
[ "$STATUS" = Accepted ] || { echo "notarization of the DMG: $STATUS"; exit 1; }
xcrun stapler staple "$DMG"

OUT="$ROOT/dist/desktop"; mkdir -p "$OUT"
APP=dist/mac-universal/psst.app
cmp "$APP/Contents/Resources/webapp.asar" webapp.asar || { echo "the app does not carry this webapp.asar"; exit 2; }
{
  codesign --verify --deep --strict --verbose=2 "$APP" 2>&1
  codesign -dvv "$APP" 2>&1 | grep -E 'Authority|TeamIdentifier|flags|Timestamp'
  spctl -a -vvv -t exec "$APP" 2>&1
  xcrun stapler validate "$APP" 2>&1
  codesign --verify --strict --verbose=2 "$DMG" 2>&1
  spctl -a -vvv -t open --context context:primary-signature "$DMG" 2>&1
  xcrun stapler validate "$DMG" 2>&1
} | tee "$OUT/verify-b$N.txt"
cp "$DMG" "$OUT/psst-macos-$D-b$N.dmg"
cp "$(ls dist/psst-*-mac.zip dist/psst-*.zip 2>/dev/null | head -1)" "$OUT/psst-macos-$D-b$N.zip"
( cd "$OUT" && shasum -a 256 "psst-macos-$D-b$N.dmg" "psst-macos-$D-b$N.zip" )
echo "DONE: $OUT/psst-macos-$D-b$N.dmg"
