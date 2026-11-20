# psst — dávka 21: otvorená registrácia s hCaptcha, bez pozvánok, hľadanie podľa presného mena

Stav k 2026-11-20. Rozhodnutia: DECISIONS.md **D88** (aj odsek „zistenia pri overení“).

## Verdikt

Hotovo a nasadené. Registráciu si teraz otvorí ktokoľvek od 18 rokov priamo z appky (stránka MAS s hCaptcha a
povinným súhlasom „Mám aspoň 18 rokov a súhlasím s Podmienkami používania“). Pozvánky zmizli zo servera, admin
stránky aj textov. Ľudí nemožno vylistovať ani hľadať podľa časti mena; rozhovor sa začína presným menom a vo
všetkých appkách funguje krátke „meno“ aj plné „@meno:psst.pro“. Nové buildy: Android b54, iOS b3 (TestFlight),
web + desktop b36 (macOS podpísaný a notarizovaný). Na produkcii sú ostré kľúče hCaptcha (overené na konci).
Do Play Console ani App Store Connect som nič neposlal okrem iOS buildu b3 do TestFlightu. Firewall, zálohy ani
Cloudflare som neriešil.

Jediné, čo som nevedel overiť úplne: **dokončenie registrácie s hCaptcha na produkcii**. hCaptcha vyžaduje
človeka a MAS 1.29 odmieta aj testovacie kľúče hCaptcha (kontroluje hostname „dummy-key-pass“), takže celá
registrácia je overená len bez captcha v dočasnom CI teste (detail nižšie, bod 6).

## 0. Kľúče hCaptcha

- `.hcaptcha-keys.txt` presunutý do `~/psst-keys/hcaptcha.txt` (chmod 600), z repa zmazaný.
- V gite nikdy nebol: žiadny commit (189 commitov, `git log --all`) neobsahuje súbor s „hcaptcha“ v mene ani hodnotu
  secretu (`git grep -F` cez všetky commity → 0).
- Na serveri: `/opt/psst/server/secrets/mas/hcaptcha_site_key` a `hcaptcha_secret` (600, vlastník UID 65532 = MAS),
  rovnako ako ostatné tajomstvá MAS. MAS nepozná `secret_key_file`, preto ich `deploy.sh` dosadí do vyrenderovaného
  `data/config/mas/config.yaml` (adresár len pre root/MAS). Bez nich `deploy.sh` skončí chybou.

## 1. Registrácia (MAS 1.29.0)

Voľby overené v `docs/reference/configuration.md` tagu v1.29.0 a cez `mas-cli config check` („looks good“):

| voľba | hodnota |
|---|---|
| `captcha.service` / `site_key` / `secret_key` | `hcaptcha` / zo `secrets/mas/` |
| `account.password_registration_enabled` | `true` |
| `account.password_registration_email_required` | `false` |
| `account.password_registration_token_required` | `false` |
| `rate_limiting.registration` | burst 3, per_second 0.0008 (3 naraz z IP, potom 1 za ~21 min) |
| `rate_limiting.login.per_ip` / `per_account` | 3 / 0.05 a 1800 / 0.5 (zapnuté, výslovne v šablóne) |
| `rate_limiting.username_availability` | 5 / 1.0 |
| `branding.tos_uri` | `https://psst.pro/terms` → natívne povinné políčko pri registrácii (MAS ho uloží v `user_terms`) |

- **Potvrdenie veku:** samostatné políčko MAS nemá, preto je v texte súhlasu: SK „Mám aspoň 18 rokov a súhlasím s
  Podmienkami používania“, EN (a ostatné jazyky) „I am at least 18 years old and I agree to the Terms and
  Conditions“. Text je v skompilovaných prekladoch React formulára; `server/scripts/mas-assets.py` ich pri každom
  deployi upraví z image MAS, uloží pod novými menami (kvôli `Cache-Control: immutable`, viď D88) a prepočíta SRI.
