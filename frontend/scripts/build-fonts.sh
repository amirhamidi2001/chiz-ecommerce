#!/usr/bin/env bash
# Rebuilds frontend/public/fonts/*.woff2 (Task 14.3.2.1) from the Fontsource build of Vazirmatn,
# keeping only the weight range the UI uses (font-medium 500, font-semibold 600, font-bold 700
# and normal 400), which cuts each file by ~27%.
#
#   Source : @fontsource-variable/vazirmatn  (OFL-1.1, Vazirmatn by Saber Rastikerdar, which
#            declares no Reserved Font Name, so a narrowed copy is allowed as long as OFL.txt ships)
#   Needs  : node/npm, python3, `pip install fonttools brotli`
#   Run    : bash scripts/build-fonts.sh        (from frontend/)
#
# If the design ever needs another weight (font-light, font-extrabold, ...), change WGHT here,
# the `font-weight` range in src/index.css, and src/__tests__/fonts.test.js together.
set -euo pipefail
WGHT="${WGHT:-400:700}"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
OUT="public/fonts"; mkdir -p "$OUT"
( cd "$WORK" && npm init -y >/dev/null && npm i @fontsource-variable/vazirmatn >/dev/null )
SRC="$WORK/node_modules/@fontsource-variable/vazirmatn"
for subset in arabic latin latin-ext; do
  fonttools varLib.instancer "$SRC/files/vazirmatn-$subset-wght-normal.woff2" "wght=$WGHT" \
    -o "$OUT/vazirmatn-$subset-wght.woff2"
done
cp "$SRC/LICENSE" "$OUT/OFL.txt"
ls -l "$OUT"
