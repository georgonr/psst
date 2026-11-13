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

## 2–3. Web + Desktop

```sh
gh workflow run web-desktop.yml -R georgonr/psst
gh run watch -R georgonr/psst <run-id>
gh run download -R georgonr/psst <run-id> -n psst-web-dist        -D dist/
gh run download -R georgonr/psst <run-id> -n psst-desktop-macos   -D dist/
gh run download -R georgonr/psst <run-id> -n psst-desktop-windows -D dist/
```

## 4. Android

```sh
gh workflow run android.yml -R georgonr/psst
scripts/android/sign-release.sh --run <run-id>   # stiahne nepodpísané APK/AAB a podpíše kľúčom z ~/psst-keys
# výstup: dist/android/*.apk, *.aab, SHA256SUMS
```

## 5. iOS

```sh
gh workflow run ios.yml -R georgonr/psst                 # simulátor, bez podpisu
gh workflow run ios-release.yml -R georgonr/psst         # až po doplnení secrets (viď docs/build/ios.md)
```

## 6. Server

```sh
cd server && LETSENCRYPT_EMAIL=admin@macet.eu ./deploy.sh   # na cieľovom serveri, nie lokálne
gh workflow run server-smoke.yml -R georgonr/psst            # lokálny test celého stacku v CI
```

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
CSC_IDENTITY_AUTO_DISCOVERY=false VARIANT_PATH=psst/build.json pnpm run build:universal --publish never -m dmg zip

# Android — APK a AAB v SAMOSTATNÝCH príkazoch (build skript vypína ABI splity, ak je v príkaze "bundle")
cd forks/android && echo "sdk.dir=$ANDROID_HOME" > local.properties
./gradlew --no-daemon :app:assembleFdroidRelease      # ≈14 min s cache, prvýkrát ≈26 min
./gradlew --no-daemon :app:bundleFdroidRelease        # ≈12 min
scripts/android/sign-release.sh <adresár s *-unsigned.apk / *.aab> dist/android

# Server lokálne (test režim: self-signed, voľnejšie login limity)
cd server && COMPOSE_FILE=compose.yml:compose.test.yml LIVEKIT_USE_EXTERNAL_IP=false LIVEKIT_NODE_IP=127.0.0.1 \
  ./deploy.sh --no-letsencrypt
~/.local/psst-venv/bin/python tests/server/run_local.py      # smoke test bez /etc/hosts
~/.local/psst-venv/bin/python tests/server/extra_test.py     # kanál + súbory
```

Živé testy klientov proti lokálnemu stacku: `scripts/web/live-test.mjs`, `scripts/web/call-test.mjs`,
`scripts/desktop/live-test.mjs` (Playwright), Android `scripts/android/ui.py` + emulátor s `-writable-system`
(testovací certifikát v systémových CA, `10.0.2.2 chat.macet.eu …` v `/system/etc/hosts`). Podrobnosti v REPORT.md.

Cez GitHub Actions: Windows inštalátor (`web-desktop.yml` → `desktop-win`) a iOS simulátor (`ios.yml`,
runner `xcode-27`, Xcode 27.x, `ARCHS=arm64`).
