#!/usr/bin/env python3
"""PSST iOS: App Store Connect steps for scripts/ios/release-testflight.sh (API key, nothing interactive).

  testflight.py check [--fix]         checklist: API key, bundle IDs + capabilities, distribution certificate,
                                      app record, App Group; --fix ADDS what the API allows (bundle IDs,
                                      capabilities, a new distribution certificate). Exit 3 = a person must act.
  testflight.py profiles <outdir>     App Store profiles for app + NSE + share extension: reuses our ACTIVE one
                                      when it has the certificate and the App Group, otherwise adds a new one
  testflight.py next-build            print last TestFlight build number + 1 (D54)
  testflight.py wait-build <N>        wait until build N is processed (VALID)
  testflight.py testers <N>           internal group "psst" + tester Geo M, build N available to the group
  testflight.py app-info              privacy policy URL on the app record

The team MHV67VMY8T is shared (D55): this script only ADDS objects named "psst …" and changes only the psst app
record; it never modifies, revokes or deletes anything that exists in the team (also not older psst profiles —
those just expire).
"""
import base64
import datetime
import json
import os
import plistlib
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asc  # noqa: E402

TEAM = "MHV67VMY8T"
BUNDLE = "eu.macet.psst"
TARGETS = {BUNDLE: "psst", BUNDLE + ".nse": "psst NSE", BUNDLE + ".shareextension": "psst Share Extension"}
CAPS = {BUNDLE: ["APP_GROUPS", "PUSH_NOTIFICATIONS", "ASSOCIATED_DOMAINS"],
        BUNDLE + ".nse": ["APP_GROUPS"], BUNDLE + ".shareextension": ["APP_GROUPS"]}
GROUP = "group." + BUNDLE
KEYS = Path(os.environ.get("PSST_KEYS_DIR", Path.home() / "psst-keys"))
DIST = KEYS / "ios-dist"
TESTER = {"email": os.environ.get("PSST_TESTER_EMAIL", ""), "firstName": "Geo", "lastName": "M"}
PRIVACY_URL = "https://app.macet.eu/privacy.html"

# What a person with the right role must do once in the Apple web portals (the API cannot do it).
HUMAN = {
    "agreement": "ACCOUNT HOLDER: sign in to developer.apple.com and appstoreconnect.apple.com and accept any pending "
                 "Program License Agreement (banner at the top; App Store Connect → Business).",
    "app_record": "ACCOUNT HOLDER (or Admin/App Manager with 'Create apps'): appstoreconnect.apple.com → Apps → + → "
                  "New App: platform iOS, name 'psst' (if taken: 'psst secure chat'), primary language Slovak, "
                  f"bundle ID {BUNDLE}, SKU {BUNDLE}, User Access: Full Access → Create.",
    "app_group": f"ACCOUNT HOLDER (or Admin): developer.apple.com → Certificates, IDs & Profiles → Identifiers → "
                 f"filter 'App Groups' → + → App Groups, description 'psst', identifier {GROUP} → Register "
                 f"(skip if it exists). Then for each of {', '.join(TARGETS)}: Identifiers → <id> → App Groups → "
                 f"Configure → tick {GROUP} → Continue → Save.",
    "certificate": "ADMIN or ACCOUNT HOLDER: the API key may not create an Apple Distribution certificate "
                   "(team limit reached or role too low) — developer.apple.com → Certificates → + → Apple Distribution "
                   f"with the CSR {DIST}/dist.csr, download it to {DIST}/dist.cer and re-run.",
    "api_key": "ADMIN: the App Store Connect API key U4SWSW9CRM must exist with role Admin "
               "(appstoreconnect.apple.com → Users and Access → Integrations → Team Keys).",
}


def die(msg, code=1):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(code)


def ok(code, d, what):
    if code >= 300:
        text = json.dumps(d)[:600]
        if code == 403 and "agreement" in text.lower():
            die(f"{what}: {code} — {HUMAN['agreement']}", 3)
        die(f"{what}: {code} {text}")
    return d


def app_record():
    d = ok(*asc.call("GET", f"/v1/apps?filter[bundleId]={BUNDLE}"), "apps")
    apps = [a for a in d["data"] if a["attributes"]["bundleId"] == BUNDLE]
    return apps[0] if apps else None


