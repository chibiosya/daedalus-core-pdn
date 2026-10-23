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
# ko_bga_top must fire exactly once, on the 0402 footprint CTEST1: the two planted vias inside
# KO_BGA_TOP (in CTEST1's pad, between balls A1/A2) must not be reported by it, vias are allowed
# under the BGA.  (Report text is localised; match rule names and coordinates only.)
n_bga=$(grep -c '^    Rule: ko_bga_top;' "$WORK/negtest/drc.rpt" || true)
[ "$n_bga" = 1 ] || { echo "negative test FAILED: ko_bga_top fired $n_bga times, expected once (footprint only)"; exit 1; }
grep -A1 '^    Rule: ko_bga_top;' "$WORK/negtest/drc.rpt" | grep -q 'CTEST1' || { echo "negative test FAILED: ko_bga_top did not flag the footprint CTEST1"; exit 1; }
# the via centred between balls A1 and A2 (94.8, 74.4) must fail on clearance to the ball pads
grep -A3 '^\[clearance\]' "$WORK/negtest/drc.rpt" | grep -q '@(94.8000 mm, 74.4000 mm)' || { echo "negative test FAILED: via between balls not reported as a clearance violation"; exit 1; }
echo "negative test passed (all keepout rules fire; ko_bga_top flags the footprint, not vias; via between balls fails clearance)"
echo "== 6. positive test: a via at an outer-ring interstitial position inside KO_BGA_TOP must pass"
mkdir -p "$WORK/postest"
python3 tools/generate_board.py --out "$WORK/postest" --positive-test >/dev/null
"$KIPY" tools/finalize_board.py "$WORK/postest/$BOARD" >/dev/null
"$KICAD_CLI" pcb drc --severity-error --exit-code-violations -o "$WORK/postest/drc.rpt" "$WORK/postest/$BOARD" >/dev/null \
  || { echo "positive test FAILED: interstitial via at (94.8, 74.8) was reported"; grep -E '^\[|@\(' "$WORK/postest/drc.rpt"; exit 1; }
echo "positive test passed (interstitial via under the BGA is accepted)"
echo "== 7. structural verification"
python3 tools/verify_board.py "$BOARD" supplied_items.json | tail -1
echo "== 8. SVG renders"
mkdir -p images
for L in F.Cu B.Cu In1.Cu In2.Cu; do
  "$KICAD_CLI" pcb export svg --layers "$L,Edge.Cuts" --page-size-mode 2 --exclude-drawing-sheet -o "images/$L.svg" "$BOARD" >/dev/null
done
echo "done. reports in $WORK"
