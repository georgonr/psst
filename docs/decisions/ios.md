# PSST iOS — rozhodnutia

Fork: [`georgonr/psst-ios`](https://github.com/georgonr/psst-ios), vetva **`psst`** založená na tagu
`release/26.11.0` (Element X iOS 26.11.0, najnovšia stabilná verzia k 2026-11-13). Každá zmena v kóde je
označená komentárom `// PSST:` (v YAML `# PSST:`), aby sa dala pri zlučovaní upstreamu ľahko nájsť
(`git grep -n "PSST"`).

## Prostredie

**I1 — Build a spustenie v simulátore iba na GitHub Actions (`macos-26`, Xcode 27).**
Upstream 26.11.0 vyžaduje Xcode 27: `ci_scripts/ci_common.sh` volá `xcode-select -s /Applications/Xcode_27.app`,
všetky ich macOS workflowy bežia na runneri `xcode-27`, `Package.swift` má `swift-tools-version: 6.2` a
deployment target je iOS 18.5. Lokálne je Xcode 16.0 na Intel Macu so ~6 GB voľného miesta — nestačí ani verzia,
ani miesto (SPM závislosti vrátane `MatrixRustSDK` xcframeworku majú niekoľko GB). GitHub-hosted image
`macos-26` (arm64) obsahuje Xcode 27; workflow si vyberie najnovší `/Applications/Xcode_27*.app` (nie beta) a
pri jeho absencii skončí jasnou chybou. Upstream `ARCHS: arm64` sedí s arm64 runnerom.

**I2 — Pracovná kópia forku mimo iCloud nebola možná natrvalo.** `~/Desktop` je synchronizovaný cez iCloud a pri
takmer plnom disku macOS „vyprázdnil" (dataless) súbory v `.git` (`HEAD`, `config`, …), takže `git` hlásil
„not a git repository". Práca preto prebiehala v dočasnom klone v `~/Developer`, ktorý sa po pushnutí zmazal;
`forks/ios` je čerstvý plytký klon vetvy `psst`. Ak sa `.git` znova vyprázdni, stačí `forks/ios` zmazať a
naklonovať znova (`git clone --depth 1 --branch psst https://github.com/georgonr/psst-ios forks/ios`).
V klone je LFS filter vypnutý (`git config filter.lfs.smudge cat` …) — `git-lfs` nie je nainštalovaný a LFS
obsahuje iba snapshoty testov a vývojové médiá.

**I3 — CI workflowy sú v hlavnom repe** (`.github/workflows/ios.yml`, `ios-release.yml`), fork sa checkoutuje
na vetve `psst` (zhodne s D5). Lint (SwiftLint/SwiftFormat) sa v CI vynecháva: post-build fázy hľadajú nástroje
cez `PATH`, preto workflow pridá no-op shimy. SwiftGen/Sourcery sa neinštalujú — vygenerované súbory
(`Generated/Strings.swift`, mocky) sú v repe commitnuté a fázy bez nástroja len vypíšu warning.
Unit/UI testy sa nespúšťajú (testy ako `AppSettingsTests` predpokladajú matrix.org a Element URL).

**I4 — Simulátorový build v konfigurácii `Debug`** (voliteľne `Release` cez input). Debug je na 3-jadrovom
runneri so 7 GB RAM výrazne rýchlejší a nehrozí OOM pri whole-module optimalizácii obrovského modulu ElementX.
Dôsledok: na úvodnej obrazovke je vedľa verzie malá ikona „developer options" (v Release nie je). Release
konfiguráciu kompiluje `ios-release.yml` (archive).

## Identita aplikácie

**I5 — Identifikátory odvodené z `app.yml`:** `BASE_BUNDLE_IDENTIFIER = eu.macet.psst`, rozšírenia
`eu.macet.psst.nse` a `eu.macet.psst.shareextension` (odvodzujú ich `target.yml` súbory upstreamu),
`APP_GROUP_IDENTIFIER = group.eu.macet.psst`, keychain group `$(DEVELOPMENT_TEAM).eu.macet.psst`,
`APP_DISPLAY_NAME = PRODUCTION_APP_NAME = psst`. Identifikátory úloh na pozadí (BGTaskScheduler) sú
premenované na `eu.macet.psst.background.*` v `Info.plist` aj `AppSettings` (musia sa zhodovať).

**I6 — V repe nie je žiadny `DEVELOPMENT_TEAM`** (upstream mal tím Elementu `7J4U792NQT`). Simulátorový build
beží bez podpisu (`CODE_SIGNING_ALLOWED=NO`), release workflow dosadí `DEVELOPMENT_TEAM=$APPLE_TEAM_ID`.

**I7 — Odstránená migrácia z Element Classic.** Kľúče `classicApp*` v Info.plist, app group `group.im.vector`
a keychain group `im.vector.app.keychain.shared` by znemožnili provisioning pod iným tímom a psst nemá
„starú" aplikáciu. `ClassicAppManager` sa bez kľúčov sám vypne (vracia `nil`).

**I8 — Ikona:** upstream používa Icon Composer balík `AppIcon.icon`; nahradený klasickým
`Assets.xcassets/AppIcon.appiconset` s jediným 1024×1024 RGB obrázkom (bez alfa) z
`assets/generated/ios/AppIcon.appiconset/icon-1024.png` (layout „Single Size", Xcode menšie veľkosti
vygeneruje sám). Pôvodný Contents.json z generátora miešal legacy `iphone`/`ipad` záznamy s veľkosťami 38/64/68,
ktoré existujú iba v single-size layoute — riziko chyby `actool`, ktorú lokálne nevieme overiť.

**I9 — Akcentová farba #38BDF8** v `colors/accent-color` (globálny tint, všetky režimy) a zároveň v Compound
tokenoch `iconAccentPrimary`, `iconAccentTertiary`, `textActionAccent`, `bgAccentRest`, `borderAccentPrimary`
(SwiftUI aj UIKit) cez `DefaultCompoundHook` — to je upstreamom určený bod pre vlastné farby. Dôsledok: na svetlom
pozadí má #38BDF8 nižší kontrast než zelená Elementu (akceptované kvôli značke).

**I10 — Úvodná obrazovka:** logo `app-logo` (PDF Elementu) nahradené `psst-logo.svg` (110 pt); nadpis
„Be in your element" nahradený názvom aplikácie a slogan s „fastest Element ever" odstránený. Spúšťací
gradient (`launch-background`) ostal — je neutrálny, bez loga.

## Homeserver

**I11 — Uzamknutie na chat.macet.eu (ako Android):** `accountProviders = [.managed(serverName: "chat.macet.eu",
baseURL: "https://chat.macet.eu")]`, `allowOtherAccountProviders = false`. Upstream z toho sám odvodí:
tlačidlo „Sign in to chat.macet.eu" priamo na úvodnej obrazovke (žiadny výber servera, žiadne „Change server"),
skryté „Create account", QR prihlásenie odmietne server mimo zoznamu, provisioning linky na iné servery sú
ignorované. Server name je `chat.macet.eu`, takže SDK robí discovery cez `.well-known` tejto domény.