def bundle_id(ident):
    d = ok(*asc.call("GET", f"/v1/bundleIds?filter[identifier]={ident}&limit=20"), "bundleIds")
    m = [b for b in d["data"] if b["attributes"]["identifier"] == ident]
    return m[0]["id"] if m else None


def capabilities(bid):
    d = ok(*asc.call("GET", f"/v1/bundleIds/{bid}/bundleIdCapabilities"), "capabilities")
    return {c["attributes"]["capabilityType"] for c in d["data"]}


def cert_id():
    env = os.environ.get("PSST_IOS_CERT_ID")
    if env:
        return env
    f = DIST / "cert-id.txt"
    return f.read_text().strip() if f.exists() else ""


def cert_state(cid):
    """'ok' (valid, with local private key + p12), or a reason why it can't be used."""
    if not cid:
        return f"no certificate id in {DIST}/cert-id.txt"
    code, d = asc.call("GET", f"/v1/certificates/{cid}")
    if code == 404:
        return f"certificate {cid} no longer exists (revoked)"
    a = ok(code, d, "certificate")["data"]["attributes"]
    exp = datetime.datetime.fromisoformat(a["expirationDate"].replace("Z", "+00:00"))
    if exp < datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7):
        return f"certificate {cid} expires {a['expirationDate'][:10]}"
    if not ((DIST / "dist.p12").exists() and (DIST / "p12.pass").exists()):
        return f"certificate {cid} is valid but {DIST}/dist.p12 or p12.pass is missing"
    return "ok"


def create_certificate():
    """Adds a new Apple Distribution certificate from our CSR (the private key never leaves this Mac)."""
    key, csr = DIST / "dist.key", DIST / "dist.csr"
    DIST.mkdir(parents=True, exist_ok=True)
    if not key.exists():
        subprocess.run(["openssl", "genrsa", "-out", str(key), "2048"], check=True, capture_output=True)
        os.chmod(key, 0o600)
    if not csr.exists() or os.path.getmtime(csr) < os.path.getmtime(key):
        subprocess.run(["openssl", "req", "-new", "-key", str(key), "-out", str(csr),
                        "-subj", "/CN=psst iOS distribution/C=SK"], check=True, capture_output=True)
    body = {"data": {"type": "certificates",
                     "attributes": {"certificateType": "DISTRIBUTION", "csrContent": csr.read_text()}}}
    code, d = asc.call("POST", "/v1/certificates", body)
    if code >= 300:
        die(f"creating the distribution certificate: {code} {json.dumps(d)[:400]}\n  → {HUMAN['certificate']}", 3)
    cid = d["data"]["id"]
    (DIST / "dist.cer").write_bytes(base64.b64decode(d["data"]["attributes"]["certificateContent"]))
    subprocess.run(["openssl", "x509", "-inform", "DER", "-in", str(DIST / "dist.cer"), "-out", str(DIST / "dist.pem")], check=True)
    pw_file = DIST / "p12.pass"
    if not pw_file.exists():
        pw_file.write_text(base64.b64encode(os.urandom(18)).decode())
        os.chmod(pw_file, 0o600)
    # -legacy: the macOS keychain on the CI runner does not read OpenSSL 3 default (AES/PBKDF2) p12 files
    subprocess.run(["openssl", "pkcs12", "-export", "-legacy", "-inkey", str(key), "-in", str(DIST / "dist.pem"),
                    "-name", "psst Apple Distribution", "-out", str(DIST / "dist.p12"),
                    "-passout", f"file:{pw_file}"], check=True)
    os.chmod(DIST / "dist.p12", 0o600)
    (DIST / "cert-id.txt").write_text(cid + "\n")
    print(f"  + added Apple Distribution certificate {cid} (expires {d['data']['attributes']['expirationDate'][:10]})")
    return cid


def newest_first(profiles_data):
    """Newest first (this endpoint may leave createdDate empty; a newer profile also expires later)."""
    return sorted(profiles_data, key=lambda p: (p["attributes"].get("expirationDate") or "",
                                                p["attributes"].get("createdDate") or ""), reverse=True)


