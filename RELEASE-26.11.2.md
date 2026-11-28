# psst 26.11.2 — vydanie (dávka 29 + doplnok o odkazoch, D99–D111)

Stav k 28. 11. 2026. Do Play Console sa nič neposielalo (Google kontroluje b54). iOS je len v TestFlighte (interná
skupina „psst“), na kontrolu ho pošle majiteľ. Metadáta v App Store Connect sa skriptom nemenili.

## Buildy

| Platforma | Build | Kde | Kontroly |
|---|---|---|---|
| iOS | **26.11.2 (9)** | TestFlight, skupina psst, VALID, `usesNonExemptEncryption=false`; IPA `dist/ios/psst-ios-20261128-b9.ipa` (`1ec015f0…`) | entitlements: applinks psst.pro + app.psst.pro, aps production, App Group; NSE + Share; `PsstLab_PsstMesh.bundle` en/sk; brána matrix.to na IPA OK |
| Android | **26.11.2-b59** (versionCode 21000059x) | len `dist/android/`: APK arm64 (`77f60a2b…`), armv7 (`cb0b8530…`), x86_64, AAB (`d9a23ca1…`), `mapping-b59.txt.gz` | podpis 3A:64…:38:99, check-manifest OK, vyhľadávanie (D84) 8/8, brána matrix.to OK |
| Web | **1.12.35-b40** | nasadené na app.psst.pro | `permalink_prefix https://psst.pro`, brána balíka OK, živý test (nižšie) |
| macOS | **b40** | `dist/desktop/psst-macos-20261128-b40.{dmg,zip}` (`cc69d2d3…`) | Developer ID, notarizované, staple, Gatekeeper „accepted“; spustené s oddeleným profilom → prihlasovacia obrazovka SK, web b40 |
| Windows | b38 (bez zmeny) | stránka na stiahnutie | — |

Zrušené medzibuildy: iOS 7 a 8 (TestFlight, prekonané 9), web b39 (nahradený b40), **macOS b39 zmazaný** — mal prázdny
`webapp.asar` (chyba lokálneho skriptu, nikdy nezverejnený). GitHub Actions v dávke: 5 zo 6 povolených behov
(psst lab push 06:55, iOS release 7, 8, 9, iOS unit tests). Web, desktop a Android sa stavali na tomto Macu (D110).

## 1. LoRa v ostrej psst pre iOS (D99)

Port z psst lab: anténa na domovskej obrazovke, „Prepojiť s LoRa“ v detaile priameho rozhovoru, karta cez
šifrovanú správu, ~140 textov EN/SK, `NSBluetoothAlwaysUsageDescription` pravdivo, bez režimu bluetooth-central na
pozadí. V IPA overené, že sa nestratili push, rozšírenia, hovory (voip), poloha, miznúce správy a ochrana obrazovky.

## 2. LoRa v Androide (D100) a kompatibilita (D101)

- `libraries/psstmesh` (JVM, 61 testov) + `features/lora`; BouncyCastle 1.85; kľúč v Keystore AES-GCM.
- Povolenia: BLUETOOTH_SCAN (neverForLocation), BLUETOOTH_CONNECT, legacy ≤ 30; `check-manifest.py` ich stráži.
- **Spoločné vektory** `psst-lora-vectors-v1.json`: Swift 38 testov, JVM 61 testov — rovnaké bajty.
- **Cez Heltec (/dev/cu.usbserial-0001 → !ea251718):**
  - Android → iOS: JVM poslal 1- a 3-rámcovú správu, všetky rámce ACK, `psst-mesh decode` PASS.
  - iOS → Android: Swift poslal 1- a 3-rámcovú správu, `gradlew :libraries:psstmesh:decodeFrames` PASS.
  - V prvom behu Swiftu 3-rámcová správa bez ACK (rádio), opakovanie hneď PASS. Rádio ani MQTT sa nemenili.
- Chýba oproti iOS: lokálne upozornenie na LoRa správu na pozadí.

## 3. Odkazy psst.pro namiesto matrix.to (D111)

- **Formát:** `https://psst.pro/u/@meno:psst.pro`, `https://psst.pro/r/%23alias:psst.pro`,
  `https://psst.pro/r/!id:psst.pro?via=psst.pro`, správa `…/r/<miestnosť>/$udalosť`.
- **Pozvánka:** SK „Ahoj, porozprávajme sa na psst: <odkaz>“, EN „Hi, let's talk on psst: <link>“.
- **AASA a assetlinks** na psst.pro a www.psst.pro: 200, `application/json`, bez presmerovania. assetlinks presne
  zadaný obsah (upload kľúč = ten istý kľúč, iný neexistuje). Apple CDN (`app-site-association.cdn-apple.com`) vracia
  nový AASA; Google Digital Asset Links API potvrdzuje odtlačok.
- **Open Graph:** stránka `/u/…` a `/r/…` vracia og:title/description/image (1200×630 `og-link.png`) a twitter:card
  pre roboty Facebook/WhatsApp, Telegram, Twitter a iMessage; bez matrix.to, bez externých skriptov, `noindex`.
