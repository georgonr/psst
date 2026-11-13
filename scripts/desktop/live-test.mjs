// PSST — macOS desktop (psst.app) proti lokálnemu stacku.
//   node live-test.mjs <psst.app> <out-dir> <user> <password>
// Spustí appku s Chromium prepínačmi (mapovanie *.macet.eu → 127.0.0.1, self-signed cert),
// pripojí sa cez CDP (remote debugging) a prihlási sa testovacím účtom.
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const [app, out, user, password] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const results = [];
const check = (name, ok, detail = "") => {
    results.push({ name, ok, detail });
    console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  -- " + detail : ""}`);
};
const profile = fs.mkdtempSync("/tmp/psst-desktop-profile-");
const proc = spawn(path.join(app, "Contents/MacOS/psst"), [
    "--remote-debugging-port=9333",
    "--host-resolver-rules=" + ["chat", "app", "call", "push"].map((h) => `MAP ${h}.macet.eu ${process.env.PSST_HOST_IP || "127.0.0.1"}`).join(", "),
    "--ignore-certificate-errors",
    // bez prístupu ku kľúčenke macOS (inak nový ad-hoc podpis vyvolá dialóg a zablokuje appku)
    "--use-mock-keychain",
    `--profile-dir=${profile}`,
], { stdio: ["ignore", "pipe", "pipe"] });
let log = "";
proc.stdout.on("data", (d) => (log += d));
proc.stderr.on("data", (d) => (log += d));

let browser;
for (let i = 0; i < 60 && !browser; i++) {
    try { browser = await chromium.connectOverCDP("http://127.0.0.1:9333"); } catch { await new Promise((r) => setTimeout(r, 1000)); }
}
check("appka sa spustila a je dostupná cez CDP", !!browser);
let page;
for (let i = 0; i < 60 && !page; i++) {
    page = browser?.contexts().flatMap((c) => c.pages()).find((p) => p.url().startsWith("vector://") || p.url().includes("index.html"));
    if (!page) await new Promise((r) => setTimeout(r, 1000));
}
check("hlavné okno načítané", !!page, page?.url());
try {
    await page.waitForSelector(".mx_ServerPicker_server, .mx_Login_fullWidthButton", { timeout: 90000 });
    check("okno má titulok psst", (await page.title()).toLowerCase().includes("psst"), await page.title());
    const server = await page.locator(".mx_ServerPicker_server").innerText();
    check("login: chat.macet.eu, bez zmeny homeservera", server.includes("chat.macet.eu") && (await page.locator(".mx_ServerPicker_change").count()) === 0, server);
    const cont = await page.locator('.mx_Login_fullWidthButton, button:has-text("Continue"), button:has-text("Pokračovať"), [role=button]:has-text("Pokračovať")').count();
    check("login ponúka prihlásenie cez MAS (Continue → MAS v systémovom prehliadači)", cont > 0, `tlačidlá: ${cont}`);
    await page.screenshot({ path: path.join(out, "1-login.png") });
    // Create account (registrácia s pozvánkou) — tiež cez MAS
    await page.goto(page.url().split("#")[0] + "#/register");
    await page.waitForTimeout(4000);
    check("registrácia: obrazovka Create account (chat.macet.eu)", (await page.locator("body").innerText()).includes("chat.macet.eu"));
    await page.screenshot({ path: path.join(out, "2-register.png") });
} catch (e) {
    check("priebeh testu", false, String(e).slice(0, 300));
    await page?.screenshot({ path: path.join(out, "FAIL.png") }).catch(() => {});
}
fs.writeFileSync(path.join(out, "app.log"), log);
fs.writeFileSync(path.join(out, "result.json"), JSON.stringify(results, null, 2));
await browser?.close().catch(() => {});
proc.kill();
const fails = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - fails}/${results.length} checks passed`);
process.exit(fails ? 1 : 0);
