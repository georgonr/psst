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
| element-x-ios (fork) | 26.11.0 · runner `macos-26` · Xcode 27.x · XcodeGen 2.46.0 · iOS deployment target 18.5 |
| Synapse | `ghcr.io/element-hq/synapse:v1.165.0` |
| PostgreSQL | `postgres:18.7-alpine` |
| LiveKit | `livekit/livekit-server:v1.13.11` |
| lk-jwt-service | `ghcr.io/element-hq/lk-jwt-service:0.10.0` |
| nginx / certbot | `nginx:1.30.6-alpine` / `certbot/certbot:v5.10.0` |
| GitHub runnery | `ubuntu-24.04`, `macos-15`, `macos-26`, `windows-2025` |
| Lokálne použité | python3 3.12 (ikony), openjdk 17 (keytool/jarsigner), Android build-tools 37.0.0 (apksigner, zipalign) v `~/.psst-tools` |

Lokálny stroj (Intel Mac, Xcode 16.0, ~5 GB voľného miesta) klientov nezbuildí — dôvody v
[DECISIONS.md](DECISIONS.md) (D1).
