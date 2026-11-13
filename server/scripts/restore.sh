#!/usr/bin/env bash
# Obnova PSST servera zo zálohy (scripts/backup.sh) — aj na novom hostiteľovi.
#
#   scripts/restore.sh psst-backup-<čas>.tar.gz [--force]
#
# Predpoklad: čistý server/ (git clone), Docker. Existujúce data/ sa bez --force neprepíšu.
# Po obnove sa spustí ./deploy.sh (ak certifikát v zálohe chýba, vystaví sa nový).
. "$(dirname "$0")/lib.sh"

ARCHIVE="${1:-}"; FORCE="${2:-}"
[ -f "$ARCHIVE" ] || die "použitie: scripts/restore.sh <psst-backup-….tar.gz> [--force]"
ARCHIVE="$(cd "$(dirname "$ARCHIVE")" && pwd)/$(basename "$ARCHIVE")"
if [ -d data/postgres ] && [ -n "$(ls -A data/postgres 2>/dev/null)" ] && [ "$FORCE" != "--force" ]; then
  die "data/postgres nie je prázdne — obnova by prepísala existujúci server (použite --force)"
fi

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
tar -C "$WORK" -xzf "$ARCHIVE"
B="$(find "$WORK" -maxdepth 1 -type d -name 'psst-backup-*' | head -1)"
[ -n "$B" ] && [ -f "$B/db.dump" ] && [ -f "$B/env" ] || die "neplatný archív"

compose down 2>/dev/null || true
if [ "$FORCE" = "--force" ]; then
  log "--force: mažem existujúce dáta"
  docker run --rm -v "$PWD/data:/d" docker.io/library/postgres:18.7-alpine sh -c 'rm -rf /d/postgres /d/synapse /d/certbot'
fi

umask 077
cp "$B/env" .env
[ -d "$B/secrets" ] && { mkdir -p secrets; cp -R "$B/secrets/." secrets/; }
load_env
mkdir -p data/synapse data/postgres data/certbot/conf data/certbot/www data/config/synapse
chmod 700 data

log "obnovujem Synapse dáta (media_store + podpisový kľúč)"
compose run --rm --no-deps -T --entrypoint sh synapse -c 'tar -C /data -xzf - && chown -R 991:991 /data' < "$B/synapse-data.tar.gz"
if [ -s "$B/letsencrypt.tar.gz" ]; then
  log "obnovujem certifikáty"
  compose run --rm --no-deps -T --entrypoint tar certbot -C /etc/letsencrypt -xzf - < "$B/letsencrypt.tar.gz"
fi

log "obnovujem databázu"
compose up -d postgres
wait_healthy postgres 120 || die "PostgreSQL nenaštartoval"
compose exec -T postgres pg_restore -U synapse -d synapse --no-owner --exit-on-error < "$B/db.dump"

log "spúšťam ./deploy.sh"
./deploy.sh
