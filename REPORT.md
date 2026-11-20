# psst — dávka 21 (2026-11-20): otvorená registrácia s hCaptcha, bez pozvánok, hľadanie podľa presného mena

Plný detail: **REGISTRATION-DONE.md**, rozhodnutia DECISIONS.md **D88**.

- Registrácia otvorená pre každého od 18 rokov (MAS 1.29: hCaptcha, limit 3 + 1/21 min na IP, povinné políčko
  „Mám aspoň 18 rokov a súhlasím s Podmienkami používania“); bez platného tokenu hCaptcha server odmietne.
- Pozvánky zrušené (admin, skripty, 10 tokenov zneplatnených); adresár používateľov vypnutý; krátke „meno“ aj plné
  „@meno:psst.pro“ fungujú na webe, macOS desktope, Androide aj iOS (overené, žiadosti o chat dorazili).
- Texty: psst.pro, /privacy (hCaptcha ako sprostredkovateľ), /terms, /support, /download, obchody, poznámky pre
  kontrolórov. hCaptcha pridáva jednu položku v Play Data safety aj v Apple App Privacy.
- Buildy: Android **b54**, iOS **b3** (TestFlight), web + desktop **b36** (macOS notarizovaný). Brány a CI zelené.
- Neoverené: dokončenie registrácie s hCaptcha na produkcii (MAS odmieta testovacie kľúče), Windows, reálne telefóny.

---

# psst — nočný beh 2026-11-19/20 (dávka 20): príprava na Google Play a App Store

**Nič sa nezaseklo na veci mimo môjho dosahu.** Do Play Console ani App Store Connect som nič neposlal, okrem iOS
buildu b2 do TestFlightu. Rozhodnutia sú v DECISIONS.md D87.

1. **Kontakt psst@psst.pro (MACET, s.r.o., IČO 35953781)** je všade: Zásady, Podmienky, /download, web a desktop
   (Help & About), Android aj iOS (O aplikácii) a MAS. Let's Encrypt účet má tiež psst@psst.pro. Úvodná
   psst.pro je bez mena, pod „Powered by GT“ má len Súkromie a Podmienky.
2. **Stránky psst.pro/privacy, /terms a /support**, každá SK aj EN na jednej URL. Pokrývajú údaje, E2EE a čo
   vidí server, EÚ, FCM/APNs, uchovávanie, zálohy 6 mesiacov, práva, 18+, pozvánky a nesľubujú anonymitu.
3. **psst.pro/delete-account:** postup v appke aj na webe, e-mail bez prihlásenia, čo sa zmaže a čo ostane.
4. **Android povolenia:** odstránené inštalácia balíkov, poloha (aj kód) a výnimka z batérie.
   - **Batéria — rozhodnutie odstrániť.** Zdroj: developer.android.com/training/monitoring-device-state/doze-standby#exemption-cases,
     riadok „Instant messaging, chat, or calling app … Yes, using FCM → Not Acceptable“; odkazuje naň politika
     Play Device and Network Abuse.
   - Krok batérie ukáže návod a otvorí App info. Overené: Allow background usage → Unrestricted.
   - `check-manifest.py` zlyhá pri návrate ktoréhokoľvek z nich alebo AD_ID.
   - Vyhlásenia sú v `play-listing/DECLARATIONS.md`, videá na psst.pro/video/….
   - Overené na b51: zvuk, rozsvietenie, hovor na celú obrazovku, hovor na pozadí, vyhľadávanie (PASS), QR
     prihlásenie, QR overenie, inštalácia cez b47.
5. **Nahlásenia na app.psst.pro/admin:** kto, koho/čo, dôvod, kedy; vybavené/nevybavené; akcie Zablokovať a
   Zmazať obsah; audit log. Obsah správ admin nevidí.
   - Overené naostro z webu, Androidu a iOS (simulátor): správa aj miestnosť.
   - Používateľa nahlásiť v appkách nejde (len cez API), stránky to tak aj píšu.
6. **Účty review a review-partner:** nie sú admin, majú šifrovanú DM, skupinu a kľúč na obnovenie. Údaje a
   návod sú v ~/proj/psst-review.txt (600). Tieto dva účty ostali aktívne.
7. **Podklady pre Play:** FACTS, FORMS, DECLARATIONS, texty EN/SK; ikona a feature grafika sú pôvodné, snímky z
   b47 (UI je rovnaké).
   **Podklady pre App Store:** texty, FORMS, APP-REVIEW-NOTES; snímky 1320×2868, 1206×2622 a iPad 2064×2752.
8. **PEPK:** encryption_public_key.pem existoval. Zip je hotový, certifikát 3A:64…:38:99 sedí s APK.
9. **Buildy:**
   - Android **b51** (APK arm64, armv7, AAB): na /download aj v dist/android;
   - iOS **b2** v TestFlighte (VALID);
   - web a desktop **b32**, a **b33** spustený omylom zmenou testovacieho skriptu (rovnaký obsah), macOS
     Gatekeeper PASS;
   - /download sedí s release/latest.json.

**Konečné povolenia b51:** INTERNET, ACCESS_NETWORK_STATE, ACCESS_LOCAL_NETWORK, POST_NOTIFICATIONS,
c2dm.RECEIVE, WAKE_LOCK, TURN_SCREEN_ON, USE_FULL_SCREEN_INTENT, VIBRATE, RECORD_AUDIO, CAMERA,
MODIFY_AUDIO_SETTINGS, FOREGROUND_SERVICE (+_MICROPHONE, _CAMERA), RECEIVE_BOOT_COMPLETED, USE_BIOMETRIC,
USE_FINGERPRINT, DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION (interné).

**Neoverené:**
- Zmazanie účtu na iOS som nedokončil. Cesta Nastavenia → Manage account & devices → stránka účtu s „Delete
  account“ je overená, samotné zmazanie je ten istý MAS, overený v D86.
- Desktop odkazy som v appke neotváral (config je rovnaký ako na webe).
- Fyzické telefóny som netestoval, všetko bežalo v emulátore a simulátore.

**Pre teba:**
- Prečítaj FORMS.md (Play aj App Store) a vyplň formuláre. Heslá a kľúč na obnovenie vlož z psst-review.txt.
  V App Store Connect prepíš Privacy URL na psst.pro/privacy.
- V Play nahraj psst-signing-key.zip (App integrity → App signing).
- Over na iPhone TestFlight b2 a na Samsungu b51: krok batérie, upozornenia a hovor.
- Nahlásenia vybavuj do 24 h, ako sľubujú Podmienky.
- V ďalšom builde doplniť do návodu batérie medzikrok „Allow background usage“.

