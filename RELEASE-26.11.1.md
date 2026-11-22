# psst 26.11.1 — vydanie (dávka 27, D94–D98)

Stav k 22. 11. 2026. Rozsah potvrdil majiteľ: body 1, 3, 4 a základ bodu 2 (miznúce správy bez mazania lokálnej DB,
indexov a príloh v šifrovaných rozhovoroch — ďalšia etapa, D95).

## Buildy

| Platforma | Build | Kde | Kontrola |
|---|---|---|---|
| Android | **26.11.1-b58** (versionCode 210000582) | APK arm64, armv7 a AAB na app.psst.pro/download (SHA-256 overené); AAB + x86_64 aj v `dist/android/` | check-manifest OK, search-gate 5/5 |
| iOS | **26.11.1 (6)** | TestFlight, interná skupina „psst“ (VALID); IPA `dist/ios/psst-ios-20261121-b6.ipa` | brána verejného Xcode: 27B52 / SDK 24B8118 OK; v IPA len en, en-US, sk |
| Web | **1.12.35-b38** | app.psst.pro (nasadené) | smoke OK (mapa cez proxy psst) |
| Desktop | **b38** (macOS DMG, Windows MSI) | app.psst.pro/download | Gatekeeper v CI OK |
| Server | Synapse retention + mapová proxy `/maps/` | ubuntu-tt | zálohy pred zmenou: `backups/{synapse,mas}-pre-d95-20261121T2042Z.dump` |

Do Play Console ani App Store Connect sa nič neposielalo okrem buildu iOS do TestFlightu. Odoslanie na kontrolu robí
majiteľ (odpovede nižšie).

## 1. Zvyšky Element (D94, D98)

- Zoznamy všetkých nájdených miest a čo sa s nimi stalo: `forks/android/PSST-ELEMENT-REMNANTS.md`,
  `forks/ios/PSST-ELEMENT-REMNANTS.md`, `forks/web/PSST-ELEMENT-REMNANTS.md`.
- Android: prepisy v app module (hovor, notifikačné zvuky, Bluetooth, starý hovor, názov zariadenia „psst Android“).
  iOS: InfoPlist texty (kamera, mikrofón, poloha, Face ID), pomocník → psst.pro/support. Web/desktop: názov značky,
  odkazy, texty hovorov.
- **D98 (nové):** Android aj iOS dodávali ~40 jazykov, ktorých preklady stále hovorili „Element X“ a nemali texty
  psst. Appky sú teraz len **slovenské a anglické** (Android `localeFilters` en, sk; iOS ostatné `.lproj`
  odstránené). Telefón v inom jazyku dostane angličtinu.
- Názov pri zdieľaní obrazovky / systémových dialógoch: Android `application-label` = „psst“ (aj sk); iOS
  `CFBundleDisplayName` = „psst“ v appke aj v rozšíreniach (NSE, Share). Appka na iOS nemá vysielacie rozšírenie,
  takže pri zdieľaní obrazovky systém ukáže názov appky.
- Ostalo (zámerne): licenčný text „upravená verzia Element…“ v O aplikácii; nedosiahnuteľné texty Element Pro /
  Element Classic; vývojárske nastavenia; názvy tried a balíkov (nie sú viditeľné).

## 2. Miznúce správy — základ (D95)

- Stav `m.room.retention` {max_lifetime}; voľby Vypnuté / 5 minút / 1 hodina / 1 deň / 1 týždeň v detaile
  rozhovoru (Android, iOS, web, desktop). Server Synapse: retention 5 min – 1 týždeň, čistenie každých 5 minút.
- Appky skrývajú expirované správy priebežne (Android 5 s, iOS 15 s, web js-sdk), aj bez spojenia.
- Text v časovej osi: „X zapína miznúce správy: 5 minút“ / „X vypína miznúce správy“.
- Oprava počas overovania: Rust SDK hlási udalosť ako `org.matrix.msc1763.retention` a Android vyraďoval všetky
  vlastné stavové udalosti — v b56 / iOS b5 sa preto namiesto textu ukazovalo „Custom event …“ a zmena ochrany
  obrazovky sa nezobrazila vôbec. Opravené v Android b58 a iOS b6 (+ unit testy).
- **Nie v tejto verzii:** mazanie z lokálnej DB a vyhľadávacieho indexu (Element X), z indexu desktopu (Seshat),
  mazanie príloh v šifrovaných rozhovoroch na serveri. Synapse nemaže stavové udalosti ani poslednú udalosť
  miestnosti (appky ju skryjú).

## 3. Ochrana obrazovky (D96)

