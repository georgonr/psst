// PSST — Web Push end-to-end test against production (D76), real Google Chrome (push needs FCM; Chromium has no keys).
//   PSST_TOKEN_A=<compat token of a> PSST_TOKEN_B=<compat token of b> node webpush-test.mjs <out-dir> <accounts.json>
// accounts.json: {"a": {"user","password"}, "b": {...}} — fresh test accounts (qa-*). a = web client under test.
// Run from a directory with node_modules/playwright (e.g. ~/.local/pw). Opens a headed Chrome window.
// Checks: pusher registered (client + admin API), tab closed → service worker notification, verification wake-up
// → notification, app focused → no duplicate generic notification, logout → pusher removed.
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const [OUT, ACC_FILE] = process.argv.slice(2);
fs.mkdirSync(OUT, { recursive: true });
const A = JSON.parse(fs.readFileSync(ACC_FILE, "utf8"));
const TA = process.env.PSST_TOKEN_A, TB = process.env.PSST_TOKEN_B;
const WEB = "https://app.psst.pro", HS = "https://chat.psst.pro", DOMAIN = "chat.psst.pro";
const SN = process.env.PSST_SERVER_NAME || "psst.pro";   // Matrix server_name (user IDs), D85
const APP_ID = "eu.macet.psst.web";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [];
const record = (id, ok, note = "") => { results.push({ id, status: ok ? "ok" : "fail", note: String(note).slice(0, 400) }); console.log(`${ok ? "OK  " : "FAIL"} ${id}  ${note}`); };
const uid = (k) => `@${A[k].user}:${SN}`;

