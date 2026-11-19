// PSST iOS audit partner (runs next to the iOS simulator test on the CI runner, docs/FEATURE-MATRIX.md).
//   node ios-partner.mjs <out-dir> <accounts.json>      accounts: {"a": ios user, "b": partner}
// Element Web as `b`: joins every invite, answers "ping:<x>" with "pong:<x>", records what the iOS app sent
// (text, reply, reaction, edit, redaction, image, file). When it sees "VERIFY-NOW" it signs `a` in on a second web
// session (a new device) and asks the iOS app (the existing device) to verify it, accepting the emoji automatically.
// Writes <out-dir>/partner.json continuously; stops when it sees "AUDIT-DONE" or after 60 minutes.
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const [OUT, ACC_FILE] = process.argv.slice(2);
fs.mkdirSync(OUT, { recursive: true });
const A = JSON.parse(fs.readFileSync(ACC_FILE, "utf8"));
const WEB = "https://app.psst.pro", HS = "chat.psst.pro";
const SN = process.env.PSST_SERVER_NAME || "psst.pro";   // Matrix server_name (user IDs), D85
const IOS = `@${A.a.user}:${SN}`;
const state = { started: new Date().toISOString(), received: [], events: {}, verification: {}, log: [] };
const save = () => fs.writeFileSync(path.join(OUT, "partner.json"), JSON.stringify(state, null, 2));
const log = (s) => { console.log(s); state.log.push(`${new Date().toISOString().slice(11, 19)} ${s}`); save(); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await chromium.launch({ args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"] });

async function login(user, password) {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, permissions: ["camera", "microphone"] });
    const p = await ctx.newPage();
    await p.goto(`${WEB}/#/login`);
    await p.locator('button:has-text("Continue")').first().click({ timeout: 90000 });
    await p.waitForURL(/chat\.macet\.eu\/auth/, { timeout: 60000 });
    await p.fill('input[name="username"]', user); await p.fill('input[name="password"]', password);
    await p.locator("button[type=submit]").first().click();
    for (let i = 0; i < 20 && !p.url().startsWith(WEB); i++) { await p.locator('button[type=submit]:has-text("Continue")').first().click({ timeout: 1500 }).catch(() => {}); await sleep(1000); }
    for (let i = 0; i < 120; i++) {
        if (await p.getByText("Confirm your digital identity").count() || await p.locator(".mx_LeftPanel, .mx_RoomListPanel").count()) break;
        await sleep(1000);
    }
    await sleep(4000);
    const uid = await p.evaluate(() => window.mxMatrixClientPeg?.get()?.getUserId() ?? null).catch(() => null);
    if (!uid) throw new Error(`login of ${user} failed (no Matrix client after the MAS form; wrong password?)`);
    return p;
}

const b = await login(A.b.user, A.b.password);
log(`partner ${A.b.user} signed in (${await b.evaluate(() => window.mxMatrixClientPeg.get().getUserId())})`);
await b.evaluate(() => {
    const c = window.mxMatrixClientPeg.get();
    window.__seen = [];
    c.on("Room.myMembership", (room, m) => { if (m === "invite") c.joinRoom(room.roomId).catch(() => {}); });
    for (const r of c.getRooms()) if (r.getMyMembership() === "invite") c.joinRoom(r.roomId).catch(() => {});
    const rec = (e, room) => {
        const ev = e.getEffectiveEvent?.() ?? e.event;
        const content = e.getClearContent?.() ?? e.getContent();
        window.__seen.push({ id: e.getId(), type: e.getType(), sender: e.getSender(), room: room?.roomId ?? e.getRoomId(), content, redacts: ev?.redacts || content?.redacts, ts: Date.now() });
    };
    c.on("Room.timeline", (e, room) => { if (e.isEncrypted() && !e.getClearContent()) return; rec(e, room); });
    c.on("Event.decrypted", (e) => rec(e, c.getRoom(e.getRoomId())));
});

let aWeb = null;
const t0 = Date.now();
const answered = new Set();
while (Date.now() - t0 < 60 * 60 * 1000) {
    await sleep(2000);
    const seen = await b.evaluate((ios) => window.__seen.filter((x) => x.sender === ios), IOS).catch(() => []);
    for (const x of seen) {
        if (state.events[x.id]) continue;
        state.events[x.id] = { type: x.type, msgtype: x.content?.msgtype, body: x.content?.body, rel: x.content?.["m.relates_to"], newBody: x.content?.["m.new_content"]?.body, redacts: x.redacts, room: x.room };
        log(`from iOS: ${x.type} ${x.content?.msgtype || ""} ${(x.content?.body || x.content?.["m.relates_to"]?.key || x.redacts || "").toString().slice(0, 60)}`);
        const body = x.content?.body || "";
        const ping = /ping:(\S+)/.exec(body);
        if (ping && !answered.has(ping[1])) {
            answered.add(ping[1]);
            await b.evaluate(([r, t]) => window.mxMatrixClientPeg.get().sendTextMessage(r, t), [x.room, `pong:${ping[1]}`]);
            log(`answered pong:${ping[1]}`);
        }
        if (body.includes("READ-ME")) await b.evaluate(async ([r, id]) => { const c = window.mxMatrixClientPeg.get(); const e = c.getRoom(r)?.findEventById(id); if (e) await c.sendReadReceipt(e); }, [x.room, x.id]);
        if (body.includes("TYPE-NOW")) await b.evaluate((r) => window.mxMatrixClientPeg.get().sendTyping(r, true, 15000), x.room);
        if (body.includes("VERIFY-NOW") && !aWeb) {
            log("signing in the iOS user on a new web session (new device) → request verification from the iOS app");
            aWeb = await login(A.a.user, A.a.password);
            state.verification.identityScreen = await aWeb.getByText("Confirm your digital identity").count() > 0;
            await aWeb.getByRole("button", { name: "Use another device" }).first().click({ timeout: 20000 }).catch((e) => log("no Use another device: " + e.message));
            state.verification.requested = true; save();
            // accept emoji automatically (once) when the iOS side starts SAS, then confirm the result dialog
            (async () => {
                let clicked = false;
                for (let i = 0; i < 150; i++) {
                    await sleep(2000);
                    if (!clicked && await aWeb.locator(".mx_VerificationShowSas_emojiSas").count().catch(() => 0)) {
                        state.verification.emoji = (await aWeb.locator(".mx_VerificationShowSas_emojiSas").innerText()).replace(/\s+/g, " ");
                        state.verification.emojiNames = (await aWeb.locator(".mx_VerificationShowSas_emojiSas_label").allInnerTexts().catch(() => [])).map((x) => x.trim());
                        await aWeb.getByRole("button", { name: "They match", exact: true }).first().click({ timeout: 5000 }).catch((e) => log("They match click failed: " + e.message));
                        clicked = true; state.verification.webConfirmed = true;
                        log("web: emoji shown, clicked They match once: " + state.verification.emoji);
                    }
                    if (clicked) {
                        const dlg = await aWeb.locator(".mx_Dialog").last().innerText().catch(() => "");
                        if (dlg && dlg !== state.verification.lastDialog) { state.verification.lastDialog = dlg.replace(/\s+/g, " ").slice(0, 300); log("web dialog: " + state.verification.lastDialog); }
                        await aWeb.getByRole("button", { name: /^(Got it|Done|Continue|OK)$/ }).first().click({ timeout: 1000 }).catch(() => {});
                    }
                    const v = await aWeb.evaluate(async () => { const c = window.mxMatrixClientPeg.get(); return !!(await c.getCrypto().getDeviceVerificationStatus(c.getUserId(), c.getDeviceId()))?.crossSigningVerified; }).catch(() => false);
                    if (v) { state.verification.webVerified = true; log("web session of the iOS user is now verified (cross-signed)"); save(); return; }
                }
                log("verification did not complete on the web side");
            })();
        }
        if (body.includes("AUDIT-DONE")) { log("done"); save(); await browser.close(); process.exit(0); }
    }
    save();
}
log("timeout");
await browser.close();
