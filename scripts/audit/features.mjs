// PSST feature audit (docs/FEATURE-MATRIX.md) — the same checks for every Element Web based client:
// Web (Chromium), Windows and macOS desktop (Electron over CDP). The client under test is `me`; `partner` and
// `third` are Element Web sessions of other test accounts, so E2EE runs in real clients on every side.
//
//   import { runFeatures } from "./features.mjs";
//   await runFeatures({ me, partner, third, users: {me, partner, third}, acc, out, record, platform, newMeSession })
//
// record(id, status, note): status "ok" | "fail" | "na" (cannot be verified here) | "upstream" (upstream limitation).
// The ids are the row ids of docs/FEATURE-MATRIX.md.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HS = "chat.macet.eu";
const FIX = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures");
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export const cli = (p, fn, arg) => p.evaluate(fn, arg);
export async function openRoom(p, roomId) {
    await p.evaluate((r) => { location.hash = `#/room/${r}`; }, roomId);
    await p.waitForSelector(".mx_RoomView", { timeout: 60000 });
    await sleep(2500);
    for (let i = 0; i < 2; i++) await p.keyboard.press("Escape").catch(() => {});
}
export async function compose(p, text, { enter = true } = {}) {
    const c = p.locator(".mx_RoomView .mx_BasicMessageComposer_input").last();
    await c.click();
    await c.pressSequentially(text, { delay: 5 });
    if (!enter) return;
    await p.keyboard.press("Enter");
    // a /command: the first Enter may only accept the autocomplete suggestion
    if (text.startsWith("/")) {
        await sleep(800);
        if ((await c.innerText().catch(() => "")).trim().startsWith("/")) await p.keyboard.press("Enter");
    }
}
/** Waits until event matching pred (serialized function source) exists in the room timeline of page p. */
export async function waitEvent(p, roomId, predSrc, timeout = 60000) {
    const t0 = Date.now();
    while (Date.now() - t0 < timeout) {
        const ev = await p.evaluate(([r, src]) => {
            const pred = eval(src);
            const room = window.mxMatrixClientPeg.get().getRoom(r);
            if (!room) return null;
            const e = room.getLiveTimeline().getEvents().find((x) => {
                const c = x.getClearContent?.() ?? x.getContent();
                return pred({ type: x.getType(), content: c ?? {}, sender: x.getSender(), redacted: x.isRedacted(), id: x.getId(), rel: x.getRelation?.() ?? c?.["m.relates_to"], ev: x });
            });
            return e ? { id: e.getId(), type: e.getType(), sender: e.getSender(), content: e.getClearContent?.() ?? e.getContent() } : null;
        }, [roomId, predSrc]).catch(() => null);
        if (ev) return ev;
        await sleep(1500);
    }
    return null;
}
const bodyIs = (b) => `(e) => e.content.body === ${JSON.stringify(b)}`;
const tileText = (p, text, timeout = 60000) =>
    p.locator(`.mx_EventTile_body:has-text("${text}"), .mx_EventTile:has-text("${text}")`).first().waitFor({ timeout }).then(() => true, () => false);

export async function dismiss(p) {
    for (const name of ["Not now", "Close", "OK", "Ok", "Later", "Got it", "Done"]) await p.getByRole("button", { name, exact: true }).first().click({ timeout: 600 }).catch(() => {});
    for (let i = 0; i < 2; i++) await p.keyboard.press("Escape").catch(() => {});
}
async function hookNotifications(p) {
    await p.evaluate(() => {
        window.__psstNotes = window.__psstNotes || [];
        if (window.__psstHooked) return; window.__psstHooked = true;
        const N = window.Notification;
        window.Notification = function (title, opts) { window.__psstNotes.push({ title, body: opts?.body, t: Date.now() }); return new N(title, opts); };
        Object.assign(window.Notification, N); window.Notification.prototype = N.prototype;
        // headless Chromium answers "denied" regardless of the granted permission → behave like a browser where
        // the user clicked "Allow" (Element's own logic — toast, setting, per-room rules — is what is tested)
        Object.defineProperty(window.Notification, "permission", { get: () => "granted" });
        Object.defineProperty(window.Notification, "requestPermission", { value: async () => "granted" });
    });
}
const notes = (p) => p.evaluate(() => (window.__psstNotes || []).length).catch(() => -1);

