#!/usr/bin/env bash
# PSST: sign the UNSIGNED Android release artifacts built by CI with the local psst release key.
#
# The release key never leaves this machine (no GitHub secrets, no artifacts, no commits).
#
# Usage:
#   scripts/android/sign-release.sh <dir-with-unsigned-artifacts> [output-dir]
#   scripts/android/sign-release.sh --run <github-run-id>          [output-dir]
#
#   <dir>      directory containing *-unsigned.apk and/or *.aab (searched recursively),
#              e.g. the result of `gh run download <id> -R georgonr/psst -n psst-android-apks-unsigned`.
#   --run ID   download the artifacts "psst-android-apks-unsigned" and "psst-android-aab-unsigned" of the
#              GitHub Actions run ID (repo $PSST_REPO, default georgonr/psst) into a temporary directory first.
#   output-dir default: <repo>/dist/android (gitignored). With the default, the result is published via
#              scripts/release/publish.py: older files -> dist/archive/android/, dist/LATEST.md updated.
#   PSST_NOTE  one sentence "what changed" for dist/LATEST.md (required when publishing to dist/android).
#
# File names (BUILD.md "Verzovanie"): psst-android-<YYYYMMDD>-b<build>-<abi>.apk, psst-android-<YYYYMMDD>-b<build>.aab
# — build number and date are read from the APK's versionName "26.11.0-b<build> (YYYY-MM-DD)".
#
# Environment (optional):
#   PSST_KEYS_DIR   default ~/psst-keys   (psst-release.jks + keystore.properties, chmod 600)
#   PSST_TOOLS_DIR  default ~/.psst-tools (Android build-tools are downloaded here if missing)
#   JAVA_HOME       default /usr/local/opt/openjdk@17 (keytool, jarsigner, java for apksigner)
#
# Steps: zipalign (4-byte, 16 KB page alignment for .so) + apksigner (v2/v3 scheme) for every APK,
# jarsigner (SHA-256) for the AAB, then verification and SHA256SUMS.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
KEYS_DIR="${PSST_KEYS_DIR:-$HOME/psst-keys}"
TOOLS_DIR="${PSST_TOOLS_DIR:-$HOME/.psst-tools}"
JAVA_HOME="${JAVA_HOME:-/usr/local/opt/openjdk@17}"
export JAVA_HOME PATH="$JAVA_HOME/bin:$PATH"
BT_VERSION="37.0.0"
BT_ZIP="build-tools_r37_macosx.zip"
BT_SHA1="eb080751b2b2028eb3604f571027d6f7b3c46321"
BT_DIR="$TOOLS_DIR/build-tools-$BT_VERSION"

die() { echo "ERROR: $*" >&2; exit 1; }

# ---------- arguments ----------
TMP_DL=""
cleanup() { [ -n "$TMP_DL" ] && rm -rf "$TMP_DL"; }
trap cleanup EXIT
if [ "${1:-}" = "--run" ]; then
  [ -n "${2:-}" ] || die "--run needs a run id"
  RUN_ID="$2"; shift 2
  TMP_DL="$(mktemp -d)"
  for name in psst-android-apks-unsigned psst-android-aab-unsigned; do
    gh run download "$RUN_ID" -R "${PSST_REPO:-georgonr/psst}" -n "$name" -D "$TMP_DL/$name"
  done
  IN_DIR="$TMP_DL"
else
  [ -n "${1:-}" ] || die "usage: $0 <dir-with-unsigned-artifacts>|--run <id> [output-dir]"
  IN_DIR="$1"; shift
fi
PUBLISH=0
if [ -n "${1:-}" ]; then OUT_DIR="$1"; else OUT_DIR="$(mktemp -d)"; PUBLISH=1; fi
[ "$PUBLISH" = 0 ] || [ -n "${PSST_NOTE:-}" ] || die "set PSST_NOTE=\"what changed\" (one sentence for dist/LATEST.md)"
[ -d "$IN_DIR" ] || die "input directory $IN_DIR not found"

# ---------- disk space ----------
avail_kb="$(df -k "$HOME" | awk 'NR==2 {print $4}')"
echo "Free disk space in \$HOME: $((avail_kb / 1024)) MB"
[ "$avail_kb" -gt 1048576 ] || die "less than 1 GB free, aborting"

