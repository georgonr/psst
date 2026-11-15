# PSST — report (2026-11-15, dávky 7 a 8: verzovanie + iOS príprava; administračná stránka)

Rozhodnutia: DECISIONS D54 (verzovanie), D55 (iOS), D56 (administrácia). Staršie dávky nižšie a v git histórii.

## Dávka 8 — administrácia https://app.macet.eu/admin

**Verdikt: hotovo a nasadené.** Prihlásenie bežným účtom cez MAS, prístup len pre adminov (teraz `geo`), ostatní 403.
Pozvánky sú priamo registračné tokeny MAS. Test na produkcii (Playwright, testovacie účty potom deaktivované):

| Test | Výsledok |
|---|---|
| prihlásenie admina cez MAS, cookie Secure/HttpOnly/SameSite=Strict/Path=/admin/30 min, žiadny token v prehliadači | ✅ |
| nová pozvánka → kód `XXXX-XXXX` + text „Pozvánka do psst: … Platí do 22. 11." | ✅ |
| registrácia z **webu** kódom → stav „použitá" 1/1, zaregistrovaný účet priradený, u člena vidieť pozvánku | ✅ |
| registrácia z **Android appky** (emulátor, psst b9) kódom z admin stránky → účet, stav „použitá" | ✅ |
| Zablokovať → „zablokovaný", Odblokovať → „aktívny"; `geo` nemá tlačidlo | ✅ |
| Zrušiť druhú pozvánku → „zrušená", registrácia s ňou odmietnutá | ✅ |
| POST z cudzieho pôvodu → 403, POST bez CSRF tokenu → 403 | ✅ |
| neadmin → 403 „Prístup zamietnutý", bez session → presmerovanie na prihlásenie | ✅ |
| mobil 390 px: karty, bez vodorovného posúvania | ✅ |
| server-smoke v CI (čistá inštalácia + obnova zo zálohy) s novou službou | ✅ 17/17 |

Audit log: `/opt/psst/server/data/admin/audit.log` (zálohuje sa). MAS obmedzuje počet registrácií z jednej IP —
pri opakovaných testoch dočasne zablokoval ďalšie registrácie (ochrana ponechaná).

## Dávka 7 — verzovanie a iOS

**Verzovanie (D54, BUILD.md):** `psst-<platforma>-<RRRRMMDD>-b<číslo>[-<abi>].<prípona>`, číslo = beh CI
(iOS = posledný TestFlight + 1), v appkách v About. `dist/<platforma>/` = len najnovšie, staré v `dist/archive/`,
prehľad `dist/LATEST.md`.

| Platforma | Aktuálne | V appke |
|---|---|---|
| Android | `dist/android/psst-android-20261115-b9-arm64.apk` (+ armv7, x86_64, AAB) | `26.11.0-b9 (2026-11-15)`; versionCode 210000094 — inštaluje sa cez staré (overené) |
| Windows / macOS | `dist/desktop/psst-windows-20261115-b9.msi`, `-setup.exe`, `psst-macos-20261115-b9.dmg`, `.zip` | `1.12.35-b9 (2026-11-15)` |
| Web | `dist/web/psst-web-20261115-b9.tar.gz`, nasadený na app.macet.eu (release `web-b9`) | `1.12.35-b9 (2026-11-15)` |
| iOS | ešte žiadny podpísaný build | `26.11.0 (bN, RRRR-MM-DD)` (simulátorový build v CI prešiel) |

Archív: staré Android `psst-26.11.0-*` a nepodpísané F-Droid z 13. 11., desktop `psst-1.12.35-*`, web 1.12.35-psst.*,
iOS simulátor + screenshoty z 13. 11.

**iOS (D55):** bundle ID (app, NSE, share) s Push + Associated Domains + App Groups, distribučný certifikát
`K2778R2L24`, profily generuje skript, workflow s podpisom a uploadom, Sygnal APNs na serveri (overené odpoveďou
APNs), universal links s Team ID, `scripts/ios/release-testflight.sh` (otestované: preflight, profily, import
certifikátu; zastaví sa na chýbajúcej App Group / zázname appky s presným návodom). Ručne zostáva (Apple to cez API
nedovolí): **App Group + priradenie k 3 identifikátorom** a **záznam appky v App Store Connect**
(`scripts/ios/README.md`), potom jeden príkaz. Exportná zhoda: `ITSAppUsesNonExemptEncryption = false` — žiadna
povinnosť voči úradom pre TestFlight/EÚ; pred verejným vydaním vo Francúzsku overiť ANSSI.

## Čo ostáva

