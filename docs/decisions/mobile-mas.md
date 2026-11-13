# PSST mobil — registrácia cez MAS, OAuth metadáta, push, právne odkazy

Kontext: homeserver `chat.macet.eu` deleguje autentifikáciu na Matrix Authentication Service (`https://chat.macet.eu/auth/` — D42).
MAS má zapnutú registráciu heslom, vyžaduje registračný (pozývací) token, e-mail nevyžaduje, dynamická registrácia
klientov je povolená (`allow_host_mismatch: true`). Tento dokument nahrádza časť D14 (registrácia už nie je len na webe)
a aktualizuje A5, A8 (Android), I11, I12, I13 (iOS) a D17.

Forky: `georgonr/psst-android` @ `297307c39`, `georgonr/psst-ios` @ `678eb3355` (vetva `psst`).

## Spoločné

**M1 — „Create account“ priamo v appke, zámok na chat.macet.eu ostáva.**
Upstream tlačidlo skrýva vždy, keď je poskytovateľ účtu vynútený (enterprise/MDM zámok), lebo predpokladá, že
používatelia firemnej appky už účty majú. Psst má jediný povolený server a jeho MAS registráciu podporuje, preto sa
tlačidlo ukazuje práve pre tento jediný vynútený server a otvára rovno registračnú stránku MAS (OIDC `prompt=create`),
kde nový člen zadá pozývací token. Žiadny výber servera ani textové pole servera sa nepridáva. Dôvod: minimálny zásah
do upstream logiky (jedna podmienka + jedna akcia), zámok (`EnterpriseService` / `allowOtherAccountProviders = false`)
sa nemení. Ak by server prestal ponúkať OAuth, appka ukáže chybu „registrácia nie je podporovaná“ (upstream správanie).

**M2 — OAuth metadáta klienta na `app.macet.eu` (Android aj iOS rovnako).**
`client_uri = https://app.macet.eu`, `logo_uri = https://app.macet.eu/vector-icons/512.png` (súbor, ktorý web klient
psst už obsahuje v nehashovanej podobe), `tos_uri = https://app.macet.eu/terms.html`,
`policy_uri = https://app.macet.eu/privacy.html`. Dôvod: politika MAS očakáva tieto URI na hoste `client_uri`
a stránky už existujú (dvojjazyčné SK/EN). Logo predtým na Androide `favicon.ico` (nie PNG), na iOS neexistujúce
`macet.eu/psst/logo.png`.

**M3 — Redirect schéma `eu.macet.app` (obrátený host `client_uri`).**
Android ju už mal (`eu.macet.app:/` release, `eu.macet.app.debug:/` debug, `.nightly`). iOS prešiel z
`eu.macet.psst:/oauth/callback` na `eu.macet.app:/oauth/callback`; schéma `eu.macet.app` bola pridaná do
`CFBundleURLSchemes` (v `target.yml` aj v commitnutom `Info.plist`). Dôvod: zhoda s pravidlom MAS bez spoliehania sa na
`allow_host_mismatch` a rovnaké pravidlo na oboch platformách. `eu.macet.psst` schéma (vlastné routy appky) ostáva.

**M4 — Právne odkazy (Nastavenia → O aplikácii / Právne informácie).**
Copyright a Acceptable use → `https://app.macet.eu/terms.html`, Privacy → `https://app.macet.eu/privacy.html`.
Odkaz „Source code (AGPL-3.0)“ na GitHub fork ostáva (AGPL §13). Dôvod: jednotné miesto pre podmienky psst; copyright
predtým viedol na LICENSE súbor forku — licencia je naďalej dostupná cez odkaz na zdrojový kód.

## Android

