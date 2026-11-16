# PSST iOS — build

| čo | verzia |
|---|---|
| Zdroj | `georgonr/psst-ios`, vetva `psst` (base `release/26.11.0` = Element X iOS 26.11.0) |
| Runner | GitHub-hosted `macos-26` (arm64) |
| Xcode | 27.x (najnovší `/Applications/Xcode_27*.app` na image, nie beta; presná verzia je v Step Summary behu) |
| Swift | toolchain z Xcode 27 (`Package.swift` vyžaduje tools-version ≥ 6.2) |
| XcodeGen | aktuálny z Homebrew (lokálne overené 2.46.0) |
| Deployment target | iOS 18.5 |
| Kľúčové balíky | matrix-rust-components-swift 26.11.05, EmbeddedElementCall 0.28.2, compound-design-tokens 11.3.1 |

Lokálny stroj (Intel, Xcode 16.0, ~6 GB voľného miesta) aplikáciu **nezbuildí** — chýba Xcode 27 a miesto pre
SPM závislosti (niekoľko GB). Lokálne sa robí len editácia a `xcodegen`.

## CI — simulátor (`.github/workflows/ios.yml`)

Spúšťa sa ručne alebo pushom do `main` (zmena workflowu, `scripts/ios/**`, `assets/generated/ios/**`, `forks/ios`).

```sh
gh workflow run ios.yml -R georgonr/psst                      # vetva psst, Debug
gh workflow run ios.yml -R georgonr/psst -f ref=psst -f configuration=Release
gh run watch -R georgonr/psst $(gh run list -R georgonr/psst -w ios.yml -L1 --json databaseId -q '.[0].databaseId')
gh run download -R georgonr/psst <run-id> -n ios-screenshots -D dist/ios/
```

Kroky workflowu (rovnaké príkazy sa dajú spustiť na Macu s Xcode 27):

```sh
git clone --depth 1 --branch psst https://github.com/georgonr/psst-ios ios && cd ios   # bez LFS a submodulov
sudo xcode-select -s /Applications/Xcode_27.app
brew install xcodegen
xcodegen                                       # ElementX.xcodeproj z project.yml/app.yml
xcodebuild -resolvePackageDependencies -project ElementX.xcodeproj -scheme ElementX \
  -clonedSourcePackagesDirPath /tmp/spm
xcodebuild build -project ElementX.xcodeproj -scheme ElementX -configuration Debug \
  -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/dd \
  -clonedSourcePackagesDirPath /tmp/spm -skipPackagePluginValidation -skipMacroValidation \
  CODE_SIGNING_ALLOWED=NO COMPILER_INDEX_STORE_ENABLE=NO
APP=/tmp/dd/Build/Products/Debug-iphonesimulator/ElementX.app
/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP/Info.plist"    # eu.macet.psst
/usr/libexec/PlistBuddy -c 'Print :CFBundleDisplayName' "$APP/Info.plist"   # psst
UDID=$(xcrun simctl list devices available | grep -m1 'iPhone .*Pro (' | grep -oE '[0-9A-F-]{36}')
xcrun simctl boot "$UDID" && xcrun simctl bootstatus "$UDID" -b
xcrun simctl install "$UDID" "$APP"
xcrun simctl launch "$UDID" eu.macet.psst
sleep 30 && xcrun simctl io "$UDID" screenshot psst.png
xcrun simctl spawn "$UDID" launchctl list | grep eu.macet.psst              # proces beží
```

SwiftLint/SwiftFormat sa v CI preskakujú (no-op shimy v `PATH`); lokálne pre vývoj upstream odporúča
`swift run tools setup-project` (git hooky, brew nástroje, xcodegen).

Artefakty: `ios-screenshots` (PNG: svetlý/tmavý režim úvodnej obrazovky, domovská obrazovka s ikonou, výpis procesu,
log aplikácie), `psst-ios-simulator-app` (`psst-ios-simulator.app.zip`, inštalovateľné do simulátora cez
`xcrun simctl install`), `ios-build-log` (`build.log.gz`).

## CI — podpísaný build (`.github/workflows/ios-release.yml`)

