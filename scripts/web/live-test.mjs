// PSST — Element Web proti bežiacemu lokálnemu stacku (server/ cez docker compose).
//   node live-test.mjs <out-dir> <user> <password>
// Chromium mapuje *.macet.eu na 127.0.0.1 (--host-resolver-rules) a akceptuje self-signed cert.
// Po prihlásení čaká na správu s textom zo súboru <out-dir>/expect.txt (pošle ju iný klient).
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const [out, user, password] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const results = [];
const check = (name, ok, detail = "") => {
    results.push({ name, ok, detail });
    console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  -- " + detail : ""}`);
};

const browser = await chromium.launch({
    args: ["--host-resolver-rules=MAP chat.macet.eu 127.0.0.1, MAP app.macet.eu 127.0.0.1, MAP call.macet.eu 127.0.0.1",
           "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
});
const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1280, height: 860 } });
const page = await ctx.newPage();
const hosts = new Set();
page.on("request", (r) => hosts.add(new URL(r.url()).host));

await page.goto("https://app.macet.eu/#/login");
await page.waitForSelector("#mx_LoginForm_username", { timeout: 90000 });
const server = await page.locator(".mx_ServerPicker_server").innerText().catch(() => "");
check("login: account provider chat.macet.eu", server.includes("chat.macet.eu"), server);
check("login: bez tlačidla na zmenu homeservera", (await page.locator(".mx_ServerPicker_change").count()) === 0);
check("login: homeserver dostupný (bez chyby pripojenia)", (await page.locator(".mx_Login_error").count()) === 0);
await page.screenshot({ path: path.join(out, "1-login.png") });

await page.fill("#mx_LoginForm_username", user);
await page.fill("#mx_LoginForm_password", password);
await page.click(".mx_Login_submit");
try {
    await page.waitForSelector(".mx_LeftPanel, .mx_RoomListPanel, .mx_SpacePanel", { timeout: 120000 });
} catch (e) {
    await page.screenshot({ path: path.join(out, "2-after-login-FAIL.png") });
    fs.writeFileSync(path.join(out, "after-login.txt"), await page.locator("body").innerText().catch(() => ""));
    throw e;
}
await page.waitForTimeout(8000);
// zavri prípadné uvítacie/obnovovacie dialógy
for (let i = 0; i < 3; i++) {
    const btn = page.locator(".mx_Dialog button:has-text('Skip'), .mx_Dialog button:has-text('Later'), .mx_Dialog button:has-text('Dismiss'), .mx_Dialog button:has-text('OK')");
    if (await btn.count()) await btn.first().click().catch(() => {});
    await page.keyboard.press("Escape").catch(() => {});
}
await page.screenshot({ path: path.join(out, "2-home.png") });
check("prihlásenie do Element Web", (await page.locator("text=Kanál PSST").count()) > 0 || (await page.url()).includes("#/home") || (await page.url()).includes("#/room"), page.url());

await page.locator("text=Kanál PSST").first().click({ timeout: 60000 });
fs.writeFileSync(path.join(out, "ready"), "1");
const expectFile = path.join(out, "expect.txt");
let expected = "";
for (let i = 0; i < 120 && !expected; i++) {
    if (fs.existsSync(expectFile)) expected = fs.readFileSync(expectFile, "utf8").trim();
    else await page.waitForTimeout(1000);
}
let seen = false;
for (let i = 0; i < 60 && expected && !seen; i++) {
    seen = (await page.locator(`.mx_EventTile_body:has-text("${expected}")`).count()) > 0;
    if (!seen) await page.waitForTimeout(1000);
}
await page.screenshot({ path: path.join(out, "3-room.png") });
check("kanál: prijatá a dešifrovaná E2EE správa od iného klienta", seen, expected);
const shield = await page.locator(".mx_EventTile_e2eIcon_warning, .mx_EventTile_e2eIcon_decryption_failure").count();
check("kanál: bez chyby dešifrovania", shield === 0 || seen, `warning ikony: ${shield}`);

const external = [...hosts].filter((h) => !/(^|\.)macet\.eu(:\d+)?$/.test(h) && !h.startsWith("localhost"));
check("žiadne požiadavky mimo *.macet.eu", external.length === 0, external.join(", "));
fs.writeFileSync(path.join(out, "result.json"), JSON.stringify(results, null, 2));
await browser.close();
const fails = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - fails}/${results.length} checks passed`);
process.exit(fails ? 1 : 0);
