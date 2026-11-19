# PSST — rozhodnutia

Každé rozhodnutie: čo, prečo, dôsledok. Detailné rozhodnutia jednotlivých platforiem sú v
[docs/decisions/](docs/decisions/) a sú zhrnuté nižšie.

## Prostredie a stratégia

**D1 — Ťažké buildy bežia na GitHub Actions, nie lokálne.**
Lokálny stroj: Intel Mac (x86_64), macOS 15.7, **6,3 GB voľného miesta**, bez Dockeru, bez Android SDK,
Java len z `brew openjdk@17` (keg-only), Xcode 16.0. Build Element Web/Desktop (pnpm monorepo + Electron),
Element X Android (Gradle + SDK + NDK cache) aj Element X iOS (SPM, matrix-rust-sdk binárky) potrebuje
desiatky GB. Repo je verejné → runnery GitHub Actions (ubuntu/macos/windows) sú zadarmo a prostredie je
reprodukovateľné. Lokálne sa robí len to, čo sa zmestí: ikony, keystore, editácia forkov, dokumentácia.

**D2 — Forky ako samostatné GitHub forky + git submoduly v hlavnom repe.**
`georgonr/psst-web` (fork element-hq/element-web), `georgonr/psst-android` (fork element-x-android),
`georgonr/psst-ios` (fork element-x-ios). Úpravy sú na vetve `psst` založenej na najnovšom stabilnom tagu.
Prečo nie subtree: element-web má ~600 MB histórie; subtree by nafúkal hlavné repo a zlúčenia z upstreamu
sú cez fork + `git merge <tag>` priamočiarejšie. GitHub fork zároveň viditeľne zachováva AGPL pôvod.
Hlavné repo `georgonr/psst` drží ikony, server, CI a dokumentáciu; forky sú v `forks/*` ako submoduly.

**D3 — Žiadne samostatné repo psst-desktop.** `element-hq/element-desktop` je archivovaný; desktop bol
vrátený do monorepa element-web (`apps/desktop`). Fork `psst-web` preto pokrýva web aj desktop.

**D4 — Verzie upstreamov (najnovšie stabilné k 2026-11-13):** element-web **v1.12.35**,
element-x-android **v26.11.0**, element-x-ios **26.11.0** (tag `release/26.11.0`),
element-call **v0.28.2**, lk-jwt-service **v0.10.0**.

**D5 — CI workflowy sú v hlavnom repe**, nie vo forkoch. Forky obsahujú desiatky upstream workflowov
(publikovanie, Sentry, Localazy…), ktoré nechceme spúšťať; v hlavnom repe sa fork checkoutne na vetve `psst`.

**D6 — Overenie (bod 7) beží v efemérnych CI runneroch.** Docker lokálne nie je a na disku nie je miesto na VM
(colima). Runner `ubuntu-latest` má Docker, KVM pre Android emulátor a je to stále „lokálne" overenie,
nie nasadenie na server.

## Logo a ikony

**D7 — Piaty stĺpec (výška 8) má polomer 4, nie 6,5.** SVG pri `rx=6.5` na obdĺžniku 13×8 orezá `ry` na 4,
čím vznikne elipsa, nie zaoblený stĺpec. Polomer `min(6.5, h/2)` zachová „zaoblené konce" ako u ostatných.

**D8 — Generátor ikon bez závislostí.** Na stroji nie je rsvg/inkscape/ImageMagick/Pillow. `scripts/make-icons.sh`
volá čistý Python rasterizér (signed-distance funkcie zaoblených obdĺžnikov s analytickým anti-aliasingom),
ktorý **kreslí každú veľkosť z geometrie**, nič sa neprevzorkováva. `.icns` balí `iconutil`, `.ico` sa skladá
priamo (PNG záznamy 16–256). Android ikony sú VectorDrawable generované z tej istej geometrie.

**D9 — Varianty podľa platformy:** web/Windows/Linux/Android legacy = zaoblený štvorec ako master;
iOS, `apple-touch-icon`, PWA maskable a Android adaptívna ikona = pozadie cez celú plochu (OS si masku
robí sám; iOS ikony bez alfa kanála); macOS = mriežka Big Sur (dlaždica 824/1024, polomer 36/160 ≈ Apple 185/824).
Notifikačná a monochromatická ikona = plné biele stĺpce bez pozadia.

**D10 — Slovná značka** (`assets/psst-wordmark.svg`) má text „psst" ako geometrické ťahy (nie font), aby
nezávisela od písma; hrúbka ťahu 12 ladí so stĺpcami šírky 13.

## Podpisovanie

**D11 — Android release kľúč nikdy neopustí lokálny stroj.** Keystore je v `~/psst-keys` (mimo repa,
ignorovaný). CI stavia **nepodpísané** release APK/AAB a podpisujú sa lokálne skriptom
`scripts/android/sign-release.sh` (zipalign + apksigner, jarsigner pre AAB). Kľúč ani heslá sa nenahrávajú
do GitHub secrets — únik kľúča by znamenal stratu možnosti aktualizovať appku; lokálne podpisovanie je
jednoduchšia a bezpečnejšia hranica dôvery. Emulátorový test v CI používa jednorazový debug kľúč.

## Prierezové rozhodnutia počas práce

**D12 — Workflowy sú v `ci/workflows/`, nie v `.github/workflows/`.** Token `gh` účtu `georgonr` má scope
`repo`, `gist`, `read:org`, ale nie `workflow` — GitHub odmietne akýkoľvek push, ktorý mení `.github/workflows/*`.
Pridanie scope vyžaduje interaktívne prihlásenie v prehliadači (`gh auth refresh -s workflow`). V keychaine je aj
token iného účtu (`infomaxicz`) so scope `workflow` — **zámerne nepoužitý**, nie je to prístup vlastníka repa.
Aby sa dala pushnúť zvyšná práca, história bola prepísaná (len lokálne, pred pushom) tak, že workflowy ležia v
`ci/workflows/`; `scripts/enable-ci.sh` ich po pridaní scope jedným príkazom aktivuje a spustí.
Dôsledok: **žiadny klient ani serverový stack zatiaľ nebol skompilovaný/spustený** (viď REPORT.md).

**D13 — Kanály = verejné miestnosti a priestory v lokálnom adresári servera.** Federácia je vypnutá a registrácia
len cez tokeny, takže „verejná" miestnosť je viditeľná iba používateľom PSST. Web config povoľuje vytváranie
verejných miestností/priestorov (`UIFeature.allowCreatingPublicRooms/Spaces: true`), Synapse povoľuje publikovanie
do adresára (`room_list_publication_rules: allow`) a adresár nie je dostupný bez prihlásenia.

**D14 (nahradené D30) — Registrácia s tokenom prebieha na webe (app.macet.eu alebo desktop).** Element X (Android aj iOS)
podporuje vytvorenie účtu len cez Matrix Authentication Service (OIDC); stack MAS nepoužíva (jednoduchší provoz,
Synapse priamo vie `registration_requires_token`). Mobilné appky sa prihlasujú heslom k existujúcemu účtu.
Pozvánka = odkaz na `https://app.macet.eu/#/register` + token z `server/scripts/new-invite.sh`.

**D15 — App Links / Universal Links servíruje nginx na app.macet.eu.** `assetlinks.json` obsahuje SHA-256
odtlačok release certifikátu (verejný údaj) a `apple-app-site-association` čaká na `APPLE_TEAM_ID` v `server/.env`.