// ------------------------------------------------------------------------------------------- calls
async function frameClick(p, selector, tries = 20) {
    for (let i = 0; i < tries; i++) {
        for (const f of p.frames()) {
            const l = f.locator(selector);
            if (await l.count().catch(() => 0)) { await l.first().click().catch(() => {}); return true; }
        }
        await sleep(1500);
    }
    return false;
}
export async function startCall(p, roomId, kind = "Video call") {
    await openRoom(p, roomId);
    await p.locator(`[aria-label="${kind}"], [aria-label="Video call"], [aria-label="Voice call"]`).first().click({ timeout: 30000 });
    await sleep(2500);
    await p.locator('[role=menuitem]:has-text("Element Call"), [role=menuitem]:has-text("psst")').first().click({ timeout: 2000 }).catch(() => {});
    return frameClick(p, '[data-testid="lobby_joinCall"], button:has-text("Join call")');
}
export async function joinFromToast(p) {
    const toast = p.locator('.mx_IncomingCallToast, .mx_Toast_toast:has-text("call"), .mx_Toast_toast:has-text("Call")').first();
    const seen = await toast.waitFor({ timeout: 60000 }).then(() => true, () => false);
    if (!seen) return { seen, joined: false };
    await toast.locator('button:has-text("Join"), button:has-text("Accept"), [aria-label="Join"]').first().click({ timeout: 10000 }).catch(() => {});
    await frameClick(p, '[data-testid="lobby_joinCall"], button:has-text("Join call")', 10);
    return { seen, joined: await inCall(p) };
}
async function inCall(p, tries = 30) {
    for (let i = 0; i < tries; i++) {
        for (const f of p.frames()) if (await f.locator('[data-testid="incall_leave"], button[aria-label="End call"], button[aria-label="Leave"]').count().catch(() => 0)) return true;
        await sleep(1500);
    }
    return false;
}
/** Media really flowing: a <video> with frames from another participant inside the Element Call frame. */
export async function remoteVideo(p, minTracks = 1, tries = 20) {
    let best = { playing: 0, total: 0 };
    for (let i = 0; i < tries; i++) {
        for (const f of p.frames()) {
            const r = await f.evaluate(() => {
                const v = [...document.querySelectorAll("video")];
                return { playing: v.filter((x) => x.videoWidth > 0 && !x.paused && x.readyState >= 2).length, total: v.length };
            }).catch(() => null);
            if (r && r.playing > best.playing) best = r;
        }
        if (best.playing >= minTracks + 1 || (best.playing >= minTracks && i > 6)) break; // own preview + remote
        await sleep(2000);
    }
    return best;
}
/** ICE path of the call: selected candidate pairs (needs the RTCPeerConnection hook from installPcHook). */
export async function icePaths(p) {
    const out = [];
    for (const f of p.frames()) {
        const r = await f.evaluate(async () => {
            const res = [];
            for (const pc of window.__psstPcs || []) {
                if (pc.connectionState === "closed") continue;
                const st = await pc.getStats();
                st.forEach((s) => {
                    if (s.type === "candidate-pair" && s.nominated && s.state === "succeeded") {
                        const l = st.get(s.localCandidateId), rm = st.get(s.remoteCandidateId);
                        res.push({ local: `${l?.candidateType}/${l?.protocol}${l?.relayProtocol ? "/" + l.relayProtocol : ""}`, remote: `${rm?.candidateType}/${rm?.protocol}:${rm?.port}`, bytes: s.bytesReceived });
                    }
                });
            }
            return res;
        }).catch(() => []);
        out.push(...r);
    }
    return out;
}
export const PC_HOOK = `(() => { if (window.__psstPcHook) return; window.__psstPcHook = 1; window.__psstPcs = [];
  const O = window.RTCPeerConnection; if (!O) return;
  window.RTCPeerConnection = function (...a) { const pc = new O(...a); window.__psstPcs.push(pc); return pc; };
  window.RTCPeerConnection.prototype = O.prototype; Object.setPrototypeOf(window.RTCPeerConnection, O); })();`;
export async function hangUp(...pages) {
    for (const p of pages) for (const f of p.frames()) await f.locator('[data-testid="incall_leave"], button[aria-label="End call"], button[aria-label="Leave"]').first().click({ timeout: 1500 }).catch(() => {});
    await sleep(4000);
}

