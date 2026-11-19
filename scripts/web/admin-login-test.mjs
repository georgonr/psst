// node admin-login-test.mjs <out-dir> <súbor s údajmi (Používateľ:/Heslo:)>
// prihlásenie admina na https://app.psst.pro (produkcia) + kontrola brandingu; heslo zo súboru, nevypisuje sa
import { chromium } from "playwright";
import fs from "fs"; import path from "path";
import { loginViaMas } from "./psst-auth.mjs";
const [out, credFile] = process.argv.slice(2);
const txt = fs.readFileSync(credFile, "utf8");
const user = /Používateľ:\s*(\S+)/.exec(txt)[1]; const pw = /Heslo:\s*(\S+)/.exec(txt)[1];
const res = []; const check = (n, ok, d = "") => { res.push({ n, ok }); console.log(`${ok ? "PASS" : "FAIL"}  ${n}${d ? "  -- " + d : ""}`); };
const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1280, height: 860 } })).newPage();
await page.goto("https://app.psst.pro/#/login");
await page.waitForSelector(".mx_ServerPicker_server, button:has-text('Continue')", { timeout: 90000 });
const title = await page.title();
check("branding: titulok stránky", /psst/i.test(title), title);
const brandImgs = await page.locator("img[src*='psst'], img[alt*='psst' i], .mx_AuthHeaderLogo img").count();
check("branding: PSST logo na prihlasovacej obrazovke", brandImgs > 0, `${brandImgs} img`);
await page.screenshot({ path: path.join(out, "1-login-branding.png") });
await loginViaMas(page, user, pw);
await page.waitForTimeout(5000);
for (let i = 0; i < 3; i++) await page.keyboard.press("Escape").catch(() => {});
check("admin geo prihlásený na webe", /app\.psst\.pro\/#\/(home|room|welcome)/.test(page.url()), page.url());
await page.screenshot({ path: path.join(out, "2-admin-home.png") });
const uid = await page.evaluate(() => { try { return window.mxMatrixClientPeg?.get()?.getUserId(); } catch { return null; } });
check("prihlásený ako @geo:psst.pro", uid === "@geo:psst.pro", uid ?? "n/a");
await browser.close();
process.exit(res.some((r) => !r.ok) ? 1 : 0);
