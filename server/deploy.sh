#!/usr/bin/env bash
# PSST server — nasadenie jedným príkazom (idempotentné: prvé nasadenie aj aktualizácia).
#
#   sudo ./deploy.sh <IP_SERVERA> <EMAIL_PRE_LETS_ENCRYPT> [voľby]
#
#   Voľby:
#     --apple-team-id <ID>  Apple Developer Team ID (iOS push cez Sygnal, universal links)
#     --contact "<text>"    kontakt prevádzkovateľa na stránkach Podmienky/Súkromie (napr. e-mail)
#     --hosting "<text>"    kde je server (napr. "Hetzner Online GmbH, Nemecko (EÚ)")
#     --staging             certifikát z Let's Encrypt staging (skúška, nie dôveryhodný)
#     --skip-harden         nemeniť systém (SSH, UFW, fail2ban, aktualizácie, cron)
#     --skip-preflight      preskočiť pre-flight kontrolu (neodporúča sa)
#     --no-pull             nesťahovať nové image
#     --local-test          lokálny test (CI/vývoj): bez Let's Encrypt, bez DNS/hardeningu,
#                           self-signed certifikát, compose.test.yml; IP = 127.0.0.1
#
# Čo robí (každý krok je bezpečné spustiť znova):
#   0. pre-flight: Docker (doinštaluje na Debian/Ubuntu), DNS všetkých subdomén → IP, voľné porty, miesto
#   1. hardening systému (scripts/harden.sh): SSH len kľúčom, bez root loginu, UFW, fail2ban, auto-updates
#   2. server/.env + secrets/ (náhodné tajomstvá len prvýkrát; existujúce hodnoty nemení)
#   3. vyrenderuje konfigurácie z templates/ do data/config/
#   4. stiahne PSST web (ak app/ je prázdne)
#   5. docker compose up, databáza pre MAS, čakanie na healthchecky
#   6. certifikát Let's Encrypt pre všetky subdomény
#   7. denné šifrované zálohy (cron) + healthcheck
#
# Push: Android = FCM cez vlastný Sygnal → JSON kľúč service accountu Firebase do secrets/fcm/service-account.json;
#       iOS = APNs → AuthKey_<KEY_ID>.p8 do secrets/apns/ (+ --apple-team-id). Potom deploy.sh znova.
set -euo pipefail
. "$(dirname "$0")/scripts/lib.sh"

usage() { sed -n '2,25p' "$0"; exit "${1:-0}"; }

SERVER_IP=""; LE_EMAIL=""; TEAM_ID=""; CONTACT=""; HOSTING=""
LETSENCRYPT=1; PULL=1; HARDEN=1; PREFLIGHT=1; LOCAL_TEST=0; STAGING=0
POSITIONAL=()
while [ $# -gt 0 ]; do
  case "$1" in
    --apple-team-id) TEAM_ID="${2:?chýba hodnota pre --apple-team-id}"; shift ;;
    --contact) CONTACT="${2:?chýba hodnota pre --contact}"; shift ;;
    --hosting) HOSTING="${2:?chýba hodnota pre --hosting}"; shift ;;
    --staging) STAGING=1 ;;
    --skip-harden) HARDEN=0 ;;
    --skip-preflight) PREFLIGHT=0 ;;
    --no-pull) PULL=0 ;;
    --local-test) LOCAL_TEST=1; LETSENCRYPT=0; HARDEN=0; PREFLIGHT=0 ;;
    -h|--help) usage 0 ;;
    -*) die "neznámy prepínač: $1 (./deploy.sh --help)" ;;
    *) POSITIONAL+=("$1") ;;
  esac
  shift
done
SERVER_IP="${POSITIONAL[0]:-}"; LE_EMAIL="${POSITIONAL[1]:-}"

if [ "$LOCAL_TEST" = 1 ]; then
  SERVER_IP="${SERVER_IP:-127.0.0.1}"
  export COMPOSE_FILE="compose.yml:compose.test.yml"
