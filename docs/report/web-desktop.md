# psst Web + Desktop — report

Stav k 2026-11-13.

## Fork

- Repo: https://github.com/georgonr/psst-web, vetva **`psst`**, HEAD **`43a441c9c8e48f3178e963ac99bb760075a58cf4`**
  (base tag `v1.12.35` = `7001d81`). Pushnuté.
- Upstream GitHub Actions vo forku vypnuté (`actions/permissions enabled=false`).

Commity na `psst`:

| SHA | Obsah |
|---|---|
| `bf1eb5e` | psst ikony/artwork: `res/vector-icons/*` (24–1024, maskable, favicon.svg/ico), wordmark + pozadie auth stránky, desktop `icon.icns/ico/png`, Squirrel splash GIF; zmazaný Element `build/icon.icon` |
| `0c26748` | `index.html` (title, app-name, theme-color, svg favicon), PWA manifest (psst, `eu.macet.psst`, maskable ikony, bez Element related_applications), statické chybové stránky, default og:image |
| `ac23331` | Help & About: sekcia **Source code** (github.com/georgonr/psst, github.com/georgonr/psst-web, AGPL veta); auth päta bez matrix.org odkazu |
| `0ee27c0` | napevno zadané element.io/docs.element.io help odkazy → `help_url` (6 súborov) |
| `44149fa` | desktop URL schémy `eu.macet.psst` + `psst` (namiesto `io.element.desktop`/`element`), OAuth client_uri `https://macet.eu` |
| `43a441c` | `apps/web/psst/config.json` (shipped konfig), `apps/desktop/psst/build.json` (appId `eu.macet.psst`, productName `psst`), electron-builder (default variant, `.icns`, bez DMG badge, bez element apt keyring), desktop `package.json` (productName/author/homepage) |

Shipped konfig: `apps/web/psst/config.json` (CI → `apps/web/config.json` → `webapp/config.json`; desktop balí ten istý `webapp/`).
Kľúčové hodnoty: `chat.macet.eu`, `disable_custom_urls`, `disable_guests`, `disable_3pid_login`, bez posthog/sentry/
rageshake/integračného manažéra/map/jitsi, `element_call.use_exclusively`, `default_theme: custom-psst` (akcent `#38BDF8`),
`login_for_welcome`, `desktop_builds.available: false`, `mobile_builds: null`, bez `update_base_url`.

Overenie lokálne (bez inštalácie monorepa): všetky upravené `.ts/.tsx` prešli syntaktickou kontrolou cez esbuild;
`config.json` je validný JSON; grep: v konfigu nie je žiadna element.io / matrix.org / vector.im URL.

## CI

- Workflow: `ci/workflows/web-desktop.yml` (joby `web`, `web-smoke`, `desktop-mac`, `desktop-win`),
  smoke test `scripts/web/smoke.mjs`. `actionlint` bez nálezov, YAML validné.
- **pending: requires workflow scope** — token `georgonr` nemá scope `workflow`, GitHub odmieta push
  `.github/workflows/*`. Po `gh auth refresh -h github.com -s workflow` spustiť `./scripts/enable-ci.sh`
  (alebo `gh workflow run web-desktop.yml -R georgonr/psst`).

| Job | Stav | Artefakt |
|---|---|---|
| web | pending: requires workflow scope | `psst-web-dist` (tar.gz) |
| web-smoke | pending: requires workflow scope | `psst-web-smoke` (login.png, register.png, smoke-result.json) |
| desktop-mac | pending: requires workflow scope | `psst-desktop-macos` (universal dmg + zip, unsigned) |
| desktop-win | pending: requires workflow scope | `psst-desktop-windows` (Setup .exe + .msi, unsigned) |

Run URL: — (zatiaľ žiadny beh). Lokálne artefakty v `dist/`: žiadne (pending).
Smoke test výsledky: pending.

## Otvorené body / riziká

1. **CI nikdy nebežalo** → build web/desktop nie je overený; prvý beh môže potrebovať drobné opravy
   (najpravdepodobnejšie: názvy výstupných súborov electron-buildera v kontrolných krokoch, Windows `tar/cmp` v bash).
2. Smoke check „no 'Element' in visible text“ na login obrazovke je prísny — ak zlyhá na nejakom upstream reťazci
   (napr. prekladový text s „Element“), treba ho buď opraviť vo forku, alebo uvoľniť check.
3. Zostávajúce Element zmienky mimo hlavných obrazoviek: prekladové reťazce s napevno „Element“ (napr.
   „Element Call“ v nastaveniach, konzolová poznámka), stránka `/mobile_guide/` (odkazy na Element X — dostupná len
   priamou URL), Jitsi fallback `meet.element.io` v kóde (nedosiahnuteľný pri `use_exclusively`).
4. Skupinové hovory fungujú až keď homeserver ponúkne `org.matrix.msc4143.rtc_foci` v `.well-known/matrix/client`
   (serverová časť). `https://chat.macet.eu` a `https://app.macet.eu` v čase písania neodpovedali.
5. macOS/Windows buildy sú nepodpísané (Gatekeeper / SmartScreen varovanie), bez auto-updatu.
6. **iCloud eviction:** `~/Desktop` je synchronizovaný cez iCloud s „Optimize storage“; pri ~5 GB voľného miesta
   macOS zmenil tisíce súborov na „dataless“ (vrátane `forks/web` ~4900 súborov a dočasne `.git/HEAD` hlavného repa),
   čítanie vracia prázdny obsah / visí. Lokálna kópia `forks/web` preto nie je spoľahlivá — zdrojom pravdy je
   GitHub vetva `psst`. Odporúčanie: presunúť repo mimo `~/Desktop` alebo vypnúť Optimize Mac Storage.
