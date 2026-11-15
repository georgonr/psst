#!/usr/bin/env bash
# Obnova PSST servera zo šifrovanej zálohy (scripts/backup.sh) — aj na novom hostiteľovi (migrácia).
#
#   scripts/restore.sh <psst-….tar.gz.enc> [--force]
#
# Predpoklad: server/ z gitu, Docker, heslová fráza v secrets/backup.pass (alebo PSST_BACKUP_PASS_FILE).
# Existujúce dáta sa bez --force neprepíšu. Po obnove naštartuje stack; pri migrácii na novú IP
# potom spustite ./deploy.sh <nová_IP> <email> (DNS najprv presmerujte).
. "$(dirname "$0")/lib.sh"
ARCHIVE="${1:-}"; FORCE="${2:-}"
[ -f "$ARCHIVE" ] || die "použitie: scripts/restore.sh <psst-….tar.gz.enc> [--force]"
PASS_FILE="${PSST_BACKUP_PASS_FILE:-secrets/backup.pass}"
[ -s "$PASS_FILE" ] || die "chýba heslová fráza ($PASS_FILE)"
if [ -n "$(ls -A data/postgres 2>/dev/null)" ] && [ "$FORCE" != "--force" ]; then
  die "data/postgres nie je prázdne — obnova by prepísala existujúci server (použite --force)"
fi
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
log "dešifrujem zálohu"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 -pass "file:$PASS_FILE" -in "$ARCHIVE" | tar -C "$WORK" -xzf - \
  || die "dešifrovanie zlyhalo (nesprávna heslová fráza?)"
B="$(find "$WORK" -maxdepth 1 -type d -name 'psst-backup-*' | head -1)"
[ -f "$B/synapse.dump" ] && [ -f "$B/mas.dump" ] && [ -f "$B/env" ] || die "neplatný archív"

[ -f .env ] && compose down --remove-orphans >/dev/null 2>&1 || true
if [ "$FORCE" = "--force" ]; then
  log "--force: mažem existujúce dáta"
  docker run --rm -v "$PWD/data:/d" docker.io/library/postgres:18.7-alpine sh -c 'rm -rf /d/postgres /d/synapse /d/config /d/certbot'
fi
umask 077
cp "$B/env" .env
mkdir -p secrets; cp -R "$B/secrets/." secrets/
load_env
# konfigurácie a dáta čítajú kontajnery pod inými UID (Synapse 991, Sygnal, nginx) → bežné práva 644/755
umask 022
mkdir -p data/synapse data/postgres data/certbot
chmod 700 data
tar -C data -xzf "$B/config.tar.gz"
[ -f "$B/admin.tar.gz" ] && tar -C data -xzf "$B/admin.tar.gz"
[ -s "$B/letsencrypt.tar.gz" ] && tar -C data/certbot -xzf "$B/letsencrypt.tar.gz"
if [ "$(id -u)" = 0 ]; then chown -R 65532:65532 secrets/mas; else chmod 755 secrets/mas; chmod 644 secrets/mas/*; fi

log "obnovujem Synapse dáta (médiá + podpisový kľúč)"
compose run --rm --no-deps -T --entrypoint sh synapse -c 'tar -C /data -xzf - && chown -R 991:991 /data' < "$B/synapse-data.tar.gz"
log "obnovujem databázy"
# prázdny dátový adresár musí patriť používateľovi postgres (entrypoint postgres 18 už beží ako postgres)
compose run --rm --no-deps -T --entrypoint sh postgres -c 'chown -R postgres:postgres /var/lib/postgresql && chmod 700 /var/lib/postgresql'
compose up -d postgres
wait_healthy postgres 120 || die "PostgreSQL nenaštartoval"
compose exec -T postgres psql -U synapse -d synapse -qc "DROP DATABASE IF EXISTS mas" >/dev/null
compose exec -T postgres psql -U synapse -d synapse -qc "CREATE DATABASE mas ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C' TEMPLATE template0" >/dev/null
compose exec -T postgres pg_restore -U synapse -d synapse --no-owner --clean --if-exists < "$B/synapse.dump" || warn "pg_restore synapse hlásil varovania"
compose exec -T postgres pg_restore -U synapse -d mas --no-owner < "$B/mas.dump" || warn "pg_restore mas hlásil varovania"
cmp -s "$B/signing.key" <(compose run --rm --no-deps -T --entrypoint cat synapse "/data/${MATRIX_DOMAIN}.signing.key") \
  && log "podpisový kľúč obnovený (zhoda)" || die "podpisový kľúč sa nezhoduje so zálohou!"
log "štartujem stack"
admin_secrets   # administrácia (D56): kópie tajomstiev pre UID 10001
compose up -d --remove-orphans
wait_healthy synapse 300 || die "Synapse nenaštartoval"
for svc in nginx element-call livekit lk-jwt-service; do wait_healthy "$svc" 120 || warn "$svc ešte nie je healthy"; done
log "obnova hotová — overte: scripts/healthcheck.sh"
