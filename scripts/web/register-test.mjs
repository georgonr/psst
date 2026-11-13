// PSST — registrácia s pozývacím tokenom cez Element Web → MAS (lokálny stack).
//   node register-test.mjs <out-dir> <jednorazový-token> <viacnásobný-token>
// Overí: platný token → účet + prihlásenie; jednorazový token 2× → odmietnutý; neplatný token → odmietnutý.
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { HOST_RULES, registerViaMas } from "./psst-auth.mjs";

const [out, tokSingle, tokMulti] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const results = [];
const check = (name, ok, detail = "") => { results.push({ name, ok, detail }); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  -- " + detail : ""}`); };
const browser = await chromium.launch({ args: [HOST_RULES] });
const sfx = Date.now() % 100000;
async function attempt(label, user, token) {
    const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1280, height: 860 } });
    const page = await ctx.newPage();
    const r = await registerViaMas(page, user, "Psst-Reg-" + sfx + "-ok!", token).catch((e) => ({ ok: false, error: String(e).slice(0, 200) }));
    await page.screenshot({ path: path.join(out, `${label}.png`) });
    await ctx.close();
    return r;
}
let r = await attempt("1-valid-single", `reg${sfx}a`, tokSingle);
check("registrácia s platným jednorazovým tokenom → účet vytvorený, appka prihlásená", r.ok, r.error || `@reg${sfx}a`);
r = await attempt("2-reused-single", `reg${sfx}b`, tokSingle);
check("jednorazový token druhýkrát → odmietnutý", !r.ok, (r.error || "").slice(0, 120));
r = await attempt("3-invalid", `reg${sfx}c`, "neplatny-token-123");
check("neplatný token → odmietnutý", !r.ok, (r.error || "").slice(0, 120));
r = await attempt("4-valid-multi", `reg${sfx}d`, tokMulti);
check("registrácia s viacnásobným tokenom → účet vytvorený", r.ok, r.error || `@reg${sfx}d`);
fs.writeFileSync(path.join(out, "result.json"), JSON.stringify(results, null, 2));
await browser.close();
const fails = results.filter((x) => !x.ok).length;
console.log(`\n${results.length - fails}/${results.length} checks passed`);
process.exit(fails ? 1 : 0);
