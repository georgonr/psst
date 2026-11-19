#!/usr/bin/env bash
# PSST (DECISIONS.md D84): release check for Android message search. Run by sign-release.sh BEFORE anything is
# signed or uploaded; a failure stops the release.
#
#   scripts/android/search-gate.sh <x86_64.apk>      (unsigned CI artifact or signed APK)
#
# What it proves, on the real release APK in an Android 14 emulator:
#   * a fresh test account signs in (clean install), a partner sends 8 Slovak messages into an ENCRYPTED room,
#   * global search finds them typed WITHOUT diacritics and by WORD BEGINNINGS, with exactly the expected number of
#     results (computed from the texts by scripts/android/search_check.py, never typed by hand),
#   * a message that arrives after the app was restarted is found too (the "just received" case),
#   * nothing is found for a word that is not there.
# The test accounts (qa-sg*) and their room are deleted at the end, also on failure.
#
# Needs: the psst test venv (~/.local/psst-venv, matrix-nio with E2EE), ssh access "psst" (accounts are created and
# deactivated with mas-cli / members.sh on the server), Android SDK with the AVD $PSST_GATE_AVD (default psst34,
# Android 14 Google APIs x86_64). An already running emulator is used if one is attached.
# The APK is installed signed with a throwaway key made for this run (the release key is not used here); the psst
# app on the test emulator is uninstalled first.
set -euo pipefail

APK="${1:?usage: search-gate.sh <x86_64.apk>}"
HERE="$(cd "$(dirname "$0")" && pwd)"
SDK="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
export PATH="$SDK/platform-tools:$SDK/emulator:$PATH"
PY="${PSST_VENV:-$HOME/.local/psst-venv}/bin/python"
AVD="${PSST_GATE_AVD:-psst34}"
PKG=eu.macet.psst
ACT=io.element.android.x.MainActivity
BT="${PSST_TOOLS_DIR:-$HOME/.psst-tools}/build-tools-37.0.0"
JAVA_HOME="${JAVA_HOME:-/usr/local/opt/openjdk@17}"; export JAVA_HOME PATH="$JAVA_HOME/bin:$PATH"
WORK="$(mktemp -d -t psst-search-gate)"
LOG="$WORK/gate.log"
STARTED_EMU=0

say() { echo "search-gate: $*" | tee -a "$LOG"; }
fail() { say "FAIL: $*"; exit 1; }
ui() { python3 "$HERE/ui.py" "$@"; }
texts() { ui texts 2>/dev/null || true; }

cleanup() {
  local rc=$?
  "$PY" -I "$HERE/search_check.py" teardown "$WORK" >>"$LOG" 2>&1 || say "teardown failed (see $LOG)"
  adb shell am force-stop "$PKG" >/dev/null 2>&1 || true
  [ "$STARTED_EMU" = 1 ] && adb emu kill >/dev/null 2>&1 || true
  if [ $rc -eq 0 ]; then rm -rf "$WORK"; else echo "search-gate: logs and screenshots kept in $WORK"; fi
}
trap cleanup EXIT

[ -f "$APK" ] || fail "no APK $APK"
[ -x "$PY" ] || fail "test venv $PY missing (python3 -m venv ~/.local/psst-venv && pip install 'matrix-nio[e2e]' requests certifi)"

# ---------- emulator ----------
if ! adb get-state >/dev/null 2>&1; then
  say "starting emulator $AVD"
  nohup emulator -avd "$AVD" -no-window -no-snapshot-save -no-audio -no-boot-anim -gpu swiftshader_indirect \
    >"$WORK/emulator.log" 2>&1 &
  STARTED_EMU=1
  adb wait-for-device
fi
for _ in $(seq 120); do [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = 1 ] && break; sleep 2; done
adb shell input keyevent KEYCODE_WAKEUP >/dev/null; adb shell wm dismiss-keyguard >/dev/null 2>&1 || true

# ---------- install (throwaway signature) ----------
keytool -genkeypair -keystore "$WORK/gate.jks" -storepass psstgate -keypass psstgate -alias gate -keyalg RSA \
  -keysize 2048 -validity 2 -dname CN=psst-search-gate >/dev/null 2>&1
"$BT/zipalign" -P 16 -f 4 "$APK" "$WORK/aligned.apk"
"$BT/apksigner" sign --ks "$WORK/gate.jks" --ks-pass pass:psstgate --out "$WORK/gate.apk" "$WORK/aligned.apk"
rm -f "$WORK/gate.apk.idsig" "$WORK/aligned.apk"   # no .idsig: a plain (not incremental) install
VERSION="$("$BT/aapt2" dump badging "$APK" | sed -n "s/.*versionName='\([^']*\)'.*/\1/p")"
say "APK $VERSION"
adb uninstall "$PKG" >/dev/null 2>&1 || true
adb install "$WORK/gate.apk" >"$WORK/install.log" 2>&1 || true
grep -q Success "$WORK/install.log" || fail "install failed: $(tail -2 "$WORK/install.log" | tr '\n' ' ')"
adb shell pm grant "$PKG" android.permission.POST_NOTIFICATIONS >/dev/null 2>&1 || true

