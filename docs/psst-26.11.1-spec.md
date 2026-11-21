# psst 26.11.1 — spoločná špecifikácia (D94–D97)

Platí pre všetky klienty (Android, iOS, web, desktop). Texty presne takto (SK podľa KSSJ/PSP, EN). Kde je v SK
tvar slovesa, je zvolený prítomný čas („zapína“), aby nebolo treba rod.

## 1. Miznúce správy (D95) — základ

- Stav miestnosti **`m.room.retention`** (MSC1763), `state_key: ""`, obsah `{"max_lifetime": <ms>}`.
  Vypnuté = obsah `{}` (bez `max_lifetime`). Hodnoty: 5 min = 300000, 1 h = 3600000, 1 deň = 86400000,
  1 týždeň = 604800000. Iné hodnoty (od iných klientov) zobraziť ako „vlastné“ / zaokrúhlene.
- Zmeniť môže, kto má právo poslať tento stav (power levels, `events["m.room.retention"]` alebo `state_default`).
  V DM (preset trusted_private_chat) majú obaja 100 → obaja môžu. Inak voľbu zobraziť len na čítanie.
- **Server** (Synapse) mazanie robí sám (purge každých 5 min). **Klient**: v časovej osi neukazovať udalosti
  typu správa (nie stavové), ktorých `origin_server_ts + max_lifetime < teraz` (aj priebežne, časovač ≤ 30 s, aj
  bez spojenia so serverom), vrátane príloh a hlasových správ. (Mazanie z lokálnej DB, indexu a príloh
  v šifrovaných rozhovoroch je ďalšia etapa — v tejto verzii NIE.)
- Nastavenie v detaile rozhovoru (DM aj skupina):
  - SK „Miznúce správy“ / EN „Disappearing messages“; voľby SK „Vypnuté“, „5 minút“, „1 hodina“, „1 deň“,
    „1 týždeň“ / EN „Off“, „5 minutes“, „1 hour“, „1 day“, „1 week“.
  - Vysvetlenie SK: „Správy v tomto rozhovore po zvolenom čase zmiznú všetkým účastníkom — aj staršie. Server psst
    ich zmaže a appky psst ich prestanú zobrazovať. Čo si niekto medzitým skopíroval, preposlal alebo odfotil,
    sa vrátiť nedá.“
    EN: „Messages in this chat disappear for everyone after the chosen time — older ones too. The psst server
    deletes them and the psst apps stop showing them. Anything someone copied, forwarded or photographed in the
    meantime can't be taken back.“
- Časová os (stavová udalosť): SK „%1$s zapína miznúce správy: %2$s“ / „%1$s vypína miznúce správy“;
  EN „%1$s turned on disappearing messages: %2$s“ / „%1$s turned off disappearing messages“. %2$s = „5 minút“ …

## 2. Ochrana obrazovky (D96)

- Vlastný stav miestnosti **`eu.macet.psst.screen_protection`**, `state_key: ""`, obsah `{"enabled": true|false}`.
  Právo meniť ako pri ostatných nastaveniach (power levels / `state_default`; v DM obaja).
- Nastavenie v detaile rozhovoru: SK „Ochrana obrazovky“ / EN „Screen protection“ (prepínač).
  Vysvetlenie SK: „Appka psst na Androide v tomto rozhovore zablokuje snímky a nahrávanie obrazovky. Na iPhone
  a na webe sa to zablokovať nedá: appka na iPhone rozhovor skryje, keď sa obrazovka nahráva alebo zdieľa, a keď
  niekto urobí snímku, ostatní dostanú upozornenie. psst pre počítač bráni zachyteniu okna, kde to systém
  umožňuje. Odfotiť displej iným zariadením nezabráni nič.“
  EN: „The psst Android app blocks screenshots and screen recording in this chat. On iPhone and on the web this
  can't be blocked: the iPhone app hides the chat while the screen is recorded or shared, and when someone takes
  a screenshot, the others are told. psst for desktop prevents capturing the window where the system allows it.
  Nothing can stop someone photographing the screen with another device.“
- Časová os: SK „%1$s zapína ochranu obrazovky“ / „%1$s vypína ochranu obrazovky“;
  EN „%1$s turned on screen protection“ / „%1$s turned off screen protection“.
- **Upozornenie o snímke** (iOS userDidTakeScreenshot; Android 14+ ScreenCaptureCallback): poslať do rozhovoru
  `m.room.message` s `msgtype: "m.notice"`, `body` v jazyku odosielateľa: SK „📸 %1$s urobil(a) snímku obrazovky“ /
  EN „📸 %1$s took a screenshot“ (%1$s = vlastné zobrazované meno), a navyše kľúč
  `"eu.macet.psst.screenshot": true`. Max. 1 upozornenie za 10 s na rozhovor. Len ak je ochrana zapnutá.
- Platformy: Android `FLAG_SECURE` na okne, kým je otvorený taký rozhovor (aj jeho detail/médiá) + na API 34+
  `registerScreenCaptureCallback`; iOS prekrytie neutrálnou obrazovkou (logo psst) pri `sceneCaptureState ==
  .active` / `UIScreen.isCaptured`, v prepínači appiek (scenePhase inactive/background) a upozornenie pri
  `userDidTakeScreenshotNotification` — žiadne nedokumentované triky (nie vrstva isSecureTextEntry); web: v
  nastavení len text, že na webe sa to zablokovať nedá; desktop (Electron): `BrowserWindow.setContentProtection(true)`
  kým je otvorený taký rozhovor.

## 3. Poloha (D97)

- Mapy **OpenFreeMap** (OpenStreetMap, bez kľúča, bez reklamnej firmy) cez proxy psst, aby IP používateľov nešla
  tretej strane: štýl svetlý `https://app.psst.pro/maps/styles/liberty`, tmavý `https://app.psst.pro/maps/styles/dark`.
  Všetky URL v štýloch (dlaždice, sprity, písma) prepisuje proxy na `https://app.psst.pro/maps/…`.
  Atribúcia „© OpenMapTiles © OpenStreetMap contributors“ musí byť viditeľná (aj na statickom náhľade).
- Statický náhľad v časovej osi: nie MapTiler static API — vykresliť lokálne (MapLibre snapshotter) alebo
  interaktívnou mapou bez gest.
- „Poslať polohu“ (jednorazovo) a „Zdieľať polohu naživo“ 15 min alebo 60 min (Matrix live location beacons
  MSC3489/MSC3672, ako ich Element podporuje); dá sa kedykoľvek ukončiť, po čase sa vypne samo.
- Poloha nikdy na pozadí bez spusteného zdieľania. Povolenie sa pýta až pri prvom použití, s textom:
  SK „psst použije vašu polohu, len keď ju sami pošlete do rozhovoru alebo spustíte živé zdieľanie. Vidia ju len
  účastníci rozhovoru; v šifrovaných rozhovoroch je šifrovaná.“
  EN „psst uses your location only when you send it to a chat or start live sharing. Only the people in the chat
  can see it; in encrypted chats it is encrypted.“
- Android: len ACCESS_FINE/COARSE_LOCATION a FOREGROUND_SERVICE_LOCATION (živé zdieľanie); NIKDY
  ACCESS_BACKGROUND_LOCATION.

## 4. Zvyšky Element (D94)

Nikde nesmie byť pre používateľa viditeľné „Element“, „Element X“, „ElementX“ ani logo Element (systémové
dialógy, rozšírenia, notifikačné kanály, povolenia, zdieľanie, hovory, zvuky…). „Element Call“ v textoch → „psst“
alebo len „hovor“. Licenčný text „upravená verzia Element…“ v O aplikácii ostáva.