else
  [ -n "$SERVER_IP" ] && [ -n "$LE_EMAIL" ] || { warn "chýba IP servera alebo e-mail"; usage 1; }
  [[ "$SERVER_IP" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || die "IP servera musí byť IPv4 adresa (napr. 203.0.113.10)"
  [[ "$LE_EMAIL" == *@*.* ]] || die "neplatný e-mail: $LE_EMAIL"
fi

# ----------------------------------------------------------------- domény
MATRIX_DOMAIN="${MATRIX_DOMAIN:-chat.macet.eu}"
DOMAIN_BASE="${MATRIX_DOMAIN#*.}"
APP_DOMAIN="${APP_DOMAIN:-app.${DOMAIN_BASE}}"
CALL_DOMAIN="${CALL_DOMAIN:-call.${DOMAIN_BASE}}"
# Produkcia má DNS len pre chat/app/call/push (viď DECISIONS D42):
#  - MAS beží na ceste https://<MATRIX_DOMAIN>/auth/ (AUTH_PREFIX), nie na vlastnej subdoméne
#  - push.<doména>: bývalý ntfy, len presmerovanie na web (notifikácie idú cez FCM/APNs a Sygnal)
#  - TURN/TLS zdieľa :443 s <CALL_DOMAIN> — nginx ho rozlíši podľa ALPN (TURN klient neposiela h2/http/1.1)
# Samostatné subdomény sa dajú zapnúť cez .env (AUTH_DOMAIN=auth.… AUTH_PREFIX= TURN_DOMAIN=turn.…).
AUTH_DOMAIN="${AUTH_DOMAIN:-${MATRIX_DOMAIN}}"
if [ -z "${AUTH_PREFIX+x}" ]; then
  if [ "$AUTH_DOMAIN" = "$MATRIX_DOMAIN" ]; then AUTH_PREFIX=/auth; else AUTH_PREFIX=""; fi
fi
NTFY_DOMAIN="${NTFY_DOMAIN:-push.${DOMAIN_BASE}}"
TURN_DOMAIN="${TURN_DOMAIN:-${CALL_DOMAIN}}"
ALL_DOMAINS="$(printf '%s\n' "$MATRIX_DOMAIN" "$APP_DOMAIN" "$CALL_DOMAIN" "$AUTH_DOMAIN" "$NTFY_DOMAIN" "$TURN_DOMAIN" | awk '!s[$0]++' | tr '\n' ' ')"
ALL_DOMAINS="${ALL_DOMAINS% }"
NGINX_IP=172.30.0.10
DOCKER_GW=172.30.0.1   # brána Docker siete "psst" (coturn v host sieti počúva aj tu pre nginx)

# ----------------------------------------------------------------- 0. pre-flight
if [ "$PREFLIGHT" = 1 ]; then
  log "pre-flight kontrola"
  [ "$(uname -s)" = Linux ] || die "nasadenie je určené pre Linux server (Debian 12/13 alebo Ubuntu 22.04/24.04)"
  [ "$(id -u)" = 0 ] || die "spustite cez sudo (hardening a inštalácia Dockeru potrebujú root)"
  export DEBIAN_FRONTEND=noninteractive
  if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
    [ -f /etc/debian_version ] || die "Docker chýba a automatická inštalácia podporuje len Debian/Ubuntu"
    log "inštalujem Docker Engine + compose plugin (oficiálny repozitár docker.com)"
    apt-get update -qq && apt-get install -y -qq ca-certificates curl >/dev/null
    curl -fsSL https://get.docker.com | sh >/dev/null
    systemctl enable --now docker >/dev/null
  fi
  docker info >/dev/null 2>&1 || die "Docker daemon nebeží"
  for c in openssl curl dig ss rsync; do
    command -v "$c" >/dev/null || apt-get install -y -qq openssl curl dnsutils iproute2 rsync python3 >/dev/null 2>&1 || true
  done

  FAIL=0
  for d in $ALL_DOMAINS; do
    got="$(dig +short A "$d" @1.1.1.1 2>/dev/null | grep -E '^[0-9.]+$' | sort -u | tr '\n' ' ' || true)"
    [ -z "$got" ] && got="$(getent ahostsv4 "$d" 2>/dev/null | awk '{print $1}' | sort -u | tr '\n' ' ' || true)"
    got="$(echo $got)"
    if [ "$got" = "$SERVER_IP" ]; then log "  DNS  $d → $SERVER_IP  OK"
    else warn "  DNS  $d → '${got:-nič}' (očakávané $SERVER_IP)"; FAIL=1; fi
  done
  if ip -4 addr 2>/dev/null | grep -q "inet ${SERVER_IP}/"; then log "  IP   $SERVER_IP je na tomto serveri  OK"
  else warn "  IP   $SERVER_IP nie je na sieťovom rozhraní (NAT v cloude?) — pokračujem, LiveKit ju ohlási ako node_ip"; fi
  # porty: obsadené smú byť len naším stackom (docker-proxy, alebo dockerd pri userland-proxy=false; coturn)
  for p in 80/tcp 443/tcp 7881/tcp 7882/udp 3478/udp; do
    proto="${p#*/}"; port="${p%/*}"; flag=-ltnpH; [ "$proto" = udp ] && flag=-lunpH
    owner="$(ss $flag "sport = :$port" 2>/dev/null | awk '{print $NF}' | head -1)"
    if [ -z "$owner" ] || echo "$owner" | grep -qE 'docker-proxy|dockerd|turnserver'; then log "  port $p voľný/náš  OK"
    else warn "  port $p obsadený: $owner"; FAIL=1; fi
  done
  free_gb=$(df -BG --output=avail . | tail -1 | tr -dc 0-9)
  if [ "$free_gb" -ge 20 ]; then log "  disk ${free_gb} GB voľných  OK"
  else warn "  disk len ${free_gb} GB voľných (minimum 20 GB)"; FAIL=1; fi
  mem_mb=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)
  if [ "$mem_mb" -ge 3500 ]; then log "  RAM ${mem_mb} MB  OK"; else warn "  RAM ${mem_mb} MB (odporúčané 4 GB+)"; fi
  [ "$FAIL" = 0 ] || die "pre-flight zlyhal — opravte DNS/porty/miesto podľa server/DEPLOY-CHECKLIST.md a spustite znova"
else
  require_cmd docker openssl sed
  docker compose version >/dev/null 2>&1 || die "potrebný je Docker Compose v2 (docker compose)"
fi

# ----------------------------------------------------------------- 1. hardening
if [ "$HARDEN" = 1 ]; then
  log "hardening systému"
  bash scripts/harden.sh
fi

# ----------------------------------------------------------------- 2. .env + secrets
ENV_KEYS="MATRIX_DOMAIN APP_DOMAIN CALL_DOMAIN AUTH_DOMAIN AUTH_PREFIX NTFY_DOMAIN TURN_DOMAIN SERVER_IP LETSENCRYPT_EMAIL LIVEKIT_USE_EXTERNAL_IP LIVEKIT_NODE_IP LIVEKIT_API_KEY LIVEKIT_API_SECRET POSTGRES_PASSWORD SYNAPSE_MACAROON_SECRET_KEY SYNAPSE_FORM_SECRET LK_JWT_AS_TOKEN LK_JWT_HS_TOKEN TURN_SECRET ANDROID_CERT_SHA256 APPLE_TEAM_ID ADMIN_CLIENT_ID"
default_for() {
  case "$1" in
    MATRIX_DOMAIN|APP_DOMAIN|CALL_DOMAIN|AUTH_DOMAIN|AUTH_PREFIX|NTFY_DOMAIN|TURN_DOMAIN) eval "echo \$$1" ;;
    SERVER_IP|LIVEKIT_NODE_IP) echo "$SERVER_IP" ;;
    LETSENCRYPT_EMAIL) echo "$LE_EMAIL" ;;
    LIVEKIT_USE_EXTERNAL_IP) echo false ;;   # node_ip = IP servera (zadaná pri nasadení)
    LIVEKIT_API_KEY) echo "psst$(gen_secret 6)" ;;
    POSTGRES_PASSWORD) gen_secret 24 ;;
    # odtlačok release certifikátu z ~/psst-keys (verejný údaj) — Android App Links
    ANDROID_CERT_SHA256) echo "3A:64:28:CF:51:EE:8F:5E:10:E8:4F:AC:5C:A8:A6:B3:C3:B8:C3:4D:26:74:DB:0F:22:24:D1:D0:09:7D:38:99" ;;
    APPLE_TEAM_ID) echo "$TEAM_ID" ;;
    ADMIN_CLIENT_ID) echo "01KPSSTADM1N0000000000000A" ;;   # ULID statického MAS klienta administrácie (D56)
    *) gen_secret 32 ;;
  esac
}
set_env() { # set_env KEY VALUE — prepíše/doplní hodnotu v .env
  if grep -q "^$1=" .env; then
    awk -v k="$1" -v v="$2" 'BEGIN{FS=OFS="="} $1==k{print k"="v; next} {print}' .env > .env.new && mv .env.new .env
  else printf '%s=%s\n' "$1" "$2" >> .env; fi
}
umask 077
mkdir -p data secrets secrets/mas secrets/apns secrets/fcm secrets/admin downloads/files   # downloads/ before compose up (bind mount would be created as root)
[ -f .env ] || { log "vytváram server/.env s novými tajomstvami"; printf '# PSST server — vygenerované %s. NECOMMITOVAŤ. Zálohovať!\n' "$(date -u +%FT%TZ)" > .env; }
for k in $ENV_KEYS; do grep -q "^${k}=" .env || printf '%s=%s\n' "$k" "$(default_for "$k")" >> .env; done
# hodnoty z príkazového riadka majú prednosť (zmena IP/e-mailu/Team ID pri opakovanom nasadení)
if [ "$LOCAL_TEST" = 0 ]; then set_env SERVER_IP "$SERVER_IP"; set_env LIVEKIT_NODE_IP "$SERVER_IP"; set_env LETSENCRYPT_EMAIL "$LE_EMAIL"; fi
[ -n "$TEAM_ID" ] && set_env APPLE_TEAM_ID "$TEAM_ID"
[ -n "$CONTACT" ] && set_env OPERATOR_CONTACT "\"$CONTACT\""
[ -n "$HOSTING" ] && set_env OPERATOR_HOSTING "\"$HOSTING\""
# skripty (members/backup/healthcheck) musia používať rovnaké compose súbory
if [ "$LOCAL_TEST" = 1 ]; then set_env COMPOSE_FILE "compose.yml:compose.test.yml"; else set_env COMPOSE_FILE "compose.yml"; fi
chmod 600 .env
load_env
# odvodené hodnoty (po načítaní .env)
MAS_PUBLIC_BASE="https://${AUTH_DOMAIN}${AUTH_PREFIX}/"
TURN_DOMAIN_RE_SED="$(printf "%s" "$TURN_DOMAIN" | sed "s/\\./\\\\\\\\./g")"   # call\\.macet\\.eu pre sed → call\.macet\.eu v nginx
ALL_DOMAINS="$(printf "%s\n" "$MATRIX_DOMAIN" "$APP_DOMAIN" "$CALL_DOMAIN" "$AUTH_DOMAIN" "$NTFY_DOMAIN" "$TURN_DOMAIN" | awk "!s[\$0]++" | tr "\n" " ")"; ALL_DOMAINS="${ALL_DOMAINS% }"

