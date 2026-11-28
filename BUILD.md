# BUILD — príkazy a verzie nástrojov

Podrobné postupy (CI aj lokálne) sú po platformách v `docs/build/`:
[web + desktop](docs/build/web-desktop.md) · [android](docs/build/android.md) · [ios](docs/build/ios.md) ·
[server](docs/build/server.md).

## 0. Predpoklady

```sh
git clone https://github.com/georgonr/psst && cd psst
git submodule update --init --depth 1          # forks/web, forks/android, forks/ios (vetva psst)
gh auth refresh -h github.com -s workflow       # jednorazovo — bez toho GitHub odmietne workflowy
./scripts/enable-ci.sh                          # skopíruje ci/workflows/* → .github/workflows/, pushne, spustí
```

## 1. Ikony

```sh
./scripts/make-icons.sh            # python3 (len stdlib); na macOS iconutil pre .icns → assets/generated/
```

## Verzovanie artefaktov (D54)

- **Číslo buildu** = poradové číslo behu CI workflowu danej platformy (`github.run_number`): Android = `android.yml`,
  web + desktop = `web-desktop.yml` (spoločné číslo), iOS = posledný build v TestFlighte + 1. Každý build má nové
  číslo; lokálne buildy majú `b0` a nepublikujú sa (`publish.py` ich odmietne).
- **Dátum** = dátum buildu v UTC, `RRRRMMDD`.
- **Názvy súborov:** `psst-<platforma>-<RRRRMMDD>-b<číslo>[-<abi>].<prípona>`, napr.
  `psst-android-20261115-b9-arm64.apk`, `psst-android-20261115-b9.aab`, `psst-windows-20261115-b9.msi`,
  `psst-windows-20261115-b9-setup.exe`, `psst-macos-20261115-b9.dmg`, `psst-web-20261115-b9.tar.gz`,
  `psst-ios-20261115-b3.ipa`. ABI: `arm64`, `armv7`, `x86_64`.
- **V appke** (Nastavenia → About / Help & About): Android `26.11.0-b9+2026-11-15` (bez medzier a zátvoriek —
  je súčasťou User-Agent), web a desktop
  `1.12.35-b9 (2026-11-15)`, iOS `26.11.0 (b3, 2026-11-15)`.
- Android `versionCode` = `(21 000 000 + číslo) × 10 + ABI` — vždy vyššie než pôvodné `202611xxx`, nové APK sa
  nainštaluje cez staré.
- `dist/android`, `dist/desktop`, `dist/web`, `dist/ios` obsahujú **len najnovšiu verziu**; staršie presúva
  `scripts/release/publish.py` do `dist/archive/<platforma>/` (nič nemaže). Prehľad: **`dist/LATEST.md`**
  (súbor, build, dátum, SHA-256, čo sa zmenilo).

## Stránka na stiahnutie — https://app.psst.pro/download (D59)

Verejná stránka s aktuálnym Android APK (arm64), Windows MSI a macOS DMG — číslo buildu, dátum, veľkosť, SHA-256,
návod na inštaláciu. Na serveri sú vždy len aktuálne súbory (`/opt/psst/server/downloads/`), staršie len v
`dist/archive/`. **Stránka sa aktualizuje automaticky, ručne sa na ňu nič nenahráva:**

| Build | Kto nahrá | Ako |
|---|---|---|
| Android | `scripts/android/sign-release.sh` (lokálne, po podpise, **len s `PSST_UPLOAD_DOWNLOAD_PAGE=1`**, D111) | `scripts/release/upload-download.sh android …-arm64.apk` |
| Windows + macOS | CI `web-desktop.yml`, job *Publish to app.psst.pro/download* | `scripts/release/upload-download.sh windows|macos …` |

`upload-download.sh` nahrá súbor cez SSH ako `psst-dl` (kľúč smie len `server/scripts/downloads.py`: overí SHA-256
prijatého súboru, odmietne starší build, prepíše stránku a `latest.json`, zmaže predošlý súbor platformy) a potom
súbor **stiahne cez HTTPS a porovná SHA-256** s lokálnym buildom — pri nezhode skončí chybou (a s ním aj build).
Kľúč: `~/psst-keys/psst-dl-upload` (lokálne), GitHub secret `PSST_DL_UPLOAD_KEY` + `PSST_DL_KNOWN_HOSTS` (CI).

**Kontrola, že stránka nie je pozadu:** `scripts/release/check-download-page.py` porovná `dist/latest.json`
(= `dist/LATEST.md`) so stránkou, v CI workflow *Download page check* (denne, po každom Web + Desktop behu a po
zmene `release/latest.json`) porovná `release/latest.json` z gitu. Zlyhá, ak má stránka starší build alebo iný SHA-256.

## 2–3. Web + Desktop

