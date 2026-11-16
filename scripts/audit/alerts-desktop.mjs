// PSST (D75): Settings → "Notifications & calls" in the installed desktop app (Windows MSI / macOS DMG), over CDP.
//   node alerts-desktop.mjs <app-binary> <out-dir> <account.json {user,password}> <platform: windows|macos>
// Run by the "Desktop audit" workflow with suite=alerts. Records every row's state as read from the OS, the raw IPC
// status, Do not disturb, the two test buttons, and checks that real changes (Windows registry, Element settings,
// login item / tray) show up in the switches.
import { chromium } from "playwright";
import { spawn, execSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
    ALERT_HOOK, sleep, openAlertsTab, closeDialog, readRows, row, refocus, clickToggle, waitRow, testNotification, testRinging,
} from "./alerts-check.mjs";

const [BIN, OUT, ACC_FILE, PLATFORM] = process.argv.slice(2);
fs.mkdirSync(OUT, { recursive: true });
const A = JSON.parse(fs.readFileSync(ACC_FILE, "utf8"));
const HS = "chat.macet.eu";
const results = [];
const record = (id, status, note = "") => {
    results.push({ id, status, note: typeof note === "string" ? note.slice(0, 800) : note });
    console.log(`${status.toUpperCase().padEnd(6)} ${id}  ${typeof note === "string" ? note.slice(0, 400) : JSON.stringify(note).slice(0, 400)}`);
};
const shot = (p, n) => p.screenshot({ path: path.join(OUT, `${PLATFORM}-alerts-${n}.png`) }).catch(() => {});
const brief = (rows) => rows.map((r) => `${r.id}=${r.on ?? r.state}:${r.code}${r.disabled ? "(fixed)" : ""}`).join(" ");
const write = () => {
    fs.writeFileSync(path.join(OUT, `${PLATFORM}-alerts-result.json`), JSON.stringify(results, null, 2));
    const md = [`### ${PLATFORM}: Notifications & calls`, "", "| test | status | note |", "|---|---|---|",
        ...results.map((r) => `| ${r.id} | ${r.status} | ${String(typeof r.note === "string" ? r.note : JSON.stringify(r.note)).replace(/\|/g, "/").replace(/\n/g, " ").slice(0, 400)} |`)];
    fs.writeFileSync(path.join(OUT, `${PLATFORM}-alerts-result.md`), md.join("\n") + "\n");
};
const sh = (cmd) => { try { return execSync(cmd, { stdio: "pipe", timeout: 30000 }).toString(); } catch (e) { return `ERR ${String(e.message).split("\n")[0]}`; } };

// ---------------------------------------------------------------- launch + MAS login (as in desktop-audit.mjs)
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "psst-alerts-"));
let appLog = "";
const proc = spawn(BIN, ["--remote-debugging-port=9334", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required", `--profile-dir=${profile}`],
    { stdio: ["ignore", "pipe", "pipe"] });
proc.stdout.on("data", (d) => (appLog += d)); proc.stderr.on("data", (d) => (appLog += d));
let cdp;
for (let i = 0; i < 90 && !cdp; i++) { try { cdp = await chromium.connectOverCDP("http://127.0.0.1:9334"); } catch { await sleep(1000); } }
if (!cdp) { record("launch", "fail", "app did not start (CDP)"); write(); process.exit(1); }
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
await me.context().addInitScript(ALERT_HOOK).catch(() => {});
await me.waitForSelector(".mx_Login_fullWidthButton, .mx_AuthPage", { timeout: 120000 });
await sleep(3000);

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
        if (await me.locator(".mx_LeftPanel, .mx_RoomListPanel").count()) return "app";
        await sleep(1000);
    }
    throw new Error("desktop login: app view not reached");
}

try {
    record("login", (await desktopLogin(A.user, A.password)) === "app" ? "ok" : "fail", "MAS login");
} catch (e) { record("login", "fail", String(e.message).slice(0, 200)); write(); process.exit(1); }
await me.evaluate(ALERT_HOOK).catch(() => {});
const version = await me.evaluate(async () => window.mxPlatformPeg.get().getAppVersion());
record("version", "info", version);

