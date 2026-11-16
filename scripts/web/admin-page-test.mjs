// PSST — test administračnej stránky https://app.macet.eu/admin na produkcii (D56).
//   node admin-page-test.mjs <out-dir> <accounts.json>     (accounts.json: {"<admin user>": "pw", "<plain user>": "pw"} (order matters))
// Overí: prihlásenie cez MAS, pozvánka → registrácia → "použitá" + priradenie, blokovanie/odblokovanie,
// zrušenie pozvánky → registrácia neprejde, 403 pre neadmina, CSRF/Origin ochrana, geo sa nedá zablokovať.
// Na konci vypíše JSON {codes, user} pre upratovanie.
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { registerViaMas } from "./psst-auth.mjs";

const [out, accFile] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const acc = JSON.parse(fs.readFileSync(accFile, "utf8"));
const [ADM, PLAIN] = Object.keys(acc); // first = admin account, second = plain account
const A = "https://app.macet.eu/admin";
const res = [];
const check = (n, ok, d = "") => { res.push({ n, ok, d }); console.log(`${ok ? "PASS" : "FAIL"}  ${n}${d ? "  -- " + d : ""}`); };
const shot = (p, n) => p.screenshot({ path: path.join(out, n + ".png"), fullPage: true });
const browser = await chromium.launch();

