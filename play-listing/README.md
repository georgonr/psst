# psst — podklady pre Google Play (D86, aktualizované D87 pre b51)

Nič z toho nie je nahraté v Play Console.

| Súbor | Čo |
|---|---|
| `en-US/`, `sk/` | názov, krátky popis (≤ 80 znakov), úplný popis |
| `graphics/icon-512.png` | ikona 512×512, 32-bit PNG (RGBA) |
| `graphics/feature-1024x500.png` | feature grafika 1024×500 (24-bit PNG), zdroj `graphics/make-graphics.mjs` |
| `screenshots/1-chats.png` … `5-search.png` | 5 snímok telefónu 1080×2400 z emulátora (Android 15, b47) |
| `FACTS.md` | overené fakty pre formuláre (AD_ID, povolenia b51, Data safety, hodnotenie obsahu, technické požiadavky, PEPK) |
| `FORMS.md` | odpovede na formuláre Play Console v poradí konzoly, s dôkazmi (bez hesiel) |
| `DECLARATIONS.md` | presné anglické texty vyhlásení: full-screen intent a typy služieb v popredí; odkazy na videá |
| videá | `https://psst.pro/video/psst-incoming-call-and-background-call.mp4`, `https://psst.pro/video/psst-message-notification.mp4` (zdroj `server/www/video/`) |

Snímky vznikli na produkčnom serveri psst.pro s vymyslenými osobami (Lucia Kováčová, Marek Novák, Zuzana
Horváthová, Tomáš Kráľ) na testovacích účtoch `qa-ps-*`. Účty sú po nafotení deaktivované a miestnosti zmazané.
Stavový riadok je v demo režime systému (čas, plná batéria).

**D87:** snímky sú z b47 a platia aj pre b51 — b51 mení len povolenia (nevidno ich) a pridáva dve položky do
O aplikácii; obrazovky na snímkach (konverzácie, skupina, chat, hovor, vyhľadávanie) sú rovnaké. Texty majú novú
časť Safety (nahlásenie, blokovanie, 18+) a odkazy na psst.pro/privacy a /terms.
