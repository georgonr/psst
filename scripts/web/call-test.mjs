// PSST — test hovoru (Element Call embedded v Element Web + LiveKit) na lokálnom stacku.
//   node call-test.mjs <out-dir> <roomId> <label> <user1> <pass1> <user2> <pass2>
// Dva izolované prehliadačové kontexty s falošnou kamerou/mikrofónom sa pripoja do hovoru v tej istej
// miestnosti. Úspech = obaja v hovore vidia 2 účastníkov (dlaždice) a médiá prúdia (inbound-rtp bajty).
import { chromium } from "playwright";
import { HOST_RULES, loginViaMas } from "./psst-auth.mjs";
import fs from "node:fs";
import path from "node:path";

const [out, roomId, label, u1, p1, u2, p2] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const results = [];
const check = (name, ok, detail = "") => {
    results.push({ name, ok, detail });
    console.log(`${ok ? "PASS" : "FAIL"}  [${label}] ${name}${detail ? "  -- " + detail : ""}`);
};
const browser = await chromium.launch({
    args: [
        HOST_RULES,
        "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required",
    ],
});

async function login(user, pass) {
    const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1280, height: 860 },
        permissions: ["camera", "microphone"] });
    const page = await ctx.newPage();
    const logf = path.join(out, `${label}-${user}-console.log`);
    page.on("console", (m) => fs.appendFileSync(logf, `[${m.type()}] ${m.location()?.url?.split("?")[0] ?? ""} ${m.text()}\n`));
    page.on("requestfailed", (r) => fs.appendFileSync(logf, `[requestfailed] ${r.url()} ${r.failure()?.errorText}\n`));
    page.on("response", (r) => { if (r.status() >= 400) fs.appendFileSync(logf, `[http ${r.status()}] ${r.url()}\n`); });
    await page.goto("https://app.macet.eu/#/login");
    try {
        await loginViaMas(page, user, pass);
    } catch (e) {
        await page.screenshot({ path: path.join(out, `${label}-${user}-login-FAIL.png`) });
        fs.writeFileSync(path.join(out, `${label}-${user}-login-FAIL.txt`), page.url() + "\n" + await page.locator("body").innerText().catch(() => ""));
        throw e;
    }
    await page.waitForTimeout(5000);
    for (let i = 0; i < 4; i++) await page.keyboard.press("Escape").catch(() => {});
    await page.goto(`https://app.macet.eu/#/room/${roomId}`);
    await page.waitForSelector(".mx_RoomView", { timeout: 60000 });
    await page.waitForTimeout(3000);
    for (let i = 0; i < 2; i++) await page.keyboard.press("Escape").catch(() => {});
    return page;
}

async function joinCall(page, who) {
    // prebiehajúci hovor → "Join" (tlačidlo "Video call" je vtedy neaktívne); inak začni nový hovor
    const join = page.locator('button:has-text("Join"):enabled, [aria-label="Join"]:enabled');
    try {
        if (await join.count()) await join.first().click({ timeout: 30000 });
        else await page.locator('[aria-label="Video call"]').first().click({ timeout: 30000 });
    } catch (e) {
        await page.screenshot({ path: path.join(out, `${label}-${who}-join-FAIL.png`) });
        const btns = await page.locator("button, [role=button]").evaluateAll((els) => els.map((e) => `${e.getAttribute("aria-label") || ""}|${e.innerText.trim().slice(0, 30)}|${e.disabled || e.getAttribute("aria-disabled")}`).filter((t) => /call|join|video/i.test(t)));
        fs.writeFileSync(path.join(out, `${label}-${who}-buttons.txt`), btns.join("\n"));
        throw e;
    }
    await page.waitForTimeout(4000);
    // Element Call môže ponúknuť lobby s tlačidlom "Join call" vnútri iframe widgetu
    for (let i = 0; i < 20; i++) {
        let clicked = false;
        for (const f of page.frames()) {
            const j = f.locator('[data-testid="lobby_joinCall"], button:has-text("Join call")');
            if (await j.count().catch(() => 0)) { await j.first().click().catch(() => {}); clicked = true; break; }
        }
        if (clicked) break;
        const outer = page.locator('.mx_Dialog button:has-text("Join"), button:has-text("Join call")');
        if (await outer.count()) { await outer.first().click().catch(() => {}); }
        await page.waitForTimeout(1500);
    }
    await page.screenshot({ path: path.join(out, `${label}-${who}-joining.png`) });
}

