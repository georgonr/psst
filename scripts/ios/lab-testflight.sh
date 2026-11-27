#!/usr/bin/env bash
# PSST (L1): psst lab (eu.macet.psst.lab) → TestFlight, internal group "psst". Branch lab/meshtastic only.
#
#   scripts/ios/lab-testflight.sh check            CI: package tests + iOS compile + unsigned simulator build (no Apple)
#   scripts/ios/lab-testflight.sh release          profile → secret → next build number → CI archive + upload →
#                                                  wait for processing → internal group "psst" + tester Geo M
#   options: --ref <psst-ios ref> (default lab/meshtastic)
#
# CI is triggered by committing lab/ios-lab-build.json on this branch (see .github/workflows/ios-lab.yml).
# Never touches the psst app (eu.macet.psst), its secrets or the 26.11.x release.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
KEYS="${PSST_KEYS_DIR:-$HOME/psst-keys}"
PY="${PSST_VENV:-$HOME/.local/psst-venv}/bin/python"
LAB="$ROOT/scripts/ios/lab_testflight.py"
REPO="${PSST_REPO:-georgonr/psst}"
KEY_ID=U4SWSW9CRM
MODE="${1:-}"; shift || true
REF=lab/meshtastic
while [ $# -gt 0 ]; do case "$1" in --ref) REF="$2"; shift ;; *) echo "unknown option $1"; exit 2 ;; esac; shift; done
[ "$MODE" = check ] || [ "$MODE" = release ] || { sed -n '2,11p' "$0"; exit 2; }
[ "$(git -C "$ROOT" branch --show-current)" = lab/meshtastic ] || { echo "run on branch lab/meshtastic"; exit 2; }
export ASC_KEY_ID="$KEY_ID" ASC_KEY_FILE="$KEYS/AuthKey_$KEY_ID.p8" PSST_KEYS_DIR="$KEYS"

# the workflow lives only on this branch, so `gh run list --workflow` (default branch) cannot find it
lastrun() { gh run list -R "$REPO" --branch lab/meshtastic --limit 20 --json databaseId,workflowName \
              --jq '[.[] | select(.workflowName == "iOS psst lab")][0].databaseId // 0'; }

trigger() { # mode build upload
  python3 - "$ROOT/lab/ios-lab-build.json" "$REF" "$1" "$2" "$3" <<'PY'
import json, sys
p, ref, mode, n, up = sys.argv[1:]
import datetime  # "requested" makes every request a change of the file → the push always starts the workflow
json.dump({"ref": ref, "mode": mode, "build_number": int(n), "upload": up == "true",
           "requested": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}, open(p, "w"), indent=1)
open(p, "a").write("\n")
PY
  git -C "$ROOT" add lab/ios-lab-build.json
  git -C "$ROOT" diff --cached --quiet || git -C "$ROOT" commit -q -m "lab: iOS psst lab $1${2:+ b$2} (ref $REF)"
  before="$(lastrun)"
  git -C "$ROOT" push -q origin lab/meshtastic
  for _ in $(seq 1 40); do
    sleep 6
    RUN="$(lastrun)"
    [ "$RUN" != "$before" ] && break
  done
  [ "$RUN" != "$before" ] || { echo "CI run did not start"; exit 1; }
  echo "CI: https://github.com/$REPO/actions/runs/$RUN"
  gh run watch "$RUN" -R "$REPO" --interval 120 --exit-status >/dev/null || {
    gh run view "$RUN" -R "$REPO" --log-failed | tail -80; echo "CI run $RUN failed"; exit 1; }
}

if [ "$MODE" = check ]; then
  trigger check 0 false
  echo "check OK"; exit 0
fi

"$PY" "$LAB" check
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
"$PY" "$LAB" profile "$TMP/profiles"
( cd "$TMP/profiles" && zip -q ../lab-profiles.zip ./*.mobileprovision )
base64 -i "$TMP/lab-profiles.zip" | gh secret set IOS_LAB_PROVISIONING_PROFILES_BASE64 -R "$REPO"
# list first, then grep (a piped `grep -q` closes early → SIGPIPE → pipefail failure, same as D86)
SECRETS="$(gh secret list -R "$REPO" --json name --jq '.[].name')"
for s in IOS_DIST_CERT_P12_BASE64 IOS_DIST_CERT_PASSWORD APPLE_TEAM_ID APP_STORE_CONNECT_API_KEY_ID; do
  grep -qx "$s" <<<"$SECRETS" || { echo "secret $s missing (scripts/ios/release-testflight.sh sets it)"; exit 1; }
done
N="$("$PY" "$LAB" next-build)"
echo "psst lab build number: $N"
trigger release "$N" true
"$PY" "$LAB" wait-build "$N"
"$PY" "$LAB" testers "$N"
printf '\nDONE: psst lab b%s is in TestFlight (internal group "psst").\n' "$N"
