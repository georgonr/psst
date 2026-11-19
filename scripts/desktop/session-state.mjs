// PSST (D85): which session does the desktop app restore from an existing profile?
//   node session-state.mjs <psst.app> <profile-dir> <out.png> [wait-seconds]
// Prints JSON {url, userId, homeserver, screen} — used to check what an updated app does with a session of the
// old server (before the move to psst.pro, D85): it must end on the sign-in screen of the new server, not hang.
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import path from "node:path";
const [app, profile, shot, waitS = "40"] = process.argv.slice(2);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const proc = spawn(path.join(app, "Contents/MacOS/psst"), ["--remote-debugging-port=9334", ...(process.env.PSST_REAL_KEYCHAIN ? [] : ["--use-mock-keychain"]),
    `--profile-dir=${profile}`], { stdio: "ignore" });
let browser; for (let i = 0; i < 60 && !browser; i++) { try { browser = await chromium.connectOverCDP("http://127.0.0.1:9334"); } catch { await sleep(1000); } }
let page; for (let i = 0; i < 60 && !page; i++) { page = browser?.contexts().flatMap((c) => c.pages()).find((p) => p.url().startsWith("vector://")); if (!page) await sleep(1000); }
const end = Date.now() + Number(waitS) * 1000;
let st = {};
while (Date.now() < end) {
    st = await page.evaluate(() => {
        let userId = null, homeserver = null;
        try { const c = window.mxMatrixClientPeg?.get(); userId = c?.getUserId() ?? null; homeserver = c?.getHomeserverUrl() ?? null; } catch {}
        const screen = document.querySelector(".mx_RoomListPanel, .mx_LeftPanel") ? "chats"
            : document.querySelector(".mx_ServerPicker_server") ? "login:" + document.querySelector(".mx_ServerPicker_server").innerText.trim()
            : document.querySelector(".mx_Spinner") ? "spinner" : document.body.innerText.slice(0, 120).replace(/\s+/g, " ");
        return { url: location.href, userId, homeserver, screen };
    }).catch((e) => ({ error: String(e) }));
    if (st.screen === "chats" || String(st.screen).startsWith("login:")) break;
    await sleep(2000);
}
await page.screenshot({ path: shot }).catch(() => {});
console.log(JSON.stringify(st));
await browser.close().catch(() => {}); proc.kill(); await sleep(1500); process.exit(0);