# ---------- key material ----------
PROPS="$KEYS_DIR/keystore.properties"
[ -f "$PROPS" ] || die "$PROPS not found"
perm="$(stat -f '%Lp' "$PROPS" 2>/dev/null || stat -c '%a' "$PROPS")"
[ "$perm" = "600" ] || die "$PROPS must be chmod 600 (is $perm)"
prop() { grep -E "^$1=" "$PROPS" | head -1 | cut -d= -f2-; }
KS_FILE="$(prop storeFile)"; KS_FILE="${KS_FILE:-$KEYS_DIR/psst-release.jks}"
KEY_ALIAS="$(prop keyAlias)"
# Passwords only ever live in environment variables of this process, never on a command line or in output.
PSST_STORE_PASS="$(prop storePassword)"
PSST_KEY_PASS="$(prop keyPassword)"
export PSST_STORE_PASS PSST_KEY_PASS
[ -f "$KS_FILE" ] || die "keystore $KS_FILE not found"

# ---------- build-tools (zipalign, apksigner, aapt2) ----------
if [ ! -x "$BT_DIR/apksigner" ]; then
  echo "Downloading Android build-tools $BT_VERSION (~80 MB) to $TOOLS_DIR"
  mkdir -p "$TOOLS_DIR"
  curl -fL -o "$TOOLS_DIR/$BT_ZIP" "https://dl.google.com/android/repository/$BT_ZIP"
  echo "$BT_SHA1  $TOOLS_DIR/$BT_ZIP" | shasum -a 1 -c -
  unzip -q -o "$TOOLS_DIR/$BT_ZIP" -d "$TOOLS_DIR"
  rm -f "$TOOLS_DIR/$BT_ZIP"
  mv "$TOOLS_DIR/android-37.0" "$BT_DIR"
fi
ZIPALIGN="$BT_DIR/zipalign"
APKSIGNER="$BT_DIR/apksigner"
AAPT2="$BT_DIR/aapt2"

# Expected certificate fingerprint, from the keystore itself
EXPECTED_SHA256="$(keytool -list -v -keystore "$KS_FILE" -storepass:env PSST_STORE_PASS -alias "$KEY_ALIAS" 2>/dev/null \
  | awk '/SHA256:/ {print $2; exit}' | tr -d ':' | tr 'A-F' 'a-f')"
[ -n "$EXPECTED_SHA256" ] || die "could not read the certificate of alias $KEY_ALIAS"
echo "Release certificate SHA-256: $EXPECTED_SHA256"

# Play Protect blocks sideloaded apps with SMS / notification listener / accessibility (D83): refuse to sign them
mapfile_list=()
while IFS= read -r -d '' f; do mapfile_list+=("$f"); done < <(find "$IN_DIR" -type f \( -name '*-unsigned.apk' -o -name '*.aab' \) -print0)
[ ${#mapfile_list[@]} -eq 0 ] || AAPT2="$AAPT2" python3 "$REPO_ROOT/scripts/android/check-manifest.py" "${mapfile_list[@]}" \
  || die "manifest check failed (DECISIONS.md D83) — not signing"

# Message search must work in the release APK (D84): emulator + test accounts, known messages in an encrypted room,
# queries without diacritics and by word beginnings must return the expected counts. A failure stops the release.
GATE_APK="$(find "$IN_DIR" -type f -name '*x86_64*-unsigned.apk' | head -1)"
[ -n "$GATE_APK" ] || die "no x86_64 APK for the message search check (D84) in $IN_DIR"
AAPT2="$AAPT2" "$REPO_ROOT/scripts/android/search-gate.sh" "$GATE_APK" \
  || die "message search check failed (DECISIONS.md D84) — not signing, not uploading"

mkdir -p "$OUT_DIR"
SIGNED=()

# ---------- APKs ----------
while IFS= read -r -d '' apk; do
  base="$(basename "$apk" .apk)"
  version="$("$AAPT2" dump badging "$apk" 2>/dev/null | sed -n "s/^package: .*versionName='\([^']*\)'.*/\1/p")"
  # versionName "26.11.0-b42+2026-11-15" (older builds: "26.11.0-b42 (2026-11-15)") -> build 42, date 20261115
  b="$(echo "$version" | sed -nE 's/.*-b([0-9]+)[+ (]+([0-9]{4})-([0-9]{2})-([0-9]{2}).*/\1/p')"
  d="$(echo "$version" | sed -nE 's/.*-b([0-9]+)[+ (]+([0-9]{4})-([0-9]{2})-([0-9]{2}).*/\2\3\4/p')"
  [ -n "$b" ] && [ "$b" -gt 0 ] || die "$apk: versionName '$version' has no build number (local build without PSST_BUILD_NUMBER?)"
  [ -z "${BUILD:-}" ] || [ "$BUILD-$DATE" = "$b-$d" ] || die "mixed builds in $IN_DIR ($BUILD-$DATE vs $b-$d)"
  BUILD="$b"; DATE="$d"
  abi="$(echo "$base" | sed -E 's/^app-[a-z]+-(.*)-release-unsigned$/\1/')"
  case "$abi" in arm64-v8a) abi=arm64;; armeabi-v7a) abi=armv7;; esac
  out="$OUT_DIR/psst-android-$DATE-b$BUILD-${abi}.apk"
  echo "==> $apk -> $out"
  aligned="$(mktemp -t psst-aligned).apk"
  "$ZIPALIGN" -P 16 -f 4 "$apk" "$aligned"
  "$APKSIGNER" sign --ks "$KS_FILE" --ks-key-alias "$KEY_ALIAS" \
    --ks-pass env:PSST_STORE_PASS --key-pass env:PSST_KEY_PASS \
    --out "$out" "$aligned"
  rm -f "$aligned" "$out.idsig"
  "$ZIPALIGN" -c -P 16 4 "$out" >/dev/null || die "zipalign check failed for $out"
  certs="$("$APKSIGNER" verify --print-certs -v "$out")"
  echo "$certs" | grep -E "^Verified using .*: true|[Ss]igner.*certificate (DN|SHA-256 digest)" | sort -u | sed 's/^/    /'
  # every signer block (v1/v2/v3) must carry the psst certificate
  got="$(echo "$certs" | awk -F'digest: ' '/certificate SHA-256 digest/ {print $2}' | sort -u)"
  [ "$got" = "$EXPECTED_SHA256" ] || die "certificate mismatch for $out ($got)"
  SIGNED+=("$out")
