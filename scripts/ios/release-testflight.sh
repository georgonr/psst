#!/usr/bin/env bash
# PSST iOS: ONE command from the Apple account to "build installable in TestFlight".
#
#   scripts/ios/release-testflight.sh            everything (below)
#   scripts/ios/release-testflight.sh --check    only the checklist, changes nothing anywhere
#   options: --ref <psst-ios ref> (default psst)   --no-download   --note "text for dist/LATEST.md"
#
# 0. local prerequisites: keys in ~/psst-keys, Python venv (created if missing), gh login, openssl
# 1. App Store Connect checklist (testflight.py check --fix): API key, bundle IDs eu.macet.psst/.nse/.shareextension
#    and their capabilities (ADDED when missing), Apple Distribution certificate (a new one is ADDED when missing or
#    expiring), app record, App Group. Stops with exact instructions for what only the Account Holder can do.
# 2. App Store profiles (our ACTIVE one is reused, otherwise a new "psst AppStore <id> <date>" is added)
# 3. encrypted GitHub secrets: certificate (.p12 + password), profiles (zip), Team ID, API key
# 4. build number = last TestFlight build + 1 (D54) → GitHub Actions "iOS release (signed)": archive, sign, upload
# 5. waits for the CI run and for App Store Connect processing (VALID)
# 6. internal TestFlight group "psst" + tester Geo M, export compliance, privacy policy URL
# 7. IPA → dist/ios/psst-ios-<YYYYMMDD>-b<N>.ipa (local only; the download page keeps iOS "Coming soon")
#
# The Apple team MHV67VMY8T is shared: only objects named "psst …" are ADDED; nothing existing is modified,
# revoked or deleted (D55). Keys stay in ~/psst-keys and go to GitHub only as encrypted secrets.
# Exit codes: 0 done / checklist OK, 3 = a person (Account Holder) must act first, other = error.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
KEYS="${PSST_KEYS_DIR:-$HOME/psst-keys}"
VENV="${PSST_VENV:-$HOME/.local/psst-venv}"
PY="$VENV/bin/python"
TF="$ROOT/scripts/ios/testflight.py"
REPO="${PSST_REPO:-georgonr/psst}"
TEAM=MHV67VMY8T
KEY_ID=U4SWSW9CRM
REF=psst; DOWNLOAD=1; CHECK=0; NOTE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --ref) REF="$2"; shift ;;
    --no-download) DOWNLOAD=0 ;;
    --check) CHECK=1 ;;
    --note) NOTE="$2"; shift ;;
    -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "unknown option: $1 (see --help)"; exit 2 ;;
  esac
  shift
done
step() { printf '\n\033[1;34m== %s\033[0m\n' "$*"; }
die() { echo "ERROR: $*" >&2; exit "${2:-1}"; }

step "0/7 local prerequisites"
[ -f "$KEYS/AuthKey_$KEY_ID.p8" ] || die "missing $KEYS/AuthKey_$KEY_ID.p8 (App Store Connect API key, role Admin)"
command -v openssl >/dev/null || die "openssl not found"
command -v gh >/dev/null || die "GitHub CLI (gh) not found: brew install gh"
gh auth status >/dev/null 2>&1 || die "gh is not logged in: gh auth login"
gh secret list -R "$REPO" >/dev/null 2>&1 || die "gh cannot manage secrets of $REPO (needs admin access to the repo)"
if ! "$PY" -c 'import jwt, requests, cryptography' 2>/dev/null; then
  echo "creating Python venv $VENV (pyjwt, cryptography, requests)"
  python3 -m venv "$VENV" && "$VENV/bin/pip" -q install pyjwt cryptography requests
fi
export ASC_KEY_ID="$KEY_ID" ASC_KEY_FILE="$KEYS/AuthKey_$KEY_ID.p8" PSST_KEYS_DIR="$KEYS"
echo "ok (keys: $KEYS, repo: $REPO, ref: $REF)"

if [ "$CHECK" = 1 ]; then
  step "1/7 App Store Connect checklist (read-only)"
  "$PY" "$TF" check
  exit $?