# PSST — report (2026-11-19, dávka 19: macOS Developer ID, iOS TestFlight, podklady pre Google Play)

**Všetky tri časti sú hotové, nič sa nezaseklo.** Podrobnosti sú v DECISIONS.md D86.

**A) macOS:**
- Certifikát patrí ku kľúču `devid.key`. Je to Developer ID Application, tím MHV67VMY8T, platný do 2027-12-19.
- Prvý podpísaný build je **b31**, notarizovaný a stapled.
- Gatekeeper:
  - čistý runner v CI: 7/7 PASS (spctl install/open/exec, codesign --deep --strict, stapler DMG aj appka);
  - lokálne na stiahnutom DMG s karanténou: „accepted, source=Notarized Developer ID“;
  - appka sa spustí a prihlási 6/6.
- Na /download je b31 a návod „Napriek tomu otvoriť“ zmizol.
- Pri aktualizácii z nepodpísanej verzie macOS raz vypýta prístup ku kľúčenke „psst Safe Storage“ → **Vždy
  povoliť**. Pri zamietnutí appka reláciu neobnoví, dáta však nezmaže. Overené z kódu, nie naostro (D86).

**B) iOS:**
- TestFlight build **b1**: spracovanie VALID, interná skupina „psst“ s testerom Geo M, export compliance
  výnimka.
- Na ploche „psst“, APNs production, applinks na app.psst.pro.
- Sygnal má `eu.macet.psst.ios.prod` v produkcii a Apple kľúč prijal (skúšobný push vrátil `BadDeviceToken`).

**C) Google Play:**
- `play-listing/`: texty EN/SK, ikona 512, feature 1024×500 a 5 snímok. Do konzoly som nič nenahral.
- `FACTS.md`:
  - AD_ID v manifeste nie je, reklamné ID sa nepoužíva;
  - targetSdk 37, 16 KB OK (arm64/x86_64), stiahnutie ~66 MB;
  - AAB je podpísaný kľúčom z ~/psst-keys; postup PEPK je pripravený.
- Zmazanie účtu funguje v appke aj na webe (MAS → Delete account, overené naostro, erased_users).
- **Chýba:**
  - verejná stránka s postupom zmazania;
  - odstránenie alebo zdôvodnenie povolení REQUEST_INSTALL_PACKAGES, polohy a výnimky z batérie;
  - zobrazenie nahlásení na admin stránke.

**Upratanie:** testovacie účty sú deaktivované (aj qa-ps-* zo snímok). Aktívni sú len geo a psstadmin, miestnosti
0. Matica funkcií: ✅ 261 · ❌ 2 · 🟠 2 · ⚪ 84.

# PSST — report (2026-11-19, dávka 18: presun na psst.pro, založené načisto)

**Výsledok:** psst beží na **psst.pro** (D85). Server_name je `psst.pro`, ID majú tvar `@meno:psst.pro`.
- homeserver a MAS: chat.psst.pro;
- web, `/download`, `/admin`: app.psst.pro;
- hovory a TURN/TLS na 443: call.psst.pro;
- úvodná stránka a `.well-known`: psst.pro; www presmeruje na psst.pro.

Databáza, podpisový kľúč a tajomstvá sú nové. Staré adresy na macet.eu sú vypnuté.

**Upozornenia na začiatok:**
- DNS je v poriadku: všetkých 5 A záznamov ukazuje na 204.168.160.131, žiadny AAAA, CAA nie je (LE povolený).
- **Fyzický Samsung A05 nebol pripojený** (`adb devices` prázdne), Android je overený len v emulátoroch
  (Android 14 a 15).

**Server:**
- Posledná šifrovaná záloha starého stavu je v `/opt/psst/archive-macet-final/`. Overené: SHA-256, dešifrovanie a
  rozbalenie, `pg_restore --list` (177 a 34 tabuliek), podpisový kľúč, 749 médií. Je mimo rotácie, zmazať po
  2026-12-19.
- Až potom sa starý stack zastavil a jeho adresár (dáta, certifikáty, vhosty, staré zálohy a buildy) sa zmazal.
- Nový stack je nasadený cez `deploy.sh 204.168.160.131 none …`.
  - Jeden LE certifikát pre 5 názvov, platí do 2027-02-17, automatická obnova.
  - Federácia vypnutá (`m.server` → chat.psst.pro:8448, zvonka zatvorený).
  - Registrácia len pozvánkou. Kontakt na stránkach Podmienky/Súkromie je @geo:psst.pro.
- Účty: `geo` (admin) a servisný `psstadmin`. Heslá sú v `~/proj/psst-admin.txt` (600). Pozvánky sa nevytvorili.
  V iCloude žiadna kópia nie je.
- Zálohy: denný cron. Skúšobná obnova naostro do dočasného prostredia (`scripts/restore-test.sh`): kľúč, 49 účtov,
  509 udalostí, 28 miestností a 5 pozvánok sa zhodujú, obnovený Synapse naštartoval.
- Neznáme názvy nedostanú TLS ani HTTP odpoveď. Overené zvonka pre chat, app, call, push, psst a ntfy.macet.eu.

**Appky:**
- Vo všetkých forkoch: homeserver, server_name, App Links / Associated Domains, push gateway, kontrola verzie a
  právne odkazy. OAuth schéma callbacku je `pro.psst.app`.
- Android má jediný provider „psst.pro“ (Managed, priamo na chat.psst.pro). `AppMigration11` po aktualizácii
  zmaže reláciu starého servera.
- Web a desktop zahodia uloženú reláciu iného homeservera (unit testy 49/49). Unit test Android migrácie je
  napísaný, lokálne ho Gradle nespustil (nedostupný plugin); správanie overila skutočná aktualizácia v emulátore.
- Buildy:
  - **Android b47** (arm64, armv7, x86_64, AAB): kontrola manifestu OK, kontrola vyhľadávania PASS 8/8;
  - **Windows/macOS/web b30** (b29 bol rovnaký kód, otestovaný auditmi);
  - iOS fork upravený, v simulátore v CI audit 20 ok / 0 fail / 2 nedá sa. TestFlight čaká na Apple.
- Stránka /download ukazuje len b47 a b30, `check-download-page.py` OK. Je na nej aj poznámka pre pôvodných
  používateľov.

**Aktualizácia zo starej appky (bod 11):**
- **Android b44**, prihlásená na starom serveri a visiaca na „Offline / Server unreachable“, → b47: bez pádu, hneď
  „Sign in to psst.pro“.
