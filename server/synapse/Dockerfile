# PSST (DECISIONS D66): official Synapse + one change — QR sign-in sessions (MSC4108 rendezvous) live 5 minutes
# instead of the hard-coded 60 seconds counted from the moment the QR code appears. The whole flow (scan, 2 digits,
# MAS verification code, "Grant access") must finish inside that window; at 60 s real users regularly ran out of time
# ("The sign in was not completed in time"). MSC4388 already uses ≥ 120 s. The build fails if the patched line is not
# found (e.g. after a Synapse update) — then check upstream before bumping the version.
ARG SYNAPSE_VERSION=v1.165.0
FROM ghcr.io/element-hq/synapse:${SYNAPSE_VERSION}
RUN set -e; f="$(python -c 'import synapse.server as s; print(s.__file__)')"; \
    grep -q "return RendezvousHandler(self)$" "$f"; \
    sed -i 's/return RendezvousHandler(self)$/return RendezvousHandler(self, ttl=5 * 60 * 1000)/' "$f"; \
    grep -q "RendezvousHandler(self, ttl=5 \* 60 \* 1000)" "$f"; \
    python -m compileall -q "$f"
