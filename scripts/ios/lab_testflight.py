#!/usr/bin/env python3
"""PSST (L1): App Store Connect steps for the psst lab test app (eu.macet.psst.lab, SKU psst-lab).

  lab_testflight.py check               app record + bundle ID exist (never created here), distribution certificate OK
  lab_testflight.py profile <outdir>    App Store profile for eu.macet.psst.lab: reuses our ACTIVE "psst lab AppStore …"
                                        profile with the current certificate, otherwise ADDS one
  lab_testflight.py next-build          last psst lab build number + 1
  lab_testflight.py wait-build <N>      waits until build N is processed (VALID)
  lab_testflight.py testers <N>         internal TestFlight group "psst" of psst lab (created if missing, internal only)
                                        + tester Geo M, export compliance answered (standard algorithms, exempt)

Only ADDS objects named "psst lab …" and touches only the psst lab app record. Never: the psst app (eu.macet.psst),
review submissions, external testers, app metadata.
"""
import base64
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asc  # noqa: E402
import testflight as tf  # noqa: E402  (certificate helpers, profile decoding)

BUNDLE = "eu.macet.psst.lab"
SKU = "psst-lab"
PROFILE_PREFIX = f"psst lab AppStore {BUNDLE}"


def app_record():
    d = tf.ok(*asc.call("GET", f"/v1/apps?filter[bundleId]={BUNDLE}"), "apps")
    apps = [a for a in d["data"] if a["attributes"]["bundleId"] == BUNDLE]
    return apps[0] if apps else None


def check():
    a = app_record()
    print(f"  [{'x' if a else ' '}] app record {BUNDLE}" + (f": '{a['attributes']['name']}' SKU {a['attributes']['sku']} ({a['id']})" if a else ""))
    bid = tf.bundle_id(BUNDLE)
    print(f"  [{'x' if bid else ' '}] bundle ID {BUNDLE}" + (f" capabilities {sorted(tf.capabilities(bid))}" if bid else ""))
    state = tf.cert_state(tf.cert_id())
    print(f"  [{'x' if state == 'ok' else ' '}] Apple Distribution certificate {tf.cert_id()}: {state}")
    if not (a and bid and state == "ok"):
        tf.die("psst lab prerequisites missing (app record / App ID are made by the owner, not by this script)", 3)
    if a["attributes"]["sku"] != SKU:
        print(f"  note: SKU is {a['attributes']['sku']}, expected {SKU}")
    print("lab preflight OK")