- **macOS b27** (profil s reláciou starého servera) → b29: prihlasovacia obrazovka psst.pro, potom prihlásenie
  @qa:psst.pro 6/6.
- Windows rovnaký kód; lokálne neoverené.
- Staré buildy o novej verzii samy nevedia, preto treba členov upozorniť.

**Testy na psst.pro:**
- server `prod_test.py` 29/29 (vrátane zamietnutej federácie a verejnej registrácie), server-smoke v CI 17/17;
- admin stránka 28/28;
- web audit 39/39 (registrácia pozvánkou, E2EE, súbory, skupina, kanál, hovory);
- Web Push 8/8;
- desktop audit Windows 43/43 a macOS 43/43;
- hovor len cez TURN/TLS 443: 6/6 (relayProtocol tls);
- Android (emulátor):
  - registrácia pozvánkou;
  - upozornenie so zvukom a vibráciou;
  - rozsvietenie za 3 s (Android 15 po povolení);
  - hovor na celú obrazovku za 3 s;
  - QR prihlásenie z webu;
  - QR overenie s webom;
  - budíček ~1 s;
  - vyhľadávanie 8/8;
- zvonka:
  - TLS 1.2/1.3, TLS 1.0/1.1 odmietnuté, hlavičky HSTS/nosniff/CSP;
  - otvorené TCP len 22, 80, 443, 7881 (UDP 7882 prenáša médiá);
  - healthcheck OK.

**Upratanie:** testovacie účty (45) deaktivované, ich miestnosti (30) zmazané. Aktívni sú len geo a psstadmin,
miestnosti 0, platné pozvánky 0. Matica funkcií má 339 buniek: ✅ 255 · ❌ 2 · 🟠 2 · ⚪ 80.

**Úplnosť (bod 12):** „macet.eu“ už nie je v repozitároch (okrem histórie v DECISIONS.md a REPORT.md), v
konfigurácii servera, vo webe, MSI, DMG ani ZIP.
- **Výnimka:** podpisový certifikát Android APK/AAB má `O=macet.eu`. Kľúč sa meniť nesmie, inak by nová verzia
  nešla nainštalovať cez starú.


# PSST — report (2026-11-18, dávka 17: vyhľadávanie na Androide — príčina hlásenia, kontrola pred vydaním)

**Výsledok:** vyhľadávanie sa medzi b37 a b42 **nepokazilo**, prvý pokazený build neexistuje. Hlásenie z dávky 16
bolo chybou testu, ktorú podporila zavádzajúca hláška upstreamu (D84). Nový build **b44** je na stránke na
stiahnutie.

**Príčina hlásenia:** test v dávke 16 napísal slovo a čítal obrazovku bez prepnutia na kartu **Správy**.
- Obrazovka hľadania sa otvára na karte **Konverzácie**, ktorá hľadá len názvy konverzácií.
- Element X na nej pri prázdnom výsledku ukazuje hlášku pre správy („No results in the last 3 months … in your
  recent messages“).
- Na b43 karta Konverzácie ukáže presne texty z dávky 16 (aj poradie prvkov) a karta Správy výsledky.
- QR beh (dávka 15) na Správy prepol a jeho 5/5 bolo správne.

**Overenie po buildoch:** b38–b41 som stiahol z CI a podpísal len na test. Jeden účet prešiel aktualizáciami
b37 → b38 → … → b43. Každý build našiel staré správy aj správu prijatú hneď po aktualizácii. b43 hľadá aj:
- po čistej inštalácii;
- po novom prihlásení s kľúčom na obnovenie;
- po resete identity;
- s prázdnou miestnosťou;
- s obrázkom v šifrovanej miestnosti.

Záplata Rust (`psst_folded`) je v `.so` b37 aj b42.

**Oprava v b44:**
- karta Konverzácie má vlastný prázdny stav „Žiadna konverzácia s týmto názvom“ s tlačidlom „Hľadať v správach“;
- obrazovka hľadania je po slovensky (Localazy ju v SK nemá).

**Deväť bodov D80 na b44** (930 správ: šifrovaná 1:1 320, šifrovaná skupina 310, nešifrovaný kanál 300; webový
partner; počty vypočítané z korpusu):

| Bod | Výsledok |
|---|---|
| 1. Všetky konverzácie | ✅ „cislo“ 56/56, „stastny“ 41/41, „zlty“ 31/31, „dakujem“ 84/84, „cisl“ 86/86 |
| 2. Jedna konverzácia | ✅ skupina „cisl“ 29/29, DM „stastny“ 14/14, kanál „kon“ 56/56 |
| 3. Šifrované aj kanál | ✅ všetky tri typy presne |
| 4. Výsledok | ✅ miestnosť, odosielateľ, čas, zvýraznenie; ťuknutie otvorí najstaršiu správu priamo na nej |
| 5. Diakritika, začiatok slova | ✅ „prada“ → „pradávny“ 3/3; vložený text s diakritikou → presne 1 správa |
| 6. Staršie správy | ✅ najstaršia správa každej miestnosti; po prihlásení dopĺňanie 30 s (CPU 17,7 s) |
| 7. Nové, odoslané, úprava, zmazanie | ✅ prijatá 1, odoslaná z telefónu 1, po úprave nové 1 / staré 0, zmazaná 0 |
| 8. Súkromie | ✅ slová v indexe 0×, na serveri 0 × /search z 14 120 požiadaviek, po odhlásení index zmazaný |
| 9. Rýchlosť | ✅ prvá stránka 2–196 ms, ďalšia 0–363 ms (emulátor; A05 neoverené) |
| Aktualizácia, inštalácia, prihlásenie, reštart | ✅ b37→b44 a b43→b44 56/56, čistá inštalácia 56/56, odhlásenie → prihlásenie 56/56, reštart 56/56 |

**Kontrola pred vydaním (D84):** `scripts/android/search-gate.sh` beží v `sign-release.sh` po kontrole manifestu.
- Čistá inštalácia vydávaného APK v emulátore a nový účet `qa-sg…`.
- Partner (nio, E2EE) pošle 8 známych správ do šifrovanej miestnosti.
- Dopyty na karte Správy:
  - bez diakritiky a začiatkom slova: `cislo` 3, `stastn` 2, `ob` 2, `zlty kon` 1, `dvanast` 2;
  - slovo, ktoré tam nie je: 0;
  - po reštarte prijatá správa: 1 a `cislo` 4.
