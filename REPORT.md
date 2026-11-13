# PSST — report (2026-11-13)

## Verdikt

**Zdrojový kód, konfigurácia, serverový stack, CI a dokumentácia sú hotové a pushnuté. Nič však zatiaľ nebolo
skompilované ani spustené.** Všetky buildy aj overenie (bod 7) bežia na GitHub Actions a GitHub odmieta
workflowy, lebo token `gh` účtu `georgonr` nemá scope `workflow`. Po jednom interaktívnom príkaze
(`gh auth refresh -s workflow`) a `./scripts/enable-ci.sh` sa spustí všetko naraz. Pri prvom behu treba
počítať s drobnými opravami: kód forkov bol overený len staticky.

## Stav po bodoch

| # | Bod | Stav |
|---|---|---|
| 0 | Repo | ✅ `georgonr/psst` (verejné), forky `psst-web`, `psst-android`, `psst-ios` (GitHub forky, vetva `psst`) ako submoduly v `forks/`. `psst-desktop` netreba — element-desktop je archivovaný a žije v monorepe element-web (D3). |
| 1 | Logo a ikony | ✅ `assets/psst-logo.svg`, slovná značka, `scripts/make-icons.sh` (čistý Python, každá veľkosť kreslená z geometrie). Overené vizuálne + `file`: iOS 1024×1024 RGB bez alfy, `.icns`, `.ico` s 10 veľkosťami 16–256. |
| 2 | Element Web | 🟡 fork hotový (`psst-web@9befe86`, základ v1.12.35); produkčný dist sa nezbuildil (CI). |
| 3 | Element Desktop | 🟡 branding hotový v `apps/desktop`; macOS lokálne nezbuildované (disk ~5 GB, D1) → job `desktop-mac` v CI; Windows workflow pripravený, nespustený. |
| 4 | Element X Android | 🟡 fork hotový (`psst-android@c26b2d9`, v26.11.0); keystore vygenerovaný; podpisový skript overený na testovacích artefaktoch; APK/AAB nezbuildované. |
| 5 | Element X iOS | 🟡 fork hotový (`psst-ios@4066e4b`, 26.11.0); xcodegen prebehol; kompilácia a simulátor nespustené (potrebný Xcode 27 → CI `macos-26`). Release workflow pripravený na doplnenie certifikátov. |
| 6 | Server | ✅ `server/` compose (Synapse 1.165.0, Postgres 18.7, LiveKit 1.13.11, lk-jwt-service 0.10.0, Element Call 0.28.2, nginx, certbot), `deploy.sh`, skripty na pozvánky/admina/zálohu/obnovu, `server/README.md`. Nič nenasadené. |
| 7 | Overenie | 🔴 testy napísané (`tests/server/smoke_test.py`, `scripts/web/smoke.mjs`, `scripts/android/emulator-test.sh` + `check_ui.py`, iOS kroky v `ios.yml`), **ani jeden nespustený** (D6, D12). |
| 8 | Dokumentácia | ✅ README.md, DECISIONS.md, BUILD.md, REPORT.md + `docs/{decisions,build,report}/*`. |

## Čo sa reálne overilo

| Kontrola | Výsledok |
|---|---|
| Ikony: rozmery, typ PNG (RGB/RGBA), `.icns` cez iconutil, `.ico` hlavička, vizuálna kontrola 192 px, 32 px a slovnej značky | PASS |
| YAML všetkých 5 workflowov (Ruby YAML parser), `actionlint` (web, iOS) | PASS |
| `compose.yml` + `compose.test.yml` voči oficiálnej compose-spec schéme; vyrenderované šablóny bez zvyšných placeholderov; `bash -n` všetkých skriptov; `py_compile` smoke testu | PASS |
| Syntax upravených `.ts/.tsx` (esbuild), JSON web configu | PASS |
| `check_ui.py` (Android): vzorový „dobrý" dump → exit 0; dump s „Change account provider" a editovateľným poľom → 4 porušenia, exit 1 | PASS |
| `sign-release.sh`: zipalign + apksigner v1/v2/v3 a jarsigner na malých testovacích APK/AAB, správny odtlačok | PASS |
| Synapse config parse, `nginx -t` | nespustené (inštalácia Synapse/nginx lokálne > 1 GB, brew kompiloval zo zdrojov) |
| Stack v Dockeri, 2 účty, E2EE správa, skupina, federácia off, MatrixRTC | **čaká na CI** |
| Web dist sa načíta a mieri na chat.macet.eu, bez zmeny homeservera | **čaká na CI** |
| Android sa nainštaluje do emulátora, homeserver sa nedá prepnúť | **čaká na CI** |
| iOS sa skompiluje a spustí v simulátore | **čaká na CI** |