# MAS: šifrovací kľúč, podpisové kľúče (RSA + EC), zdieľané tajomstvo so Synapse
[ -s secrets/mas/encryption ] || openssl rand -hex 32 | tr -d "\n" > secrets/mas/encryption
[ -s secrets/mas/rsa.pem ] || openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out secrets/mas/rsa.pem 2>/dev/null
[ -s secrets/mas/ec.pem ] || openssl ecparam -name prime256v1 -genkey -noout -out secrets/mas/ec.pem 2>/dev/null
[ -s secrets/mas/mas_shared_secret ] || openssl rand -hex 32 | tr -d "\n" > secrets/mas/mas_shared_secret
# administrácia (D56): tajomstvo MAS klienta + heslo read-only DB roly psst_admin_ro
[ -s secrets/admin/client_secret ] || openssl rand -hex 32 | tr -d "\n" > secrets/admin/client_secret
[ -s secrets/admin/db_password ] || openssl rand -hex 24 | tr -d "\n" > secrets/admin/db_password
ADMIN_CLIENT_SECRET="$(cat secrets/admin/client_secret)"
# heslo pre šifrované zálohy (BEZ NEHO SA ZÁLOHA NEDÁ OBNOVIŤ — uložte ho aj mimo servera)
NEW_BACKUP_PASS=0
[ -s secrets/backup.pass ] || { openssl rand -base64 48 | tr -d '\n' > secrets/backup.pass; NEW_BACKUP_PASS=1; }
# MAS beží v kontajneri ako UID 65532 (distroless nonroot)
if [ "$(id -u)" = 0 ]; then chmod 700 secrets/mas; chmod 600 secrets/mas/*; chown -R 65532:65532 secrets/mas
else chmod 755 secrets/mas; chmod 644 secrets/mas/*; fi   # lokálny test (colima/virtiofs)
umask 022

# ----------------------------------------------------------------- 3. render
mkdir -p data/config/coturn data/config/synapse data/config/livekit data/config/nginx data/config/nginx-main \
         data/config/element-call data/config/app-default/legal data/config/mas \
         data/config/sygnal data/synapse data/postgres data/certbot/conf data/certbot/www \

chmod 700 data

render() { # render <template> <output>
  sed -e "s|__MATRIX_DOMAIN__|${MATRIX_DOMAIN}|g" -e "s|__APP_DOMAIN__|${APP_DOMAIN}|g" \
      -e "s|__CALL_DOMAIN__|${CALL_DOMAIN}|g" -e "s|__AUTH_DOMAIN__|${AUTH_DOMAIN}|g" \
      -e "s|__NTFY_DOMAIN__|${NTFY_DOMAIN}|g" -e "s|__TURN_DOMAIN__|${TURN_DOMAIN}|g" \
      -e "s|__AUTH_PREFIX__|${AUTH_PREFIX}|g" -e "s|__MAS_PUBLIC_BASE__|${MAS_PUBLIC_BASE}|g" \
      -e "s|__TURN_DOMAIN_RE__|${TURN_DOMAIN_RE_SED}|g" \
      -e "s|__NGINX_IP__|${NGINX_IP}|g" -e "s|__SERVER_IP__|${SERVER_IP}|g" \
      -e "s|__DOCKER_GW__|${DOCKER_GW}|g" -e "s|__TURN_SECRET__|${TURN_SECRET}|g" \
      -e "s|__POSTGRES_PASSWORD__|${POSTGRES_PASSWORD}|g" \
      -e "s|__SYNAPSE_MACAROON_SECRET_KEY__|${SYNAPSE_MACAROON_SECRET_KEY}|g" \
      -e "s|__SYNAPSE_FORM_SECRET__|${SYNAPSE_FORM_SECRET}|g" \
      -e "s|__LK_JWT_AS_TOKEN__|${LK_JWT_AS_TOKEN}|g" -e "s|__LK_JWT_HS_TOKEN__|${LK_JWT_HS_TOKEN}|g" \
      -e "s|__LIVEKIT_API_KEY__|${LIVEKIT_API_KEY}|g" -e "s|__LIVEKIT_API_SECRET__|${LIVEKIT_API_SECRET}|g" \
      -e "s|__LIVEKIT_USE_EXTERNAL_IP__|${LIVEKIT_USE_EXTERNAL_IP}|g" \
      -e "s|__LIVEKIT_NODE_IP_LINE__|  node_ip: ${LIVEKIT_NODE_IP}|g" \
      -e "s|__ANDROID_CERT_SHA256__|${ANDROID_CERT_SHA256:-}|g" -e "s|__APPLE_TEAM_ID__|${APPLE_TEAM_ID:-TEAMID}|g" \
      -e "s|__ADMIN_CLIENT_ID__|${ADMIN_CLIENT_ID}|g" -e "s|__ADMIN_CLIENT_SECRET__|${ADMIN_CLIENT_SECRET}|g" \
      "$1" > "$2.tmp"
  if grep -q '__[A-Z_]*__' "$2.tmp"; then die "nevyplnený placeholder v $2: $(grep -o '__[A-Z_]*__' "$2.tmp" | sort -u | tr '\n' ' ')"; fi
  # zapisovať NA MIESTE (nie mv): jednotlivé súbory sú v kontajneroch bind-mountované a mv by vytvoril nový
  # inode — bežiaci kontajner by naďalej videl starú verziu (napr. nginx.conf)
  if [ -f "$2" ]; then cat "$2.tmp" > "$2"; rm -f "$2.tmp"; else mv "$2.tmp" "$2"; fi
}
cfg_sums() { (cd data/config 2>/dev/null && find . -type f -exec cksum {} + 2>/dev/null | sort -k3) || true; }
CFG_BEFORE="$(cfg_sums)"
log "renderujem konfigurácie do data/config/"
render templates/synapse/homeserver.yaml        data/config/synapse/homeserver.yaml
render templates/synapse/log.config             data/config/synapse/log.config
render templates/synapse/lk-jwt-appservice.yaml data/config/synapse/lk-jwt-appservice.yaml
cat secrets/mas/mas_shared_secret > data/config/synapse/mas_shared_secret
chmod 644 data/config/synapse/mas_shared_secret
render templates/mas/config.yaml                data/config/mas/config.yaml
# MAS na vlastnej subdoméne → bez prefixu (MAS nepovoľuje prázdny prefix)
[ -n "$AUTH_PREFIX" ] || sed -i.bak '/^      prefix: ""/d' data/config/mas/config.yaml && rm -f data/config/mas/config.yaml.bak
if [ "$LOCAL_TEST" = 1 ]; then
  # lokálne prichádzajú všetci testovací klienti z jednej IP → voľnejšie limity MAS
  cat >> data/config/mas/config.yaml <<'YAML'

# LEN lokálny test (--local-test)
rate_limiting:
  login:
    per_ip: {burst: 1000, per_second: 100}
    per_account: {burst: 1000, per_second: 100}
  registration: {burst: 1000, per_second: 100}
YAML
fi
render templates/livekit/livekit.yaml           data/config/livekit/livekit.yaml
# coturn: na ktorých IP počúva, z ktorej robí relay a kam smie relay posielať (len na vlastnú SFU)
if [ "$LOCAL_TEST" = 1 ]; then
  TURN_LISTEN="listening-ip=${DOCKER_GW}\nlistening-ip=127.0.0.1\nrelay-ip=127.0.0.1"
  TURN_PEERS="allowed-peer-ip=127.0.0.1\nallow-loopback-peers"   # SFU je lokálne na 127.0.0.1
else
  PRIV_IP="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}' | head -1)"
  if [ -z "$PRIV_IP" ] || [ "$PRIV_IP" = "$SERVER_IP" ]; then
    TURN_LISTEN="listening-ip=${DOCKER_GW}\nrelay-ip=${SERVER_IP}"   # len TLS cez nginx (UDP 3478 sa nepublikuje)
    TURN_PEERS="allowed-peer-ip=${SERVER_IP}"
  else   # cloud s 1:1 NAT (verejná IP nie je na rozhraní)
    TURN_LISTEN="listening-ip=${DOCKER_GW}\nrelay-ip=${PRIV_IP}\nexternal-ip=${SERVER_IP}/${PRIV_IP}"
    TURN_PEERS="allowed-peer-ip=${SERVER_IP}\nallowed-peer-ip=${PRIV_IP}"
  fi
fi
mkdir -p data/config/coturn
awk -v L="$TURN_LISTEN" -v P="$TURN_PEERS" '
  /^__TURN_LISTEN_LINES__$/ { gsub(/\\n/, "\n", L); print L; next }
  /^__TURN_ALLOWED_PEER_LINES__$/ { gsub(/\\n/, "\n", P); print P; next }
  { print }' templates/coturn/turnserver.conf > data/config/coturn/turnserver.tpl
render data/config/coturn/turnserver.tpl data/config/coturn/turnserver.conf
rm -f data/config/coturn/turnserver.tpl
chmod 644 data/config/coturn/turnserver.conf
render templates/nginx/nginx.conf               data/config/nginx-main/nginx.conf
render templates/nginx/psst.conf                data/config/nginx/psst.conf
# MAS: buď cesta na MATRIX_DOMAIN (MAS_PATH), alebo samostatný vhost (AUTH_VHOST) — nikdy oboje
if [ -n "$AUTH_PREFIX" ] && [ "$AUTH_DOMAIN" = "$MATRIX_DOMAIN" ]; then
  sed -i.bak '/# >>> AUTH_VHOST/,/# <<< AUTH_VHOST/d' data/config/nginx/psst.conf
else
  sed -i.bak '/# >>> MAS_PATH/,/# <<< MAS_PATH/d' data/config/nginx/psst.conf
fi
rm -f data/config/nginx/psst.conf.bak
render templates/element-call/config.json       data/config/element-call/config.json
render templates/app/config.json                data/config/app-default/config.json
render templates/app/index.html                 data/config/app-default/index.html
for f in templates/app/legal/*.html; do
  out="data/config/app-default/legal/$(basename "$f")"
  render "$f" "$out"
  # kontakt a hosting prevádzkovateľa (--contact / --hosting); inak zostanú viditeľné zástupné texty
  esc() { printf '%s' "$1" | sed -e 's/[&|\\]/\\&/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }
  [ -n "${OPERATOR_CONTACT:-}" ] && sed -i.bak "s|\[DOPLNIT_KONTAKT\]|$(esc "$OPERATOR_CONTACT")|g" "$out"
  [ -n "${OPERATOR_HOSTING:-}" ] && sed -i.bak "s|\[DOPLNIT_POSKYTOVATEL_A_KRAJINA_SERVERA\]|$(esc "$OPERATOR_HOSTING")|g" "$out"
  rm -f "$out.bak"
done
grep -q 'DOPLNIT_KONTAKT' data/config/app-default/legal/terms.html && warn "Podmienky/Súkromie: chýba kontakt — spustite znova s --contact \"vas@email\""
mkdir -p data/config/app-default/.well-known
render templates/app/well-known/assetlinks.json data/config/app-default/.well-known/assetlinks.json
render templates/app/well-known/apple-app-site-association data/config/app-default/.well-known/apple-app-site-association

# Sygnal (vlastná push brána): Android cez FCM HTTP v1, iOS cez APNs — každé len ak je nahraný kľúč
APNS_KEY="$(ls secrets/apns/AuthKey_*.p8 2>/dev/null | head -1 || true)"
FCM_KEY="secrets/fcm/service-account.json"
PROFILES=""; SYG_APPS=""
if [ -s "$FCM_KEY" ]; then
  FCM_PROJECT="$(sed -n 's/.*"project_id": *"\([^"]*\)".*/\1/p' "$FCM_KEY" | head -1)"
  [ -n "$FCM_PROJECT" ] || die "$FCM_KEY: chýba project_id (je to JSON kľúč service accountu Firebase?)"
  # app_id = pusher app_id Android appky (BuildTimeConfig.PUSHER_APP_ID_RELEASE)
  for app_id in ${ANDROID_PUSH_APP_IDS:-eu.macet.psst}; do
    SYG_APPS+="$(printf '  %s:\n    type: gcm\n    api_version: v1\n    project_id: %s\n    service_account_file: /fcm/service-account.json\n ' "$app_id" "$FCM_PROJECT")"$'\n'
  done
  log "Android push: Sygnal → FCM HTTP v1 (Firebase projekt $FCM_PROJECT)"
