#!/usr/bin/env python3
"""PSST iOS: App Store Connect steps for scripts/ios/release-testflight.sh (API key, nothing interactive).

  testflight.py preflight            app record, bundle IDs, App Group capability, our distribution certificate
  testflight.py profiles <outdir>    (re)create our App Store profiles for app + NSE + share extension, verify App Group
  testflight.py next-build           print last TestFlight build number + 1
  testflight.py wait-build <N>       wait until build N is processed (VALID)
  testflight.py testers <N>          internal group "psst" + tester Geo M, build N available to the group
  testflight.py app-info             privacy policy URL on the app record

Only ever creates or replaces objects named "psst …" — nothing else in the shared team is touched (D53/D55).
"""
import base64
import json
import os
import plistlib
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asc  # noqa: E402

BUNDLE = "eu.macet.psst"
TARGETS = [BUNDLE, BUNDLE + ".nse", BUNDLE + ".shareextension"]
GROUP = "group." + BUNDLE
CERT_ID = os.environ.get("PSST_IOS_CERT_ID") or (Path.home() / "psst-keys/ios-dist/cert-id.txt").read_text().strip()
TESTER = {"email": os.environ.get("PSST_TESTER_EMAIL", ""), "firstName": "Geo", "lastName": "M"}
PRIVACY_URL = "https://app.macet.eu/privacy.html"


def die(msg):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(1)


def ok(code, d, what):
    if code >= 300:
        die(f"{what}: {code} {json.dumps(d)[:600]}")
    return d


def app_id():
    d = ok(*asc.call("GET", f"/v1/apps?filter[bundleId]={BUNDLE}"), "apps")
    apps = [a for a in d["data"] if a["attributes"]["bundleId"] == BUNDLE]
    return apps[0] if apps else None


def bundle_ids():
    out = {}
    for ident in TARGETS:
        d = ok(*asc.call("GET", f"/v1/bundleIds?filter[identifier]={ident}&include=bundleIdCapabilities"), "bundleIds")
        m = [b for b in d["data"] if b["attributes"]["identifier"] == ident]
        if not m:
            die(f"bundle ID {ident} is not registered")
        out[ident] = m[0]["id"]
    return out


def preflight():
    a = app_id()
    if not a:
        die(f"no App Store Connect app record for {BUNDLE} — create it once in appstoreconnect.apple.com "
            "(My Apps → + → New App, bundle ID eu.macet.psst), see scripts/ios/README.md")
    print(f"app record: {a['attributes']['name']} ({a['id']})")
    ids = bundle_ids()
    for ident, bid in ids.items():
        caps = {c["attributes"]["capabilityType"]
                for c in ok(*asc.call("GET", f"/v1/bundleIds/{bid}/bundleIdCapabilities"), "caps")["data"]}
        if "APP_GROUPS" not in caps:
            die(f"{ident}: App Groups capability is not enabled")
        print(f"bundle ID {ident}: {', '.join(sorted(caps))}")
    c = ok(*asc.call("GET", f"/v1/certificates/{CERT_ID}"), "certificate")["data"]["attributes"]
    print(f"certificate {CERT_ID}: {c['certificateType']} until {c['expirationDate'][:10]}")


