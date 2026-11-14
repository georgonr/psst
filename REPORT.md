# PSST — report (2026-11-14, piata dávka: Android notifikácie cez Google FCM)

Predchádzajúce reporty sú v git histórii. Rozhodnutia tejto dávky: DECISIONS D47–D52. Server: `~/proj/psst-server-notes.md`.

## Verdikt

**Hotovo: Android appka dostáva notifikácie cez Google FCM a náš vlastný Sygnal, bez akejkoľvek druhej appky.**
Overené na produkcii v emulátore s Google Play services: pri ukončenej appke a vypnutej obrazovke prišla
notifikácia so šifrovanou správou za 2 sekundy; prichádzajúci hovor prišiel ako notifikácia. ntfy je zo servera preč.

## Stav po bodoch

| # | Bod | Stav |
|---|---|---|
| 1 | Firebase | ✅ firebase-tools 15.36 + gcloud 593 (v `~/.local`). Projekt `psst-macet` (č. 5949287930), Android appka `eu.macet.psst` (`1:5949287930:android:1866646413fdbb5d908843`), `google-services.json` v `~/psst-keys`. Service account `sygnal-fcm@psst-macet.iam.gserviceaccount.com` (len FCM), kľúč: server `/opt/psst/server/secrets/fcm/service-account.json` (600 root) + `~/psst-keys/sygnal-fcm-sa.json` (600). Analytics/Crashlytics nezapnuté; ~30 automaticky zapnutých API vypnutých; API kľúč obmedzený (D48). |
| 2 | Sygnal | ✅ FCM HTTP v1 (`type: gcm, api_version: v1`), `https://chat.macet.eu/_matrix/push/v1/notify` (GET 405, POST {} 400 = Sygnal odpovedá). Pusher `event_id_only`. Žiadny nový port: zvonka 22, 80, 443, 7881 otvorené; 3478, 5000, 5432, 7880, 8008, 8081, 8448, 25 zatvorené. |
| 3 | Android fork | ✅ psst-android `84208b65`: variant `gplay` s FCM ako jediným providerom, brána náš Sygnal, UnifiedPush von. Podpísané APK (arm64, armv7, x86_64) + AAB tým istým kľúčom v `dist/android/`. |
| 4 | Server | ✅ ntfy odstránený (kontajner, image, dáta, šablóna), `push.macet.eu` → 301 na app.macet.eu (staré endpointy 410). `deploy.sh`, `healthcheck.sh`, `backup.sh`, `restore.sh` upravené. Healthcheck na produkcii: OK, 0 varovaní. Stránka Ochrana súkromia prepísaná (Google FCM, čo Google vidí). |
| 5 | Overenie | ✅ viď nižšie. Testovacie účty `qa-fcm` a `qa-sender` deaktivované. |
| 6 | Záver | ✅ repo aj fork pushnuté, REPORT, DECISIONS, `server/README.md`, `DEPLOY-CHECKLIST.md`, `psst-server-notes.md` aktualizované. CI zelené: Android (gplay build + emulátor), Web+Desktop, server-smoke 17/17. |

## Test notifikácií (produkcia, emulátor API 33 s Google Play services 23.18, bez ntfy)

| Krok | Výsledok |
|---|---|
| Inštalácia nového APK, prihlásenie `qa-fcm` cez MAS | ✅ appka sa nepýtala na žiadnu ďalšiu appku ani distribútora |
| Pusher v Synapse | `eu.macet.psst`, `https://chat.macet.eu/_matrix/push/v1/notify`, `event_id_only` |
| Appka ukončená (žiadny proces), obrazovka vypnutá → šifrovaná správa z `qa-sender` | ✅ notifikácia **za 2 s**, „FCM test: qa-sender — FCM test 06b107" (dešifrované v zariadení) |
| Cesta | Synapse → Sygnal 200 → FCM (message id) → Google Play services → appka |
| Prichádzajúci hovor (qa-sender zavolal z app.macet.eu, appka ukončená) | ✅ notifikácia „📹 Incoming call" |
| Obsah APK | FCM áno; `org/unifiedpush` 0; analytics/measurement/crashlytics SDK 0; `push.macet.eu` 0; matrix.org brána 0 |

Poznámky k testu:
- Emulátor nemá nastavený PIN, „zamknutá" = vypnutá obrazovka so swipe zámkom.
- Hovor prišiel ako bežná notifikácia, **nie ako celoobrazovkové zvonenie** — to som nevidel a neoveroval ďalej.
- Prvý pokus nedorazil: spojenie Google Play services s FCM v emulátore bolo po noci mŕtve; po obnovení siete
  dorazili aj čakajúce správy. Na strane servera a Googlu bolo doručenie v poriadku od začiatku.
- Pri teste sa odhalila chyba v mojom nasadzovacom príkaze (`rsync --exclude app` vynechal aj `templates/app`) — opravené.

## Artefakty (`~/proj/psst/dist/android/`)

| Súbor | SHA-256 |
|---|---|
| `psst-26.11.0-arm64-v8a.apk` (telefóny) | `3426a6d7e45465a77b5b0eb35d78c817d988589ea04e1f0404c92dc68c82506e` |
| `psst-26.11.0-armeabi-v7a.apk` | `83290d8e667738bd65e5067b22aa7bb6ad39f6fd21f4db1e93ca6c55556ed776` |
| `psst-26.11.0-x86_64.apk` | `bcafca757a486346ce447747db04b069723d50ec682a8aea5da3dbd9a5d0c86f` |
| `psst-26.11.0.aab` | `e0d4ad94abe3c958c1e4c3d614f9e2a058c6357a75d0c67aba503c95e1dc9f1a` |

Podpis: `3a6428cf51ee8f5e10e84fac5ca8a6b3c3b8c34d2674db0f2224d1d0097d3899` (rovnaký keystore).

## CI opravy po pushi

- server-smoke 2.1 padal (aj pred touto dávkou): test hľadal MAS na `auth.` subdoméne; teraz zistí adresu z `auth_metadata` (MAS na `/auth/`, D42).
- Android emulátor test: systémový dialóg „Pixel Launcher isn't responding" na pomalom CI emulátore zakrýval appku; skript ho teraz zavrie.

## Čo ostáva

- **Kto má APK z 13. 11., musí nainštalovať nové** — staré už notifikácie nedostane (D52). ntfy appku môže odinštalovať.
- Neoverené na fyzickom telefóne (len emulátor); celoobrazovkové zvonenie hovoru neoverené.
- iOS push stále čaká na APNs kľúč (ten istý Sygnal).
- Na serveri počúva port 25 (lokálny postfix z hardeningu) — zvonka je zatvorený firewallom.
