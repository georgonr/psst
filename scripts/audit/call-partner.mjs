// PSST audit helper: Element Web call partner for a mobile client (Android emulator / iOS simulator).
//   node call-partner.mjs <user> <password> <peer-mxid> <out-dir> [group-room-id]
// Signs in, opens (or creates) a DM with <peer-mxid>, then follows commands written to <out-dir>/NEXT:
//   call:video | call:voice   start a call in the DM (Element Call) and report media
//   answer                    wait for an incoming call toast and join it
//   media                     report remote video / audio and ICE path
//   hangup | quit
import { chromium } from "playwright";
import fs from "node:fs";
import { sleep, startCall, joinFromToast, remoteVideo, icePaths, hangUp, PC_HOOK, dismiss } from "./features.mjs";

const [user, password, peer, out, group] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const log = (s) => { const l = `[${new Date().toISOString().slice(11, 19)}] ${s}`; console.log(l); fs.appendFileSync(`${out}/log.txt`, l + "\n"); };
const b = await chromium.launch({ args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required"] });
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, permissions: ["camera", "microphone", "notifications"] });
await ctx.addInitScript(PC_HOOK);
const p = await ctx.newPage();
await p.goto("https://app.psst.pro/#/login");
await p.locator('button:has-text("Continue")').first().click({ timeout: 90000 });
await p.waitForURL(/auth/, { timeout: 60000 });
await p.fill('input[name="username"]', user); await p.fill('input[name="password"]', password);
await p.locator("button[type=submit]").first().click();
for (let i = 0; i < 20 && !p.url().startsWith("https://app.psst.pro"); i++) { await p.locator('button[type=submit]:has-text("Continue")').first().click({ timeout: 1500 }).catch(() => {}); await sleep(1000); }
for (let i = 0; i < 90; i++) { if (await p.locator(".mx_LeftPanel, .mx_RoomListPanel").count()) break; await sleep(1000); }
await sleep(4000); await dismiss(p);
// join pending invites (group calls: the room is created by another participant)
await p.evaluate(async () => { const c = window.mxMatrixClientPeg.get(); for (const r of c.getRooms()) if (r.getMyMembership() === "invite") await c.joinRoom(r.roomId).catch(() => {}); });
if (group) { await p.evaluate(async (r) => { await window.mxMatrixClientPeg.get().joinRoom(r).catch(() => {}); }, group); await sleep(3000); }
const dm = group || await p.evaluate(async (who) => {
    const c = window.mxMatrixClientPeg.get();
    const r = await c.createRoom({ preset: "trusted_private_chat", is_direct: true, invite: [who] });
    await c.setAccountData("m.direct", { [who]: [r.room_id] });
    return r.room_id;
}, peer);
log(`READY dm ${dm}`);
fs.writeFileSync(`${out}/READY`, dm);
for (;;) {
    await sleep(1000);
    if (!fs.existsSync(`${out}/NEXT`)) continue;
    const cmd = fs.readFileSync(`${out}/NEXT`, "utf8").trim(); fs.unlinkSync(`${out}/NEXT`);
    log("cmd " + cmd);
    try {
        if (cmd === "quit") break;
        if (cmd.startsWith("call:")) { await p.evaluate(() => { location.hash = "#/home"; }); const ok = await startCall(p, dm, cmd === "call:voice" ? "Voice call" : "Video call"); log(`started ${ok}`); }
        if (cmd === "answer") { await p.evaluate(() => { location.hash = "#/home"; }); const r = await joinFromToast(p); log(`answer ${JSON.stringify(r)}`); }
        if (cmd === "media") {
            const v = await remoteVideo(p, 1, 10);
            let audio = false;
            for (const f of p.frames()) audio ||= await f.evaluate(() => [...document.querySelectorAll("audio, video")].some((m) => m.srcObject?.getAudioTracks?.().some((t) => t.readyState === "live"))).catch(() => false);
            log(`media video ${v.playing}/${v.total} audio ${audio} ice ${JSON.stringify(await icePaths(p))}`);
            await p.screenshot({ path: `${out}/media-${Date.now()}.png` });
        }
        if (cmd === "hangup") await hangUp(p);
    } catch (e) { log("ERR " + String(e.message).split("\n")[0]); }
    fs.writeFileSync(`${out}/DONE`, String(Date.now()));
}
await b.close();
