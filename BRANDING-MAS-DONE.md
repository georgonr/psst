# psst — dávka 22: značka psst na stránkach MAS a iOS pri novom kontakte

Stav k 2026-11-20. Rozhodnutia: DECISIONS.md **D89**. Nové buildy appiek som nerobil, do Play Console ani App Store
Connect som nič neposlal.

## Verdikt

Stránky prihlasovacej služby (MAS, chat.psst.pro/auth) majú značku psst: titulok karty „psst – <nadpis stránky>“,
tmavé pozadie, favicon a logo psst, žiadne „matrix-authentication-service“, „Matrix Authentication Service“ ani
„Element“. Preklady sa nerozbili — overené v čistom prehliadači aj s cache z predchádzajúcej verzie, SK aj EN.
**iOS Release (ako TestFlight b3) pri rozhovore s kontaktom, ktorý sa nikdy neprihlásil, nepadá — nič som
nemenil, b4 netreba.** Navyše som našiel „ElementX“ v systémovom dialógu prihlásenia na iOS (nie je to MAS, ale
názov appky); oprava je pripravená vo forku pre ďalší build.

## 1. Značka na stránkach MAS

Ako (bez úpravy kódu MAS; `server/scripts/mas-assets.py` pri každom deployi z image MAS 1.29.0):

| čo | kde | výsledok |
|---|---|---|
| titulok karty | serverové preklady `app.name`, `app.human_name` → „psst“ | „psst“; skript doplní „ – <nadpis h1>“ |
| tmavé pozadie | šablóny `base.html`, `app.html`: `<html class="cpd-theme-dark">` (téma Compound z CSS MAS) | tmavé vždy |
| favicon | `<link rel="icon">` z psst.pro (svg + png 32 + apple-touch 180), `theme-color` | psst |
| logo | inline SVG psst + „psst“ nad obsahom každej stránky | psst |
| „Matrix ID“, „(MXID)“, admin rozsah „…v matrix-authentication-service“ | serverové a frontendové preklady | „meno účtu“ / bez žargónu / „psst“ |
| bod „removed from the identity server“ v dialógu zmazania | frontendové preklady | odstránený (psst identity server nepoužíva) |

- Šablóny a serverové preklady sa renderujú na serveri → cache prehliadača ich neovplyvní. Upravené súbory
  frontendu majú nové mená (ako v D88), staršie generácie sa nemažú.
- `mas-cli templates check` s upravenými šablónami: 1585 renderov bez chyby; server-smoke v CI 18/18.
- **E-maily:** MAS žiadne neposiela (`email.transport: blackhole`); šablóny e-mailov Element/Matrix neobsahujú.
- **„Matrix“** ostal len vo formáte mena `@meno:psst.pro` a v licenčných hlavičkách šablón (nezobrazujú sa).

### Overenie

| prostredie | stránky | výsledok |
|---|---|---|
| web, Chromium, čistý profil, EN | prihlásenie, registrácia, obnovenie hesla, chyba autorizácie, 404, súhlas, účet, zariadenia, zmena hesla, reset identity, dialóg zmazania | **45/45** |
| web, čistý profil, SK | to isté | **45/45** |
| web, profil s cache z predchádzajúcej verzie, EN / SK | to isté okrem súhlasu (Element Web v profile už prihlásený; súhlas je serverová šablóna, cache ho neovplyvní) | **41/41** / **41/41** |
| Android b54, emulátor (Chrome Custom Tab) | registrácia „psst – Create an account“, prihlásenie „psst – Sign in“, účet „psst – Your account“ | tmavé, logo psst, texty (nie kľúče) |
| iOS simulátor (Release) | registrácia, prihlásenie | logo psst, žiadne zakázané texty ani kľúče; súhlas so značkou psst na snímke |

Pred nasadením (rovnaký test): titulok „matrix-authentication-service“, biele pozadie, bez loga — 0/5 stránok OK.
Kontrolný skript: `scripts/audit/mas-brand.mjs` (čistý profil aj „s cache“, EN aj SK).

## 2. iOS — pád pri novom kontakte

- Build **Release** (rovnaká konfigurácia ako TestFlight b3) pre simulátor v CI (`ios-store.yml`,
  `configuration=Release`; doplnené `ONLY_ACTIVE_ARCH=YES`, lebo Rust SDK nemá x86_64).
- Postup ako v dávke 21: Start chat → „qa-d8“ nikto → „qa-d89b“ a „@qa-d89b:psst.pro“ → QA Novak (účet, ktorý sa
  nikdy neprihlásil, bez kryptografickej identity) → Send invite → **DM vytvorený, správa odoslaná, test prešiel,
  žiadny crash report**. Príčina pádu v dávke 21 bol `MXLog.failure` → `assertionFailure` len v `#if DEBUG`.
- **Release nepadá → nič som nemenil, iOS b4 nie je potrebný.**

## Zistenie navyše (mimo MAS)

Na iOS sa pri otvorení správy účtu (a pri prihlásení) ukáže systémový dialóg **„„ElementX“ Wants to Use
„chat.psst.pro“ to Sign In“**. iOS v ňom berie `CFBundleName`, ktorý je v b3 „ElementX“ (názov na ploche
`CFBundleDisplayName` je „psst“). Oprava je vo forku psst-ios (`CFBundleName = $(APP_DISPLAY_NAME)`), pôjde s
ďalším buildom — táto dávka nové buildy nerobila.

## Neoverené

- iOS: správa účtu so značkou psst a dialóg s názvom „psst“ — test v simulátore spadol na systémovom okne „Save
  Password?“ skôr, než sa k nim dostal (správa účtu je overená na webe a Androide; je to tá istá stránka MAS).
- Slovenské texty, ktoré MAS nemá preložené (napr. „Your account“, dialóg zmazania, pätička) ostávajú anglicky.
- Widget hCaptcha volí tému podľa systému — na tmavej stránke môže byť svetlý.

## Čo spraviť ty

1. Pri ďalšom iOS builde (b4, keď bude treba) sa do TestFlightu dostane aj názov „psst“ v systémovom dialógu.
2. Raz si otvor https://chat.psst.pro/auth/account v prehliadači a pozri, či vzhľad sedí (tmavý, logo psst).

## Commity

Hlavné repo: server značka (`292868e` + nasledujúce úpravy mas-assets), test `mas-brand.mjs` (`e58f648`), CI iOS
(Release, poradie testov, architektúra), forky: psst-ios (testy, `CFBundleName`). Testovacie účty `qa-d89*`
deaktivované, dočasný secret zmazaný; aktívne účty: geo, psstadmin, review, review-partner.
