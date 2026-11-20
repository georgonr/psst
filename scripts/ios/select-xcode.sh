#!/usr/bin/env bash
# PSST (D90): select the PUBLIC (GM) Xcode named in ci/ios-public-xcode.json ("store" build) — by its build number,
# never by "latest" or folder name (on the runner /Applications/Xcode_27.3.app is a BETA, 27C5020n).
#   scripts/ios/select-xcode.sh [allowlist.json]      → sudo xcode-select -s <that Xcode>; fails if not installed
set -euo pipefail
LIST="${1:-$(cd "$(dirname "$0")/../.." && pwd)/ci/ios-public-xcode.json}"
read -r WANT SDKB VER < <(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));b=d['store'];p=d['public'][b];print(b,p['iphoneos_sdk_build'],p['version'])" "$LIST")
echo "wanted: Xcode $VER ($WANT), iOS SDK build $SDKB"
FOUND=""
for x in /Applications/Xcode*.app; do
  dev="$x/Contents/Developer"; [ -x "$dev/usr/bin/xcodebuild" ] || continue
  b=$(DEVELOPER_DIR="$dev" xcodebuild -version | sed -n 's/^Build version //p')
  echo "  $x → $b"
  [ "$b" = "$WANT" ] && [ -z "$FOUND" ] && FOUND="$x"
done
[ -n "$FOUND" ] || { echo "::error::public Xcode $VER ($WANT) is not installed on this runner"; exit 1; }
sudo xcode-select -s "$FOUND"
GOT=$(xcodebuild -version | sed -n 's/^Build version //p'); GOTSDK=$(xcrun --sdk iphoneos --show-sdk-build-version)
[ "$GOT" = "$WANT" ] && [ "$GOTSDK" = "$SDKB" ] || { echo "::error::selected $GOT / SDK $GOTSDK, expected $WANT / $SDKB"; exit 1; }
echo "selected: $FOUND — Xcode $VER ($GOT), iOS SDK $(xcrun --sdk iphoneos --show-sdk-version) ($GOTSDK)"