- Stav `eu.macet.psst.screen_protection` {enabled}, prepínač „Ochrana obrazovky“ s pravdivým vysvetlením.
- Android: FLAG_SECURE v chránenom rozhovore (aj detail a médiá), Android 14+ ScreenCaptureCallback → upozornenie.
- iOS: prekrytie logom psst pri nahrávaní/zrkadlení (`sceneCaptureState`) a v prepínači appiek; pri snímke
  upozornenie do rozhovoru. Len verejné API — žiadna vrstva isSecureTextEntry (App Review 2.5.1).
- Desktop: `BrowserWindow.setContentProtection(true)` počas chráneného rozhovoru. Web: len upozornenie, že na webe
  sa to zablokovať nedá.
- Upozornenie o snímke: `m.notice` „📸 X urobil(a) snímku obrazovky“ + `eu.macet.psst.screenshot: true`, max. 1 za 10 s.

## 4. Poloha (D97)

- „Poslať polohu“ a „Zdieľať polohu naživo“ na 15 min alebo 1 h; ukončiť sa dá kedykoľvek, po čase sa vypne samo.
- Mapy OpenFreeMap (OpenStreetMap, bez kľúča, nie reklamná firma) cez proxy `app.psst.pro/maps/` — poskytovateľ
  máp vidí len IP servera psst. Náhľady sa vykresľujú v zariadení. Atribúcia „© OpenMapTiles © OpenStreetMap
  contributors“.
- Android: len ACCESS_FINE/COARSE_LOCATION a FOREGROUND_SERVICE_LOCATION; ACCESS_BACKGROUND_LOCATION zakázané
  v `check-manifest.py`. iOS: len „When In Use“ (kľúč „Always“ odstránený).
- Povolenie až pri prvom použití, s textom „psst použije vašu polohu, len keď ju sami pošlete…“.
- /privacy (SK aj EN) doplnené o polohu, mapy, miznúce správy a ochranu obrazovky; účinnosť 22. 11. 2026.

## 5. Overenie

### Overené

| Čo | Kde | Výsledok |
|---|---|---|
| Server maže expirované správy | ubuntu-tt, 5-min retention | správa zmizla z DB po 510 s |
| Web: text miznúcich správ, text ochrany, upozornenie o snímke, správa pred limitom viditeľná, poloha s mapou cez proxy, atribúcia OSM, správa po 5 min preč | Chromium sk-SK, 2 dočasné účty | 7/7 PASS |
| Android: nastavenia v detaile („Disappearing messages: 5 minutes“, „Screen protection“ + vysvetlenie) | emulátor Android 15, b56 | OK |
| Android: snímka chráneného rozhovoru aj jeho detailu je **čierna** (FLAG_SECURE); zoznam rozhovorov nie | `adb exec-out screencap` | OK |
| Android: správa od druhého účtu zmizla po 5 min | qa-d94a → qa-d94e | OK |
| Android: povolenie polohy — systém ponúka len „Pri používaní“ / „Iba tentoraz“, nie „Vždy“; najprv text psst | emulátor | OK |
| Android: poslanie polohy (mapa OpenFreeMap, atribúcia) | `adb emu geo fix` | OK |
| Android: živé zdieľanie 15 min — služba v popredí typu location (0x8), lišta „Stop“, `beacon_info` live, timeout 900000; po 15 min samo skončilo (`live: false`, služba preč) | emulátor + server | OK |
| Android: poslané polohy podliehajú miznúcim správam (po 5 min skryté) | emulátor | OK |
| Android **b58**: texty v časovej osi EN „QA Alica turned on disappearing messages: 5 minutes“, „… turned off …“, „… turned on / off screen protection“ a SK „QA Alica zapína miznúce správy: 5 minút“, „… vypína miznúce správy“, „… zapína / vypína ochranu obrazovky“ | emulátor, 2. dočasný účet qa-d94f | OK |
| Android b58: po vypnutí ochrany v rozhovore sa snímka hneď dá urobiť (nie je čierna) | emulátor | OK |
| Android b58: v APK len jazyky predvolený (EN) + sk; povolenia FINE/COARSE/FGS_LOCATION/DETECT_SCREEN_CAPTURE, bez BACKGROUND | aapt2 | OK |
| Android b58: vyhľadávanie (search-gate D84) — 5/5 dopytov | emulátor Android 14 | OK |
| Video k deklarácii FGS location nahraté a nasadené: https://psst.pro/video/psst-live-location.mp4 (2:36, SHA-256 overený cez HTTPS) | emulátor b58 | OK |
| iOS: build verejným Xcode, názov psst, verzia 26.11.1 (6), len SK/EN | IPA b6 | OK |
| iOS unit testy (verejný Xcode): psst testy (mapy, retention, typy udalostí, lokalizácia sk) prešli | CI run 44962883766 | psst OK; padajú len staré sady upstreamu (médiá bez LFS súborov, Analytics, ServerSelection, StartChat…) — rovnaké ako pred zmenou |