Iba `workflow_dispatch`. Najprv nastaviť sekrety v `georgonr/psst` → Settings → Secrets and variables → Actions:

| secret | obsah |
|---|---|
| `IOS_DIST_CERT_P12_BASE64` | `base64 -i dist.p12` — certifikát **Apple Distribution** + privátny kľúč |
| `IOS_DIST_CERT_PASSWORD` | heslo k .p12 |
| `IOS_PROVISIONING_PROFILES_BASE64` | `zip profiles.zip *.mobileprovision && base64 -i profiles.zip` — App Store profily pre `eu.macet.psst`, `eu.macet.psst.nse`, `eu.macet.psst.shareextension` |
| `APPLE_TEAM_ID` | 10-znakové Team ID |
| `APP_STORE_CONNECT_API_KEY_ID` | (len pre TestFlight) Key ID |
| `APP_STORE_CONNECT_ISSUER_ID` | (len pre TestFlight) Issuer ID |
| `APP_STORE_CONNECT_API_KEY_BASE64` | (len pre TestFlight) `base64 -i AuthKey_XXXX.p8` |

```sh
gh secret set IOS_DIST_CERT_P12_BASE64 -R georgonr/psst < <(base64 -i dist.p12)
gh secret set IOS_DIST_CERT_PASSWORD -R georgonr/psst
gh secret set IOS_PROVISIONING_PROFILES_BASE64 -R georgonr/psst < <(base64 -i profiles.zip)
gh secret set APPLE_TEAM_ID -R georgonr/psst -b ABCDE12345
gh workflow run ios-release.yml -R georgonr/psst -f ref=psst -f upload_to_testflight=false
```

V Apple Developer portáli treba vopred vytvoriť:
- App ID `eu.macet.psst` s capabilities: App Groups (`group.eu.macet.psst`), Associated Domains,
  Push Notifications, Communication Notifications; App ID `eu.macet.psst.nse` a `eu.macet.psst.shareextension`
  s App Groups (`group.eu.macet.psst`).
- (voliteľne) žiadosť o entitlement *Notification Service Extension Filtering*
  (`com.apple.developer.usernotifications.filtering`) — bez neho ho workflow z NSE vyhodí.
- App Store provisioning profily pre všetky tri App ID, záznam aplikácie v App Store Connect (pre TestFlight).

**Odporúčaná cesta je jeden príkaz `scripts/ios/release-testflight.sh`** (`--check` = len kontrolný zoznam): bundle ID,
capabilities, distribučný certifikát a profily pridá cez API sám, secrets nastaví, spustí tento workflow s uploadom
a build pridá do TestFlightu. Ručne (Account Holder) ostáva len záznam appky — `scripts/ios/README.md`.

Workflow: kontrola sekretov (chýbajúce vypíše ako `::error` a skončí) → dočasný keychain s certifikátom →
inštalácia profilov a mapovanie bundle id → profil → `psst-signing.yml` include do XcodeGen specu,
`aps-environment: production`, build number = `inputs.build_number` alebo `github.run_number` → `xcodegen` →
`xcodebuild archive` (Release, `generic/platform=iOS`) → `xcodebuild -exportArchive` (`app-store-connect`) →
voliteľne `xcrun altool --upload-app` → artefakt `psst-ios-ipa` → zmazanie keychainu a profilov.

## Validácia workflowov

```sh
brew install actionlint
actionlint -shellcheck= .github/workflows/ios.yml .github/workflows/ios-release.yml
ruby -ryaml -e 'YAML.load_file(".github/workflows/ios-release.yml")'
```

## Zlúčenie novej verzie upstreamu

```sh
cd forks/ios
git fetch --unshallow origin      # plytký klon nemá spoločnú históriu s upstreamom
git fetch https://github.com/element-hq/element-x-ios tag release/<nová-verzia>
git merge release/<nová-verzia>          # konflikty hľadať cez: git grep -n PSST
xcodegen && git commit -am "Merge release/<nová-verzia>" && git push origin psst
```
Skontrolovať najmä `app.yml`, `ElementX/SupportingFiles/target.yml`, `AppSettings.swift`, `Secrets.swift`
a či upstream nezmenil požadovanú verziu Xcode (`ci_scripts/ci_common.sh`).
