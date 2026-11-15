#!/usr/bin/env bash
# PSST: emulator smoke test for the psst Android app (runs inside reactivecircus/android-emulator-runner).
#
#   scripts/android/emulator-test.sh <signed-x86_64.apk> <output-dir>
#
# Verifies that
#  (a) the APK installs, its label is "psst" and it starts,
#  (b) onboarding offers "Sign in to chat.macet.eu" and there is no way to pick / type another homeserver
#      (no "Sign in manually", "Change account provider", "Other", server input field, matrix.org, ...),
#      also after tapping through sign-in, the QR-code sign-in and an injected mobile.element.io login link,
#  (c) the app does not claim element.io links.
# Screenshots (*.png), UI dumps (*.xml) and a summary (result.txt) are written to <output-dir>.
set -uo pipefail

APK="$1"
OUT="$2"
PKG="eu.macet.psst"
ACTIVITY="io.element.android.x.MainActivity"
HOMESERVER="chat.macet.eu"
SIGN_IN_TEXT="Sign in to ${HOMESERVER}"
HERE="$(cd "$(dirname "$0")" && pwd)"
CHECK="python3 ${HERE}/check_ui.py"

mkdir -p "$OUT"
RESULT="$OUT/result.txt"
: > "$RESULT"
FAILED=0

log() { echo "$*" | tee -a "$RESULT"; }
fail() { log "FAIL: $*"; FAILED=1; }
pass() { log "PASS: $*"; }

dump_ui() { # dump_ui <name>: UI dump only
  local name="$1"
  adb shell uiautomator dump "/sdcard/${name}.xml" >/dev/null 2>&1 || adb shell uiautomator dump "/sdcard/${name}.xml" >/dev/null 2>&1
  adb pull "/sdcard/${name}.xml" "$OUT/${name}.xml" >/dev/null 2>&1 || echo '<hierarchy/>' > "$OUT/${name}.xml"
}

dismiss_anr() { # slow CI emulators show "<system app> isn't responding" over our app → tap "Wait";
  # psst's own first-start prompts (D57: full-screen calls, battery) → "Later"
  local i xy t
  for i in 1 2 3 4; do
    dump_ui _anr
    t="$($CHECK texts "$OUT/_anr.xml")"
    if printf '%s' "$t" | grep -q "isn't responding"; then
      log "INFO: dismissing system ANR dialog"; xy="$($CHECK tap "$OUT/_anr.xml" "Wait")" || return 0
    elif printf '%s' "$t" | grep -qE "^(Full-screen calls|Reliable calls and messages)$"; then
      log "INFO: psst prompt: $(printf '%s' "$t" | grep -E "^(Full-screen calls|Reliable calls and messages)$") → Later"
      xy="$($CHECK tap "$OUT/_anr.xml" "Later" || $CHECK tap "$OUT/_anr.xml" "LATER")" || return 0
    else
      return 0
    fi
    # shellcheck disable=SC2086
    adb shell input tap $xy; sleep 2
  done
}

snap() { # snap <name>: UI dump + screenshot
  local name="$1"
  dismiss_anr
  adb shell uiautomator dump "/sdcard/${name}.xml" >/dev/null 2>&1 || adb shell uiautomator dump "/sdcard/${name}.xml" >/dev/null 2>&1
  adb pull "/sdcard/${name}.xml" "$OUT/${name}.xml" >/dev/null 2>&1 || echo '<hierarchy/>' > "$OUT/${name}.xml"
  adb exec-out screencap -p > "$OUT/${name}.png"
}

check() { # check <name>: lock rules on the last dump of <name>
  local name="$1" out
  out="$($CHECK check "$OUT/${name}.xml" "$name")"
  local rc=$?
  [ -n "$out" ] && echo "$out" | tee -a "$RESULT"
  if [ $rc -ne 0 ]; then fail "$name: homeserver lock violated"; else pass "$name: no server selection UI"; fi
  { echo "--- texts on $name ---"; $CHECK texts "$OUT/${name}.xml"; } >> "$OUT/texts.txt"
}

wait_for_text() { # wait_for_text <name> <text> <timeout-s>
  local name="$1" text="$2" timeout="$3" t=0
  while [ $t -lt "$timeout" ]; do
    snap "$name"
    if $CHECK has "$OUT/${name}.xml" "$text"; then return 0; fi
    sleep 3; t=$((t + 3))
  done
  return 1
}

tap_text() { # tap_text <name> <text>
  local xy
  xy="$($CHECK tap "$OUT/${1}.xml" "$2")" || return 1
  # shellcheck disable=SC2086
  adb shell input tap $xy
}

back_to_onboarding() {
  for _ in 1 2 3 4; do
    snap _probe
    $CHECK has "$OUT/_probe.xml" "$SIGN_IN_TEXT" && return 0
    adb shell input keyevent KEYCODE_BACK
    sleep 2
  done
  adb shell am start -W -n "$PKG/$ACTIVITY" >/dev/null
  wait_for_text _probe "$SIGN_IN_TEXT" 30
}

