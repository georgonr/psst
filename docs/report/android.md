# PSST Android — report

Stav k 2026-11-13.

## Fork

- Repo: https://github.com/georgonr/psst-android, vetva `psst`, HEAD
  `c26b2d9120be2616d951a128433abab1f9e39b09` (základ `v26.11.0`).
- Commity (všetky zmeny označené `PSST:`):
  1. `4a8b2682` build konfigurácia: `eu.macet.psst`, „psst“, bez analytiky (noop), bez Firebase push a
     Firebase App Distribution, žiadne fallbacky na element.io, nepodpísaný release, ABI splity arm64-v8a /
     armeabi-v7a / x86_64, `fdroid` default flavour, `.gitignore` pre keystory.
  2. `8422be43` zámok na `chat.psst.pro` (`DefaultEnterpriseService`: allow list = [chat.psst.pro],
     `canConnectToAnyAccountProvider = false`), ignorované `mobile.element.io` login odkazy, Element Classic import len
     z povoleného servera, vypnutá Element Pro kontrola a rageshake, akcent `#38BDF8` (`PsstColors`).
  3. `f4b79689` branding: launcher (adaptívna + monochrome), legacy mipmapy, notifikačná ikona, Play Store ikona,
     psst logo na onboardingu, názvy aplikácie, farba notifikácií.
  4. `10581852` app links: element.io hosty nahradené `app.psst.pro`.
  5. `4f4ceecb` About → „Source code (AGPL-3.0)“ → https://github.com/georgonr/psst-android.
  6. `b5196242` GMS location backend odstránený aj z `gplay`.
  7. `f21ab543` Maestro smoke test (`.maestro/psst/`) namiesto upstreamových testov.
  8. `c26b2d91` drobnosti (KDoc, nepreložiteľný string).

Rozhodnutia: `docs/decisions/android.md`. Build: `docs/build/android.md`.

## Hlavné repo

- `ci/workflows/android.yml` — build (APK + AAB) + emulátorový test (presunie sa do `.github/workflows/` po získaní scope).
- `scripts/android/emulator-test.sh`, `scripts/android/check_ui.py` — emulátorový test.
- `scripts/android/sign-release.sh` — lokálne podpisovanie.

## CI — **pending: requires workflow scope**

GitHub odmieta push `.github/workflows/*` (token `georgonr` má len `repo, gist, read:org`; treba
`gh auth refresh -s workflow`, interaktívne). Fork má Actions pre zdedené workflowy zakázané (forky to vyžadujú
potvrdiť v UI), takže ani upstreamové `release.yml`/`maestro-local.yml` sa nedajú spustiť.
Preto:

| Položka | Stav |
|---|---|
| Build unsigned APK (per ABI) | **pending: requires workflow scope** |
| Build unsigned AAB | **pending: requires workflow scope** |
| Emulátorový test (inštalácia, názov psst, zámok servera, screenshoty) | **pending: requires workflow scope** |
| Run URL | žiadny (nebol spustený) |
| Podpísané artefakty v `dist/android/` | **pending** (čaká na CI artefakty) |

Kód nebol skompilovaný (lokálne nie je Android SDK ani miesto na Gradle cache — viď DECISIONS D1). Zmeny boli
staticky skontrolované proti zdrojom v26.11.0 (signatúry `buildConfigFieldStr`, `AccountProvider.matches`,
`UserId.domainName`, `SemanticColors.copy`, R/BuildConfig namespace, Metro DI konštruktor + unit test
`ClassicFlowNodeHelperTest` upravený). Prvý CI beh treba sledovať: `gh run watch`, pri chybe
`gh run view --log-failed`.

Statická validácia: YAML workflowu a Maestro flowov sa parsuje (Ruby `YAML.load_stream`), `bash -n` na skriptoch,
`check_ui.py` otestovaný na vzorových dumpoch (povolený onboarding → OK; „Change account provider“ + editovateľné
`matrix.org` → 4 porušenia, exit 1).

## Podpisovanie — overené lokálne

- Keystore: `~/psst-keys/psst-release.jks` (PKCS12, RSA 4096, platnosť 10000 dní do 2054-03-31, alias `psst`,
  `CN=psst` (O = pôvodná doména; certifikát sa nemení, D85)), heslá v `~/psst-keys/keystore.properties` (chmod 600, adresár 700). Nič z toho nie je
  v gite ani na GitHube.
- **Certifikát SHA-256:**
  `3A:64:28:CF:51:EE:8F:5E:10:E8:4F:AC:5C:A8:A6:B3:C3:B8:C3:4D:26:74:DB:0F:22:24:D1:D0:09:7D:38:99`
  (`3a6428cf51ee8f5e10e84fac5ca8a6b3c3b8c34d2674db0f2224d1d0097d3899`)
- Build-tools 37.0.0 (macOS, universal binárky, x86_64 OK) v `~/.psst-tools/build-tools-37.0.0`.
- `sign-release.sh` overený na minimálnych testovacích artefaktoch (APK vyrobené `aapt2 link`, AAB zip):
  2 APK → `Verified using v1/v2/v3 scheme: true`, certifikát `CN=psst` (O = pôvodná doména; certifikát sa nemení, D85) so správnym SHA-256;
  AAB → jarsigner verified, rovnaký certifikát; `SHA256SUMS` vytvorený. Skutočné psst APK/AAB sa podpíšu po CI.

## Otvorené body

1. **Workflow scope** — bez neho nebeží žiadne CI (build, emulátor, podpísané artefakty).
2. **Google Play upload** vyžaduje Play Console účet používateľa; odporúčané Play App Signing s naším kľúčom ako
   upload key (AAB podpísaný `sign-release.sh`).
3. **assetlinks.json** na `https://app.psst.pro/.well-known/assetlinks.json` (package `eu.macet.psst`, fingerprint
   vyššie), inak sa app.psst.pro odkazy neotvoria automaticky v aplikácii.
4. **Push**: používateľ potrebuje UnifiedPush distribútora (ntfy …); bez neho žiadne notifikácie na pozadí.
5. **Právne stránky** `https://app.psst.pro/terms.html` a `/privacy.html` musí dodať web/server (odkazuje na ne
   About obrazovka a OAuth metadáta). `URL_LOGO` = `https://app.psst.pro/favicon.ico`.
6. **Mapy** (zdieľanie polohy) bez MapTiler kľúča nie sú dostupné.
7. Niektoré preložené texty môžu stále spomínať „Element“ (napr. „Element Call“, „Element Pro“) — emulátorový test
   ich vypíše ako `WARN`, nie ako chybu.
8. Registrácia v aplikácii nie je (upstream ju pri vynútenom serveri skrýva); účty sa zakladajú na serveri / webe.
9. Unit testy forku neboli spúšťané (`LoginIntentResolver` testy pre mobile.element.io budú po zmene padať —
   očakávané).
