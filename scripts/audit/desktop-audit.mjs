// PSST feature audit — desktop app (Windows MSI / macOS DMG) against production (docs/FEATURE-MATRIX.md).
//   node desktop-audit.mjs <app-binary> <out-dir> <accounts.json> <platform: windows|macos>
// accounts.json: {"a": desktop user, "b": partner (Element Web), "c": third (Element Web)} — fresh test accounts.
// The app is driven over CDP; MAS login: the URL the app opens in the system browser is captured in the renderer,
// signed in with Playwright and the eu.macet.* callback handed back to the app (as protocol.ts does).
import { chromium } from "playwright";
import { spawn, execSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { runFeatures, writeResults, sleep, cli, startCall, joinFromToast, remoteVideo, icePaths, hangUp, PC_HOOK, dismiss } from "./features.mjs";

const [BIN, OUT, ACC_FILE, PLATFORM] = process.argv.slice(2);
fs.mkdirSync(OUT, { recursive: true });
const A = JSON.parse(fs.readFileSync(ACC_FILE, "utf8"));
const HS = "chat.macet.eu", WEB = "https://app.macet.eu";
const results = [];
const record = (id, status, note = "") => { results.push({ id, status, note: String(note).slice(0, 300) }); console.log(`${status.toUpperCase().padEnd(8)} ${id}  ${note}`); };
const MEDIA = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required",
    "--auto-select-desktop-capture-source=Entire screen"];

// ---------------------------------------------------------------- desktop app
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "psst-audit-"));
let appLog = "";
const launch = (extra = []) => {
    const p = spawn(BIN, ["--remote-debugging-port=9333", ...MEDIA, `--profile-dir=${profile}`, ...extra], { stdio: ["ignore", "pipe", "pipe"] });
    p.stdout.on("data", (d) => (appLog += d)); p.stderr.on("data", (d) => (appLog += d));
    return p;
};
launch();
let cdp;
for (let i = 0; i < 90 && !cdp; i++) { try { cdp = await chromium.connectOverCDP("http://127.0.0.1:9333"); } catch { await sleep(1000); } }
if (!cdp) { record("install", "fail", "appka sa nespustila (CDP)"); writeResults(OUT, PLATFORM, results); process.exit(1); }
record("install", "ok", "nainštalovaná appka sa spustila");
const mainPage = async () => {
    for (let i = 0; i < 60; i++) {
        const p = cdp.contexts().flatMap((c) => c.pages()).find((x) => x.url().startsWith("vector://"));
        if (p) return p;
        await sleep(1000);
    }
    throw new Error("main window not found");
};
let me = await mainPage();
me.on("dialog", (d) => d.accept().catch(() => {}));
await me.context().addInitScript(PC_HOOK).catch(() => {});
await me.waitForSelector(".mx_Login_fullWidthButton, .mx_AuthPage", { timeout: 120000 });
await sleep(3000);
const dl = await me.locator('a[href="https://app.macet.eu/download/"]').count();
record("download_page", dl ? "ok" : "fail", `odkaz „Download apps“ na prihlasovacej obrazovke ${dl > 0}`);

