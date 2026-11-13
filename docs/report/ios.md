# PSST iOS — report (2026-11-13)

## Stav

| položka | stav |
|---|---|
| Fork `georgonr/psst-ios`, vetva `psst` | pushnutá, HEAD `4066e4b27c3ad47cba52c8ced2e2374423681d50` (base `release/26.11.0`) |
| `forks/ios` v hlavnom repe | plytký klon vetvy `psst` (nie je v indexe; submodul zaregistruje orchestrátor) |
| `.github/workflows/ios.yml`, `ios-release.yml` | napísané, `actionlint` + YAML parse OK, commitnuté lokálne v `~/Desktop/psst` |
| Push workflowov do `georgonr/psst` | **zablokovaný** — gh token nemá scope `workflow` (pozri I21) |
| CI build + spustenie v simulátore | **nespustené** (bez pushnutého workflowu nie je čo spustiť), run URL zatiaľ neexistuje |
| Screenshoty v `dist/ios/` | zatiaľ nie sú |

## Commity vo forku (`git log release/26.11.0..psst`)

1. **Rebrand** — `app.yml`: bundle id `eu.macet.psst` (+ `.nse`, `.shareextension`), app group
   `group.eu.macet.psst`, keychain group `$(DEVELOPMENT_TEAM).eu.macet.psst`, názov `psst`, bez team ID;
   odstránená Element Classic migrácia; associated domains `applinks:app.macet.eu`; BG task ID
   `eu.macet.psst.background.*`; ikona (AppIcon.appiconset namiesto AppIcon.icon); akcent #38BDF8
   (asset catalog + Compound tokeny cez `DefaultCompoundHook`); logo na úvodnej obrazovke = psst logo.
2. **Uzamknutie servera + endpointy** — `accountProviders = [chat.macet.eu]`, `allowOtherAccountProviders = false`;
   OAuth `client_uri`/logo/terms/privacy na `macet.eu`, redirect `eu.macet.psst:/oauth/callback`;
   push gateway `https://chat.macet.eu`; `elementWebHosts`/provisioning host `app.macet.eu`;
   About → „Source code (AGPL-3.0)" → https://github.com/georgonr/psst-ios; nadpis úvodnej obrazovky = „psst".
3. **Bez analytiky** — `Secrets.swift` všetko `nil`; PostHog, Sentry (app + Rust), rageshake a analytics terms
   vypnuté natvrdo v `AppSettings`; Element Call bez PostHog/Sentry; MapTiler bez kľúča (mapy vypnuté).
4. Regenerovaný `ElementX.xcodeproj`, `Info.plist`, entitlements (xcodegen 2.46.0).
5. Odstránené zbytočné swiftlint komentáre.
6. Ikona: iba single-size 1024×1024 (bez legacy veľkostí).

Všetky zmeny sú označené `PSST:` (`git grep -n PSST`). LICENSE a AGPL hlavičky sú nedotknuté.

## Workflowy v hlavnom repe

- `ios.yml` (workflow_dispatch + push do main na relevantných cestách) — `macos-26`, Xcode 27, checkout
  `georgonr/psst-ios@psst` (bez LFS/submodulov), `brew install xcodegen`, lint shimy, `xcodegen`, SPM cache,
  `xcodebuild build` pre `generic/platform=iOS Simulator` s `CODE_SIGNING_ALLOWED=NO`, kontrola
  `CFBundleIdentifier == eu.macet.psst`, `CFBundleDisplayName == psst`, app group a ID rozšírení, boot
  iPhone Pro simulátora s najnovším iOS, `simctl install/launch`, 30 s čakanie, screenshoty (svetlý, tmavý,
  domovská obrazovka), kontrola procesu (`launchctl list` + `ps -p <pid>`), log aplikácie.
  Artefakty: **`ios-screenshots`**, **`psst-ios-simulator-app`** (`psst-ios-simulator.app.zip`), **`ios-build-log`**.
- `ios-release.yml` (workflow_dispatch) — kontrola sekretov hneď na začiatku, archive + export IPA,
  voliteľne TestFlight. Artefakt **`psst-ios-ipa`**. Úspešne spustiť sa nedá bez Apple účtu (zámerne nespúšťané).

## Výsledky testov v simulátore

Zatiaľ žiadne — CI beh sa nedal spustiť (blokátor nižšie). Lokálne bolo overené len: `xcodegen` vygeneruje
projekt bez chýb a s očakávanými identifikátormi, názvy Compound tokenov existujú v compound-design-tokens 11.3.1,
workflowy prešli `actionlint`. Swift zmeny sú malé a v štýle okolitého kódu, ale **kompilácia nebola overená**.

## Čo musí urobiť používateľ

1. Pridať scope `workflow` a pushnúť (týka sa aj Android/server workflowov):
   ```sh
   gh auth refresh -h github.com -s workflow
   cd ~/Desktop/psst && git pull --rebase --autostash && git push
   gh workflow run ios.yml -R georgonr/psst
   gh run watch -R georgonr/psst $(gh run list -R georgonr/psst -w ios.yml -L1 --json databaseId -q '.[0].databaseId')
   gh run download -R georgonr/psst <run-id> -n ios-screenshots -D dist/ios/
   ```
   Ak by build zlyhal, chyby sú v kroku „Build for iOS Simulator" (vypísané `error:` riadky) a v artefakte `ios-build-log`.
2. Pre podpísaný build nastaviť sekrety: `IOS_DIST_CERT_P12_BASE64`, `IOS_DIST_CERT_PASSWORD`,
   `IOS_PROVISIONING_PROFILES_BASE64`, `APPLE_TEAM_ID`; pre TestFlight navyše `APP_STORE_CONNECT_API_KEY_ID`,
   `APP_STORE_CONNECT_ISSUER_ID`, `APP_STORE_CONNECT_API_KEY_BASE64` (postup v docs/build/ios.md).

## Otvorené problémy

- **CI zatiaľ nebežalo** (scope `workflow`). Neoverené: kompilácia s Xcode 27, `actool` s novou ikonou/SVG logom,
  spustenie a vzhľad v simulátore (nesigned build — keychain group bez team ID).
- **Apple Developer účet** (99 USD/rok) — potrebný pre App ID, profily, certifikát, TestFlight/App Store.
- **Provisioning profily** pre 3 App ID; entitlement NSE filtering treba od Apple vyžiadať (inak ho release
  workflow odstráni).
- **APNs push**: bez vlastného Sygnalu na chat.macet.eu s APNs `.p8` kľúčom pre `eu.macet.psst` notifikácie
  nechodia (app ID pushera `eu.macet.psst.ios.prod` / `.ios.dev`).
- **macet.eu** musí hostovať `/psst/terms`, `/psst/privacy`, `/psst/logo.png` (OAuth/MAS metadáta) a
  `app.macet.eu/.well-known/apple-app-site-association` pre universal linky.
- **Mapy/zdieľanie polohy** vypnuté (chýba vlastný MapTiler kľúč).
- PostHog/Sentry knižnice sú stále nalinkované (neaktívne) — úplné odstránenie je možné neskôr.
- Unit testy upstreamu nie sú upravené na psst nastavenia (nespúšťajú sa).
- Texty „psst"/„Source code" sú len anglicky; ostatné preklady Elementu sa môžu na pár miestach odvolávať na „Element".
