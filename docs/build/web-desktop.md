# psst Web + Desktop — build

Zdroj: `georgonr/psst-web`, vetva `psst` (base `v1.12.35`). V hlavnom repe je fork ako `forks/web`.

## Verzie nástrojov (z upstream monorepa v1.12.35)

| Nástroj | Verzia | Zdroj |
|---|---|---|
| Node.js | 24 (`.node-version`), desktop 24.22.0 (`apps/desktop/.node-version`) | engines `>=22.18` |
| pnpm | 12.14.0 (`devEngines.packageManager`, stiahne sa automaticky) | `package.json` |
| nx | catalog v `pnpm-workspace.yaml` | |
| webpack | `apps/web/webpack.config.ts` (`webpack-cli --mode production`) | |
| Electron | 44.9.3 | `apps/desktop/package.json` |
| electron-builder | 26.17.0 | `apps/desktop/package.json` |
| Element Call (embedded) | `@element-hq/element-call-embedded` 0.28.2 | `apps/web/package.json` |
| Playwright (smoke test) | 1.64.1 + Chromium | `scripts/web/smoke.mjs` |
| GitHub runnery | `ubuntu-24.04`, `macos-15` (arm64, universal build), `windows-2025` | workflow |

## CI (odporúčané)

Workflow: `.github/workflows/web-desktop.yml` (spúšťa sa ručne alebo pushom do `main` pri zmene workflowu / `scripts/web/**`).

```sh
gh workflow run web-desktop.yml -R georgonr/psst            # default web_ref=psst
gh workflow run web-desktop.yml -R georgonr/psst -f web_ref=<branch|tag|sha>
gh run watch -R georgonr/psst <run-id>
gh run download -R georgonr/psst <run-id> -n psst-web-dist -D dist/
gh run download -R georgonr/psst <run-id> -n psst-desktop-macos -D dist/
gh run download -R georgonr/psst <run-id> -n psst-desktop-windows -D dist/
gh run download -R georgonr/psst <run-id> -n psst-web-smoke -D dist/smoke
```

Joby a artefakty:

| Job | Runner | Artefakt | Obsah |
|---|---|---|---|
| `web` | ubuntu-24.04 | `psst-web-dist` | `psst-web-<ver>-psst.<sha>.tar.gz` (obsah `webapp/` vrátane `config.json`) |
| `web-smoke` | ubuntu-24.04 | `psst-web-smoke` | `login.png`, `register.png`, `smoke-result.json`, `console.log` |
| `desktop-mac` | macos-15 | `psst-desktop-macos` | `psst-<ver>-universal.dmg`, `psst-<ver>-universal-mac.zip` (unsigned) |
| `desktop-win` | windows-2025 | `psst-desktop-windows` | `squirrel-windows/psst Setup <ver>.exe`, `psst-<ver>.msi` (unsigned) |

> Push workflowu vyžaduje token so scope **`workflow`** (`gh auth refresh -h github.com -s workflow`).

## Lokálne (len ak je dosť miesta: ~6–8 GB pre node_modules + build)

Web:

```sh
git clone --depth 1 --branch psst https://github.com/georgonr/psst-web
cd psst-web
corepack enable || npm i -g pnpm@12.14.0     # alebo pnpm/setup
./scripts/layered.sh                          # = pnpm install --frozen-lockfile (+ js-sdk ak je na develop)
cd apps/web
cp psst/config.json config.json
VERSION=1.12.35-psst.local pnpm run build     # výstup: apps/web/webapp/
# rýchly test: npx serve webapp  (alebo python3 -m http.server -d webapp 8080)
```

Desktop (z vyššie postaveného webu):

```sh
cd psst-web/apps/desktop
pnpm install --frozen-lockfile --filter element-desktop
ln -s ../web/webapp ./webapp      # alebo rozbaliť psst-web-dist tar.gz do ./webapp
pnpm run asar-webapp              # -> webapp.asar
# macOS (universal; pre seshat obe architektúry: pridať do pnpm-workspace.yaml
#   supportedArchitectures: {os: [current], cpu: [x64, arm64]} a znova pnpm install)
CSC_IDENTITY_AUTO_DISCOVERY=false VARIANT_PATH=psst/build.json pnpm run build:universal --publish never -m dmg zip
# Windows (bash)
VARIANT_PATH=psst/build.json pnpm run build --publish never -w squirrel msi
# Linux (voliteľné)
VARIANT_PATH=psst/build.json pnpm run build --publish never -l tar.gz deb
# výstup: apps/desktop/dist/
```

Smoke test lokálne:

```sh
mkdir -p /tmp/pw && cd /tmp/pw && npm init -y && npm i playwright@1.64.1 && npx playwright install chromium
cp <psst>/scripts/web/smoke.mjs . && node smoke.mjs /path/to/webapp /tmp/pw/out
```

## Aktualizácia na nový upstream tag

```sh
cd forks/web
git fetch --depth 50 https://github.com/element-hq/element-web tag vX.Y.Z
git merge vX.Y.Z            # konflikty len v súboroch so značkou PSST: (grep -rn "PSST:")
git push origin psst
gh workflow run web-desktop.yml -R georgonr/psst
```