else
  log "Android push: vypnutý (JSON kľúč service accountu Firebase do $FCM_KEY a spustite znova)"
fi
if [ -n "$APNS_KEY" ] && [ -n "${APPLE_TEAM_ID:-}" ]; then
  KEY_ID="$(basename "$APNS_KEY" .p8)"; KEY_ID="${KEY_ID#AuthKey_}"
  # app_id podľa iOS appky: eu.macet.psst.ios.prod (Release, APNs production), .dev (Debug, sandbox)
  for app_id in ${IOS_PUSH_APP_IDS:-eu.macet.psst.ios.prod eu.macet.psst.ios.dev}; do
    platform=production; case "$app_id" in *.dev) platform=sandbox ;; esac
    SYG_APPS+="$(printf '  %s:\n    type: apns\n    keyfile: /apns/%s\n    key_id: %s\n    team_id: %s\n    topic: eu.macet.psst\n    platform: %s\n ' \
      "$app_id" "$(basename "$APNS_KEY")" "$KEY_ID" "$APPLE_TEAM_ID" "$platform")"$'\n'
  done
  log "iOS push: Sygnal → APNs (kľúč $KEY_ID, tím $APPLE_TEAM_ID)"
else
  [ -n "$APNS_KEY" ] && warn "APNs kľúč je nahraný, ale chýba --apple-team-id → iOS push vypnutý"
  log "iOS push: vypnutý (secrets/apns/AuthKey_<KEY_ID>.p8 + --apple-team-id)"
