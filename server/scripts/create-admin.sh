#!/usr/bin/env bash
# Zachované kvôli kompatibilite — použite scripts/members.sh admin <meno>
exec "$(dirname "$0")/members.sh" admin "${1:-admin-$(date +%s)}"
