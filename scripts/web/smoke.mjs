// PSST web smoke test: serves a built Element Web dist locally, then checks the shipped
// config.json, the PWA manifest and the login screen in headless Chromium.
// Usage: node smoke.mjs <webapp-dir> <output-dir>
// Needs the `playwright` package resolvable from the current working directory.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const [root, outDir] = process.argv.slice(2);
if (!root || !outDir) {
    console.error("usage: node smoke.mjs <webapp-dir> <output-dir>");
    process.exit(2);
}
fs.mkdirSync(outDir, { recursive: true });

const TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".wasm": "application/wasm",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".gif": "image/gif",
    ".jpg": "image/jpeg",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
};
const server = http.createServer((req, res) => {
    let p = decodeURIComponent(new URL(req.url, "http://x").pathname);
    if (p.endsWith("/")) p += "index.html";
    const file = path.join(root, path.normalize(p));
    if (!file.startsWith(path.resolve(root)) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
        res.writeHead(404);
        res.end("not found");
        return;
    }
    res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] ?? "application/octet-stream" });
    fs.createReadStream(file).pipe(res);
});
await new Promise((r) => server.listen(8080, "127.0.0.1", r));
const base = "http://127.0.0.1:8080/";

const results = [];
function check(name, ok, detail = "") {
    results.push({ name, ok: !!ok, detail: String(detail) });
    console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  -- " + detail : ""}`);
}

// 1. Shipped config.json
const cfg = await (await fetch(base + "config.json")).json();
const hs = cfg.default_server_config?.["m.homeserver"] ?? {};
check("config: m.homeserver.base_url == https://chat.macet.eu", hs.base_url === "https://chat.macet.eu", hs.base_url);
check("config: m.homeserver.server_name == chat.macet.eu", hs.server_name === "chat.macet.eu", hs.server_name);
check("config: disable_custom_urls == true", cfg.disable_custom_urls === true);
check("config: disable_guests == true", cfg.disable_guests === true);
check("config: brand == psst", cfg.brand === "psst", cfg.brand);
check("config: no posthog analytics", !cfg.posthog);
check("config: no sentry", !cfg.sentry);
check("config: no bug_report_endpoint_url", !cfg.bug_report_endpoint_url);
check("config: no integration manager", !cfg.integrations_ui_url && !cfg.integrations_rest_url);
check("config: no map_style_url", !cfg.map_style_url);
check("config: no jitsi", !cfg.jitsi);
check("config: element_call.use_exclusively", cfg.element_call?.use_exclusively === true);
check("config: default theme custom-psst", cfg.default_theme === "custom-psst");
const raw = JSON.stringify(cfg);
check("config: no element.io / matrix.org / vector.im URLs", !/element\.io|matrix\.org|vector\.im/.test(raw));

// 2. PWA manifest + bundled Element Call
const manifest = await (await fetch(base + "manifest.json")).json();
check("manifest: name/short_name == psst", manifest.name === "psst" && manifest.short_name === "psst");
const ec = await fetch(base + "widgets/element-call/index.html");
check("embedded Element Call shipped at widgets/element-call/", ec.ok, ec.status);

// 3. Login screen in headless Chromium
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 860 }, colorScheme: "light" });
const consoleLines = [];
page.on("console", (m) => consoleLines.push(`[${m.type()}] ${m.text()}`));
const external = new Set();
page.on("request", (r) => {
    const u = new URL(r.url());
    if (u.hostname !== "127.0.0.1") external.add(u.hostname);
});
await page.goto(base + "#/login");
let serverText = "";
try {
    await page.waitForSelector(".mx_ServerPicker_server", { timeout: 90000 });
    await page.waitForTimeout(3000); // let fonts / theme settle
    serverText = (await page.textContent(".mx_ServerPicker_server")) ?? "";
} catch (e) {
    check("login: server picker rendered", false, e.message);
}
await page.screenshot({ path: path.join(outDir, "login.png"), fullPage: true });
check("login: shows chat.macet.eu", serverText.includes("chat.macet.eu"), serverText);
const editButtons = await page.locator(".mx_ServerPicker_change").count();
check("login: no option to change homeserver (no Edit button)", editButtons === 0, `edit buttons: ${editButtons}`);
const title = await page.title();
check("page title is psst", /psst/.test(title) && !/Element/.test(title), title);
const logoSrc = await page.locator(".mx_AuthHeaderLogo img").first().getAttribute("src").catch(() => null);
check("login: psst wordmark as auth logo", (logoSrc ?? "").includes("psst-wordmark"), logoSrc);
const accent = await page.evaluate(() => getComputedStyle(document.body).getPropertyValue("--accent-color").trim());
check("theme: custom psst theme active (accent #38BDF8)", accent.toUpperCase() === "#38BDF8", accent);
const bodyText = await page.locator("body").innerText();
check("login: no 'Element' in visible text", !/\bElement\b/.test(bodyText), bodyText.replace(/\s+/g, " ").slice(0, 300));
check("login: no links to element.io/matrix.org", (await page.locator('a[href*="element.io"], a[href*="matrix.org"]').count()) === 0);

// 4. Registration screen (informational: needs the homeserver to answer /register flows)
await page.goto(base + "#/register");
await page.waitForTimeout(8000);
await page.screenshot({ path: path.join(outDir, "register.png"), fullPage: true });

await browser.close();
server.close();

check("info: external hosts contacted", true, [...external].join(", ") || "none");
fs.writeFileSync(path.join(outDir, "console.log"), consoleLines.join("\n"));
fs.writeFileSync(path.join(outDir, "smoke-result.json"), JSON.stringify({ title, results }, null, 2));
if (process.env.GITHUB_STEP_SUMMARY) {
    const md = ["### psst web smoke test", "", "| Check | Result | Detail |", "|---|---|---|"]
        .concat(results.map((r) => `| ${r.name} | ${r.ok ? "PASS" : "FAIL"} | ${r.detail.replace(/\|/g, "\\|").slice(0, 200)} |`))
        .join("\n");
    fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, md + "\n");
}
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
process.exit(failed.length ? 1 : 0);