fi
if [ -n "$SYG_APPS" ]; then
  { sed '/__SYGNAL_APPS__/,$d' templates/sygnal/sygnal.yaml; printf '%s' "$SYG_APPS" | sed 's/^ $//'; } > data/config/sygnal/sygnal.tmp
  install -m 644 data/config/sygnal/sygnal.tmp data/config/sygnal/sygnal.yaml; rm -f data/config/sygnal/sygnal.tmp
  # Sygnal beží v kontajneri ako root → na serveri ostávajú kľúče 600 root; len lokálny test (Mac) potrebuje 644
  if [ "$(id -u)" = 0 ]; then
    [ -s "$FCM_KEY" ] && { chown root:root "$FCM_KEY"; chmod 600 "$FCM_KEY"; }
    [ -n "$APNS_KEY" ] && { chown root:root "$APNS_KEY"; chmod 600 "$APNS_KEY"; }
  else
    [ -s "$FCM_KEY" ] && chmod 644 "$FCM_KEY"
    [ -n "$APNS_KEY" ] && chmod 644 "$APNS_KEY"
  fi
  PROFILES="sygnal"
fi
export COMPOSE_PROFILES="$PROFILES"
# zapamätať profily pre ostatné skripty (members.sh, backup.sh, healthcheck.sh)
set_env COMPOSE_PROFILES "$PROFILES"