**D16 — Pracovné stromy forkov sú v hlavnom repe ako submoduly s `ignore = all`.** `~/Desktop` je synchronizovaný
s iCloudom a pri ~5 GB voľného miesta macOS odkladá súbory („dataless"); `git status` potom visí na tisícoch
súborov v `forks/web`. Zdrojom pravdy sú vetvy `psst` na GitHube.

**D17 (pre Android nahradené D32) — Push notifikácie bez Element/matrix.org infraštruktúry.** Android: len UnifiedPush (verejná gateway
`matrix.gateway.unifiedpush.org` alebo gateway distribútora, napr. ntfy) — bez distribútora chodia notifikácie len
pri otvorenej appke. iOS: push gateway nastavená na `https://chat.macet.eu`, ale Sygnal s APNs kľúčom nie je
súčasťou stacku (vyžaduje Apple Developer účet) → na iOS zatiaľ žiadne push notifikácie.

## Súhrn rozhodnutí po platformách

Plné znenie s dôvodmi: [web + desktop](docs/decisions/web-desktop.md) · [android](docs/decisions/android.md) ·
[ios](docs/decisions/ios.md) · [server](docs/decisions/server.md).

- **Web/Desktop:** config v `apps/web/psst/config.json` (CI ho kopíruje); homeserver napevno, `disable_custom_urls`;
  registrácia tokenom natívne (bez zmien kódu); bez PostHog/Sentry/rageshake/integrácií/máp/Jitsi; skupinové hovory
  len embedded Element Call; tmavá téma `custom-psst` s akcentom `#38BDF8` ako default; odkaz na zdroják v
  Help & About; desktop `appId eu.macet.psst`, URL schémy `eu.macet.psst` a `psst`, bez auto-updatera, Seshat
  ponechaný, nepodpísané buildy; upstream workflowy vo forku vypnuté.
- **Android:** zámok cez `DefaultEnterpriseService` (`accountProviderAllowList = [chat.macet.eu]`,
  `canConnectToAnyAccountProvider = false`) + spevnenie (ignorované `mobile.element.io` login linky, vypnutý
  Element Pro well-known); flavour `fdroid` (bez Firebase/Google služieb); analytika = noop modul; app links len
  `app.macet.eu`; release build nepodpísaný v CI, podpis lokálne (D11); ABI arm64, armv7, x86_64.
- **iOS:** `eu.macet.psst` + `.nse`, `.shareextension`, `group.eu.macet.psst`; žiadny `DEVELOPMENT_TEAM` v repe;
  `accountProviders = [chat.macet.eu]`, `allowOtherAccountProviders = false`; všetky analytické kľúče `nil`;
  mapy vypnuté; associated domains len `app.macet.eu`; odstránená migrácia z Element Classic; build v CI na
  `macos-26` s Xcode 27 (lokálny Xcode 16.0 nestačí).
- **Server:** jeden compose projekt, `./deploy.sh`; všetko v `server/data/`; federácia vypnutá na 3 úrovniach
  (bez listenera, nginx 404, bez 8448 navonok) s jedinou internou výnimkou pre OpenID userinfo (lk-jwt-service);
  E2EE predvolene vo všetkých miestnostiach; LiveKit `7881/tcp` + `7882/udp`, bez TURN; Element Call na
  `call.macet.eu`; admin API len na `127.0.0.1:8008` (SSH tunel).

## Build a overenie naostro (2026-11-13, druhá dávka)

**D18 — Repo presunuté do `~/psst` čistým klonom z GitHubu.** Proces stratil prístup k `~/Desktop` (TCC),
všetko bolo pushnuté, takže klon je ekvivalent presunu. Privátne vnorené submoduly Elementu
(`element-ios-enterprise`, `element-android-enterprise`) majú vo forkoch `update = none`, inak
`git clone --recurse-submodules` padá. Starú kópiu `~/Desktop/psst` treba zmazať ručne.

**D19 — Android emulátor s x86_64 image (API 33), nie arm64.** Intel Mac (HVF) arm64 system image nespustí.
API 33, lebo od API 34 sú systémové CA v APEX module a testovací self-signed certifikát sa nedá pridať do
`/system/etc/security/cacerts`. Testuje sa x86_64 split podpísaný rovnakým release kľúčom.

**D20 — JDK a Node mimo Homebrew.** Homebrew pre Intel Mac už nedodáva bottles (openjdk@21 by sa kompiloval
zo zdrojov aj s ~12 závislosťami). Temurin 21 a Node 24.22.0 sú oficiálne tarbally s overeným SHA-256 v `~/.local`.

**D21 — Lokálne overenie bez `/etc/hosts`.** Domény `*.macet.eu` sa mapujú na 127.0.0.1 len v testovacom
procese: Python (`socket.getaddrinfo`), Chromium/Electron (`--host-resolver-rules`), emulátor (`/system/etc/hosts`).
Systém ani produkčné domény sa tým nemenia; heslo správcu nebolo treba.

**D22 — Test-only limity prihlásení v Synapse.** Lokálne cez colima prichádzajú všetky požiadavky z IP brány
Dockeru, takže testovacie klienty zdieľajú `rc_login.address` (→ `M_LIMIT_EXCEEDED`). `compose.test.yml` pridáva
druhý config `templates/synapse/test-overrides.yaml`; produkcia ho nepoužíva (tam `x_forwarded` + reálne IP).

**D23 — `/widgets/` v nginx bez SPA fallbacku.** Embedded Element Call si pýta voliteľný
`widgets/element-call/config.json`; SPA fallback vracal `index.html` → JSON chyba → hovor visel na „Loading…".
Teraz 404 → Element Call použije predvolenú konfiguráciu. Skutočná produkčná chyba nájdená živým testom.

**D24 — Serverový default: každý člen sa môže pripojiť do hovoru.** `default_power_level_content_override`
(všetky presety) zachováva Synapse defaulty a nastavuje `org.matrix.msc3401.call.member` a `m.rtc.member` na 0.
Element Web to robí vo svojich miestnostiach sám, miestnosti od iných klientov/botov by inak hovor
nepovolili („You do not have permission to start video calls").

**D25 — Android: `ndk.abiFilters` len pre AAB.** Kombinácia s `splits.abi` zhadzovala konfiguráciu pri samostatnom
APK builde. APK = 3 splity (arm64-v8a, armeabi-v7a, x86_64), AAB obsahuje tie isté 3 ABI.

**D26 — iOS CI na runneri `xcode-27`, simulátor len arm64.** GitHub `macos-26` má najviac Xcode 26.6, upstream
26.11.0 vyžaduje Xcode 27 (GitHub ho ponúka ako public preview pod labelom `xcode-27`, rovnako ako upstream).
matrix-rust-sdk nemá x86_64 simulátorový slice → `ARCHS=arm64`.

**D27 — Kontrast prihlasovacej stránky.** Ľavý stĺpec s logom bol len rozmazané pozadie (sivý), biela slovná
značka bola zle čitateľná → tmavý poloprehľadný podklad `rgb(2,6,23,.72)` (`_AuthHeader.pcss`, `PSST:`).

**D28 — macOS desktop universal (x64 + arm64), nepodpísaný (ad-hoc).** Postavený lokálne na Intel Macu; jedna
appka pre Intel aj Apple Silicon. Gatekeeper pri prvom spustení vyžaduje pravý klik → Otvoriť.

## Server pripravený na nasadenie, registrácia na mobile, notifikácie (2026-11-13, tretia dávka)

**D29 — Projekt v `~/proj/psst`.** Presunutý z `~/psst`; v repe neboli absolútne cesty (len v dokumentácii).
`~/Desktop/psst` je pracovný adresár relácie — zmazanie zablokovala bezpečnostná kontrola, treba ho zmazať ručne.

**D30 — Matrix Authentication Service (MAS 1.29) na `auth.macet.eu`.** Element X vie vytvoriť účet len cez OIDC
(MAS). Synapse deleguje autentifikáciu (`matrix_authentication_service`, `enable_registration: false`,
`password_config.enabled: false`). Registrácia heslom je v MAS zapnutá, ale **vyžaduje registračný token**
(`password_registration_token_required`), e-mail sa nevyžaduje (žiadny SMTP). Pozvánky: `members.sh invite`.
Prihlásenie starších klientov ide cez MAS compat endpointy (`/_matrix/client/*/login|logout|refresh` → MAS).
Nahrádza D14.

**D31 — OIDC klienti: všetky appky majú `client_uri = https://app.macet.eu`, natívne redirect schémy `eu.macet.app`.**
Politika MAS vyžaduje, aby vlastná schéma bola obrátená doména `client_uri` — `eu.macet.psst:/…` (pôvodná
desktopová) MAS odmietol, preto desktop aj iOS používajú `eu.macet.app` ako primárnu schému (Android už mal).
`allow_host_mismatch: true` povoľuje metadáta (tos/policy/logo) na inom hoste. Overuje `tests/server/oidc_clients_test.py`.

**D32 — Android notifikácie: self-hosted ntfy (`ntfy.macet.eu`), predvolená Matrix push brána vo forku.**
ntfy povoľuje anonymne len témy `up*` (`auth-default-access: deny-all`), web UI aj registrácia sú vypnuté.
Člen potrebuje appku ntfy s *Default server* `https://ntfy.macet.eu` a vypnutou optimalizáciou batérie
(Android 13 inak nedovolí ntfy spustiť službu na pozadí — overené v emulátore). Synapse posiela len `event_id`
(`push.include_content: false`). Nahrádza D17 pre Android.

**D33 — iOS notifikácie: Sygnal (APNs) ako compose profil `apns`.** Zapne sa, keď deploy.sh nájde
`secrets/apns/AuthKey_<KEY_ID>.p8` a pozná Team ID (`--apple-team-id`); app_id `eu.macet.psst.ios.prod`
(production) a `.dev` (sandbox), topic `eu.macet.psst`. Push brána je `https://chat.macet.eu/_matrix/push/v1/notify`.

**D34 — Push brány sú za nginx; Synapse má v `ip_range_whitelist` len pevnú IP nginx (172.30.0.10).** Synapse
predvolene blokuje privátne rozsahy (ochrana pred SSRF); povolenie jedinej adresy reverznej proxy je minimálne.
Pevná IP + aliasy domén v Docker sieti chýbali (úprava compose sa pôvodne neaplikovala) — opravené a overené.

**D35 — TURN cez coturn v host sieti, nie vstavaný TURN LiveKit.** LiveKit ohlasuje relay adresu ako
`node_ip:port`; v Docker bridge sieti sa SFU k relay soketom nedostane (porty nie sú publikované) — test to
potvrdil (ICE páry „failed"). coturn v host sieti relayuje na IP servera, `denied-peer-ip` všetko okrem IP
servera (nie je otvorený relay), dočasné prihlasovacie údaje generuje LiveKit (TURN REST, `turn_servers.secret`).
**TURN/TLS na 443:** nginx `stream` rozlišuje SNI — `turn.macet.eu` ukončí TLS a pošle TURN-over-TCP na coturn
(brána Docker siete 172.30.0.1:3478, UFW povolené len z 172.30.0.0/24); ostatné domény idú na interný HTTPS
server 127.0.0.1:8443 s PROXY protocol (zachová IP klienta). Hovor s politikou „len relay" overený (médiá
tečú cez `relayProtocol=tls`) v Linux kontajneri s dôverou v testovací certifikát — WebRTC overuje TLS
certifikát TURN aj s `--ignore-certificate-errors`.

**D36 — `deploy.sh <IP> <email>` robí všetko:** pre-flight (Linux/root, inštalácia Dockeru na Debian/Ubuntu,
DNS 6 subdomén → IP cez 1.1.1.1, porty 80/443/7881/7882/3478, disk ≥ 20 GB, RAM), hardening, tajomstvá,
konfigurácie, PSST web z GitHub Release, štart, databáza `mas`, Let's Encrypt pre 6 domén, cron (zálohy 03:17,
healthcheck každých 10 min). `--contact`/`--hosting` vyplní právne stránky. `--local-test` = lokálny test.

**D37 — Hardening (scripts/harden.sh):** admin `psst` s kľúčmi roota, `sudo` bez hesla (nemá heslo), SSH len
kľúčom + `PermitRootLogin no` **len ak má admin kľúč** (inak varovanie, nikoho nezamkne), UFW, fail2ban (sshd),
unattended-upgrades s reštartom o 04:30. Overené v Debian 12 kontajneri vrátane idempotencie.

**D38 — Zálohy šifrované openssl AES-256-CBC + PBKDF2 (600 000 iterácií) heslovou frázou `secrets/backup.pass`.**
openssl je všade (žiadna ďalšia závislosť). Fráza sa nezálohuje (archív by inak nebol chránený) — deploy.sh
vyzve uložiť ju mimo servera. Rotácia 7 denných / 4 týždenné / 6 mesačných, overenie dešifrovania po každej
záloze, voliteľný rsync mimo servera. Obnova overená lokálne aj v CI (zhoda podpisového kľúča, účty, miestnosti).

**D39 — PSST web sa na server dostane cez GitHub Release** (`releases/latest/download/psst-web.tar.gz`), nie cez
`gh` CLI (na VPS nie je). Release obsahuje len web distribúciu; podpísané APK a desktopové inštalátory sa
nezverejňujú (zostávajú v `dist/` a CI artefaktoch). `fetch-web.sh` synchronizuje obsah do existujúceho `app/`
— nahradenie adresára (`mv`) rozbilo bind mount nginx (404), opravené.

**D40 — Právne stránky (SK + EN) servíruje nginx z `templates/app/legal/`** — nezávisle od web buildu, na
`app.macet.eu/terms.html` a `/privacy.html`; odkazujú na ne MAS (súhlas pri registrácii), web/desktop (Help &
About, päta prihlásenia), Android a iOS (Nastavenia → About/Legal).

**D41 — Desktop build bez nx cache (`NX_SKIP_NX_CACHE=true`).** nx považoval balenie desktopu za nezmenené aj po
výmene `webapp.asar` a vrátil starý dmg z cache (so starým webom). CI cache nepoužíva; lokálne je to nutné.

## Produkčné nasadenie na PSST (Hetzner CX33, 204.168.160.131) — 2026-11-13/14

**D42 — Produkcia beží len na 4 doménach: chat, app, call, push.macet.eu.** DNS (webglobe) má A záznamy len pre
tieto štyri mená; `auth.`, `ntfy.`, `turn.macet.eu` padajú na wildcard starého servera (195.181.248.25) a zmeniť
ich nevieme. Preto:
- **MAS** beží na ceste `https://chat.macet.eu/auth/` (MAS `listeners[].prefix: /auth`, `public_base`/`issuer`
  s cestou). Klienti ho nachádzajú dynamicky cez `/_matrix/client/v1/auth_metadata` — appky netreba meniť.
  Compat `/_matrix/client/*/login|logout|refresh` nginx prepíše na `/auth/_matrix/…`. Synapse volá MAS na
  `http://mas:8080/auth/`. Samostatná subdoména sa dá zapnúť v `.env` (`AUTH_DOMAIN=auth.… AUTH_PREFIX=`).
- **ntfy (UnifiedPush + Matrix push brána)** je na `push.macet.eu` (zadanie). Android fork: predvolená push
  brána `https://push.macet.eu/_matrix/push/v1/notify` → nový APK.
- **TURN/TLS na 443 zdieľa doménu `call.macet.eu`** s Element Call. nginx stream rozhoduje podľa SNI **a ALPN**:
  SNI call.macet.eu bez ALPN h2/http/1.x → TURN (coturn), inak HTTPS. Prehliadače vždy posielajú ALPN, TURN
  klient WebRTC nie. `TURN_DOMAIN=turn.…` v `.env` vráti samostatnú doménu.
- **TURN/UDP 3478 sa nepublikuje** — politika firewallu je len 22, 80, 443, 7881/tcp, 7882/udp. coturn počúva
  len na bráne Docker siete (172.30.0.1) pre nginx; LiveKit klientom ponúka iba `turns:call.macet.eu:443`.

**D43 — Docker nesmie obísť UFW.** `daemon.json`: `"ip": "127.0.0.1"` (port bez IP sa publikuje len na loopback),
`no-new-privileges`, `live-restore`, `userland-proxy: false`, `icc: false`, json-file 20m×5. Verejné porty sú
v compose explicitne `0.0.0.0:` (nginx 80/443, LiveKit 7881/tcp, 7882/udp). Navyše reťazec `DOCKER-USER`
(v `/etc/ufw/after.rules`) púšťa z eth0 do kontajnerov len nové spojenia na 80, 443, 7881/tcp, 7882/udp —
aj omylom publikovaný port zostane zvonka zatvorený. IPv6: AAAA záznamy nie sú, Docker IPv6 nemá → na IPv6
je dostupný len SSH.

**D44 — Hardening servera robí operátor mimo deploy.sh, deploy beží s `--skip-harden`.** Server už má
prísnejší hardening (`AllowUsers deploy`, sysctl, AIDE, ClamAV, auditd, noexec /tmp, swap — viď
`~/proj/psst-server-notes.md`); `harden.sh` by vytvoril ďalšieho používateľa a otvoril 3478/udp. Cron
(zálohy + healthcheck) teraz deploy.sh inštaluje aj pri `--skip-harden` (okrem `--local-test`).
`harden.sh` už 3478/udp neotvára.

**D45 — Žiadne externé notifikácie zo servera.** AIDE (denne), ClamAV (týždenne), healthcheck (systém denne +
stack každých 10 min) píšu len do `/var/log/psst/*.log` a `/var/log/psst-*.log` (logrotate týždenne, 12×).

**D46 — TLS: Mozilla intermediate.** nginx bez `ssl_ciphers` ponúkal v TLS 1.2 aj CBC/CAMELLIA/ARIA (testssl: LUCKY13).
Teraz len ECDHE + AES-GCM/ChaCha20 (HTTPS aj TURN/TLS listener), krivky X25519/P-256/P-384, TLS 1.2+1.3, HSTS.
SSL Labs: chat/app/push A+, call A (klient bez ALPN dostane TURN/TLS listener bez HSTS — dôsledok D42).
`deploy.sh` renderuje konfigurácie na mieste (bind mount jedného súboru) a reštartuje služby so zmenenou konfiguráciou.

## Android notifikácie cez Google FCM (2026-11-14, piata dávka)

**D47 — Android: FCM namiesto UnifiedPush/ntfy (nahrádza D32).** Zadanie: má stačiť jedna appka. UnifiedPush
vyžadoval druhú appku (ntfy) a vypnutú optimalizáciu batérie. Push brána zostáva **náš Sygnal**
(`https://chat.macet.eu/_matrix/push/v1/notify`, FCM HTTP v1), nie Element/matrix.org. Cena: Google vidí push token
zariadenia, čas notifikácie, ID udalosti a miestnosti a počet neprečítaných — obsah (ani šifrovaný) cez Google nejde
(pusher `event_id_only` je vo forku napevno + `push.include_content: false`). Stránka Ochrana súkromia to uvádza.

**D48 — Firebase projekt `psst-macet` je minimálny.** Vytvorený cez gcloud + Firebase Management API (účet
muckajur@gmail.com, bez Google Analytics). Po `addFirebase` Google zapol ~40 API — vypnuté všetko okrem
`fcm`, `fcmregistrations`, `firebaseinstallations`, `firebase` a správy projektu (IAM, serviceusage, logging…).
„Browser key" zmazaný; Android API kľúč obmedzený na balík `eu.macet.psst` + SHA-1 release certifikátu a len na
API `fcmregistrations` + `firebaseinstallations`. Service account `sygnal-fcm@…` má jedinú rolu
`roles/firebasecloudmessaging.admin` (najužšia predpripravená rola na odosielanie).

**D49 — Hodnoty Firebase sú vo forku ako `firebase.xml`, bez google-services pluginu.** Rovnako to robí upstream;
`google-services.json` je len v `~/psst-keys`. App ID, sender ID a API kľúč sú verejné údaje (sú v každom APK),
kľúč chráni obmedzenie z D48. Kľúč service accountu je len na serveri (`secrets/fcm/service-account.json`, 600 root —
Sygnal beží v kontajneri ako root) a v `~/psst-keys/sygnal-fcm-sa.json`; nikdy v repe.

**D50 — Variant `gplay` je predvolený a jediný distribuovaný; UnifiedPush modul sa nebalí.** V APK overené:
žiadne `org/unifiedpush`, žiadny Firebase Analytics/Crashlytics/measurement SDK (analytika bola z Firebase
závislostí vylúčená už v upstreame, manifest má `firebase_analytics_collection_deactivated`). Variant `fdroid`
zostáva v kóde, ale nemá žiadny push provider.

**D51 — ntfy odstránený zo servera; `push.macet.eu` len presmeruje (301) na app.macet.eu**, staré UnifiedPush
endpointy vracajú 410. Doména ostáva v certifikáte (DNS záznam existuje, netreba meniť certifikát ani DNS).
Sygnal má compose profil `sygnal` (FCM a/alebo APNs podľa nahraných kľúčov), zvonka je dostupný len cez nginx;
port 5000 je iba v Docker sieti. Zálohy už neobsahujú ntfy, obsahujú FCM kľúč (v `secrets/`).

**D52 — Dôsledok pre existujúce inštalácie:** APK z 13. 11. (UnifiedPush) po tejto zmene nedostáva notifikácie —
treba nainštalovať nové APK (rovnaký podpis, dá sa nainštalovať cez staré). `versionCode` zostal 202611004.

**D53 — Notifikácie na fyzických telefónoch (2026-11-14): server bol v poriadku, chyba bola v správaní appky.**
Diagnostika: Synapse doručil každý push (Android → náš Sygnal → FCM, iPhone → brána Elementu na matrix.org), obe
brány vrátili 200 bez odmietnutia a telefón sa po každom pushi do sekundy ozval na server. Firewall ani egress nič
neblokuje, push pravidlá sú predvolené. Android do 08:13 nemal žiadny funkčný pusher (starý ntfy zanikol s ntfy, D52).
V psst-android (fork) dve zmeny voči upstream Element X 26.11:
- kanál pre správy má `IMPORTANCE_HIGH` (upstream `DEFAULT` = zvuk, ale žiadne vyskakovacie okno) a nové ID
  `PSST_NOISY_NOTIFICATION_CHANNEL_ID_V3` — starý kanál sa zmaže, čím sa vynulujú aj stlmené nastavenia z inštalácie,
- prichádzajúci hovor zvoní, ak appka do 12 s (upstream 3 s) zistí aktívny hovor v miestnosti; ak to nestihne,
  zvoní, kým samotné zvonenie neexpiruje (max. 30 s). Na lacných telefónoch appka spustená pushom 3 s nestihla
  a hovor sa zobrazil len ako bežná notifikácia „📹 Incoming call".

**D54 — Verzovanie artefaktov.** Číslo buildu = `github.run_number` CI workflowu danej platformy (web a desktop
zdieľajú `web-desktop.yml`), iOS = posledný build v TestFlighte + 1 (Apple vyžaduje rastúce číslo). Dátum = deň buildu
v UTC. Názov `psst-<platforma>-<RRRRMMDD>-b<N>[-<abi>].<prípona>`; ABI skrátené na `arm64`/`armv7`/`x86_64`.
Číslo a dátum sú vidieť v appke (About). Android `versionCode = (21 000 000 + N) × 10 + ABI` — nad pôvodnou
schémou Element X (`202611xxx`), aby sa každé nové APK nainštalovalo cez staré; `versionName` `26.11.0-bN (RRRR-MM-DD)`.
Lokálny build bez CI má `b0` a `publish.py` ho odmietne, takže dve rôzne verzie s rovnakým číslom nevzniknú
(re-run toho istého behu CI postaví rovnaký commit s rovnakým číslom). `dist/<platforma>/` = len najnovšia verzia,
staršie v `dist/archive/<platforma>/`, prehľad `dist/LATEST.md` (generuje `scripts/release/publish.py`).

**D55 — iOS: príprava TestFlightu.** Tím `MHV67VMY8T` je zdieľaný → len pridávame a meníme výhradne objekty „psst …"
(bundle ID `eu.macet.psst`, `.nse`, `.shareextension`; distribučný certifikát `K2778R2L24`, súkromný kľúč len
v `~/psst-keys/ios-dist`; profily „psst AppStore <bundle>"). Apple cez API nedovolí vytvoriť App Group ani záznam
appky (`apps` nemá CREATE) a Xcode v CI odmieta API kľúč pri automatickom podpisovaní → tieto dva kroky robí človek
raz ručne (`scripts/ios/README.md`), všetko ostatné `scripts/ios/release-testflight.sh`. Podpisovanie manuálne
(certifikát + profily v GitHub secrets), build na runneri `xcode-27`, upload `altool` s API kľúčom.
Entitlementy, ktoré profil nemá (NSE filtering — vyžaduje súhlas Apple; Communication Notifications — len cez portál),
workflow pred buildom vynechá; App Group je povinná a bez nej build skončí chybou.
**Exportná zhoda:** `ITSAppUsesNonExemptEncryption = false` (ako Element X) — appka používa len štandardné
algoritmy (AES, Curve25519, SHA-2 v Olm/Megolm/vodozemci a TLS), nič proprietárne, a celý kryptografický kód je
verejne dostupný open source (AGPL, GitHub). Takýto softvér podľa US EAR §734.3(b)(3)/§742.15(b) nepodlieha
kontrole a od 2021 nevyžaduje ani oznámenie BIS/NSA; žiadny výročný self-classification report.
Povinnosť voči úradom pre TestFlight a EÚ teda nevzniká. **Pred verejným vydaním v App Store vo Francúzsku** treba
overiť, či netreba ohlásenie ANSSI (Apple sa pri distribúcii vo Francúzsku pýta na francúzsku deklaráciu).
**APNs:** Sygnal `eu.macet.psst.ios.prod` (production) a `.ios.dev` (sandbox), topic `eu.macet.psst`, kľúč
`NVM823LAXK` na serveri v `secrets/apns/` (600 root), overené odpoveďou APNs `BadDeviceToken` na falošný token.
`apple-app-site-association` už obsahuje `MHV67VMY8T.eu.macet.psst`.

**D56 — Administračná stránka https://app.macet.eu/admin.** Malá služba `server/admin` (FastAPI, server-rendered
HTML bez externých skriptov, kontajner `admin` ako UID 10001, dostupný len cez nginx na app doméne — žiadna nová
DNS ani port). Prihlásenie výhradne cez MAS: statický dôverný klient `01KPSSTADM1N0000000000000A`
(authorization code + PKCE, scope `openid`); prístup len pre účty s admin právom v MAS (`can_request_admin`, teraz
`geo`), servisný `psstadmin` vylúčený, ostatní dostanú 403; admin právo sa overuje znova každých 5 min.
Ten istý klient má cez `policy.data.admin_clients` prístup k MAS admin API (client_credentials, `urn:mas:admin`)
— pozvánky sú priamo **registračné tokeny MAS** (tie isté ako `members.sh invite` a registrácia v appkách).
Kto sa ktorou pozvánkou zaregistroval: read-only rola `psst_admin_ro` s SELECT len na `user_registrations` a
`user_registration_tokens`. Blokovanie = MAS lock/unlock + príznak `locked` v Synapse (ako `members.sh`); `geo`,
servisný účet ani adminov zablokovať nejde. Bezpečnosť: session len na serveri (cookie = náhodné ID, Secure,
HttpOnly, SameSite=Strict, Path=/admin, max. 30 min, 15 min nečinnosti), CSRF token vo formulároch + kontrola
Origin (preto `Referrer-Policy: same-origin` — pri `no-referrer` posiela prehliadač `Origin: null`), rate limiting
(120 GET / 20 POST / 10 prihlásení za minútu na IP), prísna CSP, audit log `data/admin/audit.log` (kto, čo, kedy,
IP; JSON lines, zálohuje sa), poznámky „pre koho" v `data/admin/notes.sqlite`. Tajomstvá (klient, DB heslo,
Synapse admin token) len v `secrets/` na serveri, kontajner dostáva kópie `secrets/admin-run/` (400).
Kódy pozvánok `XXXX-XXXX` (bez zameniteľných znakov). MAS obmedzuje počet registrácií z jednej IP (ochrana proti
zneužitiu) — ponechané.