### Neoverené (treba na zariadení / pri ďalšej príležitosti)

- **iOS v simulátore nič z UI** (prekrytie pri nahrávaní, upozornenie pri snímke, prepínač appiek, poloha): stav
  nahrávania obrazovky sa v simulátore nedá vyvolať a prihlásenie MAS v simulátore v tejto dávke neprešlo. Overiť
  na iPhone z TestFlightu (b6): Ovládacie centrum → Nahrávanie obrazovky v chránenom rozhovore → logo psst;
  snímka → v rozhovore „📸 … urobil(a) snímku obrazovky“; poloha → povolenie „Pri používaní“.
- Android upozornenie o snímke (ScreenCaptureCallback): pri FLAG_SECURE sa snímka nedá urobiť, v emulátore sa
  callback nevyvolá.
- Názov „psst“ v dialógu zdieľania obrazovky počas hovoru: overené len staticky (label APK / názov v IPA), hovor so
  zdieľaním sa nespúšťal.
- Desktop: setContentProtection a poloha v appke (kód + testy web 891/891, nie ručne).
- iOS: texty v časovej osi po oprave (b6) — len unit test (`psstStateEventTypes`), nie na obrazovke.

### Drobnosti zistené pri overovaní (neopravené)

- Android SK: v hlavičke rozhovoru ostáva nepreložený upstream text „New members see history“.
- Android: ťuknutie na trvalé upozornenie živého zdieľania appku neotvorí (zastaviť sa dá v rozhovore tlačidlom
  Stop; text deklarácie §2d je podľa toho upravený).
- search-gate na emulátore Android 15 (psst35) vyplní MAS formulár na zlých súradniciach; na predvolenom psst34
  (Android 14) prejde — pred podpisom nemá bežať iný emulátor.

### Dočasné účty

qa-d94a … qa-d94f — deaktivované (`PSST_QA_PREFIX=qa-d94 scripts/audit/cleanup.sh`: 6 účtov, 10 testovacích
miestností zmazaných, zostáva 0 aktívnych); qa-sg* zo search-gate zmazal gate sám (kontrola: 0).
Účty gg, psstadmin, review, review-partner, milan a ich miestnosti sa nemenili.

## 6. Čo zmeniť v Play Console (robí majiteľ)

1. **App content → Data safety → Edit:**
   - Data types → **Location**: zaškrtnúť **Approximate location** aj **Precise location**.
   - Pre obe: *Is this data collected, shared, or both?* → **Collected** (nie Shared).
     *Is this data processed ephemerally?* → **No**.
     *Is this data required for your app, or can users choose whether it's collected?* → **Users can choose
     whether this data is collected** (Optional).
     *Why is this user data collected?* → **App functionality** (nič iné).
   - Ostatné odpovede bez zmeny. Dôvod a zdroj: `play-listing/FORMS.md` („Poloha … prečo collected“).
2. **App content → Content rating → Edit questionnaire:** *Can users share their current physical location with
   other users?* → **Yes**. Ostatné bez zmeny (rating sa nemá meniť).
3. **App content → Foreground service permissions:** pridať **FOREGROUND_SERVICE_LOCATION** — use case
   „Other“ (Location sharing), popis, dopady a video podľa `play-listing/DECLARATIONS.md` §2d.
4. **Location permissions** (prístup na pozadí): **netýka sa** — appka ACCESS_BACKGROUND_LOCATION nežiada; ak
   sa Play Console spýta, odpoveď „No“.
5. Release: nahrať AAB `dist/android/psst-android-20261121-b58.aab` (je aj na app.psst.pro/download), poznámka
   k vydaniu (SK/EN) podľa tohto súboru.

## 7. Čo zmeniť v App Store Connect (robí majiteľ)

1. **App Privacy → Edit → Data Types:** pridať **Location → Precise Location**.
   - *Purpose:* **App Functionality** (nič iné).
   - *Is this data linked to the user's identity?* → **Yes**.
   - *Do you or your third-party partners use this data for tracking?* → **No**.
   - Coarse Location nepridávať. Ostatné bez zmeny. Dôvod: `appstore-listing/FORMS.md` („Poloha (26.11.1, D97)“).
2. Pri odoslaní verzie 26.11.1 vybrať build **6**. Privacy Policy URL je už https://psst.pro/privacy.
3. Age Rating: bez zmeny (Apple sa na polohu nepýta).
