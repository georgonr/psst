#!/usr/bin/env bash
# Skúšobná obnova zálohy NAOSTRO do dočasného prostredia vedľa bežiaceho servera (D85). Nič na bežiacom stacku nemení.
#
#   sudo scripts/restore-test.sh [archív.tar.gz.enc]      (bez argumentu: najnovšia denná záloha)
#
# Archív dešifruje a rozbalí do /opt/psst/restore-test-<čas>/, spustí tam vlastný PostgreSQL a Synapse (compose projekt
# psst-restoretest, vlastná interná sieť, žiadne publikované porty), obnoví do nich obe databázy, médiá, podpisový kľúč
# a vyrenderovanú konfiguráciu zo zálohy a overí:
#   - podpisový kľúč v obnovenom Synapse = kľúč v zálohe = kľúč bežiaceho servera,
#   - počty účtov (Synapse users, MAS users) a udalostí sedia s bežiacim serverom (ak sa medzitým nezmenili),
#   - obnovený Synapse naštartuje s konfiguráciou zo zálohy a odpovedá na /health a /_matrix/client/versions.
# Na konci dočasné prostredie zmaže (kontajnery, sieť, adresár), aj pri chybe.
. "$(dirname "$0")/lib.sh"
load_env
PASS_FILE="${PSST_BACKUP_PASS_FILE:-secrets/backup.pass}"
ARCHIVE="${1:-$(ls -1t backups/daily/psst-*.tar.gz.enc 2>/dev/null | head -1)}"
[ -f "$ARCHIVE" ] || die "žiadny archív (scripts/backup.sh)"
[ -s "$PASS_FILE" ] || die "chýba $PASS_FILE"
SV="$(sed -n 's/.*SYNAPSE_VERSION: *//p' compose.yml | head -1)"
T="/opt/psst/restore-test-$(date -u +%Y%m%dT%H%M%SZ)"
P=psst-restoretest
dc() { docker compose -p "$P" -f "$T/compose.yml" "$@"; }
cleanup() { dc down -v --remove-orphans >/dev/null 2>&1 || true; rm -rf "$T"; }
trap cleanup EXIT
umask 077; mkdir -p "$T"
log "dešifrujem $(basename "$ARCHIVE")"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 -pass "file:$PASS_FILE" -in "$ARCHIVE" | tar -C "$T" -xzf - || die "dešifrovanie/rozbalenie zlyhalo"
B="$(find "$T" -maxdepth 1 -type d -name 'psst-backup-*' | head -1)"
for f in synapse.dump mas.dump signing.key synapse-data.tar.gz config.tar.gz env; do [ -s "$B/$f" ] || die "v zálohe chýba $f"; done
mkdir -p "$T/config" "$T/synapse" "$T/pg"
tar -C "$T/config" -xzf "$B/config.tar.gz"
PGPW="$(sed -n 's/^POSTGRES_PASSWORD=//p' "$B/env")"
SN="$(sed -n 's/^SERVER_NAME=//p' "$B/env")"; SN="${SN:-$(sed -n 's/^MATRIX_DOMAIN=//p' "$B/env")}"
cat > "$T/compose.yml" <<YAML
services:
  postgres:
    image: docker.io/library/postgres:18.7-alpine
    environment: {POSTGRES_USER: synapse, POSTGRES_DB: synapse, POSTGRES_PASSWORD: "$PGPW", POSTGRES_INITDB_ARGS: "--encoding=UTF8 --lc-collate=C --lc-ctype=C"}
    volumes: ["$T/pg:/var/lib/postgresql"]
    healthcheck: {test: ["CMD-SHELL", "pg_isready -U synapse -d synapse"], interval: 3s, retries: 40}
    networks: [rt]
  synapse:
    image: psst-synapse:$SV
    command: ["run", "--config-path", "/config/homeserver.yaml"]
    volumes: ["$T/config/config/synapse:/config:ro", "$T/synapse:/data"]
    depends_on: {postgres: {condition: service_healthy}}
    networks: [rt]
