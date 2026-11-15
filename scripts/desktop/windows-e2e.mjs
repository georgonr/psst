// PSST Windows desktop — end-to-end test of the installed MSI against production chat.macet.eu (D60).
//   node windows-e2e.mjs <psst.exe> <out-dir> <accounts.json> <expected-build>
// accounts.json: {"desktop": {"user","password"}, "partner": {...}, "third": {...}} — fresh per run
//   (scripts/desktop/e2e-accounts.sh create); partner = Element Web, third = 3rd group member
//
// The desktop app is driven over CDP (--remote-debugging-port). The partner is Element Web (app.macet.eu) in
// headless Chromium, so E2EE runs in real clients on both sides. MAS login: the URL the app wants to open in the
// system browser is captured in the renderer, signed in with Playwright, and the callback handed back to the app.
import { chromium } from "playwright";
import { spawn, execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const [EXE, OUT, ACC_FILE, EXPECTED_BUILD = ""] = process.argv.slice(2);
fs.mkdirSync(OUT, { recursive: true });
const ROLES = JSON.parse(fs.readFileSync(ACC_FILE, "utf8"));
const ACC = Object.fromEntries(Object.values(ROLES).map((r) => [r.user, r.password]));
const U_DESK = ROLES.desktop.user, U_PART = ROLES.partner.user, U_THIRD = ROLES.third.user;
const HS = "chat.macet.eu";
const WEB = "https://app.macet.eu";
const res = [];
const metrics = {};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const check = (n, ok, d = "") => { res.push({ n, ok: !!ok, d: String(d).slice(0, 400) }); console.log(`${ok ? "PASS" : "FAIL"}  ${n}${d ? "  -- " + String(d).slice(0, 200) : ""}`); };
let shotN = 0;
const shot = async (p, name) => { try { await p.screenshot({ path: path.join(OUT, `${String(++shotN).padStart(2, "0")}-${name}.png`) }); } catch {} };
async function step(name, fn) {
    try { await fn(); } catch (e) { check(name, false, e?.stack || e); }
}
const ps = (cmd) => execFileSync("powershell.exe", ["-NoProfile", "-Command", cmd], { encoding: "utf8" }).trim();

// ------------------------------------------------------------------ desktop
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "psst-e2e-"));
const ARGS = ["--remote-debugging-port=9333", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
    "--autoplay-policy=no-user-gesture-required", `--profile-dir=${profile}`];
let appLog = "";
function launch(extra = []) {
    const p = spawn(EXE, [...ARGS, ...extra], { stdio: ["ignore", "pipe", "pipe"] });
    p.stdout.on("data", (d) => (appLog += d)); p.stderr.on("data", (d) => (appLog += d));
    return p;
}
let proc = launch();
let browser;
for (let i = 0; i < 90 && !browser; i++) { try { browser = await chromium.connectOverCDP("http://127.0.0.1:9333"); } catch { await sleep(1000); } }
check("1.1 inštalácia + prvé spustenie: appka beží, CDP dostupné", !!browser);
const mainPage = async () => {
    for (let i = 0; i < 60; i++) {
        const p = browser.contexts().flatMap((c) => c.pages()).find((x) => x.url().startsWith("vector://"));
        if (p) return p;
        await sleep(1000);
    }
    throw new Error("main window not found");
};
let page = await mainPage();
page.on("dialog", (d) => d.accept().catch(() => {}));
await page.waitForSelector(".mx_ServerPicker_server, .mx_Login_fullWidthButton, .mx_AuthPage", { timeout: 120000 });
await page.locator(".mx_Login_fullWidthButton, button:has-text('Continue')").first().waitFor({ state: "visible", timeout: 90000 }).catch(() => {});
check("1.2 hlavné okno: prihlasovacia obrazovka psst", (await page.title()).toLowerCase().includes("psst"), await page.title());
await shot(page, "login");

