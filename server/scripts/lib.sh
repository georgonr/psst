# shellcheck shell=bash
# Spoločné funkcie pre PSST server skripty. Načítava sa cez: . "$(dirname "$0")/lib.sh"

set -euo pipefail

PSST_SERVER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PSST_SERVER_DIR"

log()  { printf '\033[1;34m[psst]\033[0m %s\n' "$*" >&2; }
warn() { printf '\033[1;33m[psst] VAROVANIE:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[psst] CHYBA:\033[0m %s\n' "$*" >&2; exit 1; }

compose() { docker compose "$@"; }

gen_secret() { openssl rand -hex "${1:-32}"; }

load_env() {
  [ -f .env ] || die "server/.env neexistuje — spustite najprv ./deploy.sh"
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
}

require_cmd() {
  for c in "$@"; do command -v "$c" >/dev/null 2>&1 || die "chýba príkaz '$c'"; done
}

# Počká, kým je kontajner služby healthy (max $2 sekúnd)
wait_healthy() {
  local svc="$1" timeout="${2:-180}" waited=0 cid status
  while :; do
    cid="$(compose ps -q "$svc" 2>/dev/null || true)"
    if [ -n "$cid" ]; then
      status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || echo unknown)"
      [ "$status" = "healthy" ] && return 0
    fi
    [ "$waited" -ge "$timeout" ] && { warn "$svc nie je healthy po ${timeout}s (stav: ${status:-?})"; return 1; }
    sleep 3; waited=$((waited + 3))
  done
}

# Volanie Synapse admin/client API zvnútra kontajnera (nepotrebuje curl na hostiteľovi)
synapse_curl() { compose exec -T synapse curl -sS "$@"; }

admin_token() {
  if [ -n "${SYNAPSE_ADMIN_TOKEN:-}" ]; then printf '%s' "$SYNAPSE_ADMIN_TOKEN"; return; fi
  [ -f secrets/admin_token ] || die "chýba secrets/admin_token — vytvorte admina: scripts/create-admin.sh"
  cat secrets/admin_token
}

# administrácia (D56): kontajner beží ako UID 10001 → vlastné kópie tajomstiev (400) a dátový adresár
admin_secrets() {
  mkdir -p secrets/admin-run data/admin
  rm -f secrets/admin-run/*
  cp secrets/admin/client_secret secrets/admin-run/admin_client_secret
  cp secrets/admin/db_password secrets/admin-run/admin_db_password
  [ -s secrets/admin_token ] && cp secrets/admin_token secrets/admin-run/admin_token
  if [ "$(id -u)" = 0 ]; then
    chown -R 10001:10001 secrets/admin-run data/admin; chmod 500 secrets/admin-run; chmod 400 secrets/admin-run/*; chmod 700 data/admin
  else chmod 755 secrets/admin-run; chmod 777 data/admin; chmod 644 secrets/admin-run/*; fi   # lokálny test bez root
}
