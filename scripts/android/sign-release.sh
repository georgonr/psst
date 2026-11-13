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
#   output-dir default: <repo>/dist/android (gitignored).
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
OUT_DIR="${1:-$REPO_ROOT/dist/android}"
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

mkdir -p "$OUT_DIR"
SIGNED=()

# ---------- APKs ----------
while IFS= read -r -d '' apk; do
  base="$(basename "$apk" .apk)"
  version="$("$AAPT2" dump badging "$apk" 2>/dev/null | sed -n "s/^package: .*versionName='\([^']*\)'.*/\1/p")"
  abi="$(echo "$base" | sed -E 's/^app-[a-z]+-(.*)-release-unsigned$/\1/')"
  out="$OUT_DIR/psst-${version:-unknown}-${abi}.apk"
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
  base="$(basename "$aab" .aab)"
  out="$OUT_DIR/psst-${base#app-}.aab"
  out="${out/-release/}"
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

( cd "$OUT_DIR" && shasum -a 256 $(for f in "${SIGNED[@]}"; do basename "$f"; done) > SHA256SUMS )
echo
echo "Signed artifacts in $OUT_DIR:"
ls -l "$OUT_DIR"
echo "Certificate SHA-256: $EXPECTED_SHA256"
