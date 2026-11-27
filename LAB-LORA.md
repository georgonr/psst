# psst lab — LoRa / Meshtastic

Testovacia appka **psst lab** pre iPhone: bežný psst chat (server psst.pro) + sekcia **LoRa** na správy cez rádiá
Meshtastic bez internetu, s vlastným šifrovaním psst. Len na test (TestFlight, interná skupina „psst“), nikam sa
nezverejňuje. Rozhodnutia a dôvody: [DECISIONS.md](DECISIONS.md) L1-01 až L1-16.

## 0. Stav (27. 11. 2026)

- Kód: fork `georgonr/psst-ios` vetva `lab/meshtastic` (`725e858`), hlavné repo vetva `lab/meshtastic`.
- Lokálne (Mac, Swift 6.1): 31 unit testov `PsstLab` PASS; test so skutočným rádiom PASS (sekcia 7).
- CI (Xcode 27.2, run 46036679390): unit testy balíka PASS, kompilácia balíka pre iOS PASS, všetky Swift zdroje
  appky sa skompilovali; simulátorový build po oprave `ARCHS=arm64` prešiel.
- **TestFlight: psst lab 26.11.1 (1)** — VALID, interná skupina „psst“ (tester Geo M), exportné šifrovanie ako
  v psst; CI: kontrola run 46043109368, release run 46052971102 (L1-17, L1-18).

## 1. Inštalácia z TestFlightu

1. Na iPhone otvorte appku **TestFlight** (prihlásená Apple ID, ktoré je v App Store Connect ako tester „Geo M“).
2. V zozname je **psst lab** (ikona psst so žltým pásom LAB) → **Inštalovať**.
3. psst lab sa nainštaluje **vedľa** psst — nič s ňou nezdieľa (iný bundle, iná kľúčenka, bez App Group).
4. Prihláste sa ako v psst (Sign in to psst.pro). Môžete použiť ten istý účet ako v psst; psst lab je pre server
   ďalšie zariadenie (nová relácia, overte ju ako zvyčajne).
5. psst lab **nemá push notifikácie** psst správ (L1-02) — chat sa obnoví, keď appku otvoríte.

## 2. Spárovanie rádia s iPhonom

1. Rádio Meshtastic zapnite, v ňom musí byť zapnutý Bluetooth (v appke Meshtastic: Config → Bluetooth → Enabled).
   Ak je rádio pripojené k inému telefónu alebo k appke Meshtastic, odpojte ho — rádio prijme naraz len jedno
   Bluetooth spojenie.
2. V psst lab ťuknite na domovskej obrazovke hore na ikonu antény → otvorí sa **LoRa**.
3. Prvýkrát sa iPhone opýta na **Bluetooth** — povoľte (psst lab ho používa len na spojenie s vaším rádiom).
4. **Vyhľadať zariadenia cez Bluetooth…** → vyberte svoje rádio (napr. „Meshtastic_0df0“).
5. iPhone ukáže **žiadosť o spárovanie s PIN** — PIN je na displeji rádia; rádio bez displeja má pevný PIN
   z nastavení (často `123456`).
6. Stav sa zmení na *Načítavam nastavenia a uzly…* a potom **Pripojené**: vidno meno uzla, batériu, región
   (musí byť EU_868), firmvér a silu Bluetooth signálu. psst lab si rádio zapamätá a pri ďalšom otvorení LoRa sa
   pripojí samo.

## 3. Prepojenie kontaktu (raz, keď máte internet)

Obaja potrebujete psst lab so spárovaným rádiom.

**Cez psst rozhovor:** otvorte 1:1 rozhovor s kontaktom → ťuknite na jeho meno (detail rozhovoru) → sekcia
**psst lab · LoRa** → **Prepojiť s LoRa**. Do šifrovaného rozhovoru odíde správa „🔗 psst lab: prepojenie s LoRa“
s vaším LoRa uzlom a odtlačkom kľúča. To isté urobí kontakt na svojom telefóne. Keď psst lab zobrazí jeho správu
v rozhovore, kontakt sa prepojí — v detaile rozhovoru uvidíte „Prepojené: uzol !xxxxxxxx, kľúč XXXX XXXX …“.
(Ak správu dostane appka psst bez lab, zobrazí sa len ako text — dá sa ignorovať.)