## Opravy, ktoré som urobil po kontrole práce

- Web config zakazoval verejné miestnosti a priestory → kanály by nefungovali. Povolené (D13) + Synapse
  `room_list_publication_rules: allow`, adresár len pre prihlásených.
- Chýbali `assetlinks.json` a `apple-app-site-association` pre app links → nginx ich servíruje na app.macet.eu (D15).
- Push lokálnej histórie padal na `SIGBUS` (iCloud odložil objekty v `.git`) → súbory vynútene stiahnuté, `git fsck` čistý.

## Artefakty a cesty

| Čo | Kde |
|---|---|
| Ikony | `assets/generated/` (web, windows/psst.ico, macos/psst.icns, ios/AppIcon.appiconset, android/res, linux) |
| Android release keystore | `~/psst-keys/psst-release.jks` (PKCS12, RSA 4096, alias `psst`, platný do 2054-03-31), heslá `~/psst-keys/keystore.properties` (600) |
| Odtlačok certifikátu (SHA-256) | `3A:64:28:CF:51:EE:8F:5E:10:E8:4F:AC:5C:A8:A6:B3:C3:B8:C3:4D:26:74:DB:0F:22:24:D1:D0:09:7D:38:99` |
| Android build-tools (apksigner, zipalign) | `~/.psst-tools/build-tools-37.0.0` |
| Buildy klientov | po CI: `dist/` (gitignored) — názvy artefaktov v BUILD.md |

## Otvorené veci, ktoré potrebujú tvoje prístupy

1. **`gh auth refresh -h github.com -s workflow`** a potom `./scripts/enable-ci.sh` — odblokuje body 2–5 a 7.
   Následne `scripts/android/sign-release.sh --run <id>` na podpis APK/AAB.
2. **DNS:** A/AAAA záznamy `chat.macet.eu`, `app.macet.eu`, `call.macet.eu` → IP servera.
3. **Server:** výber hostiteľa; firewall 80/tcp, 443/tcp, 7881/tcp, 7882/udp (+ SSH); `LETSENCRYPT_EMAIL`.
4. **Apple Developer:** Team ID (aj do `server/.env` → `APPLE_TEAM_ID`), App ID `eu.macet.psst` + `.nse` +
   `.shareextension`, App Group `group.eu.macet.psst`, profily a certifikát → secrets pre `ios-release.yml`
   (zoznam v `docs/build/ios.md`); APNs kľúč + Sygnal pre push.
5. **Google Play:** účet v Play Console a nahranie AAB (podpísaného lokálnym kľúčom; zvážiť Play App Signing).
6. **Podpisovanie desktopu:** Apple Developer ID + notarizácia (macOS), code-signing certifikát (Windows) —
   inak Gatekeeper/SmartScreen varujú.
7. **Stránky na macet.eu:** podmienky a ochrana súkromia (odkazujú na ne mobilné appky).

## Známe obmedzenia

- Registrácia s tokenom len na webe/desktope; mobilné appky sa len prihlasujú (D14).
- Bez TURN servera: klienti s blokovaným UDP aj TCP 7881 sa do hovoru nepripoja.
- Zdieľanie polohy vypnuté (bez MapTiler kľúča).
- Niektoré preložené reťazce stále obsahujú „Element" (napr. „Element Call").
- Upstream unit testy forkov neboli upravené ani spustené.
- `~/Desktop` je v iCloude a disk je na 98 % — odporúčam presunúť repo mimo Desktop alebo vypnúť
  „Optimalizovať úložisko Macu", inak git občas visí.

Podrobnosti: `docs/report/web-desktop.md`, `docs/report/android.md`, `docs/report/ios.md`, `docs/report/server.md`.
