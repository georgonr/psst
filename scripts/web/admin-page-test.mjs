// PSST — test administračnej stránky https://app.macet.eu/admin na produkcii (D56).
//   node admin-page-test.mjs <out-dir> <accounts.json> [<pw-user>]
//     accounts.json: {"<admin user>": "pw", "<plain user>": "pw", "<pw-user>": "pw"} (order matters: admin first, plain second)
//     ADMIN_TEST_ONLY=pwreset  → len prihlásenie admina + test "Nastaviť nové heslo" (bez pozvánok/registrácií)
//     PSST_SSH=psst            → overí aj záznam v audit logu na serveri (ssh <host> sudo tail …/audit.log)
// Overí: prihlásenie cez MAS, pozvánka → registrácia → "použitá" + priradenie, blokovanie/odblokovanie,
// zrušenie pozvánky → registrácia neprejde, 403 pre neadmina, CSRF/Origin ochrana, geo sa nedá zablokovať,
// nové heslo (D70): heslo sa ukáže raz, audit bez hesla, prihlásenie do appky novým heslom, staré neplatí.
// <pw-user> = čerstvý testovací účet (napr. qa-pw<MMDDHHMM>), heslo v accounts.json; po teste ho deaktivujte.
// Na konci vypíše JSON {codes, user} pre upratovanie.
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { loginViaMas, MAS_URL_RE, registerViaMas } from "./psst-auth.mjs";

const [out, accFile, PWUSER] = process.argv.slice(2);
const ONLY = process.env.ADMIN_TEST_ONLY || "";
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
const newUser = ONLY === "pwreset" ? null : `qa-inv${sfx}`;
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

if (ONLY !== "pwreset") {
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
} // ONLY

// 8) nové heslo pre člena (D70)
if (PWUSER) {
    const oldPw = acc[PWUSER];
    await adm.page.setViewportSize({ width: 1280, height: 900 });
    await adm.page.goto(A);
    const geoRow2 = await sec(adm.page, "Členovia").locator("tr").filter({ has: adm.page.locator("b", { hasText: /^geo$/ }) }).first().innerHTML();
    check("geo: bez tlačidla Nastaviť nové heslo", !/Nastaviť nové heslo/.test(geoRow2));
    const adminRows = await sec(adm.page, "Členovia").locator("tr", { hasText: "(admin)" }).allInnerTexts();
    check("admin účty: bez tlačidla Nastaviť nové heslo", adminRows.every((t) => !/Nastaviť nové heslo/.test(t)), `${adminRows.length} admin riadkov`);
    const form = mrow(adm.page, PWUSER).locator('form[action$="/password"]');
    const action = await form.getAttribute("action");
    const bad = await adm.ctx.request.post("https://app.macet.eu" + action, { form: { csrf: "zly" }, headers: { Origin: "https://app.macet.eu" }, maxRedirects: 0 });
    check("nové heslo: POST bez platného CSRF → 403", bad.status() === 403, String(bad.status()));
    let confirmText = "";
    const onDialog = (d) => { confirmText = d.message(); };
    adm.page.on("dialog", onDialog);
    await form.locator('button:has-text("Nastaviť nové heslo")').click();
    await adm.page.waitForSelector("#newpw", { timeout: 20000 });
    adm.page.off("dialog", onDialog);
    check("nové heslo: pred resetom potvrdenie", confirmText.includes(PWUSER) && /ostanú prihlásené/.test(confirmText), confirmText);
    const newPw = (await adm.page.locator("#newpw").innerText()).trim();
    const box = await adm.page.locator("#pwreset").innerText();
    check("nové heslo: 4 skupiny, čitateľné", /^[a-z2-9]{4}(-[a-z2-9]{4}){3}$/.test(newPw), newPw.replace(/[a-z2-9]/g, "x"));
    check("nové heslo: tlačidlo Kopírovať + pokyny (raz, bezpečne, zmeniť v Nastaveniach účtu, relácie ostávajú)",
        /Kopírovať/.test(box) && /iba teraz/.test(box) && /bezpečne/.test(box) && /Nastaveniach účtu/.test(box) && /ostávajú prihlásené/.test(box),
        box.replace(/\s+/g, " ").replace(newPw, "<heslo>").slice(0, 160));
    await shot(adm.page, "7-password-reset");
    await adm.page.goto(A);
    check("nové heslo: po obnovení stránky sa už nezobrazí", (await adm.page.locator("#newpw").count()) === 0 && !(await adm.page.content()).includes(newPw));
    if (process.env.PSST_SSH) {
        const log = execFileSync("ssh", [process.env.PSST_SSH, "sudo tail -n 200 /opt/psst/server/data/admin/audit.log"], { encoding: "utf8" });
        const recs = log.trim().split("\n").map((l) => { try { return JSON.parse(l); } catch { return {}; } });
        const rec = recs.reverse().find((r) => r.action === "user_password_reset" && r.target === PWUSER);
        check("audit log: user_password_reset (kto/kedy/komu), bez hesla",
            rec && rec.user === ADM && rec.ts && !log.includes(newPw), rec ? JSON.stringify({ ...rec, ip: "…" }) : "chýba");
    }
    const c1 = await browser.newContext({ viewport: { width: 1280, height: 860 } });
    const p1 = await c1.newPage();
    await p1.goto("https://app.macet.eu/#/login");
    let loginOk = true, loginErr = "";
    await loginViaMas(p1, PWUSER, newPw).catch((e) => { loginOk = false; loginErr = String(e).slice(0, 150); });
    check("prihlásenie do appky (Element Web → MAS) novým heslom → zoznam miestností", loginOk && (await p1.locator(".mx_LeftPanel, .mx_RoomListPanel").count()) > 0, loginErr || p1.url());
    await shot(p1, "8-login-new-password");
    await c1.close();
    const c2 = await browser.newContext({ viewport: { width: 1280, height: 860 } });
    const p2 = await c2.newPage();
    await p2.goto("https://app.macet.eu/#/login");
    await p2.locator('.mx_Login_fullWidthButton, button:has-text("Continue")').first().click({ timeout: 90000 });
    await p2.waitForURL(MAS_URL_RE, { timeout: 60000 });
    await p2.fill('input[name="username"]', PWUSER);
    await p2.fill('input[name="password"]', oldPw);
    await p2.locator("button[type=submit]").first().click();
    await p2.waitForTimeout(4000);
    const still = MAS_URL_RE.test(p2.url()) && (await p2.locator('input[name="password"]').count()) > 0;
    check("staré heslo už neplatí (MAS prihlásenie odmietne)", still, (await p2.locator("body").innerText()).replace(/\s+/g, " ").slice(0, 120));
    await shot(p2, "9-old-password-rejected");
    await c2.close();
}

await browser.close();
const fails = res.filter((x) => !x.ok).length;
fs.writeFileSync(path.join(out, "result.json"), JSON.stringify({ res, codes, user: newUser }, null, 2));
console.log(JSON.stringify({ codes, user: newUser }));
console.log(`\n${res.length - fails}/${res.length} checks passed`);
process.exit(fails ? 1 : 0);