- **Odmietnutie bez platného tokenu (produkcia, požiadavka zo servera):** POST na `/auth/register` bez
  `h-captcha-response` aj s neplatným tokenom → HTTP 200, formulár s chybou `captcha`, účet nevznikol (0 v DB).

## 2. Pozvánky preč

- Admin `app.psst.pro/admin`: sekcia Pozvánky, formulár „Nová pozvánka“, stĺpec „Pozvánka“ pri členoch a
  endpointy `/admin/invites*` odstránené. Členovia, blokovanie, nové heslo a Nahlásenia ostali. Rola
  `psst_admin_ro` stratila SELECT na tabuľky registrácií MAS.
- `members.sh invite` a `scripts/new-invite.sh` zrušené.
- **Zneplatnené pozvánky:** všetkých 10 nezrušených registračných tokenov (6 z nich ešte použiteľných) →
  `revoked_at`; teraz 0 použiteľných z 11.
- **Staré odkazy:** odkazy s kódom sa nikdy nerozosielali (kód sa písal ručne do kroku MAS); `app.psst.pro` a
  „Create account“ vedú na bežnú registráciu, krok s kódom sa už neukáže.
- Appky nemali vlastné pole na kód ani odkazy s kódom (prehľadané všetky tri forky). Zmenili sa len komentáre.

## 3. Hľadanie ľudí

- Synapse 1.165: `user_directory.enabled: false` (podľa `rest/client/user_directory.py` vracia prázdny zoznam).
  Profil podľa presného mena ostáva prihláseným dostupný (`limit_profile_requests_to_users_who_share_rooms:
  false`).
- API (produkcia, účet review): `user_directory/search` pre „rev“, „review“, „review-partner“, „Review Partner“,
  „geo“, „psst“, „a“ → 0 výsledkov; profil `@review-partner:psst.pro` 200, neexistujúci 404.
- **Krátky tvar doplnený vo všetkých appkách** (plné `@meno:psst.pro` fungovalo aj predtým):
  - Android `MatrixUserRepository`: „jana“ aj „@jana“ → `@jana:<server>`, aj kratšie než 3 znaky; zobrazí sa len,
    ak profil existuje. Unit testy 12/12 (2 nové).
  - iOS `UserDiscoveryService` + prah hľadania 1 znak (Start chat aj pozvanie do miestnosti); unit testy upravené
    (2 nové).
  - Web/desktop `InviteDialog` (návrhy, Enter) a `useProfileInfo` (vyhľadávanie): „jana“. Vitest 72/72.

| | časť mena „qa-d8“ | krátke „qa-d88…“ | plné „@qa-d88…:psst.pro“ | žiadosť o chat príde |
|---|---|---|---|---|
| Web b36 (Chromium, produkcia) | nikto (dialóg aj vyhľadávanie) | ✅ QA Dana | ✅ | ✅ pozvánka u qa-d88d (API) |
| Desktop macOS b36 (lokálne, CDP) | nikto | ✅ | ✅ | ✅ pozvánka u qa-d88d (API) |
| Android b54 (emulátor, Android 15) | „No results“ | ✅ QA Dana | ✅ | ✅ DM vytvorený, pozvánka u qa-d88d (API) |
| iOS (simulátor iOS 27.2, XCUITest) | nikto | ✅ QA Filip | ✅ | ✅ Send invite → DM + správa, pozvánka is_direct u qa-d88f (API) |

Windows: netestované (rovnaký webapp b36 ako macOS).

## 4. Texty

