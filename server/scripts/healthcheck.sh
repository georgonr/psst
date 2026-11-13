#!/usr/bin/env bash
# Overí všetky služby PSST (kontajnery + verejné HTTPS endpointy cez nginx + TURN/TLS + certifikát + zálohy).
#
#   scripts/healthcheck.sh [--quiet]     exit 0 = všetko OK, 1 = niečo zlyhalo (--quiet vypíše len chyby)
. "$(dirname "$0")/lib.sh"
load_env
QUIET=0; [ "${1:-}" = "--quiet" ] && QUIET=1
FAILS=0; WARNS=0
ok()   { [ "$QUIET" = 1 ] || printf '  \033[32mOK\033[0m    %s\n' "$*"; }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$*"; FAILS=$((FAILS + 1)); }
note() { printf '  \033[33mWARN\033[0m  %s\n' "$*"; WARNS=$((WARNS + 1)); }
[ "$QUIET" = 1 ] || echo "PSST healthcheck $(date -u +%FT%TZ)"

# --- kontajnery
for svc in postgres synapse mas ntfy livekit lk-jwt-service element-call nginx; do
  cid="$(compose ps -q "$svc" 2>/dev/null || true)"
  if [ -z "$cid" ]; then bad "kontajner $svc nebeží"; continue; fi
  st="$(docker inspect -f '{{.State.Status}}{{if .State.Health}}/{{.State.Health.Status}}{{end}}' "$cid")"
  case "$st" in running|running/healthy) ok "kontajner $svc ($st)" ;; *) bad "kontajner $svc ($st)" ;; esac
done
if [ "${COMPOSE_PROFILES:-}" = apns ]; then
  [ -n "$(compose ps -q sygnal 2>/dev/null)" ] && ok "kontajner sygnal (iOS push)" || bad "kontajner sygnal nebeží"
fi

# --- HTTPS cez nginx (domény → 127.0.0.1, ako keby prišli zvonka)
K=""; [ -f data/certbot/conf/live/psst/.psst-dummy ] && K="-k"
RES=""; for d in "$MATRIX_DOMAIN" "$APP_DOMAIN" "$CALL_DOMAIN" "$AUTH_DOMAIN" "$NTFY_DOMAIN"; do RES+=" --resolve $d:443:127.0.0.1"; done
get() { curl -sS $K $RES --max-time 10 "$@"; }
check() { # check <popis> <url> <grep-vzor>
  local body; body="$(get "$2" 2>&1)" || { bad "$1 ($2: $body)"; return; }
  if printf '%s' "$body" | grep -q -- "$3"; then ok "$1"; else bad "$1 ($2 neobsahuje '$3')"; fi
}
check ".well-known/matrix/client + rtc_foci"       "https://$MATRIX_DOMAIN/.well-known/matrix/client" "livekit_service_url"
check "Synapse client API"                          "https://$MATRIX_DOMAIN/_matrix/client/versions" '"versions"'
check "Synapse → MAS (auth_metadata)"               "https://$MATRIX_DOMAIN/_matrix/client/v1/auth_metadata" "https://$AUTH_DOMAIN/"
check "MAS OIDC discovery (registrácia povolená)"   "https://$AUTH_DOMAIN/.well-known/openid-configuration" '"create"'
check "MAS compat login"                            "https://$MATRIX_DOMAIN/_matrix/client/v3/login" "m.login.sso"
check "PSST web"                                    "https://$APP_DOMAIN/" "<html"
check "Podmienky / Ochrana súkromia"                "https://$APP_DOMAIN/terms.html" "psst"
get -o /dev/null -w '%{http_code}' "https://$APP_DOMAIN/privacy.html" | grep -q 200 && ok "privacy.html" || bad "privacy.html"
check "Element Call"                                "https://$CALL_DOMAIN/" "<html"
check "ntfy (UnifiedPush)"                          "https://$NTFY_DOMAIN/v1/health" '"healthy":true'
check "ntfy Matrix push brána"                      "https://$NTFY_DOMAIN/_matrix/push/v1/notify" "unifiedpush"
get -o /dev/null -w '%{http_code}' "https://$MATRIX_DOMAIN/livekit/jwt/healthz" | grep -q 200 && ok "lk-jwt-service" || bad "lk-jwt-service (/livekit/jwt/healthz)"
check "LiveKit SFU"                                 "https://$MATRIX_DOMAIN/livekit/sfu/" "OK"
code="$(get -o /dev/null -w '%{http_code}' "https://$MATRIX_DOMAIN/_matrix/federation/v1/version")"
[ "$code" = 404 ] && ok "federácia vypnutá (404)" || bad "federácia odpovedá ($code)"
if [ "${COMPOSE_PROFILES:-}" = apns ]; then
  code="$(get -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{}' "https://$MATRIX_DOMAIN/_matrix/push/v1/notify")"
  [ "$code" = 400 ] && ok "Sygnal odpovedá" || bad "Sygnal ($code)"
fi

# --- TURN/TLS na 443 (SNI turn.)
if echo | openssl s_client -connect 127.0.0.1:443 -servername "$TURN_DOMAIN" 2>&1 | grep -q "depth=0"; then
  ok "TURN/TLS na 443 (TLS handshake pre $TURN_DOMAIN)"
else bad "TURN/TLS na 443 neodpovedá"; fi

# --- certifikát
if [ -n "$K" ]; then note "certifikát je dočasný self-signed (Let's Encrypt ešte nebol vystavený)"
else
  end="$(openssl x509 -enddate -noout -in data/certbot/conf/live/psst/fullchain.pem 2>/dev/null | cut -d= -f2)"
  if [ -n "$end" ]; then
    left=$(( ( $(date -d "$end" +%s 2>/dev/null || date -j -f '%b %d %T %Y %Z' "$end" +%s) - $(date +%s) ) / 86400 ))
    [ "$left" -ge 14 ] && ok "certifikát platí ešte $left dní" || bad "certifikát vyprší o $left dní"
  fi
fi

# --- disk, zálohy
avail=$(df -Pk . | awk 'NR==2{print int($4/1048576)}')
[ "$avail" -ge 5 ] && ok "voľné miesto ${avail} GB" || bad "málo miesta: ${avail} GB"
if [ -f /etc/cron.d/psst ]; then
  if [ -f backups/.last-success ]; then
    age=$(( ( $(date +%s) - $(date -d "$(cat backups/.last-success)" +%s 2>/dev/null || echo 0) ) / 3600 ))
    [ "$age" -le 26 ] && ok "posledná záloha pred ${age} h" || bad "posledná úspešná záloha pred ${age} h"
  else note "zatiaľ žiadna záloha (prvá prebehne o 03:17)"; fi
fi

[ "$QUIET" = 1 ] && [ "$FAILS" = 0 ] && exit 0
echo "výsledok: $([ "$FAILS" = 0 ] && echo OK || echo "$FAILS chýb"), $WARNS varovaní"
[ "$FAILS" = 0 ]
