// PSST (D75): Playwright test of Settings → "Notifications & calls" on the web, against production chat.macet.eu.
//   node alerts-web.mjs <out-dir> <user> <password> [<local webapp dir>]
// With a local webapp dir, https://app.macet.eu/* is served from that directory (same origin, so MAS login works).
// Uses a fresh test account. Permissions are driven through the browser (grant / CDP deny), never faked in the page.
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import {
    ALERT_HOOK, sleep, openAlertsTab, closeDialog, readRows, row, refocus, clickToggle, waitRow, testNotification, testRinging,
} from "./alerts-check.mjs";

const [OUT, USER, PASSWORD, LOCAL] = process.argv.slice(2);
fs.mkdirSync(OUT, { recursive: true });
const WEB = "https://app.macet.eu";
const results = [];
const record = (id, status, note = "") => {
    results.push({ id, status, note: typeof note === "string" ? note.slice(0, 600) : note });
    console.log(`${status.toUpperCase().padEnd(6)} ${id}  ${typeof note === "string" ? note.slice(0, 300) : JSON.stringify(note).slice(0, 300)}`);
};
const shot = (p, n) => p.screenshot({ path: path.join(OUT, `web-${n}.png`) }).catch(() => {});
const brief = (rows) => rows.map((r) => `${r.id}=${r.on ?? r.state}:${r.code}`).join(" ");

// new headless ("chromium" channel) behaves like a desktop browser for Notification.permission
const browser = await chromium.launch({ channel: "chromium", args: ["--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required"] });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: "en-US", serviceWorkers: "block" });
await ctx.addInitScript(ALERT_HOOK);
if (LOCAL) {
    const root = path.resolve(LOCAL);
    await ctx.route((url) => url.origin === WEB, async (route) => {
        const u = new URL(route.request().url());
        let rel = decodeURIComponent(u.pathname).replace(/^\/+/, "");
        if (rel === "") rel = "index.html";
        const file = path.join(root, rel);
        if (file.startsWith(root) && fs.existsSync(file) && fs.statSync(file).isFile()) {
            return route.fulfill({ path: file, headers: { "cache-control": "no-store" } });
        }
        return route.continue();
    });
}
const p = await ctx.newPage();
p.on("dialog", (d) => d.accept().catch(() => {}));
// Browser.setPermission must name Playwright's browser context, otherwise it changes the default context only
const { targetInfo } = await (await ctx.newCDPSession(p)).send("Target.getTargetInfo");
const bcdp = await browser.newBrowserCDPSession();
const setPerm = (name, setting) =>
    bcdp.send("Browser.setPermission", { permission: { name }, setting, origin: WEB, browserContextId: targetInfo.browserContextId });
async function waitApp(label) {
    for (let i = 0; i < 90; i++) {
        if (await p.locator(".mx_LeftPanel, .mx_RoomListPanel").count()) return true;
        await sleep(1000);
    }
    await shot(p, `stuck-${label}`);
    record(`stuck_${label}`, "fail", (await p.locator("body").innerText().catch(() => "")).replace(/\s+/g, " ").slice(0, 300));
    return false;
}

// ---------------------------------------------------------------- login (no permission granted yet)
await p.goto(`${WEB}/#/login`);
await p.locator('.mx_Login_fullWidthButton, button:has-text("Continue")').first().click({ timeout: 90000 });
await p.waitForURL(/chat\.macet\.eu\/auth/, { timeout: 60000 });
await p.fill('input[name="username"]', USER);
await p.fill('input[name="password"]', PASSWORD);
await p.locator("button[type=submit]").first().click();
for (let i = 0; i < 20 && !p.url().startsWith(WEB); i++) {
    await p.locator('button[type=submit]:has-text("Continue")').first().click({ timeout: 1500 }).catch(() => {});
    await sleep(1000);
}
// the OIDC callback arrives as a redirect, which Playwright routes don't intercept → load the app once more (local build)
if (LOCAL) {
    for (let i = 0; i < 60 && !(await p.evaluate(() => Object.keys(localStorage).some((k) => k.startsWith("mx_access_token") || k === "mx_user_id")).catch(() => false)); i++) await sleep(1000);
    await p.goto(`${WEB}/#/home`);
}
const version = await p.evaluate(async () => {
    for (let i = 0; i < 60 && !window.mxPlatformPeg?.get(); i++) await new Promise((r) => setTimeout(r, 500));
    return window.mxPlatformPeg.get().getAppVersion();
});
record("version", "info", version);
await sleep(5000);
const perm0 = await p.evaluate(() => window.Notification?.permission);
record("initial_permission", "info", `Notification.permission=${perm0}`);