1. iOS: App Group + záznam appky (ručne) → `scripts/ios/release-testflight.sh`.
2. Android telefón (jj): nainštalovať `psst-android-20261115-b9-arm64.apk`, otestovať notifikácie a zvonenie,
   potom deaktivovať testovací účet `qa-ring`.
3. Voľná pozvánka `vljYMyTsyyyA` z 13. 11. (platí do 13. 12.) — ak sa nepoužíva, zrušiť na admin stránke.

---

## Dávka 6 (2026-11-15: notifikácie a zvonenie na fyzických telefónoch)

Rozhodnutie: DECISIONS D53. Predchádzajúci report (FCM, 2026-11-14) je nižšie a v git histórii.

## Verdikt

**iPhone (oficiálny Element X, účet geo): funguje** — správa prišla na zamknutú obrazovku so zvukom, hovor prišiel
a dal sa prijať (test 15. 11., 08:46–09:00). **Android (psst, účet jj): oprava hotová a overená v emulátore,
na telefóne ešte neotestovaná** — treba nainštalovať nové APK.

## Príčina

Server bol v poriadku: Synapse doručil každý push (Android → náš Sygnal → FCM, iPhone → brána Elementu), obe brány
vrátili 200 a telefóny sa po každom pushi do sekundy ozvali na server. Firewall, egress ani push pravidlá nič nebrzdia.
Chyby boli v zariadeniach a appke:
- **Android**: do 14. 11. 08:13 žiadny funkčný pusher (starý ntfy zanikol, D52). Potom notifikácie chodili, ale
  upstream Element X dáva správy do kanála s dôležitosťou DEFAULT (bez vyskakovacieho okna) a hovor zvoní, len ak
  appka spustená pushom do 3 s zistí aktívny hovor — lacný telefón to nestihne → len tichá notifikácia „📹 Incoming call".
- **iPhone**: doručenie fungovalo celý čas; pri prvých testoch bola otvorená aj webová appka s rovnakým účtom
  (prečítala správy hneď, Element X na iPhone potom notifikáciu nezobrazí). Po zavretí webu notifikácie chodia.
- Pozor pri testoch: Android telefón je prihlásený ako **jj**, nie geo.

## Čo som opravil

| Čo | Zmena |
|---|---|
| psst-android `c4ff18e3` | kanál pre správy `IMPORTANCE_HIGH` s novým ID (vyskakovacie okno + zvuk, starý stlmený kanál sa zmaže); hovor čaká na stav hovoru 12 s a zvoní, kým zvonenie neexpiruje |
| `dist/android/` | nové podpísané APK + AAB (rovnaký kľúč, inštaluje sa cez staré) |
| testy | `tests/server/prod_push_send.py` — správa a skutočné zvonenie (call.member + ring) z testovacieho účtu |

Overené v emulátore s Google Play services (appka zatvorená, obrazovka zamknutá): správa = vyskakovacia notifikácia
so zvukom (kanál importance 4); hovor = celoobrazovkové „Incoming Element Call" s Accept/Reject.

## Test na telefónoch

| Telefón | Správa | Hovor |
|---|---|---|
| iPhone, Element X, geo | ✅ zamknutá obrazovka + zvuk | ✅ prišiel, prijatý |
| Android, psst, jj | ⏳ čaká na nové APK | ⏳ čaká na nové APK |

## Čo ostáva

1. **Android**: nainštalovať `dist/android/psst-26.11.0-arm64-v8a.apk`, raz otvoriť, povoliť notifikácie a
   celoobrazovkové upozornenia, zatvoriť appku → test správy a hovoru (testovací účet `qa-ring` ostáva aktívny len
   na tento test, potom ho deaktivovať: `sudo scripts/members.sh block qa-ring --deactivate`).
2. iPhone má len zvuk „tut" — zvuk notifikácie v oficiálnom Element X nezmeníme; vlastný zvuk pôjde až v našej
   iOS appke psst (TestFlight dávka — rozpracovaná, viď nižšie).
3. Na tom istom účte nenechávať otvorený web pri teste — správy prečíta a telefón ich nezobrazí.
4. **iOS TestFlight (prerušená dávka)**: kľúče presunuté do `~/psst-keys` a nikdy neboli v gite; Team ID `MHV67VMY8T`;
   vytvorené bundle ID `eu.macet.psst`, `.nse`, `.shareextension` (Push, Associated Domains, App Groups), distribučný
   certifikát `K2778R2L24`, GitHub secrets pre API kľúč. Blokuje: App Group `group.eu.macet.psst` sa nedá vytvoriť
   cez API a Xcode v CI odmieta API kľúč („Authentication failed") — treba vyriešiť pred podpísaným buildom.

---

## Predchádzajúca dávka (2026-11-14, piata: Android notifikácie cez Google FCM): Android notifikácie cez Google FCM)

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
