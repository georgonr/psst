# PSST (DECISIONS D91): official MAS 1.29.0 + one patched binary — the CAPTCHA hostname check accepts the parent domain
# hCaptcha returns ("psst.pro" for "chat.psst.pro", upstream issue #3549; MAS 1.29 compared strictly, so every
# registration failed) and logs why a CAPTCHA was rejected. Patch: mas/psst-captcha-hostname.patch; binary built by
# .github/workflows/mas-build.yml from the upstream Dockerfile, fetched by scripts/fetch-mas.sh, SHA-256 pinned in
# mas/mas-cli.sha256 and checked here. Templates, translations, assets and policy stay those of the official image.
ARG MAS_VERSION=1.29.0
FROM docker.io/library/debian:trixie-slim AS verify
COPY mas-cli mas-cli.sha256 /psst/
RUN cd /psst && grep -v '^#' mas-cli.sha256 | sha256sum -c - && chmod 0755 mas-cli
FROM ghcr.io/element-hq/matrix-authentication-service:${MAS_VERSION}
COPY --from=verify /psst/mas-cli /usr/local/bin/mas-cli
