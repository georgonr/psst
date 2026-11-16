// PSST feature audit — Web (https://app.macet.eu) against production, headless Chromium (docs/FEATURE-MATRIX.md).
//   node web-audit.mjs <out-dir> <accounts.json> [registration-token]
// accounts.json: {"a": {"user","password"}, "b": {...}, "c": {...}} — fresh test accounts (a = client under test)
// Needs playwright (run from a directory with node_modules/playwright, e.g. ~/.local/pw, or NODE_PATH).
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { runFeatures, runAccountFlows, writeResults, sleep, cli, compose, openRoom, waitEvent, startCall, joinFromToast, remoteVideo, icePaths, hangUp, PC_HOOK, dismiss } from "./features.mjs";

const [OUT, ACC_FILE, REG_TOKEN] = process.argv.slice(2);
fs.mkdirSync(OUT, { recursive: true });
const A = JSON.parse(fs.readFileSync(ACC_FILE, "utf8"));
const WEB = "https://app.macet.eu", HS = "chat.macet.eu";
const results = [];
const record = (id, status, note = "") => { results.push({ id, status, note: String(note).slice(0, 300) }); console.log(`${status.toUpperCase().padEnd(8)} ${id}  ${note}`); };
const MEDIA = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required",
    "--auto-select-desktop-capture-source=Entire screen", "--enable-usermedia-screen-capturing", "--auto-accept-this-tab-capture"];
const browser = await chromium.launch({ args: MEDIA });
const shot = (p, n) => p.screenshot({ path: path.join(OUT, `web-${n}.png`) }).catch(() => {});