async function api(token, method, p, body) {
    const r = await fetch(HS + p, { method, headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
    const t = await r.text();
    if (!r.ok) throw new Error(`${method} ${p}: ${r.status} ${t.slice(0, 200)}`);
    return t ? JSON.parse(t) : {};
}
const adminPushers = (user) => JSON.parse(execFileSync("ssh", ["psst", `cd /opt/psst/server && tok=$(sudo cat secrets/admin_token) && curl -s -H "Authorization: Bearer $tok" 'http://127.0.0.1:8008/_synapse/admin/v1/users/${encodeURIComponent(user)}/pushers'`]).toString());

const dir = fs.mkdtempSync(path.join(os.tmpdir(), "psst-wp-"));
const ctx = await chromium.launchPersistentContext(dir, {
    channel: process.env.PSST_CHROME_CHANNEL || "chrome",
    headless: false,
    viewport: { width: 1280, height: 900 },
    locale: process.env.PSST_LOCALE || "en-US",
    args: ["--no-first-run", "--no-default-browser-check"],
});
await ctx.grantPermissions(["notifications"], { origin: WEB });
// record what the app itself shows (page Notification or through the service worker registration)
await ctx.addInitScript(() => {
    const notes = (window.__psstNotes = []);
    const orig = ServiceWorkerRegistration.prototype.showNotification;
    ServiceWorkerRegistration.prototype.showNotification = function (t, o) { notes.push({ via: "sw-reg", title: t, tag: o?.tag }); return orig.call(this, t, o); };
    if (window.Notification) window.Notification = new Proxy(window.Notification, { construct(T, args) { notes.push({ via: "page", title: args[0], tag: args[1]?.tag }); return new T(...args); } });
});
const keeper = ctx.pages()[0] ?? (await ctx.newPage()); // keeps the browser alive while the app tab is closed
await keeper.goto("about:blank");
const shot = (p, n) => p.screenshot({ path: path.join(OUT, `wp-${n}.png`) }).catch(() => {});

/** Notifications currently shown by the app's service worker registration (evaluated inside the worker). */
async function swNotifications() {
    for (const w of ctx.serviceWorkers()) {
        if (!w.url().startsWith(WEB)) continue;
        try {
            return await w.evaluate(async () => (await self.registration.getNotifications()).map((n) => ({ title: n.title, body: n.body, tag: n.tag, data: n.data })));
        } catch {}
    }
    return null; // worker not running
}
async function waitNotification(pred, timeoutMs = 60000) {
    const t0 = Date.now();
    let last = null;
    while (Date.now() - t0 < timeoutMs) {
        const list = await swNotifications();
        if (list) { last = list; const hit = list.find(pred); if (hit) return { hit, list, ms: Date.now() - t0 }; }
        await sleep(1000);
    }
    return { hit: null, list: last, ms: Date.now() - t0 };
}
async function closeAllNotifications() {
    for (const w of ctx.serviceWorkers()) if (w.url().startsWith(WEB)) await w.evaluate(async () => (await self.registration.getNotifications()).forEach((n) => n.close())).catch(() => {});
}

async function login(p, user, password) {
    await p.goto(`${WEB}/#/login`);
    await p.locator('.mx_Login_fullWidthButton, button:has-text("Continue")').first().click({ timeout: 90000 });
    await p.waitForURL(/chat\.macet\.eu\/auth/, { timeout: 60000 });
    await p.waitForSelector('input[name="username"]', { timeout: 60000 });
    await p.fill('input[name="username"]', user); await p.fill('input[name="password"]', password);
    await p.locator("button[type=submit]").first().click();
    for (let i = 0; i < 20 && !p.url().startsWith(WEB); i++) { await p.locator('button[type=submit]:has-text("Continue"), button[type=submit]:has-text("Pokračovať")').first().click({ timeout: 1500 }).catch(() => {}); await sleep(1000); }
    await p.waitForSelector(".mx_LeftPanel, .mx_RoomListPanel, .mx_SpacePanel, .mx_AuthPage", { timeout: 120000 });
}
async function dismiss(p) {
    for (const name of ["Not now", "Close", "OK", "Later", "Got it", "Done", "Dismiss"]) await p.getByRole("button", { name, exact: true }).first().click({ timeout: 500 }).catch(() => {});
    for (let i = 0; i < 2; i++) await p.keyboard.press("Escape").catch(() => {});
}

let page;
try {
    // ---- 1. log in a on the web; with notifications allowed the app registers the web pusher by itself
    page = await ctx.newPage();
    page.on("console", (m) => { if (/psst web push|\[psst push\]/.test(m.text())) console.log("   [app]", m.text()); });
    await login(page, A.a.user, A.a.password);
    await sleep(3000); await dismiss(page); await shot(page, "1-app");
    let stored = null;
    for (let i = 0; i < 90 && !stored; i++) { stored = await page.evaluate(() => localStorage.getItem("psst_webpush_pusher")).catch(() => null); if (!stored) await sleep(1000); }
    const perm = await page.evaluate(() => Notification.permission);
    record("web.pusher_registered_client", Boolean(stored), `permission=${perm}`);
    const mine = (await api(TA, "GET", "/_matrix/client/v3/pushers")).pushers.filter((p) => p.app_id === APP_ID);
    const ep = mine[0]?.data?.endpoint ? new URL(mine[0].data.endpoint).host : "-";
    record("web.pusher_on_server(client API)", mine.length === 1 && mine[0].data.format === "event_id_only", `count=${mine.length} endpoint_host=${ep} kind=${mine[0]?.kind}`);
    const adm = adminPushers(uid("a")).pushers.filter((p) => p.app_id === APP_ID);
    record("web.pusher_on_server(admin API)", adm.length === 1, `count=${adm.length} device_id=${adm[0]?.device_id ? "set" : "missing"}`);

    // ---- room a<->b (via the API: b invites, a's second device accepts). Unencrypted (public_chat preset, not in the
    //      directory): b sends plain text through the API, which in an encrypted room the app would count as read.
    const room = (await api(TB, "POST", "/_matrix/client/v3/createRoom", { preset: "public_chat", visibility: "private", is_direct: true, invite: [uid("a")] })).room_id;
    await api(TA, "POST", `/_matrix/client/v3/rooms/${encodeURIComponent(room)}/join`, {});
    await sleep(4000);
    const send = (txt) => api(TB, "PUT", `/_matrix/client/v3/rooms/${encodeURIComponent(room)}/send/m.room.message/wp${Date.now()}`, { msgtype: "m.text", body: txt });

    // ---- 2. app tab closed (browser keeps running) → b writes → service worker notification
    await page.close();
    await sleep(5000);
    await closeAllNotifications();
    const ev1 = (await send("webpush test 1 (tab closed)")).event_id;
    const r1 = await waitNotification((n) => n.tag === `psst-room-${room}`, 60000);
    record("web.notification_tab_closed", Boolean(r1.hit && r1.hit.data?.psst_push && r1.hit.data?.event_id === ev1),
        r1.hit ? `after ${(r1.ms / 1000).toFixed(1)} s: "${r1.hit.title}" — "${r1.hit.body}"` : `none; seen=${JSON.stringify(r1.list)}`);

    // ---- 3. verification wake-up: another device of a asks for verification (nginx mirror → psst-wake → Sygnal)
    await closeAllNotifications();
    const txn = `wpv${Date.now()}`;
    await api(TA, "PUT", `/_matrix/client/v3/sendToDevice/m.key.verification.request/${txn}`, {
        messages: { [uid("a")]: { "*": { from_device: "WPTEST", methods: ["m.sas.v1"], timestamp: Date.now(), transaction_id: txn } } },
    });
    const r2 = await waitNotification((n) => n.tag === "psst-verification", 45000);
    record("web.verification_wakeup", Boolean(r2.hit), r2.hit ? `after ${(r2.ms / 1000).toFixed(1)} s: "${r2.hit.title}" — "${r2.hit.body}"` : `none; seen=${JSON.stringify(r2.list)}`);
    await api(TA, "PUT", `/_matrix/client/v3/sendToDevice/m.key.verification.cancel/${txn}c`, {
        messages: { [uid("a")]: { "*": { code: "m.user", reason: "test", transaction_id: txn } } },
    }).catch(() => {});

    // ---- 4. app open and in front → only the app's own notification (no extra generic one)
    await closeAllNotifications();
    page = await ctx.newPage();
    await page.goto(WEB);
    await page.waitForSelector(".mx_LeftPanel, .mx_RoomListPanel, .mx_SpacePanel", { timeout: 120000 });
    await sleep(6000); await dismiss(page); await page.bringToFront();
    const focus = await page.evaluate(() => ({ focus: document.hasFocus(), vis: document.visibilityState }));
    await closeAllNotifications();
    await send("webpush test 2 (app open)");
    await sleep(12000);
    const appNotes = await page.evaluate(() => window.__psstNotes);
    console.log("   app notifications:", JSON.stringify(appNotes));
    const list4 = (await swNotifications()) ?? [];
    const roomN = list4.filter((n) => n.tag === `psst-room-${room}`);
    record("web.app_open_no_duplicate", roomN.length <= 1 && !roomN.some((n) => n.data?.psst_push && !focus.focus),
        `page focus=${focus.focus} visibility=${focus.vis}; notifications for room: ${JSON.stringify(roomN.map((n) => ({ title: n.title, body: n.body, app: Boolean(n.data?.psst_app), push: Boolean(n.data?.psst_push) })))}`);
    await shot(page, "4-open");

    // ---- 4b. app open in a background tab (another tab in front) → still exactly one notification for the room
    await closeAllNotifications();
    await keeper.bringToFront();
    await sleep(2000);
    const ev3 = (await send("webpush test 3 (app in background tab)")).event_id;
    await sleep(3000);
    const dbg = await page.evaluate((r) => { const c = window.mxMatrixClientPeg?.get(); const rm = c?.getRoom(r); return { count: rm?.getUnreadNotificationCount(), enc: rm?.hasEncryptionStateEvent() }; }, room).catch((e) => String(e));
    console.log("   room state:", JSON.stringify(dbg));
    await sleep(9000);
    const list4b = ((await swNotifications()) ?? []).filter((n) => n.tag === `psst-room-${room}`);
    const notes4b = await page.evaluate(() => window.__psstNotes.slice(-3));
    record("web.background_tab_single_notification", list4b.length === 1 && list4b[0].data?.event_id === ev3,
        `visibility=${await page.evaluate(() => document.visibilityState)}; shown: ${JSON.stringify(list4b.map((n) => ({ title: n.title, body: n.body, app: Boolean(n.data?.psst_app), push: Boolean(n.data?.psst_push) })))}; app calls: ${JSON.stringify(notes4b)}`);
    await page.bringToFront();

    // ---- 5. sign out → pusher removed
    await page.evaluate(() => { location.hash = "#/home"; });
    await sleep(1000); await dismiss(page);
    await page.locator('[aria-label="User menu"]').first().click({ timeout: 15000 });
    await page.locator('[role=menuitem]:has-text("All settings")').first().click({ timeout: 15000 });
    await page.getByRole("tab", { name: "Account" }).first().click({ timeout: 15000 });
    await sleep(1500);
    await page.getByRole("button", { name: /^(Sign out|Remove this device)$/ }).first().click({ timeout: 15000 });
    await sleep(2000); await shot(page, "5-logout-dialog");
    for (let i = 0; i < 3; i++) {
        const b = page.locator(".mx_Dialog").last().locator("button, [role=button]").filter({ hasText: /^(Sign out anyway|I don't want my encrypted messages|Sign out|Remove this device|Remove this device anyway|Continue to remove this device)$/ }).first();
        if (await b.count()) { await b.click().catch(() => {}); await sleep(2500); } else break;
    }
    await page.waitForSelector(".mx_Login_fullWidthButton, .mx_AuthPage, .mx_Welcome", { timeout: 60000 }).catch(() => {});
    await sleep(3000);
    const after = (await api(TA, "GET", "/_matrix/client/v3/pushers")).pushers.filter((p) => p.app_id === APP_ID);
    const sub = await page.evaluate(async () => Boolean(await (await navigator.serviceWorker.ready).pushManager.getSubscription())).catch(() => "?");
    record("web.logout_removes_pusher", after.length === 0 && sub === false, `pushers left=${after.length}, browser subscription=${sub}`);
    fs.writeFileSync(path.join(OUT, "room.txt"), room);
} catch (e) {
    record("web.webpush_test", false, e.stack || String(e));
    if (page && !page.isClosed()) await shot(page, "error");
} finally {
    fs.writeFileSync(path.join(OUT, "results.json"), JSON.stringify(results, null, 2));
    await ctx.close();
    fs.rmSync(dir, { recursive: true, force: true });
}
process.exit(results.every((r) => r.status === "ok") ? 0 : 1);