async function callState(page) {
    let tiles = 0, inbound = 0, frameUrl = "";
    for (const f of page.frames()) {
        if (!/element-call|widgets/.test(f.url())) continue;
        frameUrl = f.url().split("#")[0];
        tiles = Math.max(tiles, await f.locator('[data-testid="videoTile"]').count().catch(() => 0));
        inbound = Math.max(inbound, await f.evaluate(async () => {
            let total = 0;
            const kinds = new Set();
            for (const pc of (globalThis.__psstPCs || [])) {
                const st = await pc.getStats();
                const byId = {}; st.forEach((r) => { byId[r.id] = r; });
                st.forEach((r) => {
                    if (r.type === "inbound-rtp") total += r.bytesReceived || 0;
                    if (r.type === "candidate-pair" && r.nominated && r.state === "succeeded") {
                        const lc = byId[r.localCandidateId] || {};
                        kinds.add(`${lc.candidateType}${lc.relayProtocol ? "/" + lc.relayProtocol : ""}/${lc.protocol}`);
                    }
                });
            }
            globalThis.__psstKinds = [...kinds].join(",");
            return total;
        }).catch(() => 0));
    }
    let kinds = "";
    for (const f of page.frames()) kinds += await f.evaluate(() => globalThis.__psstKinds || "").catch(() => "");
    for (const f of page.frames()) {
        const ice = await f.evaluate(() => (globalThis.__psstIce || []).slice(-2).join(" ")).catch(() => "");
        if (ice && ice !== "[]") fs.appendFileSync(path.join(out, "ice-servers.log"), f.url().split("?")[0] + " " + ice + "\n");
    }
    return { tiles, inbound, frameUrl, kinds };
}

// zachyť RTCPeerConnection v každom ráme (aj v iframe Element Call), aby sme vedeli čítať štatistiky
const RELAY_ONLY = process.env.PSST_RELAY_ONLY === "1";
const hook = (relayOnly) => {
    const Orig = globalThis.RTCPeerConnection;
    if (!Orig || Orig.__psst) return;
    globalThis.__psstPCs = [];
    // simulácia siete bez UDP: len TURN cez TLS (turns:…:443), žiadne priame/UDP kandidáty
    const relay = (cfg = {}) => !relayOnly ? cfg : { ...cfg, iceTransportPolicy: "relay",
        iceServers: (cfg.iceServers || []).map((s) => ({ ...s, urls: [].concat(s.urls || []).filter((u) => u.startsWith("turns:")) }))
            .filter((s) => s.urls.length) };
    globalThis.__psstIce = [];
    const origSet = Orig.prototype.setConfiguration;
    Orig.prototype.setConfiguration = function (cfg) {
        globalThis.__psstIce.push(JSON.stringify((cfg || {}).iceServers || []));
        return origSet.call(this, relay(cfg));
    };
    const Wrapped = function (cfg = {}, ...a) {
        globalThis.__psstIce.push(JSON.stringify(cfg.iceServers || []));
        const pc = new Orig(relay(cfg), ...a); globalThis.__psstPCs.push(pc); return pc;
    };
    Wrapped.prototype = Orig.prototype; Wrapped.__psst = true;
    globalThis.RTCPeerConnection = Wrapped;
};

const pageA = await login(u1, p1);
const pageB = await login(u2, p2);
await pageA.context().addInitScript(hook, RELAY_ONLY);
await pageB.context().addInitScript(hook, RELAY_ONLY);
check("oba účty prihlásené a v miestnosti", true);

await joinCall(pageA, u1);
await pageA.waitForTimeout(5000);
await pageB.reload();
await pageB.waitForSelector(".mx_RoomView", { timeout: 60000 });
await pageB.waitForTimeout(4000);
await joinCall(pageB, u2);

let a = {}, b = {};
for (let i = 0; i < 30; i++) {
    a = await callState(pageA); b = await callState(pageB);
    if (a.tiles >= 2 && b.tiles >= 2 && a.inbound > 0 && b.inbound > 0) break;
    await pageA.waitForTimeout(2000);
}
await pageA.screenshot({ path: path.join(out, `${label}-${u1}-incall.png`) });
await pageB.screenshot({ path: path.join(out, `${label}-${u2}-incall.png`) });
check("Element Call widget načítaný z embedded balíka (nie call.element.io)", !!a.frameUrl && !a.frameUrl.includes("element.io"), a.frameUrl);
check(`${u1} vidí 2 účastníkov`, a.tiles >= 2, `dlaždice: ${a.tiles}`);
check(`${u2} vidí 2 účastníkov`, b.tiles >= 2, `dlaždice: ${b.tiles}`);
check("médiá prúdia oboma smermi (inbound-rtp bajty)", a.inbound > 0 && b.inbound > 0, `A ${a.inbound} B, B ${b.inbound} B; ICE: ${a.kinds} | ${b.kinds}`);
if (RELAY_ONLY) check("spojenie ide cez TURN/TLS (relayProtocol=tls)", /(relay|prflx)\/tls\//.test(a.kinds) && /(relay|prflx)\/tls\//.test(b.kinds), `${a.kinds} | ${b.kinds}`);
fs.writeFileSync(path.join(out, `${label}-result.json`), JSON.stringify(results, null, 2));
await browser.close();
const fails = results.filter((r) => !r.ok).length;
console.log(`\n[${label}] ${results.length - fails}/${results.length} checks passed`);
process.exit(fails ? 1 : 0);
