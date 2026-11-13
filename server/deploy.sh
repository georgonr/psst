#!/usr/bin/env bash
# PSST server — nasadenie jedným príkazom.
#
#   ./deploy.sh                  prvé nasadenie aj aktualizácia (idempotentné)
#   ./deploy.sh --staging        certifikáty z Let's Encrypt staging (test)
#   ./deploy.sh --no-letsencrypt bez Let's Encrypt (ostane self-signed certifikát; CI/lokálny test)
#   ./deploy.sh --no-pull        nesťahovať nové image
#
# Čo robí:
#   1. vytvorí server/.env s náhodnými tajomstvami (len prvýkrát; existujúce hodnoty nemení)
#   2. vyrenderuje konfigurácie z templates/ do data/config/
#   3. pripraví adresáre a dočasný self-signed certifikát (aby nginx vedel naštartovať)
#   4. docker compose pull + up -d, počká na healthchecky
#   5. ak certifikát ešte nie je od Let's Encrypt: certbot --webroot → reload nginx
set -euo pipefail
. "$(dirname "$0")/scripts/lib.sh"

LETSENCRYPT="${PSST_LETSENCRYPT:-1}"
PULL=1
for arg in "$@"; do
  case "$arg" in
    --staging) export LETSENCRYPT_STAGING=1 ;;
    --no-letsencrypt) LETSENCRYPT=0 ;;
    --no-pull) PULL=0 ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) die "neznámy prepínač: $arg" ;;
  esac
done

require_cmd docker openssl sed
docker compose version >/dev/null 2>&1 || die "potrebný je Docker Compose v2 (docker compose)"

# ------------------------------------------------------------------ 1. .env
ENV_KEYS="MATRIX_DOMAIN APP_DOMAIN CALL_DOMAIN LETSENCRYPT_EMAIL LETSENCRYPT_STAGING LIVEKIT_USE_EXTERNAL_IP LIVEKIT_NODE_IP LIVEKIT_API_KEY LIVEKIT_API_SECRET POSTGRES_PASSWORD SYNAPSE_REGISTRATION_SHARED_SECRET SYNAPSE_MACAROON_SECRET_KEY SYNAPSE_FORM_SECRET LK_JWT_AS_TOKEN LK_JWT_HS_TOKEN ANDROID_CERT_SHA256 APPLE_TEAM_ID"

default_for() {
  case "$1" in
    MATRIX_DOMAIN) echo "${MATRIX_DOMAIN:-chat.macet.eu}" ;;
    APP_DOMAIN) echo "${APP_DOMAIN:-app.macet.eu}" ;;
    CALL_DOMAIN) echo "${CALL_DOMAIN:-call.macet.eu}" ;;
    LETSENCRYPT_EMAIL) echo "${LETSENCRYPT_EMAIL:-}" ;;
    LETSENCRYPT_STAGING) echo "${LETSENCRYPT_STAGING:-0}" ;;
    LIVEKIT_USE_EXTERNAL_IP) echo "${LIVEKIT_USE_EXTERNAL_IP:-true}" ;;
    LIVEKIT_NODE_IP) echo "${LIVEKIT_NODE_IP:-}" ;;
    LIVEKIT_API_KEY) echo "psst$(gen_secret 6)" ;;
    LIVEKIT_API_SECRET) gen_secret 32 ;;
    POSTGRES_PASSWORD) gen_secret 24 ;;
    # odtlačok release certifikátu z ~/psst-keys (verejný údaj) — pre Android App Links
    ANDROID_CERT_SHA256) echo "${ANDROID_CERT_SHA256:-3A:64:28:CF:51:EE:8F:5E:10:E8:4F:AC:5C:A8:A6:B3:C3:B8:C3:4D:26:74:DB:0F:22:24:D1:D0:09:7D:38:99}" ;;
    # Apple Team ID (10 znakov) — doplniť po založení Apple Developer účtu; prázdne = iOS universal links nefungujú
    APPLE_TEAM_ID) echo "${APPLE_TEAM_ID:-}" ;;
    *) gen_secret 32 ;;
  esac
}

umask 077
if [ ! -f .env ]; then
  log "vytváram server/.env s novými tajomstvami"
  printf '# PSST server — vygenerované %s. NECOMMITOVAŤ. Zálohovať!\n' "$(date -u +%FT%TZ)" > .env
