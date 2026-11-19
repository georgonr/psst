// PSST audit helper for QR code device verification (D81, docs/android-qr-verification.md): Element Web sessions
// (app.psst.pro, or psst desktop over CDP) driven step by step while the Android side is driven over adb.
//   node qr-partner.mjs <accounts-file> <out-dir> [cdp-url]
// <accounts-file>: lines "<user> <password>" (qa-* test accounts only); "<user>#2" in a command = another session of
// that user in its own browser profile. With [cdp-url] the FIRST account's session is
// the psst desktop app already running with --remote-debugging-port (signed in there by this script if needed).
// Browser profiles persist in <out-dir>/profiles (a restart keeps the same devices).
// Commands written to <out-dir>/NEXT, result in <out-dir>/DONE + log.txt:
//   login <user>                    open (and sign in) that user's web session
//   recovery <user>                 Settings → Encryption → set up recovery → <out-dir>/recovery-<user>.txt
//   dm <a> <b> <n>                  a creates an encrypted DM with b, b joins, a sends n numbered messages
//   shot <user>                     screenshot → <out-dir>/shot-<user>.png
//   qr <user> <file.png>            screenshot of the verification QR code shown by that session → file
//   click <user> <regex>            click the first visible button / link whose text matches
//   verify-other <user>             Settings → Sessions: "Verify session" on the newest other session
//   texts <user>                    visible dialog / toast texts → log
//   mas-approve <user> <code>       QR login: in that session's MAS tab, enter the code and grant access
//   eval <user> <file.js>           evaluate an async function expression from file → <out-dir>/eval.json
//   quit
import { chromium } from "playwright";
import fs from "node:fs";

const [accountsFile, out, cdpUrl] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (s) => { const l = `[${new Date().toISOString().slice(11, 19)}] ${s}`; console.log(l); fs.appendFileSync(`${out}/log.txt`, l + "\n"); };
const lines = fs.readFileSync(accountsFile, "utf8").trim().split("\n").map((l) => l.trim().split(/\s+/));
const acc = Object.fromEntries(lines);
if (!Object.keys(acc).every((u) => /^qa-[a-z0-9-]+$/.test(u))) throw new Error("test accounts must be qa-*");
const APP = ".mx_LeftPanel, .mx_RoomListPanel";
const P = {};

async function signInIfNeeded(p, profile) {
    const user = profile.split("#")[0]; // "qa-v1#2" = a second session (own browser profile) of qa-v1
    for (let i = 0; i < 30; i++) { if (await p.locator(`${APP}, button:has-text("Continue"), button:has-text("Use recovery key")`).count()) break; await sleep(1000); }
    if (await p.locator(`${APP}, button:has-text("Use recovery key"), button:has-text("Use another device")`).count()) return;
    await p.evaluate(() => { location.hash = "#/login"; });
    await p.locator('button:has-text("Continue")').first().click({ timeout: 90000 });
    await p.waitForURL(/auth/, { timeout: 60000 });
    for (let i = 0; i < 60 && !/app\.psst\.pro|vector:\/\/|file:\/\//.test(p.url()); i++) {
        if (await p.locator('input[name="username"]').count()) {
            await p.fill('input[name="username"]', user); await p.fill('input[name="password"]', acc[user]);
            await p.locator("button[type=submit]").first().click();
        } else await p.locator('button[type=submit]:has-text("Continue")').first().click({ timeout: 1500 }).catch(() => {});
        await sleep(1500);
    }
    for (let i = 0; i < 90; i++) { if (await p.locator(`${APP}, button:has-text("Use recovery key"), button:has-text("Use another device")`).count()) break; await sleep(1000); }
}

async function open(user) {
    if (P[user]) return P[user];
    let p;
    if (cdpUrl && user === lines[0][0]) {
        const b = await chromium.connectOverCDP(cdpUrl);
        for (let i = 0; i < 60 && !p; i++) {
            p = b.contexts().flatMap((c) => c.pages()).find((x) => x.url().startsWith("vector://"));
            if (!p) await sleep(1000);
        }
        if (!p) throw new Error("desktop main window not found");
        log(`${user}: desktop app at ${p.url()}`);
    } else {
        const ctx = await chromium.launchPersistentContext(`${out}/profiles/${user}`, { viewport: { width: 1280, height: 900 } });
        p = ctx.pages()[0] ?? await ctx.newPage();
        await p.goto("https://app.psst.pro/#/home");
    }
    await signInIfNeeded(p, user);
    await sleep(2000);
    for (const name of ["Not now", "Later", "Dismiss", "OK", "Got it"]) await p.getByRole("button", { name, exact: true }).first().click({ timeout: 400 }).catch(() => {});
    const who = await p.evaluate(async () => { const c = window.mxMatrixClientPeg.get(); const s = await c.getCrypto().getDeviceVerificationStatus(c.getUserId(), c.getDeviceId()); return `${c.getUserId()} device ${c.getDeviceId()} verified ${!!s?.crossSigningVerified}`; }).catch((e) => `? ${e.message}`);
    log(`${user}: ${who}`);
    P[user] = p;
    return p;
}

