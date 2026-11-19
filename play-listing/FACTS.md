# psst — overené fakty pre formuláre Google Play (stav 2026-11-19, D86)

Zdroj: vydaný **AAB b47** `dist/android/psst-android-20261119-b47.aab` (SHA-256 v `dist/LATEST.md`), fork
`georgonr/psst-android@038c30754` a produkčný server psst.pro.

Ako som fakty overil:
- zlúčený manifest: `java -jar bundletool-all-1.18.3.jar dump manifest --bundle <aab>`;
- reťazce v kóde: `unzip -p <aab> 'base/dex/*.dex' | grep -a …`;
- natívne knižnice: ELF program headers (skript v REPORT.md / D86);
- veľkosť: `bundletool build-apks` + `get-size total`.

Do Play Console som nič nenahral ani neodoslal.

## 1. Reklamné ID (AD_ID)

- Zlúčený manifest AAB b47 **neobsahuje** `com.google.android.gms.permission.AD_ID` (0 výskytov).
- Kód reklamné ID **nepoužíva**. V dex nie je `AdvertisingIdClient`, `getAdvertisingIdInfo`,
  `ads/identifier` ani `play-services-ads` (0 výskytov).
- Nie je tam ani Firebase Analytics, PostHog ani Sentry. V dex sú len názvy konfiguračných polí Rust SDK
  (`posthogApiKey`, `sentryDsn`), hodnoty sú pri builde prázdne (`BuildTimeConfig.SERVICES_POSTHOG_*`,
  `SERVICES_SENTRY_* = null`).
- **Do formulára:** „Does your app use advertising ID?“ → **No**.

## 2. Povolenia (zlúčený manifest b47) a na čo sú

| Povolenie | Na čo | Odkiaľ |
|---|---|---|
| INTERNET, ACCESS_NETWORK_STATE | spojenie so serverom chat.psst.pro, zistenie, či je sieť | app, knižnice |
| POST_NOTIFICATIONS | upozornenia na správy a hovory | push |
| com.google.android.c2dm.permission.RECEIVE | príjem pushov cez Firebase Cloud Messaging | firebase-messaging |
| WAKE_LOCK | spracovanie pushu a hovoru pri zhasnutom displeji; rozsvietenie displeja pri správe (D73) | push, call |
| TURN_SCREEN_ON | rozsvietenie displeja pri novej správe (Android 15+ len so súhlasom používateľa) | push (psst) |
| USE_FULL_SCREEN_INTENT | prichádzajúci hovor na celú obrazovku cez zamknutý displej | call |
| VIBRATE | vibrácia upozornení a zvonenia | app |
| RECORD_AUDIO | hlasové správy, hovory | voicerecorder, call |
| CAMERA | video hovory, odfotenie prílohy, skenovanie QR (prihlásenie, overenie) | call, qrcode |
| MODIFY_AUDIO_SETTINGS | prepnutie reproduktor/slúchadlo počas hovoru | call |
| FOREGROUND_SERVICE (+ _CAMERA, _MICROPHONE) | prebiehajúci hovor beží ako služba v popredí (`CallForegroundService` microphone, `ElementCallForegroundService` camera+microphone) | call |
| FOREGROUND_SERVICE (shortService) | `FetchPushForegroundService`: krátke stiahnutie správy po pushi | push |
| FOREGROUND_SERVICE_LOCATION, ACCESS_FINE/COARSE_LOCATION | zdieľanie polohy (upstream). **V psst je funkcia skrytá** (bez mapového kľúča MapTiler `LocationService.isServiceAvailable()` = false, voľba „Location“ sa v prílohách neukáže), povolenia však v manifeste ostali | features/location |
| REQUEST_IGNORE_BATTERY_OPTIMIZATIONS | „Upozornenia a hovory“: žiadosť o výnimku z optimalizácie batérie, aby hovory a správy chodili spoľahlivo | push (psst) |
| REQUEST_INSTALL_PACKAGES | otvorenie prijatej prílohy .apk v systémovom inštalátore (upstream mediaviewer) | mediaviewer |
| RECEIVE_BOOT_COMPLETED | WorkManager (naplánované úlohy po reštarte) | androidx.work |
| USE_BIOMETRIC, USE_FINGERPRINT | voliteľný zámok appky odtlačkom prsta | androidx.biometric |
| ACCESS_LOCAL_NETWORK | Android 16+: upstream knižnica (sieťové volania) | androidutils |
| eu.macet.psst.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION | interné (androidx), nie je to povolenie od používateľa | AGP |

