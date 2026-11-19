# Server — rozhodnutia

Každé rozhodnutie: čo + prečo. Súbory: `server/`, `tests/server/`, `ci/workflows/server-smoke.yml`.

**S1 — Jeden docker compose projekt v `server/`, nasadenie `./deploy.sh`.**
Jeden príkaz robí všetko (tajomstvá, konfigurácie, dočasný certifikát, štart, Let's Encrypt) a je
idempotentný, takže ten istý príkaz slúži aj na aktualizáciu. Bez Ansible/Makefile — na serveri stačí
Docker, `openssl`, `sed`.

**S2 — Všetky dáta v `server/data/`, tajomstvá v `server/.env` + `server/secrets/`.**
Migrácia = skopírovať adresár (alebo `backup.sh` → `restore.sh`). Konfigurácie sa renderujú zo šablón
`server/templates/` do `data/config/` (`sed` náhrady `__PREMENNÁ__`), takže v gite nie sú žiadne
tajomstvá a zmena konfigurácie = úprava šablóny + `./deploy.sh`. `data/` je `chmod 700`.

**S3 — Verzie (pinnuté, najnovšie stabilné k 2026-11-13):** Synapse `v1.165.0`, PostgreSQL `18.7-alpine`,
LiveKit `v1.13.11`, lk-jwt-service `0.10.0`, Element Call `v0.28.2`, nginx `1.30.6-alpine` (stable vetva),
certbot `v5.10.0`. Pinnuté tagy → reprodukovateľné nasadenie, upgrade je vedomý krok overený CI.
PostgreSQL 18 (nie 17): aktuálna stabilná hlavná verzia, Synapse podporuje PG ≥ 14; DB sa inicializuje
s `--lc-collate=C --lc-ctype=C`, ako Synapse vyžaduje.

**S4 — (od D85) `server_name` = `psst.pro`, homeserver `chat.psst.pro`, delegácia cez `.well-known` na psst.pro.**
Pôvodne (pred D85) bol `server_name` zhodný s homeserverom, lebo apex pôvodnej domény nebol náš. Na psst.pro je
`/.well-known/matrix/client` (CORS `*`) aj `m.server` (len pre internú sieť, D85); homeserver ho má tiež. Obsahuje `m.homeserver` a `org.matrix.msc4143.rtc_foci`
(`livekit_service_url: https://chat.psst.pro/livekit/jwt`).

**S5 — Federácia vypnutá na troch úrovniach.** (1) Synapse nemá `federation` listener resource,
(2) `federation_domain_whitelist: []`, `trusted_key_servers: []`, `allow_public_rooms_over_federation: false`,
(3) nginx vracia 404 pre `/_matrix/federation/*`, `/_matrix/key/*` a `/.well-known/matrix/server`;
port 8448 sa nepublikuje. `/.well-known/matrix/server` sa **zámerne neposkytuje** (404) — iný server
by tak skúšal `chat.psst.pro:8448`, ktorý je zatvorený.

**S6 — Výnimka: OpenID userinfo len v internej sieti.** Staršie MatrixRTC endpointy lk-jwt-service
(`/sfu/get`, `/get_token`, ktoré používa `rtc_foci` z .well-known) overujú OpenID token klienta voláním
`https://<server_name>:8448/_matrix/federation/v1/openid/userinfo` (well-known m.server → fallback 8448;
SRV nepodporuje). Riešenie bez otvorenia federácie: Synapse má druhý listener `8009` len s resource
`openid`, nginx má interný `listen 8448 ssl` (nepublikovaný na hostiteľa), ktorý pustí **iba** túto
jednu cestu, a nginx má v Docker sieti alias `chat.psst.pro`. Kontajner lk-jwt-service tak dosiahne
`chat.psst.pro:8448` (s platným LE certifikátom) bez toho, aby bol zvonka dostupný.

**S7 — lk-jwt-service ako application service (MSC4502 + MSC4512) + legacy endpointy.**
README 0.10.0 označuje režim bez AS za zastaraný. Synapse 1.165 má `msc4502_enabled` (overenie
členstva v miestnosti) a `msc4512_enabled` (proxy `/_matrix/client/v1/rtc/livekit/*` na AS). AS
registrácia má `url: null` (žiadny tok udalostí) a nevýhradný namespace `.*`.
`LIVEKIT_FULL_ACCESS_HOMESERVERS=chat.psst.pro` (len jeden HS → legacy endpointy tiež overujú členstvo),
`LIVEKIT_REMOTE_CAN_PUBLISH_HOMESERVERS=""` (federácia nie je), `LIVEKIT_CS_API_URL_OVERRIDES`
→ `http://synapse:8008` (interne, bez hairpin NAT). LiveKit má `room.auto_create: false` — miestnosti
vytvára len lk-jwt-service. Webhook LiveKit → `http://lk-jwt-service:8080/sfu_webhook` (delegované
„leave“ udalosti MSC4140). Redis nepoužívame (stav v pamäti; pri reštarte sa stratia len práve
prebiehajúce delegované leave úlohy).

**S8 — MatrixRTC v Synapse.** `matrix_rtc.transports`: stabilný `m.livekit` (`url: wss://chat.psst.pro/livekit/sfu`)
+ zastaraný `livekit` s `livekit_service_url` pre staršie klienty; `msc4143_enabled` zapne aj nestabilný
endpoint transports (MSC4519). `max_event_delay_duration: 24h` (MSC4140), `rc_message` 0.5/s burst 30,
`rc_delayed_event_mgmt` 1/s burst 20 (Element Call self-hosting návod). `msc3266_enabled` a
`msc4222_enabled` sa **nepoužívajú** — obe MSC sú v Synapse 1.165 stabilné a flagy boli odstránené.

**S9 — Hostnames: všetko backendové na `chat.psst.pro`, web na `app.psst.pro`, Element Call na `call.psst.pro`.**
Jedna doména pre Matrix + `/livekit/jwt` + `/livekit/sfu` (odporúčanie Element Call: routing cestami) →
menej DNS záznamov a jeden certifikát. `call.psst.pro` je samostatná SPA (pre prehliadač bez PSST webu);
PSST web aj Element X používajú vložený Element Call, takže `call.` je voliteľný komfort. Jeden SAN
certifikát `psst` pre všetky tri mená.

**S10 — LiveKit médiá: UDP mux `7882/udp` + `7881/tcp`, `use_external_ip: true`, bez TURN.**
UDP mux = jeden port vo firewalle namiesto rozsahu 50000–60000 a funguje cez Docker bridge.
`use_external_ip` zistí verejnú IP cez STUN (VPS za NAT); dá sa prebiť `LIVEKIT_NODE_IP`. TURN nie je
nasadený (vyžaduje ďalšiu doménu/port 443 alebo 5349); TCP 7881 pokrýva väčšinu sietí bez UDP. V CI
`LIVEKIT_USE_EXTERNAL_IP=false`.

**S11 — Registrácia len s tokenom.** `enable_registration: true` + `registration_requires_token: true`,
bez e-mailu/captchy/3PID, `allow_guest_access: false`. Tokeny cez admin API (`scripts/new-invite.sh`,
default 1 použitie / 7 dní). Prvý admin cez `register_new_matrix_user` a `registration_shared_secret`
(`scripts/create-admin.sh`); jeho access token sa ukladá do `secrets/admin_token` (chmod 600), aby
`new-invite.sh` fungoval bez interaktívneho prihlásenia. Admin API volajú skripty zvnútra kontajnera
(`docker compose exec synapse curl`) → na hostiteľovi netreba curl/jq.

**S12 — Súkromie/predvolené nastavenia.** `presence.enabled: false`, `url_preview_enabled: false`,
`report_stats: false`, `enable_metrics: false`, `require_auth_for_profile_requests`,
`limit_profile_requests_to_users_who_share_rooms`, user directory len pre spoločné miestnosti,
**`encryption_enabled_by_default_for_room_type: all`** (aj skupiny sú E2EE bez ohľadu na klienta),
`max_upload_size: 100M`.

**S13 — Admin API nie je verejné.** nginx vracia 404 pre `/_synapse/admin`; Synapse port 8008 je
publikovaný len na `127.0.0.1` hostiteľa → prístup cez `ssh -L 8008:127.0.0.1:8008`.

**S14 — nginx: lenivé resolvovanie upstreamov** (`resolver 127.0.0.11` + premenné v `proxy_pass`),
takže nginx naštartuje/reloadne aj keď niektorý kontajner práve reštartuje. Cesty k Synapse sa
posielajú nezmenené (zakódované room ID), `/livekit/*` prefixy sa odrežú `rewrite … break`.
Neznámy `Host` na 443 → `444`. nginx počúva len IPv4 v kontajneri (`listen 443`, bez `[::]`) —
Docker často vypína IPv6 v kontajneroch a bind na `[::]` by zlyhal; IPv6 klientov hostiteľa preposiela Docker. HSTS, `nosniff`, `Referrer-Policy: no-referrer` všade.

**S15 — PSST web: CSP len `frame-ancestors 'self'` + `X-Frame-Options: SAMEORIGIN`.** Element Web má
vlastnú prísnu CSP v `<meta>` v `index.html`; serverová CSP s `script-src` by kolidovala s jeho
WASM/workermi pri každom upgrade. Cache podľa Element dokumentácie: `index.html`, `config*.json`,
`version`, `i18n/`… `no-cache`; `bundles/` `immutable`.
`config.json`: ak ho distribúcia obsahuje (web agent), použije sa; inak serverový default
(`templates/app/config.json`: `chat.psst.pro`, `disable_custom_urls`, `disable_guests`, bez 3PID).
Distribúcia sa sťahuje `scripts/fetch-web.sh` (`gh run download -n psst-web-dist` alebo `PSST_WEB_DIST_URL`).

**S16 — Let's Encrypt: certbot webroot, bootstrap dummy → nginx → certbot → reload.** `deploy.sh`
vytvorí self-signed certifikát (aby nginx naštartoval), po štarte ho zmaže a vyžiada skutočný;
pri zlyhaní vráti dočasný a skončí s chybou (opakovateľné). Obnova: kontajner `certbot` každých 12 h
`certbot renew`, nginx sa každých 6 h `nginx -s reload` (bez prístupu certbota k Docker socketu).

**S17 — Overenie (bod 7) v GitHub Actions, rovnaký `deploy.sh`.** `compose.test.yml` len vypne
certbota a TLS overovanie v lk-jwt-service (self-signed); inak beží identická produkčná konfigurácia
vrátane nginx, `server_name chat.psst.pro` a domén mapovaných v `/etc/hosts`. E2EE klient:
**matrix-nio[e2e] 0.26.0** (Olm/Megolm cez vodozemac — bez libolm) — Python, spoľahlivý v CI,
skutočné šifrovanie a dešifrovanie (overuje sa aj, že server uložil len `m.room.encrypted`).

**S18 — Zálohy:** `scripts/backup.sh` za chodu (pg_dump -Fc + tar `/data` Synapse + podpisový kľúč
samostatne + `.env` + secrets + certifikáty) do jedného `chmod 600` archívu; `scripts/restore.sh`
obnoví na čistom hostiteľovi a spustí `deploy.sh`.