// ------------------------------------------------------------------------------------------- suite
export async function runFeatures(ctx) {
    const { me, partner, third, users, record, out, platform } = ctx;
    const ME = `@${users.me}:${HS}`, PA = `@${users.partner}:${HS}`, TH = `@${users.third}:${HS}`;
    const shot = (p, n) => p.screenshot({ path: path.join(out, `${platform}-${n}.png`) }).catch(() => {});
    const step = async (id, fn) => {
        await dismiss(me);
        try { await fn(); } catch (e) { record(id, "fail", "výnimka: " + String(e?.message || e).split("\n")[0].slice(0, 200)); await shot(me, `${id}-error`); }
        for (let i = 0; i < 2; i++) await me.keyboard.press("Escape").catch(() => {});
    };
    const state = {};

    // ---- 1:1 DM (created from the UI of the client under test: Start chat → partner)
    await step("dm", async () => {
        await dismiss(me);
        state.dm = await cli(me, async (who) => {
            const c = window.mxMatrixClientPeg.get();
            const r = await c.createRoom({ preset: "trusted_private_chat", is_direct: true, invite: [who],
                initial_state: [{ type: "m.room.encryption", state_key: "", content: { algorithm: "m.megolm.v1.aes-sha2" } }] });
            await c.setAccountData("m.direct", { [who]: [r.room_id] });
            return r.room_id;
        }, PA);
        await cli(partner, async ([r, who]) => { const c = window.mxMatrixClientPeg.get(); await c.joinRoom(r); await c.setAccountData("m.direct", { [who]: [r] }); return null; }, [state.dm, ME]);
        await sleep(5000);
        await openRoom(me, state.dm);
        const t1 = `dm me→partner ${Date.now()}`;
        await compose(me, t1);
        const got = await waitEvent(partner, state.dm, bodyIs(t1));
        const t2 = `dm partner→me ${Date.now()}`;
        await cli(partner, ([r, b]) => window.mxMatrixClientPeg.get().sendTextMessage(r, b), [state.dm, t2]);
        const seen = await tileText(me, t2);
        const enc = await cli(me, (r) => window.mxMatrixClientPeg.get().getCrypto().isEncryptionEnabledInRoom(r), state.dm);
        const utd = await me.locator(".mx_DecryptionFailureBody, .mx_EventTile_decryptionFailure").count();
        await shot(me, "dm");
        record("dm", got && seen && enc && !utd ? "ok" : "fail", `šifrovaná DM, odoslanie ${!!got}, príjem ${seen}, E2EE ${enc}, nedešifrované ${utd}`);
        state.lastMine = got?.id;
    });

    // ---- read receipts + typing (partner acts, me renders)
    await step("receipts", async () => {
        const id = state.lastMine;
        await cli(partner, async ([r, id]) => { const c = window.mxMatrixClientPeg.get(); const ev = c.getRoom(r).findEventById(id); if (ev) await c.sendReadReceipt(ev); }, [state.dm, id]);
        const ok = await me.locator(".mx_ReadReceiptGroup .mx_BaseAvatar, .mx_ReadReceiptGroup_button").first().waitFor({ timeout: 30000 }).then(() => true, () => false);
        record("receipts", ok ? "ok" : "fail", ok ? "avatar partnera pri prečítanej správe" : "potvrdenie o prečítaní sa nezobrazilo");
    });
    await step("typing", async () => {
        await cli(partner, (r) => window.mxMatrixClientPeg.get().sendTyping(r, true, 20000), state.dm);
        const ok = await me.locator(".mx_WhoIsTypingTile, .mx_RoomView_typingNotif:has-text('typing'), :text('is typing')").first().waitFor({ timeout: 20000 }).then(() => true, () => false);
        await cli(partner, (r) => window.mxMatrixClientPeg.get().sendTyping(r, false), state.dm);
        record("typing", ok ? "ok" : "fail", ok ? "„… is typing“ sa zobrazilo" : "indikátor písania sa nezobrazil");
    });

    // ---- reply, reaction, edit, delete (UI of me)
    const lastTile = (text) => me.locator(`.mx_EventTile:has-text("${text}")`).last();
    await step("reply", async () => {
        const base = `reply-base ${Date.now()}`;
        await cli(partner, ([r, b]) => window.mxMatrixClientPeg.get().sendTextMessage(r, b), [state.dm, base]);
        await tileText(me, base);
        await lastTile(base).hover();
        await lastTile(base).locator('[aria-label="Reply"]').first().click({ timeout: 10000 });
        const t = `reply ${Date.now()}`;
        await compose(me, t);
        const ev = await waitEvent(partner, state.dm, `(e) => e.content.body?.includes(${JSON.stringify(t)})`);
        const ok = !!ev?.content?.["m.relates_to"]?.["m.in_reply_to"]?.event_id;
        record("reply", ok ? "ok" : "fail", ok ? "odpoveď s odkazom na pôvodnú správu prišla partnerovi" : "odpoveď bez m.in_reply_to");
        state.replyBase = base;
    });
    await step("reaction", async () => {
        const base = state.replyBase;
        await lastTile(base).hover();
        await lastTile(base).locator('[aria-label="React"]').first().click({ timeout: 10000 });
        const search = me.locator('input[aria-label="Search"][aria-haspopup="grid"]').first();
        await search.waitFor({ state: "visible", timeout: 10000 });
        await search.fill("thumbs up");
        await sleep(800);
        await me.keyboard.press("Enter");
        const ev = await waitEvent(partner, state.dm, `(e) => e.type === "m.reaction" && e.content?.["m.relates_to"]?.key?.startsWith("👍")`);
        record("reaction", ev ? "ok" : "fail", ev ? "reakcia 👍 prišla partnerovi" : "reakcia neprišla");
    });
    await step("edit", async () => {
        const t = `edit-me ${Date.now()}`;
        await compose(me, t);
        await waitEvent(partner, state.dm, bodyIs(t));
        await lastTile(t).hover();
        await lastTile(t).locator('[aria-label="Edit"]').first().click({ timeout: 10000 });
        const ed = me.locator(".mx_EditMessageComposer .mx_BasicMessageComposer_input").first();
        await ed.click(); await me.keyboard.press("End"); await ed.pressSequentially(" EDITED"); await me.keyboard.press("Enter");
        const ev = await waitEvent(partner, state.dm, `(e) => e.content?.["m.relates_to"]?.rel_type === "m.replace" && e.content?.["m.new_content"]?.body?.endsWith("EDITED")`);
        record("edit", ev ? "ok" : "fail", ev ? "úprava (m.replace) prišla partnerovi" : "úprava neprišla");
        state.editText = t;
    });
    await step("delete", async () => {
        const t = `delete-me ${Date.now()}`;
        await compose(me, t);
        const orig = await waitEvent(partner, state.dm, bodyIs(t));
        await lastTile(t).hover();
        await lastTile(t).locator('[aria-label="Options"]').first().click({ timeout: 10000 });
        await me.locator('[role=menuitem]:has-text("Remove")').first().click({ timeout: 10000 });
        await me.locator('.mx_Dialog button:has-text("Remove")').first().click({ timeout: 10000 });
        let red = false;
        for (let i = 0; i < 30 && !red; i++) {
            red = await cli(partner, ([r, id]) => !!window.mxMatrixClientPeg.get().getRoom(r).findEventById(id)?.isRedacted(), [state.dm, orig?.id]);
            if (!red) await sleep(1500);
        }
        record("delete", red ? "ok" : "fail", red ? "správa zmazaná aj u partnera (redaction)" : "správa u partnera nezmazaná");
    });
    await step("mention", async () => {
        await compose(me, `hey @${users.partner.slice(0, 8)}`, { enter: false });
        await sleep(1500);
        await me.locator(".mx_Autocomplete .mx_Autocomplete_Completion, .mx_Autocomplete_Completion_pill").first().click({ timeout: 10000 });
        await me.keyboard.press("Enter");
        const ev = await waitEvent(partner, state.dm, `(e) => (e.content?.["m.mentions"]?.user_ids || []).includes(${JSON.stringify(PA)})`);
        const hl = await cli(partner, (r) => window.mxMatrixClientPeg.get().getRoom(r).getUnreadNotificationCount("highlight"), state.dm);
        record("mention", ev ? "ok" : "fail", ev ? `zmienka (pill, m.mentions) prišla; highlight u partnera ${hl}` : "zmienka neprišla");
    });

    // ---- files, images, video, voice message
    const upload = async (file) => {
        await me.locator(".mx_MessageComposer input[type=file], input[type=file]").first().setInputFiles(file);
        await me.locator('.mx_Dialog button:has-text("Upload")').first().click({ timeout: 20000 });
    };
    await step("file", async () => {
        const name = `psst-audit-${Date.now()}.txt`;
        await upload({ name, mimeType: "text/plain", buffer: Buffer.from("psst audit file\n") });
        const ev = await waitEvent(partner, state.dm, bodyIs(name));
        const ok = !!ev?.content?.file && ev.content.msgtype === "m.file";
        const dl = ok && await cli(partner, async (f) => { // download + decrypt like the client does
            const c = window.mxMatrixClientPeg.get();
            const url = c.mxcUrlToHttp(f.url, undefined, undefined, undefined, false, true, true);
            const r = await fetch(url, { headers: { Authorization: `Bearer ${c.getAccessToken()}` } });
            return r.ok;
        }, ev.content.file);
        record("file", ok && dl ? "ok" : "fail", `šifrovaný súbor ${ok}, stiahnutie (authenticated media) ${dl}`);
    });
    await step("image", async () => {
        const name = `psst-audit-${Date.now()}.png`;
        await upload({ name, mimeType: "image/png", buffer: fs.readFileSync(path.join(FIX, "psst-test.png")) });
        const ev = await waitEvent(partner, state.dm, bodyIs(name));
        const thumb = await partner.locator(".mx_MImageBody img").last().waitFor({ timeout: 30000 }).then(() => true, () => false);
        record("image", ev?.content?.msgtype === "m.image" ? "ok" : "fail", `m.image ${ev?.content?.msgtype === "m.image"}, ${ev?.content?.info?.w}×${ev?.content?.info?.h}, náhľad u partnera ${thumb}`);
    });
    await step("video", async () => {
        const name = `psst-audit-${Date.now()}.mp4`;
        await upload({ name, mimeType: "video/mp4", buffer: fs.readFileSync(path.join(FIX, "psst-test.mp4")) });
        const ev = await waitEvent(partner, state.dm, bodyIs(name));
        record("video", ev?.content?.msgtype === "m.video" ? "ok" : "fail", `m.video ${ev?.content?.msgtype}, trvanie ${ev?.content?.info?.duration} ms`);
    });
    await step("voice", async () => {
        const btn = me.locator('[aria-label="Voice Message"], [aria-label="Voice message"]').first();
        if (!(await btn.count())) await me.locator('[aria-label="More options"]').last().click({ timeout: 5000 }).catch(() => {});
        await me.locator('[aria-label="Voice Message"], [aria-label="Voice message"], [role=menuitem]:has-text("Voice Message")').first().click({ timeout: 10000 });
        await sleep(4000);
        await me.locator('.mx_MessageComposer_sendMessage, [aria-label="Send voice message"], [aria-label="Send message"]').first().click({ timeout: 10000 });
        const ev = await waitEvent(partner, state.dm, `(e) => !!e.content?.["org.matrix.msc3245.voice"] || !!e.content?.["org.matrix.msc3245.voice.v2"]`);
        record("voice", ev ? "ok" : "fail", ev ? `hlasová správa (msc3245), ${ev.content?.info?.duration} ms` : "hlasová správa neprišla");
    });

    // ---- search
    await step("search", async () => {
        const word = `hladaj${Date.now() % 100000}`;
        await compose(me, `slovo ${word}`);
        await waitEvent(partner, state.dm, `(e) => e.content.body?.includes(${JSON.stringify(word)})`);
        await sleep(3000);
        const seshat = await cli(me, () => !!window.mxPlatformPeg?.get?.()?.supportsEventIndexing?.());
        await me.locator('[aria-label="Room info"]').first().click({ timeout: 10000 }).catch(() => {});
        await sleep(1000);
        const searchBox = me.locator('.mx_RightPanel input[placeholder*="Search"], .mx_RoomSummaryCard_search input, input[placeholder="Search messages…"]').first();
        await searchBox.click({ timeout: 10000 }); await searchBox.fill(word); await me.keyboard.press("Enter");
        const found = await me.locator(`.mx_RoomView_searchResultsPanel .mx_EventTile:has-text("${word}"), .mx_SearchResultTile:has-text("${word}")`).first().waitFor({ timeout: 30000 }).then(() => true, () => false);
        await shot(me, "search");
        await me.keyboard.press("Escape").catch(() => {});
        if (found) record("search", "ok", seshat ? "vyhľadávanie v šifrovanej miestnosti cez lokálny index (Seshat)" : "výsledok nájdený");
        else record("search", seshat ? "fail" : "upstream", seshat ? "Seshat je k dispozícii, ale výsledok sa nenašiel" : "web: šifrované miestnosti server prehľadávať nemôže, Element Web nemá lokálny index (Seshat len desktop)");
        state.searchWord = word;
    });

    // ---- notifications (app open, other room / home)
    await step("notif_open", async () => {
        await hookNotifications(me);
        // Element Web asks with a toast ("Enable desktop notifications") → Enable = the "notificationsEnabled" device
        // setting (Settings → Notifications → "Enable desktop notifications for this session")
        if (!(await cli(me, () => window.mxSettingsStore?.getValue("notificationsEnabled")))) {
            const t = me.locator('.mx_Toast_toast:has-text("otification") button:has-text("Enable")').first();
            if (await t.count()) await t.click().catch(() => {});
            await cli(me, async () => { if (!window.mxSettingsStore.getValue("notificationsEnabled")) await window.mxSettingsStore.setValue("notificationsEnabled", null, "device", true); });
            await sleep(1500);
        }
        await me.evaluate(() => { location.hash = "#/home"; });
        await sleep(2000);
        const before = await notes(me);
        await cli(partner, ([r, b]) => window.mxMatrixClientPeg.get().sendTextMessage(r, b), [state.dm, `notify ${Date.now()}`]);
        let after = before; for (let i = 0; i < 30 && after <= before; i++) { await sleep(1000); after = await notes(me); }
        const enabled = await cli(me, () => window.mxSettingsStore?.getValue("notificationsEnabled"));
        record("notif_open", after > before ? "ok" : "fail", `notifikácia vytvorená ${before}→${after}, notifikácie zapnuté ${enabled}`);
    });

    // ---- group (3 members, encrypted) + invites from the UI (/invite)
    await step("group", async () => {
        state.group = await cli(me, async () => (await window.mxMatrixClientPeg.get().createRoom({ preset: "private_chat", name: "psst audit group",
            initial_state: [{ type: "m.room.encryption", state_key: "", content: { algorithm: "m.megolm.v1.aes-sha2" } }] })).room_id);
        await openRoom(me, state.group);
        for (const who of [PA, TH]) { await compose(me, `/invite ${who}`); await sleep(2500); await dismiss(me); }
        const invited = [];
        for (const [p, who] of [[partner, PA], [third, TH]]) {
            let inv = false;
            for (let i = 0; i < 20 && !inv; i++) { inv = await cli(p, (r) => window.mxMatrixClientPeg.get().getRoom(r)?.getMyMembership() === "invite", state.group); if (!inv) await sleep(1500); }
            invited.push(inv);
            if (inv) await cli(p, async (r) => { await window.mxMatrixClientPeg.get().joinRoom(r); }, state.group);
        }
        record("invite", invited.every(Boolean) ? "ok" : "fail", `pozvánka cez /invite doručená: ${invited.join(", ")}`);
        await sleep(5000);
        const t = `group me ${Date.now()}`;
        await compose(me, t);
        const g1 = await waitEvent(partner, state.group, bodyIs(t)), g2 = await waitEvent(third, state.group, bodyIs(t));
        const t2 = `group third ${Date.now()}`;
        await cli(third, ([r, b]) => window.mxMatrixClientPeg.get().sendTextMessage(r, b), [state.group, t2]);
        const g3 = await tileText(me, t2);
        const n = await cli(me, (r) => window.mxMatrixClientPeg.get().getRoom(r).getJoinedMemberCount(), state.group);
        await shot(me, "group");
        record("group", g1 && g2 && g3 && n === 3 ? "ok" : "fail", `3 členovia (${n}), šifrovaná, doručenie partner ${!!g1}, tretí ${!!g2}, príjem od tretieho ${g3}`);
    });

    // ---- member management + power levels (me is admin of the group)
    await step("members", async () => {
        await openRoom(me, state.group);
        await compose(me, `/op ${PA} 50`); await sleep(3000); await dismiss(me);
        const pl = await cli(partner, ([r, u]) => window.mxMatrixClientPeg.get().getRoom(r).getMember(u)?.powerLevel, [state.group, PA]);
        await compose(me, `/remove ${TH} audit`); await sleep(2000);
        await me.locator('.mx_Dialog button:has-text("Remove"), .mx_Dialog button:has-text("Continue")').first().click({ timeout: 3000 }).catch(() => {});
        let kicked = false;
        for (let i = 0; i < 20 && !kicked; i++) { kicked = await cli(third, (r) => window.mxMatrixClientPeg.get().getRoom(r)?.getMyMembership() === "leave", state.group); if (!kicked) await sleep(1500); }
        record("members", pl === 50 && kicked ? "ok" : "fail", `partner povýšený na moderátora (PL ${pl}), tretí odstránený ${kicked}`);
    });

    // ---- public channel: partner publishes, me finds it in Explore and joins from the UI
    await step("public", async () => {
        const alias = `psst-audit-${Date.now() % 1000000}`;
        state.pub = await cli(partner, async (a) => (await window.mxMatrixClientPeg.get().createRoom({ preset: "public_chat", visibility: "public", name: `Audit kanal ${a}`, room_alias_name: a })).room_id, alias);
        await sleep(3000);
        await me.evaluate(() => { location.hash = "#/directory"; });
        await me.locator('.mx_SpotlightDialog input, input[placeholder*="Search"]').first().fill(`Audit kanal ${alias}`, { timeout: 15000 });
        const hit = me.locator(`.mx_SpotlightDialog_result_publicRoomDetails:has-text("${alias}"), [role=option]:has-text("${alias}")`).first();
        const found = await hit.waitFor({ timeout: 30000 }).then(() => true, () => false);
        await shot(me, "directory");
        if (found) { await hit.locator('button:has-text("Join"), button:has-text("View")').first().click().catch(() => hit.click()); }
        let joined = false;
        for (let i = 0; i < 20 && !joined; i++) { joined = await cli(me, (r) => window.mxMatrixClientPeg.get().getRoom(r)?.getMyMembership() === "join", state.pub); if (!joined) { await me.locator('.mx_RoomPreviewBar button:has-text("Join")').first().click({ timeout: 1000 }).catch(() => {}); await sleep(1500); } }
        await me.keyboard.press("Escape").catch(() => {});
        record("public", found && joined ? "ok" : "fail", `kanál nájdený v adresári ${found}, pripojenie ${joined}`);
        // unencrypted public room → server-side search works on every platform
        if (joined) {
            const w = `verejne${Date.now() % 100000}`;
            await cli(partner, ([r, b]) => window.mxMatrixClientPeg.get().sendTextMessage(r, b), [state.pub, `kanal ${w}`]);
            await sleep(3000);
            const res = await cli(me, async (w) => (await window.mxMatrixClientPeg.get().searchRoomEvents({ term: w })).results.length, w);
            record("search_public", res > 0 ? "ok" : "fail", `serverové vyhľadávanie v nešifrovanom kanáli: ${res} výsledkov`);
        }
    });

    // ---- calls (Element Call): 1:1 voice, 1:1 video (partner rings me), group call, screen share
    await step("call_video", async () => {
        await me.evaluate(() => { location.hash = "#/home"; });
        await startCall(partner, state.dm, "Video call");
        const r = await joinFromToast(me);
        const v = r.joined ? await remoteVideo(me, 1) : { playing: 0 };
        state.callPaths = r.joined ? await icePaths(me) : [];
        await shot(me, "call-video");
        record("call_video", r.seen && r.joined && v.playing >= 1 ? "ok" : "fail", `zvonenie/oznámenie ${r.seen}, pripojenie ${r.joined}, prehrávané video ${v.playing}/${v.total}; ICE ${JSON.stringify(state.callPaths.slice(0, 2))}`);
        // screen share from me while in the call
        if (r.joined) {
            const shared = await frameClick(me, '[data-testid="incall_screenshare"], button[aria-label="Share screen"]', 5);
            await sleep(6000);
            const pv = await remoteVideo(partner, 2, 8);
            record("screenshare", shared && pv.playing >= 2 ? "ok" : (shared ? "fail" : "fail"), `tlačidlo zdieľania ${shared}, u partnera prehrávané videá ${pv.playing}/${pv.total}`);
        }
        await hangUp(me, partner);
    });
    await step("call_voice", async () => {
        await me.evaluate(() => { location.hash = "#/home"; });
        await startCall(partner, state.dm, "Voice call");
        const r = await joinFromToast(me);
        let audio = false;
        if (r.joined) for (const f of me.frames()) audio ||= await f.evaluate(() => [...document.querySelectorAll("audio, video")].some((m) => m.srcObject?.getAudioTracks?.().some((t) => t.readyState === "live"))).catch(() => false);
        record("call_voice", r.seen && r.joined ? "ok" : "fail", `oznámenie ${r.seen}, pripojenie ${r.joined}, živá zvuková stopa ${audio}`);
        await hangUp(me, partner);
    });
    await step("call_group", async () => {
        // the group lost `third` in "members"; re-invite third and use a fresh group for the call
        const g = await cli(partner, async (who) => (await window.mxMatrixClientPeg.get().createRoom({ preset: "private_chat", name: "psst audit call", invite: who })).room_id, [ME, TH]);
        await cli(me, async (r) => { await window.mxMatrixClientPeg.get().joinRoom(r); }, g);
        await cli(third, async (r) => { await window.mxMatrixClientPeg.get().joinRoom(r); }, g);
        await sleep(4000);
        await startCall(partner, g, "Video call");
        await me.evaluate(() => { location.hash = "#/home"; });
        const r = await joinFromToast(me);
        await startCall(third, g, "Video call");
        const v = r.joined ? await remoteVideo(me, 2) : { playing: 0 };
        await shot(me, "call-group");
        record("call_group", r.seen && r.joined && v.playing >= 2 ? "ok" : "fail", `oznámenie ${r.seen}, pripojenie ${r.joined}, video od ${v.playing} účastníkov (vrátane seba)`);
        await hangUp(me, partner, third);
    });

    // ---- profile + avatar (Settings → Account)
    await step("profile", async () => {
        const name = `QA ${platform} ${Date.now() % 10000}`;
        await cli(me, async (n) => window.mxMatrixClientPeg.get().setDisplayName(n), name); // UI field differs per version; avatar via UI
        await me.locator('[aria-label="User menu"]').first().click({ timeout: 15000 });
        await me.locator('[role=menuitem]:has-text("All settings")').first().click({ timeout: 15000 });
        await me.getByRole("tab", { name: "Account" }).first().click({ timeout: 15000 }).catch(() => {});
        await sleep(1500);
        await me.locator(".mx_UserProfileSettings input[type=file], .mx_AvatarSetting input[type=file], .mx_Dialog input[type=file]").first().setInputFiles(path.join(FIX, "psst-test.png"));
        await sleep(2000);
        await me.locator('.mx_Dialog button:has-text("Save"), .mx_Dialog button:has-text("Upload")').first().click({ timeout: 3000 }).catch(() => {});
        let prof = {};
        for (let i = 0; i < 15 && !(prof.avatar_url && prof.displayname === name); i++) {
            prof = await cli(partner, (u) => window.mxMatrixClientPeg.get().getProfileInfo(u), ME).catch(() => ({}));
            if (!(prof.avatar_url && prof.displayname === name)) await sleep(2000);
        }
        await shot(me, "profile");
        await me.keyboard.press("Escape");
        record("profile", prof.displayname === name && !!prof.avatar_url ? "ok" : "fail", `meno „${prof.displayname}“, avatar ${prof.avatar_url ? "nastavený" : "chýba"} (partner vidí)`);
    });

    // ---- sessions + password change links (Settings → Sessions / Account → MAS)
    await step("sessions", async () => {
        await me.locator('[aria-label="User menu"]').first().click({ timeout: 15000 });
        await me.locator('[role=menuitem]:has-text("All settings")').first().click({ timeout: 15000 });
        await me.getByRole("tab", { name: /^(Sessions|Devices)$/ }).first().click({ timeout: 15000 });
        await sleep(3000);
        const txt = (await me.locator(".mx_Dialog").innerText()).replace(/\s+/g, " ");
        const current = /Current (session|device)|This device/i.test(txt);
        const manage = await me.locator('.mx_Dialog a[href*="/auth/account"], .mx_Dialog button:has-text("Manage")').count();
        await shot(me, "sessions");
        await me.keyboard.press("Escape");
        record("sessions", current ? "ok" : "fail", `zoznam relácií: aktuálna ${current}; správa ostatných cez MAS (odkaz ${manage > 0})`);
    });

    // ---- block (ignore) user
    await step("block", async () => {
        await cli(me, (u) => window.mxMatrixClientPeg.get().setIgnoredUsers([u]), PA);
        await sleep(3000);
        const t = `ignored ${Date.now()}`;
        await cli(partner, ([r, b]) => window.mxMatrixClientPeg.get().sendTextMessage(r, b), [state.dm, t]);
        await openRoom(me, state.dm);
        await sleep(8000);
        const shown = await me.locator(`.mx_EventTile_body:has-text("${t}")`).count();
        const ignored = await cli(me, () => window.mxMatrixClientPeg.get().getIgnoredUsers());
        await cli(me, () => window.mxMatrixClientPeg.get().setIgnoredUsers([]));
        record("block", ignored.includes(PA) && shown === 0 ? "ok" : "fail", `zablokovaný ${ignored.includes(PA)}, jeho nová správa skrytá ${shown === 0}`);
    });

    // ---- leave room (UI: /leave) — the public channel
    await step("leave", async () => {
        if (!state.pub) throw new Error("no public room");
        await openRoom(me, state.pub);
        await me.locator('[aria-label="Room info"]').first().click({ timeout: 10000 });
        await me.getByText(/^Leave room$/).first().click({ timeout: 10000 });
        await me.locator('.mx_Dialog button:has-text("Leave")').first().click({ timeout: 10000 });
        let left = false;
        for (let i = 0; i < 20 && !left; i++) { left = await cli(me, (r) => window.mxMatrixClientPeg.get().getRoom(r)?.getMyMembership() !== "join", state.pub); if (!left) await sleep(1000); }
        record("leave", left ? "ok" : "fail", left ? "miestnosť opustená" : "stále člen");
    });

    return state;
}