V manifeste nie je SMS, kontakty, notification listener ani accessibility (D83, `check-manifest.py`).

**Pozor pri odoslaní do Play** (neimplementované, len zistené): pri týchto povoleniach Play vyžaduje vyhlásenie
alebo ich obmedzuje.
- `REQUEST_INSTALL_PACKAGES`: povolené len pre appky, ktorých hlavnou funkciou je inštalácia balíkov → odporúčam
  ho pre Play odstrániť (`tools:node="remove"`).
- `ACCESS_FINE/COARSE_LOCATION` + `FOREGROUND_SERVICE_LOCATION`: funkcia je skrytá → odstrániť, inak treba
  vyhlásenie o polohe.
- `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`: Play to pre bežný messenger s FCM spravidla neuzná → odstrániť alebo
  zdôvodniť.
- `USE_FULL_SCREEN_INTENT`: psst je appka s hovormi → vyhlásenie „calling app“.
- `FOREGROUND_SERVICE_CAMERA/MICROPHONE`: vyhlásenie typov služieb v popredí (video ukážka hovoru).

## 3. Data safety

Všetka komunikácia appky ide šifrovane (HTTPS, TLS 1.2/1.3; hovory DTLS-SRTP cez vlastný LiveKit/TURN) na server
psst (chat.psst.pro, Hetzner, Fínsko). Tretej strane ide len push: Google FCM.

| Údaj | Zbiera / odosiela | Kam | Voliteľné | Poznámka |
|---|---|---|---|---|
| Meno (zobrazované meno), používateľské meno | áno | server psst | meno áno, používateľské meno nie | nutné na účet; ostatní členovia ho vidia |
| E-mail | len ak ho používateľ pridá v správe účtu | server psst (MAS) | áno | registrácia e-mail nevyžaduje |
| Správy | áno | server psst | — (účel appky) | DM a súkromné skupiny end-to-end šifrované (server vidí len šifrovaný text); verejné kanály nie sú E2EE |
| Fotky, videá, súbory | len čo používateľ pošle | server psst | áno | v šifrovaných miestnostiach šifrované end-to-end |
| Hlas (hlasové správy, hovory) | len čo používateľ pošle / počas hovoru | server psst (médiá, LiveKit SFU) | áno | hlasové správy v šifr. miestnostiach E2EE; hovory šifrované pri prenose |
| Kontakty (adresár) | **nie** | — | — | povolenie na kontakty nie je |
| Poloha | **nie** | — | — | funkcia skrytá (bod 2) |
| Identifikátory zariadenia | áno: Matrix device ID (vytvorí appka), FCM registračný token, Firebase Installation ID | server psst; Google (FCM) | nie | žiadne reklamné ID ani IMEI; server pri relácii vidí aj IP adresu |
| Push token | áno | server psst (pusher) → Sygnal → Google FCM | nie (bez neho nechodia upozornenia) | push nesie len ID udalosti a miestnosti a počty (`event_id_only`, `push.include_content: false`), nikdy obsah |
| Diagnostika, crash logy, analytika | **nie** | — | — | rageshake vypnutý, žiadne Sentry/PostHog |
| Kľúče šifrovania (záloha) | len ak si používateľ zapne zálohu kľúčov | server psst | áno | zašifrované kľúčom na obnovenie, ktorý má len používateľ |

**Zmazanie účtu a údajov:**
- **V appke:** Nastavenia → **Manage account & devices** → otvorí sa správa účtu (MAS, chat.psst.pro/auth/account)
  → **Delete account** → potvrdenie.
- **Na webe:** https://chat.psst.pro/auth/account/ (po prihlásení) → Delete account. Na webovej appke aj desktope
  vedie k tomu Settings → Account → Manage account.
- Overené 2026-11-19 na testovacom účte. Po potvrdení:
  - MAS aj Synapse účet deaktivujú;
  - Synapse ho zapíše do `erased_users` (GDPR erase), profil je vymazaný;
  - používateľské meno sa už nedá znova použiť.
- Správy, ktoré už dostali iní členovia, im ostanú. Na serveri sú v šifrovaných miestnostiach len šifrované a
  novým členom sa po zmazaní nezobrazia. Nahraté médiá Synapse pri deaktivácii automaticky nemaže.

**Čo pre Play chýba** (neimplementované):
- (a) **verejná stránka** s postupom zmazania (napr. `https://app.psst.pro/delete-account`) pre pole
  „Delete account URL“. Stránka účtu v MAS vyžaduje prihlásenie, takže je to len cesta pre prihláseného
  používateľa;
