// PSST — spoločné kroky pre Playwright testy: prihlásenie a registrácia cez MAS (chat.macet.eu/auth/, alebo auth.macet.eu).
// Element Web → "Continue"/"Create account" → stránka MAS → (súhlas) → späť do appky.
// PSST_HOST_IP: kam mapovať domény (127.0.0.1 na Macu, 172.30.0.250 = nginx v Docker sieti "psst")
const IP = (typeof process !== "undefined" && process.env.PSST_HOST_IP) || "127.0.0.1";
// MAS beží na https://chat.macet.eu/auth/ (D42) alebo na vlastnej subdoméne auth.macet.eu
export const MAS_URL_RE = /(auth\.macet\.eu|macet\.eu\/auth\/)/;
export const HOST_RULES = "--host-resolver-rules=" +
    ["chat", "app", "call", "auth", "ntfy", "turn"].map((h) => `MAP ${h}.macet.eu ${IP}`).join(", ");

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
        if (page.url().startsWith("https://app.macet.eu") || page.url().startsWith("vector://")) return;
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

// Registrácia s pozývacím tokenom cez MAS. Vráti { ok, error } — pri neplatnom tokene ok=false a text chyby.
// Tok MAS 1.29: (1) meno, heslo, potvrdenie, súhlas s podmienkami → (2) stránka "Registration token" → (3) súhlas → appka
export async function registerViaMas(page, user, password, token) {
    await page.goto("https://app.macet.eu/#/register");
    await page.locator('button:has-text("Continue")').first().click({ timeout: 90000 });
    await page.waitForURL(MAS_URL_RE, { timeout: 60000 });
    await page.waitForSelector('input[name="username"]', { timeout: 60000 });
    await page.fill('input[name="username"]', user);
    await page.fill('input[name="password"]', password);
    await page.fill('input[name="password_confirm"]', password);
    await page.check('input[name="accept_terms"]');
    // MAS overuje meno asynchrónne — odošli, kým sa neobjaví krok s tokenom
    for (let i = 0; i < 5 && !/\/token/.test(page.url()); i++) {
        await page.waitForTimeout(2500);
        await page.locator('button[type=submit]').first().click().catch(() => {});
        await page.waitForURL(/\/token/, { timeout: 5000 }).catch(() => {});
    }
    if (!/\/token/.test(page.url())) {
        return { ok: false, error: "krok s tokenom sa neobjavil: " + (await page.locator("body").innerText()).slice(0, 200) };
    }
    await page.fill('input[name="token"]', token);
    await page.locator('button[type=submit]').first().click();
    await page.waitForTimeout(3000);
    if (/\/token/.test(page.url())) {
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
