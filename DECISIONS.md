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
