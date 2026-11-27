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

**D87 — psst pripravený na Google Play a App Store: prevádzkovateľ, verejné právne stránky, povolenia, nahlásenia.**

**Prevádzkovateľ a kontakt:** všade MACET, s.r.o., IČO 35953781, Slovenská republika; kontakt `psst@psst.pro`
(bez ulice, telefónu a mena osoby). Úvodná stránka psst.pro ostáva bez mena prevádzkovateľa, pod „Powered by GT“
má len dva malé odkazy Súkromie / Podmienky. Let's Encrypt účet má kontaktný e-mail `psst@psst.pro`
(`certbot update_account`, `deploy.sh` ho nastaví aj pri existujúcom certifikáte).

**Právne stránky na psst.pro** (`server/www/legal.py` → `build.py`; jedna URL = SK aj EN na jednej stránke, aby
jeden odkaz stačil v obchodoch aj v appkách):
- `/privacy` „Zásady ochrany súkromia / Privacy Policy“, `/terms`, `/delete-account`, `/support` (Support URL pre
  App Store). Obsah podľa `play-listing/FACTS.md`: čo je E2EE a čo server vidí (aj reakcie, verejné kanály),
  server v EÚ (Hetzner, Helsinki), push cez Google FCM / Apple APNs bez obsahu, IP 28 dní, zálohy 7/4/6 → zo záloh
  zmizne najneskôr do 6 mesiacov, práva GDPR a ÚOOÚ SR, 18+, len na pozvánku, žiadna anonymita.
- Staré `app.psst.pro/{privacy,terms}.html` → 301 na psst.pro. **OAuth metadáta klientov** (web `oidc_metadata`,
  Android/iOS `BuildTimeConfig`/`AppSettings`) ostávajú na `app.psst.pro/*.html`: MAS politika registrácie
  klienta vyžaduje tos/policy URI na hostiteľovi `client_uri` (app.psst.pro); presmerovanie ich dovedie na
  psst.pro. Odkazy, ktoré vidí používateľ (O aplikácii, Help & About, pätička), idú priamo na psst.pro.
- Šablóny `templates/app/legal/` a voľby `--contact/--hosting` sa už nepoužívajú (voľby sa prijmú a ignorujú).

**Android povolenia (b51):**
- `REQUEST_INSTALL_PACKAGES` odstránené (príloha .apk ide do systému ako iný súbor; aktualizácia psst cez
  prehliadač).
- Poloha odstránená úplne: povolenia, služba `LiveLocationSharingService`, čítanie polohy (`createLocationProvider`
  vracia „povolenie zamietnuté“). Funkcia bola skrytá (bez mapového kľúča).
