// PSST (D75): shared checks of Settings → "Notifications & calls" for alerts-web.mjs and alerts-desktop.mjs.
// The screen marks each row with data-psst-row / data-on / data-code; the switch is the row's checkbox.
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Counts notifications (without changing Notification.permission) and started/stopped audio buffers. */
export const ALERT_HOOK = `(() => {
    if (window.__psstAlertHook) return; window.__psstAlertHook = 1;
    window.__psstAlertNotes = []; window.__psstAudio = [];
    const N = window.Notification;
    if (N) {
        const W = function (title, opts) { window.__psstAlertNotes.push({ title, body: opts && opts.body, at: Date.now() }); return new N(title, opts); };
        W.prototype = N.prototype;
        Object.defineProperty(W, "permission", { get: () => N.permission });
        W.requestPermission = (...a) => N.requestPermission(...a);
        window.Notification = W;
    }
    if (window.AudioBufferSourceNode) {
        const P = AudioBufferSourceNode.prototype, start = P.start, stop = P.stop;
        P.start = function (...a) { this.__psstId = window.__psstAudio.length; window.__psstAudio.push({ loop: this.loop, dur: this.buffer && this.buffer.duration, start: Date.now() }); return start.apply(this, a); };
        P.stop = function (...a) { const e = window.__psstAudio[this.__psstId]; if (e) e.stop = Date.now(); return stop.apply(this, a); };
    }
})();`;

export async function hook(p) {
    await p.evaluate(ALERT_HOOK).catch(() => {});
}

export const TAB_ID = "USER_PSST_ALERTS_TAB";

/** Open the tab through the user menu like a person would; falls back to the dispatcher. */
export async function openAlertsTab(p, label = /Notifications & calls|Upozornenia a hovory/) {
    if (await p.locator("[data-psst-row]").count()) return "already";
    try {
        for (let i = 0; i < 2; i++) await p.keyboard.press("Escape").catch(() => {});
        await p.locator('[aria-label="User menu"], [aria-label="Používateľská ponuka"]').first().click({ timeout: 10000 });
        await p.locator('[role=menuitem]:has-text("All settings"), [role=menuitem]:has-text("Všetky nastavenia")').first().click({ timeout: 10000 });
        await p.getByRole("tab", { name: label }).first().click({ timeout: 10000 });
        await p.locator("[data-psst-row]").first().waitFor({ timeout: 20000 });
        return "ui";
    } catch {
        await p.evaluate((tab) => window.mxDispatcher.dispatch({ action: "view_user_settings", initialTabId: tab }), TAB_ID);
        await p.locator("[data-psst-row]").first().waitFor({ timeout: 20000 });
        return "dispatcher";
    }
}

export async function closeDialog(p) {
    for (let i = 0; i < 2; i++) await p.keyboard.press("Escape").catch(() => {});
    await sleep(500);
}

export async function readRows(p) {
    return p.$$eval("[data-psst-row]", (els) =>
        els.map((e) => ({
            id: e.dataset.psstRow,
            on: e.dataset.on ?? null,
            state: e.dataset.state ?? null,
            code: e.dataset.code,
            need: e.dataset.need ?? null,
            checked: e.querySelector("input[type=checkbox]")?.checked ?? null,
            disabled: e.querySelector("input[type=checkbox]")?.disabled ?? null,
            label: e.querySelector("label")?.textContent?.trim() ?? null,
            text: (e.querySelector("[data-psst-state]") ?? e).textContent.trim().slice(0, 240),
            hint: e.querySelector("[data-psst-hint]")?.textContent?.trim() ?? null,
        })),
    );
}

export const row = (rows, id) => rows.find((r) => r.id === id);

/** Re-read like after returning from system settings: the screen listens to focus / visibilitychange. */
export async function refocus(p, wait = 2500) {
    await p.evaluate(() => window.dispatchEvent(new Event("focus")));
    await sleep(wait);
    return readRows(p);
}

export async function clickToggle(p, id, wait = 3000) {
    await p.locator(`[data-psst-row="${id}"] input[type=checkbox]`).click({ force: true });
    await sleep(wait);
    return readRows(p);
}

/** Wait until a row's data-on matches. */
export async function waitRow(p, id, on, timeout = 20000) {
    const end = Date.now() + timeout;
    let rows;
    while (Date.now() < end) {
        rows = await readRows(p);
        if (row(rows, id)?.on === String(on)) return rows;
        await sleep(700);
    }
    return rows;
}

/** "Send test notification": counts new Notification objects created by the platform notifier. */
export async function testNotification(p) {
    const before = await p.evaluate(() => (window.__psstAlertNotes || []).length);
    await p.locator('[data-psst-test="notification"]').click();
    await sleep(2500);
    return p.evaluate((b) => ({
        notes: (window.__psstAlertNotes || []).slice(b),
        result: document.querySelector("[data-psst-test-result]")?.textContent ?? null,
    }), before);
}

/** "Test ringing": a looping buffer must start and stop after ~5 s (or when Stop is pressed). */
export async function testRinging(p, { stopAfterMs = null } = {}) {
    const before = await p.evaluate(() => (window.__psstAudio || []).length);
    const t0 = Date.now();
    await p.locator('[data-psst-test="ringing"]').click();
    let playing = false;
    for (let i = 0; i < 20 && !playing; i++) {
        await sleep(250);
        playing = (await p.locator('[data-psst-test="ringing"]').getAttribute("data-ringing")) === "true";
    }
    if (stopAfterMs !== null) {
        await sleep(stopAfterMs);
        await p.locator('[data-psst-test="ringing"]').click();
    }
    let ended = false;
    for (let i = 0; i < 40 && !ended; i++) {
        await sleep(250);
        ended = (await p.locator('[data-psst-test="ringing"]').getAttribute("data-ringing")) === "false";
    }
    const audio = await p.evaluate((b) => (window.__psstAudio || []).slice(b), before);
    const ring = audio.find((a) => a.loop);
    return {
        playing,
        ended,
        endedAfterMs: Date.now() - t0,
        ringStarted: !!ring,
        ringDurationMs: ring && ring.stop ? ring.stop - ring.start : null,
        audio,
    };
}
