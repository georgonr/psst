# D99 — upratovanie 26.11.2 (návrh na zlúčenie do DECISIONS.md)

Čísla sú zástupné (D99-1 …); pri zlúčení ich treba prečíslovať. Štýl a jazyk ako v DECISIONS.md.

## Upratovanie pred 26.11.2 (2026-11-28, dávka 28)

**D99-1 — Staré adresy na macet.eu: v repozitároch psst už nie sú, server ich nepozná, DNS záznamy treba zmazať.**
- **Stav repozitárov:** v georgonr/psst (mimo histórie v DECISIONS.md a REPORT.md, ktoré sú záznamom minulosti a
  nemenia sa) ani v psst-web nie je žiadna adresa `*.macet.eu`. Ostávajú len identifikátory, ktoré sa meniť
  nesmú (D85): balík / bundle `eu.macet.psst`, App Group, pusher app_id, typy udalostí `eu.macet.psst.*`,
  Firebase projekt `psst-macet`, podpisový certifikát Android s `O=macet.eu`. Názov firmy MACET, s.r.o. sa nemení.
- **Server (repo):** šablóny nginx nemajú pre staré názvy vhost, certifikát ani presmerovanie (D85). Zvyšok bol
  len `NTFY_DOMAIN` (bývalé `push.macet.eu` → 301): `deploy.sh` ho už nečíta a `healthcheck.sh` preň nečaká 301.
- **Presmerovanie 301 nie (úsudok):** overené zvonka 28. 11. 2026 — `chat|app|call|push|psst|ntfy.macet.eu` stále
  ukazujú na server psst (204.168.160.131) a dostanú na :443 odmietnutý TLS handshake (`unrecognized name`), na :80
  prázdnu odpoveď (444). Presmerovanie by na HTTPS potrebovalo certifikát pre staré názvy, teda vrátiť macet.eu do
  certifikátu psst, a nemalo by komu slúžiť: staré relácie sú pre iný server_name a nedajú sa preniesť (D85), staré
  buildy (Android b44, desktop b27) pýtajú `latest.json` na starej doméne cez HTTPS a z presmerovania na nový
  server by im nič nevzniklo bez novej inštalácie; členovia dostali odkaz priamo. Čistejšie je záznamy zmazať.
- **DNS záznamy na zmazanie** (zóna macet.eu u Webglobe; overené `dig` priamo na ns1.webglobe.sk, TTL 3600; iné typy
  — AAAA, CNAME, TXT, MX, CAA, `_acme-challenge`, SRV `_matrix` — pre ne neexistujú):
  | Názov | Typ | Hodnota |
  |---|---|---|
  | chat.macet.eu | A | 204.168.160.131 |
  | app.macet.eu | A | 204.168.160.131 |
  | call.macet.eu | A | 204.168.160.131 |
  | push.macet.eu | A | 204.168.160.131 |
  | psst.macet.eu | A | 204.168.160.131 |
  | ntfy.macet.eu | A | 204.168.160.131 |
  - **Nemazať:** koreň `macet.eu`, `www`, `fx`, `zakazky` a wildcard `*.macet.eu` (195.181.248.25, hosting firmy) —
    nepatria psst. `turn.`, `auth.`, `pst.macet.eu` (a ďalšie) samostatný záznam nemajú, odpovedá za ne wildcard.
  - Po zmazaní budú aj tieto názvy odpovedať cez wildcard (hosting Webglobe: HTTP 301 na https, HTTPS s cudzím
    certifikátom) — obsah psst ani certifikát psst tam nebude. API token na DNS nie je, zmazanie robí majiteľ ručne.

**D99-2 — Autorské práva psst sú „© 2026 GT“.** Tam, kde psst ukazuje vlastné autorské práva: pätička psst.pro
(úvodná SK/EN, /privacy, /terms, /delete-account, /support — namiesto „Powered by GT“), web a desktop (Pomocník a O
aplikácii → Verzie, pätička prihlasovacích obrazoviek), desktop metadáta (macOS O aplikácii
`NSHumanReadableCopyright`, Windows `LegalCopyright` — predtým „Copyright © 2026 psst“ z autora v package.json),
App Store pole Copyright `2026 GT` (Apple pridá „©“), koniec úplného popisu v Google Play (Play pole Copyright nemá).
Nemenia sa licenčné texty (AGPL, „psst is free software based on Element…“), hlavičky zdrojových súborov upstreamu
ani prevádzkovateľ MACET, s.r.o. v Podmienkach, Súkromí a kontaktoch. Android a iOS (iné tímy): zoznam miest
v správe dávky.

**D99-3 — Chýbajúce slovenské texty na webe a desktope.** Element Web 1.12.35 mal v sk.json 182 nepreložených
kľúčov, shared-components 190 a desktop 7 (v slovenskom rozhraní sa ukazovali anglicky: filtre a ponuky zoznamu
miestností, výber emoji, dlaždice hovorov, chyby dešifrovania, šifrovanie a obnovenie, odhlásenie zariadenia,
prihlásenie QR, pozvánky, sekcie, vlákna…). Preložené všetky okrem labs, devtools a Element Call mock (v psst
skryté). Kontrola: zástupné symboly `%(…)s` a značky `<…>` sedia s angličtinou, oxfmt OK, `matrix-gen-i18n` OK
(zmazal nepoužívaný kľúč `powered_by_matrix`). Nadpis „Source code“ v Pomocníkovi je preložený („Zdrojový kód“),
licenčná veta ostáva anglicky. Výrazy podľa existujúceho prekladu: rozhovor, miestnosť, kľúč na obnovenie,
úložisko kľúčov, digitálna identita, poskytovateľ účtu.

