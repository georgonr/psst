#!/usr/bin/env python3
"""psst (DECISIONS.md D83): fail if a released Android APK or AAB declares something Google Play Protect blocks on sideload.

  check-manifest.py <file.apk|file.aab> [...]

Google Play Protect blocks installing sideloaded apps that declare RECEIVE_SMS, READ_SMS, a notification listener or an
accessibility service ("App blocked to protect your device"). The check reads the final, merged manifest inside the
release file (our code + upstream + every library), so nothing a dependency adds can slip through.

It also checks that the application label is the literal "psst": an @string label can show up as the class name
("io.element.android.x.ElementXApplication") in installer and Play Protect dialogs that read the APK before install.

APK: `aapt2 dump xmltree` (build-tools from $ANDROID_HOME / $ANDROID_SDK_ROOT or $AAPT2).
AAB: the protobuf manifests (base/manifest/AndroidManifest.xml and every feature module); strings in protobuf are
plain UTF-8, so a byte search is exact for these names.
Exit code 0 = clean, 1 = forbidden entry found (or label wrong), 2 = usage/tool error.
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import zipfile

FORBIDDEN = {
    "android.permission.RECEIVE_SMS": "permission RECEIVE_SMS",
    "android.permission.READ_SMS": "permission READ_SMS",
    "android.permission.BIND_NOTIFICATION_LISTENER_SERVICE": "notification listener service",
    "android.service.notification.NotificationListenerService": "notification listener service",
    "android.permission.BIND_ACCESSIBILITY_SERVICE": "accessibility service",
    "android.accessibilityservice.AccessibilityService": "accessibility service",
}
LABEL = "psst"


def aapt2() -> str:
    if os.environ.get("AAPT2"):
        return os.environ["AAPT2"]
    for root in (os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"), os.path.expanduser("~/Library/Android/sdk")):
        if root:
            found = sorted(glob.glob(os.path.join(root, "build-tools", "*", "aapt2")))
            if found:
                return found[-1]
    return shutil.which("aapt2") or ""


def check_apk(path: str) -> list[str]:
    tool = aapt2()
    if not tool:
        sys.exit("check-manifest: aapt2 not found (set ANDROID_HOME or AAPT2)")
    out = subprocess.run([tool, "dump", "xmltree", "--file", "AndroidManifest.xml", path],
                         check=True, capture_output=True, text=True).stdout
    problems = [f"{why} ({name})" for name, why in FORBIDDEN.items() if f'"{name}"' in out]
    # application label: the first android:label after "E: application"
    app = out.split("E: application", 1)[1] if "E: application" in out else ""
    m = re.search(r"android:label\([^)]*\)=(\"[^\"]*\"|@0x[0-9a-f]+)", app.split("E: ", 1)[0])
    if not m or m.group(1) != f'"{LABEL}"':
        problems.append(f"application label is {m.group(1) if m else 'missing'}, expected literal \"{LABEL}\"")
    return problems


def check_aab(path: str) -> list[str]:
    problems = []
    with zipfile.ZipFile(path) as z:
        manifests = [n for n in z.namelist() if n.endswith("/manifest/AndroidManifest.xml")]
        if not manifests:
            sys.exit(f"check-manifest: no module manifest in {path}")
        for n in manifests:
            data = z.read(n)
            for name, why in FORBIDDEN.items():
                if name.encode() in data:
                    problems.append(f"{why} ({name}) in {n}")
    return problems


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    bad = 0
    for path in sys.argv[1:]:
        if path.endswith(".apk"):
            problems = check_apk(path)
        elif path.endswith(".aab"):
            problems = check_aab(path)
        else:
            print(f"check-manifest: not an .apk/.aab: {path}")
            return 2
        if problems:
            bad = 1
            for p in problems:
                print(f"FAIL {os.path.basename(path)}: {p}")
        else:
            print(f"OK   {os.path.basename(path)}: no SMS / notification listener / accessibility; label \"{LABEL}\""
                  if path.endswith(".apk") else
                  f"OK   {os.path.basename(path)}: no SMS / notification listener / accessibility")
    if bad:
        print("Google Play Protect blocks sideloaded apps with these entries (DECISIONS.md D83). Remove them before release.")
    return bad


if __name__ == "__main__":
    sys.exit(main())
