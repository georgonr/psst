// PSST audit helper for Android message search (docs/android-search.md): web partners that build the test data.
//   node search-partner.mjs <accounts-file> <out-dir>
// <accounts-file>: three lines "<user> <password>" (qa-* test accounts only, never real users): the Android user A (also
// signed in here on the web), partners B and C. Browser profiles persist in <out-dir>/profiles, so a restart of this
// script keeps the same devices. A signs in on Android first and creates the recovery key there; put it into
// <out-dir>/recovery-<A>.txt and this script confirms A's web session with it.
// Commands written to <out-dir>/NEXT (one per run, result in <out-dir>/DONE + log.txt):
//   setup                            B: encrypted DM B↔A, encrypted group B+A+C, public unencrypted channel;
//                                    A/C join → <out-dir>/rooms.json
//   seed <dm|group|channel> <n>      n corpus messages (B, in group/channel alternating with C), oldest first;
//                                    expected matches → <out-dir>/expected-<room>.json
//   send <room> <text>               B sends text → <out-dir>/last.json {room, id}
//   edit <room> <eventId> <text>     B edits its message
//   redact <room> <eventId>          B deletes its message
//   shot <user>                      screenshot of that partner's page → <out-dir>/shot-<user>.png
//   eval <user> <file.js>            evaluate an async function expression from file in that page → <out-dir>/eval.json
//   quit
import { chromium } from "playwright";
import fs from "node:fs";

const [accountsFile, out] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (s) => { const l = `[${new Date().toISOString().slice(11, 19)}] ${s}`; console.log(l); fs.appendFileSync(`${out}/log.txt`, l + "\n"); };
const lines = fs.readFileSync(accountsFile, "utf8").trim().split("\n").map((l) => l.trim().split(/\s+/));
const acc = Object.fromEntries(lines);
const [A, B, C] = lines.map((l) => l[0]);
if (![A, B, C].every((u) => /^qa-[a-z0-9-]+$/.test(u))) throw new Error("test accounts must be qa-*");
const HS = "chat.psst.pro";
const SN = process.env.PSST_SERVER_NAME || "psst.pro";   // Matrix server_name (user IDs), D85
const mx = (u) => `@${u}:${SN}`;

// ---------------------------------------------------------------------------------------------------------- corpus
const WORDS = ("dobrý deň ako sa máš zajtra stretnutie kancelária obed káva čaj počasie dážď slnko víkend výlet hory more " +
    "auto vlak autobus lístok faktúra zmluva projekt termín porada prezentácia dokument tabuľka heslo telefón počítač " +
    "tlačiareň kľúč dvere okno stôl stolička kniha film hudba pieseň koncert divadlo večera raňajky mlieko chlieb maslo " +
    "syr vajce jablko hruška slivka čerešňa ryža polievka mäso zelenina ovocie škola učiteľ žiak úloha skúška známka " +
    "prázdniny Vianoce narodeniny darček oslava svadba rodina mama otec brat sestra babka dedko pes mačka vták ryba " +
    "záhrada kvet strom tráva jeseň zima jar leto ráno večer noc týždeň mesiac rok pondelok utorok streda štvrtok piatok " +
    "sobota nedeľa").split(" ");
// Words with diacritics whose matches are counted exactly (query without diacritics → expected count).
const SPECIAL = [
    { every: 17, at: 0, word: "číslo" },
    { every: 29, at: 5, word: "čísla" },
    { every: 23, at: 3, word: "šťastný" },
    { every: 11, at: 4, word: "ďakujem" },
    { every: 31, at: 7, word: "Žltý" },
    { every: 13, at: 9, word: "kôň" },
];
const ROOM_WORD = { dm: "jahodový", group: "malinový", channel: "čučoriedkový" };
function rng(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32); }
function corpus(room, n) {
    const r = rng(room.length * 7919 + n);
    const msgs = [];
    for (let i = 0; i < n; i++) {
        const words = [];
        const len = 6 + Math.floor(r() * 10);
        for (let k = 0; k < len; k++) words.push(WORDS[Math.floor(r() * WORDS.length)]);
        for (const s of SPECIAL) if (i % s.every === s.at) words.splice(Math.floor(r() * words.length), 0, s.word);
        if (i % 10 === 0) words.push(ROOM_WORD[room]);
        let body = `${room} ${String(i).padStart(3, "0")}: ${words.join(" ")}.`;
        if (i === 0) body = `Prvá správa histórie (${room}): pradávny začiatok, ${ROOM_WORD[room]} ${body}`;
        msgs.push(body);
    }
    return msgs;
}
const fold = (s) => s.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
function expected(msgs) {
    const q = { cislo: "cislo", cisl: "cisl", stastny: "stastny", dakujem: "dakujem", zlty: "zlty", kon: "kon", pradavny: "pradavny" };
    const res = {};
    for (const [k, prefix] of Object.entries(q)) res[k] = msgs.filter((m) => fold(m).split(/[^\p{L}\p{N}]+/u).some((w) => w.startsWith(prefix))).length;
    return res;
}

