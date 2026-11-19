# psst Web + Desktop — rozhodnutia

Fork: [`georgonr/psst-web`](https://github.com/georgonr/psst-web), vetva **`psst`** založená na tagu
**`v1.12.35`** (element-web monorepo: `apps/web` + `apps/desktop`). Všetky zmeny kódu sú označené
komentárom `// PSST:` (v HTML `<!-- PSST: -->`). AGPL hlavičky a súbory `LICENSE-*` sú nedotknuté.

## Konfigurácia (config.json)

**W1 — Konfigurácia je v repe ako `apps/web/psst/config.json`, nie `apps/web/config.json`.**
Upstream má `/config.json` v `.gitignore` a varianty drží v `apps/web/element.io/<variant>/config.json`;
CI ho pred buildom skopíruje (`cp psst/config.json config.json`). Rovnako to robíme my — webpack potom
`config.json` sám skopíruje do `webapp/`. Desktop **nemá vlastnú kópiu**: balí `webapp/` z toho istého
behu (vrátane `config.json`), takže web a desktop majú konfiguráciu identickú z princípu (CI to overuje `cmp`).

**W2 — Homeserver napevno:** `default_server_config` = `https://chat.psst.pro` / `chat.psst.pro`,
`disable_custom_urls: true` (zmizne tlačidlo „Edit“ aj výber servera), `disable_guests: true`,
`disable_3pid_login: true` (Synapse nemá e-mail/SMS), bez identity servera
(`UIFeature.identityServer/thirdPartyId: false`), `default_federate: false` (federácia je na serveri vypnutá).
Nepoužívame `default_server_name`, aby sa pri štarte nerobil `.well-known` lookup — konfig je zdrojom pravdy.

**W3 — Registrácia cez registračný token bez úprav kódu.** Element Web má UIA stupeň
`m.login.registration_token` (`RegistrationTokenAuthEntry`) natívne. Stačí nechať `UIFeature.registration`
zapnuté (default) — odkaz „Create account“ sa ukáže, keď Synapse v `/register` flows ponúkne token stupeň
(`enable_registration: true` + `registration_requires_token: true` rieši serverová časť).

**W4 — Uvítacia stránka vypnutá:** `embedded_pages.login_for_welcome: true` → namiesto `welcome.html`
(odkazy na matrix.org/element.io) sa hneď ukáže prihlásenie.

**W5 — Odstránené tretie strany cez konfig:**
- integračný manažér: `integrations_ui_url/rest_url: null`, `integrations_widgets_urls: []` (SdkConfig default je Scalar);
- rageshake/bug report: `bug_report_endpoint_url` chýba → celá funkcia je vypnutá; `UIFeature.feedback: false`;
- analytika: žiadny `posthog` → `PosthogAnalytics.isEnabled()` je false a opt-in toast sa **nikdy** nezobrazí
  (MatrixChat ho podmieňuje práve tým); žiadny `sentry` (web aj desktop čítajú DSN len z konfigu);
- mapy: žiadny `map_style_url` a `UIFeature.locationSharing: false` (bez vlastného tile servera by zdieľanie polohy aj tak nefungovalo);
- stiahnutie aplikácií: `desktop_builds.available: false`, `mobile_builds.{ios,android,fdroid}: null`, `mobile_guide_toast: false`;
- `terms_and_conditions_links`, `privacy_policy_url` sa nenastavujú (žiadne element.io odkazy);
- `help_url`, `help_encryption_url`, `help_key_storage_url` → `https://github.com/georgonr/psst`.
- `UIFeature.allowCreatingPublicRooms/Spaces: false` — uzavretý server, verejný adresár nemá zmysel.
- `MessageComposerInput.showStickersButton: false` — nálepky potrebujú integračný manažér.

**W6 — Skupinové hovory = Element Call (embedded), Jitsi nie.** `element_call.use_exclusively: true`
→ `useRoomCall` ponúka len `PlatformCallType.ElementCall` (ani legacy 1:1, ani Jitsi widget). Element Web
1.12.35 balí `@element-hq/element-call-embedded` 0.28.2 do `webapp/widgets/element-call/` a widget URL je
vždy lokálna kópia (`./widgets/element-call/`) — žiadny call.element.io. LiveKit fókus si klient berie z
`.well-known/matrix/client` → `org.matrix.msc4143.rtc_foci` (resp. `/rtc/transports`) homeservera; tlačidlá
hovoru sú aktívne až keď server takú transport-konfiguráciu ponúka (`serverIsConfiguredForElementCall`).
`element_call.brand: "psst call"`. Labs `feature_video_rooms` + `feature_element_call_video_rooms` ponechané
ako v upstream release konfigu.
Jitsi: konfig `jitsi` nenastavujeme; v kóde zostáva fallback `meet.element.io` (SdkConfig default,
`Jitsi.ts`, v1 widgety), ale pri `use_exclusively` a bez integračného manažéra sa naň nedá dostať.

**W7 — Téma: vlastná tmavá téma `custom-psst` ako default** (`default_theme: "custom-psst"`,
`use_system_theme: false`). Definovaná v `setting_defaults.custom_themes` (konfig-level, funguje aj pred
prihlásením): legacy farby (`accent-color`/`primary-color` = `#38BDF8`, pozadia slate `#0F172A`…) plus
Compound sémantické tokeny akcentu (`--cpd-color-bg-accent-*`, `--cpd-color-text-action-accent`,
`--cpd-color-icon-accent-*`, `--cpd-color-border-accent-*`) → akcent je `#38BDF8` aj v nových Compound
komponentoch. Používateľ si môže v Nastaveniach vybrať inú tému. Dôvod konfig-témy namiesto úpravy CSS:
žiadny zásah do `res/themes`, ľahké merge z upstreamu.

## Branding v kóde/assetoch

**W8 — Ikony a artwork generované z `assets/psst-logo.svg`** (hlavné repo): `res/vector-icons/*`
(24…1024, + maskable 192/512, favicon.svg/ico), auth logo `themes/element/img/psst/psst-wordmark.svg`
(biely text — vhodné na tmavé pozadie), pozadie auth stránky `themes/element/img/psst/background.svg`
(tmavý gradient namiesto Element fotky jazera). Pôvodné Element súbory ostali v repe (nepoužité),
aby boli merge z upstreamu bez konfliktov.

**W9 — `index.html`, PWA manifest, statické chybové stránky** prepísané na „psst“ (title, app-name,
theme-color `#0F172A`, manifest name/short_name/id `eu.macet.psst`, maskable ikony, bez
`related_applications` s Element apkami). `unable-to-load.html` / `incompatible-browser.html`: psst logo,
odkaz na app.psst.pro, odstránená sekcia „Use Element on mobile“ s App Store/Play odkazmi.
Default `og:image` → `https://app.psst.pro/vector-icons/512.png` (webpack).

**W10 — Minimálne zmeny kódu (každá `// PSST:`):**
1. `AuthFooter.tsx` — odstránený napevno zadaný odkaz „Powered by Matrix“ (matrix.org); päta zobrazuje
   len `branding.auth_footer_links` z konfigu = odkazy na zdrojový kód.
2. `HelpUserSettingsTab.tsx` — nová sekcia **Source code** (Help & About) s odkazmi na
   github.com/georgonr/psst a github.com/georgonr/psst-web + veta o AGPL-3.0 (splnenie §13 AGPL).
   Text nie je prekladaný zámerne (licenčný text, ako Credits).
3. Napevno zadané odkazy na `element.io/help#…` / `docs.element.io` (SetupEncryptionToast,
   SetupEncryptionBody, SecurityRoomSettingsTab, NotificationSettings2, LogoutDialog, UserIdentityWarning)
   → `SdkConfig.get("help_url")`.
4. `ElectronPlatform.tsx` — SSO callback schéma `psst` namiesto `element`; default OAuth `client_uri`
   `https://app.psst.pro` (D85; pôvodne apex starej domény) namiesto `https://element.io`.
5. `apps/desktop/src/protocol.ts` — legacy schéma `psst` namiesto `element`.
6. `webpack.config.ts` — default og:image (viď W9).

## Desktop

**D-1 — Variant `apps/desktop/psst/build.json`:** `appId: eu.macet.psst`, `name`/`productName: psst`,
`protocols: ["eu.macet.psst", "psst"]`. `electron-builder.ts` ho berie ako default (`DEFAULT_VARIANT`),
CI ho navyše explicitne podáva cez `VARIANT_PATH`. `package.json`: productName/author/homepage psst
(meno balíčka `element-desktop` ostáva kvôli pnpm `--filter`).

**D-2 — URL schémy:** OAuth callback `pro.psst.app` (reverse-DNS `app.psst.pro` → v scope MAS/OIDC politiky pre
`client_uri https://app.psst.pro`, D85), ďalej `eu.macet.psst` (identifikátor appky) a legacy SSO schéma `psst`. `element://` ani `io.element.desktop://`
neregistrujeme, aby psst nekolidoval s nainštalovaným Element Desktop.

**D-3 — Žiadny auto-updater:** konfig neobsahuje `update_base_url` → `electron-main` vypíše
„No update_base_url is defined: auto update is disabled“; nič nekontaktuje packages.element.io.
`web_base_url: https://app.psst.pro/` (popout widgetov), `help_url` na GitHub (menu Help).
Squirrel.Windows aj tak inštaluje per-user; MSI per-machine (upstream nastavenie).

**D-4 — Ikony desktopu:** `build/icon.icns` (psst.icns), `build/icon.ico`, `build/icon.png` (512),
`build/install-spinner.gif` (Squirrel splash 320×320, generovaný Python stdlib GIF enkodérom z tej istej
geometrie). Upstream `build/icon.icon` (Icon Composer bundle s Element logom, vyžaduje Xcode 26 actool)
je zmazaný a `mac.icon` ukazuje na `.icns` → build funguje na `macos-15` bez Xcode 26.
`dmg.badgeIcon` odstránený (vyžadoval pyobjc Quartz na runneri); DMG má ikonu aplikácie.
`deb.recommends: element-io-archive-keyring` odstránené.

**D-5 — Seshat (lokálne vyhľadávanie v šifrovaných miestnostiach) ponechaný.** `@matrix-org/seshat` 6.x
má predkompilované binárky (optional deps per platforma), natívny build sa nerobí → CI neblokuje.
Pre universal macOS build sa (ako upstream) inštalujú x64 aj arm64 binárky (`supportedArchitectures`).

**D-6 — Bez podpisu.** macOS: `CSC_IDENTITY_AUTO_DISCOVERY=false`, bez notarizácie (ad-hoc podpis
cez fuse `resetAdHocDarwinSignature`) → pri prvom spustení treba pravý klik → Otvoriť / `xattr -dr
com.apple.quarantine`. Windows: bez eSigner/Authenticode → SmartScreen varovanie.
Targets: macOS universal `dmg` + `zip`, Windows x64 `squirrel` (Setup .exe) + `msi`. Linux vynechaný (voliteľný).

## CI

**C-1 — Workflow `ci/workflows/web-desktop.yml` v hlavnom repe** (D5 v DECISIONS.md; do `.github/workflows/` ho skopíruje `scripts/enable-ci.sh`, keď bude mať token scope `workflow` — GitHub inak push odmietne), checkoutuje
`georgonr/psst-web@psst` (vstup `web_ref`). Kroky kopírujú upstream (`scripts/layered.sh`,
`pnpm run build`, `pnpm install --filter element-desktop`, `asar-webapp`, `build:universal`/`build`).
Rozdiel: web build **bez `CI_PACKAGE`** (upstream ním vypína minifikáciu v PR buildoch; my chceme produkčný,
minifikovaný bundle). Desktop joby nesťahujú Element z packages.element.io (`pnpm run fetch`), ale
rozbalia artefakt `psst-web-dist` z toho istého behu → `webapp.asar`.

**C-2 — Upstream workflowy vo forku sú vypnuté** (`gh api -X PUT repos/georgonr/psst-web/actions/permissions enabled=false`),
aby push do forku nespúšťal Element publikovacie/Netlify/Localazy joby.

**C-3 — Smoke test** (`scripts/web/smoke.mjs`, Playwright Chromium): servuje rozbalený dist lokálne,
overí `config.json` (homeserver, disable_custom_urls, žiadne posthog/sentry/rageshake/integrácie/element.io URL),
manifest, prítomnosť embedded Element Call, a na `#/login`: server `chat.psst.pro`, žiadne tlačidlo „Edit“,
title „psst“, psst wordmark, aktívna téma (`--accent-color: #38BDF8`). Screenshoty `login.png`, `register.png`
v artefakte `psst-web-smoke`. Test nepotrebuje bežiaci homeserver (Element validuje `default_server_config`
pri štarte len syntakticky).