adb wait-for-device
adb shell getprop ro.build.version.release | sed 's/^/Android /' | tee -a "$RESULT"

# ---------- (a) install + label + start ----------
BT="$(ls -d "$ANDROID_HOME"/build-tools/*/ | sort -V | tail -1)"
"$BT/aapt2" dump badging "$APK" > "$OUT/badging.txt" 2>&1
grep -E "^package:|application-label:|launchable-activity" "$OUT/badging.txt" | tee -a "$RESULT"
grep -q "^package: name='${PKG}'" "$OUT/badging.txt" && pass "package name is ${PKG}" || fail "package name is not ${PKG}"
grep -q "^application-label:'psst'" "$OUT/badging.txt" && pass "app label is psst" || fail "app label is not psst"

if adb install -r -g "$APK" 2>&1 | tee -a "$RESULT" | grep -q Success; then
  pass "APK installed"
else
  fail "APK install failed"; exit 1
fi
adb shell pm list packages | grep -q "package:${PKG}$" && pass "package present" || fail "package not present"

# (c) element.io links must not resolve to psst any more; app.macet.eu should
for url in "https://mobile.element.io/element/?account_provider=matrix.org" "https://app.element.io/#/room/#a:matrix.org"; do
  if adb shell cmd package query-activities --brief -a android.intent.action.VIEW -c android.intent.category.BROWSABLE -d "'$url'" | grep -q "$PKG"; then
    fail "psst handles $url"
  else
    pass "psst does not handle $url"
  fi
done
adb shell cmd package query-activities --brief -a android.intent.action.VIEW -c android.intent.category.BROWSABLE -d "'https://app.macet.eu/#/room/#a:chat.macet.eu'" \
  | grep -q "$PKG" && pass "psst handles app.macet.eu links" || log "INFO: app.macet.eu link not resolved to psst"

adb logcat -c
adb shell am start -W -n "$PKG/$ACTIVITY" | tee -a "$RESULT"

# ---------- (b) onboarding ----------
if wait_for_text 01-onboarding "$SIGN_IN_TEXT" 120; then
  pass "onboarding shows '$SIGN_IN_TEXT'"
else
  fail "onboarding does not show '$SIGN_IN_TEXT'"
fi
adb shell pidof "$PKG" >/dev/null && pass "app process running" || fail "app process not running"
check 01-onboarding

# Tap through sign-in
if tap_text 01-onboarding "$SIGN_IN_TEXT"; then
  sleep 12
  snap 02-after-sign-in
  check 02-after-sign-in
  # A second screen deeper (e.g. dismiss a dialog / continue) if there is a Continue / OK button
  for b in "Continue" "OK"; do
    if tap_text 02-after-sign-in "$b"; then sleep 5; snap 03-after-sign-in-2; check 03-after-sign-in-2; break; fi
  done
else
  fail "could not tap '$SIGN_IN_TEXT'"
fi

# QR code sign-in screen
back_to_onboarding
if tap_text _probe "Sign in with QR code"; then
  sleep 4
  snap 04-qr-code
  check 04-qr-code
fi

# Injected Element login link pointing at matrix.org must be ignored
back_to_onboarding
adb shell am start -W -a android.intent.action.VIEW -n "$PKG/$ACTIVITY" \
  -d "'https://mobile.element.io/element/?account_provider=matrix.org&login_hint=mxid:@alice:matrix.org'" >/dev/null
sleep 5
snap 05-login-link
check 05-login-link
back_to_onboarding && pass "still locked to ${HOMESERVER} after login link" || fail "onboarding lost after login link"
cp "$OUT/_probe.xml" "$OUT/06-onboarding-final.xml"; cp "$OUT/_probe.png" "$OUT/06-onboarding-final.png"

# Launcher: show the icon + label in the app drawer (best effort, for manual review)
adb shell input keyevent KEYCODE_HOME
sleep 2
adb shell input swipe 540 1900 540 400 300
sleep 3
snap 07-app-drawer
if $CHECK has "$OUT/07-app-drawer.xml" "psst"; then pass "launcher shows 'psst'"; else log "INFO: 'psst' not found in app drawer dump (launcher layout dependent)"; fi

adb logcat -d > "$OUT/logcat.txt" 2>/dev/null || true
grep -E "FATAL EXCEPTION|AndroidRuntime: Process: ${PKG}" "$OUT/logcat.txt" | head -20 | tee -a "$RESULT"
if grep -q "AndroidRuntime: Process: ${PKG}" "$OUT/logcat.txt"; then fail "app crashed"; fi
rm -f "$OUT/_probe.xml" "$OUT/_probe.png"

if [ $FAILED -ne 0 ]; then log "RESULT: FAILED"; exit 1; fi
log "RESULT: OK"