async function newPage(b = browser) {
    const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, permissions: ["camera", "microphone", "notifications", "clipboard-read", "clipboard-write"] });
    await ctx.addInitScript(PC_HOOK);
    const p = await ctx.newPage();
    p.on("dialog", (d) => d.accept().catch(() => {}));
    return p;
}
async function masForm(p, user, password) {
    await p.waitForURL(/chat\.macet\.eu\/auth/, { timeout: 60000 });
    // MAS may still have a browser session for this account → "Continue to psst?" without the form
    for (let i = 0; i < 30; i++) {
        if (await p.locator('input[name="username"]').count()) break;
        if (await p.getByText("Continue to psst?").count()) break;
        await sleep(1000);
    }
    if (await p.locator('input[name="username"]').count()) {
        await p.fill('input[name="username"]', user); await p.fill('input[name="password"]', password);
        await p.locator("button[type=submit]").first().click();
    }
    for (let i = 0; i < 20 && !p.url().startsWith(WEB); i++) { await p.locator('button[type=submit]:has-text("Continue")').first().click({ timeout: 1500 }).catch(() => {}); await sleep(1000); }
}
const APP = ".mx_LeftPanel, .mx_RoomListPanel, .mx_SpacePanel";
/** Sign in; returns "app" | "identity" (Confirm your digital identity shown). */
async function login(p, user, password) {
    await p.goto(`${WEB}/#/login`);
    await p.locator('.mx_Login_fullWidthButton, button:has-text("Continue")').first().click({ timeout: 90000 });
    await masForm(p, user, password);
    for (let i = 0; i < 90; i++) {
        if (await p.getByText("Confirm your digital identity").count().catch(() => 0)) return "identity";
        if (await p.locator(APP).count()) { await sleep(4000); for (let k = 0; k < 3; k++) await p.keyboard.press("Escape").catch(() => {}); return "app"; }
        await sleep(1000);
    }
    throw new Error(`login ${user}: neither app nor identity screen`);
}
async function settingsTab(p, tab) {
    await dismiss(p);
    await p.locator('[aria-label="User menu"]').first().click({ timeout: 15000 });
    await p.locator('[role=menuitem]:has-text("All settings")').first().click({ timeout: 15000 });
    await p.getByRole("tab", { name: tab }).first().click({ timeout: 15000 });
    await sleep(2000);
}
async function logout(p) {
    await p.evaluate(() => { location.hash = "#/home"; });
    await settingsTab(p, "Account");
    await p.getByRole("button", { name: /^(Sign out|Remove this device)$/ }).first().click({ timeout: 15000 });
    await sleep(2000);
    await shot(p, "logout-dialog");
    // confirmation dialog (text differs with/without key backup): click its button, not the settings button again
    for (let i = 0; i < 3; i++) {
        const b = p.locator('.mx_Dialog').last().locator('button, [role=button]').filter({ hasText: /^(Continue to remove this device|Remove this device anyway|Sign out anyway|I don't want my encrypted messages|Sign out|Remove this device|Remove device)$/ }).first();
        if (await b.count()) { await b.click().catch(() => {}); await sleep(2000); } else break;
    }
    const ok = await p.waitForSelector(".mx_Login_fullWidthButton, .mx_AuthPage, .mx_Welcome", { timeout: 60000 }).then(() => true, () => false);
    if (!ok) await shot(p, "logout-stuck");
    return ok;
}

// ======================================================================================= run
const me = await newPage(), partner = await newPage(), third = await newPage();

// ---- login screen: download link, locked homeserver
await me.goto(`${WEB}/#/login`);
await me.locator('.mx_Login_fullWidthButton, button:has-text("Continue")').first().waitFor({ timeout: 90000 });
const dl = await me.locator('a[href="https://app.macet.eu/download/"]').count();
record("download_page", dl ? "ok" : "fail", `odkaz „Download apps“ na prihlasovacej obrazovke ${dl > 0}`);

// ---- registration with an invitation token (new account, deactivated with the others)
if (REG_TOKEN) {
    try {
        const reg = await newPage();
        const user = `qa-aureg${Date.now() % 1000000}`, pw = `Pw-${Date.now()}-x`;
        await reg.goto(`${WEB}/#/register`);
        await reg.locator('button:has-text("Continue")').first().click({ timeout: 90000 });
        await reg.waitForURL(/chat\.macet\.eu\/auth/, { timeout: 60000 });
        await reg.fill('input[name="username"]', user); await reg.fill('input[name="password"]', pw); await reg.fill('input[name="password_confirm"]', pw);
        await reg.check('input[name="accept_terms"]').catch(() => {});
        for (let i = 0; i < 5 && !/\/token/.test(reg.url()); i++) { await sleep(2500); await reg.locator("button[type=submit]").first().click().catch(() => {}); await reg.waitForURL(/\/token/, { timeout: 5000 }).catch(() => {}); }
        await reg.fill('input[name="token"]', REG_TOKEN); await reg.locator("button[type=submit]").first().click();
        for (let i = 0; i < 25 && !reg.url().startsWith(WEB); i++) {
            if (/display-name/.test(reg.url())) { await reg.locator("input:not([type=hidden])").first().fill("QA registered", { timeout: 3000 }).catch(() => {}); await reg.locator("button[type=submit]").first().click({ timeout: 3000 }).catch(() => {}); }
            await reg.locator('button[type=submit]:has-text("Continue")').first().click({ timeout: 1500 }).catch(() => {});
            await sleep(1500);
        }
        const ok = await reg.waitForSelector(APP, { timeout: 120000 }).then(() => true, () => false);
        const uid = await reg.evaluate(() => window.mxMatrixClientPeg?.get()?.getUserId()).catch(() => null);
        await shot(reg, "registered");
        record("register", ok && uid === `@${user}:${HS}` ? "ok" : "fail", `registrácia s pozývacím tokenom → ${uid}`);
        fs.writeFileSync(path.join(OUT, "registered-user.txt"), user + "\n");
        await reg.context().close();
    } catch (e) { record("register", "fail", String(e.message).slice(0, 200)); }
} else record("register", "na", "bez registračného tokenu");

// ---- sign in all three
const s1 = await login(me, A.a.user, A.a.password);
record("login", s1 === "app" ? "ok" : "fail", `prvé prihlásenie cez MAS → ${s1}`);
await login(partner, A.b.user, A.b.password);
await login(third, A.c.user, A.c.password);
await shot(me, "logged-in");

// ---- the shared suite (messages, files, calls, profile, ...)
// PSST_AUDIT_ONLY_ACCOUNT=1: only account flows (recovery key, verification, logout, re-login) — a quick re-test
if (!process.env.PSST_AUDIT_ONLY_ACCOUNT) {
    await runFeatures({ me, partner, third, users: { me: A.a.user, partner: A.b.user, third: A.c.user }, record, out: OUT, platform: "web" });
} else {
    // a little encrypted history to check later on the new / re-logged-in session
    const dm = await cli(me, async (who) => (await window.mxMatrixClientPeg.get().createRoom({ preset: "trusted_private_chat", is_direct: true, invite: [who] })).room_id, `@${A.b.user}:${HS}`);
    await cli(partner, async (r) => { await window.mxMatrixClientPeg.get().joinRoom(r); }, dm);
    await sleep(3000);
    for (let i = 0; i < 3; i++) await cli(me, ([r, b]) => window.mxMatrixClientPeg.get().sendTextMessage(r, b), [dm, `history ${i} ${Date.now()}`]);
    await cli(partner, ([r, b]) => window.mxMatrixClientPeg.get().sendTextMessage(r, b), [dm, `history from partner ${Date.now()}`]);
    await sleep(5000);
}

// ---- notifications in a background tab / with the app closed
// Web Push (D76) needs real Chrome (FCM): run scripts/web/webpush-test.mjs first and pass its results.json in
// PSST_WEBPUSH_RESULT; headless Chromium here cannot subscribe to push.
const WP = process.env.PSST_WEBPUSH_RESULT ? Object.fromEntries(JSON.parse(fs.readFileSync(process.env.PSST_WEBPUSH_RESULT, "utf8")).map((r) => [r.id, r])) : null;
if (WP) {
    const st = (...ids) => (ids.every((i) => WP[i]?.status === "ok") ? "ok" : "fail");
    const n = (i) => WP[i]?.note ?? "chýba";
    record("notif_background", st("web.background_tab_single_notification", "web.notification_tab_closed"), `Web Push (Chrome): appka v karte na pozadí → práve 1 notifikácia; karta zatvorená → ${n("web.notification_tab_closed")}`);
    record("notif_closed", st("web.notification_tab_closed", "web.pusher_on_server(client API)"), `Web Push (Chrome, karta zatvorená, prehliadač beží): notifikácia service workera ${n("web.notification_tab_closed")}; pusher ${n("web.pusher_on_server(client API)")}`);
    record("verify_wakeup", st("web.verification_wakeup"), `žiadosť o overenie pri zatvorenej karte → ${n("web.verification_wakeup")}`);
} else {
    record("notif_background", "na", "Web Push (D76) overuje scripts/web/webpush-test.mjs v skutočnom Chrome — spusti ho a nastav PSST_WEBPUSH_RESULT");
    record("notif_closed", "na", "Web Push (D76) overuje scripts/web/webpush-test.mjs v skutočnom Chrome — spusti ho a nastav PSST_WEBPUSH_RESULT");
}
record("notif_lock", "na", "web: zamknutá obrazovka je vec OS/prehliadača");

// ---- account flows (shared with the desktop audit): recovery key, QR, emoji verification, logout, re-login
await runAccountFlows({
    me, record, platform: "web", shot,
    newWebSession: async () => { const p = await newPage(); return { page: p, state: await login(p, A.a.user, A.a.password) }; },
    loginMe: () => login(me, A.a.user, A.a.password),
});
record("verify_qr", "na", "web/desktop zobrazí QR na overenie, naskenovať ho vie len mobil; Element X pri overovaní ponúka len emoji");

// ---- 1:1 call with UDP blocked (WebRTC may use only TCP / TURN-TLS): separate browser for me
if (!process.env.PSST_AUDIT_ONLY_ACCOUNT) try {
    const b2 = await chromium.launch({ args: [...MEDIA, "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"] });
    const me2 = await newPage(b2);
    if (!A.d) throw new Error("accounts.json needs a 4th fresh account \"d\" for this test");
    const st = await login(me2, A.d.user, A.d.password);
    if (st !== "app") throw new Error("login d → " + st);
    // partner calls d in a fresh DM
    const dm = await cli(partner, async (who) => { const c = window.mxMatrixClientPeg.get(); const r = await c.createRoom({ preset: "trusted_private_chat", is_direct: true, invite: [who] }); await c.setAccountData("m.direct", { [who]: [r.room_id] }); return r.room_id; }, `@${A.d.user}:${HS}`);
    await cli(me2, async ([r, who]) => { const c = window.mxMatrixClientPeg.get(); await c.joinRoom(r); await c.setAccountData("m.direct", { [who]: [r] }); }, [dm, `@${A.b.user}:${HS}`]);
    await sleep(4000);
    await startCall(partner, dm, "Video call");
    const r = await joinFromToast(me2);
    const v = r.joined ? await remoteVideo(me2, 1) : { playing: 0 };
    const paths = await icePaths(me2);
    const udp = paths.some((x) => /\/udp/.test(x.local) && !/relay/.test(x.local));
    await shot(me2, "call-udp-blocked");
    record("call_udp_blocked", r.joined && v.playing >= 1 && !udp ? "ok" : "fail", `UDP zakázané: pripojenie ${r.joined}, video ${v.playing}, ICE ${JSON.stringify(paths.slice(0, 3))}`);
    await hangUp(me2, partner);
    await b2.close();
} catch (e) { record("call_udp_blocked", "fail", String(e.message).slice(0, 200)); }

writeResults(OUT, "web", results);
await browser.close();
const f = results.filter((r) => r.status === "fail").length;
console.log(`\n${results.filter((r) => r.status === "ok").length} ok, ${f} fail, ${results.length} total`);