- Pri nezhode sa build nepodpíše ani nenahrá.
- **b44: PASS 8/8. b29 (pred opravou D80): FAIL 7/8 → nevydané.**
- `search_ui.py` počíta len na karte Správy (overí vybraný segment).

**Bod 5 na b44:**
- ✅ QR Android ↔ web: telefón naskenoval web, krížový podpis potvrdený zo servera.
- ✅ QR Android ↔ Android: A naskenoval B, obe zariadenia overené.
- ✅ Upozornenie so zvukom aj vibráciou.
- ✅ Rozsvietenie displeja za 2 s.
- ✅ Hovor na celú obrazovku pri zhasnutom displeji za 2 s.
- ✅ `check-manifest.py` OK (APK aj AAB).

**Účty na serveri:** aktívnych je 6.
- geo, psstadmin: admin, bez pozvánky.
- jj, ll, ss, mac: bez admina, vznikli pozvánkou.

„9“ v dávke 16 zahŕňalo aj 3 deaktivované registračné testy `reg*`.

**Upratanie:**
- Testovacie účty qa-sw1–3, qa-sg* a ich miestnosti sú zmazané.
- Disk: voľných 11,4 → 56,3 GiB (obsadených 200,9 → 155,0 GiB).
- Zmazané:
  - obraz Play emulátora;
  - nepoužívaný emulátor psst33 s obrazom Android 13;
  - staré medzibuildy;
  - lokálny Gradle build a cache;
  - testovacie kópie.

Matica: 299 buniek — ✅ 227 · ❌ 1 · 🟠 2 · ⚪ 69.

---

# PSST — report (2026-11-17, dávka 16: prezentačná stránka a Play Protect)

## A) Prezentačná stránka — https://psst.macet.eu (D82)

`pst.macet.eu` smeruje na cudzí server, preto `psst.macet.eu` (náš server). Statická stránka SK/EN zo `server/www/`:
hero s dvoma tlačidlami (Stiahnuť aplikáciu → app.macet.eu/download, Prihlásiť sa → app.macet.eu), 6 funkcií,
„Čo server vidí a čo nie“, platformy (iPhone pripravujeme), prístup len na pozvánku, pätička „Powered by GG & TT“.
Snímky z webu a Android emulátora s vymyslenými menami (Eva, Tomáš, Mária) na testovacích účtoch.

| Overenie (zvonka, HTTPS) | Výsledok |
|---|---|
| Certifikát | ✅ Let's Encrypt `psst-web`, platný do 2027-02-15, obnova existujúcim certbotom |
| Jazyk | ✅ sk-SK → /sk/, en-US → /en/, prepínač si voľbu pamätá |
| Tlačidlá | ✅ správne odkazy, viditeľné bez posúvania na 360, 390 a 1440 px, znova na konci |
| Cudzie zdroje | ✅ 0 požiadaviek mimo domény, 0 cookies, 0 chýb CSP |
| Hlavičky, healthcheck | ✅ HSTS, nosniff, no-referrer, DENY, prísne CSP; healthcheck SK + EN + certifikát |
| Bez výpadku | ✅ sonda 954 požiadaviek na app/chat/call/push/download počas nasadenia bez chyby; žiadny kontajner znovu vytvorený |
| Indexovanie | ✅ stránka indexovateľná; prihlásenie (web app, MAS) a /admin `noindex` |
| AGPL | ✅ odkaz „Source code (AGPL-3.0)“ doplnený do pätičky /download (v appke a na webe už bol) |

Zmena `deploy.sh`: pri zmene konfigurácie nginx graceful reload namiesto reštartu, admin sa reštartuje len pri zmene
tajomstiev.

## B) Play Protect blokoval inštaláciu (D83)

**Príčina:** `BIND_NOTIFICATION_LISTENER_SERVICE` — služba `PsstNotificationListener`. Bol to náš kód: voliteľná
časť diagnostiky upozornení (D67). Prvýkrát v **b25** (prvý úspešný b27), v b24 nebola. SMS ani accessibility nikde.

**Zmena:** služba odstránená. Diagnostika namiesto nej vypíše efektívny kanál upozornenia. Žiadna funkcia pre
používateľa nechýba, z diagnostiky ubudli len detaily o tom, ako systém upozornenie zaradil. Štítok aplikácie je
doslovne „psst“. Predtým `@string`, ktorý dialóg pred inštaláciou nevedel načítať, a preto ukázal `ElementXApplication`.

| Bod | Výsledok (b43) |
|---|---|
| Upozornenie so zvukom, rozsvietenie | ✅ displej rozsvietený za 4 s, importance 4, zvuk prehraný |
| Hovor pri zamknutom telefóne | ✅ prichádzajúci hovor na celú obrazovku za 2 s |
| Upozornenia a hovory + diagnostika | ✅ obe obrazovky, bez tlačidla prístupu k upozorneniam |
| Budíček pri žiadosti o overenie | ✅ notifikácia za 1 s pri spiacom telefóne |
| QR overenie | ✅ telefón naskenoval QR z webu → overené, krížovo podpísané na serveri |
| Vyhľadávanie | ❌ žiadne výsledky ani pre novú správu — **rovnako v b42**, nie je to dôsledok D83; otvorené |
| Kontrola manifestu | ✅ `check-manifest.py` v CI (APK + AAB) a pred podpisom; b42 FAIL, b43 OK, aj súbor z /download |
| Reprodukcia | ⚪ emulátor Android 14 s Google Play: Play Protect povolil b42 aj b43 (`response=0`), blok sa nezopakoval |
| Stránka /download | ✅ postup pri hláseniach (prehliadač, neznáme zdroje, Play Protect, Samsung Automatické blokovanie) SK + EN |

**Build:** Android **b43** (26.11.0-b43+2026-11-17) je na stránke na stiahnutie. Matica: 294 buniek — ✅ 220 · ❌ 3 · 🟠 2 · ⚪ 69.

**Testovacie účty:** qa-l1–3 a qa-n1–3 deaktivované, ich miestnosti (8) zmazané; skutočné účty nezmenené.

# PSST — report (2026-11-17, dávka 15: overenie zariadenia QR kódom na Androide)

**Samsung A05 nebol pripojený** (adb: len emulátory). Testované na dvoch emulátoroch Android 14 s kamerou, ktorej
obraz bol QR kód z druhého zariadenia. Rozhodnutie D81, upstream vs. psst: [docs/android-qr-verification.md](docs/android-qr-verification.md).

**Upstream:** Rust crypto a `matrix-sdk` majú štandardné QR overenie hotové. Chýbalo:
- vo FFI pre Kotlin (len emoji, feature `qrcode` vypnutý),
- v obrazovkách Element X.

