# Server — build / nasadenie

Server sa nebuilduje — používajú sa výhradne oficiálne, pinnuté image. Konfigurácia je v `server/`.

## Image (pinnuté v `server/compose.yml`)

| služba | image |
|---|---|
| Synapse | `ghcr.io/element-hq/synapse:v1.165.0` |
| PostgreSQL | `docker.io/library/postgres:18.7-alpine` |
| LiveKit SFU | `docker.io/livekit/livekit-server:v1.13.11` |
| MatrixRTC autorizácia | `ghcr.io/element-hq/lk-jwt-service:0.10.0` |
| Element Call | `ghcr.io/element-hq/element-call:v0.28.2` |
| nginx | `docker.io/library/nginx:1.30.6-alpine` |
| certbot | `docker.io/certbot/certbot:v5.10.0` |

Overenie najnovších verzií (2026-11-13):

```sh
gh release list -R element-hq/synapse -L 3
gh release list -R livekit/livekit -L 3
gh release list -R element-hq/lk-jwt-service -L 3
gh release list -R element-hq/element-call -L 3
curl -s "https://hub.docker.com/v2/repositories/library/postgres/tags?page_size=50" | jq -r '.results[].name'
```

## Produkčné nasadenie (na serveri)

```sh
# predpoklady: Docker Engine + compose plugin, openssl, git; DNS A/AAAA chat./app./call.psst.pro → server
git clone https://github.com/georgonr/psst.git /opt/psst
cd /opt/psst/server
sudo ./deploy.sh <IP> none        # prvýkrát aj pri každej aktualizácii
scripts/create-admin.sh admin                        # prvý admin (raz)
gh auth login && scripts/fetch-web.sh                # PSST web z artefaktu psst-web-dist
scripts/new-invite.sh 1 7                            # pozývací token
```

Firewall: 80/tcp, 443/tcp, 7881/tcp, 7882/udp (+ 22/tcp SSH). Viac v `server/README.md`.

## Lokálne overenie (CI)

Workflow `ci/workflows/server-smoke.yml` — kópia určená pre `.github/workflows/`; aktivuje sa
`scripts/enable-ci.sh` po `gh auth refresh -h github.com -s workflow` (token `georgonr` nemá scope
`workflow`, preto GitHub odmieta push súborov do `.github/workflows/`). Beží na ubuntu-latest, `workflow_dispatch` + push do `main`
na `server/**`, `tests/server/**`):

```sh
gh workflow run server-smoke.yml -R georgonr/psst
gh run watch -R georgonr/psst $(gh run list -R georgonr/psst -w server-smoke -L 1 --json databaseId -q '.[0].databaseId')
gh run view -R georgonr/psst --log-failed <run-id>
gh run download -R georgonr/psst <run-id> -n server-smoke-logs     # logy všetkých kontajnerov + results.json
```

Kroky workflowu:

```sh
cd server
COMPOSE_FILE=compose.yml docker compose --env-file .env.example config --quiet   # validácia produkčného compose
echo "127.0.0.1 chat.psst.pro app.psst.pro call.psst.pro" | sudo tee -a /etc/hosts
export COMPOSE_FILE=compose.yml:compose.test.yml LIVEKIT_USE_EXTERNAL_IP=false
./deploy.sh --no-letsencrypt
docker compose exec -T nginx nginx -t
pip install "matrix-nio[e2e]==0.26.0" "requests>=2.32"
python ../tests/server/smoke_test.py          # PASS/FAIL tabuľka, exit 1 pri chybe
./scripts/backup.sh /tmp/psst-backups         # záloha obsahuje db.dump + signing.key
docker compose down -v
```

Jednotlivé kontroly: `SMOKE_ONLY=1.1,2.3 python tests/server/smoke_test.py`.

## Statická validácia bez Dockeru (Mac) — vykonaná 2026-11-13

```sh
# syntax skriptov a YAML/JSON
bash -n server/deploy.sh server/scripts/*.sh
python3 -m py_compile tests/server/smoke_test.py
# compose.yml a compose.test.yml proti oficiálnej compose-spec JSON schéme (s premennými z .env.example)
python3 -m venv /tmp/v && /tmp/v/bin/pip install jsonschema pyyaml
curl -sfLO https://raw.githubusercontent.com/compose-spec/compose-go/main/schema/compose-spec.json
# (interpolácia ${VAR} z .env.example, potom jsonschema.validate) → oba súbory OK
```

Synapse (`pip install matrix-synapse` na Intel Macu kompiluje Rust, >1 GB) ani `nginx -t` (brew build zo
zdrojov) sa lokálne kvôli miestu na disku nespúšťali — overí ich CI krok „Validate rendered nginx config“
a štart Synapse.