**D99-4 — Slovenčina na stránkach MAS (prihlásenie, registrácia, účet).** MAS 1.29.0 nemá v serverových
prekladoch `translations/sk.json` 112 kľúčov (pätička Zásady / Podmienky, chyby mena a CAPTCHA, súhlas, prepojenie
zariadenia, zablokovaný / zmazaný účet, obnovenie…) a v React jazyku sk je 227 textov po anglicky („Your account“,
dialóg zmazania účtu, sila hesla, zariadenia, chyby…). Tým istým mechanizmom ako D88/D89 (bez forku MAS):
- texty sú v `server/mas/sk-server.json` (111) a `server/mas/sk-frontend.json` (231 vrátane slovenského
  množného čísla `:few`); `scripts/mas-assets.py` ich pri deployi doplní — serverové do `translations/sk.json`,
  React do skompilovaného `assets/sk-*.js`: modul (`var e={…}` s reťazcami v \`…\` a `JSON.parse(\`…\`)`) sa
  rozoberie na dáta, doplní a zapíše späť ako JSON v tom istom module s tým istým exportom;
- upravený jazyk dostane nové meno `…-p<tag>` (tag zahŕňa aj nové texty) — staré immutable assets v cache nič
  nerozbijú (poučenie D88);
- každá cesta kľúča musí byť v anglickom origináli, inak deploy skončí (pri novej verzii MAS);
- dialóg zmazania účtu je po slovensky bez „(MXID)“ a bez bodu o identity serveri (ako D89 v angličtine);
  text políčka 18+ a hlášky hCaptcha nastavuje ďalej D88.
- Overené lokálne na kópii živých assets psst (moduly en/sk) a šablónach / prekladoch MAS v1.29.0: parser vráti
  presne upstream preklady, prepis späť je zhodný, modul sa načíta v node (`default.frontend.account.title` =
  „Váš účet“), manifest a SRI prepočítané. **Na serveri zatiaľ nenasadené** (postup v správe dávky).

**D99-5 — App Store 26.11.2: poznámka pre kontrolu o LoRa a „Čo je nové“.** `appstore-listing/26.11.2/`:
anglický odsek do App Review Notes (LoRa je voliteľná, potrebuje vlastné rádio Meshtastic cez BLE, appka bez neho
funguje celá, povolenie Bluetooth až po „Search for devices via Bluetooth…“ na obrazovke LoRa; kontrolór ju otvorí
tlačidlom s anténou na domovskej obrazovke aj bez rádia) a What's New EN/SK. Pravdivo: šifrovanie psst end-to-end
platí pre priame správy medzi prepojenými kontaktmi psst, kanály majú len šifrovanie Meshtastic. Vkladá majiteľ
ručne; žiadny skript metadáta nemení.

**D99-6 — Google Play: deklarácia presnej polohy a Data safety pre LoRa.** Podklady v `play-listing/DECLARATIONS.md`
§4 a `play-listing/FORMS.md` §7 (LoRa):
- **Presná poloha:** od 27. 1. 2027 musí každá appka s `ACCESS_FINE_LOCATION` vyplniť deklaráciu v Play Console
  (Minimum Scope, support.google.com/googleplay/android-developer/answer/17033915; oznámenie 29. 10. 2026,
  answer/18100766). Odpoveď psst: Live tracking (živé zdieľanie 15/60 min) a One-time location sharing (poslať
  polohu), obe spustené používateľom, s odôvodnením, prečo približná poloha / tlačidlo polohy nestačí. psst cieli na
  API 37 (Android 17), kde je pre jednorazové žiadosti tlačidlo polohy požadovaná minimálna cesta — tímu Androidu
  odporúčam do 27. 1. 2027 posúdiť „Poslať polohu“ cez tlačidlo polohy (živé zdieľanie zostáva na FINE).
- **LoRa a Data safety:** správy LoRa idú z telefónu cez BLE do vlastného rádia používateľa a odtiaľ rádiom, nikdy
  cez servery psst ani tretej strany; prevádzkovateľ k nim nemá prístup. Google definuje „collect“ ako odoslanie
  z appky mimo zariadenia, o priamom prenose medzi zariadeniami / do periférie nehovorí. Opatrne: **formulár sa
  nemení** — „Messages → Other in-app messages“ je už deklarované ako Collected (Required, App functionality),
  takže pokrýva aj správy LoRa pri ľubovoľnom výklade; karta s verejným kľúčom pri „Link with LoRa“ ide ako
  bežná správa psst (už deklarované). Appka neposiela polohu cez LoRa; BLE sken s `neverForLocation` polohu
  neodvodzuje → Location bez zmeny (deklarované kvôli D97).
- **Bluetooth:** pre BLUETOOTH_SCAN / BLUETOOTH_CONNECT Play deklaráciu nevyžaduje (nie sú v zozname politiky
  Permissions and APIs that Access Sensitive Information, answer/16558241). Ak by Android držal spojenie s rádiom
  na pozadí službou v popredí (typ connectedDevice), treba deklaráciu služby v popredí s videom (answer/13392821).