```sh
gh workflow run web-desktop.yml -R georgonr/psst
gh run watch -R georgonr/psst <run-id>
PSST_NOTE="čo sa zmenilo" scripts/release/fetch-web-desktop.sh <run-id> [--release]   # → dist/desktop, dist/web
# --release: GitHub release web-b<N>; na serveri potom: sudo scripts/fetch-web.sh
```

**Bez GitHub Actions (D110, 26.11.2):** web aj podpísaný a notarizovaný macOS build na tomto Macu:
```sh
cd ~/Developer/psst-web && ./scripts/layered.sh && cd apps/web && cp psst/config.json config.json && rm -rf webapp \
  && VERSION="<verzia>-b<N> (RRRR-MM-DD)" pnpm run build          # web → apps/web/webapp
node scripts/psst/check-no-matrix-to.mjs --bundle apps/web/webapp   # brána D111 (v koreni psst-web)
scripts/desktop/build-mac-local.sh ~/Developer/psst-web <N> <RRRRMMDD>   # → dist/desktop/psst-macos-…-b<N>.{dmg,zip}
```
`build-mac-local.sh` skopíruje web do `apps/desktop/webapp`, zabalí `webapp.asar` (kontrola veľkosti a config.json),
stavia **bez Nx cache** (`NX_SKIP_NX_CACHE=true` — `webapp.asar` nie je vstup Nx, z cache by vyšla appka s cudzím
alebo prázdnym webom; tak vznikol nepoužiteľný b39) a overí, že appka nesie práve tento `webapp.asar`.
Čísla CI web/desktop pokračujú nad lokálnymi (`run_number + 2`).

## 4. Android

```sh
gh workflow run android.yml -R georgonr/psst
PSST_NOTE="čo sa zmenilo" scripts/android/sign-release.sh --run <run-id>   # stiahne, podpíše kľúčom z ~/psst-keys
# na app.psst.pro/download ide build len s PSST_UPLOAD_DOWNLOAD_PAGE=1 (inak ostane len v dist/)
# výstup: dist/android/psst-android-<RRRRMMDD>-b<N>-{arm64,armv7,x86_64}.apk, …-b<N>.aab, SHA256SUMS; staré → dist/archive/android/
scripts/android/check-manifest.py dist/android/*.apk dist/android/*.aab   # Play Protect (D83), beží aj v CI a pred podpisom
scripts/android/search-gate.sh <x86_64.apk>   # vyhľadávanie v správach (D84), beží v sign-release.sh pred podpisom
```

**Play Protect (D83):** vydaný APK/AAB nesmie v zlúčenom manifeste (náš kód + upstream + knižnice) obsahovať
`RECEIVE_SMS`, `READ_SMS`, notification listener ani accessibility službu — Google Play Protect inak zablokuje
inštaláciu stiahnutú z /download. Štítok aplikácie musí byť doslovne `psst`. Kontrolu robí
`scripts/android/check-manifest.py`: CI (`android.yml`, APK aj AAB) zlyhá a `sign-release.sh` odmietne podpísať.

**Vyhľadávanie v správach (D84):** `sign-release.sh` pred podpisom spustí `scripts/android/search-gate.sh` na x86_64
APK v emulátore Android 14 (AVD `psst34` alebo pripojený emulátor). Postup kontroly:

1. Vytvorí dva testovacie účty `qa-sg…`. Partner (`search_check.py`, matrix-nio s E2EE) pošle 8 známych správ
   do **šifrovanej** miestnosti.
2. Telefón hľadá na karte **Správy** bez diakritiky a začiatkom slova (`cislo`, `stastn`, `ob`, `zlty kon`,
   `dvanast`) a jedno slovo, ktoré tam nie je.
3. Po reštarte appky musí nájsť aj novo prijatú správu.

Počty výsledkov sa vypočítajú z textov správ. Ak sa ktorýkoľvek nezhoduje, build sa nepodpíše ani nenahrá na
/download. Účty aj miestnosť sa na konci zmažú, aj pri chybe.

Kontrola potrebuje:
- `~/.local/psst-venv` s `matrix-nio[e2e]`, `requests` a `certifi`;
- ssh `psst`;
- Android SDK s emulátorom.

Trvá ~4 min. Podrobnosti: docs/android-search.md.

## 5. iOS

```sh
gh workflow run ios.yml -R georgonr/psst                 # simulátor, bez podpisu
scripts/ios/release-testflight.sh                        # podpísaný build → TestFlight (viď scripts/ios/README.md)
```

## 6. Server

```sh
cd server && sudo ./deploy.sh <IP> none   # na cieľovom serveri; none = Let's Encrypt bez e-mailu (D85)
sudo scripts/restore-test.sh               # skúšobná obnova najnovšej zálohy do dočasného prostredia (D85)
gh workflow run server-smoke.yml -R georgonr/psst            # lokálny test celého stacku v CI
```