- `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` **odstránené**: Android dokumentácia, na ktorú odkazuje Play politika
  Device and Network Abuse, uvádza pre „Instant messaging, chat, or calling app“, ktorá FCM používa, „Not
  Acceptable“ (developer.android.com/training/monitoring-device-state/doze-standby#exemption-cases). Krok
  „Bez obmedzenia batérie“ zobrazí návod (Batéria → Bez obmedzení) a otvorí systémovú stránku appky; upstream
  banner otvára systémový zoznam optimalizácie.
- `app/src/main/AndroidManifest.xml` ich odstraňuje aj z knižníc (`tools:node="remove"`), `check-manifest.py`
  zlyhá, ak sa vráti ktorékoľvek z nich alebo AD_ID (CI aj pred podpisom).
- O aplikácii (Android aj iOS): Zmazanie účtu → psst.pro/delete-account, Kontakt → mailto:psst@psst.pro.

**Nahlásenia na /admin:** sekcia Nahlásenia číta Synapse `event_reports`, `room_reports`, `user_reports` cez
read-only rolu `psst_admin_ro` (stĺpcové práva len na metadáta: odosielateľ, miestnosť, čas, typ, názov
miestnosti; k obsahu udalostí prístup nemá). Stav vybavené/nevybavené a posledná akcia sú v `notes.sqlite` admina.
Akcie: Zablokovať (MAS lock + Synapse locked; nie chránené účty a admini), Zmazať správu (Synapse admin
`user/<odosielateľ>/redact` s `before_ts = after_ts = čas správy`, `limit 1`; pri nejednoznačnom čase sa nič
nezmaže), Zmazať miestnosť (purge), Zmazať správy člena (redakcia vo všetkých jeho miestnostiach). Dôvod redakcie
„Odstránené správcom psst po nahlásení“. Všetko do `audit.log`. Klienti vedia nahlásiť správu a miestnosť
(iOS miestnosť len pri skupinách, nie pri DM); nahlásenie používateľa majú len cez API → stránky to tak aj píšu.

**Účty pre kontrolórov:** `review` a `review-partner` (silné heslá, nie admin, nedeaktivujú sa), šifrovaná DM
a skupina „Weekend trip“ zo zálohovaných webových relácií; údaje + kľúče na obnovenie + anglický návod v
`~/proj/psst-review.txt` (600). V repozitári len návod bez hesla (`appstore-listing/APP-REVIEW-NOTES.txt`).

**Overenie D87:**
- **Android b51**, emulátor Android 15:
  - inštalácia cez prihlásený b47 (b47 aj sám ponúkol b51);
  - správa pri zhasnutom displeji: displej sa rozsvietil, `notification_alert` s vibráciou a zvukom;
  - hovor na celú obrazovku cez zamknutý displej (`IncomingCallActivity`);
  - hovor na pozadí: `CallForegroundService` typu microphone, médiá tečú;
  - QR overenie (sken QR z webu) a QR prihlásenie (kód 2 číslice + MAS);
  - search-gate PASS;
  - nahlásenie správy aj miestnosti;
  - O aplikácii;
  - krok batérie: návod → App info → Allow background usage → Unrestricted → psst vo `deviceidle whitelist`.
- **Videá pre Play** sú nahraté cez `adb emu screenrecord` (zachytí aj zamknutý displej, `screenrecord` v zariadení
  pri zhasnutom displeji nenahrá nič).
- **iOS** (CI `ios-store.yml`, XCUITest `PsstStoreTests`):
  - snímky App Store v natívnom rozlíšení na 3 simulátoroch, história obnovená kľúčom na obnovenie;
  - Report room funguje, odkazy v O aplikácii sú;
  - „Report content“ v menu správy sa otvára.
- **Web:**
  - nahlásenie správy a miestnosti;
  - akcie admina: zmazanie len nahlásenej udalosti (overené v DB), purge miestnosti, zablokovanie, vybavené/znova;
  - Help & About má odkazy a kontakt.
- **Testovacie nástroje:**
  - `search-gate.sh` a `emulator-test.sh` poznajú nový dialóg batérie;
  - `search-gate.sh` vyplní formulár MAS podľa polohy, keď Chrome nesprístupní web v strome prístupnosti;
  - psst34 so `swiftshader` visel pri studenom štarte (snapshot bol z `-gpu host`), preto som použil psst35.
- **/download** má pri Androide aj armv7 APK a AAB toho istého buildu (`android-armv7`, `android-aab` v
  latest.json, upload skript ich pozná).
- **Drobnosť na ďalší build:** dialóg batérie hovorí „Batéria → Bez obmedzení“. Na Android 15 je medzi tým ešte
  „Allow background usage“.

**D88 — Otvorená registrácia s hCaptcha namiesto pozvánok, hľadanie ľudí len podľa presného mena účtu.**

**Registrácia (MAS 1.29.0; názvy volieb overené v `docs/reference/configuration.md` tagu v1.29.0 a cez
`mas-cli config check`):** `password_registration_enabled: true`, `password_registration_email_required: false`,
`password_registration_token_required: false`; `captcha.service: hcaptcha` so `site_key` a `secret_key`.
`rate_limiting.registration` burst 3 / `per_second` 0.0008 (3 naraz z jednej IP, potom 1 za ~21 min); limity
prihlásenia (`rate_limiting.login.per_ip` 3 / 0.05, `per_account` 1800 / 0.5) sú v šablóne výslovne, rovnaké ako
predvolené; `username_availability` 5 / 1.0. MAS nepozná `secret_key_file`, preto `deploy.sh` dosadí secret do
vyrenderovaného `data/config/mas/config.yaml` (adresár len pre root/MAS) zo `secrets/mas/hcaptcha_secret` (600,
UID 65532), rovnako ako tajomstvo admin klienta. Bez oboch súborov `deploy.sh` skončí — otvorená registrácia bez
ochrany sa nedá nasadiť omylom. `--local-test` (CI smoke) používa verejné testovacie kľúče hCaptcha. Kľúče z
`.hcaptcha-keys.txt` sú v `~/psst-keys/hcaptcha.txt` (600); súbor v repe nikdy nebol commitnutý (história overená
podľa názvu aj obsahu).

**Súhlas s Podmienkami a vek 18+:** natívna voľba MAS `branding.tos_uri: https://psst.pro/terms` pridá do
registrácie povinné políčko (MAS ho uloží v `user_terms`). Samostatné potvrdenie veku MAS nemá → je v texte
políčka: „Mám aspoň 18 rokov a súhlasím s Podmienkami používania“ / „I am at least 18 years old and I agree to the
Terms and Conditions“ (ostatné jazyky po anglicky). Formulár je React a preklady sú skompilované v assets so SRI
hashom v manifeste, preto `server/scripts/mas-assets.py` pri každom deployi vezme assets z image MAS, nahradí text
(a v slovenčine aj hlášky hCaptcha), zmaže .br/.gz upravených súborov, prepočíta integrity a výsledok sa read-only
pripojí do kontajnera (`data/config/mas-ui`). Pri novej verzii MAS sa to zopakuje; ak kľúč chýba, deploy skončí.

**Pozvánky preč:** admin stránka bez sekcie Pozvánky, formulára, stĺpca „Pozvánka“ a endpointov `/admin/invites*`
(členovia, nové heslo a nahlásenia ostávajú); rola `psst_admin_ro` stratila SELECT na tabuľky registrácií MAS.
`members.sh invite` a `new-invite.sh` zrušené. Všetky registračné tokeny v MAS zneplatnené (10 nezrušených z 11, z
toho 6 ešte použiteľných). Odkazy s kódom sa nikdy nerozosielali (kód sa písal ručne do kroku MAS), staré odkazy
na app.psst.pro / „Create account“ vedú na bežnú registráciu. Appky nemali vlastné pole na kód — krok s tokenom
bol na stránke MAS, ktorý sa vypnutím `password_registration_token_required` neukáže.

**Hľadanie ľudí:** Synapse 1.165 `user_directory.enabled: false` (podľa kódu `rest/client/user_directory.py` vráti
prázdny zoznam) → členov sa nedá vylistovať ani hľadať podľa časti mena. Profil zostáva dostupný prihláseným aj
bez spoločnej miestnosti (`limit_profile_requests_to_users_who_share_rooms: false`, D65), inak by presné meno
nefungovalo. Appky: krátke meno sa doplní na `@meno:<server>` a ukáže sa len vtedy, ak profil existuje (aby sa pri
písaní neponúkali neexistujúce účty): Android `MatrixUserRepository` („jana“ aj „@jana“, aj kratšie ako 3 znaky),
iOS `UserDiscoveryService` + prah hľadania 1 znak (start chat, pozvanie do miestnosti), web/desktop `InviteDialog`
(návrhy, Enter) a `useProfileInfo` (vyhľadávanie). Na webe len tvar „jana“ — „@jana“ ostáva upstream správaniu
(upstream testy pri ňom počítajú s neplatným ID a pri písaní znak po znaku by sa robilo veľa zbytočných dopytov).
Plné `@meno:psst.pro` fungovalo vo všetkých appkách aj predtým. Zistenie: priame hľadanie profilu umožňuje overiť,
či účet s presným menom existuje — to je pri začatí rozhovoru menom nevyhnutné a prijateľné.

**hCaptcha v Zásadách a formulároch obchodov:** podľa hcaptcha.com/privacy a docs.hcaptcha.com/faq hCaptcha
(Intuition Machines, Inc., USA, sprostredkovateľ podľa GDPR) spracúva IP adresu, údaje o prehliadači a zariadení
(typ prehliadača, OS) a signály práce s overením (pohyby myši, dotyky, stlačenia klávesov); prenos do USA cez
EU-U.S. Data Privacy Framework a SCC. Presne toto je v `/privacy` (body 2, 4, 5, 9, 10), dátum účinnosti 20. 11.
2026. Obchody: Google vyžaduje deklarovať údaje z webview otvoreného z appky, Apple „data collected via web
traffic“ (registrácia beží v Custom Tab / ASWebAuthenticationSession) → opatrne deklarujeme jednu položku navyše:
Play **App activity → App interactions** (Fraud prevention, security, and compliance; nezdieľané — service
provider), Apple **Usage Data → Product Interaction** (App Functionality, linked, bez sledovania). IP sa nikde
nepoužíva na polohu → Location ostáva „Not collected“. Podrobne `play-listing/FORMS.md` §7 a
`appstore-listing/FORMS.md` §3.

**Texty:** všade namiesto „len na pozvánku“ pravdivo: účet si vytvorí ktokoľvek od 18 rokov, ľudia sa nájdu podľa
presného mena účtu (psst.pro SK/EN, /privacy, /terms — aj zákaz hromadného/automatizovaného zakladania účtov,
/support — nová otázka „Ako začnem rozhovor?“, /download, obchody, poznámky pre kontrolórov, feature grafika „For
adults 18+“). /delete-account sa nemenil (pozvánky nespomínal).

**D88 — zistenia pri overení (opravené / zapísané):**
- **Cache a SRI pri úprave textov MAS:** prvá verzia `mas-assets.py` prepisovala preklady pod pôvodnými menami súborov.
  MAS posiela assets s `Cache-Control: public, immutable, max-age=31536000`, takže prehliadač, ktorý ich už mal
  (Chrome v emulátore po skorších prihláseniach), odmietol `modulepreload` pre nesúhlasný SRI a stránka registrácie
  ukazovala surové kľúče prekladov (`common.username`…). To isté by postihlo správu účtu `/account` (`app.html`
  prednačítava jazyk rovnako). Oprava (nasadená, overená v emulátore aj Playwright): upravené súbory dostanú nové
  meno `…-p<tag>.js` a premenuje sa aj každý súbor, ktorý na ne odkazuje (mapa jazykov `mountIsland`, vstupné
  body, chunky účtu — spolu 52 súborov), manifest dostane nové mená a SRI; pôvodné súbory ostávajú nezmenené
  (overené: pôvodný `en-DUv-zzDo.js` má opäť pôvodný hash), takže staré cache nič nerozbijú.
- **Testovacie kľúče hCaptcha v MAS nefungujú:** MAS 1.29 po overení tokenu porovná `hostname` z odpovede hCaptcha
  so svojou doménou (`crates/handlers/src/captcha.rs`); testovacie kľúče vracajú `dummy-key-pass`, preto MAS
  odmietne každú registráciu s nimi. Celú registráciu s testovacími kľúčmi teda overiť nejde. Smoke 1.3 v CI
  overuje: bez tokenu a s neplatným tokenom odmietnuté, testovací token hCaptcha potvrdí, MAS ho odmietne (token
  overuje na serveri), a celú registráciu bez kroku s kódom na lokálnom stacku s dočasne vypnutou captcha.
- **iOS Debug assert:** pri vytvorení DM s človekom, ktorý ešte nemá kryptografickú identitu (nikdy sa neprihlásil),
  upstream `RoomScreenViewModel.updateVerificationBadge` volá `MXLog.failure` → v Debug builde (XCUITest) pád, v
  release (TestFlight) len záznam v logu. Nesúvisí s D88 (rovnako pri plnom MXID); test používa adresáta s identitou.
- Web: v predvolenom vyhľadávaní (Ctrl+K) sa profil hľadá až vo filtri „Ľudia/People“ — upstream správanie, ako pri
  plnom MXID. Hlavná cesta „Začať rozhovor“ nájde krátke meno priamo.

**D89 — Značka psst na stránkach MAS, overenie iOS Release pri novom kontakte.**

**Ako (MAS 1.29.0, bez forku MAS):** titulok karty je serverový preklad `app.name` („matrix-authentication-service“)
→ upravené serverové preklady (`translations/*.json`: `app.name` = `app.human_name` = „psst“, „Matrix ID“ → „meno
účtu“, „matrix-authentication-service“ v texte rozsahu admin → „psst“) a dve šablóny (`base.html` pre serverové
stránky, `app.html` pre správu účtu): `<html class="cpd-theme-dark">` (tmavá téma Compound, ktorú CSS MAS už
obsahuje — vynútená bez ohľadu na systém), favicon a apple-touch-icon z psst.pro, `theme-color`, logo psst (malé
inline SVG + „psst“) nad obsahom a krátky inline skript, ktorý nastaví titulok „psst – <nadpis h1 stránky>“ (aj keď
React nadpis zmení). Šablóny samy titulok podstránok nemajú (stránky neprepisujú `block title`), preto skript;
bez JS ostáva titulok „psst“. Všetko robí `server/scripts/mas-assets.py` pri deployi z image MAS (rovnako ako D88)
a pripojí sa read-only na predvolené cesty `/usr/local/share/mas-cli/{templates,translations}` — pri novej verzii
MAS sa zopakuje; ak sa nájdu očakávané miesta v šablónach, inak deploy skončí. MAS neposiela CSP, inline štýl a
skript prejdú. Šablóny a serverové preklady sa renderujú na serveri → žiadny problém s cache (poučenie z D88).
`mas-cli templates check` s upravenými šablónami: 1585 renderov bez chyby.
**Frontend texty (React, s novými menami súborov ako v D88):** dialóg zmazania účtu bez „(MXID)“ a bez bodu
„You will be removed from the identity server…“ (psst identity server nepoužíva, bod by nebol pravdivý);
„Confirm your Matrix ID“ → „Confirm your account name“ / „Potvrďte meno svojho účtu“ (pole sa ukazuje len účtom
bez hesla). Staršie generácie premenovaných súborov (`-p<tag>`) sa pri synchronizácii nemažú.
**E-maily:** MAS žiadne neposiela (`email.transport: blackhole`); šablóny e-mailov aj tak neobsahujú Element/Matrix.
**Matrix ostáva** len vo formáte mena `@meno:psst.pro` a v licenčných hlavičkách šablón (nezobrazujú sa).
**Známe drobnosti (upstream):** časť textov MAS nemá slovenský preklad (napr. „Your account“, dialóg zmazania,
pätička „Privacy Policy / Terms & Conditions“) — ostáva anglicky; widget hCaptcha volí tému podľa systému (pri
svetlom systéme je na tmavej stránke svetlý); chyby z neplatných URL (napr. `authorize` bez `scope`) vracia MAS ako
holý text bez šablóny — bežný používateľ sa k nim nedostane.
**D89 — výsledky:** web (Chromium) EN aj SK 45/45 v čistom profile a 41/41 s cache z predchádzajúcej verzie
(prihlásenie, registrácia, obnovenie, chybové stránky, súhlas, účet, zariadenia, zmena hesla, reset identity,
dialóg zmazania); Android b54 (Chrome Custom Tab): „psst – Create an account“, „psst – Sign in“, „psst – Your
account“, tmavé, logo psst; iOS simulátor: registrácia a prihlásenie so značkou psst, súhlas so značkou (snímka).
**iOS Release (konfigurácia TestFlightu) pri novom kontakte nepadá:** build Release pre simulátor (CI ios-store,
`configuration=Release`, `ONLY_ACTIVE_ARCH=YES`), Start chat „qa-d89b“ (účet, ktorý sa nikdy neprihlásil) → QA
Novak → Send invite → DM vytvorený a správa odoslaná, test prešiel, žiadny crash report. Debug assert z D88 sa v
Release nekompiluje (`#if DEBUG`) → nič nemením, b4 netreba.
**Zistenie mimo MAS:** systémový dialóg iOS „„ElementX“ Wants to Use „chat.psst.pro“ to Sign In“ — iOS v ňom
ukazuje `CFBundleName`, ktorý je v b3 „ElementX“ (`CFBundleDisplayName` je „psst“). Oprava je vo forku
(`CFBundleName = $(APP_DISPLAY_NAME)`), do TestFlightu pôjde s ďalším buildom (táto dávka nové buildy nerobí);
v simulátore ju dokončiť overiť nestihol test (spadol na systémovom „Save Password?“).

**D91 — Registrácia s hCaptcha nefungovala: MAS porovnával hostname prísne, hCaptcha vracia nadradenú doménu.**
Príznak: po vyriešení hCaptcha MAS vrátil „CAPTCHA verification failed“; nikto sa nevedel zaregistrovať (dávka 21
celú registráciu s ostrými kľúčmi neoverila — testovacie kľúče MAS odmietal, čo bol ten istý problém).
Príčina: MAS 1.29.0 (`crates/handlers/src/captcha.rs`) po úspešnom `siteverify` vyžaduje `hostname == chat.psst.pro`;
hCaptcha vracia registrovateľnú doménu (`psst.pro`) aj pri subdoméne v nastaveniach — upstream issue #3549 (otvorené,
oprava PR #5376 zatvorená bez zlúčenia; `main` aj 1.30.0-rc.0 majú stále prísnu kontrolu). Handler výsledok iba
prevedie na `is_ok()`, preto v logoch nič nebolo. Secret je platný (siteverify s neplatným tokenom → `invalid-input-
response`, nie `invalid-input-secret`), site key sedí (d49cfb64-…), MAS posiela secret, response a remoteip klienta.
Hodnotu hostname z ostrého tokenu som priamo nevidel: automat dostal obrázkovú výzvu a CAPTCHA neobchádzam.
Oprava: vlastný build MAS 1.29.0 s malým patchom (`server/mas/psst-captcha-hostname.patch`): hostname sa prijme, ak
je doménou stránky alebo jej nadradenou doménou (s bodkou, bez rozlíšenia veľkosti písmen; holá TLD nie), hostname
testovacích kľúčov „dummy-key-pass“ len pri oficiálnom testovacom sitekey; dôvod zamietnutia sa loguje (WARN).
Binárka zostavená oficiálnym Dockerfile v CI (`mas-build.yml`, unit test funkcie), release `mas-1.29.0-psst1`, SHA-256
pripnutý v `server/mas/mas-cli.sha256`; `server/mas/Dockerfile` = oficiálny obraz + táto binárka (šablóny, preklady,
assets a politika ostávajú oficiálne). Pred nasadením záloha DB MAS (`backups/mas-pre-d91-20261120T1650Z.dump`).
Overenie na produkcii: na <1 min testovacie kľúče, registrácia cez webový formulár v prehliadači (súhlas 18+,
hCaptcha) → účet qa-d91a vznikol so súhlasom s podmienkami → deaktivovaný; ostré kľúče späť (hash = ~/psst-keys).
Iné formuláre s CAPTCHA MAS nemá (obnova hesla je vypnutá). Pri aktualizácii MAS treba patch preniesť alebo overiť,
či upstream chybu opravil.

**D92 — Správca psst je odteraz účet `gg` (namiesto `geo`).** Majiteľ si 21. 11. 2026 o 07:20 UTC vytvoril cez
otvorenú registráciu účet `@gg:psst.pro` a o 07:24 UTC si sám deaktivoval `@geo:psst.pro` (MAS `deactivated_at`,
Synapse `deactivated=1`; nič som na ňom nemenil — ostáva deaktivovaný, s príznakom admin v MAS, prihlásiť sa nedá).
Správcovské práva v psst sú jediné: MAS `can_request_admin` (z neho MAS vydáva rozsah `urn:synapse:admin:*` pre
Synapse admin API a admin stránka `/admin` ho overuje cez MAS admin API každých 5 min); Synapse príznak `admin` sa
pri MAS nepoužíva (aj geo mal 0). `gg` dostal `mas-cli manage promote-admin gg` → MAS admin API: `admin=true`,
aktívny. Admin stránka: `gg` pridaný do chránených účtov (`ADMIN_PROTECTED_USERS` predvolené `gg,geo,psstadmin` —
nedá sa zablokovať ani mu resetovať heslo z /admin), kontajner `admin` prestavaný a reštartovaný. `.env`
`OPERATOR_CONTACT` a príkaz nasadenia v poznámkach: `@gg:psst.pro`. Záložný servisný správca `psstadmin` funguje
(MAS admin, Synapse admin token cez `members.sh list`). `review` a `review-partner` bez zmeny (nie sú admin).
Poznámka: deaktivované testovacie účty `qa-rpadm`, `qa-d88adm` majú v MAS ešte príznak admin — prihlásiť sa nedajú.

**D93 — Deaktivované účty natrvalo vymazané (104: `geo` + 103 testovacích `qa-*`).** Majiteľ potvrdil, že ich
nepotrebuje. Pred mazaním zoznam (`DELETED-ACCOUNTS.md`, MAS a Synapse zhodne 104, bez gg/psstadmin/review/
review-partner a bez aktívnych účtov — overené skriptom) a záloha oboch databáz (`backups/*-pre-d93-20261121T0822Z.dump`).
Synapse: deaktivácia s GDPR vymazaním (`erase: true`) pre všetkých — meno, avatar a príznak erased (správy erased
používateľov Synapse noví členovia nevidia), zariadenia 237 → 0, tokeny 0; udalosti v ostávajúcich miestnostiach
žiadne. Synapse ani MAS 1.29 neumožňujú zmazať samotný riadok používateľa (MAS: admin API a CLI bez delete) → v MAS
ostávajú deaktivované a zamknuté, bez admin príznaku, e-mailov a relácií; meno účtu sa tým nedá znova zaregistrovať
(MAS ho drží obsadené), čo je pri zmazaných účtoch žiadúce. Miestnosti bez aktívneho člena neboli (4 miestnosti,
všetky s aktívnym členom). Overené: zmazaný účet sa neprihlási (403) ani nenájde (profil 404), správcovia len gg a
psstadmin, review a review-partner sa prihlásia s rozhovorom a skupinou na mieste.

**D94 — Zvyšky značky Element (26.11.1).** Spoločná špecifikácia `docs/psst-26.11.1-spec.md`. Zoznamy nájdených
a opravených miest: `forks/{android,ios,web}/PSST-ELEMENT-REMNANTS.md`. Android: prepisy v app module
(`psst_overrides.xml`, Localazy ich neprepíše) — názov aktivity hovoru, texty hovoru, zvuky „psst (predvolený)“,
názov zariadenia „psst Android“. iOS: `InfoPlist.strings` vo všetkých jazykoch prebíjali texty povolení „Element X“;
dialóg zdieľania obrazovky v hovore („Element X, file://“) je výzva WebKitu s `CFBundleName`, ktorý je od D89/b4
„psst“ — vlastné broadcast rozšírenie psst nemá. Web/desktop: logo a alt chybovej stránky a prihlásenia, mobilný
sprievodca, názov widgetu hovoru, konfiguračné chyby, macOS texty povolení (kamera, mikrofón, poloha). Ostáva
licenčný text „upravená verzia Element“ a nedosiahnuteľné Element Pro / Classic texty a vývojárske nastavenia.

**D95 — Miznúce správy, základ (rozsah potvrdil majiteľ).** Štandard MSC1763 `m.room.retention` {max_lifetime}
(5 min, 1 h, 1 deň, 1 týždeň; vypnuté = {}), meniť môže, kto smie poslať tento stav (v DM obaja). Server: Synapse
`retention` (allowed 5m–1w, purge každých 5 min) + `experimental_features.msc1763_enabled`; mazanie aj v šifrovaných
rozhovoroch (nečíta obsah); nemaže stavové udalosti, poslednú udalosť miestnosti (ostane skrytá) ani médiá.
Klienti: voľba v nastaveniach rozhovoru, text v časovej osi, skrytie expirovaných správ (aj offline; web: js-sdk
MSC1763 maže aj z IndexedDB). NIE v tejto verzii (ďalšia etapa, odhad 6–8 týždňov): mazanie z lokálnej DB a
vyhľadávacieho indexu v Element X (Rust SDK nemá podporu, iOS by potreboval vlastný build SDK), z indexu desktopu
(Seshat), mazanie príloh v šifrovaných rozhovoroch na serveri (server nevie, ku ktorej miestnosti patria).

**D96 — Ochrana obrazovky.** Vlastný stav `eu.macet.psst.screen_protection` {enabled}. Android: FLAG_SECURE, kým je
otvorený chránený rozhovor (zdieľané so zámkom PIN cez `PsstSecureWindow`), Android 14+ ScreenCaptureCallback
→ upozornenie (pri FLAG_SECURE sa snímka spravidla nepodarí, upozornenie je pre prípad, že áno). iOS: prekrytie pri
nahrávaní/zrkadlení a v prepínači appiek, upozornenie pri `userDidTakeScreenshotNotification` — len verejné API, nie
trik s isSecureTextEntry (App Review 2.5.1). Desktop: `setContentProtection` počas chráneného rozhovoru (IPC
`psstScreenProtection`). Web: len pravdivé upozornenie. Upozornenie o snímke = `m.notice` s `eu.macet.psst.screenshot`.

**D97 — Poloha späť, len na vyžiadanie.** Poslať polohu + živé zdieľanie 15/60 min (Matrix beacons), povolenie až
pri prvom použití s pravdivým textom; Android FINE/COARSE + FOREGROUND_SERVICE_LOCATION, nikdy
ACCESS_BACKGROUND_LOCATION (`check-manifest.py`). Mapy: OpenFreeMap (OpenStreetMap, bez kľúča, nie reklamná firma)
cez proxy psst `app.psst.pro/maps/` (nginx prepíše URL v JSON, cache 7 dní) — poskytovateľ máp vidí len IP servera.
Statické náhľady sa vykresľujú v zariadení (MapLibre snapshotter), nie cez MapTiler static API. Obchody: poloha
„collected“ (Google: E2EE výnimka neplatí pre verejné kanály; Apple: výnimku nemá) — `play-listing/FORMS.md`,
`DECLARATIONS.md` §2d (služba v popredí typu location, video), `appstore-listing/FORMS.md`.

**D98 — Appky len po slovensky a anglicky.** Element X dodával ~40 jazykov (Android `localeFilters`, iOS `*.lproj`);
tieto preklady stále hovorili „Element X“ a nemali texty psst, takže napr. pri nemčine v telefóne by sa zobrazila
zmes Element a anglických textov psst. Android: `localeFilters` en, sk + `locales_config.xml` (výber jazyka appky
v systéme ponúkne len tieto dva); iOS: odstránené ostatné `Localizations/*.lproj` a `Settings.bundle/*.lproj`, testy
lokalizácie prepnuté na sk. Ostatné jazyky systému dostanú angličtinu. Web/desktop: Element Web používa názov
značky (`brand` psst) cez premennú, preto ostáva bez zmeny; psst texty tam majú len SK/EN (ostatné jazyky → EN).
Súčasne opravené zobrazenie psst nastavení v časovej osi Android/iOS: Rust SDK hlási `m.room.retention` ako
`org.matrix.msc1763.retention` a filter Element X Android vyraďoval všetky vlastné stavy (aj ochranu obrazovky).

## psst lab — LoRa / Meshtastic s vlastným šifrovaním (2026-11-27, dávka L1, len vetva `lab/meshtastic`)

Testovacia iOS appka **psst lab** (`eu.macet.psst.lab`), nikam sa nezverejňuje. Kód je len vo vetvách
`lab/meshtastic` (hlavné repo aj fork `georgonr/psst-ios`); vetvy `main`/`psst`, ostré buildy a verzia 26.11.x sa
nemenili, server tiež nie. Návod a výsledky testov: [LAB-LORA.md](LAB-LORA.md).

**L1-01 — Samostatný variant appky na vlastnej vetve forku.** `lab/meshtastic` vo `psst-ios` vychádza z `psst`
(26.11.1, `c35055f`). Rozdiely voči psst sú len v `app.yml`, `target.yml`, ikone, štyroch miestach UI a v novom
balíku `Components/PsstLab`. `MARKETING_VERSION` ostáva 26.11.1 (rovnaký kód; Element X podľa verzie spúšťa
migrácie, iné číslo by ich mohlo spustiť nečakane), čísla buildov má psst lab vlastné od 1 — je to iný záznam
v App Store Connect (`psst lab`, SKU `psst-lab`, založil majiteľ; nič nové sa nezakladalo okrem profilu).

**L1-02 — Nič sa nezdieľa s psst.** Bundle `eu.macet.psst.lab`, skupina kľúčenky `<TEAM>.eu.macet.psst.lab`, **bez
App Group entitlementu** (`APP_GROUP_IDENTIFIER = group.eu.macet.psst.lab` je len hodnota v Info.plist; bez
entitlementu Element X použije vlastný kontajner appky — upstream fallback v `URL.appGroupContainerDirectory`).
Bez rozšírení NSE a Share (potrebujú App Group), bez push (`aps-environment`), universal links a Communication
Notifications. Dôsledky: psst lab **nedostáva push notifikácie** (Sygnal pozná len `eu.macet.psst`, server sa
nemení), zdieľanie z iných appiek do psst lab nejde. Appka sa dá nainštalovať vedľa psst. Overuje to CI (bundle ID,
žiadne PlugIns, entitlementy bez `application-groups`/`aps-environment`).

**L1-03 — Ten istý server psst.pro, bežný chat ako v psst.** Konfigurácia homeservera, MAS prihlásenie a všetky
funkcie chatu sú nezmenené. OAuth callback schéma `pro.psst.app` je v oboch appkách — `ASWebAuthenticationSession`
odovzdá callback priamo relácii, ktorá ho otvorila, takže sa appky nebijú. Pusher sa nezaregistruje (bez APNs tokenu).

**L1-04 — Meshtastic Client API, verzia.** Podľa meshtastic.org (client-api, docs 2.8, čítané 27. 11. 2026):
BLE služba `6ba1b218-15a8-461f-9fa8-5dcae273eafd`, ToRadio `f75c76d2-…` (zápis), FromRadio `2c55e69e-…` (čítanie
do prázdnej hodnoty), FromNum `ed9da18c-…` (notify); sériový stream s hlavičkou `0x94 0xC3 len_hi len_lo`
(max. 512 B). Spojenie: `ToRadio.want_config_id = nonce` → my_info, node_info…, kanály, config → `config_complete_id
= nonce`; potom pakety. Protobufy: oficiálne `meshtastic/protobufs` tag **v2.8.3** (2026-11-17); firmvér testovacieho
Heltecu je 2.7.26 — protobuf je spätne aj dopredne kompatibilný (overené: načítanie konfigurácie, uzly, správy, ACK).
Heartbeat každých 60 s (sériové API odpája nečinných klientov). Vzorom pre postup bola oficiálna appka
Meshtastic-Apple, **kód z nej sa nepreberal**.

**L1-05 — Licencie (overené v repozitároch).** `meshtastic/protobufs`: **GPL-3.0** (súbor LICENSE, v balíku
`Components/PsstLab/proto/LICENSE`) → vygenerovaný Swift kód je odvodené dielo pod GPL-3.0. SwiftProtobuf 1.33.3:
Apache-2.0 (zlučiteľná s GPLv3/AGPLv3). Meshtastic-Apple (GPL-3.0) len ako referencia, bez kopírovania kódu.
Zlučiteľnosť: GPLv3 §13 aj AGPLv3 §13 výslovne dovoľujú spojiť dielo pod GPLv3 s dielom pod AGPLv3 do jedného
programu; každá časť si ponechá svoju licenciu, celok sa šíri so zdrojovým kódom (fork je verejný na GitHube).
Dôsledok: alternatívna komerčná licencia Elementu (`LicenseRef-Element-Commercial`) sa na psst lab nevzťahuje — psst
používa AGPL, takže to nevadí. Distribúcia cez TestFlight má rovnaký status ako psst a oficiálna appka Meshtastic
(GPL-3.0) v App Store.

**L1-06 — Komunikačná vrstva oddelená od BLE.** Lokálny Swift balík `Components/PsstLab`: `MeshtasticProtobufs`
(generované), `PsstMesh` (Client API nad ľubovoľným transportom, uzly, kanály, správy, stavy doručenia, šifrovanie,
delenie, perzistencia), `PsstMeshBLE` (CoreBluetooth; protokolová logika `BLESession` je oddelená od CoreBluetooth
a testovaná s falošným spojením), `PsstMeshSerial` + nástroj `psst-mesh` (Mac, sériový port — ten istý `PsstMesh`
ako v appke), `PsstLabUI` (SwiftUI obrazovky LoRa). Balík sa kompiluje a testuje aj na Macu bez Xcode (Swift 6.1 CLT).

**L1-07 — Limity dĺžky.** API: `Data.payload` max. **233 B** (`DATA_PAYLOAD_LEN`), LoRa rámec 255 B (16 B
hlavička). Bežná textová správa Meshtastic: **200 B UTF-8** (ako oficiálne appky — rezerva na PKI réžiu 12 B).
Šifrovaný rámec psst ≤ 200 B (6 B hlavička + 194 B šifrovaného textu); jedna správa max. **8 rámcov** = **1 535 B**
textu (formát unesie 16). Namerané na vzduchu (LongFast EU868): plný rámec 236 B, **~2,0 s** vysielania; ACK ~0,5 s.

**L1-08 — Nastavenia rádia sa nemenia.** Appka ani `psst-mesh` nič nezapisujú do konfigurácie (región, kanály,
kľúče, čas), firmvér sa neaktualizuje. Jediná výnimka: ak rádio hlási región `UNSET`, appka ponúkne tlačidlo
a `psst-mesh test` pošle `AdminMessage.set_config(lora.region = EU_868)` — **tu sa nepoužilo**, Heltec mal EU_868.
Zistenie: Heltec má zapnuté MQTT („client proxy“) — firmvér ponúka klientovi kópie paketov na odoslanie do MQTT
(`msh/2/e/PKI/…`); psst lab ich ignoruje (nič neposiela na internet), ale iný pripojený klient by mohol. Obsah psst
správ je aj tam šifrovaný naším kľúčom.

**L1-09 — Vlastné šifrovanie (psst E2E) priamych správ.** Každý používateľ má statický pár X25519 v Keychain
(`AfterFirstUnlockThisDeviceOnly`, nesynchronizuje sa). Kľúč pre smer A→B = HKDF-SHA256(X25519(a, B),
salt „psst-lab/lora/v1“, info = „psst-lab/lora/v1 msg“ ‖ pubA ‖ pubB ‖ uzolA ‖ uzolB) — zvlášť pre každý smer, takže
rovnaké počítadlá na oboch stranách nikdy nepoužijú ten istý (kľúč, nonce). Šifra ChaCha20-Poly1305 (CryptoKit),
nonce = 8 nulových B ‖ počítadlo (UInt32), počítadlo sa uloží **pred** odoslaním. AAD = magic, počítadlo, počet
rámcov, uzol odosielateľa a príjemcu. Rámec: `0xB1` ‖ počítadlo (4 B) ‖ index<<4 | (počet−1) ‖ časť (šifrovaný text
‖ 16 B tag sa delí na rámce). Príjemca skladá podľa (uzol, počítadlo), otvorí až kompletnú správu; ochrana proti
opakovaniu = najvyššie počítadlo + okno 64 správ na kontakt (perzistentné), za videnú sa označí len overená správa.
Overenie odosielateľa vyplýva zo statického X25519 (tag vie vytvoriť len držiteľ súkromného kľúča kontaktu; smer
kľúča vylučuje odraz správy späť) + kontrola, že `from` paketu je uzol z karty. Bez podpisov (šetrí 64 B na rámec;
dôsledok: popierateľnosť medzi dvoma stranami, čo je pri 1:1 v poriadku). Port `PRIVATE_APP` (256), aby iné
appky Meshtastic nezobrazovali binárne dáta ako text. Rádio správu navyše zabalí do svojho PKI (log: „Use PKI!“).
**Nie je:** forward secrecy (únik kľúča odhalí aj zachytené staré správy), skrytie metadát (hlavička Meshtastic:
kto, komu, kedy), psst šifrovanie v kanáli (len 1:1).

**L1-10 — Výmena kľúčov.** Karta `psstlab1:<base64url>` = verzia, uzol (4 B), verejný kľúč (32 B), Matrix ID,
meno (~120 znakov). (a) Tlačidlo **„Prepojiť s LoRa“** v detaile 1:1 psst rozhovoru pošle do E2EE rozhovoru správu
`m.text` s čitateľným textom, odtlačkom kľúča a kartou (aj v poli `eu.macet.psst.lab.lora_card`). psst lab druhej
strany ju nájde pri zostavovaní časovej osi (`RoomTimelineItemFactory`) a prepojí kontakt **len ak odosielateľ
Matrix správy = Matrix ID v karte**; staršia karta nikdy neprepíše novšiu (porovnanie času udalosti). (b) **QR kód**
s tou istou kartou (LoRa → Môj kľúč / Prepojiť cez QR), pri ktorom dôvera vychádza z osobného stretnutia. Obe
obrazovky ukazujú odtlačok kľúča na porovnanie. Nová karta s iným kľúčom vynuluje počítadlá a okno pre ten uzol.

**L1-11 — Stavy doručenia.** *odosiela sa* (odovzdané rádiu) → *odoslané* (implicitné ACK: rádio počulo
preposlanie / vysielanie kanála) → *potvrdené* (ACK od cieľového uzla; delená správa až keď prídu ACK všetkých
rámcov) → *zlyhalo* (Routing chyba, napr. MAX_RETRANSMIT, alebo 120 s bez aktivity). Kanál končí na *odoslané*
(Meshtastic pri broadcaste ACK od príjemcov nemá). **Oprava po prvom teste naostro:** všetky 3 rámce delenej správy
odovzdané rádiu naraz → potvrdený len 1 z 3 do 120 s; po zavedení „stop-and-wait“ (ďalší rámec až po ACK/chybe
predošlého, max. 75 s na rámec) prešli 3/3.

**L1-12 — Uloženie.** Správy, uzly, kontakty, počítadlá a okná: JSON v Application Support appky
(`completeUntilFirstUserAuthentication`), mimo zálohy kľúčov; súkromný kľúč len v Keychain. Prežijú reštart.

**L1-13 — Bluetooth a poloha.** `NSBluetoothAlwaysUsageDescription` (EN + SK): „používa Bluetooth len na spojenie
s vaším vlastným LoRa rádiom Meshtastic … nesleduje iné zariadenia ani vašu polohu“. Povolenie sa vypýta až pri
otvorení LoRa (CBCentralManager vzniká lenivo). `UIBackgroundModes` + `bluetooth-central` (spojenie s rádiom pri
zamknutej obrazovke, lokálna notifikácia prijatej LoRa správy), **bez `location`** — živé zdieľanie polohy v psst lab
beží len v popredí (`LiveLocationManager` zapne `allowsBackgroundLocationUpdates` len pri režime `location`, inak
by appka spadla). Pozície z rádií sa ignorujú.

**L1-14 — Overenie.** Lokálny Mac (Intel, macOS 15.7) nemá Xcode; balík `PsstLab` sa testuje lokálne cez Swift 6.1
CLT (`swift test`, 31 testov) a naostro cez `psst-mesh` na sériovom porte. Appka sa kompiluje a podpisuje len v CI
(`ios-lab.yml`, runner `xcode-27`, verejný Xcode podľa D90). BLE na iPhone sa v CI overiť nedá (simulátor nemá
Bluetooth) → unit testy `BLESessionTests` + test na iPhone podľa LAB-LORA.md.

**L1-15 — Spúšťanie CI zápisom súboru.** `workflow_dispatch` funguje len pre workflowy na predvolenej vetve a lab
nesmie ísť do `main`. `ios-lab.yml` sa preto spúšťa pushom zmeny `lab/ios-lab-build.json` (ref, režim
`check`/`release`, číslo buildu, upload) do `lab/meshtastic`; robí to `scripts/ios/lab-testflight.sh`.
Podpis: existujúci certifikát Apple Distribution, nový profil „psst lab AppStore eu.macet.psst.lab …“ (jediný nový
objekt v Apple účte), secret `IOS_LAB_PROVISIONING_PROFILES_BASE64`. TestFlight: interná skupina „psst“ v appke
psst lab, tester Geo M, žiadni externí testeri, nič na kontrolu.

**L1-16 — Ikona a jazyk.** Ikona psst so žltým pásom „LAB“ (`Components/PsstLab/Scripts/make-lab-icon.swift`).
Sekcia LoRa je len po slovensky (testovacia appka); zvyšok appky ostáva SK/EN ako psst.