done < <(find "$IN_DIR" -type f -name '*-unsigned.apk' -print0 | sort -z)

# ---------- AAB ----------
while IFS= read -r -d '' aab; do
  [ -n "${BUILD:-}" ] || die "sign the APKs together with the AAB (build number is read from the APK)"
  out="$OUT_DIR/psst-android-$DATE-b$BUILD.aab"
  echo "==> $aab -> $out"
  jarsigner -keystore "$KS_FILE" -storepass:env PSST_STORE_PASS -keypass:env PSST_KEY_PASS \
    -sigalg SHA256withRSA -digestalg SHA-256 -signedjar "$out" "$aab" "$KEY_ALIAS" >/dev/null
  jarsigner -verify -strict "$out" >/dev/null 2>&1 || jarsigner -verify "$out" | tail -3
  got="$(keytool -printcert -jarfile "$out" | awk '/SHA256:/ {print $2; exit}' | tr -d ':' | tr 'A-F' 'a-f')"
  [ "$got" = "$EXPECTED_SHA256" ] || die "certificate mismatch for $out ($got)"
  echo "    jarsigner: verified, certificate SHA-256 $got"
  SIGNED+=("$out")
done < <(find "$IN_DIR" -type f -name '*.aab' -print0 | sort -z)

unset PSST_STORE_PASS PSST_KEY_PASS
[ "${#SIGNED[@]}" -gt 0 ] || die "no *-unsigned.apk or *.aab found in $IN_DIR"

if [ "$PUBLISH" = 1 ]; then
  python3 "$REPO_ROOT/scripts/release/publish.py" android "$BUILD" "$DATE" --note "$PSST_NOTE" "${SIGNED[@]}"
  # download page https://app.macet.eu/download (D59): upload + HTTPS SHA-256 check; failure = build failure
  if [ "${PSST_SKIP_DOWNLOAD_PAGE:-0}" != 1 ]; then
    "$REPO_ROOT/scripts/release/upload-download.sh" android "$REPO_ROOT/dist/android/psst-android-$DATE-b$BUILD-arm64.apk" "$PSST_NOTE"
  fi
  rmdir "$OUT_DIR" 2>/dev/null || true
  OUT_DIR="$REPO_ROOT/dist/android"
else
  ( cd "$OUT_DIR" && shasum -a 256 $(for f in "${SIGNED[@]}"; do basename "$f"; done) > SHA256SUMS )
fi
echo
echo "Signed artifacts (build b$BUILD, $DATE) in $OUT_DIR:"
ls -l "$OUT_DIR"
echo "Certificate SHA-256: $EXPECTED_SHA256"