# ----------------------------------------------------------------- 4. PSST web
if [ ! -f app/index.html ] || grep -q 'psst-placeholder' app/index.html 2>/dev/null; then
  if bash scripts/fetch-web.sh >/dev/null 2>&1; then log "PSST web stiahnutý do app/"
  else warn "PSST web sa nepodarilo stiahnuť — dávam dočasnú stránku (neskôr: scripts/fetch-web.sh)"
       cp data/config/app-default/index.html app/index.html; fi
fi

# ----------------------------------------------------------------- 5. certifikát (dočasný) + štart
CERT_DIR=data/certbot/conf/live/psst
SAN="$(for d in $ALL_DOMAINS; do printf 'DNS:%s,' "$d"; done)"; SAN="${SAN%,}"
make_selfsigned() {
  mkdir -p "$CERT_DIR"
  openssl req -x509 -nodes -newkey rsa:2048 -days 30 -keyout "$CERT_DIR/privkey.pem" -out "$CERT_DIR/fullchain.pem" \
    -subj "/CN=${MATRIX_DOMAIN}" -addext "subjectAltName=${SAN}" 2>/dev/null
  chmod 644 "$CERT_DIR/fullchain.pem"
  touch "$CERT_DIR/.psst-dummy"
}
# dočasný certifikát aj keď pribudla subdoména (aktualizácia zo staršej verzie bez auth/ntfy/turn)
if [ ! -f "$CERT_DIR/fullchain.pem" ] || { [ -f "$CERT_DIR/.psst-dummy" ] && ! openssl x509 -in "$CERT_DIR/fullchain.pem" -noout -text | grep -q "DNS:${TURN_DOMAIN}"; }; then
  log "vytváram dočasný self-signed certifikát pre: $ALL_DOMAINS"
  make_selfsigned