# ---------- accounts + encrypted room ----------
"$PY" -I "$HERE/search_check.py" setup "$WORK" >>"$LOG" 2>&1 || fail "setup of the test accounts failed"
USER_A="$("$PY" -I -c "import json,sys;print(json.load(open(sys.argv[1]))['a'][0])" "$WORK/accounts.json")"
PASS_A="$("$PY" -I -c "import json,sys;print(json.load(open(sys.argv[1]))['a'][1])" "$WORK/accounts.json")"

# ---------- sign in (MAS in a Chrome custom tab) ----------
adb shell am start -n "$PKG/$ACT" >/dev/null
signed_in=0
for _ in $(seq 100); do
  t="$(texts)"
  case "$t" in
    *"'Chats'"*"'Search'"*|*"'Konverzácie'"*) signed_in=1; break ;;
    *"isn't responding"*|*"nereaguje"*) ui tap Wait >/dev/null 2>&1 || ui tap Čakať >/dev/null 2>&1 ;;
    *"run in background"*|*"na pozadí"*) ui tap Allow >/dev/null 2>&1 || ui tap Povoliť >/dev/null 2>&1 ;;
    *"Notifications &amp; calls"*|*"Upozornenia a hovory"*) adb shell input keyevent KEYCODE_BACK ;;
    *"New psst version"*|*"Nová verzia"*) ui tap LATER >/dev/null 2>&1 || ui tap NESKÔR >/dev/null 2>&1 ;;
    *"Sign in to psst.pro"*) ui tap "Sign in to psst.pro" >/dev/null ;;
    *"Use another account"*) if echo "$t" | grep -q "'$USER_A'"; then ui tap Continue >/dev/null; else ui tap "Use another account" >/dev/null; fi ;;
    *"Account deleted"*) ui tap "Sign in" >/dev/null ;;
    *"'Username'"*"'Password'"*)
      ui tapfield 0 >/dev/null; adb shell input keyevent KEYCODE_MOVE_END; adb shell input keyevent $(printf 'KEYCODE_DEL %.0s' $(seq 1 40)); ui type "$USER_A"
      ui tapfield 1 >/dev/null; ui type "$PASS_A"; adb shell input keyevent KEYCODE_ENTER ;;
    *"Continue to psst"*) ui tap Continue >/dev/null ;;
    *"Back up your chats"*|*"Zálohujte"*) ui tap Close >/dev/null 2>&1 || ui tap Zavrieť >/dev/null 2>&1 ;;
    # the throwaway signature gets no FCM token (Firebase is bound to the release certificate): push is not needed here
    *"Unable to register pusher"*|*"Firebase token"*) ui tap "Do not show this again" >/dev/null 2>&1; ui tap OK >/dev/null 2>&1 ;;
    # Chrome keeps the MAS session of the previous run's (deleted) test account; its page is not always in the
    # accessibility tree: tap its "Sign in" button where MAS puts it
    *"matrix-authentication-service"*)
      mas_idle=$((${mas_idle:-0} + 1)); [ "$mas_idle" -ge 3 ] && { ui tap "Sign in" >/dev/null 2>&1 || adb shell input tap 540 1030; mas_idle=0; } ;;
  esac
  sleep 3
done
ui shot "$WORK/signed-in.png"
[ "$signed_in" = 1 ] || fail "could not sign in the test account (screen: $(texts | head -c 300))"
for b in Close Zavrieť OK; do ui tap "$b" >/dev/null 2>&1 || true; done

# ---------- corpus ----------
"$PY" -I "$HERE/search_check.py" seed "$WORK" >>"$LOG" 2>&1 || fail "sending the corpus failed"
EXPECTED="$(cat "$WORK/expected.json")"
say "expected (from the corpus): $EXPECTED"
sleep 10

check() { # check <query> <expected count>
  local got
  got="$(python3 "$HERE/search_ui.py" "$1" 45 | tail -1)"
  echo "$got" >>"$LOG"
  local n; n="$(echo "$got" | python3 -c 'import json,sys;print(json.load(sys.stdin)["count"])')"
  if [ "$n" = "$2" ]; then say "OK   \"$1\": $n/$2"; else ui shot "$WORK/fail-$(echo "$1" | tr ' ' _).png"; say "FAIL \"$1\": $n, expected $2"; BAD=1; fi
}
BAD=0
for q in $(echo "$EXPECTED" | python3 -c 'import json,sys;print(" ".join(k.replace(" ","+") for k in json.load(sys.stdin)))'); do
  q="${q//+/ }"
  check "$q" "$(echo "$EXPECTED" | python3 -c 'import json,sys;print(json.load(sys.stdin)[sys.argv[1]])' "$q")"
done
check "nenajdes" 0

# ---------- restart, then a message that arrives after it ----------
adb shell am force-stop "$PKG"; adb shell am start -n "$PKG/$ACT" >/dev/null; sleep 12
for b in Close Zavrieť LATER NESKÔR OK; do ui tap "$b" >/dev/null 2>&1 || true; done
"$PY" -I "$HERE/search_check.py" send "$WORK" "Po reštarte prišlo ďalšie číslo (sg99)" >>"$LOG" 2>&1 || fail "sending after restart failed"
sleep 10
check "restarte" 1
check "cislo" "$(( $(echo "$EXPECTED" | python3 -c 'import json,sys;print(json.load(sys.stdin)["cislo"])') + 1 ))"

[ "$BAD" = 0 ] || fail "message search does not return the expected results — not releasing ($VERSION)"
say "PASS: message search in an encrypted room (no diacritics, word beginnings, after restart) — $VERSION"