## Element-hosted endpointy

**I12 — OAuth (MAS) metadáta na doméne macet.eu.** `client_uri = https://macet.eu/psst/ios`,
`logo_uri = https://macet.eu/psst/logo.png`, `tos_uri = https://macet.eu/psst/terms`,
`policy_uri = https://macet.eu/psst/privacy`, redirect `eu.macet.psst:/oauth/callback`. Dôvod: politika MAS
pri dynamickej registrácii vyžaduje logo/tos/policy na rovnakom hoste ako `client_uri` a private-use schému
redirectu = obrátený host `client_uri` (+ prípona) — `eu.macet.psst` vyhovuje pre `macet.eu` a schéma je už
zaregistrovaná v `CFBundleURLSchemes`. Pôvodný redirect `https://element.io/oauth/ios/…` by fungoval len s
Element associated domain. Dôsledok: stránky `/psst/terms`, `/psst/privacy`, `/psst/logo.png` treba na
macet.eu zverejniť (inak MAS zobrazí nefunkčné odkazy). Ak server nepoužíva MAS (len heslo), na nič z toho nezáleží.
Copyright odkaz vedie na LICENSE vo forku.

**I13 — Push gateway `https://chat.macet.eu`** (namiesto Element/matrix.org Sygnalu, ktorý pre `eu.macet.psst`
aj tak nemá APNs kľúč). Vlastný Sygnal je mimo rozsah → **push notifikácie nefungujú**, kým na chat.macet.eu
nebude Sygnal s APNs kľúčom (`.p8`) pre bundle `eu.macet.psst` a app ID `eu.macet.psst.ios.prod`
(`.ios.dev` pre Debug). Registrácia pushera na homeserveri prebehne, doručenie zlyhá na strane servera.