// ------------------------------------------------------------------ resources
function sample() {
    const j = JSON.parse(ps("$p = Get-Process psst -ErrorAction SilentlyContinue; @{ws=($p | Measure-Object WorkingSet64 -Sum).Sum; cpu=($p | Measure-Object CPU -Sum).Sum; n=$p.Count} | ConvertTo-Json -Compress"));
    return { t: Date.now(), wsMB: Math.round((j.ws || 0) / 1048576), cpu: j.cpu || 0, n: j.n || 0 };
}
async function monitor(label, seconds) {
    const cores = os.cpus().length; const s = [sample()]; let maxLag = 0;
    for (let t = 0; t < seconds; t += 15) {
        await sleep(15000);
        const t0 = Date.now(); await Promise.race([page.evaluate(() => 1), sleep(10000).then(() => { throw new Error("renderer not responding for 10 s"); })]);
        maxLag = Math.max(maxLag, Date.now() - t0); s.push(sample());
    }
    const dt = (s.at(-1).t - s[0].t) / 1000; const cpuPct = ((s.at(-1).cpu - s[0].cpu) / dt / cores) * 100;
    const maxWs = Math.max(...s.map((x) => x.wsMB)); const growth = s.at(-1).wsMB - s[1].wsMB;
    metrics[label] = { seconds: Math.round(dt), avgCpuPct: +cpuPct.toFixed(1), maxWorkingSetMB: maxWs, wsGrowthMB: growth, maxRendererLagMs: maxLag, samples: s };
    return metrics[label];
}

// After a 2nd login on an account with cross-signing Element shows "Confirm your identity" — a real user would
// verify or skip; the test skips (it only needs to send/receive in new E2EE rooms).
async function skipVerification(p) {
    for (let i = 0; i < 6; i++) {
        const skip = p.locator('button:has-text("Skip verification for now"), [role=button]:has-text("Skip verification for now"), button:has-text("Can\'t confirm?")').first();
        if (await skip.count().catch(() => 0)) {
            await skip.click().catch(() => {}); await sleep(1500);
            await p.locator('.mx_Dialog button:has-text("I\'ll verify later"), .mx_Dialog button:has-text("Skip"), button:has-text("I\'ll verify later")').first().click({ timeout: 3000 }).catch(() => {});
        }
        if (await p.locator(".mx_LeftPanel, .mx_RoomListPanel, .mx_SpacePanel").count().catch(() => 0)) return;
        await sleep(2000);
    }
}

// ------------------------------------------------------------------ MAS login (desktop)
async function desktopLogin(user) {
    await page.waitForSelector(".mx_Login_fullWidthButton, button:has-text('Continue')", { timeout: 90000 });
    let authUrl = "";
    page.on("request", (r) => { if (r.url().includes(`${HS}/auth/authorize`)) authUrl = r.url(); });
    // navigation to MAS is intercepted by Electron (opened in the system browser) → catch it on the CDP level
    const cdp = await page.context().newCDPSession(page); await cdp.send("Page.enable");
    cdp.on("Page.frameRequestedNavigation", (e) => { if (e.url.includes(`${HS}/auth/`)) authUrl = e.url; });
    await page.locator(".mx_Login_fullWidthButton, button:has-text('Continue')").first().waitFor({ state: "visible", timeout: 90000 });
    await sleep(2000);
    await page.evaluate(() => { window.__psstUrls = []; window.open = (u) => { window.__psstUrls.push(String(u)); return null; }; });
    await page.getByText(/^(Pokračovať|Continue)$/).first().evaluate((e) => e.click());
    for (let i = 0; i < 30 && !authUrl; i++) { authUrl = (await page.evaluate(() => window.__psstUrls[0] || "").catch(() => "")) || authUrl; if (!authUrl) await sleep(1000); }
    if (!authUrl) throw new Error("MAS URL not captured");
    const b2 = await chromium.launch(); const p2 = await (await b2.newContext()).newPage();
    let callback = "";
    p2.on("response", async (r) => { const loc = (await r.allHeaders().catch(() => ({})))["location"] || ""; if (/^(eu\.macet\.|psst:)/.test(loc)) callback = loc; });
    await p2.goto(authUrl);
    await p2.fill('input[name="username"]', user, { timeout: 30000 }); await p2.fill('input[name="password"]', ACC[user]);
    await p2.click("button[type=submit]");
    for (let i = 0; i < 20 && !callback; i++) { await p2.locator('button[type=submit]:has-text("Continue")').first().click({ timeout: 2000 }).catch(() => {}); await sleep(1500); }
    await b2.close();
    if (!callback) throw new Error("no OIDC callback");
    // same as protocol.ts handleDeeplink: vector://vector/webapp/ + search + hash
    const cb = new URL(callback); const target = new URL("vector://vector/webapp/"); target.search = cb.search; target.hash = cb.hash;
    await page.goto(target.href).catch(() => {}); await page.reload().catch(() => {});
    for (let i = 0; i < 90; i++) {
        if (await page.locator(".mx_LeftPanel, .mx_RoomListPanel, .mx_SpacePanel").count()) break;
        if (i % 5 === 4) await skipVerification(page);
        await sleep(1000);
    }
    await sleep(4000); for (let i = 0; i < 4; i++) await page.keyboard.press("Escape").catch(() => {});
    return await page.evaluate(() => window.mxMatrixClientPeg?.get()?.getUserId() ?? null);
}

