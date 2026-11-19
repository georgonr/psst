#!/usr/bin/env bash
# PSST audit helper: fill the MAS sign-in form shown in the Chrome custom tab on the emulator, then consent.
#   scripts/android/mas-login.sh <user> <password>
# Expects the MAS "Sign in" page to be on screen (tap "Sign in to psst.pro" first).
set -euo pipefail
export PATH="$HOME/Library/Android/sdk/platform-tools:$PATH"
UI="python3 $(cd "$(dirname "$0")" && pwd)/ui.py"
$UI wait "Username" 60 >/dev/null
clear() { adb shell input keyevent KEYCODE_MOVE_END; adb shell input keyevent $(printf 'KEYCODE_DEL %.0s' $(seq 1 40)); }
$UI tapfield 0 >/dev/null; clear; $UI type "$1"
$UI tapfield 1 >/dev/null; clear; $UI type "$2"
$UI tap "Continue" >/dev/null
for _ in $(seq 1 20); do
  t="$($UI texts)"
  case "$t" in
    *"'Continue'"*|*"Allow access"*|*"Grant access"*) $UI tap "Continue" >/dev/null 2>&1 || $UI tap "Allow" >/dev/null 2>&1 || $UI tap "Grant" >/dev/null 2>&1 || true ;;
    *"matrix-authentication-service"*) ;;
    *) echo "left MAS: $t"; exit 0 ;;
  esac
  sleep 3
done
echo "still on MAS"; exit 1