**I14 — Analytika a crash reporting vypnuté natvrdo:** `Secrets.swift` má všetky hodnoty `nil`;
`AppSettings.analyticsConfiguration = nil` (PostHog sa nespustí, súhlas sa nikdy nepýta),
`bugReportSentryURL`/`bugReportSentryRustURL = nil`, rageshake `.disabled` (tlačidlo „Report a problem" sa
neukáže), `analyticsTermsURL = nil`, Element Call nedostane PostHog/Sentry konfiguráciu Elementu.
Swift balíky PostHog a Sentry ostali nalinkované: odstránenie by zasiahlo ~11 upstream súborov a komplikovalo
merge, pričom bez DSN/kľúča sa SDK vôbec neinicializujú (žiadna sieťová komunikácia).

**I15 — Mapy vypnuté.** MapTiler kľúč Elementu nepoužívame (`apiKey: nil`) → zdieľanie polohy je vypnuté a
prijaté polohy sa v timeline zobrazia ako rozmazaný placeholder. Zapnutie = vlastný MapTiler kľúč v
`bundledMapTilerConfiguration` (alebo vlastný tile server s rovnakým API).

**I16 — Associated domains:** `applinks:app.macet.eu` namiesto element.io/matrix.to; `webcredentials:*.element.io`
odstránené. Universal linky začnú fungovať až keď `https://app.macet.eu/.well-known/apple-app-site-association`
bude obsahovať `<TEAM_ID>.eu.macet.psst`. `elementWebHosts` a `accountProvisioningHost` = `app.macet.eu`.
`matrix:` URL schéma ostáva.

**I17 — Odkazy na nápovedu (element.io/help#…) ponechané.** Sú to len informačné stránky otvárané používateľom
(šifrovanie, záloha, overenie zariadenia), nie endpointy; obsah platí aj pre psst.

**I18 — Element Call:** používa sa web app zabalený v balíku `EmbeddedElementCall` 0.28.2 (`elementCallBaseURL =
EmbeddedElementCall.appURL`, lokálny súbor v app bundli) — nikdy `call.element.io`. LiveKit focus (MatrixRTC
transport) sa berie z `.well-known` homeservera chat.macet.eu (`org.matrix.msc4143.rtc_foci`). Natívny
`ElementCall` stack ostáva vypnutý (upstream default).

## Licencia

**I19 — AGPL:** hlavičky a `LICENSE`/`LICENSE-COMMERCIAL` nezmenené. V Nastavenia → About (Legal information)
pribudla sekcia „Source code (AGPL-3.0)" s odkazom na https://github.com/georgonr/psst-ios a pätičkou o pôvode
(AGPL-3.0 §13). Text je zatiaľ len anglicky (nie je v Localazy).

## Podpísaný build

**I20 — `ios-release.yml` s manuálnym podpisom.** Profily sa načítajú z ZIPu v sekrete, z každého sa zistí bundle
id a meno; per-target `PROVISIONING_PROFILE_SPECIFIER` sa vloží do XcodeGen specu cez dodatočný include
(`psst-signing.yml`), globálne sa nastaví `CODE_SIGN_STYLE=Manual`, `CODE_SIGN_IDENTITY="Apple Distribution"`,
`DEVELOPMENT_TEAM`. `aps-environment` sa pre App Store prepne na `production`. Entitlement
`com.apple.developer.usernotifications.filtering` (NSE) Apple udeľuje len na žiadosť — ak ho NSE profil nemá,
workflow ho z NSE odstráni (s warningom). Upload do TestFlight cez `xcrun altool` s App Store Connect API kľúčom.

## Blokátor

**I21 — Push workflowov do GitHubu zlyhal na chýbajúcom scope `workflow`.** Token `gh` (`georgonr`) má scope
`repo, gist, read:org`; GitHub odmieta push súborov v `.github/workflows/` („refusing to allow an OAuth App to
create or update workflow … without `workflow` scope"). To isté postihlo aj Android/server workflowy. Commity
sú pripravené lokálne v `~/Desktop/psst` (vetva `main`, ahead of origin). Neinteraktívne sa scope pridať nedá
(vyžaduje prihlásenie v prehliadači) → CI build/simulátor zatiaľ **nebežal**. Riešenie pre používateľa:
`gh auth refresh -h github.com -s workflow`, potom `git push` a `gh workflow run ios.yml`.
