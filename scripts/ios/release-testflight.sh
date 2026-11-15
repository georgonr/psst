#!/usr/bin/env bash
# PSST iOS: one command from "App Group exists" to "build installable in TestFlight".
#
#   scripts/ios/release-testflight.sh [--ref psst] [--no-download]
#
# 1. preflight: app record, bundle IDs + capabilities, distribution certificate (App Store Connect API)
# 2. App Store profiles for eu.macet.psst, .nse, .shareextension — fails if group.eu.macet.psst is not assigned
# 3. GitHub secrets: certificate (.p12 + password), profiles (zip), Team ID, API key
# 4. build number = last TestFlight build + 1 → GitHub Actions "iOS release (signed)" with upload to TestFlight
# 5. waits for the CI run and for App Store Connect processing (VALID)
# 6. internal TestFlight group "psst" + tester Geo M, privacy policy URL, export compliance
# 7. IPA → dist/ios/psst-ios-<YYYYMMDD>-b<N>.ipa (older ones → dist/archive/ios/)
#
# Keys stay in ~/psst-keys (never in the repo): AuthKey_U4SWSW9CRM.p8 (API), ios-dist/{dist.p12,p12.pass,cert-id.txt}.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
KEYS="${PSST_KEYS_DIR:-$HOME/psst-keys}"
PY="${PSST_PY:-$HOME/.local/psst-venv/bin/python}"
TF="$PY $ROOT/scripts/ios/testflight.py"
REPO="${PSST_REPO:-georgonr/psst}"
REF=psst; DOWNLOAD=1
while [ $# -gt 0 ]; do
  case "$1" in --ref) REF="$2"; shift ;; --no-download) DOWNLOAD=0 ;; *) echo "unknown: $1"; exit 2 ;; esac; shift
done
step() { printf '\n\033[1;34m== %s\033[0m\n' "$*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

for f in "$KEYS/AuthKey_U4SWSW9CRM.p8" "$KEYS/ios-dist/dist.p12" "$KEYS/ios-dist/p12.pass" "$KEYS/ios-dist/cert-id.txt"; do
  [ -f "$f" ] || die "missing $f"
done
gh auth status >/dev/null 2>&1 || die "gh is not logged in"

step "1/7 App Store Connect preflight"
$TF preflight

step "2/7 provisioning profiles (App Group check)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
$TF profiles "$TMP/profiles"
( cd "$TMP/profiles" && zip -q ../profiles.zip ./*.mobileprovision )

step "3/7 GitHub secrets (encrypted, repo $REPO)"
base64 -i "$KEYS/ios-dist/dist.p12" | gh secret set IOS_DIST_CERT_P12_BASE64 -R "$REPO"
gh secret set IOS_DIST_CERT_PASSWORD -R "$REPO" < "$KEYS/ios-dist/p12.pass"
base64 -i "$TMP/profiles.zip" | gh secret set IOS_PROVISIONING_PROFILES_BASE64 -R "$REPO"
gh secret set APPLE_TEAM_ID -R "$REPO" -b MHV67VMY8T
base64 -i "$KEYS/AuthKey_U4SWSW9CRM.p8" | gh secret set APP_STORE_CONNECT_API_KEY_BASE64 -R "$REPO"
gh secret set APP_STORE_CONNECT_API_KEY_ID -R "$REPO" -b U4SWSW9CRM
gh secret set APP_STORE_CONNECT_ISSUER_ID -R "$REPO" -b 012f177d-1289-4736-b5a4-99b8f387e4b4
echo "secrets set"

step "4/7 build number + CI build"
N="$($TF next-build)"
echo "build number: b$N"
before="$(gh run list -R "$REPO" --workflow ios-release.yml --limit 1 --json databaseId --jq '.[0].databaseId // 0')"
gh workflow run ios-release.yml -R "$REPO" -f ref="$REF" -f build_number="$N" -f upload_to_testflight=true
RUN=""
for _ in $(seq 1 30); do
  sleep 5
  RUN="$(gh run list -R "$REPO" --workflow ios-release.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
  [ "$RUN" != "$before" ] && break
done
[ -n "$RUN" ] && [ "$RUN" != "$before" ] || die "CI run did not start"
echo "CI: https://github.com/$REPO/actions/runs/$RUN"

step "5/7 waiting for CI (archive ≈ 60–90 min) and App Store Connect processing"
gh run watch "$RUN" -R "$REPO" --interval 120 --exit-status >/dev/null || {
  gh run view "$RUN" -R "$REPO" --log-failed | tail -60; die "CI run $RUN failed"; }
$TF wait-build "$N"

step "6/7 TestFlight group, tester, app info"
$TF testers "$N"
$TF app-info || echo "(privacy policy URL: set it in App Store Connect → App Information if this failed)"

if [ "$DOWNLOAD" = 1 ]; then
  step "7/7 IPA → dist/ios"
  gh run download "$RUN" -R "$REPO" -n psst-ios-ipa -D "$TMP/ipa"
  IPA="$(ls "$TMP"/ipa/psst-ios-*-b"$N".ipa)"
  DATE="$(basename "$IPA" | sed -E 's/^psst-ios-([0-9]{8})-b.*/\1/')"
  python3 "$ROOT/scripts/release/publish.py" ios "$N" "$DATE" --note "${PSST_NOTE:-TestFlight build b$N}" "$IPA"
fi

printf '\n\033[1;32mHOTOVO: psst iOS b%s je v TestFlighte (interná skupina „psst").\033[0m\n' "$N"
echo "iPhone: appka TestFlight → psst → Install."