fi
for k in $ENV_KEYS; do
  if ! grep -q "^${k}=" .env; then
    printf '%s=%s\n' "$k" "$(default_for "$k")" >> .env
  fi
done
chmod 600 .env
umask 022
load_env

[ -n "$MATRIX_DOMAIN" ] || die "MATRIX_DOMAIN je prázdne"
if [ "$LETSENCRYPT" = 1 ] && [ -z "${LETSENCRYPT_EMAIL:-}" ]; then
  die "nastavte LETSENCRYPT_EMAIL v server/.env (alebo spustite: LETSENCRYPT_EMAIL=vy@domena ./deploy.sh)"
fi

# ------------------------------------------------------------------ 2. render
mkdir -p data secrets
chmod 700 data secrets
mkdir -p data/config/{synapse,livekit,nginx,element-call,app-default} \
         data/synapse data/postgres data/certbot/conf data/certbot/www

NODE_IP_LINE=""
[ -n "${LIVEKIT_NODE_IP:-}" ] && NODE_IP_LINE="  node_ip: ${LIVEKIT_NODE_IP}"

render() { # render <template> <output>
  sed -e "s|__MATRIX_DOMAIN__|${MATRIX_DOMAIN}|g" \
      -e "s|__APP_DOMAIN__|${APP_DOMAIN}|g" \
      -e "s|__CALL_DOMAIN__|${CALL_DOMAIN}|g" \
      -e "s|__POSTGRES_PASSWORD__|${POSTGRES_PASSWORD}|g" \
      -e "s|__SYNAPSE_REGISTRATION_SHARED_SECRET__|${SYNAPSE_REGISTRATION_SHARED_SECRET}|g" \
      -e "s|__SYNAPSE_MACAROON_SECRET_KEY__|${SYNAPSE_MACAROON_SECRET_KEY}|g" \
      -e "s|__SYNAPSE_FORM_SECRET__|${SYNAPSE_FORM_SECRET}|g" \
      -e "s|__LK_JWT_AS_TOKEN__|${LK_JWT_AS_TOKEN}|g" \
      -e "s|__LK_JWT_HS_TOKEN__|${LK_JWT_HS_TOKEN}|g" \
      -e "s|__LIVEKIT_API_KEY__|${LIVEKIT_API_KEY}|g" \
      -e "s|__ANDROID_CERT_SHA256__|${ANDROID_CERT_SHA256:-}|g" \
      -e "s|__APPLE_TEAM_ID__|${APPLE_TEAM_ID:-TEAMID}|g" \
      -e "s|__LIVEKIT_API_SECRET__|${LIVEKIT_API_SECRET}|g" \
      -e "s|__LIVEKIT_USE_EXTERNAL_IP__|${LIVEKIT_USE_EXTERNAL_IP}|g" \
      -e "s|__LIVEKIT_NODE_IP_LINE__|${NODE_IP_LINE}|g" \
      "$1" > "$2.tmp"
  mv "$2.tmp" "$2"
  chmod 644 "$2"
}
log "renderujem konfigurácie do data/config/"
render templates/synapse/homeserver.yaml      data/config/synapse/homeserver.yaml
render templates/synapse/log.config           data/config/synapse/log.config
render templates/synapse/lk-jwt-appservice.yaml data/config/synapse/lk-jwt-appservice.yaml
render templates/livekit/livekit.yaml         data/config/livekit/livekit.yaml
render templates/nginx/psst.conf              data/config/nginx/psst.conf
render templates/element-call/config.json     data/config/element-call/config.json
render templates/app/config.json              data/config/app-default/config.json
render templates/app/index.html               data/config/app-default/index.html
mkdir -p data/config/app-default/.well-known
render templates/app/well-known/assetlinks.json data/config/app-default/.well-known/assetlinks.json
render templates/app/well-known/apple-app-site-association data/config/app-default/.well-known/apple-app-site-association
if [ ! -f app/index.html ]; then
  warn "app/ neobsahuje PSST web — dávam dočasnú stránku (stiahnite web: scripts/fetch-web.sh)"
  cp data/config/app-default/index.html app/index.html
