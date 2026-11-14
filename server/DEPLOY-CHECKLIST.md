# PSST — kontrolný zoznam na deň nasadenia

Všetko okrem bodov 1–4 spraví `deploy.sh`: inštaláciu Dockeru, hardening servera, tajomstvá, konfigurácie,
certifikáty Let's Encrypt, štart všetkých služieb, denné šifrované zálohy, healthcheck.

## 1. Objednať VPS

| | minimum | odporúčané |
|---|---|---|
| CPU | 2 vCPU | 4 vCPU (skupinové hovory s videom) |
| RAM | 4 GB | 8 GB |
| Disk | 40 GB SSD | 80 GB+ SSD (médiá rastú s používaním) |
| Sieť | 1 verejná IPv4, ≥ 2 TB prenosu/mesiac | neobmedzený prenos (video hovor ≈ 1–2 Mbit/s na účastníka) |
| OS | Debian 12/13 alebo Ubuntu 24.04 LTS (čistá inštalácia) | |
| Prístup | root cez **SSH kľúč** (nahrajte svoj verejný kľúč pri objednávke) | |
| Lokalita | EÚ (GDPR) | |

Príklady: Hetzner CPX31/CX32, OVH VPS, Contabo, Scaleway — čokoľvek s verejnou IPv4 bez NAT obmedzení na UDP.

## 2. DNS záznamy (u registrátora domény macet.eu)

Všetky ako **A** záznam na IP servera (TTL napr. 300). **AAAA (IPv6) nepridávajte** — stack beží len na IPv4;
existujúci AAAA záznam pre tieto mená by rozbil Let's Encrypt aj klientov.

| Názov | Typ | Hodnota | Na čo |
|---|---|---|---|
| `chat.macet.eu` | A | `<IP>` | Matrix homeserver (Synapse), prihlásenie/registrácia (MAS na `/auth/`), LiveKit signalizácia, iOS push |
| `app.macet.eu` | A | `<IP>` | PSST web, Podmienky, Ochrana súkromia, App Links |
| `call.macet.eu` | A | `<IP>` | Element Call + TURN/TLS na 443 (pre siete bez UDP) |
| `push.macet.eu` | A | `<IP>` | (bývalý ntfy) len presmerovanie na web |
| `macet.eu` | CAA | `0 issue "letsencrypt.org"` | (voliteľné) len Let's Encrypt smie vydať certifikát |

Kontrola: `dig +short chat.macet.eu` (a ďalšie) musí vrátiť `<IP>` — deploy.sh to overí sám a bez toho nepokračuje.

## 3. Cloud firewall poskytovateľa (ak ho má) — prichádzajúce

| Port | Protokol | Účel |
|---|---|---|
| 22 | TCP | SSH (ideálne len z vašej IP) |
| 80 | TCP | Let's Encrypt overenie, presmerovanie na HTTPS |
| 443 | TCP | HTTPS (všetky domény) + TURN cez TLS |
| 7881 | TCP | hovory — ICE/TCP |
| 7882 | UDP | hovory — médiá |

Odchádzajúce: všetko povolené (Let's Encrypt, sťahovanie image, APNs). Na serveri samotnom nastaví
rovnaké pravidlá UFW `deploy.sh`.

## 4. Čo dodáte vy

| Čo | Kedy | Ako |
|---|---|---|
| **IP adresa servera** | vždy | 1. argument `deploy.sh` |
| **e-mail pre Let's Encrypt** | vždy | 2. argument (upozornenia na expiráciu certifikátu) |
| **kontakt prevádzkovateľa** | odporúčané | `--contact "vas@email.sk"` → Podmienky / Ochrana súkromia |
| **kde je server** | odporúčané | `--hosting "Hetzner Online GmbH, Nemecko (EÚ)"` |
| **Apple Team ID + APNs kľúč** | keď bude iOS appka | `AuthKey_<KEY_ID>.p8` → `server/secrets/apns/`, potom `--apple-team-id <TEAM_ID>` |

## 5. Nasadenie (≈ 10 minút)

```sh
ssh root@<IP>
apt-get update && apt-get install -y git
git clone https://github.com/georgonr/psst /opt/psst
cd /opt/psst/server
./deploy.sh <IP> <email> --contact "vas@email.sk" --hosting "Poskytovateľ, Krajina (EÚ)"
```

`deploy.sh` vypíše výsledok pre-flight kontroly (DNS, porty, disk, RAM), a ak je všetko OK, spraví zvyšok.
**Po hardeningu sa root už neprihlási** — prihlasujte sa ako `psst` (rovnaký SSH kľúč, `sudo` bez hesla):

```sh
ssh psst@<IP>
cd /opt/psst/server
sudo scripts/members.sh admin juro            # váš admin účet (vypíše heslo)
sudo scripts/members.sh invite 5 7            # pozvánka pre 5 ľudí, platná 7 dní
sudo cat secrets/backup.pass                  # ULOŽTE SI mimo servera (bez neho sa záloha neobnoví)
sudo scripts/healthcheck.sh                   # všetko OK?
```

## 6. Po nasadení

- [ ] `https://app.macet.eu` sa načíta, „Create account" s pozvánkou funguje, prihlásenie funguje
- [ ] Android: nainštalovať `psst-26.11.0-arm64-v8a.apk` — notifikácie fungujú hneď (Google FCM cez náš Sygnal),
      žiadna ďalšia appka; kľúč Firebase service accountu musí byť v `secrets/fcm/service-account.json`
- [ ] iOS: TestFlight cez `ios-release.yml` (vyžaduje Apple Developer účet a secrets)
- [ ] skúšobný hovor 1:1 aj skupinový
- [ ] heslo k zálohám uložené mimo servera; voliteľne kópia záloh mimo servera:
      `BACKUP_RSYNC_TARGET=user@host:/zalohy` do `server/.env`

## Aktualizácia a údržba

```sh
cd /opt/psst && git pull && cd server && sudo ./deploy.sh <IP> <email>   # idempotentné
sudo scripts/fetch-web.sh                                                # nový PSST web (posledný release)
sudo scripts/members.sh list | block <meno> | unblock <meno>
sudo scripts/restore.sh backups/daily/psst-<čas>.tar.gz.enc --force      # obnova
```
