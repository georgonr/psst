#!/usr/bin/env bash
# PSST audit cleanup (D64) — touches ONLY test data:
#   * deactivates every active account whose name starts with "qa-" (test accounts, never real users),
#   * deletes rooms created by "qa-*" accounts in which no non-test user is a member (purge, incl. directory entry),
#   * revokes unused registration tokens created on <date> whose usage count is 0.
#   scripts/audit/cleanup.sh [--dry-run] [YYYY-MM-DD]
#   PSST_QA_PREFIX=qa-io scripts/audit/cleanup.sh   only accounts/rooms of that prefix (other audits may be running)
set -euo pipefail
DRY=0; [ "${1:-}" = "--dry-run" ] && { DRY=1; shift; }
DAY="${1:-$(date -u +%F)}"
SSH="${PSST_SSH:-psst}"
PREFIX="${PSST_QA_PREFIX:-qa-}"
case "$PREFIX" in qa-*) ;; *) echo "PSST_QA_PREFIX must start with qa-" >&2; exit 2 ;; esac
[[ "$PREFIX" =~ ^[a-z0-9-]+$ ]] || { echo "bad PSST_QA_PREFIX" >&2; exit 2; }
run() { ssh "$SSH" "cd /opt/psst/server && $*"; }
psql_syn() { run "sudo docker compose exec -T postgres psql -U synapse -d synapse -Atc \"$1\""; }
psql_mas() { run "sudo docker compose exec -T postgres psql -U synapse -d mas -Atc \"$1\""; }

users=$(psql_syn "select substring(name from 2 for position(':' in name)-2) from users where name like '@$PREFIX%' and deactivated=0 order by 1")
rooms=$(psql_syn "select r.room_id from rooms r where r.creator like '@$PREFIX%' and not exists (select 1 from local_current_membership m where m.room_id=r.room_id and m.membership in ('join','invite') and m.user_id not like '@qa-%')")
tokens=""  # registration tokens are not per prefix: only the full cleanup revokes them
[ "$PREFIX" = qa- ] && tokens=$(psql_mas "select token from user_registration_tokens where created_at::date = '$DAY' and times_used = 0 and revoked_at is null")
echo "test accounts to deactivate: $(echo "$users" | grep -c . || true)"
echo "test rooms to delete:        $(echo "$rooms" | grep -c . || true)"
echo "unused tokens from $DAY:     $(echo "$tokens" | grep -c . || true)"
[ "$DRY" = 1 ] && { echo "(dry run)"; exit 0; }

for r in $rooms; do
  run "tok=\$(sudo cat secrets/admin_token); curl -s -o /dev/null -w '%{http_code} ' -X DELETE -H \"Authorization: Bearer \$tok\" -H 'Content-Type: application/json' -d '{\"purge\": true, \"block\": false}' 'http://127.0.0.1:8008/_synapse/admin/v2/rooms/$r'"
done; echo
for t in $tokens; do
  run "sudo docker compose exec -T postgres psql -U synapse -d mas -qc \"update user_registration_tokens set revoked_at = now() where token = '$t' and times_used = 0\"" >/dev/null
done
for u in $users; do
  run "sudo scripts/members.sh block $u --deactivate" 2>&1 | tail -1
done
echo "remaining active $PREFIX* accounts: $(psql_syn "select count(*) from users where name like '@$PREFIX%' and deactivated=0")"
