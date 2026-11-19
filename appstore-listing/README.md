# psst — podklady pre App Store Connect (D87)

Nič z tohto nie je nahraté v App Store Connect. Do App Store Connect išiel len iOS build do TestFlightu.
Odpovede sú v angličtine, v poradí, v akom ich kladie App Store Connect. Pri každej je dôkaz.

| Súbor | Čo |
|---|---|
| `en-US/`, `sk/` | názov (≤ 30), podtitul (≤ 30), propagačný text (≤ 170), popis (≤ 4000), kľúčové slová (≤ 100 bajtov) |
| `screenshots/iphone-6.9/` | 1320×2868, iPhone 17 Pro Max simulátor (6,9″) |
| `screenshots/iphone-6.3/` | 1206×2622, iPhone 17 Pro simulátor (6,3″, „medium display“) |
| `screenshots/ipad-13/` | 2064×2752, iPad Pro 13″ simulátor (appka beží aj na iPade: `UIDeviceFamily` = [1, 2]) |
| `FORMS.md` | App Information, App Privacy, Age Rating, App Review Information |

Dĺžky textov (znaky / bajty):

| | name | subtitle | promotional | description | keywords |
|---|---|---|---|---|---|
| en-US | 16 | 25 | 113 | 1650 | 70 B |
| sk | 16 | 25 (28 B) | 108 | 1697 | 79 B |

Snímky vznikli v iOS simulátore z buildu psst iOS b2 na produkčnom serveri psst.pro s vymyslenými osobami
(testovacie účty `qa-*`, po nafotení deaktivované, miestnosti zmazané). Bez alfa kanála (App Store ho odmieta).
