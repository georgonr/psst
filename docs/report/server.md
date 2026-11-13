# Server — report (2026-11-13)

## Čo je hotové

* `server/` — docker compose stack nasaditeľný jedným príkazom `./deploy.sh`:
  Synapse `v1.165.0` + PostgreSQL `18.7-alpine` (C collation), LiveKit `v1.13.11`,
  lk-jwt-service `0.10.0` (application service MSC4502/MSC4512 + legacy endpointy), Element Call
  `v0.28.2` (`call.macet.eu`), nginx `1.30.6-alpine` (chat./app./call.macet.eu, .well-known s `rtc_foci`),
  certbot `v5.10.0` (bootstrap dummy → LE webroot → reload, automatická obnova).
* Šablóny konfigurácií `server/templates/` (Synapse, AS registrácia, LiveKit, nginx, Element Call,
  default `config.json` pre PSST web), tajomstvá generované do `server/.env` (nikdy v gite).
* Skripty: `scripts/create-admin.sh`, `scripts/new-invite.sh`, `scripts/fetch-web.sh`
  (`gh run download -n psst-web-dist` / `PSST_WEB_DIST_URL`), `scripts/backup.sh`, `scripts/restore.sh`.
* `server/README.md` (SK): služby, nasadenie, DNS, firewall, tokeny, admin cez SSH tunel, záloha,
  obnova/migrácia, upgrade.
* `tests/server/smoke_test.py` + workflow `ci/workflows/server-smoke.yml` (pôvodne
  `.github/workflows/`, viď nižšie).
* `docs/decisions/server.md`, `docs/build/server.md`.

## Overenie

### CI smoke test — **PENDING: requires workflow scope**

GitHub odmietol push `.github/workflows/server-smoke.yml`: token účtu `georgonr` nemá scope `workflow`
(`refusing to allow an OAuth App to create or update workflow … without workflow scope`). Workflow je
preto v `ci/workflows/server-smoke.yml`; po `gh auth refresh -h github.com -s workflow` ho aktivuje
`scripts/enable-ci.sh` a spustí sa `gh workflow run server-smoke.yml`. **Žiadny CI beh zatiaľ neprebehol
→ run URL: žiadna.**

| # | kontrola | stav |
|---|---|---|
| 0 | `docker compose config` produkčného compose (CI) | pending: requires workflow scope |
| 1.1 | Synapse health + client API cez nginx | pending: requires workflow scope |
| 1.2 | admin cez shared secret (`create-admin.sh`) | pending: requires workflow scope |
| 1.3 | registračné tokeny cez admin API (`new-invite.sh`) | pending: requires workflow scope |
| 1.4 | admin API verejne 404, z loopbacku 200 | pending: requires workflow scope |
| 2.1 | registrácia bez tokenu odmietnutá (+ guest 403) | pending: requires workflow scope |
| 2.2 | neplatný token odmietnutý | pending: requires workflow scope |
| 2.3 | registrácia s tokenom (alice, bob, carol), jednorazový token 2× odmietnutý | pending: requires workflow scope |
| 3.1 | federácia vypnutá (404 endpointy, 8448 zatvorený, žiadny federation listener) | pending: requires workflow scope |
| 4.1 | E2EE DM alice→bob (megolm, bob dešifruje, server má len `m.room.encrypted`) | pending: requires workflow scope |
| 5.1 | E2EE skupina (3 účastníci, šifrovaná serverovým defaultom) | pending: requires workflow scope |
| 6.1 | `.well-known/matrix/client` + `rtc_foci` + CORS | pending: requires workflow scope |
| 6.2 | `/_matrix/client/v1/rtc/transports` | pending: requires workflow scope |
| 6.3 | lk-jwt `/healthz` + LiveKit cez nginx | pending: requires workflow scope |
| 6.4 | MatrixRTC legacy `/sfu/get` + `/get_token` (OpenID cez interný 8448) + LiveKit validate | pending: requires workflow scope |
| 6.5 | MatrixRTC C-S `/rtc/livekit/get_token` (Synapse → AS proxy), nečlen 403 | pending: requires workflow scope |
| 6.6 | všetky kontajnery healthy | pending: requires workflow scope |
| 7.1 | app.macet.eu index/config.json/hlavičky | pending: requires workflow scope |
| 7.2 | call.macet.eu + HTTP→HTTPS + ACME webroot | pending: requires workflow scope |
| — | `scripts/backup.sh` obsahuje `db.dump` + `signing.key` | pending: requires workflow scope |

### Lokálna statická validácia (vykonaná, bez Dockeru)

| kontrola | výsledok |
|---|---|
| `bash -n` všetkých skriptov | PASS |
| `py_compile tests/server/smoke_test.py` | PASS |
| YAML parse compose/workflow/šablón, JSON parse configov | PASS |
| `compose.yml` + `compose.test.yml` proti compose-spec JSON schéme (interpolované `.env.example`) | PASS |
| render šablón (žiadne nenahradené `__PREMENNÉ__`) | PASS |
| Synapse config parse / `nginx -t` lokálne | nespustené (pip build Synapse >1 GB Rust, brew nginx zo zdrojov — disk ~5 GB) |

Konfigurácia bola navyše manuálne porovnaná so zdrojmi: Synapse 1.165 `experimental.py` (msc4143/4502/4512
existujú, msc3266/msc4222 sú stabilné a flagy odstránené), config dokumentácia (`matrix_rtc.transports`,
`rc_delayed_event_mgmt`, `max_event_delay_duration`), lk-jwt-service 0.10.0 README a zdroj (env premenné,
OpenID lookup `well-known m.server → :8448` bez SRV, `LIVEKIT_URL` musí sedieť s `url` v C-S požiadavke,
Twirp volania zachovávajú path prefix `/livekit/sfu`), Element Call v0.28.2 self-hosting docs a Dockerfile
(`/app/config.json`, port 8080), LiveKit v1.13.11 config-sample (UDP mux `udp_port`).

## Otvorené body

1. **CI**: `gh auth refresh -h github.com -s workflow` → `scripts/enable-ci.sh` → `gh workflow run server-smoke.yml`;
   najrizikovejšie miesta pri prvom behu: MatrixRTC kontroly 6.4/6.5 (AS proxy MSC4512, interný OpenID
   8448 cez nginx alias) a E2EE cez matrix-nio 0.26 (vodozemac).
2. **DNS**: A (a AAAA) záznamy `chat.macet.eu`, `app.macet.eu`, `call.macet.eu` → IP servera (nevytvorené).
3. **Server/hostiteľ**: nie je vybraný/nasadený; potrebný Linux VPS s Dockerom (≥2 vCPU / 4 GB).
4. **Firewall**: otvoriť len 80/tcp, 443/tcp, 7881/tcp, 7882/udp (+ SSH).
5. **TURN** nie je nasadený (klienti za firewallom blokujúcim UDP aj TCP 7881 sa na hovor nepripoja).
6. **PSST web**: `scripts/fetch-web.sh` závisí od artefaktu `psst-web-dist` z web CI (tiež blokovaného
   rovnakým workflow scope); dovtedy app.macet.eu ukazuje dočasnú stránku.
7. `LETSENCRYPT_EMAIL` treba zadať pri prvom `./deploy.sh`.
8. Element Call standalone (`call.macet.eu`) funguje len s existujúcimi PSST účtami (registrácia na
   tokeny → žiadni anonymní hostia).
