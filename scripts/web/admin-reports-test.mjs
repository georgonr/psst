// PSST — test sekcie Nahlásenia na https://app.psst.pro/admin (D87), na produkcii, len s testovacími účtami qa-*.
//   node admin-reports-test.mjs <out-dir> <accounts.json> <step> [args]
//     accounts.json: {"qa-…adm": "pw", …} — prvý kľúč = testovací admin (MAS admin), ostatné sa nepoužijú
//     step list                       → screenshot + JSON zoznam nahlásení (riadky tabuľky) do <out>/reports.json
//     step act <match> <action>       → v riadku obsahujúcom <match> stlačí tlačidlo <action>
//                                       (Vybavené | Znova otvoriť | Zablokovať | Zmazať), potvrdí dialóg, screenshot
// Overuje aj, že stránka neukazuje šifrovaný obsah (žiadne "ciphertext"/"m.megolm"/base64 dlhé reťazce).
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const [out, accFile, step, ...args] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const acc = JSON.parse(fs.readFileSync(accFile, "utf8"));
const ADM = Object.keys(acc).find((u) => /adm/.test(u)) || Object.keys(acc)[0];
if (!/^qa-[a-z0-9-]+$/.test(ADM)) throw new Error("only qa-* test admin accounts");
const A = "https://app.psst.pro/admin";
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1400, height: 1000 } });
const page = await ctx.newPage();
page.on("dialog", (d) => d.accept());
await page.goto(A);
await page.waitForURL(/chat\.psst\.pro\/auth\//, { timeout: 60000 });
await page.fill('input[name="username"]', ADM);
await page.fill('input[name="password"]', acc[ADM]);
await page.locator("button[type=submit]").first().click();
for (let i = 0; i < 20 && !page.url().startsWith(A); i++) {
    await page.locator('button[type=submit]:has-text("Continue"), button:has-text("Allow")').first().click({ timeout: 1500 }).catch(() => {});
    await page.waitForTimeout(1000);
}
await page.goto(A + "#reports");
const sec = page.locator("section#reports");
await sec.waitFor({ timeout: 30000 });

async function rows() {
    return await sec.locator("tr").evaluateAll((trs) => trs.slice(0).map((tr) =>
        Array.from(tr.querySelectorAll("td")).map((td) => td.innerText.replace(/\s+/g, " ").trim())).filter((r) => r.length));
}

if (step === "list") {
    const r = await rows();
    const html = await sec.innerHTML();
    const leak = /ciphertext|m\.megolm|sender_key|[A-Za-z0-9+/]{120,}/.test(html);
    fs.writeFileSync(path.join(out, "reports.json"), JSON.stringify({ rows: r, leak }, null, 1));
    await sec.screenshot({ path: path.join(out, "admin-reports.png") });
    console.log(JSON.stringify({ rows: r.length, leak }));
} else if (step === "act") {
    const [match, action] = args;
    await sec.locator("details").evaluateAll((ds) => ds.forEach((d) => (d.open = true)));
    const tr = sec.locator("tr", { hasText: match }).first();
    await tr.locator("button", { hasText: new RegExp("^" + action) }).first().click({ timeout: 15000 });
    await page.waitForLoadState("networkidle").catch(() => {});
    await page.waitForTimeout(1500);
    const body = (await page.locator("body").innerText()).slice(0, 300);
    await page.goto(A + "#reports");
    await sec.waitFor({ timeout: 30000 });
    await sec.locator("details").evaluateAll((ds) => ds.forEach((d) => (d.open = true)));
    const after = (await sec.locator("tr", { hasText: match }).first().innerText().catch(() => "")).replace(/\s+/g, " ");
    await sec.screenshot({ path: path.join(out, `admin-act-${action.replace(/\W+/g, "_")}.png`) });
    console.log(JSON.stringify({ action, match, response: body.startsWith("psst") ? "page" : body, after }));
}
await browser.close();
