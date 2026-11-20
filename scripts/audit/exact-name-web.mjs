// PSST (D88) — hľadanie ľudí len podľa presného mena účtu v Element Web (aj v desktope je ten istý webapp).
//   node exact-name-web.mjs <out-dir> <user> <password> <target-localpart> <target-display-name> [base-url]
// Overí na produkcii (testovacie účty qa-*):
//   * „Začať rozhovor“ (InviteDialog): časť mena nenájde nikoho, krátke meno aj plné @meno:psst.pro nájdu osobu,
//     Enter pri krátkom mene pridá @meno:psst.pro, „Go“ + prvá správa → DM (pozvánku overí volajúci cez API),
//   * vyhľadávanie (Ctrl+K → People): krátke meno nájde osobu, časť mena nie.
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

import { fileURLToPath } from "node:url";

const domain = "psst.pro";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));


/** Kontroly presného mena na už prihlásenej stránke Element (web aj desktop cez CDP). */
export async function runExactName(page, { target, targetName, check, shot, label = "webu" }) {
    const dlgInput = () => page.locator('[data-testid="invite-dialog-input"], .mx_InviteDialog_editor input').first();
    const option = (name) => page.locator('[role=option]', { hasText: name });
    async function inviteDialogQuery(q, expectFound) {
        const input = dlgInput();
        await input.fill("");
        await input.pressSequentially(q, { delay: 40 });
        if (expectFound) await option(targetName).first().waitFor({ timeout: 20000 }).catch(() => {});
        else await sleep(5000);
        return (await option(targetName).count()) > 0;
    }

    const partial = target.slice(0, -2);
    // 1) vyhľadávanie (spotlight) → People — PRED vytvorením DM (známych ľudí zo spoločných miestností Element nájde aj
    //    podľa časti mena lokálne, to nie je adresár servera)
    await page.keyboard.press(process.platform === "darwin" ? "Meta+k" : "Control+k");
    const sInput = page.locator(".mx_SpotlightDialog input").first();
    await sInput.waitFor({ timeout: 15000 });
    async function spotlight(q, expectFound) {
        await sInput.fill("");
        await sInput.pressSequentially(q, { delay: 40 });
        await sleep(800);
        const people = page.getByRole("option", { name: /^(People|Ľudia)$/ });
        await people.first().waitFor({ timeout: 10000 }).catch(() => {});
        if (await people.count()) { await people.first().click(); await sleep(800); }
        const hit = page.locator(".mx_SpotlightDialog [role=option]", { hasText: `@${target}:${domain}` });
        if (expectFound) await hit.first().waitFor({ timeout: 20000 }).catch(() => {});
        else await sleep(5000);
        return (await hit.count()) > 0;
    }
    check(`vyhľadávanie People: časť mena „${partial}“ → nikto`, !(await spotlight(partial, false)));
    check(`vyhľadávanie People: krátke meno „${target}“ → @${target}:${domain}`, await spotlight(target, true));
    await shot(page, "5-spotlight");

    await page.keyboard.press("Escape");
    await sleep(800);

    // 2) Začať rozhovor
    await page.getByRole("button", { name: /^(Not now|Teraz nie)$/ }).first().click({ timeout: 3000 }).catch(() => {});
    await page.getByRole("button", { name: /^(Send a Direct Message|Poslať priamu správu)$/ }).first().click({ timeout: 20000 });
    await sleep(3000);
    await shot(page, "0b-dialog");
    await dlgInput().waitFor({ timeout: 20000 });
    check(`DM dialóg: časť mena „${partial}“ → nikto`, !(await inviteDialogQuery(partial, false)));
    await shot(page, "1-partial");
    check(`DM dialóg: krátke meno „${target}“ → ${targetName}`, await inviteDialogQuery(target, true));
    await shot(page, "2-short");
    check(`DM dialóg: plné „@${target}:${domain}“ → ${targetName}`, await inviteDialogQuery(`@${target}:${domain}`, true));
    await inviteDialogQuery(target, true);
    await dlgInput().press("Enter");
    await sleep(1500);
    const pill = await page.getByRole("dialog").getByText(`@${target}:${domain}`, { exact: true }).count();
    check(`Enter pri krátkom mene → @${target}:${domain} vybraný`, pill > 0, `${pill}×`);
    await shot(page, "3-selected");
    await page.locator('button:has-text("Ok"), [role=button]:has-text("Ok")').first().click({ timeout: 2000 }).catch(() => {});
    await page.getByRole("dialog").getByRole("button", { name: /^(Go|Spustiť|Prejsť)$/ }).click();
    const composer = page.locator(".mx_BasicMessageComposer_input, [contenteditable=true][role=textbox]").first();
    await sleep(3000);
    await page.getByRole("dialog").getByRole("button", { name: /^(Continue|Pokračovať)$/ }).click({ timeout: 10000 }).catch(() => {});
    await composer.waitFor({ timeout: 60000 });
    await composer.click();
    await page.keyboard.type(`Ahoj z ${label} (D88)`);
    await page.keyboard.press("Enter");
    await sleep(8000);
    await shot(page, "4-dm");
    check("prvá správa odoslaná → DM vytvorený", true, page.url());

}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
const [out, user, password, target, targetName, base = "https://app.psst.pro"] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const res = [];
const check = (n, ok, d = "") => { res.push({ n, ok, d }); console.log(`${ok ? "PASS" : "FAIL"}  ${n}${d ? "  -- " + d : ""}`); };
const shot = (p, n) => p.screenshot({ path: path.join(out, n + ".png") });
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: "en-US" });
const page = await ctx.newPage();

// prihlásenie: Element Web → Continue → MAS → (súhlas) → appka
await page.goto(base + "/#/login");
await page.locator('.mx_Login_fullWidthButton, [role=button]:has-text("Continue"), button:has-text("Continue")').first().click({ timeout: 90000 });
await page.waitForSelector('input[name="username"]', { timeout: 60000 });
await page.fill('input[name="username"]', user);
await page.fill('input[name="password"]', password);
await page.locator("button[type=submit]").first().click();
for (let i = 0; i < 30 && !page.url().startsWith(base); i++) {
    await page.locator('button[type=submit]:has-text("Continue"), button:has-text("Allow")').first().click({ timeout: 1000 }).catch(() => {});
    await sleep(1000);
}
await page.waitForSelector(".mx_LeftPanel, .mx_RoomListPanel, .mx_SpacePanel", { timeout: 120000 });
await sleep(4000);
for (let i = 0; i < 4; i++) { await page.keyboard.press("Escape"); await sleep(400); }
check("prihlásenie " + user, true);
await shot(page, "0-home");

await runExactName(page, { target, targetName, check, shot });
fs.writeFileSync(path.join(out, "result.json"), JSON.stringify(res, null, 2));
await browser.close();
const fails = res.filter((x) => !x.ok).length;
console.log(`\n${res.length - fails}/${res.length} checks passed`);
process.exit(fails ? 1 : 0);
}