async function settingsTab(p, tab) {
    await p.keyboard.press("Escape").catch(() => {});
    await p.locator('[aria-label="User menu"]').first().click({ timeout: 15000 });
    await p.locator('[role=menuitem]:has-text("All settings")').first().click({ timeout: 15000 });
    await p.getByRole("tab", { name: tab }).first().click({ timeout: 15000 });
    await sleep(2000);
}

async function recovery(user) {
    const p = await open(user);
    await settingsTab(p, "Encryption");
    await p.locator('button:has-text("Set up recovery"), button:has-text("Create recovery key")').first().click({ timeout: 15000 });
    const KEY = /(?:[1-9A-HJ-NP-Za-km-z]{4}\s){11}[1-9A-HJ-NP-Za-km-z]{4}/;
    let key = null;
    for (let i = 0; i < 10 && !key; i++) {
        await sleep(1500);
        key = (KEY.exec(await p.locator(".mx_Dialog, .mx_SettingsDialog").first().innerText()) || [null])[0];
        if (!key) await p.locator('.mx_Dialog button:has-text("Continue")').first().click({ timeout: 2000 }).catch(() => {});
    }
    if (!key) throw new Error("recovery key not shown");
    await p.locator('.mx_Dialog button:has-text("Continue")').first().click({ timeout: 10000 });
    await sleep(1500);
    await p.locator(".mx_Dialog input:not([type=hidden]), .mx_Dialog textarea").last().fill(key);
    await p.locator('.mx_Dialog button:has-text("Finish set up"), .mx_Dialog button:has-text("Continue")').first().click({ timeout: 10000 });
    await sleep(5000);
    const st = await p.evaluate(async () => { const c = window.mxMatrixClientPeg.get().getCrypto(); return { backup: await c.getActiveSessionBackupVersion(), ss: await c.isSecretStorageReady() }; });
    await p.keyboard.press("Escape");
    fs.writeFileSync(`${out}/recovery-${user}.txt`, key + "\n", { mode: 0o600 });
    log(`${user}: recovery key created, backup ${st.backup}, secret storage ${st.ss}`);
}

async function dm(a, b, n) {
    const pa = await open(a); const pb = await open(b);
    const enc = [{ type: "m.room.encryption", state_key: "", content: { algorithm: "m.megolm.v1.aes-sha2" } }];
    const room = await pa.evaluate(async ([who, enc]) => {
        const c = window.mxMatrixClientPeg.get();
        const r = (await c.createRoom({ preset: "trusted_private_chat", is_direct: true, invite: [who], initial_state: enc })).room_id;
        await c.setAccountData("m.direct", { [who]: [r] });
        return r;
    }, [`@${b}:psst.pro`, enc]);
    await pb.evaluate(async ([r, who]) => { const c = window.mxMatrixClientPeg.get(); await c.joinRoom(r); await c.setAccountData("m.direct", { [who]: [r] }); }, [room, `@${a}:psst.pro`]);
    await sleep(3000);
    for (let i = 1; i <= n; i++) await pa.evaluate(([r, t]) => window.mxMatrixClientPeg.get().sendTextMessage(r, t), [room, `Stará správa ${i} pred overením: tajné číslo ${1000 + i}`]);
    fs.writeFileSync(`${out}/room-${a}-${b}.txt`, room);
    log(`dm ${room}: ${n} messages from ${a}`);
}

async function clickText(p, re) {
    const rx = new RegExp(re, "i");
    for (let i = 0; i < 15; i++) {
        const cands = p.locator("button, [role=button], a, .mx_AccessibleButton");
        const count = await cands.count();
        for (let k = 0; k < count; k++) {
            const el = cands.nth(k);
            const t = ((await el.innerText().catch(() => "")) || (await el.getAttribute("aria-label").catch(() => "")) || "").trim();
            if (t && rx.test(t) && await el.isVisible().catch(() => false)) { await el.click(); return t; }
        }
        await sleep(1000);
    }
    throw new Error(`no visible button matching ${re}`);
}

async function qrShot(user, file) {
    const p = await open(user);
    const qr = p.locator(".mx_VerificationQRCode, .mx_QRCode, canvas, img[alt*='QR' i]").first();
    await qr.waitFor({ timeout: 30000 });
    await sleep(500);
    await qr.screenshot({ path: file });
    log(`${user}: QR code → ${file}`);
}

