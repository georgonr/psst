// PSST — otvorená registrácia cez Element Web → MAS (D88).
//   node register-test.mjs <out-dir> [--complete]
// Vždy (aj na produkcii): registračná obrazovka MAS sa otvorí z appky, NEMÁ pole na pozývací kód, zobrazí hCaptcha
// a povinné políčko súhlasu s Podmienkami s potvrdením veku 18+.
// --complete: celá registrácia nového účtu — LEN na lokálnom stacku s testovacími kľúčmi hCaptcha (deploy.sh
// --local-test, PSST_HOST_IP=127.0.0.1); na produkcii sú ostré kľúče a automat hCaptcha neprejde.
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { HOST_RULES, openMasRegistration, registerViaMas } from "./psst-auth.mjs";

const [out, mode] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const results = [];
const check = (name, ok, detail = "") => { results.push({ name, ok, detail }); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  -- " + detail : ""}`); };
const local = mode === "--complete";
const browser = await chromium.launch(local ? { args: [HOST_RULES] } : {});

for (const [lang, re18] of [["en-US", /18 years old/], ["sk-SK", /18 rokov/]]) {
    const ctx = await browser.newContext({ ignoreHTTPSErrors: local, viewport: { width: 1280, height: 900 }, locale: lang });
    const page = await ctx.newPage();
    await openMasRegistration(page);
    check(`[${lang}] registrácia z appky otvorí stránku MAS`, true, page.url());
    check(`[${lang}] bez poľa na pozývací kód`, (await page.locator('input[name="token"]').count()) === 0 && !/registration token|pozývac/i.test(await page.locator("body").innerText()));
    const frame = page.locator('iframe[src*="hcaptcha.com"]').first();
    await frame.waitFor({ state: "attached", timeout: 30000 }).catch(() => {});
    check(`[${lang}] hCaptcha zobrazená`, (await page.locator('iframe[src*="hcaptcha.com"]').count()) > 0);
    const terms = page.locator('input[name="accept_terms"]');
    const body = (await page.locator("body").innerText()).replace(/\s+/g, " ");
    const label = (body.match(/(I am at least 18[^.]*?Conditions|Mám aspoň 18[^.]*?používania)/) || [""])[0];
    const required = await terms.evaluate((el) => el.required);
    check(`[${lang}] povinný súhlas s Podmienkami + 18+`, required && re18.test(label), `required=${required} „${label}“`);
    const href = await page.locator('a[href*="/terms"]').first().getAttribute("href").catch(() => null);
    check(`[${lang}] odkaz na Podmienky`, href === "https://psst.pro/terms", String(href));
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(out, `register-${lang}.png`), fullPage: true });
    await ctx.close();
}

if (local) {
    const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1280, height: 860 } });
    const page = await ctx.newPage();
    const user = `reg${Date.now() % 100000}`;
    const r = await registerViaMas(page, user, "Psst-Reg-" + user + "-ok!").catch((e) => ({ ok: false, error: String(e).slice(0, 200) }));
    await page.screenshot({ path: path.join(out, "register-complete.png") });
    check("registrácia s testovacím hCaptcha → účet vytvorený, appka prihlásená", r.ok, r.error || `@${user}`);
    await ctx.close();
}

fs.writeFileSync(path.join(out, "result.json"), JSON.stringify(results, null, 2));
await browser.close();
const fails = results.filter((x) => !x.ok).length;
console.log(`\n${results.length - fails}/${results.length} checks passed`);
process.exit(fails ? 1 : 0);