// ------------------------------------------------------------------------------------------------------- browsers
const contexts = [];
const APP = ".mx_LeftPanel, .mx_RoomListPanel";
async function login(user) {
    const ctx = await chromium.launchPersistentContext(`${out}/profiles/${user}`, { viewport: { width: 1280, height: 900 } });
    contexts.push(ctx);
    const p = ctx.pages()[0] ?? await ctx.newPage();
    log(`${user}: opening the web app`);
    await p.goto("https://app.psst.pro/#/home");
    for (let i = 0; i < 30; i++) { if (await p.locator(`${APP}, button:has-text("Use recovery key"), button:has-text("Continue")`).count()) break; await sleep(1000); }
    if (await p.locator(`${APP}, button:has-text("Use recovery key")`).count() === 0) {
        // no stored session in the profile: sign in (MAS)
        log(`${user}: signing in`);
        await p.goto("https://app.psst.pro/#/login");
        await p.locator('button:has-text("Continue")').first().click({ timeout: 90000 });
        await p.waitForURL(/auth/, { timeout: 60000 });
        // MAS: sign-in form, or (a MAS session is still in the profile) only the consent "Continue"
        for (let i = 0; i < 60 && !p.url().startsWith("https://app.psst.pro"); i++) {
            if (await p.locator('input[name="username"]').count()) {
                await p.fill('input[name="username"]', user); await p.fill('input[name="password"]', acc[user]);
                await p.locator("button[type=submit]").first().click();
            } else await p.locator('button[type=submit]:has-text("Continue")').first().click({ timeout: 1500 }).catch(() => {});
            await sleep(1500);
        }
        for (let i = 0; i < 90; i++) { if (await p.locator(`${APP}, button:has-text("Use recovery key")`).count()) break; await sleep(1000); }
    }
    const keyFile = `${out}/recovery-${user}.txt`;
    if (await p.locator('button:has-text("Use recovery key")').count() && fs.existsSync(keyFile)) {
        // a second device of an account with an identity: confirm it with the recovery key
        log(`${user}: confirming the identity with the recovery key`);
        await p.locator('button:has-text("Use recovery key")').first().click();
        await sleep(1500);
        await p.locator("input:not([type=hidden]), textarea").last().fill(fs.readFileSync(keyFile, "utf8").trim());
        await p.locator('button:has-text("Continue")').first().click({ timeout: 10000 });
        for (let i = 0; i < 60; i++) { if (await p.locator(APP).count()) break; await p.locator('button:has-text("Done"), button:has-text("Continue")').first().click({ timeout: 1000 }).catch(() => {}); await sleep(1000); }
    }
    await p.screenshot({ path: `${out}/login-${user}.png` });
    await sleep(3000);
    for (const name of ["Not now", "Close", "OK", "Later", "Got it", "Done", "Dismiss"]) await p.getByRole("button", { name, exact: true }).first().click({ timeout: 500 }).catch(() => {});
    const who = await p.evaluate(async () => { const c = window.mxMatrixClientPeg.get(); const s = await c.getCrypto().getDeviceVerificationStatus(c.getUserId(), c.getDeviceId()); return `${c.getUserId()} device ${c.getDeviceId()} verified ${!!s?.crossSigningVerified}`; });
    log(`signed in ${who}`);
    return p;
}
const P = {};
for (const u of [A, B, C]) P[u] = await login(u);
const roomsFile = `${out}/rooms.json`;
let rooms = fs.existsSync(roomsFile) ? JSON.parse(fs.readFileSync(roomsFile, "utf8")) : {};

