# PSST Android — build

## Zdroj

- Fork: `https://github.com/georgonr/psst-android`, vetva `psst` (základ: tag `v26.11.0` z element-x-android).
- Lokálny klon (shallow): `forks/android` (submodul doplní koordinátor).

```sh
git clone --depth 1 --branch psst https://github.com/georgonr/psst-android forks/android
```

## Verzie nástrojov (z `v26.11.0`)

| Nástroj | Verzia | Zdroj |
|---|---|---|
| JDK | 21 (Temurin) | `plugins/src/main/kotlin/Versions.kt` (`JAVA_VERSION = 21`), upstream `setup-build` action |
| Gradle | 9.8.2 | `gradle/wrapper/gradle-wrapper.properties` |
| Android Gradle Plugin | 9.3.2 | `gradle/libs.versions.toml` (`android_gradle_plugin`) |
| Kotlin | 2.4.21 | `gradle/libs.versions.toml` |
| compileSdk / targetSdk | 37 / 37 | `Versions.kt` |
| minSdk | 24 | `Versions.kt` (`MIN_SDK_FOSS`) |
| Build-tools | 37.0.0 | `Versions.kt` (`BUILD_TOOLS_VERSION`); lokálne podpisovanie tiež 37.0.0 |
| NDK | nepinovaný (natívny kód je predkompilovaný v matrix-rust-sdk AAR; AGP použije NDK z runnera len na strip) | — |
| Element Call (embedded) | 0.28.2 | `libs.versions.toml` |

## Build (CI)

Workflow: `ci/workflows/android.yml` (hlavné repo). Kvôli chýbajúcemu `workflow` scope tokenu nie je v
`.github/workflows/`. Aktivácia (jednorazovo, používateľ):

```sh
gh auth refresh -h github.com -s workflow      # interaktívne v prehliadači
mkdir -p .github/workflows && git mv ci/workflows/android.yml .github/workflows/android.yml
git commit -m "Enable Android CI" && git push
gh workflow run android.yml -R georgonr/psst            # voliteľne -f fork_ref=<sha>
gh run watch -R georgonr/psst
```

Joby:

1. `apk` — checkout `georgonr/psst-android@psst`, JDK 21, `./gradlew :app:assembleFdroidRelease`
   → artefakt `psst-android-apks-unsigned`
   (`app-fdroid-{arm64-v8a,armeabi-v7a,x86_64}-release-unsigned.apk` + `output-metadata.json`).
2. `aab` — `./gradlew :app:bundleFdroidRelease` (samostatný job, lebo AGP vypína ABI splity, keď sa v tom istom
   behu volá `bundle*`) → artefakt `psst-android-aab-unsigned` (`app-fdroid-release.aab`).
3. `emulator` — stiahne x86_64 APK, podpíše ho jednorazovým kľúčom (vygenerovaným v jobe, zahodeným),
   spustí `reactivecircus/android-emulator-runner` (API 34, google_apis, x86_64, KVM) a
   `scripts/android/emulator-test.sh` → artefakt `psst-android-emulator-results` (PNG screenshoty, XML UI dumpy,
   `result.txt`, `logcat.txt`). Job zlyhá pri porušení zámku servera alebo zlom názve.

Gradle parametre ako upstream: `GRADLE_OPTS=-Xmx8g …`, `--no-daemon --no-configuration-cache`.

Lokálny ekvivalent (len na stroji s Android SDK, nie na tomto Macu):

```sh
cd forks/android
./gradlew :app:assembleFdroidRelease --no-daemon
./gradlew :app:bundleFdroidRelease --no-daemon
```

## Podpisovanie (lokálne, release kľúč nikdy neopustí stroj)

Kľúč (vytvorený raz):

```sh
umask 077; mkdir -p ~/psst-keys; chmod 700 ~/psst-keys
export PSST_KS_PASS="$(openssl rand -base64 36 | tr -d '/+=\n' | cut -c1-40)"
/usr/local/opt/openjdk@17/bin/keytool -genkeypair -keystore ~/psst-keys/psst-release.jks -storetype PKCS12 \
  -storepass:env PSST_KS_PASS -keypass:env PSST_KS_PASS -alias psst -keyalg RSA -keysize 4096 \
  -validity 10000 -dname "CN=psst, O=psst.pro"   # nový kľúč; vydaný psst má O = pôvodná doména (D85)
# heslá -> ~/psst-keys/keystore.properties (storeFile, storePassword, keyAlias, keyPassword), chmod 600
```

PKCS12 má rovnaké heslo pre store aj kľúč. **Záloha:** `~/psst-keys` treba zálohovať offline (napr. šifrovaný
USB disk); strata kľúča = nemožnosť aktualizovať aplikáciu u existujúcich inštalácií (mimo Play App Signing).

Podpísanie artefaktov z CI:

```sh
df -h ~                                                    # skript vyžaduje >1 GB voľného miesta
scripts/android/sign-release.sh --run <run-id>             # stiahne psst-android-{apks,aab}-unsigned cez gh
# alebo
gh run download <run-id> -R georgonr/psst -n psst-android-apks-unsigned -D /tmp/psst-unsigned
gh run download <run-id> -R georgonr/psst -n psst-android-aab-unsigned  -D /tmp/psst-unsigned
scripts/android/sign-release.sh /tmp/psst-unsigned         # výstup: dist/android/ (gitignored)
```

Skript:
- pri prvom spustení stiahne `build-tools_r37_macosx.zip` (~80 MB, SHA-1 `eb080751b2b2028eb3604f571027d6f7b3c46321`)
  do `~/.psst-tools/build-tools-37.0.0` (mimo repa a mimo iCloud Desktopu),
- APK: `zipalign -P 16 -f 4` (16 KB page alignment natívnych knižníc) → `apksigner sign` (v1/v2/v3 podľa minSdk)
  → `apksigner verify --print-certs -v`, kontrola SHA-256 certifikátu,
- AAB: `jarsigner -sigalg SHA256withRSA -digestalg SHA-256` → `jarsigner -verify` + `keytool -printcert -jarfile`,
- heslá číta z `keystore.properties` do env premenných (`--ks-pass env:…`, `-storepass:env …`), nikdy ich nevypíše,
- zapíše `dist/android/SHA256SUMS`.

Výstupy: `dist/android/psst-<verzia>-<abi>.apk`, `dist/android/psst-fdroid.aab`.

Overenie ručne:

```sh
~/.psst-tools/build-tools-37.0.0/apksigner verify --print-certs dist/android/psst-26.11.0-arm64-v8a.apk
keytool -printcert -jarfile dist/android/psst-fdroid.aab
```

Očakávaný certifikát: `CN=psst` (O = pôvodná doména; certifikát sa nemení, D85), SHA-256
`3A:64:28:CF:51:EE:8F:5E:10:E8:4F:AC:5C:A8:A6:B3:C3:B8:C3:4D:26:74:DB:0F:22:24:D1:D0:09:7D:38:99`.

## Aktualizácia na nový upstream

```sh
cd forks/android
git fetch --depth 50 https://github.com/element-hq/element-x-android tag vX.Y.Z
git checkout psst && git merge vX.Y.Z      # konflikty hľadať podľa komentárov "PSST:"
git push origin psst
```
