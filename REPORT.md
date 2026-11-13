# PSST — report (2026-11-13, tretia dávka: server pripravený na nasadenie)

Predchádzajúce reporty (prvá a druhá dávka) sú v git histórii.

## Verdikt

**Server je pripravený na nasadenie jedným príkazom** (`sudo ./deploy.sh <IP> <email>`) a všetky appky sú
prebuildované s novými funkciami. Na lokálnom stacku je overená registrácia pozývacím tokenom z webu aj
priamo z Android appky (MAS), Android notifikácie cez self-hosted ntfy bez Google/Element, hovory
cez TURN/TLS na 443 (sieť bez UDP), šifrované zálohy s obnovou a hardening servera. Všetky CI workflowy sú
zelené. Nič nie je nasadené (VPS ešte nie je). Cestou som našiel a opravil 14 chýb, z nich 5 by sa prejavilo
až v produkcii (TURN relay, push brány za nginx, aktualizácia webu, desktop OIDC, obnova na Linuxe).

## Stav po bodoch

| # | Bod | Stav |
|---|---|---|
| 1 | Presun projektu | ✅ `~/proj/psst` (submoduly OK, `git fsck` čistý); `~/psst-github-code.txt` zmazaný; `~/psst-keys` mimo repa, v `.gitignore`, v žiadnej git histórii. ⚠️ `~/Desktop/psst` som zmazať nesmel (pracovný adresár relácie, bezpečnostná kontrola) — zmažte ručne. |
| 2 | Registrácia na mobile | ✅ MAS 1.29 na `auth.macet.eu`, Synapse delegovaný, registrácia **len s tokenom**, bez e-mailu. Forky: „Create account" v Android aj iOS appke, OIDC metadáta na app.macet.eu. Overené: web 4/4, Android emulátor end-to-end, iOS simulátor (tlačidlo), OIDC registrácia klientov 5/5. |
| 3 | Notifikácie | ✅ ntfy na `ntfy.macet.eu` (predvolená brána v Android forku), Sygnal pre APNs (zapne sa po nahraní 1 súboru `.p8` + Team ID). Overené: Android dostal notifikáciu cez ntfy. iOS push neoverený (bez Apple účtu). |
| 4 | Prevádzka | ✅ `deploy.sh <IP> <email>` (pre-flight, hardening, všetko), hardening overený v Debian 12, šifrované zálohy + rotácia + obnova (lokálne aj CI), `healthcheck.sh`, `members.sh`, TURN/TLS 443 overený relay-only hovorom. |
| 5 | Stránky | ✅ `terms.html`, `privacy.html` (SK+EN, vecné: E2EE, metadáta, IP, žiadna analytika, kde sú dáta) na app.macet.eu, prepojené v MAS (súhlas pri registrácii), webe/desktope (Help & About, päta), Android a iOS. `--contact`/`--hosting` doplní kontakt. |
| 6 | Dokumentácia | ✅ `server/DEPLOY-CHECKLIST.md` (VPS, DNS, porty, čo dodáte), `server/README.md`, DECISIONS D29–D41, BUILD.md. |
| 7 | Prebuild | ✅ web, macOS, Android (lokálne, APK/AAB podpísané), Windows a iOS (CI). Všetky overené, artefakty v `dist/`, všetko pushnuté. Web je ako GitHub Release (stiahne ho deploy.sh). |

## Nájdené a opravené chyby