// ------------------------------------------------------------------ partner (web)
const pb = await chromium.launch({ args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"] });
async function webLogin(user) {
    const ctx = await pb.newContext({ viewport: { width: 1280, height: 860 }, permissions: ["camera", "microphone", "notifications"] });
    const p = await ctx.newPage();
    await p.goto(`${WEB}/#/login`);
    await p.locator('.mx_Login_fullWidthButton, button:has-text("Continue")').first().click({ timeout: 90000 });
    await p.waitForURL(/chat\.macet\.eu\/auth/, { timeout: 60000 });
    await p.fill('input[name="username"]', user); await p.fill('input[name="password"]', ACC[user]);
    await p.locator("button[type=submit]").first().click();
    for (let i = 0; i < 20 && !p.url().startsWith(WEB); i++) { await p.locator('button[type=submit]:has-text("Continue")').first().click({ timeout: 1500 }).catch(() => {}); await sleep(1000); }
    for (let i = 0; i < 60; i++) {
        if (await p.locator(".mx_LeftPanel, .mx_RoomListPanel, .mx_SpacePanel").count()) break;
        if (i % 5 === 4) await skipVerification(p);
        await sleep(2000);
    }
    if (!(await p.locator(".mx_LeftPanel, .mx_RoomListPanel, .mx_SpacePanel").count())) {
        await p.screenshot({ path: path.join(OUT, `web-login-${user}-FAIL.png`) }).catch(() => {});
        throw new Error("web login did not reach the room list");
    }
    await sleep(5000); for (let i = 0; i < 4; i++) await p.keyboard.press("Escape").catch(() => {});
    return p;
}
const evalClient = (p, fn, arg) => p.evaluate(fn, arg);
async function waitDecrypted(p, roomId, body, timeout = 90000) {
    const t0 = Date.now();
    while (Date.now() - t0 < timeout) {
        const ok = await p.evaluate(([r, b]) => {
            const room = window.mxMatrixClientPeg.get().getRoom(r);
            return !!room && room.getLiveTimeline().getEvents().some((e) => (e.getClearContent?.() ?? e.getContent())?.body === b);
        }, [roomId, body]).catch(() => false);
        if (ok) return true; await sleep(1500);
    }
    return false;
}
async function openRoom(p, roomId) {
    await p.evaluate((r) => { location.hash = `#/room/${r}`; }, roomId);
    await p.waitForSelector(".mx_RoomView", { timeout: 60000 }); await sleep(2500);
    for (let i = 0; i < 2; i++) await p.keyboard.press("Escape").catch(() => {});
}
async function sendViaComposer(p, text) {
    const c = p.locator(".mx_BasicMessageComposer_input").first();
    await c.click(); await c.type(text); await p.keyboard.press("Enter");
}

// ================================================================== run
let uid = null, partner = null, dm = null, group = null;
await step("2.1 prihlásenie cez MAS", async () => {
    uid = await desktopLogin(U_DESK);
    check("2.1 prihlásenie cez MAS", uid === `@${U_DESK}:${HS}`, uid);
    await shot(page, "logged-in");
});
await step("1.3 stabilita 3 min po štarte", async () => {
    const m = await monitor("after_login_idle", 180);
    check("1.3 stabilita 3 min po prihlásení: nezamrzla, CPU a pamäť v norme",
        m.maxRendererLagMs < 5000 && m.avgCpuPct < 25 && m.maxWorkingSetMB < 1500 && sample().n > 0,
        `CPU ${m.avgCpuPct} %, max ${m.maxWorkingSetMB} MB (rast ${m.wsGrowthMB} MB), odozva max ${m.maxRendererLagMs} ms`);
});
await step("6.1 About: číslo buildu", async () => {
    await dismissPopovers(page);
    await page.locator('[aria-label="User menu"], .mx_UserMenu_userAvatar, .mx_UserMenu').first().click({ timeout: 15000 });
    await page.locator('[role=menuitem]:has-text("All settings"), [aria-label="All settings"]').first().click({ timeout: 15000 });
    await page.locator('[role=tab]:has-text("Help"), .mx_TabbedView_tabLabel:has-text("Help")').first().click({ timeout: 15000 });
    await sleep(2000); await shot(page, "about");
    const txt = (await page.locator(".mx_Dialog").innerText()).replace(/\s+/g, " ");
    const m = /-b(\d+) \((\d{4}-\d{2}-\d{2})\)/.exec(txt);
    check("6.1 About ukazuje číslo buildu a dátum", m && (!EXPECTED_BUILD || m[1] === String(EXPECTED_BUILD)), m ? `b${m[1]} ${m[2]}` : txt.slice(0, 200));
    await page.keyboard.press("Escape");
});
await step("3.x partner (web) prihlásený", async () => {
    partner = await webLogin(U_PART);
    check("partner prihlásený na webe", !!partner, U_PART);
});
await step("3.1 šifrovaná DM: príjem", async () => {
    dm = await evalClient(partner, async (who) => (await window.mxMatrixClientPeg.get().createRoom({
        preset: "trusted_private_chat", is_direct: true, invite: [who], name: "win e2e DM",
        initial_state: [{ type: "m.room.encryption", state_key: "", content: { algorithm: "m.megolm.v1.aes-sha2" } }],
    })).room_id, uid);
    await page.evaluate((r) => window.mxMatrixClientPeg.get().joinRoom(r), dm);
    // mark as a direct chat on both sides (as Element does when a DM is started from the UI) — Element sends a
    // ringing call notification ("ring") only in DMs, in other rooms just "notification"
    await evalClient(partner, ([r, other]) => window.mxMatrixClientPeg.get().setAccountData("m.direct", { [other]: [r] }), [dm, uid]);
    await page.evaluate(([r, other]) => window.mxMatrixClientPeg.get().setAccountData("m.direct", { [other]: [r] }), [dm, `@${U_PART}:${HS}`]);
    await sleep(6000);
    const t = "web→win " + Date.now();
    await evalClient(partner, ([r, b]) => window.mxMatrixClientPeg.get().sendTextMessage(r, b), [dm, t]);
    await openRoom(page, dm);
    const ok = await page.locator(`.mx_EventTile_body:has-text("${t}")`).first().waitFor({ timeout: 60000 }).then(() => true, () => false);
    const enc = await page.evaluate((r) => window.mxMatrixClientPeg.get().getCrypto().isEncryptionEnabledInRoom(r), dm);
    await shot(page, "dm-received");
    check("3.1 príjem šifrovanej správy (desktop dešifroval)", ok && enc, t);
});
await step("3.2 šifrovaná DM: odoslanie", async () => {
    const t = "win→web " + Date.now();
    await sendViaComposer(page, t);
    check("3.2 odoslanie šifrovanej správy (web dešifroval)", await waitDecrypted(partner, dm, t), t);
});
await step("3.3 súbor", async () => {
    const name = `psst-e2e-${Date.now()}.txt`;
    await page.locator('.mx_MessageComposer input[type=file], input[type=file]').first().setInputFiles({ name, mimeType: "text/plain", buffer: Buffer.from("psst windows e2e file\n") });
    await page.locator('.mx_Dialog button:has-text("Upload")').first().click({ timeout: 20000 });
    const ok = await waitDecrypted(partner, dm, name);
    const encFile = await evalClient(partner, ([r, n]) => window.mxMatrixClientPeg.get().getRoom(r).getLiveTimeline().getEvents()
        .some((e) => e.getContent()?.body === n && !!e.getContent()?.file), [dm, name]);
    await shot(page, "file");
    check("3.3 súbor odoslaný šifrovane a prijatý na webe", ok && encFile, name);
});
await step("3.4 skupina", async () => {
    group = await evalClient(partner, async (who) => (await window.mxMatrixClientPeg.get().createRoom({
        preset: "private_chat", invite: who, name: "win e2e group",
        initial_state: [{ type: "m.room.encryption", state_key: "", content: { algorithm: "m.megolm.v1.aes-sha2" } }],
    })).room_id, [uid, `@${U_THIRD}:${HS}`]);
    await page.evaluate((r) => window.mxMatrixClientPeg.get().joinRoom(r), group);
    // 3rd member joins over plain HTTP (only to make it a group of 3)
    const tok = (await (await fetch(`https://${HS}/_matrix/client/v3/login`, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "m.login.password", identifier: { type: "m.id.user", user: U_THIRD }, password: ACC[U_THIRD] }) })).json()).access_token;
    await fetch(`https://${HS}/_matrix/client/v3/join/${encodeURIComponent(group)}`, { method: "POST", headers: { Authorization: `Bearer ${tok}`, "Content-Type": "application/json" }, body: "{}" });
    await fetch(`https://${HS}/_matrix/client/v3/logout`, { method: "POST", headers: { Authorization: `Bearer ${tok}` } });
    await sleep(5000);
    await openRoom(page, group);
    const t = "group win " + Date.now();
    await sendViaComposer(page, t);
    const ok1 = await waitDecrypted(partner, group, t);
    const t2 = "group web " + Date.now();
    await evalClient(partner, ([r, b]) => window.mxMatrixClientPeg.get().sendTextMessage(r, b), [group, t2]);
    const ok2 = await page.locator(`.mx_EventTile_body:has-text("${t2}")`).first().waitFor({ timeout: 60000 }).then(() => true, () => false);
    const members = await page.evaluate((r) => window.mxMatrixClientPeg.get().getRoom(r).getJoinedMemberCount(), group);
    await shot(page, "group");
    check("3.4 skupina (3 členovia, šifrovaná): odoslanie aj príjem", ok1 && ok2 && members === 3, `členovia ${members}`);
});

