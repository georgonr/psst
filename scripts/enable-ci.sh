#!/usr/bin/env bash
# Activates PSST CI. GitHub only accepts .github/workflows/* from a token with the
# `workflow` scope, so the workflows live in ci/workflows/ until you run this once.
#   gh auth refresh -h github.com -s workflow     # one-time, opens the browser
#   ./scripts/enable-ci.sh                        # copies, commits, pushes, starts all builds
set -euo pipefail
cd "$(dirname "$0")/.."
gh auth status 2>&1 | awk '/Active account: true/{a=1} a&&/Token scopes/{print; exit}' | grep -q workflow \
  || { echo "Missing 'workflow' scope: run  gh auth refresh -h github.com -s workflow"; exit 1; }
mkdir -p .github/workflows
cp ci/workflows/*.yml .github/workflows/
git add .github/workflows
git commit -m "ci: enable GitHub Actions workflows" || true
git push
sleep 5
for wf in ci/workflows/*.yml; do
  name=$(basename "$wf")
  grep -q workflow_dispatch "$wf" && [[ "$name" != ios-release.yml ]] && gh workflow run "$name" && echo "started $name"
done
echo "Follow: gh run list -R georgonr/psst"
