# App Store Connect — pripravené odpovede (D87)

Poradie podľa App Store Connect: App Information → Pricing → App Privacy → verzia (texty, snímky, App Review
Information) → Age Rating. Odpovede po anglicky, ako sa vypĺňajú. **Heslo ani kľúč na obnovenie tu nie sú** —
sú v `~/proj/psst-review.txt` (chmod 600), majiteľ ich doplní do formulára.

Dôkazy: `play-listing/FACTS.md` (rovnaký kód a server ako iOS), IPA b2 (`dist/ios/`), stránky na psst.pro.

## 1. App Information

| Pole | Odpoveď | Dôkaz |
|---|---|---|
| Name | `psst secure chat` | app record už existuje (D86) |
| Subtitle | `Encrypted chats and calls` (SK: `Šifrované správy a hovory`) | `en-US/subtitle.txt` |
| Bundle ID | `eu.macet.psst` (nemení sa) | D85, D86 |
| Primary language | English (U.S.); lokalizácia Slovak | |
| Category | Primary **Social Networking**, secondary **Productivity** (voliteľné) | messenger; rovnako ako iné messengery |
| Content Rights | „Does your app contain, show, or access third-party content?“ → **No** (obsah tvoria používatelia; appka nezobrazuje cudzí licencovaný obsah) | |
| Age Rating | pozri bod 5 | |
| Privacy Policy URL | `https://psst.pro/privacy` | stránka verejná, SK + EN |
| **Pozor** | Dnešná hodnota v App Store Connect je `https://app.psst.pro/privacy.html` (nastavil ju skript v dávke 19). Funguje, lebo presmeruje na psst.pro/privacy, ale odporúčam ju prepísať na `https://psst.pro/privacy` (neurobil som to: do App Store Connect sa okrem buildu nič neposielalo). | `scripts/ios/testflight.py` PRIVACY_URL |
| Copyright | `2026 MACET, s.r.o.` | |

## 2. Pricing and Availability

- Price: **Free** (0). In-app purchases: none.
- Availability: podľa rozhodnutia majiteľa (služba je len na pozvánku; odporúčam EÚ alebo všetky krajiny).
- Distribution: Public on the App Store (appka je len na pozvánku, ale kontrolór má hotový účet; „Unlisted app“
  je alternatíva, ak ju nechcete mať vo vyhľadávaní — žiadosť cez Apple formulár).

## 3. App Privacy (Data Collection)

**„Do you or your third-party partners collect data from this app?“ → Yes.**

Údaje, ktoré server psst uchováva dlhšie než na vybavenie požiadavky (definícia „collect“ podľa Apple). Žiadne sa
nepoužívajú na sledovanie (tracking), reklamu ani analytiku. Všetky sú **Linked to the user** (sú pri účte).

| Kategória → typ | Collected | Purposes | Linked | Tracking | Prečo / dôkaz |
|---|---|---|---|---|---|
| Contact Info → **Name** | Yes | App Functionality | Yes | No | zobrazované meno (voliteľné, ostatní ho vidia) |
| Contact Info → **Email Address** | Yes (len ak ho používateľ pridá) | App Functionality | Yes | No | MAS, voliteľné; registrácia e-mail nevyžaduje |
| User Content → **Emails or Text Messages** | Yes | App Functionality | Yes | No | správy; v DM a súkromných skupinách len šifrované (E2EE), verejné kanály nešifrované |
| User Content → **Photos or Videos** | Yes | App Functionality | Yes | No | prílohy, ktoré používateľ pošle; v šifrovaných miestnostiach E2EE |
| User Content → **Audio Data** | Yes | App Functionality | Yes | No | hlasové správy; hovory sa neukladajú |
| User Content → **Other User Content** | Yes | App Functionality | Yes | No | súbory, reakcie, názvy a témy miestností, profilový obrázok, nahlásenia |
| Identifiers → **User ID** | Yes | App Functionality | Yes | No | `@meno:psst.pro` |
| Identifiers → **Device ID** | Yes | App Functionality | Yes | No | Matrix device ID a APNs push token (server ho odovzdá Apple na doručenie upozornenia) |