**D57 — Prichádzajúci hovor na zamknutom telefóne ako bežný hovor.** Príčina: od Androidu 14 smie appka zobraziť
hovor cez celú zamknutú obrazovku (rozsvietený displej, volajúci, Prijať/Odmietnuť) len s povolením „Upozornenia
na celú obrazovku" (`USE_FULL_SCREEN_INTENT`). Samsung ho appkám nainštalovaným z APK nechá vypnuté → systém ukáže
len notifikáciu na zamknutej ploche. Upstream Element X na to upozorní iba prehliadnuteľným bannerom v zozname
konverzácií. Oprava v psst-android: (1) `IncomingCallActivity` má `showWhenLocked`/`turnScreenOn` v manifeste aj cez
API 27+ (staré window flagy sú na nových Androidoch nespoľahlivé); hovor sa zobrazí a prijme bez odomknutia,
`ElementCallActivity` už nad zámkou beží. (2) `PsstCallReadiness`: pri prvom spustení a po každej aktualizácii, ak
povolenie chýba, jedna veta + priamo obrazovka `ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT`; potom žiadosť o výnimku
z optimalizácie batérie (`ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`, povolenie appka už mala). (3) Keď zazvoní
hovor bez povolenia: notifikácia s priamym odkazom na nastavenie a pri ďalšom otvorení appky výzva znova.
Notifikácia hovoru už bola správna (CallStyle, kanál „Ringing calls" `IMPORTANCE_MAX` s vyzváňaním,
`fullScreenIntent` na `IncomingCallActivity`) — bez zmeny. **Self-managed ConnectionService nie:** ani s ním
Android nezobrazí hovor nad zámkou inak než cez ten istý full-screen intent (vyžaduje rovnaké povolenie), pridal by
len Bluetooth/auto integráciu za cenu veľkého zásahu do Element X (ten telecom integráciu nemá) — samotný problém
by nevyriešil.