fi

if [ "$PULL" = 1 ]; then log "sťahujem image"; compose pull --ignore-buildable --quiet 2>/dev/null || compose pull --ignore-buildable; fi   # psst-admin sa zostavuje lokálne

log "štartujem PostgreSQL"
compose run --rm --no-deps -T --entrypoint sh postgres -c \
  '[ "$(stat -c %U /var/lib/postgresql)" = postgres ] || chown -R postgres:postgres /var/lib/postgresql' >/dev/null
compose up -d postgres
wait_healthy postgres 120 || die "PostgreSQL nenaštartoval"
# databáza pre MAS (idempotentne)
if ! compose exec -T postgres psql -U synapse -d synapse -tAc "SELECT 1 FROM pg_database WHERE datname='mas'" | grep -q 1; then
  log "vytváram databázu mas"
  compose exec -T postgres psql -U synapse -d synapse -qc "CREATE DATABASE mas ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C' TEMPLATE template0" >/dev/null
fi
compose run --rm --no-deps -T --entrypoint sh synapse -c '[ "$(stat -c %u /data)" = 991 ] || chown -R 991:991 /data' >/dev/null

admin_secrets
log "zostavujem psst-admin"
compose build -q admin

log "štartujem celý stack"
compose up -d --remove-orphans
# služby, ktorých konfigurácia sa pri tomto behu zmenila, reštartovať (compose up -d zmenu obsahu nevidí)
if [ -n "$CFG_BEFORE" ]; then
  CHANGED="$(diff <(printf '%s\n' "$CFG_BEFORE") <(cfg_sums) | awk '/^[<>]/{print $4}' | cut -d/ -f2 | sort -u || true)"
  RESTART=""
  for d in $CHANGED; do
    case "$d" in
      nginx|nginx-main|app-default) RESTART+=" nginx" ;;
      synapse) RESTART+=" synapse lk-jwt-service" ;;
      livekit|mas|coturn|element-call|sygnal) RESTART+=" $d" ;;
    esac
  done
  RESTART="$(printf '%s\n' $RESTART | sort -u | tr '\n' ' ')"
  if [ -n "${RESTART// }" ]; then
    log "zmenená konfigurácia → reštartujem:$RESTART"
    for svc in $RESTART; do compose ps --status running --services 2>/dev/null | grep -qx "$svc" && compose restart "$svc" >/dev/null; done
  fi
fi
wait_healthy synapse 300 || { compose logs --tail=80 synapse mas; die "Synapse nenaštartoval"; }
wait_healthy nginx 90 || { compose logs --tail=80 nginx; die "nginx nenaštartoval"; }
# stránka na stiahnutie appiek https://<APP_DOMAIN>/download (D59): používateľ psst-dl smie cez SSH len
# scripts/downloads.py (forced command) — CI a build skripty nahrávajú nové verzie, staré sa mažú
if [ "$(id -u)" = 0 ] && [ "$LOCAL_TEST" = 0 ]; then
  id psst-dl >/dev/null 2>&1 || useradd --system --home-dir /var/lib/psst-dl --create-home --shell /bin/sh psst-dl
  install -d -o psst-dl -g psst-dl -m 755 downloads downloads/files
  if [ -s secrets/download_upload.pub ]; then
    install -d -o psst-dl -g psst-dl -m 700 /var/lib/psst-dl/.ssh
    printf 'command="env APP_DOMAIN=%s PSST_DOWNLOADS=%s /usr/bin/python3 %s ssh",no-pty,no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-user-rc %s\n' \
      "$APP_DOMAIN" "$PWD/downloads" "$PWD/scripts/downloads.py" "$(cat secrets/download_upload.pub)" > /var/lib/psst-dl/.ssh/authorized_keys
    chown psst-dl:psst-dl /var/lib/psst-dl/.ssh/authorized_keys; chmod 600 /var/lib/psst-dl/.ssh/authorized_keys
    HC=/etc/ssh/sshd_config.d/00-hardening.conf
    if [ -f "$HC" ] && grep -q '^AllowUsers' "$HC" && ! grep -q '^AllowUsers.*psst-dl' "$HC"; then
      cp "$HC" "$HC.bak"; sed -i 's/^AllowUsers .*/& psst-dl/' "$HC"
      if sshd -t; then systemctl reload ssh 2>/dev/null || systemctl reload sshd; else cp "$HC.bak" "$HC"; warn "sshd -t zlyhal, AllowUsers vrátené"; fi
    fi
  else
    warn "secrets/download_upload.pub chýba → nahrávanie na stránku /download vypnuté"
  fi
  sudo -u psst-dl env APP_DOMAIN="$APP_DOMAIN" PSST_DOWNLOADS="$PWD/downloads" python3 scripts/downloads.py render >/dev/null