// ---------------------------------------------------------------- 1. opens automatically on first run
let auto = false;
for (let i = 0; i < 90 && !auto; i++) {
    auto = (await p.locator("[data-psst-row]").count()) > 0;
    if (!auto) await sleep(1000);
}
await sleep(1500);
let rows = auto ? await readRows(p) : [];
const banner = await p.locator("[data-psst-missing]").getAttribute("data-psst-missing").catch(() => null);
record("auto_open_first_run", auto ? "ok" : "fail", auto ? `opened by itself, highlighted: ${banner} | ${brief(rows)}` : "screen did not open");
await shot(p, "01-auto-open");
if (!auto) await openAlertsTab(p);
rows = await readRows(p);
fs.writeFileSync(path.join(OUT, "web-rows-initial.json"), JSON.stringify(rows, null, 2));

// ---------------------------------------------------------------- 2. toggle notifications while the browser has not decided
const n0 = row(rows, "notifications");
record("notif_initial", n0 && n0.on === "false" && ["web_prompt", "web_denied"].includes(n0.code) ? "ok" : "fail", `${n0?.code}: ${n0?.text}`);
rows = await clickToggle(p, "notifications", 4000);
const n1 = row(rows, "notifications");
record("notif_toggle_no_grant", n1.on === "false" ? "ok" : "fail", `after click without grant: on=${n1.on} code=${n1.code} hint=${n1.hint}`);

// ---------------------------------------------------------------- 3. grant in the browser → re-read on focus
await ctx.grantPermissions(["notifications", "microphone", "camera"], { origin: WEB });
rows = await refocus(p, 3000);
const g = Object.fromEntries(["notifications", "microphone", "camera"].map((id) => [id, row(rows, id)]));
record("granted_reflected", g.notifications.on === "true" && g.microphone.on === "true" && g.camera.on === "true" ? "ok" : "fail", brief(rows));
await shot(p, "02-granted");

// psst's own per-device switch: turning notifications off/on changes the real Element setting
rows = await clickToggle(p, "notifications", 2500);
const off = row(rows, "notifications");
const settingOff = await p.evaluate(() => window.mxSettingsStore.getValue("notificationsEnabled"));
rows = await clickToggle(p, "notifications", 2500);
const on = row(rows, "notifications");
const settingOn = await p.evaluate(() => window.mxSettingsStore.getValue("notificationsEnabled"));
record("notif_psst_switch", off.on === "false" && off.code === "psst_off" && settingOff === false && on.on === "true" && settingOn === true ? "ok" : "fail",
    `off→ ${off.code}/${settingOff}, on→ ${on.code}/${settingOn}`);

// ---------------------------------------------------------------- 4. test notification + ringing
const tn = await testNotification(p);
record("test_notification", tn.notes.length === 1 && tn.notes[0].title === "psst" ? "ok" : "fail", JSON.stringify(tn));
const tr = await testRinging(p);
record("test_ringing", tr.playing && tr.ended && tr.ringStarted && tr.ringDurationMs >= 4500 && tr.ringDurationMs <= 7000 ? "ok" : "fail",
    `playing=${tr.playing} ended=${tr.ended} ring loop buffer ${tr.ringDurationMs} ms`);
const ts = await testRinging(p, { stopAfterMs: 1200 });
record("test_ringing_stop", ts.ringStarted && ts.ringDurationMs !== null && ts.ringDurationMs < 3000 ? "ok" : "fail", `stopped after ${ts.ringDurationMs} ms`);

// ---------------------------------------------------------------- 5. sound + ringing map to the real settings / push rule
rows = await clickToggle(p, "sound", 2000);
const soundOff = await p.evaluate(() => window.mxSettingsStore.getValue("audioNotificationsEnabled"));
const sOff = row(rows, "sound");
rows = await clickToggle(p, "sound", 2000);
const soundOn = await p.evaluate(() => window.mxSettingsStore.getValue("audioNotificationsEnabled"));
record("sound_switch", sOff.on === "false" && soundOff === false && row(rows, "sound").on === "true" && soundOn === true ? "ok" : "fail",
    `audioNotificationsEnabled off=${soundOff} on=${soundOn}`);
