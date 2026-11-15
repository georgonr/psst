#!/usr/bin/env bash
# PSST: fresh test accounts for one run of the Windows desktop E2E (D60).
#
#   scripts/desktop/e2e-accounts.sh create     # 3 new accounts → GitHub secret PSST_E2E_ACCOUNTS + ~/psst-keys/e2e-accounts.json
#   scripts/desktop/e2e-accounts.sh cleanup    # deactivate the accounts from ~/psst-keys/e2e-accounts.json
#
# Fresh accounts per run: after a second sign-in Element requires confirming the identity (other device or recovery
# key) — correct for people, but it blocks repeated automated runs on the same account.
set -euo pipefail
STATE="${PSST_E2E_STATE:-$HOME/psst-keys/e2e-accounts.json}"
SSH="${PSST_SSH:-psst}"
case "${1:-}" in
  create)
    sfx="$(date +%m%d%H%M)"
    json="{"
    for role in desktop partner third; do
      user="qa-e2e-${role:0:1}$sfx"; pw="$(openssl rand -hex 12)"
      ssh "$SSH" "cd /opt/psst/server && sudo docker compose exec -T mas mas-cli manage register-user --yes $user --password '$pw' --display-name '$user' --ignore-password-complexity --config /config/config.yaml >/dev/null 2>&1" \
        || { echo "ERROR: could not create $user"; exit 1; }
      json+="\"$role\": {\"user\": \"$user\", \"password\": \"$pw\"},"
      echo "created $user ($role)"
    done
    json="${json%,}}"
    umask 077; printf '%s\n' "$json" > "$STATE"
    gh secret set PSST_E2E_ACCOUNTS < "$STATE"
    echo "secret PSST_E2E_ACCOUNTS updated"
    ;;
  cleanup)
    [ -f "$STATE" ] || { echo "nothing to clean"; exit 0; }
    for user in $(python3 -c "import json,sys; print(' '.join(v['user'] for v in json.load(open('$STATE')).values()))"); do
      ssh "$SSH" "cd /opt/psst/server && sudo scripts/members.sh block $user --deactivate" 2>&1 | tail -1
    done
    rm -f "$STATE"
    ;;
  *) echo "usage: $0 create|cleanup"; exit 2 ;;
esac
