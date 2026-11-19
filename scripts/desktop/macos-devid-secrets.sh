#!/usr/bin/env bash
# PSST (D69): put the macOS "Developer ID Application" certificate into GitHub Actions secrets so that every
# web-desktop.yml build is signed + notarized (and the download page drops its "unsigned" note).
#
#   scripts/desktop/macos-devid-secrets.sh developerID_application.cer          # cert Apple issued for our CSR
#   scripts/desktop/macos-devid-secrets.sh devid.p12 <file with p12 password>   # or a .p12 exported by the Account Holder
#   ... [--run]   also start the Web + Desktop workflow afterwards
#
# .cer route (preferred): the private key never leaves this Mac — it was generated together with the CSR
# ~/psst-keys/macos-devid/devid.csr (key devid.key). The script checks that the certificate belongs to that key and
# to team MHV67VMY8T, builds devid.p12 (+ intermediate CA) with a random password, keeps both in
# ~/psst-keys/macos-devid/ (chmod 600) and sets the encrypted secrets PSST_MAC_CERT_P12_BASE64 + PSST_MAC_CERT_PASSWORD.
# Notarization reuses the existing secrets APP_STORE_CONNECT_API_KEY_BASE64 / _KEY_ID / _ISSUER_ID and APPLE_TEAM_ID.
# Nothing is ever written into the repository. DRY_RUN=1: check + build the p12 only, no secrets.
set -euo pipefail
REPO=georgonr/psst
TEAM=MHV67VMY8T
DIR="${PSST_DEVID_DIR:-$HOME/psst-keys/macos-devid}"
die() { echo "ERROR: $*" >&2; exit 1; }
IN="${1:?usage: $0 <developerID_application.cer | devid.p12 password-file> [--run]}"; shift
RUN=0; PASSFILE=""
for a in "$@"; do case "$a" in --run) RUN=1 ;; *) PASSFILE="$a" ;; esac; done
[ -f "$IN" ] || die "missing $IN"
umask 077; mkdir -p "$DIR"; chmod 700 "$DIR"
# never the infomaxicz account: use the georgonr token explicitly
GH_TOKEN="$(gh auth token -u georgonr)"; export GH_TOKEN
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

case "$IN" in
*.cer|*.crt|*.pem)
    KEY="$DIR/devid.key"; [ -f "$KEY" ] || die "missing $KEY (the key belonging to devid.csr)"
    openssl x509 -inform DER -in "$IN" -out "$TMP/cert.pem" 2>/dev/null || openssl x509 -in "$IN" -out "$TMP/cert.pem"
    [ "$(openssl x509 -in "$TMP/cert.pem" -noout -pubkey | openssl sha256)" = "$(openssl pkey -in "$KEY" -pubout | openssl sha256)" ] \
        || die "certificate does not belong to $KEY — was it created from ~/psst-keys/macos-devid/devid.csr?"
    SUBJ="$(openssl x509 -in "$TMP/cert.pem" -noout -subject -nameopt RFC2253)"
    ISSUER="$(openssl x509 -in "$TMP/cert.pem" -noout -issuer -nameopt RFC2253)"
    # Apple intermediate (G2 for new certificates), so codesign can build the chain on the CI runner
    case "$ISSUER" in
        *"G2"*) CA_URL=https://www.apple.com/certificateauthority/DeveloperIDG2CA.cer ;;
        *) CA_URL=https://www.apple.com/certificateauthority/DeveloperIDCA.cer ;;
    esac
    curl -fsSL --proto '=https' "$CA_URL" | openssl x509 -inform DER -out "$TMP/ca.pem"
    PASS="$(openssl rand -base64 30 | tr -d '/+=\n' | cut -c1-32)"
    # 3DES/SHA1 PKCS#12: what `security import` on every macOS version accepts
    openssl pkcs12 -export -inkey "$KEY" -in "$TMP/cert.pem" -certfile "$TMP/ca.pem" -name "psst Developer ID Application" \
        -certpbe PBE-SHA1-3DES -keypbe PBE-SHA1-3DES -macalg sha1 -passout fd:3 -out "$DIR/devid.p12" 3<<<"$PASS"
    printf '%s' "$PASS" > "$DIR/p12.pass"
    cp "$TMP/cert.pem" "$DIR/devid.cer.pem"
    P12="$DIR/devid.p12"
    ;;
*.p12|*.pfx)
    [ -n "$PASSFILE" ] && [ -f "$PASSFILE" ] || die "give the file with the .p12 password as 2nd argument"
    PASS="$(cat "$PASSFILE")"; P12="$IN"
    openssl pkcs12 -in "$P12" -nokeys -clcerts -passin fd:3 3<<<"$PASS" 2>/dev/null >"$TMP/cert.pem" \
        || openssl pkcs12 -legacy -in "$P12" -nokeys -clcerts -passin fd:3 3<<<"$PASS" >"$TMP/cert.pem" || die "cannot read $P12 (password?)"
    SUBJ="$(openssl x509 -in "$TMP/cert.pem" -noout -subject -nameopt RFC2253)"
    ;;
*) die "expected .cer or .p12" ;;
esac

echo "certificate: $SUBJ"
openssl x509 -in "$TMP/cert.pem" -noout -dates
case "$SUBJ" in *"Developer ID Application"*"$TEAM"*) ;; *) die "not a 'Developer ID Application … ($TEAM)' certificate" ;; esac

# On a Mac: the p12 must import and give a valid code signing identity
if command -v security >/dev/null; then
    KC="$TMP/check.keychain-db"
    security create-keychain -p x "$KC" && security unlock-keychain -p x "$KC"
    security import "$P12" -k "$KC" -P "$PASS" -T /usr/bin/codesign >/dev/null
    security find-identity -p codesigning "$KC" | grep "Developer ID Application" || die "p12 gives no code signing identity"
    security delete-keychain "$KC"
fi

[ "${DRY_RUN:-0}" = 1 ] && { echo "DRY_RUN: p12 OK ($P12), secrets not set"; exit 0; }
base64 < "$P12" | tr -d '\n' | gh secret set PSST_MAC_CERT_P12_BASE64 -R "$REPO"
printf '%s' "$PASS" | gh secret set PSST_MAC_CERT_PASSWORD -R "$REPO"
SECRETS="$(gh secret list -R "$REPO")"   # whole list first: `| grep -q` under pipefail fails on SIGPIPE
for s in APP_STORE_CONNECT_API_KEY_BASE64 APP_STORE_CONNECT_API_KEY_ID APP_STORE_CONNECT_ISSUER_ID APPLE_TEAM_ID; do
    printf '%s\n' "$SECRETS" | grep -q "^$s[[:space:]]" || die "secret $s missing (scripts/ios/release-testflight.sh sets it)"
done
echo "OK: secrets PSST_MAC_CERT_P12_BASE64 + PSST_MAC_CERT_PASSWORD set in $REPO"
if [ "$RUN" = 1 ]; then
    gh workflow run web-desktop.yml -R "$REPO"
    echo "started Web + Desktop; the macOS job now signs + notarizes, 'Gatekeeper check of the published DMG' verifies the download"
fi
