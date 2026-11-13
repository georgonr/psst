# PSST Android — rozhodnutia

Fork: [georgonr/psst-android](https://github.com/georgonr/psst-android), vetva `psst` nad tagom `v26.11.0`
(element-x-android). Všetky zmeny v kóde sú označené komentárom `// PSST:` (v XML `<!-- PSST: -->`).

**A1 — Identita aplikácie: `eu.macet.psst`, názov „psst“.**
Nastavené v `plugins/src/main/kotlin/config/BuildTimeConfig.kt` (to je upstreamový mechanizmus pre
white-label buildy). `namespace` (Kotlin balíky `io.element.android.*`) sa nemení — zmena by znamenala tisíce
riadkov diffu a ťažké zlučovanie z upstreamu; používateľ ani systém ho nevidia. `ApplicationConfig`
(`PRODUCTION_APPLICATION_NAME`, `DESKTOP_APPLICATION_NAME`) = „psst“, takže texty typu „Welcome to …“ hovoria o psst.

**A2 — Zámok homeservera cez `EnterpriseService`, nie cez úpravy obrazoviek.**
`features/enterprise/impl-foss/.../DefaultEnterpriseService.kt`: `accountProviderAllowList() = [chat.macet.eu]`,
`canConnectToAnyAccountProvider() = false`, `isAllowedToConnectToAccountProvider()` povolí len zhodu s týmto
zoznamom. Upstream už presne tieto hodnoty používa pre Element Pro / MDM: onboarding potom ukáže len tlačidlo
„Sign in to chat.macet.eu“ (+ QR prihlásenie), nikdy „Sign in manually“ / „Change account provider“ / textové pole
servera, a predvolený poskytovateľ je `chat.macet.eu` (nie matrix.org ani história). Všetky ďalšie vstupy (QR kód,
login odkazy, zmena servera) prechádzajú cez `AccountProviderAccessControl`, ktorý iný server odmietne.
Prečo nie mazanie obrazoviek: minimálny diff = jednoduché zlučovanie nových verzií upstreamu.
Doména je v `BuildTimeConfig.PSST_HOMESERVER` a do kódu sa dostane cez `BuildConfig`.

**A3 — Dodatočné spevnenie zámku.**
(a) Import relácie z Element Classic (`ClassicFlowNodeHelper`) sa ponúkne len pre používateľa z povoleného servera
(upstream tu kontrolu nemal). (b) `DefaultLoginIntentResolver` ignoruje `mobile.element.io` login odkazy
(parameter `account_provider`). (c) Kontrola „Element Pro enforced“ (sťahovala `/.well-known/element/element.json`)
je vypnutá — psst sa pripája len na vlastný server.

**A4 — Flavour `fdroid`.**
`gplay` pridáva Firebase Cloud Messaging (Elementov Firebase projekt `vector-alpha` + Sygnal na matrix.org)
a Google Play Services location backend; `fdroid` nemá žiadnu závislosť na Google ani Element službách.
`fdroid` je nastavený ako `isDefault`. Navyše je GMS location odstránený aj z `gplay`, takže oba flavoury majú
rovnaké závislosti (keby sa niekedy použil upstreamový `release.yml`, ktorý balí AAB z `gplay`).
AAB pre Google Play sa robí z `fdroid` flavouru — Play nevyžaduje GMS.

**A5 — Push: len UnifiedPush, gateway `https://matrix.gateway.unifiedpush.org/_matrix/push/v1/notify`.**
`PUSH_CONFIG_INCLUDE_FIREBASE = false`. FCM by fungoval len s vlastným Firebase projektom a vlastným Sygnalom
(google-services.json pre `eu.macet.psst` + Sygnal s FCM kľúčom) — self-hosted Sygnal je mimo rozsahu.
UnifiedPush gateway je prevádzkovaný projektom UnifiedPush (nie Element); distribútor (napr. ntfy) zvyčajne
ponúka vlastný gateway, ktorý má prednosť. Pusher app ID: `eu.macet.psst`.
**Dôsledok:** bez nainštalovaného UnifiedPush distribútora (ntfy, NextPush, …) nechodia push notifikácie, keď je
aplikácia na pozadí; aplikácia to hlási v „Troubleshoot notifications“. Synapse musí povoliť pushery na tento
gateway (predvolene áno).

**A6 — Bez analytiky a crash reportingu.** `ModulesConfig.analyticsConfig = Disabled` → modul
`services/analytics/noop`; PostHog ani Sentry sa do APK nedostanú. Embedded Element Call má Sentry/PostHog/rageshake
konfiguráciu natvrdo prázdnu (predtým z env premenných CI).

**A7 — Bug report (rageshake) vypnutý.** `BUG_REPORT_URL` prázdne + `bugReportUrlFlow = Disabled`; nič sa
neposiela na `rageshakes.element.io`. Vlastný rageshake server je mimo rozsahu.

**A8 — Odkazy a URL.** Žiadny fallback na `element.io` (cookie policy, copyright, AUP, privacy, OAuth client URI).
OAuth metadáta: `client_uri = https://app.macet.eu`, redirect schéma `eu.macet.app` (MAS vyžaduje reverzný
(sub)doménový zápis hostu `client_uri`; `eu.macet.psst` by zodpovedalo `psst.macet.eu`, ktorá neexistuje).
Copyright → LICENSE vo forku, AUP/privacy → `https://app.macet.eu/terms.html`, `/privacy.html` (stránky musí
dodať web/server). Odkazy „Learn more“ (`element.io/help#…`) ostali — sú to len verejné návody otvárané
v prehliadači, nie konfigurácia ani služba.

**A9 — App links.** Intent-filtre pre `app.element.io`, `develop.element.io`, `staging.element.io`
a `mobile.element.io` odstránené; pridaný `https://app.macet.eu` (permalinky psst webu `/#/room/...`).
Overenie (`autoVerify`) vyžaduje na serveri `https://app.macet.eu/.well-known/assetlinks.json` s package
`eu.macet.psst` a SHA-256 certifikátu (viď report). Schémy `matrix:` a `element://` (z matrix.to) ostali.

**A10 — Hovory.** Ponechaný embedded Element Call (balík `element-call-embedded`, načítaný z
`appassets.androidplatform.net`, nie z `call.element.io`). LiveKit focus sa berie z `rtc_foci` v
`/.well-known/matrix/client` homeservera (`call.macet.eu`). Žiadna zmena kódu nebola potrebná; analytika EC vypnutá (A6).

**A11 — Branding.** Ikony z `scripts/make-icons.sh` (hlavné repo): adaptívna ikona (pozadie `#0F172A`, popredie,
monochromatická vrstva), legacy PNG mipmapy, notifikačná ikona (`libraries/designsystem/.../ic_notification.xml`),
Play Store ikona. Onboarding zobrazuje psst logo (`app/src/main/res/drawable/onboarding_logo.xml`, upstreamový
mechanizmus `OnBoardingLogoResIdProvider`) namiesto loga Element a textu „Be in your element“.
Akcentová farba `#38BDF8` cez `EnterpriseService.semanticColorsFlow` (`PsstColors.kt`): v tmavej téme priamo
`#38BDF8`; vo svetlej téme by `#38BDF8` na bielej mala kontrast ~2,1:1, preto text/ikony používajú tmavšie odtiene
toho istého odtieňa (sky-600/700). Farba notifikácií `#38BDF8`.

**A12 — About.** V obrazovke „About“ pribudla položka „Source code (AGPL-3.0)“ →
`https://github.com/georgonr/psst-android` (AGPL §13). Licenčné hlavičky a `LICENSE` nezmenené; nové súbory majú
AGPL-3.0-only hlavičku.

**A13 — Podpisovanie: release kľúč nikdy neopustí stroj.** `release` build type má `signingConfig = null`
(upstream podpisoval release debug kľúčom). CI vyrába nepodpísané APK (split per ABI) a AAB; podpisuje sa lokálne
`scripts/android/sign-release.sh` (zipalign + apksigner pre APK, jarsigner pre AAB) kľúčom z `~/psst-keys`
(RSA 4096, 10000 dní, alias `psst`). `.gitignore` forku pokrýva `*.jks`, `*.keystore`, `keystore.properties`.
Emulátorový test podpisuje x86_64 APK jednorazovým kľúčom vygenerovaným v jobe.

**A14 — ABI.** `arm64-v8a`, `armeabi-v7a` (telefóny) a `x86_64` (emulátor, Chromebooky); 32-bit `x86` a universal
APK vypustené (menej artefaktov, x86 zariadenia prakticky neexistujú).

**A15 — Firebase App Distribution plugin odstránený** z `app/build.gradle.kts` aj z classpath `plugins/`.

**A16 — CI v hlavnom repe, workflow v `ci/workflows/android.yml`.** Token `gh` nemá scope `workflow`, preto
GitHub odmieta push súborov v `.github/workflows/`; workflow je uložený mimo a aktivuje sa po
`gh auth refresh -s workflow` (viď `docs/build/android.md`). Fork má GitHub Actions pre workflowy zakázané
(štandard pre forky), preto sa upstreamové workflowy nepoužívajú. Maestro testy vo forku (`.maestro/`) boli
nahradené psst smoke testom (rovnaké kontroly ako emulátorový test) — upstreamové testy vyžadovali účet na matrix.org.

**A17 — Emulátorový test** (`scripts/android/emulator-test.sh` + `check_ui.py`): API 34 `google_apis` x86_64,
inštalácia release APK, kontrola `application-label:'psst'`, onboarding musí ukázať „Sign in to chat.macet.eu“ a
v žiadnom UI dumpe (onboarding, po kliknutí na sign-in, QR obrazovka, po injektovanom `mobile.element.io` odkaze)
sa nesmie objaviť „Sign in manually“, „Change account provider“, „Other“, „Create account“, `matrix.org`,
`element.io` ani editovateľné pole so serverom. Overuje aj, že element.io odkazy sa už neotvárajú v psst.
