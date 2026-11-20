// PSST (D89) — značka psst na stránkach MAS (chat.psst.pro/auth/) v reálnom prehliadači.
//   node mas-brand.mjs <out-dir> <profile-dir> <locale en-US|sk-SK> <user> <password> [--warm]
// Prejde stránky, ktoré vidí používateľ: prihlásenie, registrácia, súhlas (z app.psst.pro), správa účtu (prehľad,
// zariadenia, zmena hesla, reset identity, dialóg „Zmazať účet“), obnovenie hesla, chybové stránky.
// Pri každej: titulok karty, viditeľný text bez „matrix-authentication-service“, „Matrix Authentication Service“,
// „Element“ a bez surových kľúčov prekladov (common.username …), tmavé pozadie, favicon psst, logo psst.
// <profile-dir> = trvalý profil Chromia: s --warm len navštívi stránky (naplní cache starou verziou), bez neho
// kontroluje — rovnaký profil po nasadení = „s cache z predchádzajúcej verzie“, nový profil = „čistý prehliadač“.
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const [out, profile, locale, user, password, mode] = process.argv.slice(2);
const warm = mode === "--warm";
fs.mkdirSync(out, { recursive: true });
const MAS = "https://chat.psst.pro/auth";
const res = [];
const check = (n, ok, d = "") => { res.push({ n, ok, d }); console.log(`${ok ? "PASS" : "FAIL"}  ${n}${d ? "  -- " + d : ""}`); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const FORBIDDEN = /matrix-authentication-service|Matrix Authentication Service|\bElement\b/i;
const RAWKEY = /\b(?:common|frontend|mas|action|branding|app|error)\.[a-z0-9_]+(?:\.[a-z0-9_]+)+\b/;

const ctx = await chromium.launchPersistentContext(profile, { locale, viewport: { width: 1100, height: 900 } });
const page = ctx.pages()[0] || (await ctx.newPage());

async function inspect(name) {
    await sleep(2500);
    if (warm) return;
    const title = await page.title();
    const text = (await page.locator("body").innerText().catch(() => "")).replace(/\s+/g, " ");
    const info = await page.evaluate(() => {
        const bg = getComputedStyle(document.body).backgroundColor;
        const icon = [...document.querySelectorAll("link[rel~=icon]")].map((l) => l.href).join(" ");
        return { bg, icon, brand: !!document.querySelector(".psst-brand svg"), dark: document.documentElement.classList.contains("cpd-theme-dark") };
    });
    const m = info.bg.match(/\d+/g) || [255, 255, 255];
    const lum = (0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]) / 255;
    const bad = text.match(FORBIDDEN);
    const raw = text.replace(/[a-z0-9.-]*psst\.pro\S*/gi, "").match(RAWKEY);
    const okTitle = title === "psst" || title.startsWith("psst – ");
    check(`[${locale}] ${name}: titulok „${title}“`, okTitle);
    check(`[${locale}] ${name}: bez MAS/Element textov`, !bad, bad ? bad[0] : "");
    check(`[${locale}] ${name}: preklady (žiadne kľúče)`, !raw, raw ? raw[0] : "");
    check(`[${locale}] ${name}: tmavé pozadie, favicon a logo psst`, lum < 0.2 && info.dark && info.brand && info.icon.includes("psst.pro"),
        `bg ${info.bg}, logo ${info.brand}`);
    await page.screenshot({ path: path.join(out, `${locale}-${name}.png`), fullPage: true });
}

// 1) prihlásenie, registrácia, obnovenie hesla, chybové stránky (bez prihlásenia)
await page.goto(MAS + "/login"); await inspect("prihlasenie");
await page.goto(MAS + "/register"); await inspect("registracia");
await page.goto(MAS + "/recover"); await inspect("obnovenie-hesla");
await page.goto(MAS + "/authorize?client_id=psst-neexistuje&response_type=code&scope=openid&redirect_uri=https://app.psst.pro/"); await inspect("chyba-autorizacia");
await page.goto(MAS + "/neexistuje-psst"); await inspect("chyba-404");

// 2) súhlas: prihlásenie z app.psst.pro (Element Web → MAS → „Continue to psst?“)
// (profil s cache už môže byť v Element Web prihlásený — súhlas je serverová šablóna, cache ho neovplyvní)
try {
    await page.goto("https://app.psst.pro/#/login", { timeout: 60000 });
    await page.locator('.mx_Login_fullWidthButton, [role=button]:has-text("Continue"), [role=button]:has-text("Pokračovať")').first().click({ timeout: 60000 });
    await page.waitForURL(/chat\.psst\.pro\/auth\//, { timeout: 60000 });
    if (await page.locator('input[name="username"]').count()) {
        await page.fill('input[name="username"]', user);
        await page.fill('input[name="password"]', password);
        await page.locator("button[type=submit]").first().click();
    }
    await page.waitForLoadState("networkidle").catch(() => {});
    if (page.url().includes("chat.psst.pro/auth/")) await inspect("suhlas");
    for (let i = 0; i < 10 && page.url().includes("chat.psst.pro/auth/"); i++) {
        await page.locator("button[type=submit]").first().click({ timeout: 2000 }).catch(() => {});
        await sleep(1500);
    }
} catch (e) {
    console.log(`INFO  [${locale}] súhlas preskočený (${String(e).split("\n")[0].slice(0, 80)})`);
    await page.goto(MAS + "/login");
    if (await page.locator('input[name="username"]').count()) {
        await page.fill('input[name="username"]', user);
        await page.fill('input[name="password"]', password);
        await page.locator("button[type=submit]").first().click();
        await sleep(3000);
    }
}

// 3) správa účtu (React)
for (const [name, p] of [["ucet", "/account/"], ["zariadenia", "/account/sessions"], ["zmena-hesla", "/account/password/change"],
    ["reset-identity", "/account/reset-cross-signing"]]) {
    await page.goto(MAS + p);
    await page.waitForSelector("#root *", { timeout: 30000 }).catch(() => {});
    await inspect(name);
}
await page.goto(MAS + "/account/");
await sleep(3000);
const del = page.getByRole("button", { name: /Delete account|Deactivate account|Zmazať účet|Deaktivovať účet|Odstrániť účet/i }).first();
if (await del.count()) {
    await del.click(); await sleep(1500);
    await inspect("zmazanie-uctu-dialog");
    const dlg = (await page.locator("body").innerText().catch(() => "")).replace(/\s+/g, " ");
    const bad = dlg.match(/Matrix|MXID|identity server/);
    if (!warm) check(`[${locale}] dialóg zmazania: bez „Matrix ID/MXID“ a „identity server“`, /Delete this account|Zmazať tento účet/i.test(dlg) && !bad, bad ? bad[0] : "ok");
    await page.keyboard.press("Escape");
} else if (!warm) check(`[${locale}] tlačidlo zmazania účtu`, false, "nenašlo sa");

await ctx.close();
if (!warm) {
    fs.writeFileSync(path.join(out, `result-${locale}.json`), JSON.stringify(res, null, 2));
    const fails = res.filter((x) => !x.ok).length;
    console.log(`\n${res.length - fails}/${res.length} checks passed`);
    process.exit(fails ? 1 : 0);
}
console.log("warm: hotovo");
