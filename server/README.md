# PSST server

Súkromný Matrix server pre PSST: **Synapse** (homeserver) + **PostgreSQL** + **LiveKit SFU** a
**lk-jwt-service** (hlasové/video hovory cez MatrixRTC / Element Call) + **Element Call** (samostatná
webová aplikácia na hovory) + **nginx** (TLS, reverzná proxy, PSST web) + **certbot** (Let's Encrypt).

Všetko je jeden `docker compose` projekt v adresári `server/`; všetky dáta sú v `server/data/`.
Nasadenie jedným príkazom: `./deploy.sh`.

## Služby

| služba | image | čo robí |
|---|---|---|
| `postgres` | `postgres:18.7-alpine` | databáza Synapse (UTF8, `C` collation). Dáta: `data/postgres/` |
| `synapse` | `ghcr.io/element-hq/synapse:v1.165.0` | Matrix homeserver `chat.macet.eu`. Registrácia **len s pozývacím tokenom**, bez federácie, bez hostí, bez presence a URL náhľadov, všetky miestnosti šifrované E2EE defaultne. Počúva len v internej sieti + `127.0.0.1:8008` na hostiteľovi. Dáta (médiá, **podpisový kľúč**): `data/synapse/` |
| `livekit` | `livekit/livekit-server:v1.13.11` | SFU pre audio/video hovory. Signalizácia `wss://chat.macet.eu/livekit/sfu` (cez nginx), médiá priamo: `7882/udp` (UDP mux) a `7881/tcp` (fallback) |
| `lk-jwt-service` | `ghcr.io/element-hq/lk-jwt-service:0.10.0` | MatrixRTC autorizačná služba: overí Matrix používateľa a vydá LiveKit token. Beží ako **application service** Synapse (MSC4502/MSC4512) a zároveň poskytuje staršie endpointy `https://chat.macet.eu/livekit/jwt/{sfu/get,get_token}` |
| `element-call` | `ghcr.io/element-hq/element-call:v0.28.2` | samostatná webová aplikácia na hovory na `https://call.macet.eu` (prihlásenie existujúcim PSST účtom) |
| `nginx` | `nginx:1.30.6-alpine` | TLS, `.well-known/matrix/client`, proxy na Synapse/LiveKit/jwt/Element Call, servíruje PSST web (`server/app/`) na `https://app.macet.eu` |
| `certbot` | `certbot/certbot:v5.10.0` | obnovuje Let's Encrypt certifikát (každých 12 h `certbot renew`, nginx sa reloaduje každých 6 h) |

### Hostnames a cesty

| URL | kam |
|---|---|
| `https://chat.macet.eu/_matrix/…`, `/_synapse/client/…` | Synapse client API |
| `https://chat.macet.eu/.well-known/matrix/client` | `m.homeserver` + `org.matrix.msc4143.rtc_foci` (CORS `*`) |
| `https://chat.macet.eu/.well-known/matrix/server` | **404** — federácia je vypnutá |
| `https://chat.macet.eu/_matrix/federation/…`, `/_matrix/key/…` | **404** |
| `https://chat.macet.eu/_synapse/admin/…` | **404** — admin API len cez SSH tunel |
| `https://chat.macet.eu/livekit/jwt/` | lk-jwt-service |
| `wss://chat.macet.eu/livekit/sfu/` | LiveKit signalizácia |
| `https://app.macet.eu/` | PSST web (Element Web fork) |
| `https://call.macet.eu/` | Element Call |

## Požiadavky na server

* Linux VPS (x86_64 alebo arm64), odporúčané ≥ 2 vCPU, 4 GB RAM, 40 GB disk (+ priestor na médiá)
* Docker Engine 24+ s pluginom Docker Compose v2 (`docker compose version`), `openssl`, `git`
* voliteľne `gh` (GitHub CLI) na stiahnutie PSST webu
* verejná IPv4 (a ideálne IPv6)

### DNS záznamy

Všetky tri mená na verejnú IP servera (zónu `macet.eu` apex netreba meniť — `server_name` je priamo
`chat.macet.eu`, delegácia `.well-known` je na ňom):

```
chat.macet.eu.   A     <IPv4 servera>
app.macet.eu.    A     <IPv4 servera>
call.macet.eu.   A     <IPv4 servera>
; ak má server IPv6:
chat.macet.eu.   AAAA  <IPv6 servera>
app.macet.eu.    AAAA  <IPv6 servera>
call.macet.eu.   AAAA  <IPv6 servera>
```

Žiadny SRV `_matrix._tcp` záznam (federácia je vypnutá).

### Firewall

Otvoriť **len**:

| port | protokol | účel |
|---|---|---|
| 80 | TCP | HTTP → HTTPS presmerovanie + Let's Encrypt HTTP-01 |
| 443 | TCP | HTTPS (Matrix, web, Element Call, LiveKit signalizácia) |
| 7881 | TCP | LiveKit WebRTC cez TCP (fallback) |
| 7882 | UDP | LiveKit WebRTC médiá (UDP mux) |
| 22 | TCP | SSH (správa; ideálne obmedziť na vlastné IP) |

Nič iné. Port 8008 (Synapse) je publikovaný len na `127.0.0.1`, 8448 sa nepublikuje vôbec.
Pozor: Docker obchádza `ufw` pre publikované porty — preto sú interné služby publikované len na loopback
alebo vôbec. Príklad pre `ufw`:

```sh
ufw default deny incoming
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 7881/tcp && ufw allow 7882/udp
ufw enable
```

**TURN**: nie je nasadený. Klienti za prísnym firewallom, ktorý blokuje UDP aj TCP 7881, sa na hovor
nepripoja. Ak to bude problém, zapnite vstavaný TURN v LiveKit (`turn:` v
`templates/livekit/livekit.yaml`, ideálne TURN/TLS na 443 s vlastnou doménou, napr. `turn.macet.eu`, a
samostatnou IP alebo SNI routingom) — viď [LiveKit docs](https://docs.livekit.io/home/self-hosting/deployment/).

## Nasadenie (jeden príkaz)

```sh
git clone https://github.com/georgonr/psst.git
cd psst/server
LETSENCRYPT_EMAIL=admin@macet.eu ./deploy.sh
```

`deploy.sh` je idempotentný (prvé nasadenie aj aktualizácia):

1. vytvorí `server/.env` s náhodnými tajomstvami (heslo DB, `registration_shared_secret`,
   `macaroon_secret_key`, `form_secret`, LiveKit API kľúč a secret, tokeny application service);
   existujúce hodnoty nikdy neprepíše,
2. vyrenderuje konfigurácie z `templates/` do `data/config/`,
3. vytvorí dočasný self-signed certifikát, aby mohol nginx naštartovať,
4. `docker compose pull` + `up -d`, počká na healthchecky,
5. ak je certifikát ešte dočasný: `certbot certonly --webroot` pre `chat.`, `app.`, `call.macet.eu`
   (jeden SAN certifikát `psst`) a reload nginx. Obnova je automatická (kontajner `certbot`).

Prepínače: `--staging` (LE staging na skúšku), `--no-letsencrypt` (ostane self-signed — lokálny test),
`--no-pull`. Ak certbot zlyhá (DNS ešte nepropagované, zatvorený port 80), skript vráti dočasný
certifikát a stačí ho neskôr spustiť znova.

Potom:

```sh
scripts/create-admin.sh admin          # prvý admin (heslo vypíše raz) + uloží admin token do secrets/
scripts/fetch-web.sh                   # stiahne PSST web (artefakt psst-web-dist z GitHub Actions)
scripts/new-invite.sh                  # prvý pozývací token
```

### PSST web (app.macet.eu)

`scripts/fetch-web.sh` stiahne najnovší artefakt `psst-web-dist` z `georgonr/psst` cez `gh run download`
(treba `gh auth login`), alebo z URL: `PSST_WEB_DIST_URL=https://…/psst-web.tar.gz scripts/fetch-web.sh`,
alebo z konkrétneho behu: `PSST_WEB_RUN_ID=<id> scripts/fetch-web.sh`. Súbory sa atomicky vymenia
v `server/app/`; reštart netreba. Ak distribúcia neobsahuje `config.json`, nginx servíruje serverový
default z `templates/app/config.json` (homeserver `https://chat.macet.eu`, bez vlastných serverov,
bez hostí). `index.html`, `config*.json`, `version`, `i18n/` majú `Cache-Control: no-cache`,
`bundles/` sú cacheované natrvalo (hashované názvy).

## Pozývacie tokeny (registrácia)

Registrácia je možná **iba** s tokenom (`registration_requires_token: true`, bez e-mailu a captchy).

```sh
scripts/new-invite.sh            # 1 použitie, platnosť 7 dní
scripts/new-invite.sh 5 30       # 5 použití, 30 dní
scripts/new-invite.sh --list     # zoznam tokenov
```

Token pošlite pozvanému; v PSST aplikácii pri registrácii zadá meno, heslo a token.
Skript volá admin API zvnútra kontajnera s tokenom zo `secrets/admin_token` (alebo `SYNAPSE_ADMIN_TOKEN`).

### Admin API cez SSH tunel

Admin API (`/_synapse/admin`) nie je z internetu dostupné. Z vlastného počítača:

```sh
ssh -N -L 8008:127.0.0.1:8008 user@chat.macet.eu
curl -H "Authorization: Bearer <admin token>" http://127.0.0.1:8008/_synapse/admin/v1/server_version
```

Funguje aj [synapse-admin](https://github.com/etkecc/synapse-admin) s homeserverom `http://127.0.0.1:8008`.

## Záloha

```sh
scripts/backup.sh                 # → server/backups/psst-backup-<čas>.tar.gz (chmod 600)
```

Záloha beží za chodu a obsahuje:

* `db.dump` — `pg_dump -Fc` databázy (účty, miestnosti, udalosti, šifrované kľúče zálohy…),
* `synapse-data.tar.gz` — `media_store` (obrázky, súbory) a **podpisový kľúč servera**
  `chat.macet.eu.signing.key`; bez neho server po obnove dostane novú identitu,
* `signing.key` — ten istý kľúč ešte raz samostatne,
* `env` — `server/.env`: heslo DB, `registration_shared_secret`, `macaroon_secret_key` (bez neho sa
  zneplatnia prihlásenia), `form_secret`, **LiveKit API kľúč/secret**, tokeny application service,
* `secrets/` — admin token, `letsencrypt.tar.gz` — certifikáty (dajú sa vystaviť znova).

Archív obsahuje tajomstvá — kopírujte ho šifrovane mimo servera (napr. `age`/`gpg` + `rsync`/`restic`).
Príklad cronu (denne 03:30): `30 3 * * * cd /opt/psst/server && scripts/backup.sh >/dev/null && find backups -mtime +14 -delete`.

## Obnova / migrácia na iný server

```sh
# na novom serveri (DNS ešte smeruje na starý alebo už na nový)
git clone https://github.com/georgonr/psst.git && cd psst/server
scp starý:/opt/psst/server/backups/psst-backup-XYZ.tar.gz .
scripts/restore.sh psst-backup-XYZ.tar.gz
```

`restore.sh` obnoví `.env` a `secrets/`, rozbalí Synapse dáta (médiá + podpisový kľúč) s vlastníkom
UID 991, obnoví certifikáty, spustí PostgreSQL (nová DB s `C` collation) a `pg_restore`, nakoniec
`./deploy.sh`. Potom prepnite DNS A/AAAA záznamy na novú IP a znovu stiahnite web (`scripts/fetch-web.sh`).

Alternatíva bez zálohy (s odstávkou): `docker compose down` na starom serveri a skopírovať celý adresár
`server/` (`rsync -aHAX --numeric-ids` ako root, aby ostali vlastníci `data/`), na novom `./deploy.sh`.

`server_name` (`chat.macet.eu`) sa po prvom spustení meniť nedá.

## Aktualizácia

```sh
cd psst && git pull                 # nové verzie image sú pinnuté v server/compose.yml
cd server && scripts/backup.sh      # vždy najprv záloha
./deploy.sh                         # pull + recreate; Synapse si DB migruje sám
docker compose logs -f synapse      # kontrola
```

Postup pri zvyšovaní verzií (v repe): zmeniť tag v `compose.yml`, prečítať release notes (najmä
[Synapse upgrade notes](https://element-hq.github.io/synapse/latest/upgrade.html)), pushnúť — CI
workflow `server-smoke` stack overí (registrácia, E2EE, MatrixRTC) — a až potom `git pull && ./deploy.sh`
na serveri. Hlavnú verziu PostgreSQL (napr. 18 → 19) nemeniť len tagom: `scripts/backup.sh`, zmeniť tag,
`docker compose down`, presunúť `data/postgres` bokom, `scripts/restore.sh … --force`.

## Prevádzka

```sh
docker compose ps                   # stav (všetko má healthcheck)
docker compose logs -f nginx synapse
docker compose restart synapse
docker compose down                 # zastavenie (dáta ostávajú v data/)
```

## Lokálny test

Lokálne (bez DNS a Let's Encrypt) — tak beží aj CI `ci/workflows/server-smoke.yml`:

```sh
echo "127.0.0.1 chat.macet.eu app.macet.eu call.macet.eu" | sudo tee -a /etc/hosts
export COMPOSE_FILE=compose.yml:compose.test.yml LIVEKIT_USE_EXTERNAL_IP=false
./deploy.sh --no-letsencrypt
pip install "matrix-nio[e2e]==0.26.0" requests && python ../tests/server/smoke_test.py
```

## Súbory

```
server/
  compose.yml            produkčný stack (pinnuté verzie)
  compose.test.yml       override pre lokálny/CI test (bez certbota, self-signed TLS)
  deploy.sh              nasadenie jedným príkazom
  .env.example           popis premenných (.env generuje deploy.sh)
  templates/             šablóny konfigurácií (synapse, livekit, nginx, element-call, app)
  scripts/               create-admin, new-invite, fetch-web, backup, restore
  app/                   PSST web distribúcia (sťahuje fetch-web.sh, necommituje sa)
  data/                  VŠETKY dáta + vyrenderované konfigurácie (necommituje sa)
  secrets/               admin token (necommituje sa)
```