Navyše nové neoverené zariadenie zahadzovalo žiadosť, ktorú začalo už overené zariadenie.

**Doprogramované:**
- záplata FFI (len doplnky) v spoločnom psst build SDK s vyhľadávaním (`android-rust-sdk-26.11.05-psst3`, AAR z oficiálneho projektu);
- na obrazovkách overenia: náš QR kód, „Naskenovať QR kód“ a vždy „Porovnať emoji“;
- chybové hlášky; povolenie kamery až pri skenovaní;
- žiadosť sa zobrazí aj nad FTUE a FTUE potom pokračuje; texty SK/EN.

| Bod | Výsledok |
|---|---|
| 1. Android skenuje web | ✅ QR z dialógu Element Web → zelený štít → „Device verified“ na oboch stranách |
| 1. Android skenuje desktop | ⚪ netestované: desktop sa prihlasuje cez systémový prehliadač tohto Macu; desktop obsahuje ten istý web b27 |
| 2. Android ↔ Android | ✅ obe role (A ukáže a B skenuje, aj opačne) |
| 3. Oba smery začatia | ✅ začne nový Android; začne nový web a odpovie Android; začne overený web a odpovie nový Android (oprava FTUE) |
| 4. Emoji ako náhrada | ✅ vždy ponúknuté, overenie emoji dokončené; druhá strana len s emoji → rovno emoji |
| 5. Kamera | ✅ povolenie až pri skenovaní; odmietnutie → hláška, Otvoriť nastavenia, emoji |
| 6. Chyby | ✅ cudzí QR, QR iného overenia (nezhoda kľúčov), vypršanie po 10 min, zrušenie druhou stranou |
| 7. Výsledok | ✅ krížový podpis potvrdený zo servera; nové zariadenie dešifruje staršie správy zo zálohy |
| 8. Regresia | ✅ emoji, push budíček pri žiadosti, prihlásenie QR kódom (až po „Access granted“), vyhľadávanie |
| 9. SK/EN | ✅ obe jazykové verzie na emulátoroch |
| Aktualizácia / čistá inštalácia | ✅ b37 → b39 (A), čistá inštalácia (B), b41 → b42 |

**Build:** Android **b42** (26.11.0-b42+2026-11-17) je na stránke na stiahnutie. b38–b41 boli medzibuildy počas testov.
Matica: 285 buniek — ✅ 213 · ❌ 1 · 🟠 2 · ⚪ 69.

**Pozor — účet @mac:** pri pokuse prihlásiť psst desktop sa otvoril Firefox na tomto Macu. V ňom niekto o 15:58 UTC
zaregistroval účet `@mac` pozývacím tokenom z 15. 11. Moja automatizácia Firefox neovláda, preto som účet nechal tak.
Ak ho nepoznáte, deaktivujte ho v administrácii.

**Testovacie účty:** qa-v1, qa-v2 a qa-v3 sú deaktivované a ich miestnosti zmazané. Dočasný druhý emulátor je odstránený.

---

# PSST — report (2026-11-17, dávka 14: vyhľadávanie v správach na Androide)

**Samsung A05 nebol pripojený** (adb: len emulátor). Android testovaný v emulátore Android 14 (Google APIs, x86_64).
Rozhodnutie D80 v DECISIONS.md, čo je upstream a čo náš kód: [docs/android-search.md](docs/android-search.md),
matica [docs/FEATURE-MATRIX.md](docs/FEATURE-MATRIX.md) (sekcia „Android: vyhľadávanie v správach“).

**Čo upstream mal:** celý mechanizmus. Šifrovaný index tantivy pre každú miestnosť v telefóne, indexovanie nových,
odoslaných, upravených aj zmazaných správ, dopĺňanie histórie (~3 mesiace), globálne hľadanie a otvorenie správy.
**Prečo boli výsledky prázdne:** analyzátor len delil slová a hľadal celé slová bez ohľadu na diakritiku. „cislo“
nenašlo „číslo“ a „ob“ nenašlo „obed“ (overené na b29). Históriu navyše indexoval len pri otvorenom hľadaní.

**Čo psst doplnil:**
- záplatu Rust SDK (odstránenie diakritiky a hľadanie podľa začiatku slova) bez zmeny FFI, postavenú v CI
  (`android-rust-sdk.yml`) do oficiálneho AAR;
- jednorazové preindexovanie starého indexu;
- dopĺňanie histórie počas používania appky, najviac raz za deň;
- stiahnutie celej zálohy kľúčov po obnovení, aby sa dala prehľadávať aj história po novom prihlásení;
- úryvok so zvýraznením;
- „Hľadať v konverzácii“ (lupa v hlavičke konverzácie).

Testovacie dáta: šifrovaná 1:1 (320 správ), šifrovaná skupina (310) a verejný kanál (300), slovenské slová
s diakritikou. Očakávané počty sa vypočítali z korpusu.

| Bod | Výsledok |
|---|---|
| 1. Všetky konverzácie | ✅ „cislo“ 56/56, „stastny“ 41/41, „zlty“ 31/31, „dakujem“ 84/84 |
| 2. Jedna konverzácia | ✅ skupina „cisl“ 29/29, DM „stastny“ 14/14, kanál „kon“ 56/56 |
| 3. Šifrované aj kanál | ✅ všetky tri typy úplné |
| 4. Výsledok | ✅ miestnosť, odosielateľ, dátum, zvýraznený úryvok; ťuknutie otvorí správu (aj najstaršiu) |
| 5. Diakritika, začiatok slova | ✅ „cislo“→„číslo“, „cisl“→„čísla“, „prada“→„pradávny“, dopyt s diakritikou funguje |
| 6. Staršie správy | ✅ najstaršia správa každej miestnosti nájdená; dopĺňanie 930 správ za 48–59 s, riadok „Staršie správy sa ešte indexujú“ |
| 7. Nové, odoslané, úprava, zmazanie | ✅ prijatá aj odoslaná správa hneď; úprava → nové znenie, staré nie; zmazaná zmizne |
| 8. Súkromie | ✅ index šifrovaný (slová v súboroch 0×); 0 požiadaviek /search na serveri; po odhlásení zmazaný |
| 9. Rýchlosť | ✅ v emulátore: prvá stránka 250–650 ms, ďalšia 450–750 ms; prvé indexovanie ~36 s CPU, ďalší prechod ~10 s CPU najviac raz za deň; **na A05 neoverené** |
| Reštart, aktualizácia, nové prihlásenie | ✅ po reštarte hneď; aktualizácia b29→b35→b36→b37; odhlásenie → prihlásenie → 56/56 do ~1,5 min |