**Osobne cez QR:** LoRa → **Môj kľúč a QR kód** na jednom telefóne, na druhom LoRa → **Prepojiť kontakt cez QR
kód** → Naskenovať. Potom naopak.

Porovnajte odtlačok kľúča (4 skupiny po 4 znaky) na oboch telefónoch. Zoznam: LoRa → Prepojené kontakty (potiahnutím
doľava sa prepojenie zruší).

## 4. Poslanie správy medzi dvoma telefónmi

- **Priama správa:** LoRa → Rozhovory → kontakt (alebo *Nová priama správa — zoznam uzlov* → uzol). Pri prepojenom
  kontakte je zapnuté **psst šifrovanie** (zelený zámok). Napíšte text → odoslať.
- **Kanál:** LoRa → Rozhovory → *Verejný kanál* (alebo kanál s vlastným menom). Správu dostane každý v dosahu, kto má
  ten kanál; psst šifrovanie sa v kanáli nepoužíva.
- Pri každej správe je štítok šifrovania:
  - **psst šifrovanie** (zelený) — prečíta ju len prepojený kontakt;
  - **len Meshtastic (PKI)** / **len Meshtastic (kľúč kanála)** (oranžový) — chráni ju len šifrovanie rádií;
  - **verejný kľúč kanála** / **nešifrované** (červený) — predvolený kanál s kľúčom „AQ==“ prečíta ktokoľvek.
- Stav doručenia: *odosiela sa* → *odoslané* (✓, rádio počulo preposlanie) → **potvrdené** (✓ v krúžku, ACK od
  cieľového rádia; pri delenej správe „odoslané 2/3“, kým neprídu všetky) → *zlyhalo: dôvod*.
- Limity: bežná správa **200 bajtov** (diakritika ≈ 2 B/znak, emoji 4 B); psst šifrovaná **1 535 B** — počítadlo
  pod poľom ukazuje bajty a počet LoRa paketov. Jeden plný paket ≈ 2 s vysielania; v EU868 platí limit vysielacieho
  času (duty cycle), dlhé správy preto šetrite.
- Správy ostávajú v appke aj po reštarte. Keď je appka na pozadí a rádio pripojené, prijatá LoRa správa ukáže
  notifikáciu.

## 5. Keď sa zariadenie nenájde

| Príznak | Čo robiť |
|---|---|
| „Bluetooth je vypnutý“ / „nemá povolený Bluetooth“ | Ovládacie centrum → Bluetooth; Nastavenia → psst lab → Bluetooth zapnúť. |
| Zoznam zariadení je prázdny | Rádio zapnuté a nabité? Bluetooth v rádiu zapnutý? Odpojte ho z appky Meshtastic alebo iného telefónu (rádio vysiela Bluetooth len bez pripojeného klienta). Priblížte sa na pár metrov. Reštartujte rádio. |
| Nevypýta PIN / „Pripojenie zlyhalo“ | Nastavenia iPhonu → Bluetooth → (i) pri rádiu → **Zabudnúť zariadenie**, potom v psst lab znova vyhľadať. Ak rádio zmenilo PIN alebo bolo preflashované, starý pár nefunguje. |
| Visí na „Načítavam nastavenia…“ | Odpojiť → Pripojiť znova; reštart rádia. Rádio s veľkou databázou uzlov posiela nastavenia aj 10–20 s. |
| Región UNSET | psst lab ponúkne „nastaviť EU_868“ — iné nastavenia rádia appka nemení. |
| Správa „zlyhalo: bez potvrdenia“ | Druhé rádio je mimo dosahu alebo vypnuté; skúste kanál, iné miesto alebo vyššiu polohu antény. |
| Prepojenie sa neukazuje | Obaja ste stlačili „Prepojiť s LoRa“ až po spárovaní rádia? Otvorte 1:1 rozhovor, aby sa načítala správa kontaktu. |

## 6. Ako je to šifrované (pravdivo)

