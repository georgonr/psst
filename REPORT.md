# PSST — report (2026-11-13/14, štvrtá dávka: produkcia na PSST serveri)

Predchádzajúce reporty sú v git histórii. Detaily servera: `~/proj/psst-server-notes.md`.
Rozhodnutia tejto dávky: DECISIONS D42–D46.

## Verdikt

**Áno — ráno sa môžete pripojiť.** Celý stack beží naostro na `chat.macet.eu` (Hetzner CX33, Helsinki)
s platnými Let's Encrypt certifikátmi. Všetko z bodu 7 je overené na produkcii: web s brandingom
a prihlásenie admina, registrácia pozvánkovým tokenom (web aj Android), šifrované správy, skupina, kanál,
súbor, Android notifikácia cez push.macet.eu, macOS desktop, hovory 1:1 aj skupinové, aj len cez TURN/TLS
na 443. Federácia a verejná registrácia sú zvonka zamietnuté, TLS má A+/A. Testovacie účty sú
deaktivované, admin `geo` a jeden pozvánkový token pre člena zostali.

## Stav po bodoch

| # | Bod | Stav |
|---|---|---|
| 0 | Druhá session | ✅ Čakal som, kým nebola hotová (DEPLOY-CHECKLIST.md, `~/psst` preč, posledný commit 20:35, kontrola o 20:54). Body 1–2 som robil počas čakania. |
| 1 | Spevnenie servera | ✅ swap 4 GB (swappiness 10), sysctl (rp_filter, redirecty, syncookies, kptr/dmesg_restrict, fs.protected_*), odstránené snapd/apport/lxd/multipath/iscsi/open-vm-tools/pollinate (+ atd, motd-news, cloud-init hotplug), AIDE (denne), ClamAV (týždenne), auditd (20 pravidiel), systémový healthcheck (denne) + healthcheck stacku (každých 10 min), logrotate, žiadne externé notifikácie. **Docker neobchádza UFW**: `daemon.json` (`ip 127.0.0.1`, no-new-privileges, live-restore, logy 20m×5) + reťazec `DOCKER-USER`. |
| 2 | DNS | ✅ chat/app/call/push.macet.eu → 204.168.160.131 cez 1.1.1.1 aj 8.8.8.8 (už o 18:28). |
| 3 | Push doména | ✅ Druhá session použila `ntfy.macet.eu` → **všade zmenené na `push.macet.eu`** (server stack, Android fork `73d2171d`, dokumentácia). Repo potrebovalo aj `auth.` a `turn.macet.eu`, ktoré v DNS nie sú → MAS na `chat.macet.eu/auth/`, TURN/TLS na `call.macet.eu:443` podľa ALPN (D42). |
| 4 | Nasadenie | ✅ `deploy.sh` → Synapse, Postgres, MAS, LiveKit + lk-jwt, Element Call, Element Web, ntfy, coturn, nginx, Let's Encrypt (4 domény, ECDSA), zálohy (cron 03:17), healthcheck. Sygnal sa spustí až s APNs kľúčom. Federácia vypnutá, registrácia len tokenom. Tajomstvá vygenerované na serveri. **Šifrovaná záloha a obnova otestované naostro** (zhodný podpisový kľúč aj účty, healthcheck OK). |
| 5 | Účty | ✅ admin `geo` (jediný MAS admin) + 1 pozvánkový token (1 použitie, platný do 13. 12. 2026) → `~/proj/psst-admin.txt` (600). |
| 6 | Appky | ✅ Push doména sa zmenila → **Android prebuildovaný** (arm64, armv7, x86_64 + AAB, podpísané, v dexe overené `push.macet.eu`). Web/desktop/Windows netreba: homeserver je rovnaký a MAS sa zisťuje dynamicky → existujúce buildy ponechané. |
| 7 | Overenie naostro | ✅ všetko — viď tabuľku nižšie. |
| 8 | Záver | ✅ commit + push repa a Android forku, aktualizované `psst-server-notes.md`, tento report. |

## Výsledky testov (produkcia, skutočné DNS a certifikáty)