Budíček pri žiadosti o overenie zariadenia beží ako `psst-wake` (`server/wake`, profil sygnal, D68); nginx mu zrkadlí
`sendToDevice/m.key.verification.request`.

Synapse beží z `server/synapse/Dockerfile` (oficiálny image + QR relácia 5 min, D66). Pri zmene verzie Synapse
upraviť `SYNAPSE_VERSION` v `compose.yml`; ak build zlyhá na `grep`, upstream zmenil riadok s `RendezvousHandler`
— skontrolovať, či je oprava ešte potrebná. Aktualizácia na serveri: rsync `server/` (bez `data`, `secrets`, `.env`,
`app`, `backups`, `downloads`; `--rsync-path="sudo rsync"`) a `sudo ./deploy.sh …` (viď `~/proj/psst-server-notes.md`).

## 7. Audit funkcií (docs/FEATURE-MATRIX.md, D64)

Vždy len **nové testovacie účty** (`qa-au*`, `mas-cli manage register-user`), na konci deaktivovať
(`sudo scripts/members.sh block <meno> --deactivate`); testovacie verejné kanály stiahnuť z adresára.

| platforma | ako | poznámka |
|---|---|---|
| Web | `node scripts/audit/web-audit.mjs <out> accounts.json [token]` | accounts: `{a,b,c,d}`; d = test hovoru s blokovaným UDP |
| Windows, macOS | `gh workflow run desktop-audit.yml -f run_id=<Web + Desktop run>` | secret `PSST_AUDIT_DESKTOP_ACCOUNTS` `{windows:{a,b,c}, macos:{…}}` |
| Upozornenia a hovory (D75) | web: `node scripts/audit/alerts-web.mjs <out> <user> <heslo> [webapp-dir]`; desktop: `gh workflow run desktop-audit.yml -f run_id=… -f suite=alerts` | desktop secret `PSST_AUDIT_ALERTS_ACCOUNTS` `{windows:{user,password}, macos:{…}}` |
| Android | emulátor `psst34` (Google APIs), `scripts/android/ui.py`, `mas-login.sh`, partner `scripts/audit/call-partner.mjs` | UDP blok: `adb root` + iptables |
| iOS | `gh workflow run ios-audit.yml` (XCUITest `PsstAuditTests` + `scripts/audit/ios-partner.mjs`) | secret `PSST_AUDIT_IOS_ACCOUNTS` `{a,b}` |

Výsledky (JSON zoznam `{id, status, note}`) → `python3 scripts/audit/matrix.py docs/FEATURE-MATRIX.md web=… windows=… macos=… android=… ios=…`.
Po audite secrets zmazať (`gh secret delete …`).

## Verzie

| Komponent | Verzia |
|---|---|
| element-web / desktop (fork) | v1.12.35 · Node 24 · pnpm 12.14.0 · Electron 44.9.3 · electron-builder 26.17.0 |
| Element Call embedded / standalone | 0.28.2 / `ghcr.io/element-hq/element-call:v0.28.2` |
| element-x-android (fork) | v26.11.0 · JDK 21 (Temurin) · Gradle 9.8.2 · AGP 9.3.2 · Kotlin 2.4.21 · compile/target SDK 37 · minSdk 24 · build-tools 37.0.0 |
| element-x-ios (fork) | 26.11.0 · runner `xcode-27` (GitHub public preview) · Xcode 27.x · XcodeGen 2.46.0 · iOS deployment target 18.5 |
| Synapse | `ghcr.io/element-hq/synapse:v1.165.0` |
| PostgreSQL | `postgres:18.7-alpine` |
| LiveKit | `livekit/livekit-server:v1.13.11` |
| lk-jwt-service | `ghcr.io/element-hq/lk-jwt-service:0.10.0` |
| nginx / certbot | `nginx:1.30.6-alpine` / `certbot/certbot:v5.10.0` |
| GitHub runnery | `ubuntu-24.04`, `macos-15`, `xcode-27`, `windows-2025` |
| Lokálne použité | python3 3.12 (ikony), openjdk 17 (keytool/jarsigner), Android build-tools 37.0.0 (apksigner, zipalign) v `~/.psst-tools` |

## Lokálne buildy (overené 2026-11-13 na Intel Macu, macOS 15.7)

Homebrew už pre Intel Mac nemá bottles (JDK by kompiloval zo zdrojov), preto sú JDK a Node stiahnuté
priamo od vydavateľov do `~/.local` (overené SHA-256). Cesty nastaví `source scripts/env.sh`.