**D58 — Prihlásenie nového zariadenia QR kódom.** Synapse `experimental_features`: `msc4108_enabled: true`
(verzia 2024) a `msc4388_mode: open` (bezpečný kanál pre novšie klienty); MAS už podporoval device-code grant.
„open" = rendezvous môže založiť aj ešte neprihlásené zariadenie; dáta sú krátkodobé, šifrované medzi zariadeniami
a obmedzené rate limitom. Overené na produkcii: web „Link new device → Show QR code" → Android (nové zariadenie)
naskenuje → 2-ciferný kód na webe → overovací kód a „Grant access" v MAS → Android prihlásený. Kontakt cez QR:
Element X nemá vlastný skener kontaktov; QR v dialógu „Share" na webe/desktope je odkaz `https://app.macet.eu/#/user/…`
(`permalink_prefix`), ktorý Android po naskenovaní fotoaparátom otvorí priamo v psst (App Links overené) na profile
s tlačidlom „Message" — bez zmeny.

**D59 — Stránka na stiahnutie https://app.macet.eu/download.** Statická stránka generovaná na serveri
(`server/scripts/downloads.py`, bez JS, anglicky), súbory v `/opt/psst/server/downloads` (mimo `data/`, nezálohujú
sa — sú v `dist/archive`). Nahráva výhradne používateľ `psst-dl` cez SSH kľúč s forced command (nič iné nespustí),
ten istý kľúč používa lokálny podpisový skript Androidu aj CI (GitHub secret, hostiteľský kľúč pripnutý). Server
overí SHA-256 prijatého súboru, odmietne starší build a zmaže predošlú verziu; klient potom súbor stiahne cez HTTPS
a SHA-256 porovná — inak build zlyhá. Kontrola „stránka nie je pozadu" lokálne aj v CI (`release/latest.json`
v gite). Na prihlasovacej obrazovke webu/desktopu odkaz „Download apps" (`branding.auth_footer_links`).
**Aktualizácie desktopu:** Elementov updater (Squirrel/packages.element.io) je vypnutý (žiadne `update_base_url`)
a pre MSI ani nepodpísaný macOS by nefungoval; namiesto neho appka po štarte a raz denne prečíta
`/download/latest.json` a pri novšom builde ukáže systémovú notifikáciu s odkazom na stránku.