def profile_plist(raw: bytes, path: Path):
    path.write_bytes(raw)
    return plistlib.loads(subprocess.run(["security", "cms", "-D", "-i", str(path)], capture_output=True, check=True).stdout)


def app_group_seen():
    """True/False from our newest ACTIVE app profile, None if there is none (the API cannot read App Groups)."""
    bid = bundle_id(BUNDLE)
    if not bid:
        return None
    d = ok(*asc.call("GET", f"/v1/bundleIds/{bid}/profiles?limit=50"), "profiles")
    mine = [p for p in d["data"] if p["attributes"]["name"].startswith("psst AppStore")
            and p["attributes"]["profileState"] == "ACTIVE"]
    if not mine:
        return None
    newest = newest_first(mine)[0]
    tmp = Path(os.environ.get("TMPDIR", "/tmp")) / "psst-probe.mobileprovision"
    plist = profile_plist(base64.b64decode(newest["attributes"]["profileContent"]), tmp)
    tmp.unlink(missing_ok=True)
    return GROUP in plist["Entitlements"].get("com.apple.security.application-groups", [])


def check(fix=False):
    todo, warn = [], []

    def line(good, text):
        print(f"  [{'x' if good else ' '}] {text}")

    code, _ = asc.call("GET", "/v1/apps?limit=1")
    line(code == 200, f"App Store Connect API key works (HTTP {code})")
    if code != 200:
        print("\n" + HUMAN["api_key"])
        sys.exit(3)

    for ident, name in TARGETS.items():
        bid = bundle_id(ident)
        if not bid and fix:
            body = {"data": {"type": "bundleIds", "attributes": {"identifier": ident, "name": name, "platform": "IOS"}}}
            bid = ok(*asc.call("POST", "/v1/bundleIds", body), f"create bundle ID {ident}")["data"]["id"]
            print(f"  + added bundle ID {ident}")
        line(bool(bid), f"bundle ID {ident}")
        if not bid:
            warn.append(f"bundle ID {ident} missing (the full run adds it)")
            continue
        have = capabilities(bid)
        for cap in CAPS[ident]:
            if cap not in have and fix:
                body = {"data": {"type": "bundleIdCapabilities", "attributes": {"capabilityType": cap},
                                 "relationships": {"bundleId": {"data": {"type": "bundleIds", "id": bid}}}}}
                c, _ = asc.call("POST", "/v1/bundleIdCapabilities", body)
                if c < 300:
                    have.add(cap)
                    print(f"  + enabled {cap} on {ident}")
            line(cap in have, f"  {ident}: capability {cap}")
            if cap not in have:
                warn.append(f"{ident}: capability {cap} not enabled (the full run adds it)")

    state = cert_state(cert_id())
    if state != "ok" and fix:
        create_certificate()
        state = cert_state(cert_id())
    line(state == "ok", f"Apple Distribution certificate {cert_id() or '—'}: {state}")
    if state != "ok":
        warn.append(state + " (the full run adds a new certificate)")

    a = app_record()
    line(bool(a), f"App Store Connect app record for {BUNDLE}" + (f": '{a['attributes']['name']}' ({a['id']})" if a else ""))
    if not a:
        todo.append(HUMAN["app_record"])

    group = app_group_seen()
    line(group is True, f"App Group {GROUP} assigned to the identifiers"
         + ("" if group is not None else " — not known yet (the API cannot read it; checked when the profiles are made)"))
    if group is False:
        todo.append(HUMAN["app_group"])

    if warn:
        print("\nWARNINGS:\n  - " + "\n  - ".join(warn))
    if todo:
        print("\nA PERSON MUST DO THIS ONCE (the App Store Connect API does not allow it):")
        for i, t in enumerate(todo, 1):
            print(f"  {i}. {t}")
        if group is None:
            print(f"  {len(todo) + 1}. If not done yet — {HUMAN['app_group']}")
        print(f"  Also: {HUMAN['agreement']}")
        print("Then run scripts/ios/release-testflight.sh again.")
        sys.exit(3)
    if warn:
        sys.exit(1)
    print("\npreflight OK")