| Nástroj | Verzia | Inštalácia |
|---|---|---|
| Docker (bez Docker Desktop) | colima 0.10.3 (VM `vz`, 4 CPU / 8 GB / 60 GB), docker CLI 29.9.3, engine 29.5.2, compose 5.7.1 | `brew install colima docker docker-compose docker-buildx`; `colima start --vm-type vz --cpu 4 --memory 8 --disk 60` |
| JDK | Temurin 21.0.13+9 | `~/.local/jdk-21.0.13+9` (api.adoptium.net, checksum overený) |
| Node.js | 24.22.0 (element-desktop `.node-version`) | `~/.local/node-v24.22.0-darwin-x64` (nodejs.org, SHASUMS256 overené) |
| pnpm | 12.14.0 | `npm i -g --prefix ~/.local pnpm@12.14.0` |
| Android SDK | cmdline-tools (Android CLI 1.1), platform-tools 37.0.1, emulator 37.2.13, build-tools 37.0.0, platforms 37 (Gradle stiahne) | `brew install --cask android-commandlinetools`; `sdkmanager --sdk_root=~/Library/Android/sdk ...` |
| Emulátor | AVD `psst33`: `system-images;android-33;google_apis;x86_64`, Pixel 6 | Intel Mac nespustí arm64 image → x86_64 (DECISIONS D19) |
| Testy | Playwright 1.64.1 + Chromium (`~/.local/pw`), Python 3.12 venv `~/.local/psst-venv` s matrix-nio 0.26.0 + vodozemac 0.10.0 | |

```sh
source scripts/env.sh

# Web (≈2,5 min)
cd forks/web && ./scripts/layered.sh && cd apps/web && cp psst/config.json config.json
rm -rf webapp && VERSION="$(jq -r .version package.json)-psst.$(git rev-parse --short=8 HEAD)" pnpm run build

# macOS desktop, universal dmg + zip (≈15 min); pnpm-workspace.yaml úpravu potom vrátiť (git checkout)
cd forks/web && printf '\nsupportedArchitectures:\n    os: [current]\n    cpu: [x64, arm64]\n' >> pnpm-workspace.yaml
cd apps/desktop && pnpm install --frozen-lockfile --filter element-desktop
mkdir webapp && tar -C webapp --strip-components=1 -xzf ../../../../dist/psst-web-*.tar.gz && pnpm run asar-webapp
NX_SKIP_NX_CACHE=true CSC_IDENTITY_AUTO_DISCOVERY=false VARIANT_PATH=psst/build.json pnpm run build:universal --publish never -m dmg zip
# NX_SKIP_NX_CACHE: inak nx vráti starý dmg z cache aj po výmene webapp.asar (D41)

# Android — APK a AAB v SAMOSTATNÝCH príkazoch (build skript vypína ABI splity, ak je v príkaze "bundle")
cd forks/android && echo "sdk.dir=$ANDROID_HOME" > local.properties
./gradlew --no-daemon :app:assembleGplayRelease      # ≈14 min s cache, prvýkrát ≈26 min
./gradlew --no-daemon :app:bundleGplayRelease        # ≈12 min
scripts/android/sign-release.sh <adresár s *-unsigned.apk / *.aab> dist/android

# Server lokálne (test režim: self-signed certifikát, compose.test.yml, voľnejšie limity)
cd server && ./deploy.sh --local-test
PY=~/.local/psst-venv/bin/python
$PY tests/server/run_local.py          # smoke test (17 kontrol) bez /etc/hosts
$PY tests/server/extra_test.py         # kanál + šifrované súbory (9)
$PY tests/server/oidc_clients_test.py  # MAS registrácia OIDC klientov všetkých appiek (5)
node scripts/web/register-test.mjs <out> <token1x> <token3x>   # registrácia tokenom cez MAS (4)
node scripts/web/live-test.mjs <out> <user> <pass>             # web naostro (7)
node scripts/web/call-test.mjs <out> <roomId> <label> <u1> <p1> <u2> <p2>   # hovor (5)
PSST_RELAY_ONLY=1 scripts/web/docker/run-call-test.sh <out> …  # hovor len cez TURN/TLS 443 (6)
cd server && scripts/backup.sh && scripts/restore.sh backups/daily/psst-….tar.gz.enc --force
```

Živé testy klientov proti lokálnemu stacku: `scripts/web/live-test.mjs`, `scripts/web/call-test.mjs`,
`scripts/desktop/live-test.mjs` (Playwright), Android `scripts/android/ui.py` + emulátor s `-writable-system`
(testovací certifikát v systémových CA, `10.0.2.2 chat.psst.pro …` v `/system/etc/hosts`). Podrobnosti v REPORT.md.

PSST web pre server: GitHub Release `web-<verzia>` s `psst-web.tar.gz` (stiahne `server/scripts/fetch-web.sh`):
`gh release create web-<verzia> dist/psst-web.tar.gz --latest`.

Cez GitHub Actions: Windows inštalátor (`web-desktop.yml` → `desktop-win`) a iOS simulátor (`ios.yml`,
runner `xcode-27`, Xcode 27.x, `ARCHS=arm64`).