| Test | Výsledok |
|---|---|
| `tests/server/prod_test.py`: TLS, federácia (3 endpointy 404 + port 8448 zavretý), admin API zvonka 404, Synapse `/register` 403, hosť 403, MAS issuer, MAS registrácia vyžaduje token, zlé heslo 403, 2× login, **E2EE DM** (na serveri len `m.room.encrypted`), **skupina**, **verejný kanál** (adresár bez prihlásenia 401, pripojenie cez alias), **šifrovaný súbor** (na serveri len blob, SHA-256 zhoda) | **24/24** |
| Web: app.macet.eu — titulok psst, PSST logo, prihlásenie **admina geo** cez MAS (`@geo:chat.macet.eu`) | **4/4** |
| Web: registrácia tokenom (platný jednorazový ✓, znova ✗, neplatný ✗, viacnásobný ✓) | **4/4** |
| Web: login cez MAS, zamknutý homeserver, prijatá E2EE správa z iného klienta, žiadne požiadavky mimo *.macet.eu | **7/7** |
| **Android APK v emulátore**: prihlásenie na chat.macet.eu (MAS v Custom Tab), pusher `https://push.macet.eu/_matrix/push/v1/notify`, notifikácia pozvánky, **notifikácia so šifrovanou správou (dešifrovaný text)**, správa v miestnosti | ✅ |
| **Android registrácia** tokenom: Create account → formulár → token → meno → súhlas → späť v appke | ✅ |
| **macOS desktop** (psst.app z dist): štart, chat.macet.eu, Pokračovať → MAS, prihlásenie + súhlas → callback → prihlásený `@qa-hana` | **6/6** |
| **Hovor 1:1** (DM, Element Call cez LiveKit) | **5/5** (médiá UDP) |
| **Skupinový hovor** (miestnosť s 3 členmi) | **5/5** |
| **Hovor len cez TURN/TLS na 443** (relay-only) — 2× (pred aj po sprísnení šifier) | **6/6**, `relayProtocol=tls`, coturn potvrdil spojenia z nginx |
| Federácia zvonka / verejná registrácia | zamietnuté (viď prod_test) |
| SSL Labs (`publish=off`, pred aj po sprísnení šifier) | chat **A+**, app **A+**, push **A+**, call **A** (bez varovaní) |
| testssl.sh 3.2 | chat.macet.eu **A+** (96) pred sprísnením šifier; po sprísnení CBC odmietnuté (LUCKY13 varovanie zmizne) |
| Sken portov IPv4 — všetkých 65 535 TCP (TCP connect z Macu + nmap 7.98) | otvorené **len 22, 80, 443, 7881**; 8448 a ostatné filtrované. UDP: 3478, 5349, 53, 123, 19302, 49160+ neodpovedajú; 7882/udp prenáša médiá hovorov (`prflx/udp`) |
| Sken portov IPv6 (TCP connect, všetkých 65 535 portov z Macu) | otvorený **len 22** |
| Záloha → obnova `--force` na produkcii | ✅ podpisový kľúč (SHA-256) zhodný, účty aj tokeny zhodné, healthcheck 0 varovaní |
| `scripts/healthcheck.sh` | OK, 0 varovaní |