// ------------------------------------------------------------------ Win32 helpers (real window actions, like a user)
const W32 = `Add-Type -Name W -Namespace P -MemberDefinition '[DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr h, int c); [DllImport("user32.dll")] public static extern bool IsIconic(System.IntPtr h); [DllImport("user32.dll")] public static extern bool IsWindowVisible(System.IntPtr h); [DllImport("user32.dll")] public static extern bool PostMessage(System.IntPtr h, uint m, System.IntPtr w, System.IntPtr l); [DllImport("user32.dll")] public static extern System.IntPtr FindWindow(string c, string t);'`;
let HWND = "";
function win32(cmd) {
    if (!HWND) HWND = ps(`(Get-Process psst | Where-Object MainWindowHandle -ne 0 | Select-Object -First 1).MainWindowHandle`);
    return ps(`${W32}; $h = [System.IntPtr]${HWND}; ${cmd}`);
}

// ------------------------------------------------------------------ notifications
async function dismissPopovers(p) {
    for (const name of ["Not now", "Dismiss", "Close"]) await p.getByRole("button", { name, exact: true }).first().click({ timeout: 1500 }).catch(() => {});
    for (let i = 0; i < 2; i++) await p.keyboard.press("Escape").catch(() => {});
}
async function hookNotifications() {
    await page.evaluate(() => {
        window.__psstNotes = window.__psstNotes || [];
        if (window.__psstHooked) return; window.__psstHooked = true;
        const N = window.Notification;
        window.__psstClosed = 0;
        window.Notification = function (title, opts) {
            window.__psstNotes.push({ title, body: opts?.body, t: Date.now() });
            const n = new N(title, opts); const c = n.close.bind(n); n.close = () => { window.__psstClosed++; c(); }; return n;
        };
        Object.assign(window.Notification, N); window.Notification.prototype = N.prototype;
        Object.defineProperty(window.Notification, "permission", { get: () => N.permission });
    });
}
const notes = () => page.evaluate(() => window.__psstNotes.length).catch(() => -1);
const toastHistory = () => { try { return ps(`[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime] > $null; $ids = Get-ChildItem 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings' | ForEach-Object { $_.PSChildName } | Where-Object { $_ -match 'psst|macet' }; $n=0; foreach ($id in $ids) { $n += [Windows.UI.Notifications.ToastNotificationManager]::History.GetHistory($id).Count }; "$($ids -join ',')|$n"`); } catch (e) { return "n/a"; } };
await step("4.0 notifikácie povolené", async () => {
    const enabled = await page.evaluate(() => window.mxSettingsStore?.getValue("notificationsEnabled"));
    metrics.notificationsEnabledByDefault = enabled;
    check("4.0 desktopové notifikácie sú zapnuté hneď po prihlásení", enabled === true, String(enabled));
    await hookNotifications();
    // leave the room view so messages in the DM are not "currently viewed"
    await page.evaluate(() => { location.hash = "#/home"; });
});
await step("4.1 notifikácia pri minimalizovanom okne", async () => {
    // Electron's CDP has no Browser.setWindowBounds → minimize the real window via Win32 ShowWindow(SW_MINIMIZE)
    win32("[void][P.W]::ShowWindow($h, 6)"); await sleep(2000);
    const minimized = win32("[P.W]::IsIconic($h)") === "True";
    const before = await notes(); const t = "notify-min " + Date.now();
    await evalClient(partner, ([r, b]) => window.mxMatrixClientPeg.get().sendTextMessage(r, b), [dm, t]);
    let after = before; for (let i = 0; i < 40 && after <= before; i++) { await sleep(500); after = await notes(); }
    metrics.toastHistoryAfterMinimize = toastHistory();   // right after the toast was raised
    await sleep(8000); metrics.notificationsClosedByApp = await page.evaluate(() => window.__psstClosed).catch(() => -1);
    check("4.1 systémová notifikácia pri minimalizovanom okne", minimized && after > before, `minimalizované ${minimized}, notifikácie ${before}→${after}; toast história ${metrics.toastHistoryAfterMinimize}`);
    win32("[void][P.W]::ShowWindow($h, 9)"); await sleep(1500);
});
await step("4.2 notifikácia pri okne zavretom do tray", async () => {
    // like clicking the window's X: WM_CLOSE (0x0010) → Element hides the window to the tray on Windows
    win32("[void][P.W]::PostMessage($h, 0x0010, [System.IntPtr]::Zero, [System.IntPtr]::Zero)");
    await sleep(4000);
    const alive = sample().n > 0;
    const hidden = alive && win32("[P.W]::IsWindowVisible($h)") === "False";
    metrics.closeToTray = { alive, hidden };
    const before = await notes(); const t = "notify-tray " + Date.now();
    await evalClient(partner, ([r, b]) => window.mxMatrixClientPeg.get().sendTextMessage(r, b), [dm, t]);
    let after = before; for (let i = 0; i < 40 && after <= before; i++) { await sleep(1500); after = await notes(); }
    metrics.toastHistoryAfterTray = toastHistory();
    check("4.2 okno zavreté (X) do tray: appka beží skrytá a notifikácia príde", alive && hidden && after > before, `beží ${alive}, skryté ${hidden}, notifikácie ${before}→${after}`);
    if (alive) { launch(); await sleep(6000); }   // second instance → shows the window again (like clicking the tray icon)
    else { proc = launch(); await sleep(15000); browser = await chromium.connectOverCDP("http://127.0.0.1:9333"); }
    page = await mainPage(); page.on("dialog", (d) => d.accept().catch(() => {}));
    check("4.3 okno sa po opätovnom spustení znova zobrazí", win32("[P.W]::IsWindowVisible($h)") === "True");
});

