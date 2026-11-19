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
| en-US | 16 | 25 | 113 | 1660 | 79 B |
| sk | 16 | 25 (28 B) | 108 | 1707 | 76 B |

Snímky vznikli v iOS simulátore (CI `ios-store.yml`, iOS 27.2, stavový riadok 9:41) zo zdrojového kódu buildu psst iOS b2 na produkčnom serveri psst.pro s vymyslenými osobami
(testovacie účty `qa-*`, po nafotení deaktivované, miestnosti zmazané). Bez alfa kanála (App Store ho odmieta).