**Not collected:** Health & Fitness, Financial Info, Location, Sensitive Info, Contacts, Browsing History, Search
History (vyhľadávanie v správach beží len v zariadení), Purchases, Usage Data, Diagnostics (žiadne crash reporty,
žiadna analytika), Surroundings, Body, Other Data.

**Tracking:** „Do you or your third-party partners use data for tracking?“ → **No.** Appka nemá IDFA ani
App Tracking Transparency prompt.

Dôkaz: `play-listing/FACTS.md` bod 1 a 3 (žiadne analytické ani reklamné knižnice; push `event_id_only`),
`https://psst.pro/privacy`.

## 4. Verzia: texty, snímky, App Review Information

| Pole | Hodnota |
|---|---|
| Promotional Text | `en-US/promotional-text.txt` |
| Description | `en-US/description.txt` (SK: `sk/description.txt`) |
| Keywords | `en-US/keywords.txt` (70 bajtov) |
| Support URL | `https://psst.pro/support` (kontakt psst@psst.pro, nahlásenie, zmazanie účtu) |
| Marketing URL | `https://psst.pro` |
| Screenshots | `screenshots/iphone-6.9/` (1320×2868), `screenshots/iphone-6.3/` (1206×2622), `screenshots/ipad-13/` (2064×2752) |
| Build | psst iOS **b2** (TestFlight, verzia 26.11.0) |
| Version „What's New“ | prvé vydanie — netreba |

**App Review Information**

- Sign-in required: **Yes**.
- User name: `review`
- Password: *(doplní majiteľ zo súboru `~/proj/psst-review.txt`)*
- Contact: first/last name *(majiteľ)*, phone *(majiteľ — Apple ho vyžaduje, verejne sa nezobrazuje)*,
  e-mail `psst@psst.pro`.
- Notes (skopírovať zo súboru `~/proj/psst-review.txt`, časť „Text to paste…“, doplniť heslo a kľúč na
  obnovenie). Obsah: služba je len na pozvánku → hotový účet; prihlásenie; „Use recovery key“; kde je chat a
  skupina; nahlásenie (podržať správu → Report; Report room); blokovanie; zmazanie účtu (Settings → Manage
  account & devices → Delete account) a `https://psst.pro/delete-account`.

Guideline 1.2 (user-generated content) — čo appka má: podmienky s nulovou toleranciou
(`https://psst.pro/terms` bod 3), nahlásenie správy a miestnosti, blokovanie používateľa, správca vidí
nahlásenia na `https://app.psst.pro/admin` (sekcia Nahlásenia: zablokovať člena, zmazať obsah), záväzok do 24 h
v podmienkach. Guideline 5.1.1(v) (zmazanie účtu v appke): Settings → Manage account & devices → Delete account
(overené v iOS builde, REPORT.md).

## 5. Age Rating (dotazník, v poradí formulára)

| Sekcia | Otázka | Odpoveď | Prečo |
|---|---|---|---|
| In-App Controls | Parental Controls | No | |
| | Age Assurance | No | vek sa neoveruje technicky; podmienky: 18+ a len na pozvánku |
| Capabilities | Unrestricted Web Access | No | appka nemá prehliadač; odkazy otvára v Safari |
| | User-Generated Content | **Yes** | správy, súbory, kanály |
| | Social Media | No | nie je verejný profil ani feed |
| | Messaging and Chat | **Yes** | |
| | Advertising | No | |
| Mature Themes | Profanity or Crude Humor / Horror/Fear / Alcohol, Tobacco, Drugs | None | appka sama obsah netvorí |
| Medical or Wellness | Medical or Treatment Information / Health or Wellness Topics | No / No | |
| Sexuality or Nudity | všetky tri | None | |
| Violence | všetky štyri | None | |
| Chance-Based Activities | Gambling / Simulated Gambling / Contests / Loot Boxes | No / None / No / No | |

Výsledné hodnotenie vypočíta App Store Connect (pri „Messaging and Chat“ + „User-Generated Content“ zvyčajne
13+ alebo 16+). Podmienky služby určujú **18+** — ak formulár ponúkne vyššie hodnotenie („Override to higher
age rating“), zvoľte **18+**. Overiť priamo vo formulári, neoverené (do App Store Connect som nič neposielal).

## 6. Export compliance

Už vyriešené pri builde: `ITSAppUsesNonExemptEncryption = false` (štandardná kryptografia, výnimka) — D86.