/** Writes result.json + a markdown table. */
export function writeResults(out, platform, results) {
    fs.writeFileSync(path.join(out, `${platform}-result.json`), JSON.stringify(results, null, 2));
    const md = [`| feature | ${platform} | note |`, "|---|---|---|", ...results.map((r) => `| ${r.id} | ${r.status} | ${r.note.replace(/\|/g, "/")} |`)].join("\n");
    fs.writeFileSync(path.join(out, `${platform}-result.md`), md + "\n");
}

// ------------------------------------------------------------------------------------------- account flows
const APP_SEL = ".mx_LeftPanel, .mx_RoomListPanel, .mx_SpacePanel";
async function settingsTab(p, tab) {
    await dismiss(p);
    await p.locator('[aria-label="User menu"]').first().click({ timeout: 15000 });
    await p.locator('[role=menuitem]:has-text("All settings")').first().click({ timeout: 15000 });
    await p.getByRole("tab", { name: tab }).first().click({ timeout: 15000 });
    await sleep(2000);
}
export async function logoutUi(p, shot = async () => {}) {
    await p.evaluate(() => { location.hash = "#/home"; });
    await settingsTab(p, "Account");
    await p.getByRole("button", { name: /^(Sign out|Remove this device)$/ }).first().click({ timeout: 15000 });
    await sleep(2000);
    await shot(p, "logout-dialog");
    for (let i = 0; i < 3; i++) {
        const b = p.locator(".mx_Dialog").last().locator("button, [role=button]").filter({ hasText: /^(Continue to remove this device|Remove this device anyway|Sign out anyway|I don't want my encrypted messages|Sign out|Remove this device|Remove device)$/ }).first();
        if (await b.count()) { await b.click().catch(() => {}); await sleep(2000); } else break;
    }
    const ok = await p.waitForSelector(".mx_Login_fullWidthButton, .mx_AuthPage, .mx_Welcome", { timeout: 60000 }).then(() => true, () => false);
    if (!ok) await shot(p, "logout-stuck");
    return ok;
}
async function decryptedHistory(p) {
    return p.evaluate(async () => {
        const c = window.mxMatrixClientPeg.get();
        let enc = 0, ok = 0;
        for (const r of c.getRooms().filter((r) => r.getMyMembership() === "join")) {
            await c.scrollback(r, 50).catch(() => {});
            for (const e of r.getLiveTimeline().getEvents()) if (e.isEncrypted()) { enc++; if (!e.isDecryptionFailure() && (e.getClearContent()?.body || e.getClearContent()?.["m.relates_to"])) ok++; }
        }
        const s = await c.getCrypto().getDeviceVerificationStatus(c.getUserId(), c.getDeviceId());
        return { enc, ok, verified: !!s?.crossSigningVerified };
    });
}

/**
 * Recovery key, "Link new device" QR, emoji verification of a new web session, history on it, password link,
 * logout, sign in again with the recovery key and history from key backup.
 * ctx: { me, record, shot, platform, newWebSession: async () => {page, state}, loginMe: async () => state,
 *        getMe: () => Page (after re-login the desktop main window may be a new Page) }
 */
export async function runAccountFlows(ctx) {
    const { record, shot, platform } = ctx;
    let me = ctx.me;
    let recoveryKey = null;
    try {
        await settingsTab(me, "Encryption");
        await me.locator('button:has-text("Create recovery key"), button:has-text("Set up recovery")').first().click({ timeout: 15000 });
        const KEY = /(?:[1-9A-HJ-NP-Za-km-z]{4}\s){11}[1-9A-HJ-NP-Za-km-z]{4}/;
        for (let i = 0; i < 10 && !recoveryKey; i++) {
            await sleep(1500);
            recoveryKey = (KEY.exec(await me.locator(".mx_Dialog").innerText()) || [null])[0];
            if (!recoveryKey) await me.locator('.mx_Dialog button:has-text("Continue")').first().click({ timeout: 2000 }).catch(() => {});
        }
        if (!recoveryKey) throw new Error("recovery key not shown");
        await me.locator('.mx_Dialog button:has-text("Continue")').first().click({ timeout: 10000 });
        await sleep(1500);
        await me.locator(".mx_Dialog input:not([type=hidden]), .mx_Dialog textarea").last().fill(recoveryKey);
        await me.locator('.mx_Dialog button:has-text("Finish set up"), .mx_Dialog button:has-text("Continue")').first().click({ timeout: 10000 });
        await sleep(5000);
        const st = await cli(me, async () => { const c = window.mxMatrixClientPeg.get().getCrypto(); return { backup: await c.getActiveSessionBackupVersion(), ss: await c.isSecretStorageReady() }; });
        await me.keyboard.press("Escape");
        record("recovery", st.backup && st.ss ? "ok" : "fail", `Settings → Encryption → Create recovery key: kľúč vytvorený, záloha kľúčov verzia ${st.backup}, secret storage ${st.ss}`);
    } catch (e) { record("recovery", "fail", String(e.message).slice(0, 200)); await shot(me, "recovery-error"); }

    try {
        await dismiss(me);
        await me.locator('[aria-label="User menu"]').first().click({ timeout: 15000 });
        await me.locator('[role=menuitem]:has-text("Link new device")').first().click({ timeout: 10000 });
        await me.locator('button:has-text("Show QR code"), button:has-text("Mobile device")').first().click({ timeout: 10000 }).catch(() => {});
        const qr = await me.locator(".mx_LoginWithQR canvas, .mx_LoginWithQR img, .mx_QRCode, .mx_Dialog canvas").first().waitFor({ timeout: 30000 }).then(() => true, () => false);
        await shot(me, "qr");
        record("qr_login", qr ? "ok" : "fail", qr ? "„Link new device“ zobrazí QR na prihlásenie nového zariadenia (MSC4108); naskenovanie a prihlásenie overené Androidom" : "QR sa nezobrazil");
        for (let i = 0; i < 3; i++) await me.keyboard.press("Escape");
    } catch (e) { record("qr_login", "fail", String(e.message).slice(0, 200)); }

    try {
        await settingsTab(me, "Account");
        const href = await me.locator('.mx_Dialog a:has-text("Manage account")').first().getAttribute("href", { timeout: 10000 });
        record("password", href && href.includes("/auth/account") ? "ok" : "fail", `Settings → Account → „Manage account“ → ${href} (MAS: Change password; zmena hesla overená na Androide)`);
        await me.keyboard.press("Escape");
    } catch (e) { record("password", "fail", String(e.message).slice(0, 200)); }

    let second = null;
    try {
        const s2 = await ctx.newWebSession();
        second = s2.page;
        if (s2.state !== "identity") throw new Error("2nd session did not ask to confirm identity: " + s2.state);
        record("verify_unverified_state", (await second.locator(APP_SEL).count()) === 0 ? "ok" : "fail", "nová relácia (web) je zablokovaná na „Confirm your digital identity“, kým ju neoverí " + platform);
        await second.locator('button:has-text("Use another device")').click({ timeout: 15000 });
        const toast = me.locator('.mx_Toast_toast:has-text("Verification requested"), .mx_Toast_toast:has-text("verify")').first();
        const req = await toast.waitFor({ timeout: 60000 }).then(() => true, () => false);
        await toast.getByRole("button", { name: /^(Start Verification|Verify session|Verify|Accept)$/ }).first().click({ timeout: 10000 });
        for (let i = 0; i < 20; i++) {
            for (const p of [second, me]) await p.locator(".mx_Dialog").getByRole("button", { name: /^(Start|Verify by emoji)$/ }).first().click({ timeout: 1000 }).catch(() => {});
            if (await me.locator(".mx_VerificationShowSas_emojiSas").count() && await second.locator(".mx_VerificationShowSas_emojiSas").count()) break;
            await sleep(1500);
        }
        const e1 = (await me.locator(".mx_VerificationShowSas_emojiSas").innerText().catch(() => "")).replace(/\s+/g, " ");
        const e2 = (await second.locator(".mx_VerificationShowSas_emojiSas").innerText().catch(() => "")).replace(/\s+/g, " ");
        await shot(me, "verify-emoji");
        await me.getByRole("button", { name: "They match" }).first().click({ timeout: 10000 }).catch(() => {});
        await second.getByRole("button", { name: "They match" }).first().click({ timeout: 10000 }).catch(() => {});
        let verified = false;
        for (let i = 0; i < 30 && !verified; i++) {
            verified = await second.evaluate(async () => { const c = window.mxMatrixClientPeg.get(); return !!(await c.getCrypto().getDeviceVerificationStatus(c.getUserId(), c.getDeviceId()))?.crossSigningVerified; }).catch(() => false);
            if (!verified) await sleep(1500);
        }
        record("verify_emoji", req && e1 && e1 === e2 && verified ? "ok" : "fail", `${platform} (overené zariadenie) ↔ nová webová relácia: žiadosť doručená ${req}, emoji zhodné ${!!e1 && e1 === e2}, nová relácia cross-signed ${verified}`);
        for (let i = 0; i < 4; i++) { await second.getByRole("button", { name: /^(Done|Got it)$/ }).first().click({ timeout: 2000 }).catch(() => {}); await second.keyboard.press("Escape").catch(() => {}); }
        await me.getByRole("button", { name: /^(Done|Got it)$/ }).first().click({ timeout: 2000 }).catch(() => {});
        await sleep(8000);
        const old = await decryptedHistory(second);
        record("history_new_device", old.enc && old.ok === old.enc ? "ok" : (old.enc ? "fail" : "na"), `nová overená relácia: dešifrovaných ${old.ok}/${old.enc} starších šifrovaných správ`);
    } catch (e) { record("verify_emoji", "fail", String(e.message).slice(0, 200)); await shot(second || me, "verify-error"); }
    if (second) await second.context().close().catch(() => {});

    try {
        const out = await logoutUi(me, shot);
        record("logout", out ? "ok" : "fail", "Settings → Account → Remove this device → prihlasovacia obrazovka");
        const st = await ctx.loginMe();
        me = ctx.getMe ? await ctx.getMe() : me;
        if (st === "identity" && recoveryKey) {
            await me.locator('button:has-text("Use recovery key")').click({ timeout: 15000 });
            await sleep(1500);
            await me.locator(".mx_Dialog input:not([type=hidden]), .mx_Dialog textarea, input:not([type=hidden])").last().fill(recoveryKey);
            await me.getByRole("button", { name: "Continue" }).last().click({ timeout: 15000 });
            await me.getByRole("button", { name: /^(Done|Got it)$/ }).first().click({ timeout: 60000 }).catch(() => {});
            await me.waitForSelector(APP_SEL, { timeout: 60000 });
        }
        await sleep(15000);
        const hist = await decryptedHistory(me);
        await shot(me, "relogin");
        record("relogin", st ? "ok" : "fail", `opätovné prihlásenie → ${st}${st === "identity" ? " → obnovovací kľúč" : ""}, relácia overená ${hist.verified}`);
        record("key_backup_restore", hist.verified && hist.enc && hist.ok >= hist.enc - 1 ? "ok" : "fail", `po prihlásení s obnovovacím kľúčom dešifrovaných ${hist.ok}/${hist.enc} starších správ`);
    } catch (e) { record("relogin", "fail", String(e.message).slice(0, 200)); await shot(me, "relogin-error"); }
    return me;
}
