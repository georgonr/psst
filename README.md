# psst

**psst** je súkromný messenger postavený na [Matrixe](https://matrix.org/) — vlastný Synapse homeserver pre
**psst.pro** (ID `@meno:psst.pro`) a klienti Element s vlastným brandingom pre web, Windows, macOS, Android a iOS.

- vlastný server bez federácie; registrácia otvorená pre každého od 18 rokov, chránená **hCaptcha** a limitom
  na IP, s povinným súhlasom s Podmienkami (priamo v appkách cez Matrix Authentication Service, D88); adresár
  používateľov je vypnutý — ľudia sa nájdu len podľa presného mena účtu
- notifikácie cez vlastnú push bránu (Sygnal): Android doručuje Google FCM, iOS Apple APNs — cez ne ide len ID udalosti,
  nikdy obsah (ani šifrovaný); žiadna analytika ani iné služby Google
- 1:1 chaty, skupiny, kanály (adresár miestností viditeľný len používateľom servera), súbory
- end-to-end šifrovanie predvolene vo všetkých nových miestnostiach
- hlasové a video hovory vrátane skupinových: Element Call + self-hosted LiveKit SFU
- bez analytiky (PostHog, Sentry), bez bug reportov a integrácií tretích strán

| | |
|---|---|
| Matrix server_name (ID `@meno:psst.pro`), úvodná stránka | `psst.pro` (`www.psst.pro` presmeruje) |
| Homeserver | `chat.psst.pro` |
| Prihlásenie / registrácia (MAS) | `chat.psst.pro/auth/` |
| Web, stiahnutie appiek, administrácia | `app.psst.pro`, `app.psst.pro/download/`, `app.psst.pro/admin` |
| Element Call (samostatne) + TURN/TLS na 443 | `call.psst.pro` |
| Push brána (Sygnal: FCM + APNs + Web Push) | `chat.psst.pro/_matrix/push/v1/notify` |
| Bundle / package id | `eu.macet.psst` |

## Štruktúra repa

```
assets/            logo (psst-logo.svg), slovná značka, assets/generated/ = všetky ikony
scripts/
  make-icons.sh    generátor všetkých ikon z geometrie loga
  enable-ci.sh     aktivuje GitHub Actions (vyžaduje token so scope `workflow`)
  web/ android/    pomocné skripty (smoke test webu, emulátorový test, lokálne podpisovanie APK/AAB)
ci/workflows/      GitHub Actions workflowy (web-desktop, android, ios, ios-release, server-smoke)
forks/             git submoduly (vetva psst):
  web/             georgonr/psst-web     ← element-hq/element-web v1.12.35 (web + desktop v apps/desktop)
  android/         georgonr/psst-android ← element-hq/element-x-android v26.11.0
  ios/             georgonr/psst-ios     ← element-hq/element-x-ios 26.11.0
server/            docker compose stack: Synapse, MAS, PostgreSQL, LiveKit, coturn, lk-jwt-service, Element Call,
                   Sygnal, nginx, certbot; deploy.sh, members/backup/restore/healthcheck — DEPLOY-CHECKLIST.md
tests/server/      smoke test servera (registrácia tokenom, E2EE správa, skupina, federácia off, MatrixRTC)
docs/              podrobnosti po platformách: decisions/, build/, report/
DECISIONS.md       všetky rozhodnutia a dôvody
BUILD.md           presné príkazy a verzie nástrojov
REPORT.md          stav projektu, výsledky overenia, otvorené veci
```

Forky si stiahnete cez `git submodule update --init --depth 1`.

## Ako sa buildí

Všetky klientske buildy bežia na GitHub Actions (verejné repo, runnery zadarmo). Najprv raz:

```sh
gh auth refresh -h github.com -s workflow   # token musí mať scope `workflow`
./scripts/enable-ci.sh                      # presunie workflowy do .github/workflows a spustí buildy
```

| Platforma | Workflow | Výstup |
|---|---|---|
| Web (app.psst.pro) | `web-desktop.yml` → job `web` + `web-smoke` | `psst-web-dist` (tar.gz) |
| macOS | `web-desktop.yml` → `desktop-mac` | nepodpísaný universal `.dmg` + `.zip` |
| Windows | `web-desktop.yml` → `desktop-win` | `psst Setup <ver>.exe` + `.msi` |
| Android | `android.yml` → `apk`, `aab`, `emulator` | nepodpísané APK (arm64, armv7, x86_64) + AAB → podpis lokálne `scripts/android/sign-release.sh` |
| iOS | `ios.yml` (simulátor), `ios-release.yml` (podpísaný IPA po doplnení certifikátov) | `.app` pre simulátor, screenshoty |
| Server | `server-smoke.yml` | výsledky testov, logy |

Presné príkazy, lokálne postupy a verzie nástrojov: [BUILD.md](BUILD.md). Nasadenie servera:
[server/README.md](server/README.md).

## Licencia

Klienti sú forky projektov Element pod **AGPL-3.0** (element-web aj pod GPL-3.0/komerčnou licenciou) —
licenčné hlavičky a súbory `LICENSE*` vo forkoch sú nezmenené a obrazovky „O aplikácii" odkazujú na zdrojový
kód. Zmeny vo forkoch sú označené komentárom `PSST:`.
