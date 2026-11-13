#!/usr/bin/env bash
# Šifrovaná záloha PSST servera (za chodu, bez odstávky) s rotáciou. Cron ju spúšťa denne (deploy.sh).
#
#   scripts/backup.sh [adresár=backups]
#
# Obsah (AES-256, kľúč z heslovej frázy secrets/backup.pass, PBKDF2 600k iterácií):
#   synapse.dump / mas.dump   pg_dump -Fc oboch databáz (správy, miestnosti, účty, relácie)
#   synapse-data.tar.gz       médiá (media_store) + PODPISOVÝ KĽÚČ Synapse
#   signing.key               podpisový kľúč ešte raz samostatne
#   ntfy.tar.gz               ntfy databázy (UnifiedPush registrácie)
#   config.tar.gz             data/config (vyrenderované konfigurácie), letsencrypt.tar.gz (certifikáty)
#   env, secrets/             .env a tajomstvá (MAS kľúče, APNs kľúč, admin token) — BEZ backup.pass
# Rotácia: 7 denných, 4 týždenné (nedeľa), 6 mesačných (1. deň). Kontrolný súčet .sha256 vedľa archívu.
# Kópia mimo servera: nastavte v .env BACKUP_RSYNC_TARGET=user@host:/cesta (rsync cez SSH kľúč).
. "$(dirname "$0")/lib.sh"
load_env
DEST="${1:-backups}"
PASS_FILE="${PSST_BACKUP_PASS_FILE:-secrets/backup.pass}"
[ -s "$PASS_FILE" ] || die "chýba $PASS_FILE (vytvorí ho deploy.sh)"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
umask 077
mkdir -p "$DEST/daily" "$DEST/weekly" "$DEST/monthly"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
B="$WORK/psst-backup-$TS"; mkdir -p "$B"

log "pg_dump synapse + mas"
compose exec -T postgres pg_dump -U synapse -Fc synapse > "$B/synapse.dump"
compose exec -T postgres pg_dump -U synapse -Fc mas > "$B/mas.dump"
log "Synapse dáta (médiá, podpisový kľúč)"
compose exec -T synapse tar -C /data -czf - . > "$B/synapse-data.tar.gz"
compose exec -T synapse cat "/data/${MATRIX_DOMAIN}.signing.key" > "$B/signing.key"
log "ntfy, konfigurácie, certifikáty, tajomstvá"
tar -C data -czf "$B/ntfy.tar.gz" ntfy 2>/dev/null || warn "ntfy dáta sa nezálohovali"
tar -C data -czf "$B/config.tar.gz" config
tar -C data/certbot -czf "$B/letsencrypt.tar.gz" conf 2>/dev/null || warn "certifikáty sa nezálohovali"
cp .env "$B/env"
mkdir -p "$B/secrets"; (cd secrets && tar --exclude=./backup.pass -cf - .) | tar -C "$B/secrets" -xf -
cat > "$B/README.txt" <<TXT
PSST záloha $TS (server_name ${MATRIX_DOMAIN})
Obnova: server/scripts/restore.sh <archív.tar.gz.enc>   (heslová fráza: secrets/backup.pass)
TXT
for f in synapse.dump mas.dump signing.key; do [ -s "$B/$f" ] || die "záloha je neúplná ($f)"; done

OUT="$DEST/daily/psst-$TS.tar.gz.enc"
tar -C "$WORK" -czf - "psst-backup-$TS" \
  | openssl enc -aes-256-cbc -salt -pbkdf2 -iter 600000 -pass "file:$PASS_FILE" -out "$OUT"
(cd "$(dirname "$OUT")" && shasum -a 256 "$(basename "$OUT")" 2>/dev/null || sha256sum "$(basename "$OUT")") > "$OUT.sha256"
# overenie: dá sa dešifrovať a obsahuje podpisový kľúč
openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 -pass "file:$PASS_FILE" -in "$OUT" | tar -tzf - | grep -q 'signing.key' \
  || die "overenie zálohy zlyhalo"

# rotácia
[ "$(date -u +%u)" = 7 ] && cp "$OUT" "$OUT.sha256" "$DEST/weekly/"
[ "$(date -u +%d)" = 01 ] && cp "$OUT" "$OUT.sha256" "$DEST/monthly/"
prune() { ls -1t "$1"/psst-*.tar.gz.enc 2>/dev/null | tail -n +$(($2 + 1)) | while read -r f; do rm -f "$f" "$f.sha256"; done; }
prune "$DEST/daily" 7; prune "$DEST/weekly" 4; prune "$DEST/monthly" 6

if [ -n "${BACKUP_RSYNC_TARGET:-}" ]; then
  log "kopírujem zálohy na $BACKUP_RSYNC_TARGET"
  rsync -a --delete "$DEST/" "$BACKUP_RSYNC_TARGET/" || warn "rsync zlyhal"
fi
date -u +%FT%TZ > "$DEST/.last-success"
log "záloha: $OUT ($(du -h "$OUT" | cut -f1))"
echo "$OUT"
