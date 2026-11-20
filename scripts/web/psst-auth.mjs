// PSST — spoločné kroky pre Playwright testy: prihlásenie a registrácia cez MAS (chat.psst.pro/auth/, alebo auth.psst.pro).
// Element Web → "Continue"/"Create account" → stránka MAS → (súhlas) → späť do appky.
// PSST_HOST_IP: kam mapovať domény (127.0.0.1 na Macu, 172.30.0.250 = nginx v Docker sieti "psst")
const IP = (typeof process !== "undefined" && process.env.PSST_HOST_IP) || "127.0.0.1";
// MAS beží na https://chat.psst.pro/auth/ (D42) alebo na vlastnej subdoméne auth.psst.pro
export const MAS_URL_RE = /(auth\.psst\.pro|chat\.psst\.pro\/auth\/)/;
export const HOST_RULES = "--host-resolver-rules=" +
    ["chat.psst.pro", "app.psst.pro", "call.psst.pro", "auth.psst.pro", "psst.pro", "www.psst.pro"].map((h) => `MAP ${h} ${IP}`).join(", ");

async function clickIfVisible(page, selector, timeout = 1500) {
    const loc = page.locator(selector).first();
    try {
        await loc.waitFor({ state: "visible", timeout });
        await loc.click();
        return true;
    } catch {
        return false;
    }
}

// Na stránke MAS: po prihlásení/registrácii môže prísť súhlas ("Continue"/"Allow") pre klienta psst.
async function finishConsent(page) {
    for (let i = 0; i < 20; i++) {
        if (page.url().startsWith("https://app.psst.pro") || page.url().startsWith("vector://")) return;
        await clickIfVisible(page, 'button[type=submit]:has-text("Continue"), button:has-text("Allow"), button:has-text("Pokračovať")', 1000);
        await page.waitForTimeout(1000);
    }
}

async function waitForApp(page, timeout = 120000) {
    await page.waitForSelector(".mx_LeftPanel, .mx_RoomListPanel, .mx_SpacePanel", { timeout });
}

// Prihlásenie heslom cez MAS. page už musí byť na prihlasovacej obrazovke Element Web.
export async function loginViaMas(page, user, password) {
    await page.waitForSelector('.mx_Login_fullWidthButton, .mx_SSOButton, button:has-text("Continue"), .mx_Login_submit', { timeout: 90000 });
    // Element Web s MAS: jediné tlačidlo "Continue" (next-gen auth)
    await clickIfVisible(page, '.mx_Login_fullWidthButton, button:has-text("Continue")', 10000);
    await page.waitForURL(MAS_URL_RE, { timeout: 60000 });
    await page.locator('input[name="username"]').fill(user);
    await page.locator('input[name="password"]').fill(password);
    await page.locator('button[type=submit]').first().click();
    await finishConsent(page);
    await waitForApp(page);
}

// Otvorí registračný formulár MAS z Element Web (#/register → Continue). Vráti page na stránke MAS.
export async function openMasRegistration(page, base = "https://app.psst.pro") {
    await page.goto(base + "/#/register");
    await page.locator('.mx_Login_fullWidthButton, [role=button]:has-text("Continue"), button:has-text("Continue")').first().click({ timeout: 90000 });
    await page.waitForURL(MAS_URL_RE, { timeout: 60000 });
    await page.waitForSelector('input[name="username"]', { timeout: 60000 });
}

// Otvorená registrácia cez MAS (D88): meno, heslo, potvrdenie, súhlas s Podmienkami a 18+, hCaptcha → (zobrazované
// meno) → súhlas → appka. Automaticky len na lokálnom stacku s DOČASNE vypnutou captcha: MAS 1.29 odmietne aj
// testovacie kľúče hCaptcha (hostname "dummy-key-pass" ≠ doména MAS, D88); na produkcii registruje človek.
// Ak je na stránke hCaptcha, skript klikne jej políčko (prejde len pri ľudskom overení). Vráti { ok, error }.
export async function registerViaMas(page, user, password) {
    await openMasRegistration(page);
    await page.fill('input[name="username"]', user);
    await page.fill('input[name="password"]', password);
    await page.fill('input[name="password_confirm"]', password);
    await page.check('input[name="accept_terms"]');
    if (await page.locator('iframe[src*="hcaptcha.com"]').count()) {
        const box = page.frameLocator('iframe[src*="hcaptcha.com"][title*="checkbox" i]').locator("#checkbox");
        await box.click({ timeout: 60000 }).catch(() => {});
        await page.waitForTimeout(3000);
    }
    for (let i = 0; i < 5 && /\/register\/?(\?|$)/.test(new URL(page.url()).pathname + "?"); i++) {
        await page.locator('button[type=submit]').first().click().catch(() => {});
        await page.waitForTimeout(3000);
    }
    if (/\/register\/?$/.test(new URL(page.url()).pathname)) {
        const txt = (await page.locator("body").innerText()).replace(/\s+/g, " ");
        return { ok: false, error: txt.slice(0, 200) };
    }
    // (2b) zobrazované meno (voliteľný krok MAS)
    for (let i = 0; i < 5 && /\/display-name/.test(page.url()); i++) {
        const input = page.locator('input[type=text], input[name="display_name"], input[name="displayname"]').first();
        if (await input.count()) await input.fill(user).catch(() => {});
        await page.locator('button[type=submit]').first().click().catch(() => {});
        await page.waitForTimeout(2500);
    }
    await finishConsent(page);
    try {
        await waitForApp(page, 90000);
        return { ok: true };
    } catch (e) {
        return { ok: false, error: "appka sa po registrácii nenačítala: " + page.url() };
    }
}