Testovacie účty (qa-*, reg*) sú **deaktivované** a testovacie tokeny zrušené. Pri testoch som dočasne uvoľnil
rate-limit prihlásení v MAS (testy idú z jednej IP), potom vrátil. Produkčný limit funguje (429 / „too many
requests" som videl naživo).

## Chyby nájdené a opravené pri nasadení

| # | Chyba | Oprava |
|---|---|---|
| 1 | `deploy.sh`: certbot `certonly` sa nikdy nespustil (služba má entrypoint s renew slučkou → visel 12 h) | `--entrypoint certbot` |
| 2 | `backup.sh`: každá záloha na Linuxe skončila „overenie zlyhalo" (`tar | grep -q` + pipefail → SIGPIPE) | zoznam najprv do premennej |
| 3 | `deploy.sh`: zmena konfigurácie sa neprejavila (render cez `mv` → bind mount jedného súboru drží starý inode) | zápis na mieste + reštart služieb so zmenenou konfiguráciou (overené) |
| 4 | pre-flight hlásil obsadené porty (s `userland-proxy: false` ich drží `dockerd`, nie `docker-proxy`) | akceptuje dockerd/coturn |
| 5 | Repo očakávalo 6 subdomén (auth/ntfy/turn) — DNS má 4 | MAS na `/auth/`, ntfy → push, TURN podľa ALPN na call (D42) |
| 6 | Docker by verejne publikoval aj omylom pridané porty (obchádza UFW) | `daemon.json ip=127.0.0.1` + `DOCKER-USER` + explicitné `0.0.0.0:` len pre 4 porty |
| 7 | UFW by zablokoval nginx → coturn (host sieť) | interné pravidlo 172.30.0.0/24 → 172.30.0.1:3478/tcp |
| 8 | TLS 1.2 ponúkal CBC/CAMELLIA/ARIA (nginx default) | Mozilla intermediate (ECDHE + AEAD) pre HTTPS aj TURN/TLS |
| 9 | Testy predpokladali `auth.macet.eu` a lokálny stack; nio bez CA bundle (macOS Python) | `MAS_URL_RE`, `PSST_HOST_IP`, `PSST_PROD=1`, certifi; nové `prod_test.py`, `admin-login-test.mjs`, `desktop/prod-login-test.mjs` |

## Appky na stiahnutie (`~/proj/psst/dist/`)

| Platforma | Súbor | SHA-256 |
|---|---|---|
| **Android** (väčšina telefónov) | `dist/android/psst-26.11.0-arm64-v8a.apk` | `0c9bfb4c45e9f5cf36933b50188801dbc94fd628f3eecefe7226f4a61ae8b605` |
| Android (staré 32-bit) | `dist/android/psst-26.11.0-armeabi-v7a.apk` | `141382659c6ddd2fe7afba4935f73490aecab49cdce80fd2a0ee872b2bfbdb0e` |
| **Windows** | `dist/desktop/psst-1.12.35-windows.msi` (alebo `…-windows-setup.exe`) | `fef410a647ac25f1cfa6208bbcb3638ed483b82dfe34fbe2fb586d2c6632cc4b` |
| **macOS** (Intel + Apple Silicon) | `dist/desktop/psst-1.12.35-universal.dmg` | `ee143d552a653b3567945cb31ec23a419183c76c80d8519d7c47a341e85ef33f` |

Ďalšie: `psst-26.11.0-x86_64.apk` (emulátor), `psst-26.11.0.aab` (Play), `psst-1.12.35-universal-mac.zip`,
`psst-web.tar.gz`; všetko v `dist/SHA256SUMS.txt`. Android podpis `3a6428cf…7d3899`. Desktop nie je podpísaný
Apple/Windows certifikátom → macOS: pravý klik → Otvoriť; Windows: SmartScreen „Viac informácií → Spustiť".

**Android notifikácie:** nainštalovať aj appku **ntfy** (F-Droid/GitHub), v nej *Settings → Default server*
= `https://push.macet.eu`, vypnúť optimalizáciu batérie pre ntfy.

## Prihlasovacie údaje

`~/proj/psst-admin.txt` (chmod 600, mimo repa): admin **geo** + heslo, pozvánkový token pre ďalšieho člena.
Heslo k zálohám je len na serveri: `ssh psst sudo cat /opt/psst/server/secrets/backup.pass`.

## Čo ostáva otvorené

- **Zálohy sú len na tom istom serveri** — nastaviť kópiu mimo (`BACKUP_RSYNC_TARGET`) a uložiť heslovú frázu mimo servera.
- iOS: Apple Developer účet (podpis, TestFlight, APNs → Sygnal). Podpis desktopu (Developer ID, Windows cert).
- Voliteľne DNS: CAA `0 issue "letsencrypt.org"`; samostatné `auth.`/`turn.macet.eu` nie sú potrebné.
- call.macet.eu má v SSL Labs A (nie A+): klient bez ALPN dostane TURN/TLS listener (bez HSTS hlavičky) — dôsledok D42.
- Pri teste desktopu sa na Macu mohli v predvolenom prehliadači otvoriť karty s prihlásením MAS (appka volá
  `shell.openExternal`) — môžete ich zavrieť.
- Emulátor `psst33`: zo `/system/etc/hosts` som odstránil staré mapovanie *.macet.eu → 10.0.2.2 (lokálny stack);
  pre lokálne testy ho treba vrátiť.