**M5 — Implementácia „Create account“.** `OnBoardingPresenter`: `canCreateAccount` je true aj keď existuje
`forcedAccountProvider` (singleton allow list + `canConnectToAnyAccountProvider() == false`). Nová udalosť
`OnBoardingEvent.OnSignUp` pošle `LoginModeEvent.Submit(isAccountCreation = true)` pre `chat.macet.eu` →
`LoginModePresenter` vyžiada OAuth URL s `OAuthPrompt.Create` → otvorí sa MAS v Custom Tab. Upstream cesta
(`navigateToSignUpFlow` → obrazovka s textovým poľom servera) sa pri vynútenom serveri nepoužije. Maestro test
`psstLock.yaml` teraz očakáva „Create account“ na onboardingu; `assertNoServerChoice.yaml` ho už nezakazuje
(objavuje sa aj na stránke MAS po kliknutí na Sign in).

**M6 — Push: predvolená UnifiedPush Matrix gateway `https://push.macet.eu/_matrix/push/v1/notify`.**
`UnifiedPushConfig.DEFAULT_PUSH_GATEWAY_HTTP_URL` (predtým `matrix.gateway.unifiedpush.org`). Appka najprv skúša
gateway na hoste endpointu distribútora (`/_matrix/push/v1/notify` discovery); push.macet.eu sa použije, keď ho
distribútor neponúka. Firebase ostáva vypnutý (`PUSH_CONFIG_INCLUDE_FIREBASE = false`), takže UnifiedPush je jediný
poskytovateľ — nie je čo „preferovať“. Testy v „Troubleshoot notifications“ nemajú natvrdo žiadny Element/Google host
(loopback test ide cez gateway aktuálneho pushera); odkaz na zoznam distribútorov `unifiedpush.org/users/distributors/`
ostal (len informačná stránka). Pozor: ntfy gateway prijíma iba pushkey na vlastnom serveri, takže reálne funguje pre
ntfy app nastavenú na server `https://push.macet.eu` — vtedy ju appka nájde aj discovery. Odporúčanie pre členov:
v ntfy appke nastaviť predvolený server `https://push.macet.eu`.

## iOS

**M7 — Implementácia „Create account“.** `AuthenticationStartScreenViewModel`: pri zamknutom jedinom poskytovateľovi
`showCreateAccountButton = appSettings.showCreateAccountButton` (upstream `false`); akcia `.register` volá
`loginDirectly(using: "chat.macet.eu", flow: .register)` → `AuthenticationService.configure(flow: .register)` →
`urlForOAuthLogin` s `prompt = .create` (ak MAS hlási podporu `create`) → `ASWebAuthenticationSession`.
Obrazovka výberu servera sa nepoužije.

**M8 — Push gateway a app ID pre Sygnal.** Pusher URL `https://chat.macet.eu/_matrix/push/v1/notify`
(`pushGatewayBaseURL` + `_matrix/push/v1/notify`), formát `event_id_only`, pushkey = base64 APNs token.
App ID = `baseBundleIdentifier` + prípona: **Debug `eu.macet.psst.ios.dev`** (APNs sandbox, `aps-environment:
development`), **Release `eu.macet.psst.ios.prod`** (APNs production po prepnutí v `ios-release.yml`). APNs topic =
bundle id `eu.macet.psst`.

**M9 — XcodeGen.** `project.yml` sa nemenil; v `target.yml` sa zmenili len `info.properties` (URL schéma), z ktorých
xcodegen generuje `Info.plist` — ten je upravený ručne rovnako, `project.pbxproj` sa nemení. CI (`ci/workflows/ios.yml`
a `ios-release.yml`) aj tak spúšťa `xcodegen` pred buildom.

## Čo zostáva mimo forkov
- `scripts/android/check_ui.py` v hlavnom repe má v `FORBIDDEN` vzor `create account` → emulátorový test by teraz
  zlyhal na onboardingu; treba ho odstrániť (alebo povoliť len na onboardingu).
- `app.macet.eu/vector-icons/512.png`, `/terms.html`, `/privacy.html` musia byť nasadené (pri overovaní 2026-11-13
  vracal app.macet.eu 404 na všetko).