async function desktopLogin(user, password) {
    await me.locator(".mx_Login_fullWidthButton, button:has-text('Continue')").first().waitFor({ state: "visible", timeout: 90000 });
    let authUrl = "";
    const s = await me.context().newCDPSession(me); await s.send("Page.enable");
    s.on("Page.frameRequestedNavigation", (e) => { if (e.url.includes(`${HS}/auth/`)) authUrl = e.url; });
    await sleep(2000);
    await me.evaluate(() => { window.__psstUrls = []; window.open = (u) => { window.__psstUrls.push(String(u)); return null; }; });
    await me.getByText(/^(Pokračovať|Continue)$/).first().evaluate((e) => e.click());
    for (let i = 0; i < 30 && !authUrl; i++) { authUrl = (await me.evaluate(() => window.__psstUrls[0] || "").catch(() => "")) || authUrl; if (!authUrl) await sleep(1000); }
    if (!authUrl) throw new Error("MAS URL not captured");
    const b2 = await chromium.launch(); const p2 = await (await b2.newContext()).newPage();
    let callback = "";
    p2.on("response", async (r) => { const loc = (await r.allHeaders().catch(() => ({})))["location"] || ""; if (/^(eu\.macet\.|psst:)/.test(loc)) callback = loc; });
    await p2.goto(authUrl);
    await p2.fill('input[name="username"]', user, { timeout: 30000 }); await p2.fill('input[name="password"]', password);
    await p2.click("button[type=submit]");
    for (let i = 0; i < 20 && !callback; i++) { await p2.locator('button[type=submit]:has-text("Continue")').first().click({ timeout: 2000 }).catch(() => {}); await sleep(1500); }
    await b2.close();
    if (!callback) throw new Error("no OIDC callback");
    const cb = new URL(callback); const target = new URL("vector://vector/webapp/"); target.search = cb.search; target.hash = cb.hash;
    await me.goto(target.href).catch(() => {}); await me.reload().catch(() => {});
    for (let i = 0; i < 120; i++) {
        if (await me.locator(".mx_LeftPanel, .mx_RoomListPanel").count()) { await sleep(4000); await dismiss(me); return "app"; }
        if (await me.getByText("Confirm your digital identity").count().catch(() => 0)) return "identity";
        await sleep(1000);
    }
    throw new Error("desktop login: neither app nor identity screen");
}

// ---------------------------------------------------------------- partner + third (Element Web)
const pb = await chromium.launch({ args: MEDIA });
async function webLogin(user, password) {
    const ctx = await pb.newContext({ viewport: { width: 1280, height: 900 }, permissions: ["camera", "microphone", "notifications"] });
    await ctx.addInitScript(PC_HOOK);
    const p = await ctx.newPage();
    p.on("dialog", (d) => d.accept().catch(() => {}));
    await p.goto(`${WEB}/#/login`);
    await p.locator('button:has-text("Continue")').first().click({ timeout: 90000 });
    await p.waitForURL(/chat\.macet\.eu\/auth/, { timeout: 60000 });
    await p.fill('input[name="username"]', user); await p.fill('input[name="password"]', password);
    await p.locator("button[type=submit]").first().click();
    for (let i = 0; i < 20 && !p.url().startsWith(WEB); i++) { await p.locator('button[type=submit]:has-text("Continue")').first().click({ timeout: 1500 }).catch(() => {}); await sleep(1000); }
    for (let i = 0; i < 90; i++) { if (await p.locator(".mx_LeftPanel, .mx_RoomListPanel").count()) break; await sleep(1000); }
    await sleep(4000); await dismiss(p);
    return p;
}

// ================================================================ run
try {
    const st = await desktopLogin(A.a.user, A.a.password);
    record("login", st === "app" ? "ok" : "fail", `prihlásenie cez MAS (systémový prehliadač → ${PLATFORM === "macos" ? "eu.macet.app://" : "protocol handler"}) → ${st}`);
} catch (e) { record("login", "fail", String(e.message).slice(0, 200)); writeResults(OUT, PLATFORM, results); process.exit(1); }
const partner = await webLogin(A.b.user, A.b.password);
const third = await webLogin(A.c.user, A.c.password);

// About shows the build
try {
    const v = await me.evaluate(async () => (await window.mxPlatformPeg.get().getAppVersion()));
    record("about_build", /-b\d+ \(\d{4}-\d{2}-\d{2}\)/.test(v) ? "ok" : "fail", `verzia ${v}`);
} catch (e) { record("about_build", "fail", e.message); }

await runFeatures({ me, partner, third, users: { me: A.a.user, partner: A.b.user, third: A.c.user }, record, out: OUT, platform: PLATFORM });

