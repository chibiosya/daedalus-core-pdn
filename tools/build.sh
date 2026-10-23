#!/usr/bin/env bash
# Rebuild, validate and render daedalus_core_pdn from scratch.
#
#   KICAD_APP=/path/to/KiCad.app tools/build.sh
#
# KICAD_APP defaults to /Applications/KiCad/KiCad.app (KiCad 8.0.x).  Needs: any python3
# for the generator/verifier, KiCad's bundled python (pcbnew) for zone filling, kicad-cli
# for DRC and SVG export.
set -euo pipefail
cd "$(dirname "$0")/.."
KICAD_APP="${KICAD_APP:-/Applications/KiCad/KiCad.app}"
KICAD_CLI="$KICAD_APP/Contents/MacOS/kicad-cli"
KIPY="$KICAD_APP/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"
BOARD=daedalus_core_pdn.kicad_pcb
WORK="${WORK:-$(mktemp -d)}"
mkdir -p "$WORK"

echo "== kicad-cli $("$KICAD_CLI" version)"
echo "== 1. generate (S-expression, zones unfilled)"
python3 tools/generate_board.py
echo "== 2. fill zones with pcbnew and re-save in canonical KiCad 8 format"
"$KIPY" tools/finalize_board.py "$BOARD"
echo "== 3. DRC, error severity (must be 0)"
"$KICAD_CLI" pcb drc --severity-error --exit-code-violations -o "$WORK/drc_error.rpt" "$BOARD"
echo "== 4. DRC, warning severity (informational)"
"$KICAD_CLI" pcb drc --severity-warning -o "$WORK/drc_warning.rpt" "$BOARD" || true
grep -E 'Found|^\[' "$WORK/drc_warning.rpt" || true
echo "== 5. negative test: planted illegal items must be flagged by the .kicad_dru rules"
mkdir -p "$WORK/negtest"
python3 tools/generate_board.py --out "$WORK/negtest" --negative-test >/dev/null
"$KIPY" tools/finalize_board.py "$WORK/negtest/$BOARD" >/dev/null
if "$KICAD_CLI" pcb drc --severity-error --exit-code-violations -o "$WORK/negtest/drc.rpt" "$WORK/negtest/$BOARD" >/dev/null 2>&1; then
  echo "negative test FAILED: planted violations were not reported"; exit 1
fi
for rule in ko_bga_top ko_vrm ko_ddr_channel ko_mh1 no_via_in_pad mounting_hole_copper_keepout; do
  grep -q "$rule" "$WORK/negtest/drc.rpt" || { echo "negative test FAILED: rule $rule did not fire"; exit 1; }
done
echo "negative test passed (all keepout rules fire)"
echo "== 6. structural verification"
python3 tools/verify_board.py "$BOARD" supplied_items.json | tail -1
echo "== 7. SVG renders"
mkdir -p images
for L in F.Cu B.Cu In1.Cu In2.Cu; do
  "$KICAD_CLI" pcb export svg --layers "$L,Edge.Cuts" --page-size-mode 2 --exclude-drawing-sheet -o "images/$L.svg" "$BOARD" >/dev/null
done
echo "done. reports in $WORK"