def profile(outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    cid = tf.cert_id()
    bid = tf.bundle_id(BUNDLE) or tf.die(f"bundle ID {BUNDLE} is not registered", 3)
    f = out / f"{BUNDLE}.mobileprovision"
    d = tf.ok(*asc.call("GET", f"/v1/bundleIds/{bid}/profiles?limit=50"), "profiles")
    for p in tf.newest_first(d["data"]):
        at = p["attributes"]
        if not (at["name"].startswith(PROFILE_PREFIX) and at["profileState"] == "ACTIVE" and at["profileType"] == "IOS_APP_STORE"):
            continue
        certs = tf.ok(*asc.call("GET", f"/v1/profiles/{p['id']}/certificates"), "profile certificates")["data"]
        if any(c["id"] == cid for c in certs):
            plist = tf.profile_plist(base64.b64decode(at["profileContent"]), f)
            print(f"profile {at['name']}: reused ({plist['UUID']})")
            return
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M")
    name = f"{PROFILE_PREFIX} {stamp}"
    body = {"data": {"type": "profiles", "attributes": {"name": name, "profileType": "IOS_APP_STORE"},
                     "relationships": {"bundleId": {"data": {"type": "bundleIds", "id": bid}},
                                       "certificates": {"data": [{"type": "certificates", "id": cid}]}}}}
    d = tf.ok(*asc.call("POST", "/v1/profiles", body), f"create profile {name}")
    plist = tf.profile_plist(base64.b64decode(d["data"]["attributes"]["profileContent"]), f)
    print(f"profile {name}: added ({plist['UUID']}), entitlements {sorted(plist['Entitlements'])}")


def builds(app_id):
    d = tf.ok(*asc.call("GET", f"/v1/builds?filter[app]={app_id}&sort=-uploadedDate&limit=50"
                                "&fields[builds]=version,processingState,uploadedDate,usesNonExemptEncryption"), "builds")
    return d["data"]


def next_build():
    a = app_record() or tf.die("no psst lab app record", 3)
    nums = [int(b["attributes"]["version"]) for b in builds(a["id"]) if b["attributes"]["version"].isdigit()]
    print(max(nums, default=0) + 1)


def find_build(app_id, n):
    return next((b for b in builds(app_id) if b["attributes"]["version"] == str(n)), None)


def wait_build(n, timeout=5400):
    import time
    a = (app_record() or tf.die("no app record"))["id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        b = find_build(a, n)
        state = b["attributes"]["processingState"] if b else "NOT_YET_VISIBLE"
        print(f"[{int(time.time() - t0):4d}s] psst lab build {n}: {state}", flush=True)
        if state == "VALID":
            return
        if state in ("FAILED", "INVALID"):
            tf.die(f"build {n} processing {state}")
        time.sleep(30)
    tf.die(f"build {n} not processed within {timeout}s")


def testers(n):
    a = (app_record() or tf.die("no app record"))["id"]
    b = find_build(a, n) or tf.die(f"build {n} not found")
    if b["attributes"].get("usesNonExemptEncryption") is None:
        # same answer as Info.plist ITSAppUsesNonExemptEncryption=false: standard algorithms only (CryptoKit X25519,
        # ChaCha20-Poly1305 — exempt under the mass-market / standard cryptography exemption, as for psst, D55)
        asc.call("PATCH", f"/v1/builds/{b['id']}", {"data": {"type": "builds", "id": b["id"], "attributes": {"usesNonExemptEncryption": False}}})
    d = tf.ok(*asc.call("GET", f"/v1/betaGroups?filter[app]={a}&filter[name]=psst"), "betaGroups")
    g = next((x for x in d["data"] if x["attributes"]["name"] == "psst"), None)
    if g and not g["attributes"].get("isInternalGroup"):
        tf.die("group 'psst' of psst lab exists but is EXTERNAL — not touching it", 3)
    if not g:
        g = tf.ok(*asc.call("POST", "/v1/betaGroups", {"data": {"type": "betaGroups",
                  "attributes": {"name": "psst", "isInternalGroup": True, "hasAccessToAllBuilds": True},
                  "relationships": {"app": {"data": {"type": "apps", "id": a}}}}}), "create group")["data"]
        print("created internal TestFlight group psst (psst lab)")
    gid = g["id"]
    if not g["attributes"].get("hasAccessToAllBuilds"):
        asc.call("POST", f"/v1/betaGroups/{gid}/relationships/builds", {"data": [{"type": "builds", "id": b["id"]}]})
    users = tf.ok(*asc.call("GET", "/v1/users?limit=200&fields[users]=firstName,lastName,username"), "users")["data"]
    u = next((x for x in users if x["attributes"]["firstName"] == "Geo" and x["attributes"]["lastName"] == "M"), None) \
        or tf.die("App Store Connect user Geo M not found")
    email = u["attributes"]["username"]
    have = tf.ok(*asc.call("GET", f"/v1/betaGroups/{gid}/betaTesters?limit=200"), "testers")["data"]
    if not any(t["attributes"].get("email", "").lower() == email.lower() for t in have):
        c, d = asc.call("POST", "/v1/betaTesters", {"data": {"type": "betaTesters",
                        "attributes": {"email": email, "firstName": "Geo", "lastName": "M"},
                        "relationships": {"betaGroups": {"data": [{"type": "betaGroups", "id": gid}]}}}})
        print("added tester Geo M" if c < 300 else f"tester: {c} {json.dumps(d)[:300]}")
    else:
        print("tester Geo M already in group psst")
    ext = tf.ok(*asc.call("GET", f"/v1/betaGroups?filter[app]={a}"), "groups")["data"]
    print("groups of psst lab: " + ", ".join(f"{x['attributes']['name']} ({'internal' if x['attributes'].get('isInternalGroup') else 'EXTERNAL'})" for x in ext))
    print(f"psst lab build {n} available to the internal group psst")


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:] or ["help"]
    {"check": check, "profile": lambda: profile(rest[0]), "next-build": next_build,
     "wait-build": lambda: wait_build(int(rest[0])), "testers": lambda: testers(int(rest[0]))}.get(cmd, lambda: print(__doc__))()