- **psst.pro** SK/EN: „…na vlastnom serveri v EÚ, pre každého od 18 rokov.“
- **/privacy** (účinné od 20. 11. 2026): hCaptcha (Intuition Machines, Inc., USA) ako sprostredkovateľ — pri
  registrácii spracúva IP adresu, údaje o prehliadači a zariadení (typ prehliadača, OS) a to, ako s overením
  pracujete (pohyby myši, dotyky, klávesy); prenos do USA cez EU-U.S. Data Privacy Framework a SCC; len pri
  vytvorení účtu. Zdroj: hcaptcha.com/privacy a docs.hcaptcha.com/faq. Ďalej body „Stručne“, „Aké údaje“
  (Registrácia), právny základ, vek, cookies.
- **/terms:** účet si vytvorí ktokoľvek od 18 rokov, potvrdí to pri registrácii; ľudí nájdete len podľa presného
  mena; nový zákaz hromadného/automatizovaného zakladania účtov.
- **/support:** „Ako si vytvorím účet?“ a nová otázka „Ako začnem rozhovor?“. **/delete-account** sa nemenil
  (pozvánky nespomínal). **/download:** stará veta o pozvánke nahradená + krátky odsek „Účet“.
- **Obchody:** `play-listing/` (en-US, sk, FORMS, FACTS; DECLARATIONS pozvánky nespomínali) a
  `appstore-listing/` (en-US, sk, FORMS, APP-REVIEW-NOTES, README), nová feature grafika „For adults 18+.“.
  Text pre kontrolórov v `~/proj/psst-review.txt` upravený (heslá a kľúče nezmenené, overené).
- **Limity dĺžky:** Play krátky popis 70/80 (EN), 71/80 (SK); dlhý 1813 a 1772 / 4000. App Store subtitle 25/30,
  keywords 77 B a 71 B / 100, propagačný text 154 a 155 / 170, popis 1731 a 1755 / 4000.
- **Mení hCaptcha formuláre obchodov? Áno, jednu položku v každom** (opatrný výklad — registrácia beží v Custom Tab /
  ASWebAuthenticationSession; Google aj Apple chcú deklarovať údaje z web obsahu otvoreného z appky):
  - Play Data safety: **pridať App activity → App interactions** — Collected, Shared No (service provider),
    Required, Purpose „Fraud prevention, security, and compliance“. Location ostáva „Not collected“ (IP sa
    nepoužíva na polohu), Device or other IDs bez zmeny.
  - Apple App Privacy: **pridať Usage Data → Product Interaction** — App Functionality, Linked: Yes, Tracking: No.
    Location a Identifiers bez zmeny.
  - Podrobne `play-listing/FORMS.md` §7 a `appstore-listing/FORMS.md` §3.

## 5. Buildy

| platforma | build | kde | brány |
|---|---|---|---|
| Android | **b54** (26.11.0-b54+2026-11-20) — APK arm64, armv7, x86_64 + AAB | `dist/android/`, /download (arm64, armv7, AAB) | check-manifest OK (4/4), search-gate PASS (psst35) |
| iOS | **b3** (26.11.0) | TestFlight, interná skupina psst (VALID); IPA `dist/ios/psst-ios-20261120-b3.ipa` | — |
| Web | **b36** | app.psst.pro (`/version` 1.12.35-b36), release `web-b36` | CI smoke web ✅ |
| Desktop | **b36** — macOS dmg/zip, Windows msi/exe | `dist/desktop/`, /download | macOS Gatekeeper (CI aj lokálne `spctl`: Notarized Developer ID) |

- Stránka na stiahnutie sedí s `release/latest.json` aj `dist/latest.json` (`check-download-page.py`: 5× OK).
- Web + Desktop #34 a #35 sa zrušili (ručne spustený #35 zrušil #34 cez `cancel-in-progress`); platný je #36.
- Registrácia beží na stránke MAS, ale všetky appky potrebovali nový build kvôli krátkemu tvaru mena.

## 6. Overenie

- **Registračná obrazovka bez poľa na kód + hCaptcha + súhlas 18+:** web (EN aj SK, 10/10), Android b54 (Chrome
  Custom Tab), iOS simulátor (XCUITest `testRegistrationScreen`). Snímky v scratchpade a v CI artefakte.