// ------------------------------------------------------------------ calls
async function partnerStartCall(roomId) {
    await openRoom(partner, roomId);
    await partner.locator('[aria-label="Video call"], [aria-label="Voice call"]').first().click({ timeout: 30000 });
    await sleep(2500);
    await partner.locator('[role=menuitem]:has-text("Element Call"), [role=menuitem]:has-text("psst")').first().click({ timeout: 2000 }).catch(() => {});
    for (let i = 0; i < 15; i++) {
        for (const f of partner.frames()) {
            const j = f.locator('[data-testid="lobby_joinCall"], button:has-text("Join call")');
            if (await j.count().catch(() => 0)) { await j.first().click().catch(() => {}); return; }
        }
        await sleep(1500);
    }
}
async function desktopJoinFromToast(label) {
    const toast = page.locator('.mx_IncomingCallToast, .mx_Toast_toast:has-text("call"), .mx_Toast_toast:has-text("Call")').first();
    const seen = await toast.waitFor({ timeout: 60000 }).then(() => true, () => false);
    await shot(page, `${label}-incoming`);
    metrics[`${label}_toast`] = (await toast.innerText().catch(() => "")).replace(/\s+/g, " ").slice(0, 200);
    metrics[`${label}_audio`] = await page.evaluate(() => {
        const a = document.getElementById("ringAudio");
        return { exists: !!a, paused: a?.paused, src: a?.currentSrc?.slice(-40), muted: a?.muted, t: a?.currentTime,
            audioNotif: window.mxSettingsStore?.getValue("audioNotificationsEnabled") };
    }).catch((e) => String(e));
    let ringing = false;
    for (let i = 0; i < 10 && !ringing; i++) {
        // Element plays the ringtone via WebAudio (LegacyCallHandler.play(AudioID.Ring)), not an <audio> element
        ringing = await page.evaluate(() => !!window.mxSdkContext?.legacyCallHandler?.isPlaying("ringAudio")).catch(() => false);
        if (!ringing) await sleep(500);
    }
    if (!seen) return { seen, ringing, joined: false };
    await toast.locator('button:has-text("Join"), button:has-text("Accept"), [aria-label="Join"]').first().click({ timeout: 10000 });
    let joined = false;
    for (let i = 0; i < 40 && !joined; i++) {
        for (const f of page.frames()) {
            const j = f.locator('[data-testid="lobby_joinCall"], button:has-text("Join call")');
            if (await j.count().catch(() => 0)) await j.first().click().catch(() => {});
            if (await f.locator('[data-testid="incall_leave"], button[aria-label="End call"], button:has-text("Leave")').count().catch(() => 0)) joined = true;
        }
        if (!joined) await sleep(1500);
    }
    await sleep(5000); await shot(page, `${label}-in-call`);
    return { seen, ringing, joined };
}
async function hangUpAll() {
    for (const p of [page, partner]) for (const f of p.frames()) await f.locator('[data-testid="incall_leave"], button[aria-label="End call"]').first().click({ timeout: 2000 }).catch(() => {});
    await sleep(5000);
}
await step("5.1 hovor 1:1", async () => {
    await page.evaluate(() => { location.hash = "#/home"; });
    await partnerStartCall(dm);
    const r = await desktopJoinFromToast("call-1to1");
    check("5.1 prichádzajúci hovor 1:1: zvonenie + oznámenie, prijatie, okno hovoru", r.seen && r.ringing && r.joined, `toast ${r.seen}, zvonenie ${r.ringing}, v hovore ${r.joined}`);
    metrics.call1to1 = r; await hangUpAll();
});
await step("5.2 skupinový hovor", async () => {
    await page.evaluate(() => { location.hash = "#/home"; });
    await partnerStartCall(group);
    const r = await desktopJoinFromToast("call-group");
    check("5.2 skupinový hovor: oznámenie + pripojenie", r.seen && r.joined, `toast ${r.seen}, v hovore ${r.joined}`);
    metrics.callGroup = r; await hangUpAll();
});