**Build:** Android **b37** (26.11.0-b37+2026-11-17) je na stránke na stiahnutie, SHA-256 overený.
b30–b36 boli medzibuildy počas vývoja (nezverejnené). Upravené SDK: release `android-rust-sdk-26.11.05-psst1`.

**Obmedzenia:**
- história len ~3 mesiace dozadu (upstream);
- indexuje sa len správa, ktorá sa dá dešifrovať;
- výsledok pre upravenú správu ukazuje čas úpravy;
- hľadanie v konverzácii prechádza globálne výsledky (pri počte miestností v psst rýchle);
- web: šifrované miestnosti naďalej nie (D79).

**Testovacie účty:** qa-s*, qa-t* a qa-u* (9) sú deaktivované, ich miestnosti zmazané a výnimky z limitu správ zrušené.

---

# PSST — report (2026-11-17, dávka 13: nočný beh — upozornenia a hovory na všetkých platformách)

**Samsung A05 nebol pripojený** (adb: len emulátor). Android testovaný v emulátore Android 14 (Google APIs, FCM).
Rozhodnutia D72–D79 v DECISIONS.md, matica [docs/FEATURE-MATRIX.md](docs/FEATURE-MATRIX.md).

| Bod | Výsledok | Overenie |
|---|---|---|
| 1. Obrazovka „Upozornenia a hovory“ | Android b29, web/desktop b27, iOS (fork, simulátor) — prepínače so skutočným stavom, žiadosti za sebou, test upozornenia a zvonenia, samo sa otvorí raz za verziu, ak niečo chýba | Android emulátor; web Playwright 17/17; Windows 18 a macOS 15 kontrol na runneroch; iOS XCUITest |
| 2. Rozsvietenie obrazovky (Android) | predvolene zapnuté; Android 14 nepotrebuje povolenie, Android 15+ „Zapnúť obrazovku“ (TURN_SCREEN_ON) | emulátor 14: displej sa pri správe rozsvietil, v Nerušiť nie; Android 15 neoverený (emulátor príliš pomalý) |
| 3. Sprievodca po aktualizácii | reťaz dialógov nahradená obrazovkou z bodu 1, ktorá si chýbajúce povolenia hneď vyžiada | aktualizácia b28→b29 aj čistá inštalácia: upozornenia → celá obrazovka → batéria |
| 4. Upstream obmedzenia | web: upozornenia pri karte na pozadí/zatvorenej a žiadosť o overenie — vyriešené (Web Push); ostatné nie (odhady v D79) | Chrome na produkcii |
| 5. iOS / macOS | iOS obrazovka + overenie v simulátore OK, TestFlight jedným skriptom; macOS podpis overený suchým behom | run 43972090982, 43962661843 |
| 6. Regresia | 265 buniek: ✅ 191 · ❌ 1 · 🟠 5 · ⚪ 68; pokazený hovor s blokovaným UDP na macOS (b26) opravený v b27 | desktop audit 43962770275 |

**Čaká na Account Holdera GexPay SE:** (1) Developer ID Application certifikát (G2) z `devid.csr` → podpis
a notarizácia macOS sa zapnú samy; (2) záznam appky `eu.macet.psst` v App Store Connect → `scripts/ios/release-testflight.sh`.

**Verzie na stránke:** Android b29, Windows b27, macOS b27 (nepodpísaný + návod), iOS „Coming soon“; web b27.

---

# PSST — report (2026-11-16, dávka 12: chyby z testov na skutočných zariadeniach)

Rozhodnutia: D67 (Samsung notifikácie, diagnostika), D68 (budíček pri overení), D69 (podpis macOS), D70 (nové heslo
v administrácii), D71 (overenie na webe/desktope). Matica: [docs/FEATURE-MATRIX.md](docs/FEATURE-MATRIX.md) (sekcia
„Dávka 12“), porovnanie s upstreamom: [docs/android-notifications-upstream.md](docs/android-notifications-upstream.md).

| Bod | Stav | Dôkaz |
|---|---|---|
| 1. Samsung A05: pípne, bez pop-upu | **Telefón nebol pripojený cez adb** — príčinu na ňom nebolo možné potvrdiť. Nájdená upstream chyba: súhrnná notifikácia skupiny sama zvoní (GROUP_ALERT_CHILDREN je na nesprávnej notifikácii); na AOSP ju stlmí len limit 1 upozornenie/s, na One UI môže zvoniť súhrn, ktorý sa nikdy neukáže ako pop-up. b24: súhrn nikdy nezvoní + diagnostika v Nastavenia → Upozornenia s exportom do súboru | emulátor b23: `notification_alert` len vďaka limitu; b24: súhrn `groupAlertBehavior=2`, správa pop-up, test pri zamknutí, export `psst-diagnostika-*.txt` |
| 1b. Hovor na celú obrazovku pri zamknutí | funguje (emulátor, b24, PIN) | `IncomingCallActivity` nad zamknutou obrazovkou, kanál RINGING_CALL |
| 2. macOS DMG sa nedá otvoriť | podpis blokovaný Apple: Developer ID certifikát vie vytvoriť len Account Holder (API 403). CI podpíše + notarizuje automaticky po nahratí certifikátu; stránka zatiaľ ukazuje návod | spctl na stiahnutom DMG: „rejected, no usable signature“ (run 43902841926) |
| 3a. Budíček pri žiadosti o overenie | nasadené (server psst-wake + Android b24) | zastavená appka: notifikácia 0,5 s po žiadosti z webu, ťuknutie → „Verification requested“ |
| 3b. Windows → iPhone neotvoril žiadosť | príčina: to-device žiadosť sa nepushuje, iPhone ju dostane až po otvorení appky (platí 10 min). Web/desktop b19: výzva otvoriť appku, odpočet, „Poslať znova“ | Playwright lokálne aj produkcia, emoji overenie dokončené |
| 4. Admin: nové heslo | nasadené | prihlásenie novým heslom prešlo, staré odmietnuté, audit log bez hesla |

**Account Holder GexPay SE musí:** na developer.apple.com → Certificates → + → Developer ID Application (G2 Sub-CA)
nahrať `devid.csr` (pošleme) a vrátiť `.cer`; potom `scripts/desktop/macos-devid-secrets.sh <cer> --run`
(docs/build/macos-signing.md). Ak je zobrazená výzva na novú licenčnú zmluvu, prijať ju.

