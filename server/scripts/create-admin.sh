#!/usr/bin/env bash
# Vytvorí admin účet cez registration_shared_secret (obíde pozývacie tokeny) a uloží
# admin access token do server/secrets/admin_token (používa ho new-invite.sh).
#
#   scripts/create-admin.sh [meno] [heslo]
#   (bez hesla sa vygeneruje náhodné a raz sa vypíše)
. "$(dirname "$0")/lib.sh"
load_env

USERNAME="${1:-admin}"
PASSWORD="${2:-}"
GENERATED=0
if [ -z "$PASSWORD" ]; then PASSWORD="$(gen_secret 16)"; GENERATED=1; fi

case "$USERNAME$PASSWORD" in *\"*|*\\*) die "meno/heslo nesmie obsahovať \" ani \\" ;; esac

log "registrujem admina @${USERNAME}:${MATRIX_DOMAIN}"
compose exec -T synapse register_new_matrix_user -c /config/homeserver.yaml \
  -u "$USERNAME" -p "$PASSWORD" --admin http://localhost:8008 >&2

log "prihlasujem a ukladám token do secrets/admin_token"
RESP="$(synapse_curl -X POST -H 'Content-Type: application/json' \
  -d "{\"type\":\"m.login.password\",\"identifier\":{\"type\":\"m.id.user\",\"user\":\"${USERNAME}\"},\"password\":\"${PASSWORD}\",\"initial_device_display_name\":\"psst admin cli\"}" \
  http://localhost:8008/_matrix/client/v3/login)"
TOKEN="$(printf '%s' "$RESP" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')"
[ -n "$TOKEN" ] || die "prihlásenie zlyhalo: $RESP"
mkdir -p secrets; chmod 700 secrets
( umask 077; printf '%s' "$TOKEN" > secrets/admin_token )

log "admin @${USERNAME}:${MATRIX_DOMAIN} vytvorený"
if [ "$GENERATED" = 1 ]; then
  echo "heslo: ${PASSWORD}"
  warn "heslo sa nikde neukladá — zapíšte si ho do správcu hesiel"
fi
