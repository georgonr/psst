# psst — podklady pre Google Play (D86)

Nič z toho nie je nahraté v Play Console.

| Súbor | Čo |
|---|---|
| `en-US/`, `sk/` | názov, krátky popis (≤ 80 znakov), úplný popis |
| `graphics/icon-512.png` | ikona 512×512, 32-bit PNG (RGBA) |
| `graphics/feature-1024x500.png` | feature grafika 1024×500 (24-bit PNG), zdroj `graphics/make-graphics.mjs` |
| `screenshots/1-chats.png` … `5-search.png` | 5 snímok telefónu 1080×2400 z emulátora (Android 15, b47) |
| `FACTS.md` | overené fakty pre formuláre (AD_ID, povolenia, Data safety, hodnotenie obsahu, technické požiadavky, PEPK) |

Snímky vznikli na produkčnom serveri psst.pro s vymyslenými osobami (Lucia Kováčová, Marek Novák, Zuzana
Horváthová, Tomáš Kráľ) na testovacích účtoch `qa-ps-*`. Účty sú po nafotení deaktivované a miestnosti zmazané.
Stavový riadok je v demo režime systému (čas, plná batéria).
