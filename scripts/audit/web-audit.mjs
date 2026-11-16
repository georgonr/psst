// PSST feature audit — Web (https://app.macet.eu) against production, headless Chromium (docs/FEATURE-MATRIX.md).
//   node web-audit.mjs <out-dir> <accounts.json> [registration-token]
// accounts.json: {"a": {"user","password"}, "b": {...}, "c": {...}} — fresh test accounts (a = client under test)
// Needs playwright (run from a directory with node_modules/playwright, e.g. ~/.local/pw, or NODE_PATH).
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { runFeatures, writeResults, sleep, cli, compose, openRoom, waitEvent, startCall, joinFromToast, remoteVideo, icePaths, hangUp, PC_HOOK, dismiss } from "./features.mjs";

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
    await sleep(1500);
    await p.getByText(/^(Remove this device anyway|Sign out anyway|I don't want my encrypted messages|Sign out|Remove this device)$/).last().click({ timeout: 10000 }).catch(() => {});
    return p.waitForSelector(".mx_Login_fullWidthButton, .mx_AuthPage, .mx_Welcome", { timeout: 60000 }).then(() => true, () => false);
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

// ---- recovery key: Settings → Encryption → Set up recovery
let recoveryKey = null;
try {
    await dismiss(me);
    await settingsTab(me, "Encryption");
    await me.locator('button:has-text("Create recovery key"), button:has-text("Set up recovery")').first().click({ timeout: 15000 });
    const KEY = /(?:[1-9A-HJ-NP-Za-km-z]{4}\s){11}[1-9A-HJ-NP-Za-km-z]{4}/;
    for (let i = 0; i < 10 && !recoveryKey; i++) {
        await sleep(1500);
        recoveryKey = (KEY.exec(await me.locator(".mx_Dialog").innerText()) || [null])[0];
        if (!recoveryKey) await me.locator('.mx_Dialog button:has-text("Continue")').first().click({ timeout: 2000 }).catch(() => {});
    }
    await shot(me, "recovery-key");
    if (!recoveryKey) throw new Error("recovery key not shown");
    await me.locator('.mx_Dialog button:has-text("Continue")').first().click({ timeout: 10000 });
    await sleep(1500);
    await me.locator(".mx_Dialog input:not([type=hidden]), .mx_Dialog textarea").last().fill(recoveryKey);
    await me.locator('.mx_Dialog button:has-text("Finish set up"), .mx_Dialog button:has-text("Continue")').first().click({ timeout: 10000 });
    await sleep(5000);
    const st = await cli(me, async () => { const c = window.mxMatrixClientPeg.get().getCrypto(); return { backup: await c.getActiveSessionBackupVersion(), ss: await c.isSecretStorageReady() }; });
    await shot(me, "recovery");
    await me.keyboard.press("Escape");
    record("recovery", recoveryKey && st.backup && st.ss ? "ok" : "fail", `obnovovací kľúč vytvorený, záloha kľúčov verzia ${st.backup}, secret storage ${st.ss}`);
} catch (e) { record("recovery", "fail", String(e.message).slice(0, 200)); await shot(me, "recovery-error"); }

// ---- QR sign-in: "Link new device" shows a QR code (scanned by the Android app in the Android part)
try {
    await dismiss(me);
    await me.locator('[aria-label="User menu"]').first().click({ timeout: 15000 });
    await me.locator('[role=menuitem]:has-text("Link new device")').first().click({ timeout: 10000 });
    await me.locator('button:has-text("Show QR code"), button:has-text("Mobile device")').first().click({ timeout: 10000 }).catch(() => {});
    const qr = await me.locator(".mx_LoginWithQR canvas, .mx_LoginWithQR img, .mx_QRCode, canvas").first().waitFor({ timeout: 30000 }).then(() => true, () => false);
    await shot(me, "qr");
    record("qr_login", qr ? "ok" : "fail", qr ? "web zobrazí QR na prihlásenie nového zariadenia (MSC4108)" : "QR sa nezobrazil");
    await me.keyboard.press("Escape"); await me.keyboard.press("Escape");
} catch (e) { record("qr_login", "fail", String(e.message).slice(0, 200)); }

// ---- the shared suite (messages, files, calls, profile, ...)
await runFeatures({ me, partner, third, users: { me: A.a.user, partner: A.b.user, third: A.c.user }, record, out: OUT, platform: "web" });

// ---- notifications in a background tab / with the app closed
record("notif_background", "upstream", "web: notifikácia príde, kým je karta otvorená (aj na pozadí); Element Web nemá Web Push");
record("notif_closed", "upstream", "web: po zatvorení karty nič nepríde — Element Web nepodporuje Web Push (upstream)");
record("notif_lock", "na", "web: zamknutá obrazovka je vec OS/prehliadača");

// ---- device verification by emoji: a 2nd web session of `me` → "Use another device" → me accepts
let second = null;
try {
    second = await newPage();
    const st = await login(second, A.a.user, A.a.password);
    if (st !== "identity") throw new Error("2nd session did not ask to confirm identity: " + st);
    record("verify_unverified_state", (await second.locator(APP).count()) === 0 ? "ok" : "fail", "nová relácia je zablokovaná na „Confirm your digital identity“, kým nie je overená");
    await second.locator('button:has-text("Use another device")').click({ timeout: 15000 });
    const toast = me.locator('.mx_Toast_toast:has-text("Verification requested"), .mx_Toast_toast:has-text("verify")').first();
    const req = await toast.waitFor({ timeout: 60000 }).then(() => true, () => false);
    await shot(me, "verify-toast");
    await toast.locator('button:has-text("Start Verification"), button:has-text("Verify session"), button:has-text("Verify"), button:has-text("Accept")').first().click({ timeout: 10000 });
    await me.locator('button:has-text("Verify by emoji"), button:has-text("Start")').first().click({ timeout: 20000 }).catch(() => {});
    await second.locator('button:has-text("Verify by emoji")').first().click({ timeout: 20000 }).catch(() => {});
    const emoji = await me.locator(".mx_VerificationShowSas_emojiSas").first().waitFor({ timeout: 40000 }).then(() => true, () => false);
    const e1 = (await me.locator(".mx_VerificationShowSas_emojiSas").innerText().catch(() => "")).replace(/\s+/g, " ");
    const e2 = (await second.locator(".mx_VerificationShowSas_emojiSas").innerText().catch(() => "")).replace(/\s+/g, " ");
    await shot(second, "verify-emoji");
    await me.locator('button:has-text("They match")').first().click({ timeout: 10000 }).catch(() => {});
    await second.locator('button:has-text("They match")').first().click({ timeout: 10000 }).catch(() => {});
    let verified = false;
    for (let i = 0; i < 30 && !verified; i++) {
        verified = await second.evaluate(async () => { const c = window.mxMatrixClientPeg.get(); return !!(await c.getCrypto().getDeviceVerificationStatus(c.getUserId(), c.getDeviceId()))?.crossSigningVerified; }).catch(() => false);
        if (!verified) await sleep(1500);
    }
    record("verify_emoji", req && emoji && e1 && e1 === e2 && verified ? "ok" : "fail", `žiadosť doručená ${req}, emoji zhodné ${!!e1 && e1 === e2}, relácia cross-signed ${verified}`);
    for (let i = 0; i < 4; i++) { await second.locator('button:has-text("Done"), button:has-text("Got it")').first().click({ timeout: 2000 }).catch(() => {}); await second.keyboard.press("Escape").catch(() => {}); }
    await me.locator('button:has-text("Done"), button:has-text("Got it")').first().click({ timeout: 2000 }).catch(() => {});
    record("verify_qr", "na", "web/desktop zobrazí QR na overenie, skenovať ho vie len mobil (overené v časti Android)");
    // history on the newly verified session (keys from backup / key sharing)
    const old = await second.evaluate(async () => {
        const c = window.mxMatrixClientPeg.get();
        const rooms = c.getRooms().filter((r) => r.getMyMembership() === "join");
        let enc = 0, ok = 0;
        for (const r of rooms) { await c.scrollback(r, 30).catch(() => {}); for (const e of r.getLiveTimeline().getEvents()) if (e.isEncrypted()) { enc++; if (!e.isDecryptionFailure() && e.getClearContent()?.body) ok++; } }
        return { enc, ok };
    });
    record("history_new_device", old.enc && old.ok === old.enc ? "ok" : (old.enc ? "fail" : "na"), `nová overená relácia: dešifrovaných ${old.ok}/${old.enc} starších šifrovaných správ`);
} catch (e) { record("verify_emoji", "fail", String(e.message).slice(0, 200)); await shot(second || me, "verify-error"); }

// ---- logout → sign in again with the recovery key → history restored from key backup
try {
    if (second) { await logout(second).catch(() => {}); await second.context().close(); }
    const out = await logout(me);
    record("logout", out ? "ok" : "fail", "odhlásenie (Settings → Account → Remove this device)");
    const st = await login(me, A.a.user, A.a.password);
    if (st === "identity" && recoveryKey) {
        await me.locator('button:has-text("Use recovery key")').click({ timeout: 15000 });
        await sleep(1500);
        await me.locator(".mx_Dialog input:not([type=hidden]), .mx_Dialog textarea, input:not([type=hidden])").last().fill(recoveryKey);
        await me.locator('button:has-text("Continue")').last().click({ timeout: 15000 });
        await me.locator('button:has-text("Done")').first().click({ timeout: 30000 }).catch(() => {});
        await me.waitForSelector(APP, { timeout: 60000 });
    }
    await sleep(15000);
    const hist = await me.evaluate(async () => {
        const c = window.mxMatrixClientPeg.get();
        let enc = 0, ok = 0;
        for (const r of c.getRooms().filter((r) => r.getMyMembership() === "join")) {
            await c.scrollback(r, 50).catch(() => {});
            for (const e of r.getLiveTimeline().getEvents()) if (e.isEncrypted()) { enc++; if (!e.isDecryptionFailure() && (e.getClearContent()?.body || e.getClearContent()?.["m.relates_to"])) ok++; }
        }
        const s = await c.getCrypto().getDeviceVerificationStatus(c.getUserId(), c.getDeviceId());
        return { enc, ok, verified: !!s?.crossSigningVerified };
    });
    await shot(me, "relogin");
    record("relogin", st ? "ok" : "fail", `opätovné prihlásenie → ${st}${st === "identity" ? " → obnovovací kľúč" : ""}, relácia overená ${hist.verified}`);
    record("key_backup_restore", hist.verified && hist.enc && hist.ok >= hist.enc - 1 ? "ok" : "fail", `po prihlásení s obnovovacím kľúčom dešifrovaných ${hist.ok}/${hist.enc} starších správ`);
} catch (e) { record("relogin", "fail", String(e.message).slice(0, 200)); await shot(me, "relogin-error"); }

// ---- 1:1 call with UDP blocked (WebRTC may use only TCP / TURN-TLS): separate browser for me
try {
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
