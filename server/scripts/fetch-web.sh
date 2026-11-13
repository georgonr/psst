#!/usr/bin/env bash
# Stiahne PSST Element Web distribúciu do server/app/ (servíruje ju nginx na APP_DOMAIN).
#
#   scripts/fetch-web.sh                       najnovší release: github.com/georgonr/psst/releases/latest (curl)
#   PSST_WEB_DIST_URL=https://…/psst-web.tar.gz scripts/fetch-web.sh   z inej URL (.tar.gz / .tgz / .zip)
#   PSST_WEB_FROM_CI=1 [PSST_WEB_RUN_ID=123] scripts/fetch-web.sh      artefakt "psst-web-dist" z CI (gh CLI)
#
# Po stiahnutí netreba reštart — nginx servíruje súbory priamo z app/.
. "$(dirname "$0")/lib.sh"

REPO="${PSST_WEB_REPO:-georgonr/psst}"
ARTIFACT="${PSST_WEB_ARTIFACT:-psst-web-dist}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/dl" "$TMP/x"

if [ -z "${PSST_WEB_FROM_CI:-}" ]; then
  PSST_WEB_DIST_URL="${PSST_WEB_DIST_URL:-https://github.com/${REPO}/releases/latest/download/psst-web.tar.gz}"
fi
if [ -n "${PSST_WEB_DIST_URL:-}" ]; then
  require_cmd curl
  log "sťahujem $PSST_WEB_DIST_URL"
  curl -fsSL "$PSST_WEB_DIST_URL" -o "$TMP/dl/dist.${PSST_WEB_DIST_URL##*.}"
else
  require_cmd gh
  log "sťahujem artefakt $ARTIFACT z $REPO ${PSST_WEB_RUN_ID:+(beh $PSST_WEB_RUN_ID)}"
  gh run download ${PSST_WEB_RUN_ID:-} -R "$REPO" -n "$ARTIFACT" -D "$TMP/dl"
fi

# rozbaľ archívy (artefakt môže obsahovať priamo súbory alebo tarball/zip)
for f in "$TMP"/dl/*; do
  case "$f" in
    *.tar.gz|*.tgz) tar -xzf "$f" -C "$TMP/x" ;;
    *.tar) tar -xf "$f" -C "$TMP/x" ;;
    *.zip) require_cmd unzip; unzip -q "$f" -d "$TMP/x" ;;
    *) cp -R "$f" "$TMP/x/" ;;
  esac
done

INDEX="$(find "$TMP/x" -maxdepth 4 -name index.html -not -path '*/node_modules/*' | awk '{ print length, $0 }' | sort -n | head -1 | cut -d' ' -f2-)"
[ -n "$INDEX" ] || die "v artefakte nie je index.html"
SRC="$(dirname "$INDEX")"
log "distribúcia nájdená v ${SRC#$TMP/x}"

rm -rf app.new app.old
cp -R "$SRC" app.new
touch app.new/.gitkeep
chmod -R a+rX app.new
[ -d app ] && mv app app.old
mv app.new app
rm -rf app.old
log "PSST web nasadený do server/app/ ($(du -sh app | cut -f1))"
[ -f app/config.json ] && log "používa sa config.json z distribúcie" || log "distribúcia nemá config.json → nginx servíruje serverový default"