// raw OS status straight from the main process (what the switches are built from)
const raw = await me.evaluate(async () => window.electron.psstAlerts("status", "fresh")).catch((e) => ({ error: String(e) }));
record("ipc_status", raw?.error ? "fail" : "info", JSON.stringify(raw));
fs.writeFileSync(path.join(OUT, `${PLATFORM}-alerts-ipc.json`), JSON.stringify(raw, null, 2));

// ---------------------------------------------------------------- 1. automatic opening on the first run
let auto = false;
for (let i = 0; i < 60 && !auto; i++) { auto = (await me.locator("[data-psst-row]").count()) > 0; if (!auto) await sleep(1000); }
const notifRequired = raw?.notifications && ["denied", "not-determined"].includes(raw.notifications.state);
record("auto_open_first_run", auto === !!notifRequired ? "ok" : "fail",
    `opened=${auto}; OS notifications ${raw?.notifications?.state}/${raw?.notifications?.detail} → ${notifRequired ? "required row missing, must open" : "nothing required missing, must stay closed"}`);
if (auto) await shot(me, "01-auto-open");
const how = await openAlertsTab(me);
await sleep(2000);
let rows = await readRows(me);
fs.writeFileSync(path.join(OUT, `${PLATFORM}-alerts-rows.json`), JSON.stringify(rows, null, 2));
await shot(me, "02-screen");
record("rows", "info", `${how}: ${brief(rows)}`);
for (const r of rows) record(`row_${r.id}`, "info", `${r.label ?? ""} | on=${r.on ?? r.state} code=${r.code} | ${r.text}`);

// rows match the OS status
const n = row(rows, "notifications");
const osOk = raw?.notifications?.state === "granted" || raw?.notifications?.state === "unknown";
record("notif_matches_os", (n.on === "true") === (osOk && n.code !== "psst_off" && n.code !== "account_off" && n.code !== "silenced") ? "ok" : "fail",
    `OS ${raw?.notifications?.state} → switch ${n.on} (${n.code})`);
for (const kind of ["microphone", "camera"]) {
    const r = row(rows, kind);
    const expect = raw?.[kind] === "granted";
    record(`${kind}_matches_os`, raw?.[kind] === "unknown" || (r.on === "true") === expect ? "ok" : "fail", `OS ${raw?.[kind]} → switch ${r.on} (${r.code})`);
}
const dnd = row(rows, "dnd");
record("dnd_row", dnd ? "ok" : "fail", `${dnd?.state}/${dnd?.code}: ${dnd?.text}`);

// ---------------------------------------------------------------- 2. test buttons
const tn = await testNotification(me);
record("test_notification", (n.on === "true" ? tn.notes.length === 1 : tn.notes.length === 0) ? "ok" : "fail", JSON.stringify(tn));
const tr = await testRinging(me);
record("test_ringing", tr.playing && tr.ended && tr.ringStarted && tr.ringDurationMs >= 4500 && tr.ringDurationMs <= 7000 ? "ok" : "fail",
    `playing=${tr.playing} ended=${tr.ended} ring ${tr.ringDurationMs} ms`);