- **Overenie v appkách:**
  - Android b59 (release kľúč) na emulátore Android 14: `pm get-app-links` → psst.pro, www.psst.pro, app.psst.pro
    **verified**; `https://psst.pro/u/@…` otvorí profil, `/r/!…?via=` otvorí miestnosť, pill psst.pro aj starý
    matrix.to v správe otvorí profil; Share = `https://psst.pro/u/@…`; „Invite people to psst“ = „Hi, let's talk
    on psst: https://psst.pro/u/@…“.
  - Web b40 naživo: Share profile = `https://psst.pro/u/@…`, kopírovaná pozvánka „Hi, let's talk on psst: …“,
    psst.pro aj matrix.to v správe = pill a otvorí profil v klientovi (bez novej karty).
  - iOS: CI unit testy (1505, nové testy odkazov prešli; 5 suít padá rovnako ako pred zmenou — chýbajúce LFS médiá),
    PsstLinks 32 testov lokálne, entitlementy a texty v IPA. **Otvorenie universal linku na zariadení neoverené.**
- **Výnimka:** v HTML zmienky z editora formátovaného textu (iOS, Android wysiwyg) ostáva matrix.to — editor inak
  zmienku nerozpozná a označený človek by nedostal upozornenie (D111). Používateľ ho nevidí.
- **Staré matrix.to mimo appky** (napr. vo WhatsAppe) otvorí web matrix.to ako doteraz (upstream nemá https filter
  pre matrix.to); v appke sa otvárajú.

## 4. Upratovanie (D102–D109)

- macet.eu: v kóde ani na serveri nie je; DNS na zmazanie (API token nie je) — chat, app, call, push, psst, ntfy
  `.macet.eu` A 204.168.160.131. Nemazať koreň, www, fx, zakazky, wildcard.
- © 2026 GT: psst.pro, web/desktop, macOS metadáta, Android O aplikácii, iOS Právne informácie, App Store pole.
- Slovenčina: web/desktop 380 textov, MAS 342 textov (nasadené), Android ~290 (vrátane „Noví členovia vidia históriu“).
- Android: upozornenie živej polohy otvorí miestnosť; návod na batériu podľa Androidu 14/15; **R8 obfuskácia ostala
  zapnutá** (keep pravidlá, overené na API 34 a 35); natívne symboly v AAB nie sú (Mac nemá NDK, .so sú stripnuté).
- Variant fdroid sa nezostaví (pre psst nepoužívaný) — na ďalšiu verziu.

## 5. Server

Zálohy pred každou zmenou v `server/backups/`: `{synapse,mas,config}-pre-d99-20261128T0903Z`,
`app-web-pre-d99-20261128T0913Z`, `{synapse,mas,config}-pre-d111-20261128T1153Z`, `app-web-pre-d111-20261128T1234Z`,
`config-pre-d111b-20261128T1328Z` (len nginx — pri tejto poslednej malej zmene databázy zálohované neboli, zmena sa
ich netýka). Po zmenách: prihlásenie, správa medzi účtami, registrácia s hCaptcha (SK/EN), hovory (rtc foci, lk-jwt,
Element Call), healthcheck — OK. Len reload nginx, reštart kontajnera MAS (ráno); žiadny apt, reboot ani docker
daemon. Chránené účty gg, psstadmin, review, review-partner, milan — aktívne, miestnosti zachované.

**Incident:** `sign-release.sh` po podpise b59 automaticky nahral arm64 APK na app.psst.pro/download (13:22:47 UTC).
O 13:26 UTC vrátené b58 (súbor z lokálnej kópie, SHA-256 `f656f6b4…` zhodný); v logoch nginx si b59 nestiahlo žiadne
zariadenie. Skript teraz nahráva len s `PSST_UPLOAD_DOWNLOAD_PAGE=1`.

Dočasné účty qa-d99a–h deaktivované, ich 11 miestností zmazaných. Heslá qa-d99a a qa-d99c sa pri testoch na
emulátore dostali do prepisu agenta (pole Username) — účty sú deaktivované.

## 6. Čo vyplniť ručne

**App Store Connect (26.11.2):** vybrať build **9**; What's New EN/SK z `appstore-listing/26.11.2/WHATS-NEW-*.txt`;
do App Review Notes doplniť `APP-REVIEW-NOTE-LORA.txt`; pole Copyright `2026 GT`; odoslať na kontrolu.

**Play Console:** nič neposielať, kým beží kontrola b54. Od decembra 2026 (povinné 27. 1. 2027) vyplniť deklaráciu
presnej polohy podľa `play-listing/DECLARATIONS.md` §4. Data safety bez zmeny (`play-listing/FORMS.md` §7).
Bluetooth deklaráciu nevyžaduje. Pri nahratí b59 do Play: App Links fungujú len ak Play podpisuje kľúčom 3A:64…
(PEPK zip, `play-listing/FACTS.md`).

**DNS (Webglobe):** zmazať 6 A záznamov `*.macet.eu` vyššie.
