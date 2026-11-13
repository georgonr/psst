# PSST server

> Produkcia (od 2026-11-13): DNS len pre `chat`, `app`, `call`, `push`.macet.eu — MAS na `https://chat.macet.eu/auth/`,
> ntfy na `push.macet.eu`, TURN/TLS zdieľa :443 s `call.macet.eu` (DECISIONS D42–D45).

Súkromný Matrix server pre PSST — jeden `docker compose` projekt, nasadenie jedným príkazom.
**Deň nasadenia krok za krokom: [DEPLOY-CHECKLIST.md](DEPLOY-CHECKLIST.md).**

```sh
sudo ./deploy.sh <IP_SERVERA> <EMAIL> [--contact "…"] [--hosting "…"] [--apple-team-id ID]
```

## Služby

| Služba | Image | Doména / port | Úloha |
|---|---|---|---|
| Synapse | `ghcr.io/element-hq/synapse:v1.165.0` | chat.macet.eu (len cez nginx; admin API 127.0.0.1:8008) | Matrix homeserver, federácia vypnutá |
| MAS | `ghcr.io/element-hq/matrix-authentication-service:1.29.0` | chat.macet.eu**/auth/** | účty, prihlásenie, **registrácia len s pozývacím tokenom** (aj z Element X) |
| PostgreSQL | `postgres:18.7-alpine` | interne | databázy `synapse` a `mas` |
| LiveKit | `livekit/livekit-server:v1.13.11` | chat.macet.eu/livekit/sfu, 7881/tcp, 7882/udp | SFU pre hovory |
| lk-jwt-service | `ghcr.io/element-hq/lk-jwt-service:0.10.0` | chat.macet.eu/livekit/jwt | MatrixRTC autorizácia |
| coturn | `coturn/coturn:4.18.0` (host sieť) | call.macet.eu:443 (TLS cez nginx, rozlíšené podľa ALPN) | TURN pre siete bez UDP; relay len na vlastnú SFU; 3478/udp sa nepublikuje |
| Element Call | `ghcr.io/element-hq/element-call:v0.28.2` | call.macet.eu | samostatná web appka hovorov |
| ntfy | `binwiederhier/ntfy:v2.37.2` | push.macet.eu | Android notifikácie (UnifiedPush + Matrix push brána) |
| Sygnal | `matrixdotorg/sygnal:v0.15.1` (profil `apns`) | chat.macet.eu/_matrix/push/v1/notify | iOS notifikácie (APNs) — po nahraní kľúča |
| nginx | `nginx:1.30.6-alpine` | 80, 443 | TLS, SNI smerovanie (stream), reverzná proxy, PSST web, právne stránky |
| certbot | `certbot/certbot:v5.10.0` | — | Let's Encrypt (obnova 2× denne) |

Port 443 obsluhuje nginx `stream`: SNI `call.macet.eu` **bez HTTP ALPN** (TURN klient WebRTC ALPN neposiela) → ukončí TLS → TURN-over-TCP na coturn; všetko
ostatné → interný HTTPS server (127.0.0.1:8443, PROXY protocol zachová IP klienta).
Všetky dáta sú v `server/data/`, tajomstvá v `server/.env` a `server/secrets/` (mimo gitu).

## Skripty

| Skript | Čo robí |
|---|---|
| `deploy.sh <IP> <email>` | pre-flight (Docker, DNS 6 subdomén, porty, disk, RAM) → hardening → tajomstvá → konfigurácie → štart → Let's Encrypt → cron |
| `scripts/harden.sh` | admin používateľ `psst` so SSH kľúčom, SSH len kľúčom, root login vypnutý (len ak kľúč existuje), UFW, fail2ban, unattended-upgrades |
| `scripts/members.sh` | `invite [počet] [dni]`, `list`, `block <meno> [--deactivate]`, `unblock`, `admin <meno>`, `password <meno>` |
| `scripts/healthcheck.sh` | kontajnery, všetky HTTPS endpointy, MAS, ntfy, Sygnal, TURN/TLS handshake, certifikát, disk, vek zálohy |
| `scripts/backup.sh` | šifrovaná záloha (AES-256, PBKDF2) — DB synapse + mas, médiá, **podpisový kľúč**, ntfy, konfigurácie, certifikáty, tajomstvá; rotácia 7/4/6; cron denne 03:17 |
| `scripts/restore.sh <archív.enc> [--force]` | obnova (aj na nový server); overí zhodu podpisového kľúča |
| `scripts/fetch-web.sh` | stiahne PSST web (posledný GitHub release) do `app/` za chodu |

## Registrácia a členovia

Verejná registrácia neexistuje. Admin vytvorí pozvánku (`members.sh invite`), nový člen v ktorejkoľvek appke
psst (Android, iOS, web, desktop) ťukne **Create account** → stránka MAS → meno, heslo, súhlas s podmienkami
→ **pozývací token** → zobrazované meno → späť v appke. Neplatný, expirovaný alebo vyčerpaný token MAS odmietne.

## Notifikácie

- **Android:** UnifiedPush cez vlastný ntfy. Člen si nainštaluje appku ntfy (F-Droid/GitHub), nastaví
  *Default server* `https://push.macet.eu` a vypne optimalizáciu batérie. Žiadny Google ani Element.
  ntfy povoľuje anonymne len náhodné témy `up*` (ostatné `deny-all`). Obsah správ sa do push neposiela
  (`push.include_content: false`), len ID udalosti.
- **iOS:** Sygnal → APNs. Nahrajte `AuthKey_<KEY_ID>.p8` do `secrets/apns/` a spustite
  `deploy.sh … --apple-team-id <TEAM_ID>` — Sygnal sa zapne sám (app_id `eu.macet.psst.ios.prod` / `.dev`).

## Zálohy a obnova

Heslová fráza `secrets/backup.pass` sa **nezálohuje** (bez nej je záloha nečitateľná) — uložte ju mimo servera.
Kópia záloh mimo servera: `BACKUP_RSYNC_TARGET=user@host:/cesta` v `.env`.
Migrácia na iný server: nový server podľa checklistu → `secrets/backup.pass` + archív → `scripts/restore.sh` →
presmerovať DNS → `./deploy.sh <nová IP> <email>`.

## Bezpečnosť

- federácia vypnutá (žiadny listener, nginx 404 pre `/_matrix/federation` a `/_matrix/key`, 8448 nie je verejný)
- admin API Synapse aj MAS len na 127.0.0.1 (SSH tunel), z internetu 404
- Docker publikuje verejne len 80, 443, 7881/tcp, 7882/udp (explicitne `0.0.0.0:`; `daemon.json` `"ip": "127.0.0.1"` + reťazec `DOCKER-USER`); coturn počúva len na bráne Docker siete; UFW zvyšok blokuje
- coturn nie je otvorený relay: `denied-peer-ip` všetko okrem IP servera, dočasné prihlasovacie údaje (TURN REST)
- E2EE predvolene vo všetkých nových miestnostiach; URL náhľady a presence vypnuté

## Lokálny test (bez domén a bez sudo)

```sh
./deploy.sh --local-test                      # self-signed certifikát, compose.test.yml
~/.local/psst-venv/bin/python ../tests/server/run_local.py   # smoke test
```