| # | Chyba | Príčina | Oprava |
|---|---|---|---|
| 1 | Hovor bez UDP nefunguje (ICE „failed") — **aj v produkcii** | vstavaný TURN LiveKit v Docker bridge sieti: relay adresa = `node_ip`, SFU sa k relay portom nedostane | coturn v host sieti, TURN REST údaje z LiveKit, relay len na IP servera; nginx SNI 443 → TLS → coturn |
| 2 | Push na ntfy/Sygnal by v produkcii nefungoval | v `compose.yml` chýbala pevná IP nginx a aliasy domén (úprava sa pôvodne neaplikovala) → `ip_range_whitelist` nesedel | `ipv4_address: 172.30.0.10` + aliasy chat/ntfy/auth |
| 3 | Po aktualizácii webu vracia app.macet.eu 404 | `fetch-web.sh` nahrádzal `app/` cez `mv` → bind mount nginx ukazoval na zmazaný adresár | rsync do existujúceho adresára |
| 4 | Desktop sa nevie prihlásiť ani registrovať cez MAS | redirect `eu.macet.psst:/…` porušuje politiku MAS (schéma = obrátená doména `client_uri`) | primárna schéma desktopu `eu.macet.app` (psst-web `fc25b970`) |
| 5 | Obnova zálohy na Linuxe: PostgreSQL ani Synapse neštartujú | `umask 077` pri obnove → zlé vlastníctvo/práva (macOS/virtiofs to maskoval) | chown cez postgres image, configy s `umask 022`; test obnovy pridaný do CI |
| 6 | MAS sa reštartuje dookola | šifrovací kľúč so znakom nového riadku | generovanie bez `\n` |
| 7 | `harden.sh` skončil po prvom UFW pravidle | apostrof v komentári UFW („Let's Encrypt") | text bez apostrofu; overené v Debiane vrátane idempotencie |
| 8 | Odblokovaný člen zostal „locked" | MAS pri `unlock-user` nezruší príznak v Synapse | `members.sh` volá aj Synapse admin API |
| 9 | Zablokovaní členovia chýbali v zozname | Synapse admin API ich bez `locked=true` nevracia | parameter doplnený |
| 10 | `backup.sh` po vytvorení archívu skončil chybou | `[ … ] && cp` a `ls` v prázdnom adresári pod `set -e`/`pipefail` | `if`, bezpečná rotácia |
| 11 | macOS desktop obsahoval starý web | nx vrátil build z cache (zmena `webapp.asar` nie je vstup) | `NX_SKIP_NX_CACHE=true` (BUILD.md) |
| 12 | Zoznam členov/tokeny sa nevypísali | `mas-cli` loguje výsledky na stderr, f-string so `\"` | parsovanie stderr, prepis formátovania |
| 13 | CI `server-smoke` volal neexistujúci prepínač | nové API `deploy.sh` | `--local-test`, nové domény, kontrola šifrovanej zálohy |
| 14 | Lokálny test desktopu zamrzol | dialóg kľúčenky macOS pri novom ad-hoc podpise | test s `--use-mock-keychain` |

## Výsledky testov (lokálny stack, docker compose cez colima)

| Test | Výsledok |
|---|---|
| Server smoke (`tests/server/run_local.py`): admin token cez MAS, tokeny, admin API len loopback, Synapse `/register` zablokovaný + MAS `prompt=create`, účty, federácia off, **E2EE DM**, **E2EE skupina**, .well-known + rtc_foci, MatrixRTC, LiveKit, kontajnery, app/call vhosty | **17/17** |
| Kanál + súbory (`extra_test.py`): verejný kanál len pre prihlásených, šifrovaný súbor a obrázok (SHA-256 zhoda) | **9/9** |
| OIDC klienti v MAS (`oidc_clients_test.py`): web, desktop, Android, iOS prijatí; cudzí klient odmietnutý | **5/5** |
| Registrácia tokenom cez web (`register-test.mjs`): platný jednorazový ✓, ten istý znova ✗, neplatný ✗, viacnásobný ✓ | **4/4** |
| **Registrácia z Android appky** (emulátor): Create account → MAS v Custom Tab → meno/heslo/súhlas → token → meno → súhlas → späť v appke, prihlásený | ✅ |
| **Android notifikácia cez ntfy**: pusher `https://ntfy.macet.eu/_matrix/push/v1/notify`, Synapse → ntfy 200, ntfy → psst, notifikácia „dana invited you to chat" | ✅ |
| Element Web naostro (`live-test.mjs`): login cez MAS, zamknutý homeserver, prijatá E2EE správa, žiadne požiadavky mimo *.macet.eu | **7/7** |
| macOS desktop (`desktop/live-test.mjs`): štart, chat.macet.eu bez zmeny, prihlásenie cez MAS, Create account | **6/6** |
| Hovor 1:1 cez MAS prihlásenie | **5/5** (médiá host/udp) |
| **Hovor len cez TURN/TLS 443** (Linux kontajner, relay-only politika) | **5/6 → po oprave kontroly OK**: 2 účastníci, médiá tečú, `relayProtocol=tls` |
| Šifrovaná záloha + obnova (lokálne): podpisový kľúč, 6 členov, 6 miestností, 7 MAS účtov, login po obnove | ✅ |
| Hardening (Debian 12 kontajner): admin `psst`, SSH len kľúčom, root vypnutý, UFW 7 pravidiel, fail2ban, unattended-upgrades, 2. beh, bez kľúča nezamkne | ✅ |
| `healthcheck.sh` (22 kontrol vrátane TURN/TLS handshake) | OK (1 varovanie: self-signed v teste) |
| CI: server-smoke (vrátane obnovy), Android (APK, AAB, emulátor), iOS (Xcode 27.2, simulátor), Web+Desktop (web, smoke, macOS, Windows) | **všetko zelené** |

## Artefakty (`~/proj/psst/dist/`, SHA256 aj v `dist/SHA256SUMS.txt`)

| Súbor | SHA-256 |
|---|---|
| `psst-web.tar.gz` (1.12.35-psst.dfee39dc, aj GitHub Release) | `8798187af68ae2e405d02fc1202d33c8930f35de3373ba74627db040b71168e4` |
| `desktop/psst-1.12.35-universal.dmg` | `ee143d552a653b3567945cb31ec23a419183c76c80d8519d7c47a341e85ef33f` |
| `desktop/psst-1.12.35-universal-mac.zip` | `084da5b3bdca7219fb99e27ebbc03fbc1c8fa328ceacd952fda7f05a11e589f6` |
| `desktop/psst-1.12.35-windows-setup.exe` | `78bf21f9eea9af4cb53ab21685eff637c2651e3781b8bf130c32cf69ba106045` |
| `desktop/psst-1.12.35-windows.msi` | `fef410a647ac25f1cfa6208bbcb3638ed483b82dfe34fbe2fb586d2c6632cc4b` |
| `android/psst-26.11.0-arm64-v8a.apk` | `9bc0ba4bdd53febc4a9126060c007ac0c093ea948d7ed8c3fc2cf88ef8b87441` |
| `android/psst-26.11.0-armeabi-v7a.apk` | `31dc5bc3aaca33d28efaf4eac0800756d0010c1f5eb4c59e536cde55f0e5950f` |
| `android/psst-26.11.0-x86_64.apk` | `f01515249bee50650b171785f31abe1bdaf509e4c41621d1a3f2ae7a4a628e72` |
| `android/psst-26.11.0.aab` | `a330c211e372e83d702c6efc90ec828aecf638500220a99e48de4c2e464bb42d` |
| `ios/psst-ios-simulator.app.zip` | `fa7d5c8215d86b16e0c916eb2b218518c57fa8d067db9ecdff78b01cb5defa3b` |

Android podpis: certifikát `3a6428cf51ee8f5e10e84fac5ca8a6b3c3b8c34d2674db0f2224d1d0097d3899` (v2+v3).
Forky: psst-web `fc25b970`, psst-android `297307c3`, psst-ios `678eb335`.

## Čo dodáte v deň nasadenia (detail: `server/DEPLOY-CHECKLIST.md`)

1. **VPS**: 2–4 vCPU, 4–8 GB RAM, 40–80 GB SSD, verejná IPv4, Debian 12/13 alebo Ubuntu 24.04, root cez SSH kľúč.
2. **DNS A** na IP servera: `chat`, `app`, `auth`, `call`, `ntfy`, `turn` .macet.eu (bez AAAA).
3. **Cloud firewall**: 22/tcp, 80/tcp, 443/tcp, 7881/tcp, 7882/udp, 3478/udp.
4. **Príkaz**: `sudo ./deploy.sh <IP> <email> --contact "…" --hosting "…"`; potom `members.sh admin`, `members.sh invite`,
   uložiť `secrets/backup.pass` mimo servera.
5. **iOS push** (neskôr): `AuthKey_<KEY_ID>.p8` do `server/secrets/apns/` + `--apple-team-id`.

## Zostávajúce otvorené veci

- `~/Desktop/psst` zmazať ručne; runtime simulátora iOS 18.0 (8 GB, SIP) zmazať po reinštalácii Xcode.
- Apple Developer účet (podpis iOS, APNs, universal links), Google Play Console, podpis desktopu (Developer ID, Windows certifikát).
- Na skutočnom VPS ešte neoverené: Let's Encrypt, pre-flight DNS, coturn s verejnou IP (logika aj pre NAT cloudy je pripravená).
- Android: člen musí mať appku **ntfy** (server `ntfy.macet.eu`, vypnutá optimalizácia batérie) — bez nej žiadne notifikácie na pozadí.
- Drobnosti: logo na súhlasnej stránke MAS sa zobrazí až s platným certifikátom; nízky kontrast bieleho textu na #38BDF8 tlačidlách.
