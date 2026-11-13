#!/usr/bin/env bash
# Generate every PSST icon from the master geometry (assets/psst-logo.svg).
# Each raster is drawn at its final size (SDF rasteriser), never resampled.
# Requirements: python3 (stdlib only). On macOS, iconutil packs the .icns.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/assets/generated}"
python3 "$ROOT/scripts/icons/psst_icons.py" "$OUT"
cp "$OUT/svg/psst-wordmark.svg" "$ROOT/assets/psst-wordmark.svg"
cp "$OUT/svg/psst-wordmark-on-dark.svg" "$ROOT/assets/psst-wordmark-on-dark.svg"