fi

step "1/7 App Store Connect checklist (adds missing bundle IDs, capabilities, certificate)"
rc=0; "$PY" "$TF" check --fix || rc=$?
[ "$rc" = 0 ] || exit "$rc"
for f in dist.p12 p12.pass cert-id.txt; do [ -f "$KEYS/ios-dist/$f" ] || die "missing $KEYS/ios-dist/$f"; done

step "2/7 App Store provisioning profiles"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
"$PY" "$TF" profiles "$TMP/profiles"
( cd "$TMP/profiles" && zip -q ../profiles.zip ./*.mobileprovision )

step "3/7 encrypted GitHub secrets (repo $REPO)"
base64 -i "$KEYS/ios-dist/dist.p12" | gh secret set IOS_DIST_CERT_P12_BASE64 -R "$REPO"
gh secret set IOS_DIST_CERT_PASSWORD -R "$REPO" < "$KEYS/ios-dist/p12.pass"
base64 -i "$TMP/profiles.zip" | gh secret set IOS_PROVISIONING_PROFILES_BASE64 -R "$REPO"
gh secret set APPLE_TEAM_ID -R "$REPO" -b "$TEAM"
base64 -i "$KEYS/AuthKey_$KEY_ID.p8" | gh secret set APP_STORE_CONNECT_API_KEY_BASE64 -R "$REPO"
gh secret set APP_STORE_CONNECT_API_KEY_ID -R "$REPO" -b "$KEY_ID"
"$PY" -c 'import sys; sys.path.insert(0, sys.argv[1]); import asc; print(asc.ISSUER)' "$ROOT/scripts/ios" \
  | gh secret set APP_STORE_CONNECT_ISSUER_ID -R "$REPO"
echo "secrets set"

step "4/7 build number + signed CI build with TestFlight upload"
N="$("$PY" "$TF" next-build)"
echo "build number: b$N (last TestFlight build + 1, D54)"
before="$(gh run list -R "$REPO" --workflow ios-release.yml --limit 1 --json databaseId --jq '.[0].databaseId // 0')"
gh workflow run ios-release.yml -R "$REPO" -f ref="$REF" -f build_number="$N" -f upload_to_testflight=true
RUN=""
for _ in $(seq 1 30); do
  sleep 5
  RUN="$(gh run list -R "$REPO" --workflow ios-release.yml --limit 1 --json databaseId --jq '.[0].databaseId // 0')"
  [ "$RUN" != "$before" ] && break
done
[ -n "$RUN" ] && [ "$RUN" != "$before" ] || die "CI run did not start"
echo "CI: https://github.com/$REPO/actions/runs/$RUN"

step "5/7 waiting for CI (archive ≈ 60–90 min) and App Store Connect processing"
gh run watch "$RUN" -R "$REPO" --interval 120 --exit-status >/dev/null || {
  gh run view "$RUN" -R "$REPO" --log-failed | tail -60; die "CI run $RUN failed"; }
"$PY" "$TF" wait-build "$N"

step "6/7 TestFlight group, tester, export compliance, app info"
"$PY" "$TF" testers "$N"
"$PY" "$TF" app-info || echo "(privacy policy URL: set it in App Store Connect → App Information if this failed)"

if [ "$DOWNLOAD" = 1 ]; then
  step "7/7 IPA → dist/ios (local; the download page keeps iOS 'Coming soon')"
  gh run download "$RUN" -R "$REPO" -n psst-ios-ipa -D "$TMP/ipa"
  IPA="$(ls "$TMP"/ipa/psst-ios-*-b"$N".ipa)"
  DATE="$(basename "$IPA" | sed -E 's/^psst-ios-([0-9]{8})-b.*/\1/')"
  python3 "$ROOT/scripts/release/publish.py" ios "$N" "$DATE" --note "${NOTE:-TestFlight build b$N}" "$IPA"
fi

printf '\n\033[1;32mDONE: psst iOS b%s is in TestFlight (internal group "psst").\033[0m\n' "$N"
echo "iPhone: TestFlight app → psst → Install."
