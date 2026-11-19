// PSST produkcia: prihlási <user> do app.psst.pro (MAS), otvorí miestnosť a začne hovor (zvoní druhej strane).
//   node prod-ring.mjs <out> <roomId> <user> <pass> [sekúnd v hovore=40]
import { chromium } from "playwright";
import fs from "node:fs"; import path from "node:path";
const [out, roomId, user, pass, hold = "40"] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const b = await chromium.launch({ args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"] });
const ctx = await b.newContext({ viewport: { width: 1280, height: 860 }, permissions: ["camera", "microphone"] });
const p = await ctx.newPage();
await p.goto("https://app.psst.pro/#/login");
await p.locator('.mx_Login_fullWidthButton, button:has-text("Continue")').first().click({ timeout: 90000 });
await p.waitForURL(/chat\.macet\.eu\/auth/, { timeout: 60000 });
await p.fill('input[name="username"]', user); await p.fill('input[name="password"]', pass);
await p.locator("button[type=submit]").first().click();
for (let i = 0; i < 20 && !p.url().startsWith("https://app.psst.pro"); i++) {
    await p.locator('button[type=submit]:has-text("Continue"), button:has-text("Allow")').first().click({ timeout: 1500 }).catch(() => {});
    await p.waitForTimeout(1000);
}
await p.waitForSelector(".mx_LeftPanel, .mx_RoomListPanel, .mx_SpacePanel, .mx_AuthPage", { timeout: 120000 });
await p.waitForTimeout(6000);
await p.screenshot({ path: path.join(out, "ring-1-after-login.png") });
for (let i = 0; i < 4; i++) await p.keyboard.press("Escape").catch(() => {});
await p.goto(`https://app.psst.pro/#/room/${roomId}`);
await p.waitForSelector(".mx_RoomView", { timeout: 60000 }); await p.waitForTimeout(4000);
for (let i = 0; i < 2; i++) await p.keyboard.press("Escape").catch(() => {});
await p.locator('[aria-label="Video call"], [aria-label="Voice call"]').first().click({ timeout: 30000 });
await p.waitForTimeout(3000);
// prípadné menu (Element Call) a lobby
await p.locator('[role=menuitem]:has-text("Element Call"), [role=menuitem]:has-text("psst")').first().click({ timeout: 2000 }).catch(() => {});
for (let i = 0; i < 15; i++) {
    let done = false;
    for (const f of p.frames()) {
        const j = f.locator('[data-testid="lobby_joinCall"], button:has-text("Join call")');
        if (await j.count().catch(() => 0)) { await j.first().click().catch(() => {}); done = true; break; }
    }
    if (done) break; await p.waitForTimeout(1500);
}
console.log("CALL STARTED");
await p.waitForTimeout(8000); await p.screenshot({ path: path.join(out, "ring-2-in-call.png") });
await p.waitForTimeout(Number(hold) * 1000);
await b.close();