else
  mkdir -p downloads/files; PSST_DOWNLOADS="$PWD/downloads" APP_DOMAIN="$APP_DOMAIN" python3 scripts/downloads.py render >/dev/null || true
fi
# administrácia: read-only prístup k 2 tabuľkám MAS (kto sa ktorou pozvánkou zaregistroval) + Synapse admin token
compose exec -T postgres psql -U synapse -d mas -v ON_ERROR_STOP=1 -q >/dev/null <<SQL || warn "DB rola psst_admin_ro: zlyhalo"
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'psst_admin_ro') THEN CREATE ROLE psst_admin_ro LOGIN; END IF;
END \$\$;
ALTER ROLE psst_admin_ro WITH LOGIN PASSWORD '$(cat secrets/admin/db_password)' NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE mas TO psst_admin_ro;
GRANT USAGE ON SCHEMA public TO psst_admin_ro;
GRANT SELECT ON user_registrations, user_registration_tokens TO psst_admin_ro;
SQL
[ -s secrets/admin_token ] || PSST_QUIET=1 scripts/members.sh list >/dev/null 2>&1 || warn "Synapse admin token sa nepodarilo vydať"
admin_secrets
compose up -d admin >/dev/null && compose restart admin >/dev/null
compose exec -T nginx nginx -s reload >/dev/null 2>&1 || true

# ----------------------------------------------------------------- 6. Let's Encrypt
if [ "$LETSENCRYPT" = 1 ] && [ -f "$CERT_DIR/.psst-dummy" ]; then
  log "žiadam certifikát Let's Encrypt pre: $ALL_DOMAINS"
  STAGING_ARG=""; [ "$STAGING" = 1 ] && STAGING_ARG="--staging"
  DOMAIN_ARGS=""; for d in $ALL_DOMAINS; do DOMAIN_ARGS+=" -d $d"; done
  compose run --rm --no-deps -T --entrypoint sh certbot -c \
    'rm -rf /etc/letsencrypt/live/psst /etc/letsencrypt/archive/psst /etc/letsencrypt/renewal/psst.conf'
  # shellcheck disable=SC2086
  if compose run --rm --no-deps -T --entrypoint certbot certbot certonly --webroot -w /var/www/certbot --cert-name psst $DOMAIN_ARGS \
       --email "$LETSENCRYPT_EMAIL" --agree-tos --no-eff-email --non-interactive --key-type ecdsa $STAGING_ARG; then
    compose exec -T nginx nginx -s reload
    log "certifikát Let's Encrypt nainštalovaný"
  else
    make_selfsigned; compose exec -T nginx nginx -s reload || true
    die "Let's Encrypt zlyhal (DNS záznamy? port 80 v cloud firewalle?) — opravte a spustite ./deploy.sh znova"
  fi
fi

# ----------------------------------------------------------------- 7. zálohy + healthcheck
# cron aj pri --skip-harden (systém zabezpečený inak) — len nie pri lokálnom teste
if [ "$LOCAL_TEST" = 0 ] && [ "$(id -u)" = 0 ]; then
  SERVER_DIR="$(pwd)"
  cat > /etc/cron.d/psst <<CRON
# PSST — spravuje server/deploy.sh
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
# denná šifrovaná záloha 03:17 (rotácia 7 denných / 4 týždenné / 6 mesačných)
17 3 * * * root cd ${SERVER_DIR} && scripts/backup.sh >> /var/log/psst-backup.log 2>&1
# healthcheck každých 10 minút
*/10 * * * * root cd ${SERVER_DIR} && scripts/healthcheck.sh --quiet >> /var/log/psst-health.log 2>&1
CRON
  chmod 644 /etc/cron.d/psst
  log "cron: denné zálohy a healthcheck (/etc/cron.d/psst)"
fi

# pomalšie služby (prvý štart MAS robí migrácie DB)
wait_healthy element-call 90 || true
for _ in $(seq 60); do
  compose exec -T nginx wget -q -O /dev/null http://mas:8080/.well-known/openid-configuration 2>/dev/null && break; sleep 2
done
compose ps
log "spúšťam healthcheck"
bash scripts/healthcheck.sh || warn "healthcheck hlási problém (viď vyššie)"
echo
log "HOTOVO. Ďalší krok: prvý admin a pozvánka"
echo "    sudo scripts/members.sh admin <meno>          # admin účet (vypíše heslo)"
echo "    sudo scripts/members.sh invite [počet] [dni]  # pozývací token → appka: Create account"
if [ "$NEW_BACKUP_PASS" = 1 ]; then
  echo
  warn "Heslo k zálohám je v server/secrets/backup.pass — SKOPÍRUJTE SI HO mimo servera (bez neho sa záloha nedá obnoviť):"
  echo "    sudo cat $(pwd)/secrets/backup.pass"
fi