def profiles(outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    ids = bundle_ids()
    missing = []
    for ident, bid in ids.items():
        name = f"psst AppStore {ident}"
        # replace only our own profile of that name (capabilities may have changed since)
        d = ok(*asc.call("GET", f"/v1/profiles?filter[name]={name}&limit=50"), "profiles")
        for p in d["data"]:
            if p["attributes"]["name"] == name:
                asc.call("DELETE", f"/v1/profiles/{p['id']}")
        body = {"data": {"type": "profiles", "attributes": {"name": name, "profileType": "IOS_APP_STORE"},
                         "relationships": {"bundleId": {"data": {"type": "bundleIds", "id": bid}},
                                           "certificates": {"data": [{"type": "certificates", "id": CERT_ID}]}}}}
        d = ok(*asc.call("POST", "/v1/profiles", body), f"create profile {name}")
        raw = base64.b64decode(d["data"]["attributes"]["profileContent"])
        f = out / f"{ident}.mobileprovision"
        f.write_bytes(raw)
        plist = plistlib.loads(subprocess.run(["security", "cms", "-D", "-i", str(f)], capture_output=True, check=True).stdout)
        groups = plist["Entitlements"].get("com.apple.security.application-groups", [])
        ents = sorted(k for k in plist["Entitlements"] if k.startswith(("com.apple", "aps")))
        print(f"profile {name}: {plist['UUID']}  groups={groups}  {ents}")
        if GROUP not in groups:
            missing.append(ident)
    if missing:
        die(f"App Group {GROUP} is not assigned to: {', '.join(missing)} — developer.apple.com → Identifiers → "
            f"<identifier> → App Groups → Configure → tick {GROUP} → Save (for every identifier listed)")


def builds(app):
    d = ok(*asc.call("GET", f"/v1/builds?filter[app]={app}&sort=-uploadedDate&limit=50&fields[builds]=version,processingState,uploadedDate"), "builds")
    return d["data"]


def next_build():
    a = app_id() or die("no app record")
    nums = [int(b["attributes"]["version"]) for b in builds(a["id"]) if b["attributes"]["version"].isdigit()]
    print(max(nums, default=0) + 1)


def find_build(app, n):
    for b in builds(app):
        if b["attributes"]["version"] == str(n):
            return b
    return None


def wait_build(n, timeout=3600):
    a = (app_id() or die("no app record"))["id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        b = find_build(a, n)
        state = b["attributes"]["processingState"] if b else "NOT_YET_VISIBLE"
        print(f"[{int(time.time() - t0):4d}s] build {n}: {state}", flush=True)
        if state == "VALID":
            return
        if state in ("FAILED", "INVALID"):
            die(f"build {n} processing {state} — see the e-mail from App Store Connect")
        time.sleep(30)
    die(f"build {n} not processed within {timeout}s")


def testers(n):
    a = (app_id() or die("no app record"))["id"]
    b = find_build(a, n) or die(f"build {n} not found")
    # export compliance: same answer as Info.plist ITSAppUsesNonExemptEncryption=false (DECISIONS D55)
    if b["attributes"].get("usesNonExemptEncryption") is None:
        asc.call("PATCH", f"/v1/builds/{b['id']}", {"data": {"type": "builds", "id": b["id"], "attributes": {"usesNonExemptEncryption": False}}})
    d = ok(*asc.call("GET", f"/v1/betaGroups?filter[app]={a}&filter[name]=psst"), "betaGroups")
    g = next((x for x in d["data"] if x["attributes"]["name"] == "psst"), None)
    if not g:
        g = ok(*asc.call("POST", "/v1/betaGroups", {"data": {"type": "betaGroups", "attributes": {"name": "psst", "isInternalGroup": True, "hasAccessToAllBuilds": True},
                                                          "relationships": {"app": {"data": {"type": "apps", "id": a}}}}}), "create group")["data"]
        print("created internal TestFlight group psst")
    gid = g["id"]
    if not g["attributes"].get("hasAccessToAllBuilds"):
        asc.call("POST", f"/v1/betaGroups/{gid}/relationships/builds", {"data": [{"type": "builds", "id": b["id"]}]})
    if not TESTER["email"]:
        # internal testers must be App Store Connect users; find "Geo M"
        users = ok(*asc.call("GET", "/v1/users?limit=200&fields[users]=firstName,lastName,username"), "users")["data"]
        u = next((x for x in users if x["attributes"]["firstName"] == "Geo" and x["attributes"]["lastName"] == "M"), None) or die("user Geo M not found")
        TESTER["email"] = u["attributes"]["username"]
    have = ok(*asc.call("GET", f"/v1/betaGroups/{gid}/betaTesters?limit=200"), "testers")["data"]
    if not any(t["attributes"].get("email", "").lower() == TESTER["email"].lower() for t in have):
        c, d = asc.call("POST", "/v1/betaTesters", {"data": {"type": "betaTesters", "attributes": TESTER,
                                                          "relationships": {"betaGroups": {"data": [{"type": "betaGroups", "id": gid}]}}}})
        print("added tester Geo M" if c < 300 else f"tester: {c} {json.dumps(d)[:300]}")
    else:
        print("tester Geo M already in group psst")
    print(f"build {n} available to internal group psst")


def app_info():
    a = (app_id() or die("no app record"))["id"]
    infos = ok(*asc.call("GET", f"/v1/apps/{a}/appInfos"), "appInfos")["data"]
    for info in infos:
        locs = ok(*asc.call("GET", f"/v1/appInfos/{info['id']}/appInfoLocalizations"), "locs")["data"]
        for l in locs:
            if l["attributes"].get("privacyPolicyUrl") != PRIVACY_URL:
                c, d = asc.call("PATCH", f"/v1/appInfoLocalizations/{l['id']}", {"data": {"type": "appInfoLocalizations", "id": l["id"], "attributes": {"privacyPolicyUrl": PRIVACY_URL}}})
                print(f"privacy policy URL ({l['attributes']['locale']}): {c}")
            else:
                print(f"privacy policy URL ({l['attributes']['locale']}): ok")


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:] or ["help"]
    {"preflight": lambda: preflight(), "profiles": lambda: profiles(rest[0]), "next-build": lambda: next_build(),
     "wait-build": lambda: wait_build(int(rest[0])), "testers": lambda: testers(int(rest[0])),
     "app-info": lambda: app_info()}.get(cmd, lambda: print(__doc__))()