// notifications with the window hidden (closed to tray / dock)
try {
    await me.evaluate(() => { location.hash = "#/home"; });
    const before = await me.evaluate(() => (window.__psstNotes || []).length);
    if (PLATFORM === "macos") {
        // red close button: Element hides the window on macOS, the app keeps running in the Dock
        await me.evaluate(() => window.close());
    } else {
        execSync(`powershell -NoProfile -Command "Add-Type -Name W -Namespace P -MemberDefinition '[DllImport(\\"user32.dll\\")] public static extern bool PostMessage(System.IntPtr h, uint m, System.IntPtr w, System.IntPtr l);'; $h=(Get-Process psst | Where-Object MainWindowHandle -ne 0 | Select-Object -First 1).MainWindowHandle; [void][P.W]::PostMessage($h, 0x0010, [System.IntPtr]::Zero, [System.IntPtr]::Zero)"`);
    }
    await sleep(4000);
    const dm = await partner.evaluate((u) => { const c = window.mxMatrixClientPeg.get(); const d = c.getAccountData("m.direct")?.getContent() || {}; return (d[u] || [])[0]; }, `@${A.a.user}:${HS}`);
    await partner.evaluate(([r, b]) => window.mxMatrixClientPeg.get().sendTextMessage(r, b), [dm, `closed ${Date.now()}`]);
    let after = before;
    for (let i = 0; i < 30 && after <= before; i++) { await sleep(1000); after = await me.evaluate(() => (window.__psstNotes || []).length).catch(() => -1); }
    record("notif_closed", after > before ? "ok" : "fail", `okno zatvorené (${PLATFORM === "macos" ? "appka v Docku" : "appka v tray"}), notifikácia ${before}→${after}`);
} catch (e) { record("notif_closed", "fail", String(e.message).slice(0, 200)); }
record("notif_lock", "na", "zamknutá obrazovka OS sa na CI runneri nedá overiť");

// 1:1 call with outgoing UDP blocked by the OS firewall (DNS allowed) → media must go over TCP / TURN-TLS 443
try {
    const block = PLATFORM === "windows"
        ? `powershell -NoProfile -Command "New-NetFirewallRule -DisplayName psst-block-udp -Direction Outbound -Protocol UDP -RemotePort 1-52,54-65535 -Action Block | Out-Null"`
        : `printf 'block drop out quick proto udp from any to any port != 53\\n' | sudo tee /etc/pf.psst.conf >/dev/null && sudo pfctl -E -f /etc/pf.psst.conf`;
    const unblock = PLATFORM === "windows"
        ? `powershell -NoProfile -Command "Remove-NetFirewallRule -DisplayName psst-block-udp"`
        : `sudo pfctl -d`;
    execSync(block, { stdio: "inherit" });
    // the window may be hidden after notif_closed → show it again (second launch focuses the running instance)
    launch(); await sleep(6000); me = await mainPage();
    const dm = await partner.evaluate((u) => { const c = window.mxMatrixClientPeg.get(); const d = c.getAccountData("m.direct")?.getContent() || {}; return (d[u] || [])[0]; }, `@${A.a.user}:${HS}`);
    await me.evaluate(() => { location.hash = "#/home"; });
    await startCall(partner, dm, "Video call");
    const r = await joinFromToast(me);
    const v = r.joined ? await remoteVideo(me, 1) : { playing: 0 };
    const paths = await icePaths(me);
    const udp = paths.some((x) => /\/udp/.test(x.local) && !/relay/.test(x.local));
    record("call_udp_blocked", r.joined && v.playing >= 1 && !udp ? "ok" : "fail", `UDP zablokované firewallom: pripojenie ${r.joined}, video ${v.playing}, ICE ${JSON.stringify(paths.slice(0, 3))}`);
    await hangUp(me, partner);
    execSync(unblock, { stdio: "inherit" });
} catch (e) { record("call_udp_blocked", "fail", String(e.message).slice(0, 200)); }

// update check against app.macet.eu/download
const m = /psst update check: installed b(\d+), available b(\d+)/.exec(appLog);
record("update_check", m ? "ok" : "fail", m ? m[0] : "v logu chýba „psst update check“ (spúšťa sa 60 s po štarte)");

fs.writeFileSync(path.join(OUT, `${PLATFORM}-app.log`), appLog);
writeResults(OUT, PLATFORM, results);
await pb.close().catch(() => {});
await cdp.close().catch(() => {});
console.log(`\n${results.filter((r) => r.status === "ok").length} ok, ${results.filter((r) => r.status === "fail").length} fail, ${results.length} total`);
process.exit(0);
