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
for svc in postgres synapse mas livekit coturn lk-jwt-service element-call admin nginx; do
  cid="$(compose ps -q "$svc" 2>/dev/null || true)"
  if [ -z "$cid" ]; then bad "kontajner $svc nebeží"; continue; fi
  st="$(docker inspect -f '{{.State.Status}}{{if .State.Health}}/{{.State.Health.Status}}{{end}}' "$cid")"
  case "$st" in running|running/healthy) ok "kontajner $svc ($st)" ;; *) bad "kontajner $svc ($st)" ;; esac
done
if [ "${COMPOSE_PROFILES:-}" = sygnal ]; then
  [ -n "$(compose ps -q sygnal 2>/dev/null)" ] && ok "kontajner sygnal (push brána FCM/APNs)" || bad "kontajner sygnal nebeží"
fi

# --- HTTPS cez nginx (domény → 127.0.0.1, ako keby prišli zvonka)
K=""; [ -f data/certbot/conf/live/psst/.psst-dummy ] && K="-k"
RES=""; for d in "$MATRIX_DOMAIN" "$APP_DOMAIN" "$CALL_DOMAIN" "$AUTH_DOMAIN" ${NTFY_DOMAIN:-} ${WEB_DOMAIN:-} ${WWW_DOMAIN:-} ${SERVER_NAME}; do RES+=" --resolve $d:443:127.0.0.1"; done
get() { curl -sS $K $RES --max-time 10 "$@"; }
check() { # check <popis> <url> <grep-vzor>
  local body; body="$(get "$2" 2>&1)" || { bad "$1 ($2: $body)"; return; }
  if printf '%s' "$body" | grep -q -- "$3"; then ok "$1"; else bad "$1 ($2 neobsahuje '$3')"; fi
}
check ".well-known/matrix/client + rtc_foci"       "https://$MATRIX_DOMAIN/.well-known/matrix/client" "livekit_service_url"
check "Synapse client API"                          "https://$MATRIX_DOMAIN/_matrix/client/versions" '"versions"'
check "Synapse → MAS (auth_metadata)"               "https://$MATRIX_DOMAIN/_matrix/client/v1/auth_metadata" "https://$AUTH_DOMAIN${AUTH_PREFIX:-}/"
check "MAS OIDC discovery (registrácia povolená)"   "https://$AUTH_DOMAIN${AUTH_PREFIX:-}/.well-known/openid-configuration" '"create"'
check "MAS compat login"                            "https://$MATRIX_DOMAIN/_matrix/client/v3/login" "m.login.sso"
check "PSST web"                                    "https://$APP_DOMAIN/" "<html"
check "Podmienky / Ochrana súkromia"                "https://$APP_DOMAIN/terms.html" "psst"
get -o /dev/null -w '%{http_code}' "https://$APP_DOMAIN/privacy.html" | grep -q 200 && ok "privacy.html" || bad "privacy.html"
# stránka na stiahnutie (D59)
check "stránka na stiahnutie /download" "https://$APP_DOMAIN/download/" "Download psst"
# administrácia: bez prihlásenia presmeruje na MAS (D56)
get -o /dev/null -w '%{http_code} %{redirect_url}' "https://$APP_DOMAIN/admin/login" | grep -q "^303 .*/authorize" \
  && ok "administrácia /admin (prihlásenie cez MAS)" || bad "administrácia /admin"
check "Element Call"                                "https://$CALL_DOMAIN/" "<html"
# prezentačná stránka (D82): obe jazykové verzie (rovnaký certifikát "psst" ako ostatné domény, D85)
if [ -n "${WEB_DOMAIN:-}" ]; then
  check "prezentačná stránka SK ($WEB_DOMAIN)" "https://$WEB_DOMAIN/sk/" "Stiahnuť aplikáciu"
  check "prezentačná stránka EN ($WEB_DOMAIN)" "https://$WEB_DOMAIN/en/" "Download the app"
