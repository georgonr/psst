# psst — podklady pre App Store Connect (D87)

Nič z tohto nie je nahraté v App Store Connect. Do App Store Connect išiel len iOS build do TestFlightu.
Odpovede sú v angličtine, v poradí, v akom ich kladie App Store Connect. Pri každej je dôkaz.

| Súbor | Čo |
|---|---|
| `en-US/`, `sk/` | názov (≤ 30), podtitul (≤ 30), propagačný text (≤ 170), popis (≤ 4000), kľúčové slová (≤ 100 bajtov) |
| `screenshots/iphone-6.9/` | 1320×2868, iPhone Pro Max simulátor (6,9″), 4 ks: zoznam, skupina, chat, detail skupiny |
| `screenshots/iphone-6.3/` | 1206×2622, iPhone Pro simulátor (6,3″, „medium display“, podľa Apple povinné), 4 ks |
| `screenshots/ipad-13/` | 2064×2752, iPad Pro 13″ simulátor, 3 ks (appka beží aj na iPade: `UIDeviceFamily` = [1, 2]) |
| `FORMS.md` | App Information, App Privacy, Age Rating, App Review Information |
| `APP-REVIEW-NOTES.txt` | text do App Review Notes (bez hesla a kľúča na obnovenie — doplní majiteľ z `~/proj/psst-review.txt`) |

Dĺžky textov (znaky / bajty):

| | name | subtitle | promotional | description | keywords |
|---|---|---|---|---|---|
| en-US | 16 | 25 | 154 | 1731 | 77 B |
| sk | 16 | 25 (28 B) | 155 | 1755 | 71 B |

Snímky vznikli v iOS simulátore (CI `ios-store.yml`, iOS 27.2, stavový riadok 9:41) zo zdrojového kódu buildu psst iOS b2 na produkčnom serveri psst.pro s vymyslenými osobami
(testovacie účty `qa-*`, po nafotení deaktivované, miestnosti zmazané). Bez alfa kanála (App Store ho odmieta).

## Verzia 26.11.2 (D108)

Vkladá **majiteľ ručne** v App Store Connect (žiadny skript metadáta App Store nemení; `scripts/ios/testflight.py`
nahráva len build):

| Súbor | Kam |
|---|---|
| `26.11.2/APP-REVIEW-NOTE-LORA.txt` | App Review Information → Notes: odsek o LoRa **pridať** pod doterajší text z `APP-REVIEW-NOTES.txt` (spolu ~3 800 znakov, limit 4 000) |
| `26.11.2/WHATS-NEW-en-US.txt`, `26.11.2/WHATS-NEW-sk.txt` | verzia 26.11.2 → What's New in This Version (EN a SK, limit 4 000) |
| `FORMS.md` → Copyright | `2026 GT` (App Information) |
