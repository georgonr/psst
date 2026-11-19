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

## Absolútne cesty

- AAB: /Users/juromucka/proj/psst/dist/android/psst-android-20261119-b51.aab
- Snímky Play: /Users/juromucka/proj/psst/play-listing/screenshots/
- Snímky App Store: /Users/juromucka/proj/psst/appstore-listing/screenshots/ (iphone-6.9, iphone-6.3, ipad-13)
- FORMS.md (Play): /Users/juromucka/proj/psst/play-listing/FORMS.md
- Vyhlásenia (Play): /Users/juromucka/proj/psst/play-listing/DECLARATIONS.md
- appstore-listing: /Users/juromucka/proj/psst/appstore-listing/ (FORMS.md, APP-REVIEW-NOTES.txt)
- PEPK zip: /Users/juromucka/psst-keys/play/psst-signing-key.zip
- Účty pre kontrolórov: /Users/juromucka/proj/psst-review.txt