async function verifyOther(user) {
    const p = await open(user);
    await settingsTab(p, "Devices").catch(async () => { await settingsTab(p, "Sessions"); });
    await clickText(p, "^Verify session$|^Verify$");
    log(`${user}: verify session clicked`);
}

async function texts(user) {
    const p = await open(user);
    const t = await p.locator(".mx_Dialog, .mx_Toast_toast, .mx_RightPanel, .mx_CompleteSecurity").allInnerTexts().catch(() => []);
    log(`${user}: ${JSON.stringify(t.map((x) => x.replace(/\s+/g, " ").slice(0, 300)))}`);
}

log("READY");
fs.writeFileSync(`${out}/READY`, String(Date.now()));
for (;;) {
    await sleep(500);
    if (!fs.existsSync(`${out}/NEXT`)) continue;
    const cmd = fs.readFileSync(`${out}/NEXT`, "utf8").trim(); fs.unlinkSync(`${out}/NEXT`);
    log("cmd " + cmd.slice(0, 120));
    const [verb, a1, a2, ...rest] = cmd.split(" ");
    try {
        if (verb === "quit") break;
        if (verb === "login") await open(a1);
        if (verb === "recovery") await recovery(a1);
        if (verb === "dm") await dm(a1, a2, Number(rest[0]));
        if (verb === "shot") await (await open(a1)).screenshot({ path: `${out}/shot-${a1}.png` });
        if (verb === "qr") await qrShot(a1, a2);
        if (verb === "click") log(`clicked "${await clickText(await open(a1), [a2, ...rest].join(" "))}"`);
        if (verb === "verify-other") await verifyOther(a1);
        if (verb === "texts") await texts(a1);
        if (verb === "mas-approve") {
            const pages = (await open(a1)).context().pages();
            const m = pages.find((x) => /chat\.psst\.pro/.test(x.url()));
            if (!m) throw new Error(`no MAS tab: ${pages.map((x) => x.url()).join(", ")}`);
            await m.bringToFront();
            for (let i = 0; i < 15; i++) {
                const real = a1.split("#")[0];
                if (await m.locator('input[name="username"]').count()) {
                    await m.fill('input[name="username"]', real); await m.fill('input[name="password"]', acc[real]);
                } else {
                    const inp = m.locator("input:not([type=hidden])");
                    if (a2 && await inp.count()) await inp.first().fill(a2).catch(() => {});
                }
                const b = m.locator('button:has-text("Grant"), button:has-text("Allow"), button:has-text("Continue"), button:has-text("Approve"), button[type=submit]');
                log(`mas controls: ${JSON.stringify(await m.locator("button, input[type=submit], a").evaluateAll((els) => els.map((e) => (e.innerText || e.value || "").trim()).filter(Boolean)).catch(() => []))}`);
                const grant = m.locator('button:has-text("Grant access"), input[type=submit][value*="Grant" i], button:has-text("Allow access")');
                if (await grant.count() || await m.getByText("Grant access", { exact: true }).count()) {
                    await m.locator("input[type=checkbox]").first().check().catch(() => {});
                    await m.getByText("Grant access", { exact: true }).first().click({ force: true }).catch((e) => log(`grant click: ${e.message.split("\n")[0]}`));
                    await sleep(3000);
                    await m.screenshot({ path: `${out}/mas-${Date.now()}.png`, fullPage: true }).catch(() => {});
                    log(`mas after grant: ${(await m.innerText("body").catch(() => "closed")).replace(/\s+/g, " ").slice(0, 160)}`);
                    break;
                }
                if (await b.count()) await b.first().click().catch(() => {});
                await sleep(1500);
                if (m.isClosed() || /Access granted|device has been|You can close/i.test(await m.innerText("body").catch(() => ""))) break;
            }
            log(`mas: ${m.isClosed() ? "closed" : (await m.innerText("body").catch(() => "")).replace(/\s+/g, " ").slice(0, 200)}`);
        }
        if (verb === "eval") {
            const r = await (await open(a1)).evaluate(`(${fs.readFileSync(a2, "utf8")})()`);
            fs.writeFileSync(`${out}/eval.json`, JSON.stringify(r ?? null, null, 1));
            log(`eval → ${JSON.stringify(r ?? null).slice(0, 300)}`);
        }
    } catch (e) { log("ERR " + String(e.message).split("\n")[0]); }
    fs.writeFileSync(`${out}/DONE`, `${Date.now()} ${cmd.slice(0, 60)}`);
}
process.exit(0);