// ---------------------------------------------------------------- 3. real changes show up
if (PLATFORM === "windows") {
    // raw Do-not-disturb signals next to what the app concluded (WNF quiet-hours profile, SHQueryUserNotificationState)
    const ps = `Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class D { [DllImport("ntdll.dll")] static extern int NtQueryWnfStateData(ref ulong n, IntPtr t, IntPtr s, out uint c, byte[] b, ref uint z); [DllImport("shell32.dll")] static extern int SHQueryUserNotificationState(out int q); public static string Q() { ulong n = 0x0D83063EA3BF1C75UL; uint c; byte[] b = new byte[4]; uint z = 4; int st = NtQueryWnfStateData(ref n, IntPtr.Zero, IntPtr.Zero, out c, b, ref z); int q; SHQueryUserNotificationState(out q); return "wnf_status=" + st + " size=" + z + " value=" + BitConverter.ToInt32(b, 0) + " quns=" + q; } }'; [D]::Q()`;
    const diag = sh(`powershell -NoProfile -EncodedCommand ${Buffer.from(ps, "utf16le").toString("base64")}`).trim();
    const regs = sh('reg query "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings"').replace(/\s+/g, " ").slice(0, 400);
    record("win_dnd_raw", "info", `${diag} | ${regs} | edition ${sh("powershell -NoProfile -Command (Get-CimInstance Win32_OperatingSystem).Caption").trim()}`);
    const key = "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings\\eu.macet.psst";
    const before = sh(`reg query "${key}" /v Enabled`);
    sh(`reg add "${key}" /v Enabled /t REG_DWORD /d 0 /f`);
    rows = await refocus(me, 4000);
    const blocked = row(rows, "notifications");
    record("win_app_notifications_off", blocked.on === "false" && blocked.code === "os_denied_app" ? "ok" : "fail", `${blocked.code}: ${blocked.text}`);
    await shot(me, "03-win-blocked");
    if (/REG_DWORD\s+0x0\b/.test(before)) sh(`reg add "${key}" /v Enabled /t REG_DWORD /d 0 /f`);
    else if (/REG_DWORD/.test(before)) sh(`reg add "${key}" /v Enabled /t REG_DWORD /d 1 /f`);
    else sh(`reg delete "${key}" /v Enabled /f`);
    const gkey = "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\PushNotifications";
    const gbefore = sh(`reg query "${gkey}" /v ToastEnabled`);
    sh(`reg add "${gkey}" /v ToastEnabled /t REG_DWORD /d 0 /f`);
    rows = await refocus(me, 4000);
    record("win_all_notifications_off", row(rows, "notifications").code === "os_denied_system" ? "ok" : "fail", row(rows, "notifications").text);
    if (/REG_DWORD/.test(gbefore)) sh(`reg add "${gkey}" /v ToastEnabled /t REG_DWORD /d ${/0x0\b/.test(gbefore) ? 0 : 1} /f`);
    else sh(`reg delete "${gkey}" /v ToastEnabled /f`);
    rows = await refocus(me, 4000);
    record("win_restored", row(rows, "notifications").on === n.on ? "ok" : "fail", row(rows, "notifications").code);
}

// turning a switch on asks the OS / opens exactly the right system screen
if (PLATFORM === "macos" && row(rows, "notifications").code === "os_not_determined") {
    const before = await me.evaluate(() => (window.__psstAlertNotes || []).length);
    await clickToggle(me, "notifications", 8000);
    rows = await refocus(me, 3000);
    const after = await me.evaluate(() => (window.__psstAlertNotes || []).slice(-1));
    const st = await me.evaluate(async () => window.electron.psstAlerts("status", "fresh"));
    record("mac_notifications_request", "info",
        `click → notification shown ${JSON.stringify(after)} (count +${(await me.evaluate(() => (window.__psstAlertNotes || []).length)) - before}); OS now ${st.notifications.state}/${st.notifications.detail}; switch ${row(rows, "notifications").on} (${row(rows, "notifications").code})`);
    await shot(me, "03-mac-after-request");
}
{
    const mic = row(rows, "microphone");
    const proc = PLATFORM === "windows" ? 'tasklist /FI "IMAGENAME eq SystemSettings.exe"' : "pgrep -lf 'System Settings|System Preferences'";
    const before = sh(proc);
    await clickToggle(me, "microphone", 6000);
    rows = await readRows(me);
    const after = sh(proc);
    const opened = PLATFORM === "windows" ? /SystemSettings\.exe/i.test(after) : /System (Settings|Preferences)/.test(after);
    record("microphone_opens_settings", row(rows, "microphone").hint && opened ? "ok" : "fail",
        `${mic.on === "true" ? "on→off" : "off→on"} (${mic.code}): hint "${row(rows, "microphone").hint}", settings app running before ${PLATFORM === "windows" ? /SystemSettings/i.test(before) : /System/.test(before)} / after ${opened}`);
    if (PLATFORM === "windows") sh("taskkill /IM SystemSettings.exe /F");
    else sh(`osascript -e 'quit app "System Settings"'`);
    await sleep(1000);
}

