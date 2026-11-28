// psst (D111): renders og-link.html → server/www/assets/img/og-link.png (1200×630).
//   NODE_PATH=<dir with playwright> node scripts/www/render-og.mjs
import { chromium } from "playwright";
import { fileURLToPath } from "node:url";
import path from "node:path";
const here = path.dirname(fileURLToPath(import.meta.url));
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1200, height: 630 } });
await page.goto("file://" + path.join(here, "og-link.html"));
await page.evaluate(() => document.fonts.ready);
await page.screenshot({ path: path.join(here, "../../server/www/assets/img/og-link.png") });
await browser.close();