const rule = () => p.evaluate(() => {
    const r = window.mxMatrixClientPeg.get().pushProcessor.getPushRuleById(".m.rule.call");
    return r ? { enabled: r.enabled, actions: r.actions } : null;
});
rows = await clickToggle(p, "ringing", 1000);
rows = await waitRow(p, "ringing", false);
const ruleOff = await rule();
rows = await clickToggle(p, "ringing", 1000);
rows = await waitRow(p, "ringing", true);
const ruleOn = await rule();
record("ringing_switch", row(rows, "ringing").on === "true" && JSON.stringify(ruleOn).includes('"ring"') && !JSON.stringify(ruleOff).includes('"ring"') ? "ok" : "fail",
    `.m.rule.call off=${JSON.stringify(ruleOff)} on=${JSON.stringify(ruleOn)}`);

// ---------------------------------------------------------------- 6. denied in the browser → explanation, no fake "on"
await setPerm("notifications", "denied");
await setPerm("microphone", "denied");
rows = await refocus(p, 3000);
const dn = row(rows, "notifications"), dm = row(rows, "microphone");
record("denied_reflected", dn.on === "false" && dn.code === "web_denied" && dm.on === "false" && dm.code === "web_denied" ? "ok" : "fail",
    `notifications: ${dn.text} | microphone: ${dm.text}`);
rows = await clickToggle(p, "microphone", 2500);
record("denied_toggle_hint", row(rows, "microphone").on === "false" && row(rows, "microphone").hint ? "ok" : "fail", `hint: ${row(rows, "microphone").hint}`);
await shot(p, "03-denied");
const blocked = await testNotification(p);
record("test_notification_blocked", blocked.notes.length === 0 && blocked.result ? "ok" : "fail", blocked.result ?? "");

// ---------------------------------------------------------------- 7. back to "ask" → turning on requests one after another
await setPerm("notifications", "granted");
await setPerm("microphone", "prompt");
await setPerm("camera", "prompt");
rows = await refocus(p, 2500);
record("prompt_reflected", row(rows, "microphone").code === "web_prompt" && row(rows, "camera").code === "web_prompt" ? "ok" : "fail", brief(rows));
// the user grants when asked (auto-accept the next prompts), clicks both switches quickly
await ctx.grantPermissions(["notifications", "microphone", "camera"], { origin: WEB });
await p.locator('[data-psst-row="microphone"] input[type=checkbox]').click({ force: true });
await p.locator('[data-psst-row="camera"] input[type=checkbox]').click({ force: true });
rows = await waitRow(p, "camera", true, 15000);
const media = await p.evaluate(async () => {
    const d = await navigator.mediaDevices.enumerateDevices();
    return d.filter((x) => x.kind === "audioinput" || x.kind === "videoinput").length;
});
record("media_sequential", row(rows, "microphone").on === "true" && row(rows, "camera").on === "true" ? "ok" : "fail", `${brief(rows)}; devices ${media}`);

// ---------------------------------------------------------------- 8. no second automatic opening within the same version
await closeDialog(p);
await p.reload();
await waitApp("reload");
let again = false;
for (let i = 0; i < 25 && !again; i++) { again = (await p.locator("[data-psst-row]").count()) > 0; if (!again) await sleep(1000); }
const seen = await p.evaluate(() => localStorage.getItem("psst_alerts_auto_version"));
record("no_nag_same_version", !again && seen === version ? "ok" : "fail", `after reload: opened=${again}, remembered version ${seen} (app ${version})`);

// ---------------------------------------------------------------- 9. Slovak
await p.evaluate(() => window.mxSettingsStore.setValue("language", null, "device", "sk"));
await p.reload();
await waitApp("slovak");
await sleep(3000);
await openAlertsTab(p);
await sleep(1500);
rows = await readRows(p);
const title = await p.locator(".mx_UserSettingsDialog_title, .mx_Dialog_title").first().textContent().catch(() => "");
record("slovak", /Upozornenia a hovory/.test(title) && rows.some((r) => /Mikrofón/.test(r.label ?? "")) ? "ok" : "fail", `${title} | ${rows.map((r) => r.label).join(" · ")}`);
fs.writeFileSync(path.join(OUT, "web-rows-sk.json"), JSON.stringify(rows, null, 2));
await shot(p, "04-slovak");
await p.evaluate(() => window.mxSettingsStore.setValue("language", null, "device", "en"));

fs.writeFileSync(path.join(OUT, "web-result.json"), JSON.stringify(results, null, 2));
console.log(`\n${results.filter((r) => r.status === "ok").length} ok, ${results.filter((r) => r.status === "fail").length} fail`);
await browser.close();