async function setup() {
    const enc = [{ type: "m.room.encryption", state_key: "", content: { algorithm: "m.megolm.v1.aes-sha2" } }];
    rooms = await P[B].evaluate(async ([s1, s3, enc]) => {
        const c = window.mxMatrixClientPeg.get();
        const dm = (await c.createRoom({ preset: "trusted_private_chat", is_direct: true, invite: [s1], initial_state: enc })).room_id;
        await c.setAccountData("m.direct", { [s1]: [dm] });
        const group = (await c.createRoom({ preset: "private_chat", name: "Hľadanie QA skupina", invite: [s1, s3], initial_state: enc })).room_id;
        // public channel: anyone can join, not encrypted, NOT published in the room directory (keeps it out of real users' view)
        const channel = (await c.createRoom({ preset: "public_chat", name: "Hľadanie QA kanál", visibility: "private" })).room_id;
        return { dm, group, channel };
    }, [mx(A), mx(C), enc]);
    for (const u of [A, C]) {
        await P[u].evaluate(async ([r, s2, isA]) => {
            const c = window.mxMatrixClientPeg.get();
            for (const id of [isA ? r.dm : null, r.group, r.channel].filter(Boolean)) await c.joinRoom(id);
            if (isA) await c.setAccountData("m.direct", { [s2]: [r.dm] });
        }, [rooms, mx(B), u === A]);
    }
    fs.writeFileSync(roomsFile, JSON.stringify(rooms, null, 1));
    log(`rooms ${JSON.stringify(rooms)}`);
}

async function send(user, roomKey, body) {
    return P[user].evaluate(async ([r, b]) => (await window.mxMatrixClientPeg.get().sendTextMessage(r, b)).event_id, [rooms[roomKey], body]);
}

async function seed(roomKey, n) {
    const msgs = corpus(roomKey, n);
    fs.writeFileSync(`${out}/expected-${roomKey}.json`, JSON.stringify({ n, ...expected(msgs) }, null, 1));
    const t0 = Date.now();
    for (let i = 0; i < msgs.length; i++) {
        const user = roomKey !== "dm" && i % 3 === 2 ? C : B;
        for (let a = 0; ; a++) {
            try { await send(user, roomKey, msgs[i]); break; } catch (e) { if (a > 5) throw e; await sleep(2000 * (a + 1)); }
        }
        if (i % 50 === 49) log(`seed ${roomKey} ${i + 1}/${n}`);
    }
    log(`seeded ${roomKey} ${n} messages in ${Math.round((Date.now() - t0) / 1000)} s`);
}

log("READY");
fs.writeFileSync(`${out}/READY`, String(Date.now()));
for (;;) {
    await sleep(700);
    if (!fs.existsSync(`${out}/NEXT`)) continue;
    const cmd = fs.readFileSync(`${out}/NEXT`, "utf8").trim(); fs.unlinkSync(`${out}/NEXT`);
    log("cmd " + cmd.slice(0, 120));
    const [verb, a1, a2, ...rest] = cmd.split(" ");
    try {
        if (verb === "quit") break;
        if (verb === "setup") await setup();
        if (verb === "seed") await seed(a1, Number(a2));
        if (verb === "send") {
            const id = await send(B, a1, [a2, ...rest].join(" "));
            fs.writeFileSync(`${out}/last.json`, JSON.stringify({ room: a1, id }));
            log(`sent ${id}`);
        }
        if (verb === "edit") {
            const text = rest.join(" ");
            await P[B].evaluate(async ([r, id, t]) => window.mxMatrixClientPeg.get().sendMessage(r, {
                msgtype: "m.text", body: `* ${t}`, "m.new_content": { msgtype: "m.text", body: t },
                "m.relates_to": { rel_type: "m.replace", event_id: id },
            }), [rooms[a1], a2, text]);
            log(`edited ${a2}`);
        }
        if (verb === "shot") await P[a1].screenshot({ path: `${out}/shot-${a1}.png` });
        if (verb === "eval") {
            const r = await P[a1].evaluate(`(${fs.readFileSync(a2, "utf8")})()`);
            fs.writeFileSync(`${out}/eval.json`, JSON.stringify(r ?? null, null, 1));
            log(`eval → ${JSON.stringify(r ?? null).slice(0, 200)}`);
        }
        if (verb === "redact") { await P[B].evaluate(async ([r, id]) => window.mxMatrixClientPeg.get().redactEvent(r, id), [rooms[a1], a2]); log(`redacted ${a2}`); }
    } catch (e) { log("ERR " + String(e.message).split("\n")[0]); }
    fs.writeFileSync(`${out}/DONE`, `${Date.now()} ${cmd.slice(0, 60)}`);
}
for (const c of contexts) await c.close();
