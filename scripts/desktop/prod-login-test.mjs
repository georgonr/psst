// macOS desktop (psst.app) — skutočné prihlásenie cez MAS na produkcii.
// Hlavný proces: --inspect → zachytí shell.openExternal (URL MAS); prihlásenie v Playwright Chromiu;
// callback (vlastná schéma eu.macet.*) sa vráti appke cez app.emit("open-url").
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import fs from "node:fs"; import path from "node:path";
// Použitie: node prod-login-test.mjs <psst.app> <out-dir> <user> <password>   (skripty spúšťať z adresára s playwright)
const [app, out, user, pw] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const res = []; const check = (n, ok, d = "") => { res.push({ n, ok, d }); console.log(`${ok ? "PASS" : "FAIL"}  ${n}${d ? "  -- " + d : ""}`); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const profile = fs.mkdtempSync("/tmp/psst-desktop-prod-");
const proc = spawn(path.join(app, "Contents/MacOS/psst"), ["--remote-debugging-port=9333",
    "--use-mock-keychain", `--profile-dir=${profile}`], { stdio: ["ignore", "pipe", "pipe"] });
let log = ""; proc.stdout.on("data", (d) => (log += d)); proc.stderr.on("data", (d) => (log += d));
// inspector hlavného procesu je v release builde vypnutý (Electron fuse) → URL zachytíme v rendereri
// --- renderer
let browser; for (let i = 0; i < 60 && !browser; i++) { try { browser = await chromium.connectOverCDP("http://127.0.0.1:9333"); } catch { await sleep(1000); } }
let page; for (let i = 0; i < 60 && !page; i++) { page = browser?.contexts().flatMap((c) => c.pages()).find((p) => p.url().startsWith("vector://")); if (!page) await sleep(1000); }
check("appka spustená, hlavné okno", !!page, page?.url());
await page.waitForSelector(".mx_ServerPicker_server", { timeout: 90000 });
check("titulok okna psst", (await page.title()).toLowerCase().includes("psst"), await page.title());
check("server chat.macet.eu", (await page.locator(".mx_ServerPicker_server").innerText()).includes("chat.macet.eu"));
await page.screenshot({ path: path.join(out, "1-login.png") });
let authUrl = "";
page.on("request", (r) => { if (r.url().startsWith("https://chat.macet.eu/auth/authorize")) authUrl = r.url(); });
const cdp = await page.context().newCDPSession(page); await cdp.send("Page.enable");
cdp.on("Page.frameRequestedNavigation", (e) => { if (e.url.startsWith("https://chat.macet.eu/auth/")) authUrl = e.url; });
await page.evaluate(() => { window.__psstUrls = []; const o = window.open; window.open = (u, ...a) => { window.__psstUrls.push(String(u)); return null; }; });
const cont = page.getByText(/^(Pokračovať|Continue)$/).first();
await cont.evaluate((e) => e.click());
for (let i = 0; i < 30 && !authUrl; i++) { authUrl = await page.evaluate(() => window.__psstUrls[0] || "").catch(() => "") || authUrl; if (!authUrl) await sleep(1000); }
// --- prihlásenie v MAS (Playwright Chromium = "systémový prehliadač")
const b2 = await chromium.launch(); const p2 = await (await b2.newContext()).newPage();
let callback = "";
// fragment (#code=…) nie je v request URL → callback berieme z hlavičky Location presmerovania MAS
p2.on("response", async (r) => { const loc = (await r.allHeaders().catch(() => ({})))["location"] || ""; if (/^(eu\.macet\.|psst:)/.test(loc)) callback = loc; });

await p2.screenshot({ path: path.join(out, '2a-mas.png') }); await p2.fill('input[name="username"]', user, { timeout: 20000 }); await p2.fill('input[name="password"]', pw);
await p2.click('button[type=submit]');
for (let i = 0; i < 20 && !callback; i++) {
    await p2.locator('button[type=submit]:has-text("Continue")').first().click({ timeout: 2000 }).catch(() => {});
    await sleep(1500);
}
await p2.screenshot({ path: path.join(out, "2-mas.png") }).catch(() => {});
check("MAS: prihlásenie + súhlas → callback do appky", !!callback, callback.split("?")[0]);
await b2.close();
// --- callback späť do appky
// to isté, čo robí protocol.ts (handleDeeplink): vector://vector/webapp/ + search + hash
const cb = new URL(callback); const target = new URL("vector://vector/webapp/"); target.search = cb.search; target.hash = cb.hash;
await page.goto(target.href).catch(() => {});
await page.reload().catch(() => {});   // zmena len v hashi → Element spracuje OIDC callback až pri načítaní
let inApp = false; for (let i = 0; i < 60 && !inApp; i++) { inApp = (await page.locator(".mx_LeftPanel, .mx_RoomListPanel, .mx_SpacePanel").count()) > 0; if (!inApp) await sleep(1000); }
await sleep(3000); for (let i = 0; i < 3; i++) await page.keyboard.press("Escape").catch(() => {});
await page.screenshot({ path: path.join(out, "3-logged-in.png") });
const uid = await page.evaluate(() => { try { return window.mxMatrixClientPeg?.get()?.getUserId(); } catch { return null; } });
check("desktop prihlásený", inApp && uid === `@${user}:chat.macet.eu`, uid ?? "n/a");
fs.writeFileSync(path.join(out, "app.log"), log);
await browser?.close().catch(() => {}); proc.kill();
const fails = res.filter((r) => !r.ok).length; console.log(`\n${res.length - fails}/${res.length} checks passed`); process.exit(fails ? 1 : 0);