networks:
  rt:
    internal: true
YAML
chmod 755 "$T"; chmod -R a+rX "$T/config"
log "dočasný PostgreSQL ($P)"
dc run --rm --no-deps -T --entrypoint sh postgres -c 'chown -R postgres:postgres /var/lib/postgresql' >/dev/null 2>&1
dc up -d postgres >/dev/null 2>&1
pg=0; for _ in $(seq 60); do dc exec -T postgres pg_isready -U synapse -d synapse >/dev/null 2>&1 && { pg=1; break; }; sleep 2; done
[ "$pg" = 1 ] || { dc logs --tail 30 postgres; die "dočasný PostgreSQL nenaštartoval"; }
dc exec -T postgres psql -U synapse -d synapse -qc "CREATE DATABASE mas ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C' TEMPLATE template0" >/dev/null
dc exec -T postgres psql -U synapse -d synapse -qc "DO \$\$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'psst_admin_ro') THEN CREATE ROLE psst_admin_ro LOGIN; END IF; END \$\$" >/dev/null
log "obnovujem databázy"
dc exec -T postgres pg_restore -U synapse -d synapse --no-owner --clean --if-exists < "$B/synapse.dump" 2>/dev/null || true
dc exec -T postgres pg_restore -U synapse -d mas --no-owner < "$B/mas.dump" 2>/dev/null || true
log "obnovujem médiá a podpisový kľúč"
dc run --rm --no-deps -T --entrypoint sh synapse -c 'tar -C /data -xzf - && chown -R 991:991 /data' < "$B/synapse-data.tar.gz" >/dev/null
cmp -s "$B/signing.key" "$T/synapse/${SN}.signing.key" && log "podpisový kľúč obnovený = záloha" || die "podpisový kľúč v obnovených dátach sa nezhoduje so zálohou"
LIVE_KEY="$(compose exec -T synapse cat "/data/${SN}.signing.key" 2>/dev/null || true)"
[ "$LIVE_KEY" = "$(cat "$B/signing.key")" ] && log "podpisový kľúč = bežiaci server" || warn "podpisový kľúč sa líši od bežiaceho servera (iná záloha?)"
q() { dc exec -T postgres psql -U synapse -d "$1" -tAc "$2"; }
lq() { compose exec -T postgres psql -U synapse -d "$1" -tAc "$2"; }
FAIL=0
for c in "synapse|SELECT count(*) FROM users|účty Synapse" "synapse|SELECT count(*) FROM events|udalosti" "synapse|SELECT count(*) FROM rooms|miestnosti" "mas|SELECT count(*) FROM users|účty MAS" "mas|SELECT count(*) FROM user_registration_tokens|pozvánky"; do
  IFS='|' read -r db sql label <<<"$c"
  got="$(q "$db" "$sql")"; live="$(lq "$db" "$sql")"
  if [ "$got" = "$live" ]; then log "  $label: $got (= bežiaci server)"; else warn "  $label: obnovené $got, bežiaci server $live (zmena po zálohe?)"; [ "$got" -gt 0 ] || FAIL=1; fi
done
log "štartujem obnovený Synapse"
dc up -d synapse >/dev/null 2>&1
ok=0; for _ in $(seq 90); do dc exec -T synapse curl -fsS http://localhost:8008/health >/dev/null 2>&1 && { ok=1; break; }; sleep 2; done
[ "$ok" = 1 ] || { dc logs --tail 40 synapse; die "obnovený Synapse nenaštartoval"; }
dc exec -T synapse curl -fsS http://localhost:8008/_matrix/client/versions | grep -q '"versions"' && log "obnovený Synapse odpovedá (server_name $SN)" || FAIL=1
[ "$FAIL" = 0 ] || die "skúšobná obnova: niektorá kontrola zlyhala"
log "SKÚŠOBNÁ OBNOVA OK: $(basename "$ARCHIVE") → dočasné prostredie $P (zmazané)"
