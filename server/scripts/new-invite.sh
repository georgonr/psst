#!/usr/bin/env bash
# Vytvorí pozývací (registračný) token cez Synapse admin API.
#
#   scripts/new-invite.sh [počet_použití=1] [platnosť_dní=7]
#   scripts/new-invite.sh 5 30        # token pre 5 registrácií, platný 30 dní
#   scripts/new-invite.sh 0 0         # neobmedzený počet použití, bez expirácie (neodporúčané)
#   scripts/new-invite.sh --list      # výpis existujúcich tokenov
#
# Na stdout vypíše LEN token (vhodné pre skripty); detaily idú na stderr.
# Admin token: secrets/admin_token (scripts/create-admin.sh) alebo premenná SYNAPSE_ADMIN_TOKEN.
. "$(dirname "$0")/lib.sh"
load_env
TOKEN="$(admin_token)"
API=http://localhost:8008/_synapse/admin/v1/registration_tokens

if [ "${1:-}" = "--list" ]; then
  synapse_curl -H "Authorization: Bearer $TOKEN" "$API"; echo; exit 0
fi

USES="${1:-1}"
DAYS="${2:-7}"
case "$USES$DAYS" in *[!0-9]*) die "počet použití a dni musia byť čísla" ;; esac

BODY="{"
[ "$USES" != 0 ] && BODY="${BODY}\"uses_allowed\":${USES}"
if [ "$DAYS" != 0 ]; then
  EXP=$(( ($(date +%s) + DAYS * 86400) * 1000 ))
  [ "$BODY" != "{" ] && BODY="${BODY},"
  BODY="${BODY}\"expiry_time\":${EXP}"
fi
BODY="${BODY}}"

RESP="$(synapse_curl -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "$BODY" "$API/new")"
INVITE="$(printf '%s' "$RESP" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')"
[ -n "$INVITE" ] || die "vytvorenie tokenu zlyhalo: $RESP"
log "pozývací token (použití: ${USES/#0/∞}, platnosť: ${DAYS/#0/∞} dní) pre https://${APP_DOMAIN}"
echo "$INVITE"
