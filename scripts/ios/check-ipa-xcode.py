#!/usr/bin/env python3
"""PSST (D90): gate — refuse an IPA built with a beta Xcode or beta iOS SDK (App Store Connect rejects such builds).

    scripts/ios/check-ipa-xcode.py <app.ipa> [ci/ios-public-xcode.json]

Reads DTXcode, DTXcodeBuild, DTSDKName, DTSDKBuild, DTPlatformVersion, BuildMachineOSBuild from the app's Info.plist
and requires DTXcodeBuild to be a public (GM) Xcode from the allowlist and DTSDKBuild to be the iOS SDK build that
this Xcode ships. Exit 1 otherwise (before any upload)."""
import json
import os
import plistlib
import sys
import zipfile

ipa = sys.argv[1]
allow = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), "..", "..", "ci", "ios-public-xcode.json")
public = json.load(open(allow))["public"]
with zipfile.ZipFile(ipa) as z:
    name = next(n for n in z.namelist() if n.startswith("Payload/") and n.count("/") == 2 and n.endswith(".app/Info.plist"))
    info = plistlib.loads(z.read(name))
keys = ["DTXcode", "DTXcodeBuild", "DTSDKName", "DTSDKBuild", "DTPlatformVersion", "BuildMachineOSBuild",
        "CFBundleIdentifier", "CFBundleShortVersionString", "CFBundleVersion", "CFBundleName", "CFBundleDisplayName"]
for k in keys:
    print(f"{k} = {info.get(k)}")
xb, sb = info.get("DTXcodeBuild"), info.get("DTSDKBuild")
pub = public.get(xb)
if not pub:
    sys.exit(f"FAIL: DTXcodeBuild {xb} is not a public (GM) Xcode release (allowlist: {', '.join(public)}) — beta Xcode?")
if sb != pub["iphoneos_sdk_build"]:
    sys.exit(f"FAIL: DTSDKBuild {sb} is not the public iOS SDK {pub['iphoneos_sdk']} ({pub['iphoneos_sdk_build']}) of Xcode {pub['version']}")
print(f"OK: public Xcode {pub['version']} ({xb}), iOS SDK {pub['iphoneos_sdk']} ({sb})")
