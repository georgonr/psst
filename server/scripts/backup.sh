#!/usr/bin/env bash
# Kompletná záloha PSST servera do jedného archívu (beží za chodu, bez odstávky).
#
#   scripts/backup.sh [cieľový_adresár=server/backups]
#
# Obsah archívu psst-backup-<čas>.tar.gz:
#   db.dump               pg_dump -Fc databázy synapse
#   synapse-data.tar.gz   /data Synapse: media_store + PODPISOVÝ KĽÚČ servera
#   signing.key           podpisový kľúč ešte raz samostatne (bez neho = nová identita servera)
#   letsencrypt.tar.gz    certifikáty (voliteľné, dajú sa vystaviť znova)
#   env                   server/.env (heslo DB, registration_shared_secret, macaroon/form secret,
#                         LiveKit API kľúč/secret, AS tokeny)
#   secrets/              admin token
# Archív obsahuje tajomstvá → chmod 600, ukladajte šifrovane mimo servera.
. "$(dirname "$0")/lib.sh"
load_env

DEST="${1:-backups}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
umask 077
mkdir -p "$DEST"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
B="$WORK/psst-backup-$TS"; mkdir -p "$B"

log "pg_dump"
compose exec -T postgres pg_dump -U synapse -Fc synapse > "$B/db.dump"
log "Synapse dáta (media_store, podpisový kľúč)"
compose exec -T synapse tar -C /data -czf - . > "$B/synapse-data.tar.gz"
compose exec -T synapse cat "/data/${MATRIX_DOMAIN}.signing.key" > "$B/signing.key"
log "certifikáty"
compose run --rm --no-deps -T --entrypoint tar certbot -C /etc/letsencrypt -czf - . > "$B/letsencrypt.tar.gz" 2>/dev/null || warn "certifikáty sa nezálohovali"
cp .env "$B/env"
[ -d secrets ] && cp -R secrets "$B/secrets"
cat > "$B/README.txt" <<TXT
PSST záloha $TS (server_name ${MATRIX_DOMAIN})
Obnova: server/scripts/restore.sh <tento archív>   — postup v server/README.md
TXT

tar -C "$WORK" -czf "$DEST/psst-backup-$TS.tar.gz" "psst-backup-$TS"
chmod 600 "$DEST/psst-backup-$TS.tar.gz"
[ -s "$B/db.dump" ] && [ -s "$B/signing.key" ] || die "záloha je neúplná!"
log "záloha: $DEST/psst-backup-$TS.tar.gz ($(du -h "$DEST/psst-backup-$TS.tar.gz" | cut -f1))"
echo "$DEST/psst-backup-$TS.tar.gz"
