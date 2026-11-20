# Play Console — pripravené odpovede (D87)

Poradie podľa Play Console: **Dashboard → Set up your app** (App content) a potom **Store settings** a **Main store
listing**. Odpovede sú po anglicky, ako sa vypĺňajú. Pri každej je odkaz na dôkaz. Heslá tu nie sú: App access
odkazuje na `~/proj/psst-review.txt` (chmod 600, len na Macu majiteľa).

Overené na buildoch **b51** (AAB `dist/android/psst-android-20261119-b51.aab`) a na produkčnom serveri psst.pro.
Do Play Console som nič nenahral ani neodoslal.

Poradie sekcií App content nie je v dokumentácii Google celé popísané; je podľa Play Console (Privacy policy,
App access, Ads, Content rating, Target audience, News apps, Data safety, Government apps, Financial features,
Health, Advertising ID, potom vyhlásenia o povoleniach) — pri vypĺňaní stačí ísť po sekciách.

---

## 1. Privacy policy

- **Privacy policy URL:** `https://psst.pro/privacy`
- Dôkaz: verejná stránka bez prihlásenia, SK + EN, prevádzkovateľ MACET, s.r.o., kontakt psst@psst.pro, údaje
  podľa FACTS.md §3, sekcia o zmazaní účtu. `curl -s https://psst.pro/privacy` → 200.

## 2. App access

- **"All or some functionality in my app is restricted"** → yes (the app requires an account). Od D88 si účet
  vytvorí ktokoľvek od 18 rokov priamo v appke (Create account → stránka MAS s hCaptcha), ale pripravené šifrované
  konverzácie má len účet `review` — kontrolórovi dávame ten.
- **Add instructions:**
  - Name: `psst review account`
  - Username: `review`
  - Password: *(z `~/proj/psst-review.txt`)*
  - "Any other information required to access your app": vložiť text z `~/proj/psst-review.txt` (časť „Text to
    paste…“) a doplniť kľúč na obnovenie. Text v súbore: sign-in steps, „Enter recovery key“, where the test
    chat and group are, how to report and delete the account.
- Dôkaz: účty `@review:psst.pro` a `@review-partner:psst.pro` existujú, nie sú admin, majú šifrovanú
  konverzáciu (5 správ) a skupinu „Weekend trip“ (4 správy); všetkých 9 správ je na serveri len ako
  `m.room.encrypted`; záloha kľúčov aktívna (REPORT.md D87).

## 3. Ads

- **Does your app contain ads?** → **No.** Dôkaz: FACTS.md §1 (žiadne reklamné SDK, žiadne AD_ID).

## 4. Content rating (IARC questionnaire)

- E-mail: `psst@psst.pro`
- **Category:** "All Other App Types" → in the questionnaire choose the *communication / social* type if
  offered ("Social Networking, Forums, Blogs and UGC Sharing" alebo "Communication").
- Answers:

| Question (IARC) | Answer | Prečo |
|---|---|---|
| Violence, fear, sexuality, language, controlled substances, crude humor (app's own content) | **No** to all | appka sama obsah nevytvára |
| Gambling / simulated gambling | No | |
| Does the app allow users to interact or exchange content with other users? | **Yes** | správy, súbory, hovory |
| Can users share their current physical location with other users? | **No** | poloha odstránená v b51 (FACTS.md §2) |
| Does the app allow users to purchase digital goods? | No | |
| Does the app contain advertising / promote tobacco/alcohol? | No | |
| Is the app a web browser or search engine / unrestricted internet access? | No | |
| Does the app share user-provided personal information with third parties? | No | FCM dostane len push token (poskytovateľ služby) |
| Moderation (if asked): "Does the app provide a way to block users / report content?" | **Yes / Yes** | blokovanie; nahlásenie správy a miestnosti → `app.psst.pro/admin` Nahlásenia |

Očakávaný výsledok: IARC zvyčajne „Teen“/„PEGI 12“ s označením „Users Interact“. Služba je pre 18+ (Target
audience).

## 5. Target audience and content

- **Target age groups:** **18 and over** only.
- **Could your store listing unintentionally appeal to children?** → **No.**
- Dôkaz: `https://psst.pro/terms` bod 2 (od 18 rokov), `https://psst.pro/privacy` bod 9.

## 6. News apps

- **Is your app a news app?** → **No.**

## 7. Data safety

**Data collection and security**

| Question | Answer | Dôkaz |
|---|---|---|
| Does your app collect or share any of the required user data types? | **Yes** | |
| Is all of the user data collected by your app encrypted in transit? | **Yes** | HTTPS/TLS 1.2+ k chat.psst.pro, hovory DTLS-SRTP (FACTS.md §3) |
| Which of the following methods of account creation does your app support? | **Username and password** | MAS, otvorená registrácia s hCaptcha a súhlasom s Podmienkami (D88); bez e-mailu a telefónu |
| Delete account URL | `https://psst.pro/delete-account` | verejná stránka: postup v appke, na webe, e-mailom bez prihlásenia; čo sa zmaže a čo ostane (zálohy 6 mesiacov) |
| Do you provide a way for users to request that some or all of their data is deleted, without requiring them to delete their account? | **Yes** — mazanie vlastných správ v appke; súbory zo servera na žiadosť e-mailom (psst.pro/delete-account) | |
| Independent security review | No | |

**Data types** (collected = odoslané na server psst; **shared = No** pri všetkých — Google FCM je poskytovateľ
služby, ktorý spracúva push token v mene appky; to Play nepovažuje za zdieľanie)

| Category → type | Collected | Shared | Required / optional | Purposes | Poznámka |
|---|---|---|---|---|---|
| Personal info → **Name** | Yes | No | Optional | App functionality, Account management | zobrazované meno |
| Personal info → **Email address** | Yes | No | Optional | Account management | len ak si ho používateľ pridá |
| Personal info → **User IDs** | Yes | No | Required | App functionality, Account management | `@meno:psst.pro` |
| Messages → **Other in-app messages** | Yes | No | Required | App functionality | DM a súkromné skupiny E2EE (server má len šifrovaný text), verejné kanály nešifrované |
| Photos and videos → **Photos**, **Videos** | Yes | No | Optional | App functionality | len čo používateľ pošle |
| Audio → **Voice or sound recordings** | Yes | No | Optional | App functionality | hlasové správy; hovory sa neukladajú |
| Files and docs → **Files and docs** | Yes | No | Optional | App functionality | prílohy |
| App activity → **Other user-generated content** | Yes | No | Optional | App functionality | reakcie, názvy a témy miestností, nahlásenia |
| Device or other IDs → **Device or other IDs** | Yes | No | Required | App functionality | Matrix device ID, FCM registration token, Firebase Installation ID |
| App activity → **App interactions** | Yes | No | Required | **Fraud prevention, security, and compliance** | **nové v D88:** hCaptcha pri registrácii (práca s overením: pohyby, dotyky, klávesy) |

**Not collected:** Location (odstránená), Financial info, Health and fitness, Contacts, Calendar, Web browsing,
In-app search history, Installed apps, Crash logs, Diagnostics, Advertising ID.

**Mení hCaptcha (D88) odpovede v Data safety? Áno, jednu.** hCaptcha (Intuition Machines, Inc.) beží len na
registračnej stránke MAS, ktorú appka otvorí v prehliadači (Custom Tab), a spracúva IP adresu, údaje o prehliadači
a zariadení (typ prehliadača, OS) a signály práce s overením (pohyby myši, dotyky, klávesy) — hcaptcha.com/privacy,
docs.hcaptcha.com/faq. Google vyžaduje uviesť údaje „collected from a webview which has been opened from your app“;
o Custom Tabs výslovne nehovorí, preto volíme opatrný výklad a deklarujeme:
- **pridať** App activity → **App interactions**: Collected **Yes**, Shared **No** (hCaptcha je sprostredkovateľ,
  t. j. „service provider“), **Required** (bez overenia sa účet nevytvorí), Purpose **Fraud prevention, security,
  and compliance**, nie ephemeral (hCaptcha údaje krátko uchováva podľa svojich zásad);
- **bez zmeny:** IP adresu Google vyžaduje uviesť len ako polohu, ak sa z nej poloha určuje — psst ani hCaptcha ju
  na to pre nás nepoužívajú → Location ostáva „Not collected“; údaje o prehliadači a OS nie sú identifikátor
  zariadenia → Device or other IDs bez zmeny; „Is all data encrypted in transit?“ ostáva Yes (HTTPS).
Dôkaz: FACTS.md §1–3 (manifest b51, dex bez analytiky a reklamného ID, `event_id_only` push).

Ephemeral processing: push notifikácia (len ID udalosti) sa spracuje v zariadení a neukladá.

## 8. Government apps

- **Is your app developed by or on behalf of a government?** → **No.**

## 9. Financial features

- **Does your app provide any financial features?** → **No** (none of the listed).

## 10. Health

- **Health features** → **No** / "My app does not have any health features".

## 11. Advertising ID

- **Does your app use advertising ID?** → **No.**
- Dôkaz: manifest b51 neobsahuje `com.google.android.gms.permission.AD_ID`; `check-manifest.py` ho od D87 zakazuje.

## 12. Permission declarations (App content → Sensitive permissions)

Presné texty a video: **`play-listing/DECLARATIONS.md`**.

| Formulár | Odpoveď |
|---|---|
| Full-screen intent | core functionality **Calling** — text v DECLARATIONS.md §1 |
| Foreground service types | **microphone** (VoIP call), **camera** (video call), **shortService** (fetch message after push) — texty a video v DECLARATIONS.md §2 |
| Photo and video permissions | netýka sa: appka nežiada READ_MEDIA_IMAGES/VIDEO (výber cez systémový picker) |
| Location permissions | netýka sa: odstránené v b51 |
| Install packages | netýka sa: odstránené v b51 |
| Battery optimisation (REQUEST_IGNORE_BATTERY_OPTIMIZATIONS) | netýka sa: odstránené v b51 |
| SMS / Call log | netýka sa |

Konečný zoznam povolení b51 je vo FACTS.md §2.

## 13. Store settings — App category and contact details

| Field | Value |
|---|---|
| App or game | App |
| Category | **Communication** |
| Tags | Messaging, Video calling (podľa ponuky konzoly) |
| Email address | `psst@psst.pro` (povinné, verejné) |
| Phone number | nevypĺňať (podľa zadania žiadny telefón) |
| Website | `https://psst.pro` |
| External marketing | On (podľa majiteľa) |

## 14. Main store listing

| Field | Value | Súbor |
|---|---|---|
| App name | `psst secure chat` (16/30) | `en-US/title.txt`, `sk/title.txt` |
| Short description | 70/80 (EN), 71/80 (SK) | `*/short-description.txt` |
| Full description | 1813 / 1772 znakov (≤ 4000) | `*/full-description.txt` |
| App icon | 512×512, 32-bit PNG s alfa kanálom | `graphics/icon-512.png` |
| Feature graphic | 1024×500, PNG bez alfa | `graphics/feature-1024x500.png` |
| Phone screenshots | 1080×2400 (9:20), 5 ks | `screenshots/` |
| Languages | English (United States) – default, Slovak | |

## 15. Play App Signing

App integrity → App signing → „Use a different key“ → „Export and upload a key from Java KeyStore“ → nahrať
**`~/psst-keys/play/psst-signing-key.zip`** (pripravené PEPK v D87, certifikát `3A:64:…:38:99`). Po nahratí musí
„App signing key certificate“ v Play ukazovať ten istý odtlačok. Upload key: odporúčaný samostatný (FACTS.md, PEPK
krok 4).