// psst's own switches: message sound, ringing (push rule), tray, start at login
for (const id of ["sound", "ringing"]) {
    const start = row(rows, id).on;
    await clickToggle(me, id, 1000);
    const flipped = await waitRow(me, id, start !== "true");
    await clickToggle(me, id, 1000);
    const back = await waitRow(me, id, start === "true");
    record(`${id}_switch`, row(flipped, id).on !== start && row(back, id).on === start ? "ok" : "fail", `${start} → ${row(flipped, id).on} → ${row(back, id).on}`);
}
const tray = row(rows, "tray");
if (PLATFORM === "macos") {
    record("tray_mac", tray && tray.on === "true" && tray.disabled ? "ok" : "fail", tray?.text ?? "missing");
} else if (tray) {
    const start = tray.on;
    await clickToggle(me, "tray", 1500);
    const flipped = await waitRow(me, "tray", start !== "true");
    const real = await me.evaluate(async () => window.mxPlatformPeg.get().getSettingValue("Electron.showTrayIcon"));
    await clickToggle(me, "tray", 1500);
    const back = await waitRow(me, "tray", start === "true");
    record("tray_switch", row(flipped, "tray").on !== start && String(real) === row(flipped, "tray").on && row(back, "tray").on === start ? "ok" : "fail",
        `${start} → ${row(flipped, "tray").on} (tray.hasTray=${real}) → ${row(back, "tray").on}`);
}
const al = row(rows, "autolaunch");
if (al) {
    const start = al.on;
    const probe = () => PLATFORM === "windows"
        ? sh(`reg query "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"`)
        : sh(`ls ~/Library/LaunchAgents/`);
    await clickToggle(me, "autolaunch", 2500);
    const flipped = await waitRow(me, "autolaunch", start !== "true");
    const seenOn = probe();
    await clickToggle(me, "autolaunch", 2500);
    const back = await waitRow(me, "autolaunch", start === "true");
    const seenOff = probe();
    record("autolaunch_switch", row(flipped, "autolaunch").on !== start && row(back, "autolaunch").on === start ? "ok" : "fail",
        `${start} → ${row(flipped, "autolaunch").on} → ${row(back, "autolaunch").on}; system while on: ${/psst/i.test(seenOn)} / after: ${/psst/i.test(seenOff)}`);
}

// ---------------------------------------------------------------- 4. no second automatic opening for the same version
await closeDialog(me);
await me.reload();
await me.locator(".mx_LeftPanel, .mx_RoomListPanel").first().waitFor({ timeout: 90000 });
let again = false;
for (let i = 0; i < 20 && !again; i++) { again = (await me.locator("[data-psst-row]").count()) > 0; if (!again) await sleep(1000); }
record("no_nag_same_version", !again ? "ok" : "fail", `after reload opened=${again}; remembered ${await me.evaluate(() => localStorage.getItem("psst_alerts_auto_version"))}`);

// ---------------------------------------------------------------- 5. Slovak
await me.evaluate(() => window.mxSettingsStore.setValue("language", null, "device", "sk"));
await me.reload();
await me.locator(".mx_LeftPanel, .mx_RoomListPanel").first().waitFor({ timeout: 90000 });
await sleep(3000);
await openAlertsTab(me);
await sleep(2000);
rows = await readRows(me);
fs.writeFileSync(path.join(OUT, `${PLATFORM}-alerts-rows-sk.json`), JSON.stringify(rows, null, 2));
record("slovak", rows.some((r) => /Mikrofón/.test(r.label ?? "")) ? "ok" : "fail", rows.map((r) => `${r.label ?? r.id}: ${r.text}`).join(" · "));
await shot(me, "04-slovak");

fs.writeFileSync(path.join(OUT, `${PLATFORM}-alerts-app.log`), appLog);
write();
await cdp.close().catch(() => {});
try { proc.kill(); } catch { /* ignore */ }
console.log(`\n${results.filter((r) => r.status === "ok").length} ok, ${results.filter((r) => r.status === "fail").length} fail`);
process.exit(0);