**Verzie na stránke na stiahnutie:** Android b24, Windows b19 (MSI), macOS b19 (DMG, nepodpísaný + návod), iOS
„Coming soon“; web b19.

**Treba otestovať na skutočných zariadeniach:** Samsung A05 s b24 (aktualizácia sa ponúkne sama): správa pri
odomknutom aj zamknutom telefóne; ak stále len pípne → Nastavenia → Upozornenia → Diagnostika upozornení → povoliť
prístup k upozorneniam → nechať si poslať správu → oba testy → „Uložiť a odoslať“ a súbor poslať. Ďalej: hovor pri
zamknutom Samsungu, budíček overenia (prihlásiť sa na počítači, „Použiť iné zariadenie“, telefón so zatvorenou appkou),
„Poslať znova“ na Windows, nové heslo z /admin.

Testovacie účty qa-n*, qa-pw*, qa-vw* sú deaktivované; skutočných používateľov sa testy nedotkli.

---

# PSST — report (2026-11-16, dávka 11: tri chyby z telefónov + audit funkcií)

Rozhodnutia: D61 (Android sprievodca + kanál správ), D62 (neoverená relácia na webe/desktope), D63 (Android kontrola
verzie), D64 (audit), D65 (adresár členov, nešifrované kanály), D66 (QR relácia 5 min). Celá matica:
[docs/FEATURE-MATRIX.md](docs/FEATURE-MATRIX.md).

## Tri chyby (Samsung A05, build b13)