async function adminLogin(user, pw, viewport = { width: 1280, height: 900 }) {
    const ctx = await browser.newContext({ viewport });
    const page = await ctx.newPage();
    page.on("dialog", (d) => d.accept());
    await page.goto(A);
    await page.waitForURL(/macet\.eu\/auth\//, { timeout: 60000 });
    await page.fill('input[name="username"]', user);
    await page.fill('input[name="password"]', pw);
    let final = null;
    page.on("response", (r) => { if (r.url().includes("/admin/callback")) final = r.status(); });
    await page.locator("button[type=submit]").first().click();
    for (let i = 0; i < 20 && !page.url().startsWith("https://app.macet.eu/admin"); i++) {
        await page.locator('button[type=submit]:has-text("Continue"), button:has-text("Allow")').first().click({ timeout: 1500 }).catch(() => {});
        await page.waitForTimeout(1000);
    }
    await page.waitForLoadState("networkidle").catch(() => {});
    return { ctx, page, status: () => final };
}

async function newInvite(page, note, uses = 1, days = 7) {
    await page.goto(A);
    await page.fill('input[name="uses"]', String(uses));
    await page.fill('input[name="days"]', String(days));
    await page.fill('input[name="note"]', note);
    await page.locator('button:has-text("Nová pozvánka")').click();
    await page.waitForSelector("#code", { timeout: 20000 });
    return { code: (await page.locator("#code").innerText()).trim(), msg: await page.locator("#msg").innerText() };
}

const sec = (page, title) => page.locator("section").filter({ has: page.locator("h2", { hasText: new RegExp("^" + title + "$") }) });
const row = (page, text) => sec(page, "Pozvánky").locator("tr", { hasText: text }).first();
const mrow = (page, text) => sec(page, "Členovia").locator("tr", { hasText: text }).first();
const sfx = Date.now() % 100000;
const newUser = `qa-inv${sfx}`;
const codes = [];

// 1) admin login
const adm = await adminLogin(ADM, acc[ADM]);
check("admin: prihlásenie cez MAS → stránka správy", (await adm.page.locator("h2", { hasText: "Nová pozvánka" }).count()) === 1, adm.page.url());
await shot(adm.page, "1-admin");
const cookies = await adm.ctx.cookies();
const ck = cookies.find((c) => c.name === "psst_admin");
check("session cookie: Secure, HttpOnly, SameSite=Strict, Path=/admin, ≤ 30 min",
    ck && ck.secure && ck.httpOnly && ck.sameSite === "Strict" && ck.path === "/admin" && ck.expires - Date.now() / 1000 <= 1805,
    ck ? `${ck.sameSite} ${ck.path} ${Math.round(ck.expires - Date.now() / 1000)}s` : "chýba");
const html = await adm.page.content();
check("v prehliadači nie je admin token (len náhodné ID session + CSRF)", !/mct_|mat_|Bearer|client_secret/.test(html));

// 2) invite A → registration
const invA = await newInvite(adm.page, "test A");
codes.push(invA.code);
check("pozvánka A vytvorená, kód + text na poslanie", /^[A-Z0-9]{4}-[A-Z0-9]{4}$/.test(invA.code) && invA.msg.includes(invA.code) && /Platí do \d+\. \d+\./.test(invA.msg), invA.msg.split("\n")[0]);
await shot(adm.page, "2-invite-created");
check("pozvánka A: stav voľná, 0/1", /voľná/.test(await row(adm.page, invA.code).innerText()) && /0\/1/.test(await row(adm.page, invA.code).innerText()));
const invB = await newInvite(adm.page, "test B");
codes.push(invB.code);

const regCtx = await browser.newContext({ viewport: { width: 1280, height: 860 } });
const reg = await registerViaMas(await regCtx.newPage(), newUser, "Psst-Inv-" + sfx + "-ok!", invA.code);
await regCtx.close();
check("registrácia z webu kódom A → účet vytvorený", reg.ok, reg.error || `@${newUser}`);

await adm.page.goto(A);
const rA = await row(adm.page, invA.code).innerText();
check("pozvánka A: stav použitá, 1/1, zaregistrovaný " + newUser, /použitá/.test(rA) && /1\/1/.test(rA) && rA.includes(newUser), rA.replace(/\s+/g, " "));
const rU = await mrow(adm.page, newUser).innerText();
check("člen " + newUser + ": pozvánka A, stav aktívny", rU.includes(invA.code) && /aktívny/.test(rU), rU.replace(/\s+/g, " "));
await shot(adm.page, "3-used");

// 3) lock / unlock
await mrow(adm.page, newUser).locator('button:has-text("Zablokovať")').click();
await adm.page.waitForLoadState("networkidle");
check("Zablokovať → stav zablokovaný", /zablokovaný/.test(await mrow(adm.page, newUser).innerText()));
await shot(adm.page, "4-locked");
await mrow(adm.page, newUser).locator('button:has-text("Odblokovať")').click();
await adm.page.waitForLoadState("networkidle");
check("Odblokovať → stav aktívny", /aktívny/.test(await mrow(adm.page, newUser).innerText()));
const geoRow = await sec(adm.page, "Členovia").locator("tr").filter({ has: adm.page.locator("b", { hasText: /^geo$/ }) }).first().innerHTML();
check("geo sa nedá zablokovať (žiadne tlačidlo)", !/Zablokovať/.test(geoRow));

// 4) revoke B → registration must fail
await row(adm.page, invB.code).locator('button:has-text("Zrušiť")').click();
await adm.page.waitForLoadState("networkidle");
check("Zrušiť pozvánku B → stav zrušená", /zrušená/.test(await row(adm.page, invB.code).innerText()));
const regCtx2 = await browser.newContext({ viewport: { width: 1280, height: 860 } });
const reg2 = await registerViaMas(await regCtx2.newPage(), `${newUser}b`, "Psst-Inv-" + sfx + "-ok!", invB.code);
await regCtx2.close();
check("registrácia zrušeným kódom B → odmietnutá", !reg2.ok, (reg2.error || "").slice(0, 100));

// 5) CSRF / Origin
const csrf1 = await adm.ctx.request.post(A + "/invites", { form: { uses: "1", days: "1", note: "csrf" }, headers: { Origin: "https://evil.example" }, maxRedirects: 0 });
check("POST z cudzieho pôvodu → 403", csrf1.status() === 403, String(csrf1.status()));
const csrf2 = await adm.ctx.request.post(A + "/invites", { form: { uses: "1", days: "1", note: "csrf", csrf: "zly" }, headers: { Origin: "https://app.macet.eu" }, maxRedirects: 0 });
check("POST bez platného CSRF tokenu → 403", csrf2.status() === 403, String(csrf2.status()));

// 6) mobile layout
await adm.page.setViewportSize({ width: 390, height: 844 });
await adm.page.goto(A);
const overflow = await adm.page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
check("mobil (390 px): bez vodorovného posúvania stránky", overflow <= 1, `${overflow}px`);
await shot(adm.page, "5-mobile");

// 7) non-admin → 403
const pl = await adminLogin(PLAIN, acc[PLAIN]);
check("neadmin → 403", pl.status() === 403 && /Prístup zamietnutý/.test(await pl.page.content()), `status ${pl.status()}`);
await shot(pl.page, "6-forbidden");
const direct = await pl.ctx.request.get(A, { maxRedirects: 0 });
check("neadmin bez session → presmerovanie na prihlásenie", [302, 303, 307].includes(direct.status()), String(direct.status()));

await browser.close();
const fails = res.filter((x) => !x.ok).length;
fs.writeFileSync(path.join(out, "result.json"), JSON.stringify({ res, codes, user: newUser }, null, 2));
console.log(JSON.stringify({ codes, user: newUser }));
console.log(`\n${res.length - fails}/${res.length} checks passed`);
process.exit(fails ? 1 : 0);