def profiles(outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    cid = cert_id()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M")
    for ident in TARGETS:  # app first: when it lacks the App Group we stop before adding the other two
        bid = bundle_id(ident) or die(f"bundle ID {ident} is not registered (run: testflight.py check --fix)")
        f = out / f"{ident}.mobileprovision"
        reuse = None
        d = ok(*asc.call("GET", f"/v1/bundleIds/{bid}/profiles?limit=50"), "profiles")
        for p in newest_first(d["data"]):
            at = p["attributes"]
            if not (at["name"].startswith(f"psst AppStore {ident}") and at["profileState"] == "ACTIVE"
                    and at["profileType"] == "IOS_APP_STORE"):
                continue
            certs = ok(*asc.call("GET", f"/v1/profiles/{p['id']}/certificates"), "profile certificates")["data"]
            plist = profile_plist(base64.b64decode(at["profileContent"]), f)
            if any(c["id"] == cid for c in certs) and GROUP in plist["Entitlements"].get("com.apple.security.application-groups", []):
                reuse = (at["name"], plist)
                break
        if reuse:
            name, plist = reuse
            print(f"profile {name}: reused ({plist['UUID']})")
        else:
            name = f"psst AppStore {ident} {stamp}"
            body = {"data": {"type": "profiles", "attributes": {"name": name, "profileType": "IOS_APP_STORE"},
                             "relationships": {"bundleId": {"data": {"type": "bundleIds", "id": bid}},
                                               "certificates": {"data": [{"type": "certificates", "id": cid}]}}}}
            d = ok(*asc.call("POST", "/v1/profiles", body), f"create profile {name}")
            plist = profile_plist(base64.b64decode(d["data"]["attributes"]["profileContent"]), f)
            print(f"profile {name}: added ({plist['UUID']})")
        groups = plist["Entitlements"].get("com.apple.security.application-groups", [])
        ents = sorted(k for k in plist["Entitlements"] if k.startswith(("com.apple", "aps")))
        print(f"  groups={groups}  {ents}")
        if GROUP not in groups:
            die(f"App Group {GROUP} is not assigned to {ident}.\n  → {HUMAN['app_group']}", 3)


def builds(app):
    d = ok(*asc.call("GET", f"/v1/builds?filter[app]={app}&sort=-uploadedDate&limit=50&fields[builds]=version,processingState,uploadedDate,usesNonExemptEncryption"), "builds")
    return d["data"]


def next_build():
    a = app_record() or die("no app record\n  → " + HUMAN["app_record"], 3)
    nums = [int(b["attributes"]["version"]) for b in builds(a["id"]) if b["attributes"]["version"].isdigit()]
    print(max(nums, default=0) + 1)


def find_build(app, n):
    for b in builds(app):
        if b["attributes"]["version"] == str(n):
            return b
    return None


def wait_build(n, timeout=5400):
    a = (app_record() or die("no app record"))["id"]
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
    a = (app_record() or die("no app record"))["id"]
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
    a = (app_record() or die("no app record"))["id"]
    infos = ok(*asc.call("GET", f"/v1/apps/{a}/appInfos"), "appInfos")["data"]
    for info in infos:
        locs = ok(*asc.call("GET", f"/v1/appInfos/{info['id']}/appInfoLocalizations"), "locs")["data"]
        for loc in locs:
            if loc["attributes"].get("privacyPolicyUrl") != PRIVACY_URL:
                c, _ = asc.call("PATCH", f"/v1/appInfoLocalizations/{loc['id']}", {"data": {"type": "appInfoLocalizations", "id": loc["id"], "attributes": {"privacyPolicyUrl": PRIVACY_URL}}})
                print(f"privacy policy URL ({loc['attributes']['locale']}): {c}")
            else:
                print(f"privacy policy URL ({loc['attributes']['locale']}): ok")


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:] or ["help"]
    {"check": lambda: check(fix="--fix" in rest), "preflight": lambda: check(fix="--fix" in rest),
     "profiles": lambda: profiles(rest[0]), "next-build": lambda: next_build(),
     "wait-build": lambda: wait_build(int(rest[0])), "testers": lambda: testers(int(rest[0])),
     "app-info": lambda: app_info()}.get(cmd, lambda: print(__doc__))()
