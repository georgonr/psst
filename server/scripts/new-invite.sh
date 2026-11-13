#!/usr/bin/env bash
# Zachované kvôli kompatibilite — použite scripts/members.sh invite [počet] [dni]
exec "$(dirname "$0")/members.sh" invite "$@"