fi

# ------------------------------------------------------------------ 3. certifikát
CERT_DIR=data/certbot/conf/live/psst
if [ ! -f "$CERT_DIR/fullchain.pem" ]; then
  log "vytváram dočasný self-signed certifikát (nginx potrebuje certifikát na štart)"
  mkdir -p "$CERT_DIR"
  openssl req -x509 -nodes -newkey rsa:2048 -days 30 \
    -keyout "$CERT_DIR/privkey.pem" -out "$CERT_DIR/fullchain.pem" \
    -subj "/CN=${MATRIX_DOMAIN}" \
    -addext "subjectAltName=DNS:${MATRIX_DOMAIN},DNS:${APP_DOMAIN},DNS:${CALL_DOMAIN}" 2>/dev/null
  touch "$CERT_DIR/.psst-dummy"
fi

# ------------------------------------------------------------------ 4. štart
if [ "$PULL" = 1 ]; then
  log "sťahujem image"
  compose pull --quiet --ignore-buildable 2>/dev/null || compose pull --quiet
fi

log "štartujem PostgreSQL"
compose up -d postgres
wait_healthy postgres 120 || die "PostgreSQL nenaštartoval"

# /data Synapse musí patriť UID 991 (používateľ v image)
compose run --rm --no-deps -T --entrypoint sh synapse -c \
  '[ "$(stat -c %u /data)" = 991 ] || chown -R 991:991 /data' >/dev/null

log "štartujem celý stack"
compose up -d --remove-orphans
wait_healthy synapse 240 || { compose logs --tail=80 synapse; die "Synapse nenaštartoval"; }
wait_healthy nginx 60 || { compose logs --tail=80 nginx; die "nginx nenaštartoval"; }
# nová konfigurácia nginxu pri aktualizácii (kontajner nemusel byť znovu vytvorený)
compose exec -T nginx nginx -s reload >/dev/null 2>&1 || true

# ------------------------------------------------------------------ 5. Let's Encrypt
if [ "$LETSENCRYPT" = 1 ] && [ -f "$CERT_DIR/.psst-dummy" ]; then
  log "žiadam certifikát Let's Encrypt pre ${MATRIX_DOMAIN}, ${APP_DOMAIN}, ${CALL_DOMAIN}"
  STAGING_ARG=""
  [ "${LETSENCRYPT_STAGING:-0}" = 1 ] && STAGING_ARG="--staging"
  # dočasný certifikát musí zmiznúť, inak certbot odmietne vytvoriť lineage "psst"
  compose run --rm --no-deps -T --entrypoint sh certbot -c \
    'rm -rf /etc/letsencrypt/live/psst /etc/letsencrypt/archive/psst /etc/letsencrypt/renewal/psst.conf'
  if compose run --rm --no-deps -T certbot certonly --webroot -w /var/www/certbot \
       --cert-name psst -d "$MATRIX_DOMAIN" -d "$APP_DOMAIN" -d "$CALL_DOMAIN" \
       --email "$LETSENCRYPT_EMAIL" --agree-tos --no-eff-email --non-interactive \
       --rsa-key-size 4096 $STAGING_ARG; then
    compose exec -T nginx nginx -s reload
    log "certifikát Let's Encrypt nainštalovaný"
  else
    warn "certbot zlyhal (DNS záznamy? port 80?) — vraciam dočasný certifikát"
    mkdir -p "$CERT_DIR"
    openssl req -x509 -nodes -newkey rsa:2048 -days 30 \
      -keyout "$CERT_DIR/privkey.pem" -out "$CERT_DIR/fullchain.pem" -subj "/CN=${MATRIX_DOMAIN}" \
      -addext "subjectAltName=DNS:${MATRIX_DOMAIN},DNS:${APP_DOMAIN},DNS:${CALL_DOMAIN}" 2>/dev/null
    touch "$CERT_DIR/.psst-dummy"
    compose exec -T nginx nginx -s reload || true
    die "Let's Encrypt certifikát sa nepodarilo získať; opravte DNS/firewall a spustite ./deploy.sh znova"
  fi
fi

compose ps
log "hotovo. Ďalej: scripts/create-admin.sh (prvý admin), scripts/new-invite.sh (pozývací token)"