**Meshtastic (rádiá):** kanál má jeden zdieľaný kľúč (AES-128/256-CTR, bez overenia integrity); predvolený kanál
LongFast má verejne známy kľúč `AQ==` — prakticky nešifrované. Priame správy (firmvér 2.5+) rádiá šifrujú kľúčmi
uzlov (X25519 → SHA-256 → AES-256-CCM, 8 B tag) — prečíta ich cieľové rádio a každý telefón k nemu pripojený.
Hlavička paketu (odosielateľ, príjemca, ID, skoky, hash kanála) šifrovaná nie je. Bez forward secrecy; identita
uzla je „trust on first use“. Zdroj: meshtastic.org/docs/overview/encryption a …/reference/encryption-technical.

**psst šifrovanie (navyše, len priame správy prepojeným kontaktom):** X25519 (kľúč v Keychain iPhonu) + HKDF-SHA256
(zvlášť pre každý smer) + ChaCha20-Poly1305; počítadlo správ = nonce a ochrana proti opakovaniu; odosielateľa
overuje kľúč kontaktu + číslo uzla. Text neprečíta nikto iný v sieti — ani rádiá, ani ich pripojené telefóny.
Neskrýva metadáta (kto komu kedy píše) a nemá forward secrecy. Detail formátu: DECISIONS.md L1-09.

## 7. Test so skutočným zariadením (27. 11. 2026)

Heltec V2.1 (`!bd460df0`, firmvér 2.7.26, EU868, LongFast) cez USB `/dev/cu.usbserial-0001`, tá istá vrstva
`PsstMesh` ako v appke, nástroj `psst-mesh` (`Components/PsstLab` vo forku). Druhé rádio: LilyGO T-LoRa V2.1-1.6
`!ea251718` v tej istej miestnosti (SNR 12,8 dB, RSSI −41 dBm). Report: `Components/PsstLab/TestResults/`.

| Test | Výsledok |
|---|---|
| Pripojenie cez sériové API, `want_config` → `config_complete` | PASS |
| Načítanie uzlov (3 okrem vlastného, mená, SNR, skoky, PKI kľúče) a kanálov (0 = predvolený kľúč, 1 = vlastný AES-256) | PASS |
| Správa do kanála 0 | PASS — *odoslané* (implicitné ACK) |
| Priama správa na `!ea251718` | PASS — **potvrdené** ACK uzla |
| psst šifrovaná správa, 1 paket (47 B) | PASS — potvrdené |
| psst šifrovaná **delená** správa (490 B → 3 pakety) | 1. pokus FAIL (3 pakety naraz, ACK 1/3) → oprava stop-and-wait → **PASS 3/3 ACK** |
| Odoslané rámce druhá strana poskladá a dešifruje (kľúč testovacieho kontaktu) | PASS |
| Prijatie bežnej správy z kanála (od cudzieho uzla `!4572c052`) | PASS |
| Prijatie **psst šifrovanej** správy cez vzduch | **neoverené** — druhé rádio nemá psst lab klienta, ktorý by odpovedal; overené unit testom so simulovanou sieťou (2 klienti, delenie, odpoveď, odmietnutie zopakovanej správy) |
| BLE vrstva | unit testy (`BLESessionTests`: čítanie do prázdna, FromNum počas čítania, zápisy po jednom, UUID) — na iPhone overí používateľ |

Opakovanie testu: `cd Components/PsstLab && swift build && .build/debug/psst-mesh test --port /dev/cu.usbserial-0001 --to '!ea251718'`.

## 8. Čo otestovať na iPhone (2 telefóny, 2 rádiá)

1. Inštalácia vedľa psst, prihlásenie, bežný chat funguje.
2. LoRa → spárovanie s PIN, stav Pripojené, batéria, zoznam uzlov s časom a signálom.
3. Správa do kanála a priama správa uzlu → stav *odoslané*/*potvrdené*.
4. „Prepojiť s LoRa“ na oboch telefónoch → oba ukazujú *Prepojené* a rovnaký odtlačok; alternatívne QR.
5. psst šifrovaná správa oboma smermi, aj dlhá (> 177 B → viac paketov) → zelený štítok, *potvrdené*.
6. Reštart appky → správy a prepojenie ostali.
7. Vypnúť druhé rádio → správa skončí *zlyhalo*.
8. Zamknutá obrazovka s pripojeným rádiom → notifikácia prijatej LoRa správy.