**D60 — Windows desktop E2E na `windows-latest`.** Workflow *Desktop Windows E2E* nainštaluje MSI (msiexec /qn),
spustí appku s CDP, prihlási sa cez MAS (URL zachytená v rendereri, callback vrátený appke), partner je Element Web
v headless Chromiu (E2EE na oboch stranách skutočné klienty). Testovacie účty sú **nové pre každý beh**
(`scripts/desktop/e2e-accounts.sh create|cleanup`): po druhom prihlásení Element vyžaduje potvrdenie identity
(iné zariadenie/recovery key), čo je správne pre ľudí, ale blokuje opakované automatické behy. Nájdené a opravené:
About na desktope ukazoval len verziu Electronu bez buildu (teraz `1.12.35-bN (dátum)`); Android `versionName`
so zátvorkami rozbíjal User-Agent (názov zariadenia „psst on 2026-11-15) (…") → teraz `26.11.0-bN+RRRR-MM-DD`.

## Tri chyby z telefónov a audit funkcií (2026-11-16, desiata dávka)

**D61 — Android: sprievodca nastavením a kanál správ.** (1) Nastavenia sa otvárali s `FLAG_ACTIVITY_NEW_TASK`;
One UI ich potom nechá v úlohe aplikácie Nastavenia a „Späť" nevráti do psst, takže ďalší krok neprišiel (na AOSP
sa to neprejaví). Teraz sa otvárajú v úlohe psst (bez NEW_TASK) a `MainActivity.onResume` po návrate sám zistí
skutočný stav a ukáže ďalší chýbajúci krok: upozornenia + vyskakovacie okno kanála správ → upozornenia na zamknutej
obrazovke (globálny prepínač → systémová stránka Upozornenia) → celoobrazovkové hovory → batéria. Každý krok
najviac raz za verziu; „Neskôr" pokračuje ďalším krokom hneď. (2) Kanál správ dostal nové ID `PSST_MESSAGES_V4`
(Android si pamätá nastavenia kanála, vrátane ručne zníženej dôležitosti), `IMPORTANCE_HIGH`, názov „Správy/
Messages"; staré `PSST_NOISY_*_V3` a `DEFAULT_NOISY_*_V2` sa pri štarte mažú. `lockscreenVisibility` appka nastaviť
nemôže (Android ju pri vytvorení kanála nahradí „bez prepísania" = rozhoduje nastavenie telefónu), preto ju
kontroluje sprievodca. Notifikácia je `CATEGORY_MESSAGE` s `MessagingStyle` (upstream). Overené v emulátore
(Android 14): vyskakovacie okno, zamknutá obrazovka, aktualizácia b13 → b18 → b20 (starý kanál zmazaný).
Samsung One UI má navyše vlastné „Štýl vyskakovacích upozornení" a „Upozornenia na zamknutej obrazovke → Skryť obsah"
— tie appka nevidí ani nezmení; na skutočnom A05 treba overiť.

**D62 — Neoverená relácia na webe/desktope sa nesmie tváriť ako overená.** Príčina zle zobrazeného stavu: keď
iné zariadenie resetuje digitálnu identitu (Element X: „Can't confirm?" → reset — v databáze to vidno aj na dvoch
skutočných účtoch), existujúca relácia na počítači prestane byť overená, ale upstream Element ukáže len odložiteľný toast
„Verify this device" (Later/Continue) a appka ďalej normálne funguje — vyzerá ako overená. `force_verification`
upstream platí len pri čerstvom prihlásení. Fork: s `force_verification` sa zablokuje aj existujúca relácia,
ktorá stratila overenie — pri štarte (`shouldForceVerification`) aj počas behu (DeviceListener →
`psst_force_verification` → obrazovka „Confirm your digital identity"). Nasadené (web b13, desktop b15) a overené
na produkcii: reset identity z Androidu → web sa okamžite prepne na potvrdenie identity → „Use another device" →
telefón (otvorený) → emoji → späť v appke. Skutoční používatelia: všetky ich aktívne webové/desktopové relácie sú
podpísané aktuálnym kľúčom (overené read-only v DB), zmena ich nezablokuje.

**Chýbajúca notifikácia o žiadosti o overenie (bez zmeny kódu — obmedzenie protokolu a upstreamu).** Žiadosť
o overenie zariadenia je *to-device* správa; Matrix push (pravidlá aj Sygnal) existuje len pre udalosti
v miestnostiach, MSC na push to-device správ neexistuje. Element X ju preto zobrazí len pri bežiacej synchronizácii
(otvorená appka) a s limitom 1 minúta; staršiu žiadosť zahodí. Neoverené nové zariadenie Element X navyše vôbec
neregistruje push (až po overení). Postup pre ľudí: overovať tak, že **na novom zariadení** zvolíte „Use another
device" a **na starom zariadení appku otvoríte**. Možné rozšírenie (navrhnuté, nenasadené): malá služba za nginx
(`mirror` na `PUT /sendToDevice/m.key.verification.request/…`) pošle cez Sygnal „budíček" na pushery cieľového
používateľa a fork Androidu zobrazí notifikáciu „Žiadosť o overenie — otvorte psst"; iOS NSE by bez entitlementu
na filtrovanie ukázal len všeobecný text.

**D63 — Android: kontrola novej verzie.** APK sa inštaluje mimo obchodu, nič neupozorní na novší build (zastarané
APK boli príčinou výpadku push v D52). Appka najviac raz za 12 h (pri `onResume`, keď sprievodca nič neukazuje)
prečíta verejné `https://app.macet.eu/download/latest.json` (bez cookies a údajov o používateľovi); ak je
`android.build` vyšší než nainštalovaný (`versionCode/10 − 21 000 000`), ponúkne „Stiahnuť" → stránka na stiahnutie.
Ten istý build ponúkne znova najskôr o 3 dni. iOS rieši aktualizácie TestFlight/App Store.

**D64 — Audit funkcií (docs/FEATURE-MATRIX.md).** Testuje sa na produkcii, výhradne na nových testovacích účtoch
(`qa-au*`), ktoré sa po audite deaktivujú; skutočných používateľov ani ich miestnosti sa test nedotkne. Web:
`scripts/audit/web-audit.mjs` (Playwright, partner = ďalšia webová relácia). Windows/macOS: workflow *Desktop audit*
nainštaluje MSI/DMG na GitHub runneri a spustí rovnakú sadu (`features.mjs`) cez CDP; hovor s blokovaným UDP cez
firewall OS. Android: emulátor API 34 s Google Play services, ručne riadený cez adb/uiautomator + webový partner
(`scripts/audit/call-partner.mjs` pre hovory), blokované UDP cez iptables. iOS: workflow *iOS audit* — XCUITest
`PsstAuditTests` v simulátore + partner Element Web (`ios-partner.mjs`); podpísaný build nie je (zmluva v App Store
Connect), takže bez APNs, kamery a mikrofónu. Prihlasovacie údaje testovacích účtov len ako šifrované GitHub
secrets, po audite zmazané. Bunka „funguje" len po skutočnom teste.

**D65 — Server: adresár členov, nešifrované verejné kanály.** (1) `limit_profile_requests_to_users_who_share_rooms`
+ `search_all_users: false` spôsobovali, že Element X pri platnom používateľovi písal „This Matrix ID can't be found"
a nový kontakt sa nedal nájsť menom. Na uzavretom serveri (registrácia len pozvánkou) je zoznam členov ako firemný
adresár → `search_all_users: true`, profily členov viditeľné aj bez spoločnej miestnosti; mimo prihlásených
členov sa nič nezverejňuje (`require_auth_for_profile_requests`). (2) `encryption_enabled_by_default_for_room_type:
invite` (predtým `all`): súkromné miestnosti a DM sú šifrované automaticky, verejné kanály nie — noví členovia
kanála vidia históriu a funguje serverové vyhľadávanie; šifrovanie kanála môže tvorca zapnúť ručne.

**D66 — QR prihlásenie: relácia 5 minút namiesto 60 s.** Synapse drží rendezvous reláciu MSC4108 natvrdo 60 s od
vytvorenia QR kódu (zápisy ju nepredlžujú, voľba v konfigurácii neexistuje). Celý postup — naskenovať, opísať
2 číslice, opísať overovací kód v MAS, „Grant access" — musel stihnúť do minúty, inak „The sign in was not
completed in time" (v produkčných logoch: posledný zápis telefónu 63 s po vytvorení → 404). `server/synapse/
Dockerfile`: oficiálny image + jediná zmena `RendezvousHandler(self, ttl=5 min)`; build zlyhá, ak sa riadok
v novej verzii Synapse zmení. Overené: prihlásenie cez QR prešlo pri 96 s. MSC4388 má už 120 s (bez zmeny).

## Chyby z testov na skutočných zariadeniach (2026-11-16, dvanásta dávka)

**D67 — Samsung: zvuk bez vyskakovacieho okna — diagnostika v appke a tichá súhrnná notifikácia.** Samsung A05 nebol
počas dávky pripojený cez adb, takže dôkaz zo samotného telefónu chýba. Porovnanie s upstreamom Element X v26.11.0
(`docs/android-notifications-upstream.md`): cesta push → WorkManager → resolver → renderer je v psst nezmenená; líšime
sa len kanálom (HIGH namiesto DEFAULT, D61). Našla sa upstream chyba: `GROUP_ALERT_CHILDREN` je nastavené na
notifikáciách miestností, kde nemá účinok, a súhrnná notifikácia skupiny (rovnaký HIGH kanál, `GROUP_ALERT_ALL`) tak
sama zvoní pri každej prvej správe po vyčistení. Na AOSP ju stlmí len limit 1 upozornenie/s na appku (emulátor:
`notification_alert` len pre notifikáciu miestnosti). Na One UI s pomalým telefónom môže zvoniť súhrn, ktorý sa nikdy
neukáže ako vyskakovacie okno → presne „pípne, ale nič nevyskočí". b24: súhrn má `GROUP_ALERT_CHILDREN` (nikdy
nezvoní). Keďže príčinu na Samsungu nemožno potvrdiť bez telefónu, b24 pridáva Nastavenia → Upozornenia →
„Diagnostika upozornení (psst)": stav systému, všetky kanály (dôležitosť, zamknutá obrazovka, zmenené používateľom),
čitateľné nastavenia telefónu (vrátane Samsung pop-up / lock screen), aktívne notifikácie, záznam pushov a
zobrazených notifikácií (kanál, dôležitosť, onlyAlertOnce, skupina, fallback, stav zámku — bez obsahu správ a mien),
voliteľne prístup k upozorneniam (zaznamená, ako systém notifikáciu zaradil: efektívna dôležitosť, kanál konverzácie,
potlačené efekty), dva testy o 10 s (ako správa / jednoduché) a „Uložiť a odoslať" (Stiahnuté + zdieľanie).

**D68 — Budíček pri žiadosti o overenie zariadenia (rozšírenie D62).** nginx zrkadlí
`PUT …/sendToDevice/m.key.verification.request/…` do novej služby `server/wake` (psst-wake, stdlib Python, profil
sygnal). Služba overí token cez `/whoami`, budí len zariadenia **toho istého používateľa** (overovanie vlastných
zariadení; cudzích ľudí nikdy), načíta jeho pushery cez Synapse admin API (token zostáva na serveri), vynechá
žiadajúce zariadenie a pošle cez Sygnal high-priority push s označením `!psst-verification:<doména>` len pusherom
psst Android; max. 1× za 20 s na používateľa; v logoch žiadne celé ID. Android (b24) pre takýto push nič nesťahuje ani
nesynchronizuje (inak by žiadosť mohol spotrebovať notifikačný klient) a ukáže „Žiadosť o overenie — otvorte psst"
(kanál „Overenie zariadenia", HIGH, platnosť 10 min); ťuknutie otvorí psst, ktorý po synchronizácii zobrazí obrazovku
„Verification requested". Overené na produkcii: zastavená appka v emulátore dostala notifikáciu 0,5 s po žiadosti
z webu, ťuknutie otvorilo overenie. iPhone (oficiálny Element X ani psst iOS) budíček nedostane — tam treba appku
otvoriť (web/desktop to teraz hovorí, D71). Staršie Android buildy (≤ b23) by takýto push zobrazili ako „nová správa"
(fallback) — aktualizácia na b24 to rieši.

**D69 — macOS: Developer ID podpis + notarizácia, dovtedy návod na stránke.** Certifikát Developer ID Application
nejde vytvoriť cez App Store Connect API (POST /v1/certificates → 403 „This operation can only be performed by the
Account Holder.", aj pre G2); vytvorí ho Account Holder GexPay SE z nášho CSR (`~/psst-keys/macos-devid/devid.csr`,
súkromný kľúč neopúšťa Mac). CI (`web-desktop.yml`) podpisuje a notarizuje automaticky, keď existujú secrets
`PSST_MAC_CERT_P12_BASE64` + `PSST_MAC_CERT_PASSWORD` (notarizácia existujúcim ASC kľúčom U4SWSW9CRM, overené, že
notarytool sa ním prihlási); bez nich build ostáva nepodpísaný (warning). Po každom publikovaní `macos-gatekeeper.yml`
stiahne DMG z app.macet.eu cez HTTPS s quarantine a spustí spctl/codesign/stapler. Stránka na stiahnutie zobrazuje
slovenský návod (Súkromie a bezpečnosť → Napriek tomu otvoriť), kým `latest.json` nemá `"signed": true` — to nastaví CI
len pre overený podpísaný build. Postup: `docs/build/macos-signing.md`, `scripts/desktop/macos-devid-secrets.sh`.

**D70 — Nové heslo pre člena z administrácie.** https://app.macet.eu/admin → pri členovi „Nastaviť nové heslo"
(potvrdenie, CSRF + Origin ako ostatné akcie). Náhodné dočasné heslo (4×4 znaky bez l/1/o/0/i, ≈ 79 bitov) sa nastaví
cez MAS admin API `set-password` a zobrazí adminovi **raz** s tlačidlom „Kopírovať" (len v pamäti session, nikdy
v URL, logu ani na disku). Audit log: `user_password_reset` (kto, kedy, komu — bez hesla). Nedá sa použiť na chránené,
admin, servisné, vlastné ani deaktivované účty. Relácie člena ostávajú (typicky zabudnuté heslo pri prihlásenom
telefóne — zachová si zariadenia aj kľúče); pri podozrení na zneužitie treba „Zablokovať". `members.sh password` ostáva
ako záloha cez SSH. Overené na produkcii: prihlásenie novým heslom prešlo, staré odmietnuté.

**D71 — Overenie „Použiť iné zariadenie": jasná výzva, odpočet a „Poslať znova".** Hlásenie: po prihlásení na Windows
sa žiadosť na iPhone (oficiálny Element X) prvýkrát neotvorila. Príčina (bez chyby v kóde): web/desktop pošle
nešifrovanú to-device `m.key.verification.request` všetkým vlastným cross-signed zariadeniam (okrem seba); to-device
správy sa nepushujú a iPhone ju spracuje až pri otvorenej appke. matrix-sdk-crypto 0.19.1: žiadosť platí 10 min
u odosielateľa (potom `m.timeout`), príjemca ignoruje žiadosť staršiu ako 10 min (alebo > 5 min v budúcnosti).
Element X iOS ďalší limit nemá — údaj „1 minúta" v D62 platí len pre obrazovku Element X Android (odpočet „Time limited
action"), nie pre samotnú žiadosť. Fork web/desktop: počas čakania výzva otvoriť psst/Element na druhom zariadení,
poznámka, že psst na Androide ukáže upozornenie (D68), inde nie, zostávajúci čas a „Poslať znova" (zruší aktuálnu,
pošle novú) aj po zrušení/vypršaní. Overené Playwrightom lokálne aj na produkcii. Podrobnosti:
`docs/verification-request-notes.md`.

## Upozornenia a hovory na všetkých platformách, nočný beh (2026-11-16/17, trinásta dávka)

Samsung A05 nebol pripojený (adb videl len emulátor); Android testovaný v emulátore Android 14.

**D72 — Android: obrazovka „Upozornenia a hovory".** Nastavenia → App settings → „Upozornenia a hovory" (aj z diagnostiky
a z pripomienky po zmeškanom hovore). Riadky = prepínače, ktoré vždy ukazujú skutočný stav (čítaný pri každom návrate
na obrazovku a po výsledku povolenia): upozornenia povolené (POST_NOTIFICATIONS + appka), vyskakovacie okno (kanál
Správy ≥ HIGH), zamknutá obrazovka (kanál nie je „tajný" + systémové `lock_screen_show_notifications`), hovory na celú
obrazovku (`canUseFullScreenIntent`), bez obmedzenia batérie, zvuk a vibrácie správ (kanál), zvonenie hovorov (kanál
zvonenia ≥ HIGH so zvukom), rozsvietiť obrazovku (D73), mikrofón, kamera. Zapnutie: runtime povolenie, inak presná
systémová stránka (bez NEW_TASK → „Späť" vedie do psst); po trvalom odmietnutí stránka appky. Viac položiek ide za
sebou (fronta, pokračuje po návrate). Tlačidlá: „Zapnúť všetko potrebné", „Poslať testovacie upozornenie" (rovnaký
tvar ako správa), „Otestovať zvonenie" (kanál zvonenia, opakovaný tón 8 s), „Diagnostika upozornení" (D67, podstránka).
Vypnutie: otvorí systémovú stránku (appka povolenie sama odobrať nemôže), okrem rozsvietenia (naša voľba).

**D73 — Android: rozsvietenie obrazovky pri novej správe.** One UI nerozsvieti displej pri upozornení appky. psst pri
zobrazení upozornenia správy (kategória msg, nie súhrn, nie tichá aktualizácia, kanál ≥ DEFAULT), keď je displej
vypnutý a filter Nerušiť = „všetko", získa na 3 s wake lock SCREEN_BRIGHT + ACQUIRE_CAUSES_WAKEUP. Android 14+ to
podmieňuje špeciálnym prístupom „Zapnúť obrazovku" (`android.permission.TURN_SCREEN_ON`, normal|appop; stránka
`android.settings.TURN_SCREEN_ON_SETTINGS` s `package:`), bez neho sa wake lock získa, ale displej ostane zhasnutý.
Predvolene zapnuté, ak je povolenie udelené; prepínač si ho vyžiada. Každé rozsvietenie (alebo dôvod, prečo nie) je
v zázname diagnostiky.

**D74 — Android: chýbajúce povolenia hneď po inštalácii a po aktualizácii.** Pôvodný sprievodca (D57/D61) bol reťaz
dialógov: krok sa označil ako „opýtaný" už pri zobrazení, dialóg sa dal zrušiť dotykom mimo / prekryť systémovým
dialógom (napr. povolenie upozornení) a statický príznak „dialóg sa zobrazuje" sa nulovať len v dismiss callbacku,
ktorý pri zničení aktivity nebeží. V emulátore sa krok „hovory na celú obrazovku" po aktualizácii b23→b24 zobrazil
(appop zamietnutý), na Samsungu podľa hlásenia nie — presnú príčinu bez telefónu potvrdiť nemožno, uvedené slabiny
ju vysvetľujú. Teraz: MainActivity.onResume otvorí obrazovku D72 so zvýraznenými chýbajúcimi položkami, ak chýba
niečo potrebné (upozornenia, vyskakovacie okno, zamknutá obrazovka, celá obrazovka, batéria) — raz za verziu (prvé
spustenie aj každá aktualizácia) a znova po hovore, ktorý nemohol zazvoniť na celú obrazovku; obrazovka si chýbajúce
položky hneď vyžiada jednu po druhej. Žiadny dialóg, ktorý by sa dal omylom zrušiť.

**D75 — Web a desktop: Nastavenia → „Upozornenia a hovory".** Nová karta v nastaveniach používateľa so skutočným
stavom: upozornenia (web `Notification.permission`; Windows register `PushNotifications\ToastEnabled` +
`Notifications\Settings\eu.macet.psst`; macOS `com.apple.ncprefs`, najlepší dostupný signál) spolu s nastaveniami
Element, zvuk správ, zvonenie (pravidlo `.m.rule.call`; podľa neho po novom zvoní aj Element Call), na desktope beh
v lište po zatvorení okna a spustenie po prihlásení, mikrofón a kamera; Windows Nerušiť (WNF + SHQueryUserNotificationState),
macOS Sústredenie bez Full Disk Access zistiť nejde — obrazovka to povie. Zapnutie si vyžiada povolenie alebo otvorí
systémovú stránku, viac žiadostí za sebou. Tlačidlá test upozornenia a test zvonenia (5 s). Pri prvom spustení
a po každej aktualizácii sa karta otvorí sama, ak chýbajú upozornenia — raz za verziu; značka verzie prežije aj
odhlásenie (b26 ju na macOS po opätovnom prihlásení otváral znova a dialóg prekryl prichádzajúci hovor — b27).

**D76 — Web Push pre psst web.** Pri zapnutých upozorneniach si web vytvorí push subscription (VAPID kľúč len na
serveri, `secrets/webpush/`, verejná časť `https://app.macet.eu/psst-push.json`) a pusher `eu.macet.psst.web`
(event_id_only). Synapse → Sygnal (pushkin webpush, `allowed_endpoints` len FCM/Mozilla/WNS/Apple) → service worker:
„psst — Nová správa" bez obsahu, jedno na miestnosť, klik otvorí miestnosť; ak je okno appky vpredu, worker nič
neukáže. psst-wake budí aj web („Žiadosť o overenie"). Pusher sa ruší pri odhlásení a pri vypnutí upozornení;
desktop pusher neregistruje. Prehliadač musí bežať; overené v Chrome, Firefox/Safari netestované. Zároveň nginx
v sieti psst má pevnú IP 172.30.0.250 (predtým .10, ktorú pri čistom štarte stihol zabrať iný kontajner) — D34 platí
s novou IP.

**D77 — iOS: „Upozornenia a hovory", audit v simulátore, TestFlight jedným skriptom.** Obrazovka v Nastaveniach so
skutočným stavom iOS (upozornenia, zvuk, zamknutá obrazovka, bannery, CallKit, mikrofón, kamera), žiadosti za sebou,
kde iOS nedovolí, jedna veta + nastavenia appky; test upozornenia a CallKit test hovoru; otvorí sa raz za verziu, ak
niečo chýba. Simulátor (run 43972090982): overenie zariadenia iOS↔web end-to-end, úprava, blokovanie, odpoveď,
reakcia, mazanie potvrdené partnerom. `scripts/ios/release-testflight.sh` (`--check`) v zdieľanom tíme len pridáva
(nič nemaže); chýba iba záznam appky v App Store Connect od Account Holdera.

**D78 — macOS: cesta Developer ID overená suchým behom.** `macos-signing-dryrun.yml` spustil produkčné kroky
macOS jobu s jednorazovým certifikátom „Developer ID Application: PSST CI Test (MHV67VMY8T)": import, kontrola
identity, podpis appky (hardened runtime) aj DMG a `codesign --verify` prešli; `spctl` odmietol podľa očakávania
(chýba dôvera Apple a notarizácia). Po vložení `PSST_MAC_CERT_*` netreba v CI nič meniť; testovacie secrets zmazané,
do `PSST_MAC_CERT_*` sa nikdy nesmú dať testovacie hodnoty.

**D79 — Upstream obmedzenia z auditu: čo sa doplnilo a čo nie.**
- **Web — upozornenia pri karte na pozadí / zatvorenej, upozornenie na žiadosť o overenie:** doplnené Web Pushom (D76),
  ohraničená zmena (service worker + pusher + Sygnal webpush), otestované v Chrome na produkcii.
- **Android — vyhľadávanie v správach (šifrované aj kanály):** Element X v26.11 má vyhľadávanie rozpracované (feature
  flag `MessageSearch`, upstream `isFinished = false`; v našom builde je zapnuté). V teste b27 sa lokálny index (tantivy)
  vytvoril, ale vyhľadávanie vrátilo 0 výsledkov ani pre správy odoslané z telefónu. Chyba je v nedokončenej upstream
  funkcii (Rust SDK search service + UI), nie v našom forku. Vlastná oprava = zásah do matrix-rust-sdk a vlastný build
  natívnej knižnice: odhad 1–2 týždne, vysoké riziko (šifrovaný index, migrácie). Nerobené; počkať na upstream
  (funkcia je v aktívnom vývoji). Obchádzka: vyhľadávanie na desktope (Seshat) a na webe v nešifrovaných miestnostiach.
  **→ Vyriešené v D80 (dávka 14):** príčina nebola v nedokončenej funkcii, ale v analyzátore; malá záplata Rust SDK
  bez zmeny FFI + doplnky vo forku.
- **Android — zdieľanie obrazovky v hovore:** Element Call beží v Android WebView, ktorý `getDisplayMedia` nepodporuje.
  Riešenie = natívny MediaProjection + foreground service + most do LiveKit v Element Call (zmeny vo forku Element X aj
  Element Call). Odhad 2–3 týždne, vysoké riziko (Android 14 obmedzenia projekcie, údržba dvoch forkov). Nerobené.
- **Android — overenie zariadenia QR kódom:** FFI `SessionVerificationController` v26.11 vie len SAS (emoji); QR
  overenie by vyžadovalo nové FFI v matrix-rust-sdk + UI (kamera, zobrazenie QR). Odhad 1–2 týždne, stredné riziko.
  Nerobené; emoji overenie funguje a je rovnako bezpečné.
- **Web — vyhľadávanie v šifrovaných miestnostiach:** Element Web nemá lokálny index (Seshat je natívny modul len pre
  desktop). Riešenie = index v prehliadači (IndexedDB + vlastný indexer) s rizikom úniku obsahu do úložiska
  prehliadača. Odhad 3+ týždne, vysoké riziko. Nerobené; obchádzka: desktop appka.

## Android: vyhľadávanie v správach (2026-11-17, štrnásta dávka)

**D80 — Dokončené upstreamové vyhľadávanie, nie vlastný index.** Element X v26.11 + matrix-rust-sdk už majú celý
mechanizmus: šifrovaný tantivy index na miestnosť v telefóne (kľúč relácie), indexovanie z event cache (nové, odoslané,
upravené, zmazané správy), dopĺňanie histórie (`run_search_backfill`, ~13 týždňov), globálne hľadanie a otvorenie
správy. Prázdne výsledky v D79 neboli chyba indexu, ale analyzátora: predvolený tokenizér len delí slová a mení na malé
písmená a parser hľadá celé slová — „cislo“ nikdy nenájde „číslo“, „ob“ nenájde „obed“ (overené na b29 s 930 správami).
Diakritiku ani začiatok slova nevie Kotlin obísť (regex aj prefix sú v parseri vypnuté), preto:
- **Malá záplata Rust SDK** (`scripts/android/rust-sdk/psst-search.patch`, 2 súbory v `matrix-sdk-search`): tokenizér
  tela správy `psst_folded` = predvolený + `AsciiFoldingFilter` (aj pre dopyt), každé slovo dopytu = prefix
  (`set_field_fuzzy(prefix, vzdialenosť 0)`); vlastný unit test. **FFI sa nemení** — workflow
  `android-rust-sdk.yml` postaví len `libmatrix_sdk_ffi.so` (arm64, armv7, x86_64) z commitu oficiálneho vydania,
  overí, že vygenerované Kotlin väzby sú bajt po bajte zhodné s oficiálnym sources jar, a vymení `.so` v
  **oficiálnom** AAR. Výsledok je GitHub release `android-rust-sdk-26.11.05-psst1` (AAR + SHA-256); `android.yml` ho
  stiahne podľa `libraries/rustsdk/psst-rust-sdk.properties` vo forku, overí hash a skontroluje, že APK obsahuje
  presne tieto `.so`. Prečo nie vlastný build celého SDK: menej času v CI (~15 min), žiadna zmena Kotlin väzieb,
  pri aktualizácii stačí zmeniť pin (docs/android-search.md).
- **Fork** (všetko označené `PSST (D80)`): dopyt sa delí na slová rovnako ako index (`PsstSearchQuery.kt`, každé
  slovo povinné); starý index (bez značky `psst-folded-v1`) sa raz zmaže a SDK ho postaví znova z uložených udalostí
  a histórie; história sa indexuje aj počas používania appky (upstream len pri otvorenom hľadaní alebo na nabíjačke
  cez Wi-Fi) — `FOREGROUND` stratégia, zastaví sa na pozadí; úryvok so zvýraznením; riadok
  „Staršie správy sa ešte indexujú“; nová obrazovka „Hľadať v konverzácii“ (lupa v hlavičke konverzácie aj Detail →
  Hľadať v správach) nad upstream `createMessageSearch(roomId)`.
- **Záloha kľúčov naraz (`ONE_SHOT`).** Upstream sťahuje kľúč zo zálohy len po chybe dešifrovania v časovej osi.
  Preto po novom prihlásení ostala história stiahnutá dopĺňaním zašifrovaná a nevyhľadateľná: test našiel 38 z 56,
  zvyšok až po prelistovaní konverzácií. psst stiahne celú zálohu raz po zadaní kľúča na obnovenie; redecryptor potom
  správy dešifruje a zaindexuje. Rizikom je kľúč, ktorý sa do zálohy dostane až neskôr (zriedkavé); pri účtoch psst je
  sťahovanie celej zálohy malé.
- **Šetrenie batérie.** Jeden prechod históriou znovu číta celú uloženú históriu (~10 s CPU na ~930 správ v emulátore).
  psst ho spustí najviac raz za deň na zariadenie a aj upstreamové spustenie pri otvorení hľadania podmieňuje tým
  istým pravidlom. Nové správy sa indexujú priebežne pri prijatí.
- **Obmedzenia:** história ~3 mesiace (upstream limit backfillu); indexuje sa len dešifrovaná správa; predpona len
  pre jednotlivé slová; hľadanie v miestnosti filtruje globálny prúd výsledkov (pri psst počte miestností dosť rýchle).

## Android: overenie zariadenia QR kódom (2026-11-17, pätnásta dávka)

**D81 — Štandardné Matrix QR overenie: Rust FFI rozšírené, obrazovky doplnené.** Rust crypto aj `matrix-sdk` majú QR
overenie (`m.qr_code.show.v1` / `m.qr_code.scan.v1` / `m.reciprocate.v1`) hotové; chýbalo vo FFI pre Kotlin (len SAS,
feature `qrcode` vypnutý) a v obrazovkách Element X. Riešenie (podrobne docs/android-qr-verification.md):
- **Záplata FFI** `scripts/android/rust-sdk/psst-qr-verification.patch` — len doplnky (QR delegát, `qr_options`,
  `generate_qr_code`, `scan_qr_code`, `confirm_qr_scanned`), žiadosti/prijatie ponúkajú SAS + QR ako Element Web,
  emoji ostáva možné aj po zobrazení QR. Keďže sa menia Kotlin väzby, AAR sa už nestavia výmenou `.so`, ale
  oficiálnym projektom `matrix-rust-components-kotlin` (rovnaký tag); CI zastaví vydanie, ak by sa väzby líšili mimo
  `matrix_sdk_ffi.kt`. Spoločné vydanie s D80: `android-rust-sdk-26.11.05-psst3`.
- **Obrazovky:** po prijatí žiadosti sa podľa schopností druhej strany ukáže náš QR kód, „Naskenovať QR kód“ a vždy
  „Porovnať emoji“; ak druhá strana pozná len emoji (Element X iOS), spustí sa rovno emoji. Kamera sa pýta až pri
  skenovaní; chybové hlášky pre cudzí/neplatný kód, kód iného overenia (nezhoda kľúčov), vypršanie, zrušenie druhou
  stranou, nezhodu emoji. SK/EN.
- **Upstream chyba opravená:** nové neoverené zariadenie (obrazovka „Potvrďte, že ste to vy“) zahadzovalo žiadosť o
  overenie začatú z už overeného zariadenia (čakalo na domovskú obrazovku). Žiadosť sa teraz zobrazí aj nad FTUE a po
  overení FTUE pokračuje.
- **Prihlásenie QR kódom (MSC4108) nezmenené** a otestované (sken QR z webu → kód → MAS → prihlásený a overený).
- **Obmedzenia:** Element Web/Desktop nevedia skenovať (bez kamery), s nimi vždy skenuje telefón. Element X nemá
  vstup „overiť iné moje zariadenie“ — overenie medzi dvoma telefónmi začína nový telefón (alebo web/desktop).

## Prezentačná stránka psst.macet.eu (2026-11-17, šestnásta dávka)

**D82 — Statická prezentačná stránka na `psst.macet.eu`, bez cudzích zdrojov.** `pst.macet.eu` smeruje na cudzí server
(195.181.248.25), `psst.macet.eu` na náš (204.168.160.131) → použitá `psst.macet.eu`.
- **Zdroj** `server/www/`: texty SK/EN v `build.py` (generuje `sk/`, `en/`, koreň a `404.html`), CSS, `lang.js`,
  písmo Inter (OFL, rovnaké súbory ako v Element Call), logo, ikony. Žiadne cudzie písma/skripty/analytika/cookies;
  CSP `default-src 'none'` + len `'self'` (overené: žiadna požiadavka mimo domény, žiadne chyby CSP).
- **Jazyk:** koreň `/` presmeruje podľa uloženej voľby (localStorage `psst-lang`), inak podľa jazyka prehliadača
  (sk/cs → SK, inak EN); bez JS ostanú odkazy Slovenčina/English. Prepínač v hlavičke voľbu uloží. Samostatné URL
  `/sk/` a `/en/` s `hreflang`, `canonical`, OG/Twitter náhľadom (`og-sk.png`, `og-en.png`) pre každý jazyk.
- **Texty pravdivé:** obsah šifrovaný medzi zariadeniami, server ho neprečíta; sekcia „Čo server vidí a čo nie“
  (kto s kým a kedy, názvy a členovia skupín, pripojenie; notifikácie doručuje Google/Apple bez obsahu). Žiadna
  anonymita, „100 %“ ani superlatívy. Prístup len na pozvánku, bez formulára/kontaktu. Pätička len
  „Powered by GG & TT“. Odkaz na zdrojový kód (AGPL) je na stránke `/download` (pätička) a v appkách, nie tu.
- **Snímky** zo skutočnej appky (web + Android emulátor) s testovacími účtami qa-* a vymyslenými menami/správami
  (Eva, Tomáš, Mária); účty a miestnosti boli po nasadení zmazané.
- **Nasadenie bez výpadku:** vlastný certifikát `psst-web` (zdieľaný `psst` pre app/chat/call/push sa nemení),
  obnovuje ho existujúci kontajner certbot. Obsah sa kopíruje do už pripojeného `/srv/app-default/www` — nový
  bind mount by vyžadoval znovuvytvorenie kontajnera nginx (výpadok všetkých služieb vrátane TURN). Vhost
  `templates/nginx/www.conf` sa zapne až s certifikátom; `WEB_DOMAIN` v `.env` je voliteľné. `deploy.sh` odteraz
  pri zmene konfigurácie nginx robí `nginx -t` + graceful reload namiesto reštartu a reštartuje admin len pri zmene
  jeho tajomstiev (predtým každé nasadenie krátko prerušilo /admin). Overené sondou počas nasadenia: 954 požiadaviek
  na app/chat/call/push/download bez chyby, žiadny kontajner nebol znovu vytvorený.
- **Indexovanie:** `psst.macet.eu` indexovateľná (robots + sitemap). `app.macet.eu/robots.txt` povolí len
  `/download/` a právne texty, web app (prihlasovacia stránka) a `/admin` majú `X-Robots-Tag: noindex, nofollow`,
  rovnako prihlásenie MAS na `chat.macet.eu/auth/`; `chat.macet.eu/robots.txt` zakazuje všetko. Predtým
  `app…/robots.txt` vracal HTML web appky.
- **Healthcheck:** obe jazykové verzie + platnosť certifikátu `psst-web`.

## Android: Google Play Protect blokoval inštaláciu (2026-11-17, šestnásta dávka)

**D83 — Žiadne SMS, notification listener ani accessibility v manifeste; kontrola v CI.** Samsung A05 (Android 14)
zablokoval inštaláciu b37 zo stránky /download („App blocked to protect your device“); b24 prešla. Play Protect
(rozšírená ochrana pred podvodmi) blokuje aplikácie nainštalované z prehliadača, správ alebo správcu súborov, ktoré
deklarujú `RECEIVE_SMS`, `READ_SMS`, službu notification listener alebo accessibility.
- **Príčina:** vlastný kód psst — `PsstNotificationListener` (služba s `BIND_NOTIFICATION_LISTENER_SERVICE`), voliteľná
  časť diagnostiky upozornení (D67), pridaná vo forku 2026-11-16 (`7df57a358`). Prvý build s ňou je **b25** (prvý
  úspešný b27). V b24 nebola. SMS ani accessibility nie sú nikde (náš kód, upstream ani knižnice).
  `REQUEST_INSTALL_PACKAGES` je upstream (otvorenie APK prílohy), bola už v b24 a nie je na zozname → ostáva.
- **Zmena:** služba odstránená. Diagnostika namiesto „ranking“ z listenera vypíše efektívny kanál každého aktívneho
  upozornenia vrátane kanála konverzácie (`getNotificationChannel(kanál, shortcutId)`). Stratené: per-upozornenie
  `suppressed`/`intercepted` (DND sa ďalej zapisuje pri každom upozornení). Žiadna funkcia pre používateľa nechýba.
- **Názov v dialógu:** Play Protect ukázal `io.element.android.x.ElementXApplication`. Štítok aplikácie bol
  `@string/app_name` (správne „psst“), ale dialógy, ktoré čítajú APK pred inštaláciou bez zdrojov, padnú v
  `loadLabel()` na `android:name`. Štítok je teraz doslovný `android:label="psst"` (rovnaký vo všetkých jazykoch).
- **Kontrola:** `scripts/android/check-manifest.py` číta zlúčený manifest vo vydanom APK (aapt2) aj AAB (protobuf
  manifesty všetkých modulov) a zlyhá pri ktorejkoľvek zo štyroch položiek alebo nedoslovnom štítku. Beží v CI
  (`android.yml`, oba joby) a v `sign-release.sh` pred podpisom. Na b42 zlyhá, na b43 prejde.
- **Reprodukcia:** emulátor Android 14 s Google Play (bez Google účtu), overovanie Play Protect zapnuté aj pre ADB:
  b42 aj b43 → `VerifyApps … response=0` (povolené). Blok sa **nezopakoval** — rozšírená ochrana platí len v
  niektorých krajinách a pre inštalácie z prehliadača/správ/súborov; Chrome v emulátore na tomto Macu nevykresľoval
  stránky. Rozhodujúca je preto kontrola manifestu.
- **Stránka /download:** postup pre hlásenia pri inštalácii (prehliadač „súbor môže poškodiť zariadenie“, neznáme
  zdroje, Play Protect sken / odoslanie na kontrolu, Samsung Automatické blokovanie, čo robiť pri „App blocked“), SK + EN.

## Android: „vyhľadávanie nefunguje“ v b42/b43 (2026-11-18, sedemnásta dávka)

**D84 — Vyhľadávanie sa nepokazilo. Chyba bola v teste a v zavádzajúcej hláške upstreamu. Pred vydaním odteraz beží
automatická kontrola hľadania.** Dávka 16 hlásila, že b42 aj b43 nenájdu nič, ani práve prijatú správu.
- **Overenie po buildoch:** b38 až b41 som stiahol z CI (artefakty) a podpísal len na test. Na jednom účte som
  postupne aktualizoval b37 → b38 → … → b43. Každý build našiel staré správy aj správu prijatú hneď po aktualizácii.
  Nájdu sa aj po čistej inštalácii b43, po novom prihlásení s kľúčom na obnovenie a po resete identity.
  **Prvý pokazený build neexistuje.** Rust knižnica (psst2/psst3 s QR) obsahuje záplatu hľadania (`psst_folded`
  v `.so` b37 aj b42) a Kotlin zmeny QR behu sa hľadania nedotýkajú.
- **Skutočná príčina hlásenia:** test v dávke 16 napísal slovo a čítal obrazovku bez prepnutia na kartu
  **Správy**. Obrazovka hľadania sa otvára na karte **Konverzácie**, ktorá hľadá len názvy konverzácií. Upstream
  (Element X) pri prázdnom výsledku ukazuje na oboch kartách hlášku pre správy: „No results in the last 3 months –
  There are no results for “…” in your recent messages“. Overené na b43: karta Konverzácie ukáže presne texty
  z dávky 16 (vrátane poradia prvkov), karta Správy výsledky. QR beh (dávka 15) prepol na Správy a výsledok 5/5 bol
  správny.
- **Oprava v appke (b44):**
  - karta Konverzácie má vlastný prázdny stav „Žiadna konverzácia s týmto názvom – Slová môžu byť vo vašich
    správach“ s tlačidlom **Hľadať v správach**;
  - obrazovka hľadania je po slovensky (Localazy pre ňu SK nemá, texty sú v `psst_search_strings.xml`).
  Prečo nie automatické prepnutie na Správy: zoznam konverzácií hneď po zmene dopytu najprv vráti medzistav a
  prepnutie by preskakovalo kartu aj pri hľadaní názvu. Tlačidlo je jednoznačné.
- **Oprava testov:** `scripts/android/search_ui.py` vždy prepne na Správy. Počet uzná len vtedy, keď vidí hlavičku
  „Z vašich správ“ alebo prázdny stav pre správy. Výsledky prejde posúvaním a pred aj po dopyte sa vráti na zoznam
  konverzácií, takže sa dopyty nespájajú.
- **Kontrola pred vydaním:** `scripts/android/search-gate.sh` beží v `sign-release.sh` hneď po kontrole manifestu.
  Ak zlyhá, build sa nepodpíše ani nenahrá na /download. Postup:
  - čistá inštalácia vydávaného x86_64 APK (podpísaného jednorazovým kľúčom) v emulátore Android 14;
  - nový účet `qa-sg…`, ktorému partner cez nio s E2EE pošle 8 známych správ do šifrovanej miestnosti;
  - dopyty bez diakritiky a začiatkom slova (`cislo` 3, `stastn` 2, `ob` 2, `zlty kon` 1, `dvanast` 2) a slovo,
    ktoré tam nie je (0);
  - po reštarte appky prijatá správa (1) a nový súčet pre `cislo` (4).
  Očakávané počty počíta `search_check.py` z textov správ podľa pravidiel indexu. Účty a miestnosť sa zmažú aj pri
  chybe. Kontrola potrebuje Mac s emulátorom, ssh `psst` a test venv. V GitHub Actions nebeží, lebo by
  potrebovala prístup na produkčný server na zakladanie účtov.

## Presun na finálnu doménu psst.pro (2026-11-19, osemnásta dávka)

**D85 — psst beží na psst.pro, založený načisto. Staré adresy na macet.eu sú vypnuté.**
- **Adresy (natrvalo):**
  - Matrix `server_name` je **psst.pro**, ID majú tvar `@meno:psst.pro`;
  - homeserver a prihlasovanie (MAS na `/auth/`) bežia na **chat.psst.pro**;
  - web, `/download` a `/admin` sú na **app.psst.pro**;
  - hovory (Element Call) a TURN/TLS na 443 sú na **call.psst.pro**;
  - úvodná stránka a `.well-known/matrix/{client,server}` sú na **psst.pro**, `www.psst.pro` presmeruje na psst.pro;
  - bývalá doména `push.` (ntfy) sa už nezakladá.
- **Prečo server_name ≠ homeserver:** ID sú krátke (`@geo:psst.pro`) a na psst.pro je úvodná stránka.
  - Klienti nájdu homeserver cez `/.well-known/matrix/client`.
  - `m.server` ukazuje na `chat.psst.pro:8448`. Port 8448 je zvonka zatvorený (UFW, nepublikovaný), takže
    federácia nefunguje.
  - V Docker sieti tú istú cestu používa lk-jwt-service na overenie OpenID tokenov hovorov: psst.pro → .well-known
    → chat.psst.pro:8448 → interný vhost so samotným `openid/userinfo`. Oba názvy sú v sieti alias nginx.
- **Certifikát:** jeden Let's Encrypt certifikát (`psst`) pre všetkých päť názvov, s automatickou obnovou
  (kontajner certbot). Samostatný certifikát pre úvodnú stránku (D82) už netreba.
  - Registrácia v LE je **bez e-mailu** (`deploy.sh … none`). LE expiračné e-maily aj tak už neposiela a
    `healthcheck.sh` stráži platnosť.
  - Kontakt prevádzkovateľa na stránkach Podmienky a Súkromie je **@geo:psst.pro** (správa v psst). Predtým tam bol
    e-mail na starej doméne a reťazec „macet.eu“ nesmie ostať.
- **Neznáme názvy nedostanú nič:** nginx na 443 odmietne TLS handshake pre neznámy SNI (`ssl_reject_handshake`) a
  na :80 vráti 444 (bez presmerovania). Bývalé názvy, ktorých DNS ešte ukazuje na server, tak nedostanú obsah psst
  ani certifikát.
- **Načisto:** nová databáza, nový podpisový kľúč Synapse a nové tajomstvá (MAS kľúče, VAPID, LiveKit, TURN, DB,
  admin). Účty, správy, miestnosti, pozvánky ani relácie sa nepreniesli.
  - Prenesené sú len kľúče, ktoré nesúvisia s doménou: FCM service account, APNs kľúč, verejný kľúč na nahrávanie
    na `/download` a heslová fráza záloh.
  - Heslová fráza ostala rovnaká, aby otvorila novú aj poslednú zálohu starého stavu.
- **Posledná záloha starého stavu:** `/opt/psst/archive-macet-final/` na serveri, mimo rotácie.
  - Je to šifrovaný archív + `.sha256`, `backup.pass` a `README.txt` (root, 700/600).
  - Overené: SHA-256 sedí, archív sa dešifruje a rozbalí, `pg_restore --list` prečíta obe databázy (177 a 34
    tabuliek s dátami), podpisový kľúč aj médiá (749 súborov) sú v ňom.
  - Ponechať do 2026-12-19, potom ho zmazať ručne (príkaz je v README).
- **Identifikátory sa nemenia:**
  - balík a bundle `eu.macet.psst` (+ `.nse`, `.shareextension`), App Group `group.eu.macet.psst`;
  - pusher app_id `eu.macet.psst*`, keystore, Firebase projekt, APNs kľúč.
  - Zmenila sa len **URL schéma OAuth callbacku** desktopu, Androidu a iOS: `eu.macet.app` → `pro.psst.app`
    (reverse-DNS `app.psst.pro`, client_uri). Je to adresa, nie identifikátor appky.
- **Android:** povolený je jediný account provider `Managed(serverName = psst.pro, baseUrl = https://chat.psst.pro,
  canUseServerName = false)`.
  - Tlačidlo hovorí „Sign in to psst.pro“ a appka sa pripája priamo na homeserver bez .well-known.
  - QR prihlásenie z webu nesie URL homeservera, takže sa zhoduje.
- **Aktualizácia zo starej appky:**
  - **Android:** `AppMigration11` pri aktualizácii zmaže lokálne každú reláciu, ktorej ID nie je `@…:psst.pro`.
    Zmaže záznam, súbory relácie a naplánované úlohy, k starému serveru sa nepripája. Appka sa otvorí na
    prihlásení nového servera.
  - **Web a desktop:** `restoreSessionFromStorage` zahodí uloženú reláciu pre iný homeserver, než má build v
    konfigurácii (vlastné servery sú vypnuté), a ukáže prihlásenie.
  - Staré buildy (Android b44, desktop b27) o novej verzii samy nevedia, lebo kontrolujú adresu na starej doméne,
    ktorá už neodpovedá. Členov treba upozorniť priamo; odkaz je https://app.psst.pro/download/.

## macOS Developer ID, iOS TestFlight, podklady pre Google Play (2026-11-19, devätnásta dávka)

**D86 — macOS je podpísaný a notarizovaný, iOS b1 je v TestFlighte, podklady pre Play sú v `play-listing/`.**

**macOS:**
- Certifikát `developerID_application.cer` patrí ku kľúču `devid.key` (zhodný verejný kľúč). Je to Developer ID
  Application (OID 1.2.840.113635.100.6.1.13), subjekt „GexPay, SE (MHV67VMY8T)“, platný do 2027-12-19.
- `macos-devid-secrets.sh` vytvoril p12 a nastavil šifrované tajomstvá `PSST_MAC_CERT_*`. Oprava v skripte:
  kontrola tajomstiev cez `gh secret list | grep -q` padala pod `pipefail` na SIGPIPE, teraz sa zoznam načíta
  najprv do premennej.
- Prvý podpísaný build je **b31**.
  - Gatekeeper na čistom runneri v CI (7/7) aj lokálne na stiahnutom DMG s karanténou: `accepted, source=Notarized
    Developer ID`, `stapler validate` OK pre DMG aj appku, hardened runtime.
  - Stránka /download sama zahodila návod „Napriek tomu otvoriť“ (`signed: true` v latest.json).
- macOS joby na GitHube dvakrát nedostali runner do 15 minút (runnery práve vyťažoval iOS archív). Pomohol
  `gh run rerun --failed`, build číslo ostalo b31.
- **Kľúčenka pri aktualizácii z nepodpísanej verzie** (z kódu a zo správania macOS, naostro neoverené, aby sa
  nemenila skutočná položka „psst Safe Storage“ v kľúčenke na tomto Macu):
  - položku „psst Safe Storage“ vytvorila ad-hoc podpísaná verzia a jej ACL dôveruje len tomuto podpisu;
  - podpísaná verzia má iný podpis, preto macOS **raz** ukáže dialóg „psst chce použiť vaše dôverné údaje
    uložené v ‚psst Safe Storage‘ v kľúčenke“. Po zadaní hesla a **Vždy povoliť** všetko funguje a ďalšie
    podpísané verzie sa už nepýtajú (požiadavka na podpis = Team ID);
  - pri **Zamietnuť** upstream kód tajomstvo nezahodí (`SafeStorageDecryptionError`), reláciu však nevie
    obnoviť a ukáže chybu obnovenia relácie. Po novom spustení a povolení v kľúčenke sa obnoví bez straty
    správ.

**iOS:**
- `release-testflight.sh` nájde appku podľa bundle ID (`eu.macet.psst`), názov v App Store Connect („psst secure
  chat“) mu nevadí. Názov na ploche ostáva `psst` (`CFBundleDisplayName`).
- **Build b1:**
  - spracovanie Apple: VALID za ~4 min;
  - interná skupina „psst“ s testerom Geo M;
  - export compliance: `ITSAppUsesNonExemptEncryption = false` (výnimka, štandardné algoritmy);
  - entitlement `aps-environment: production`, applinks `app.psst.pro`, NSE v App Group `group.eu.macet.psst`.
- **APNs:** Release build registruje pusher `eu.macet.psst.ios.prod`. Sygnal ho má ako APNs `production`, topic
  `eu.macet.psst`; NSE dostáva ten istý push (mutable-content), samostatný topic nemá. Skúšobný push s vymysleným
  tokenom: Apple odpovedalo `BadDeviceToken` (nie `InvalidProviderToken`), takže kľúč, tím a produkčné prostredie
  sú prijaté.

**Google Play** (len podklady, do konzoly nič):
- `play-listing/` obsahuje:
  - texty EN/SK; tvrdenia sú overené, bez sľubu anonymity a s výslovným „psst vás nerobí anonymnými“;
  - ikonu 512 (RGBA) a feature grafiku 1024×500;
  - 5 snímok z emulátora (vymyslené osoby, správy z overených webových relácií, aby pri nich nebol varovný
    otáznik).
- `FACTS.md` obsahuje overené fakty s dôkazmi z AAB b47.
- **Zistené, neimplementované:**
  - pre Play treba odstrániť alebo zdôvodniť `REQUEST_INSTALL_PACKAGES`, polohu (funkcia je bez mapového kľúča
    skrytá) a `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`; vyhlásiť full-screen intent a typy služieb v popredí;
  - chýba verejná stránka s postupom zmazania účtu (pre pole „Delete account URL“);
  - nahlásenia obsahu sa nezobrazujú na admin stránke.
- **Zmazanie účtu:** v appke cez Nastavenia → Manage account & devices → MAS → Delete account, na webe
  chat.psst.pro/auth/account. Overené naostro: deaktivácia v MAS aj Synapse + `erased_users`.
- **Play App Signing:** nahrať **existujúci** kľúč cez PEPK (postup v FACTS.md, nespustené), aby verzia z Play a
  z /download mali rovnaký podpis a fungovali App Links.