// ------------------------------------------------------------------ logout / login again
await step("2.2 odhlásenie", async () => {
    await page.evaluate(() => { location.hash = "#/home"; });
    await sleep(2000); await dismissPopovers(page);
    await shot(page, "before-logout");
    await page.locator('[aria-label="User menu"]').first().click({ timeout: 15000 });
    await sleep(1500); await shot(page, "user-menu");
    // Element 1.12: "Sign out" is in Settings → Account (the user menu has only Link new device / Security / All settings)
    await page.locator('[role=menuitem]:has-text("All settings")').first().click({ timeout: 15000 });
    await sleep(1500);
    await page.getByRole("tab", { name: "Account" }).first().click({ timeout: 15000 }).catch(() => {});
    await sleep(2000); await shot(page, "settings-account");
    await page.getByRole("button", { name: "Sign out", exact: true }).first().click({ timeout: 15000 });
    for (let i = 0; i < 3; i++) await page.locator('.mx_Dialog button:has-text("Sign out"), .mx_Dialog button:has-text("I don\'t want my encrypted messages")').first().click({ timeout: 4000 }).catch(() => {});
    const out = await page.waitForSelector(".mx_Login_fullWidthButton, .mx_AuthPage, .mx_Welcome", { timeout: 60000 }).then(() => true, () => false);
    await shot(page, "logged-out");
    check("2.2 odhlásenie", out);
});
await step("2.3 opätovné prihlásenie", async () => {
    const u = await desktopLogin(U_DESK);
    check("2.3 opätovné prihlásenie", u === `@${U_DESK}:${HS}`, u);
});
await step("6.2 kontrola novej verzie mieri na app.macet.eu", async () => {
    const m = /psst update check: installed b(\d+), available b(\d+)/.exec(appLog);
    const element = /packages\.element\.io|update_base_url.*element/i.test(appLog);
    check("6.2 aktualizácie: Element updater vypnutý, kontrola cez app.macet.eu/download", !element && !!m, m ? m[0] : "log: " + (appLog.match(/update[^\n]{0,120}/gi) || []).slice(0, 3).join(" | "));
});
await step("1.4 stabilita na konci", async () => {
    const m = await monitor("end", 60);
    check("1.4 na konci testu: bez zamrznutia, pamäť bez úniku", m.maxRendererLagMs < 5000 && m.maxWorkingSetMB < 1500, `CPU ${m.avgCpuPct} %, max ${m.maxWorkingSetMB} MB`);
});

fs.writeFileSync(path.join(OUT, "app.log"), appLog);
fs.writeFileSync(path.join(OUT, "result.json"), JSON.stringify({ res, metrics }, null, 2));
await pb.close().catch(() => {}); await browser?.close().catch(() => {});
try { ps("Get-Process psst -ErrorAction SilentlyContinue | Stop-Process -Force"); } catch {}
const fails = res.filter((r) => !r.ok).length;
console.log(`\n${res.length - fails}/${res.length} checks passed`);
process.exit(fails ? 1 : 0);
