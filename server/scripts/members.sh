#!/usr/bin/env bash
# Správa členov PSST (účty spravuje Matrix Authentication Service).
#
#   scripts/members.sh invite [počet_použití=1] [platnosť_dní=7]   nový pozývací token
#   scripts/members.sh list                                         zoznam členov
#   scripts/members.sh block <meno> [--deactivate]                  zablokovať (odhlási všetky relácie)
#   scripts/members.sh unblock <meno>                               odblokovať
#   scripts/members.sh admin <meno>                                 vytvoriť admin účet (vypíše heslo)
#   scripts/members.sh password <meno>                              nastaviť nové náhodné heslo
#
# Nový člen: v appke psst (Android/iOS/web/desktop) → „Create account" → zadá pozývací token.
. "$(dirname "$0")/lib.sh"
load_env

mas() { compose exec -T mas mas-cli manage "$@" --config /config/config.yaml; }
need_user() { [ -n "${1:-}" ] || die "chýba meno používateľa"; [[ "$1" =~ ^[a-z0-9._=/-]+$ ]] || die "neplatné meno: $1"; }
gen_password() { openssl rand -base64 18 | tr -d '/+=' | cut -c1-20; }

ensure_admin_token() {
  # Synapse admin API (zoznam členov) potrebuje token s admin právami vydaný cez MAS
  if [ -s secrets/admin_token ]; then
    local code
    code="$(synapse_curl -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $(cat secrets/admin_token)" \
      "http://localhost:8008/_synapse/admin/v1/server_version" || true)"
    [ "$code" = 200 ] && return 0
  fi
  local adm="${PSST_ADMIN_USER:-psstadmin}"
  local out
  if ! out="$(mas register-user --yes "$adm" --password "$(gen_password)$(gen_password)" --admin \
                --ignore-password-complexity 2>&1)"; then
    printf '%s' "$out" | grep -q "already exists" || die "servisný admin: $out"
  else
    log "vytvorený servisný admin účet '$adm' (len pre správu, nie na chat)"
  fi
  mas issue-compatibility-token "$adm" "PSSTADMIN$(openssl rand -hex 4 | tr a-f A-F)" \
    --yes-i-want-to-grant-synapse-admin-privileges 2>&1 | grep -oE 'mct_[A-Za-z0-9_]+' | tail -1 > secrets/admin_token.new || true
  [ -s secrets/admin_token.new ] || die "nepodarilo sa vydať admin token"
  umask 077; mv secrets/admin_token.new secrets/admin_token
}

LIST_PY='
import json, sys, datetime
users = [u for u in json.load(sys.stdin).get("users", [])
         if u.get("user_type") != "bot" and not u["name"].startswith("@psstadmin:")]
fmt = "{:40} {:24} {:5} {:12} {}"
print(fmt.format("POUŽÍVATEĽ", "MENO", "ADMIN", "STAV", "VYTVORENÝ"))
for u in users:
    st = "deaktivovaný" if u.get("deactivated") else ("zablokovaný" if u.get("locked") else "aktívny")
    ts = u.get("creation_ts", 0)
    ts = datetime.datetime.fromtimestamp(ts / 1000 if ts > 1e11 else ts).strftime("%Y-%m-%d")
    print(fmt.format(u["name"], (u.get("displayname") or "")[:24], "áno" if u.get("admin") else "", st, ts))
print("spolu:", len(users))
'

# príznak "locked" v Synapse (MAS ho pri odblokovaní nezruší)
synapse_lock() {
  ensure_admin_token
  synapse_curl -o /dev/null -X PUT -H "Authorization: Bearer $(cat secrets/admin_token)" \
    -H 'Content-Type: application/json' -d "{\"locked\": $2}" \
    "http://localhost:8008/_synapse/admin/v2/users/@$1:${MATRIX_DOMAIN}" || warn "Synapse lock=$2 zlyhal"
}

cmd="${1:-}"; shift || true
case "$cmd" in
  invite)
    uses="${1:-1}"; days="${2:-7}"
    [[ "$uses" =~ ^[0-9]+$ && "$days" =~ ^[0-9]+$ ]] || die "použitie: members.sh invite [počet_použití] [platnosť_dní]"
    args=(issue-user-registration-token)
    if [ "$uses" = 0 ]; then args+=(--unlimited); else args+=(--usage-limit "$uses"); fi
    [ "$days" != 0 ] && args+=(--expires-in "$((days * 86400))")
    out="$(mas "${args[@]}" 2>&1)" || die "$out"
    token="$(printf '%s\n' "$out" | sed -n 's/.*registration token: \([^ ]*\).*/\1/p' | tail -1)"
    [ -n "$token" ] || die "token sa nepodarilo vytvoriť: $out"
    log "pozývací token (použití: ${uses/#0/neobmedzene}, platnosť: ${days/#0/bez expirácie} dní):"
    echo "$token"
    log "pošlite novému členovi: nainštaluj psst → Create account → zadaj tento token (web: https://${APP_DOMAIN})"
    ;;
  list)
    ensure_admin_token
    synapse_curl -H "Authorization: Bearer $(cat secrets/admin_token)" \
      "http://localhost:8008/_synapse/admin/v2/users?limit=1000&guests=false&deactivated=true&locked=true&order_by=creation_ts" \
    | python3 -c "$LIST_PY"
    ;;
  block)
    need_user "${1:-}"; user="$1"; extra=()
    [ "${2:-}" = "--deactivate" ] && extra=(--deactivate)
    mas lock-user "$user" ${extra[@]+"${extra[@]}"} >/dev/null
    mas kill-sessions "$user" >/dev/null 2>&1 || true
    synapse_lock "$user" true
    log "účet $user zablokovaný${extra[0]+ a deaktivovaný}; všetky relácie ukončené"
    ;;
  unblock)
    need_user "${1:-}"
    mas unlock-user "$1" --reactivate >/dev/null 2>&1 || mas unlock-user "$1" >/dev/null
    synapse_lock "$1" false
    log "účet $1 odblokovaný"
    ;;
  admin)
    need_user "${1:-}"; pw="$(gen_password)"
    mas register-user --yes "$1" --password "$pw" --admin --ignore-password-complexity >/dev/null
    log "admin účet @$1:${MATRIX_DOMAIN} vytvorený. Heslo (zmeňte si ho po prihlásení na https://${AUTH_DOMAIN}/account):"
    echo "$pw"
    ;;
  password)
    need_user "${1:-}"; pw="$(gen_password)"
    mas set-password "$1" "$pw" --ignore-complexity >/dev/null
    log "nové heslo pre $1:"; echo "$pw"
    ;;
  *) sed -n '2,11p' "$0"; exit 1 ;;
esac