| Chyba | Príčina | Oprava | Overenie |
|---|---|---|---|
| 1. Sprievodca: po „Otvoriť nastavenia" sa nevráti, batéria nepríde | nastavenia otvárané s `FLAG_ACTIVITY_NEW_TASK` → One UI ich nechá v úlohe Nastavení, „Späť" nevedie do psst | otvárané v úlohe psst; `onResume` zistí skutočný stav a pokračuje: upozornenia+pop-up → zamknutá obrazovka → celá obrazovka → batéria | emulátor Android 14: všetky 4 kroky za sebou, každý sa po „Späť" vráti a sám pokračuje |
| 2. Správy len pípnu, bez pop-upu a zamknutej obrazovky | kanál si pamätal staré nastavenia; dôležitosť/viditeľnosť na zamknutej obrazovke appka po vytvorení kanála zmeniť nemôže; One UI má vlastné prepínače | nový kanál `PSST_MESSAGES_V4` (HIGH, „Správy"), staré zmazané; sprievodca kontroluje povolené upozornenia, pop-up kanála aj upozornenia na zamknutej obrazovke | emulátor: heads-up aj zamknutá obrazovka (PIN); aktualizácia b13→b18→b20, starý kanál zmazaný |
| 3a. Telefón nedostane notifikáciu o žiadosti o overenie | **obmedzenie protokolu**: žiadosť je to-device správa, Matrix push existuje len pre udalosti v miestnostiach; Element X ju ukáže len otvorený (limit 1 min); neoverené zariadenie push vôbec nemá | bez zmeny kódu; postup: overovať z nového zariadenia („Use another device") pri otvorenej appke na starom; návrh rozšírenia v D62 | reprodukované: push sa neposlal, pri otvorenej appke žiadosť hneď s odpočtom 1 min |
| 3b. Počítač sa tváril ako overený | po resete identity na inom zariadení (Element X „Can't confirm?") upstream ukáže len odložiteľný toast a appka ide ďalej | `force_verification` blokuje aj reláciu, ktorá overenie stratila (štart aj počas behu) | produkcia: reset z Androidu → web sa hneď prepne na „Confirm your digital identity" → overenie telefónom (emoji) → späť v appke |

## Audit funkcií — súhrn (celá matica: docs/FEATURE-MATRIX.md)

| platforma | ✅ funguje | ❌ nefunguje | 🟠 upstream | ⚪ nedá sa tu overiť |
|---|---|---|---|---|
| Web | 40 | 0 | 3 | 2 |
| Windows | 41 | 0 | 0 | 4 |
| macOS | 41 | 0 | 0 | 4 |
| Android | 40 | 0 | 4 | 1 |
| iOS | 9 | 0 | 0 | 36 |

Spolu 225 buniek: ✅ 171 · ❌ 0 · 🟠 7 · ⚪ 47 (iOS: simulátor bez APNs, kamery a mikrofónu; zvyšok dôvod v bunke).

Testované na produkcii, len na nových testovacích účtoch `qa-au*` (po audite deaktivované, testovacie miestnosti
zmazané). Web: Playwright; Windows/macOS: MSI/DMG b15 na GitHub runneroch (workflow *Desktop audit*); Android:
emulátor API 34 s Google Play services, build b13 → b23; iOS: simulátor (workflow *iOS audit*, XCUITest).

**Opravené počas auditu (náš fork/build/server):**
- Android: sprievodca nastavením (D61), kanál správ (D61), kontrola novej verzie (D63), odkaz „Download" otváral psst
  namiesto prehliadača — App Link už len pre permalinky `/#/…` (b23).
- Web/desktop: neoverená relácia sa tvárila ako overená (D62); macOS build nemal číslo buildu → About bez buildu
  a nefungovala kontrola novej verzie (nx zhltol `-c.*` argumenty electron-builderu; desktop b15).
- Server: Element X hlásil „This Matrix ID can't be found" a kontakty sa nedali nájsť menom; verejné kanály boli
  šifrované, takže noví členovia nevideli históriu a serverové vyhľadávanie nefungovalo (D65); QR prihlásenie
  padalo po 60 s („The sign in was not completed in time") → 5 min (D66); CI test servera: `downloads/` vytvorené
  rootom / nečitateľné pre nginx, obnova zo zálohy bez DB roly administrácie.

**Stále nefunguje (upstream, nie náš kód):**
- Notifikácia o žiadosti o overenie zariadenia na zatvorenú/neotvorenú appku (Matrix nepushuje to-device správy;
  Element X ukáže žiadosť len otvorený, 1 min). Obchádzka: overovať z nového zariadenia pri otvorenej appke na starom.
- Web: žiadne notifikácie pri zatvorenej karte (Element Web nemá Web Push); vyhľadávanie v šifrovaných miestnostiach
  na webe (Seshat len desktop) a v Element X Android (nemá vyhľadávanie v správach).
- Element X Android: zdieľanie obrazovky v hovore (len prijímanie); overenie zariadenia QR kódom (len emoji).

## Čo otestovať na skutočných zariadeniach
- Samsung A05 (b23): sprievodca od začiatku do konca (One UI: „Späť" z nastavení), vyskakovacie okno a zamknutá
  obrazovka pri správe; One UI „Štýl vyskakovacích upozornení" a „Skryť obsah" sú nastavenia telefónu.
- Android: odchádzajúce video z telefónu v hovore (emulátor nemá prednú kameru).
- Windows/macOS: viditeľný toast/notifikácia a zvonenie (CI nemá zvuk ani skutočnú plochu); zamknutá obrazovka.
- iOS (po TestFlighte): notifikácie (APNs), hovory, QR, súbory/fotky, overenie zariadenia do konca.
- Overenie zariadenia: po resete identity na telefóne sa počítač musí sám prepnúť na „Confirm your digital identity".


# PSST — report (2026-11-15, dávka 10: Windows, QR prihlásenie, stránka na stiahnutie)

Rozhodnutia: D58 (QR), D59 (stránka + automatika + aktualizácie desktopu), D60 (Windows E2E).

## Windows desktop — E2E na `windows-latest`, produkcia, MSI b12: **20/20**

Workflow *Desktop Windows E2E* (`scripts/desktop/windows-e2e.mjs`), čerstvé testové účty pre každý beh.

| Oblasť | Výsledok |
|---|---|
| inštalácia MSI (msiexec /qn), prvé spustenie | ✅ |
| stabilita 3 min po prihlásení + na konci | ✅ CPU 0,1 %, max ~715 MB, odozva ≤ 3 ms, bez rastu pamäte |
| prihlásenie cez MAS, odhlásenie, opätovné prihlásenie | ✅ (po opätovnom prihlásení Element žiada potvrdiť identitu — správne) |
| šifrovaná správa príjem / odoslanie, súbor, skupina 3 členov | ✅ (druhá strana Element Web, dešifrovanie overené) |
| notifikácia pri minimalizovanom okne a pri okne zavretom (X) do tray | ✅ appka beží skrytá v tray, notifikácia vyvolaná |
| prichádzajúci hovor 1:1 (zvonenie + toast + prijatie + video) | ✅ |
| skupinový hovor (oznámenie + pripojenie) | ✅ |
| About: číslo buildu | ✅ `1.12.35-b12 (2026-11-15)` |
| aktualizácie | ✅ Element updater vypnutý; appka kontroluje app.macet.eu/download |

Opravené: About na desktope bez čísla buildu; kontrola novej verzie cez našu stránku (namiesto Elementovho updatera);
Android `versionName` so zátvorkami rozbíjal User-Agent (názov zariadenia v zozname relácií); presmerovanie
`/download` ukazovalo na interný port 8443 (teraz `absolute_redirect off` pre celý nginx).
Poznámka: Windows história notifikácií (Action Center) zostáva prázdna, hoci appka notifikáciu vyvolá a Windows
appku registruje (AUMID `eu.macet.psst`) — skutočné zobrazenie toastu na pracovnej ploche overte na PC.

## QR prihlásenie — ✅ na produkcii

Synapse MSC4108 + MSC4388. Overené: web „Link new device → Show QR code" → Android (nové zariadenie) naskenoval
(emulátor, kamera s obrázkom QR) → kód 2 číslice na webe → overovací kód + „Grant access" v MAS → Android prihlásený.
Kontakt cez QR: QR v „Share" na webe/desktope je odkaz `app.macet.eu/#/user/…`, Android ho otvorí priamo v psst
(App Links overené) na profile s „Message".

## Stránka https://app.macet.eu/download

Android **b15** (APK arm64), Windows **b12** (MSI), macOS **b12** (DMG), iOS „Coming soon"; build, dátum, veľkosť,
SHA-256, návod. Odkaz „Download apps" na prihlasovacej obrazovke webu. Na serveri len aktuálne verzie.
Automatika: Android = `sign-release.sh`, Windows/macOS = CI → nahratie cez obmedzený SSH kľúč → server overí SHA-256
a zmaže starú verziu → klient stiahne cez HTTPS a porovná SHA-256 (inak build zlyhá); kontrola „stránka nie je
pozadu" lokálne aj v CI (denne + po každom desktop builde). Postup v BUILD.md.

## Čo ostáva

- Skutočné zobrazenie Windows toastu a zvuk zvonenia overiť na reálnom PC (v CI bez zvuku a bez interaktívnej plochy).
- QR prihlásenie s desktopom ako novým zariadením (desktop vie len zobraziť QR, skenuje mobil).
- iOS: App Group + záznam appky → `scripts/ios/release-testflight.sh`.

---

# PSST — report (2026-11-15, dávka 9: hovor na zamknutom Androide)

**Príčina:** Android 14+ zobrazí hovor cez celú zamknutú obrazovku len s povolením „Upozornenia na celú obrazovku"
(`USE_FULL_SCREEN_INTENT`); Samsung ho appkám z APK nechá vypnuté → len notifikácia na zamknutej ploche (D57).

**Zmeny (psst-android `8d5b83b8b`):** `IncomingCallActivity` `showWhenLocked`/`turnScreenOn` (manifest + API 27+);
pri prvom spustení / po aktualizácii / po hovore bez povolenia výzva s jednou vetou a priamym otvorením nastavenia
`ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT`, potom výnimka z optimalizácie batérie; notifikácia s odkazom na
nastavenie, keď hovor zazvonil bez povolenia. Notifikácia hovoru (CallStyle, kanál „Ringing calls" MAX + vyzváňanie,
fullScreenIntent) bola v poriadku. ConnectionService nie (problém by nevyriešil, D57).

**Test (emulátor Android 14, produkčný server, appka zatvorená):**

| Situácia | Výsledok |
|---|---|
| povolenie vypnuté, prvé spustenie | ✅ výzva „Full-screen calls" → otvorí presne „Allow full screen notifications" pre psst |
| po návrate z nastavení | ✅ výzva na batériu; v tej istej verzii sa znova nepýta |
| povolenie vypnuté, displej vypnutý, hovor | ✅ reprodukuje Samsung: zvoní, displej ostane zhasnutý; + notifikácia „Full-screen calls are off"; pri ďalšom otvorení appky výzva znova |
| povolenie zapnuté, displej vypnutý, zamknuté PINom, hovor | ✅ displej sa rozsvieti, „PSST test — Incoming Element Call", Accept / Reject cez zámku |
| Accept bez zadania PINu | ✅ otvorí sa hovor nad zámkou |
| CI (build + emulátor) | ✅ b13 |

**APK:** `dist/android/psst-android-20261115-b13-arm64.apk` (b9 → `dist/archive/android/`).

---

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