fi
if [ -n "${WWW_DOMAIN:-}" ]; then
  get -o /dev/null -w '%{http_code} %{redirect_url}' "https://$WWW_DOMAIN/sk/" | grep -q "^301 https://${WEB_DOMAIN}/sk/" \
    && ok "$WWW_DOMAIN presmeruje na $WEB_DOMAIN" || bad "$WWW_DOMAIN nepresmeruje na $WEB_DOMAIN"
fi
# server_name ≠ homeserver (D85): klienti a lk-jwt-service hľadajú homeserver cez .well-known na server_name
if [ "$SERVER_NAME" != "$MATRIX_DOMAIN" ]; then
  check ".well-known/matrix/client na $SERVER_NAME" "https://$SERVER_NAME/.well-known/matrix/client" "\"https://$MATRIX_DOMAIN\""
  check ".well-known/matrix/server na $SERVER_NAME" "https://$SERVER_NAME/.well-known/matrix/server" "\"$MATRIX_DOMAIN:8448\""
fi
# neznámy názov (napr. bývalá doména, ktorej DNS ešte ukazuje sem) nedostane žiadny obsah psst
code="$(curl -sS -k --resolve psst-unknown.invalid:443:127.0.0.1 --max-time 5 -o /dev/null -w '%{http_code}' https://psst-unknown.invalid/ 2>/dev/null || true)"
[ "$code" = 000 ] && ok "neznámy Host: spojenie zatvorené (444)" || bad "neznámy Host dostal HTTP $code"
code="$(curl -sS --resolve psst-unknown.invalid:80:127.0.0.1 --max-time 5 -o /dev/null -w '%{http_code}' http://psst-unknown.invalid/ 2>/dev/null || true)"
[ "$code" = 000 ] && ok "neznámy Host na :80: bez presmerovania (444)" || bad "neznámy Host na :80 dostal HTTP $code"
if [ -n "${NTFY_DOMAIN:-}" ]; then
  code="$(get -o /dev/null -w '%{http_code}' "https://$NTFY_DOMAIN/")"
  [ "$code" = 301 ] && ok "push doména len presmeruje (ntfy zrušený)" || bad "https://$NTFY_DOMAIN/ vrátil $code (očakávané 301)"
fi
get -o /dev/null -w '%{http_code}' "https://$MATRIX_DOMAIN/livekit/jwt/healthz" | grep -q 200 && ok "lk-jwt-service" || bad "lk-jwt-service (/livekit/jwt/healthz)"
check "LiveKit SFU"                                 "https://$MATRIX_DOMAIN/livekit/sfu/" "OK"
code="$(get -o /dev/null -w '%{http_code}' "https://$MATRIX_DOMAIN/_matrix/federation/v1/version")"
[ "$code" = 404 ] && ok "federácia vypnutá (404)" || bad "federácia odpovedá ($code)"
if [ "${COMPOSE_PROFILES:-}" = sygnal ]; then
  code="$(get -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{}' "https://$MATRIX_DOMAIN/_matrix/push/v1/notify")"
  [ "$code" = 400 ] && ok "Sygnal odpovedá na chat…/_matrix/push/v1/notify" || bad "Sygnal ($code)"
  if [ -s secrets/fcm/service-account.json ]; then
    compose logs --no-log-prefix sygnal 2>/dev/null | grep -qiE "Unable to load|InvalidConfig|PushkinSetupException|service_account_file" \
      && bad "Sygnal hlási chybu konfigurácie (compose logs sygnal)" || ok "Sygnal FCM v1 nakonfigurovaný"
  fi
  # Web push (D76): verejný VAPID kľúč pre web + Sygnal webpush bez chyby nastavenia
  check "Web push: /psst-push.json (VAPID)" "https://$APP_DOMAIN/psst-push.json" '"vapid_public_key"'
  compose logs --no-log-prefix sygnal 2>/dev/null | grep -qiE "vapid|PushkinSetupException" \
    && bad "Sygnal webpush: chyba konfigurácie (compose logs sygnal)" || ok "Sygnal webpush nakonfigurovaný"
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