- (b) zmazanie **len údajov** bez zrušenia účtu appka neponúka, okrem mazania vlastných správ;
- (c) médiá zmazaného účtu ostávajú na serveri, kým ich správca nevyčistí.

## 4. Dotazník hodnotenia obsahu

- **Komunikácia medzi používateľmi:** áno. Text, hlas, video, súbory, obrázky v 1:1, skupinách a kanáloch.
  Registrácia len na pozvánku.
- **Zdieľanie obsahu používateľov:** áno, v rámci konverzácií. Verejný web ani profil, ktorý by videl ktokoľvek,
  nie je; adresár kanálov vidia len prihlásení členovia servera.
- **Zdieľanie polohy:** nie (funkcia je skrytá, bod 2).
- **Nákupy v appke / reklamy:** nie / nie.
- **Nástroje proti zneužitiu:**
  - zablokovanie používateľa (detail používateľa → Block, jeho správy sa skryjú);
  - „Decline and block“ pri pozvánke;
  - nahlásenie správy a miestnosti správcovi servera (Synapse `/report` → tabuľka `event_reports`);
  - správcovia miestností môžu vyhodiť alebo zakázať člena a meniť práva;
  - správca servera môže účet zablokovať (https://app.psst.pro/admin).
- **Medzera:** nahlásenia sa zatiaľ nikde nezobrazujú. Admin stránka ich neukazuje (dnes je 0 nahlásení), dajú
  sa čítať len cez Synapse admin API.

## 5. Technické požiadavky Play

- **targetSdk 37**, minSdk 24, versionCode 210000470, versionName `26.11.0-b47+2026-11-19`. Play dnes vyžaduje
  cieľové API ≥ 35 pre nové appky; 37 to spĺňa.
- **16 KB stránky:**
  - všetkých 14 natívnych knižníc pre **arm64-v8a** a **x86_64** má LOAD segmenty zarovnané na **16384**, takže
    to spĺňa;
  - armeabi-v7a (32-bit) má 4096 a požiadavka sa naň nevzťahuje.
- **Veľkosť stiahnutia z Play** (bundletool get-size, Android 10+):
  - arm64 ≈ **66 MB** (66 060 284 – 66 155 609 B);
  - armv7 ≈ 62 MB;
  - x86_64 ≈ 69 MB.
  - AAB má 162 MB, lebo obsahuje všetky ABI.
- **Podpis:** AAB b47 je podpísaný kľúčom `psst` z `~/psst-keys/psst-release.jks`. SHA-256 certifikátu
  `3A:64:28:CF:51:EE:8F:5E:10:E8:4F:AC:5C:A8:A6:B3:C3:B8:C3:4D:26:74:DB:0F:22:24:D1:D0:09:7D:38:99` = keystore
  (overené `keytool -printcert -jarfile` vs. `keytool -list`). Ten istý odtlačok je v `assetlinks.json` na
  app.psst.pro.

## Play App Signing: nahratie existujúceho kľúča (PEPK) — postup, nespustené

Prečo existujúci kľúč: psst sa už inštaluje z app.psst.pro/download. Keby Play podpisoval novým kľúčom, verzia z
Play by sa nedala nainštalovať cez verziu z webu, a naopak. Navyše by prestali fungovať App Links
(`assetlinks.json`).

1. Play Console → appka → Test and release → **App integrity** → App signing → „Use a different key“ →
   **„Export and upload a key from Java KeyStore“**.
2. Stiahnuť `pepk.jar` a verejný šifrovací kľúč Google (`encryption_public_key.pem`) do `~/psst-keys/play/`
   (adresár 700).
3. Na tomto Macu (kľúč neopustí počítač inak než zašifrovaný pre Google). Heslá sa zadajú interaktívne a
   nikam sa nezapisujú:
   ```sh
   cd ~/psst-keys/play
   java -jar pepk.jar --keystore=$HOME/psst-keys/psst-release.jks --alias=psst \
     --output=psst-play-signing-key.zip --include-cert --rsa-aes-encryption \
     --encryption-key-path=encryption_public_key.pem
   ```
4. Nahrať `psst-play-signing-key.zip` v tom istom dialógu. **Upload key:** odporúčam vytvoriť samostatný upload
   kľúč (`keytool -genkeypair … -alias psst-upload`, certifikát `.pem` nahrať v Play). Pri úniku sa potom dá
   vymeniť bez zmeny podpisu appky. Alternatíva: ten istý kľúč aj ako upload kľúč.
5. Po potvrdení musí byť odtlačok „App signing key certificate“ v Play rovný `3A:64:…:38:99`. Zip potom zmazať.