- **Celá registrácia:** testovacími kľúčmi hCaptcha v MAS 1.29 nejde (MAS porovná hostname `dummy-key-pass`).
  CI smoke 1.3 (lokálny stack, 18/18 PASS): bez tokenu a s neplatným tokenom odmietnuté; testovací token hCaptcha
  potvrdí, MAS ho odmietne → token overuje na serveri; s **dočasne vypnutou captcha** (len v tom CI stacku):
  kroky `finish → display-name → finish`, žiadny krok s kódom, účet vznikol a prihlásil sa; captcha potom späť.
- **Ostré kľúče na produkcii (kontrola na konci):** `service: hcaptcha`, SHA-256 site key aj secret na serveri =
  `~/psst-keys/hcaptcha.txt`, testovacie kľúče nikde, `password_registration_token_required: false`.
- **Účet review:** prihlásenie 200, DM s review-partner (5 šifrovaných správ), skupina „Weekend trip“ (4).
  Relácie z kontroly odhlásené.
- **Admin stránka:** 14/14 (dočasný admin účet qa-d88adm, potom deaktivovaný).
- **Server smoke (CI):** 18/18 vrátane 2.4 „adresár vypnutý“.
- **Upratovanie:** 23 testovacích účtov `qa-d88*` deaktivovaných, ich 13 miestností zmazaných, dočasný secret
  `PSST_STORE_IOS` zmazaný. Aktívne účty: geo, psstadmin, review, review-partner.

### Chyba nájdená a opravená počas overenia

Prvá verzia úpravy textu súhlasu prepisovala preklady MAS pod pôvodnými menami súborov. MAS ich posiela ako
`immutable` na rok, takže prehliadač s nimi v cache (emulátor) ukázal na registrácii surové kľúče prekladov; to
isté by postihlo stránku účtu `/account`. Opravené pred koncom dávky (nové mená súborov, pôvodné nezmenené) a
overené v emulátore aj na webe. Chyba bola na produkcii približne od 07:30 do 09:10 SEČ (týkala sa len
prehliadačov, ktoré mali starý súbor MAS v cache).

## Neoverené

- Dokončenie registrácie s hCaptcha na produkcii (vyžaduje človeka; overené bez captcha v CI, viď bod 6).
- Windows desktop (rovnaký webapp b36 ako overený macOS).
- Fyzické telefóny (emulátor a simulátor).
- iOS v Debug builde padá upstream assertom, keď adresát nového DM ešte nemá kryptografickú identitu; release
  (TestFlight) to len zaloguje — na reálnom iPhone s b3 neoverené.

## Čo spraviť ty

1. Raz si sám vyskúšaj registráciu na https://app.psst.pro (hCaptcha + súhlas 18+) a nový účet potom zmaž
   (Nastavenia → Manage account → Delete account).
2. V Play Console a App Store Connect pri vypĺňaní formulárov pridaj položky z bodu 4 (App interactions /
   Product Interaction); texty obchodov a poznámky pre kontrolórov vlož z aktualizovaných súborov.
3. TestFlight b3 a Android b54 vyskúšaj na reálnych telefónoch: nový rozhovor zadaním „review-partner“.
4. Sleduj počet nových registrácií a nahlásení v /admin — registrácia je verejná.

## Commity

Hlavné repo: `5dd7381` (registrácia + hCaptcha), `c8e203f` (pozvánky preč), `548d7c1` (adresár), `64b3e49` (web
stránky), `8248fd4`, `7787be6`, `95864c9`, `7cd18ea` (testy), `4a237a4` (obchody), `5d90c57` (forky), `9404984`,
`131a8b1` (CI iOS), `73cb4f8` (docs) a záverečný commit s maticou a reportom. Forky (vetva psst): Android
`72af080fc`, iOS `aa739beb3` + `fdf6f2f9a`, web `f995d0434`.
