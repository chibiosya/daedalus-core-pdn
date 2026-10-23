# daedalus-core-pdn

Supplied KiCad 8 board asset for the Daedalus core power-delivery-network (PDN) exercise: a
60 x 40 mm, 4-layer board carrying a 225-ball SoC (U1) with its core-supply fanout, a VRM output
(U2), a GND plane, a VDD_CORE plane, four mounting holes and a set of named keepout areas. It is
meant to be designed *onto*: you add decoupling capacitors, their vias and tracks; everything that
is already here is a **supplied item** and must not be moved or changed.

| File | Purpose |
|---|---|
| `daedalus_core_pdn.kicad_pcb` | The board (KiCad 8 format, version 20240108, all footprints embedded, zones filled) |
| `daedalus_core_pdn.kicad_pro` | Project: numeric design-rule constraints and the `Default` net class |
| `daedalus_core_pdn.kicad_dru` | Custom rules: no via-in-pad, the keepout rules, the mounting-hole copper keepout |
| `supplied_items.json` | UUID + geometry of every supplied item (footprints, tracks, vias, zones, rule areas, edge cuts, groups) and the U1 ball map |
| `tools/` | Reproducible generator / zone filler / verifier / build script |
| `images/` | SVG renders of F.Cu, B.Cu, In1.Cu and In2.Cu |

**Keep the three `daedalus_core_pdn.*` files together.** `kicad-cli pcb drc` loads the `.kicad_pro`
and `.kicad_dru` that sit next to the board; without them KiCad falls back to its defaults
(0.2 mm net-class clearance) and the supplied BGA fanout no longer passes DRC.

## Validation status (KiCad 8.0.9, `kicad-cli`)

```
kicad-cli pcb drc --severity-error   --exit-code-violations daedalus_core_pdn.kicad_pcb   -> exit 0, 0 violations, 0 unconnected
kicad-cli pcb drc --severity-warning --exit-code-violations daedalus_core_pdn.kicad_pcb   -> exit 0, 0 violations (no warnings remain)
```

The keepout rules were proven to fire with a negative-test board (`tools/generate_board.py
--negative-test`): a C_0402 capacitor placed inside KO_BGA_TOP, a via inside KO_VRM, a track inside
KO_DDR_CHANNEL on B.Cu, a via inside KO_MH1 and a via inside a non-U2 SMD pad are each reported as
an error by the corresponding rule (`ko_bga_top`, `ko_vrm`, `ko_ddr_channel`, `ko_mh1` +
`mounting_hole_copper_keepout`, `no_via_in_pad`). `tools/build.sh` re-runs that test every build.

## Board

* Outline: rectangle 60 x 40 mm on Edge.Cuts, corners (70,60) (130,60) (130,100) (70,100). All
  coordinates in this document are KiCad board coordinates in mm (x to the right, y downwards).
* Finished thickness 1.54 mm, 4 copper layers. Stackup is stored in the board file
  (Board Setup > Physical Stackup):

| # | Layer | Type | Thickness | Note |
|---|---|---|---|---|
| 1 | F.Cu | copper | 0.035 mm | signal, components |
| | dielectric 1 | prepreg FR4 | 0.200 mm | |
| 2 | In1.Cu | copper | 0.035 mm | GND plane |
| | dielectric 2 | core FR4 | 1.000 mm | |
| 3 | In2.Cu | copper | 0.035 mm | VDD_CORE plane |
| | dielectric 3 | prepreg FR4 | 0.200 mm | |
| 4 | B.Cu | copper | 0.035 mm | signal |

Solder-mask layers are entered with 0 thickness so the stackup total shown by KiCad equals the
specified 1.54 mm.

* Nets: `GND` (net 1) and `VDD_CORE` (net 2). There are no other nets; 176 of the U1 balls are
  intentionally unconnected.
* Planes: In1.Cu is a filled GND zone, In2.Cu a filled VDD_CORE zone. Both cover the board with a
  1.0 mm clearance to the edge (outline (71,61)-(129,99)), zone clearance 0.1 mm, minimum width
  0.2 mm, solid (no thermal relief) connections. The fills are stored in the file.
* Mounting holes H1..H4: non-plated 3.2 mm drill at (73,63), (127,63), (73,97), (127,97). Copper is
  kept 3.5 mm (radius) away from each hole centre on every layer, see `mounting_hole_copper_keepout`
  below and the KO_MH rule areas.

## U1: SoC BGA (supplied, do not change)

* Footprint `BGA-225_15x15_0.8mm`, reference U1, centre (100.000, 80.000), rotation 0, body
  12 x 12 mm, courtyard (F.CrtYd) 13 x 13 mm centred on U1.
* 15 x 15 balls on a 0.8 mm pitch. Pad: SMD circle 0.400 mm, NSMD (solder-mask margin +0.05 mm).
  Rows A B C D E F G H J K L M N P R (JEDEC, I/O/Q skipped), columns 1..15. Ball A1 is top-left in
  the KiCad view at (94.4, 74.4); ball R15 is bottom-right at (105.6, 85.6). Ball (row r, col c)
  is at x = 94.4 + 0.8 (c-1), y = 74.4 + 0.8 (index of r).
* Core region: the central 7 x 7 balls, rows E..L (E F G H J K L) x columns 5..11, checkerboard:
  `VDD_CORE` where (i + j) is even (25 balls), `GND` where odd (24 balls), i,j = 0..6 inside the
  block. Every other ball has no net.

Ball map (V = VDD_CORE, G = GND, . = no net):

| row \ col | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **A** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . |
| **B** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . |
| **C** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . |
| **D** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . |
| **E** | . | . | . | . | V | G | V | G | V | G | V | . | . | . | . |
| **F** | . | . | . | . | G | V | G | V | G | V | G | . | . | . | . |
| **G** | . | . | . | . | V | G | V | G | V | G | V | . | . | . | . |
| **H** | . | . | . | . | G | V | G | V | G | V | G | . | . | . | . |
| **J** | . | . | . | . | V | G | V | G | V | G | V | . | . | . | . |
| **K** | . | . | . | . | G | V | G | V | G | V | G | . | . | . | . |
| **L** | . | . | . | . | V | G | V | G | V | G | V | . | . | . | . |
| **M** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . |
| **N** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . |
| **P** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . |
| **R** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . |

* Dog-bone fanout, one per core ball (49): F.Cu track, width 0.15 mm, from the ball centre to a via
  at (+0.400, +0.400) mm from the ball centre (towards +x, +y, i.e. down-right in the view).
  Via: through-hole, drill 0.200 mm, diameter 0.450 mm, same net as the ball. The vias sit on the
  interstitial positions of the ball grid, at x = 94.8 + 0.8 (c-1), y = 74.8 + 0.8 (row index),
  for c = 5..11 and row index 4..10. All 49 tracks and 49 vias are members of the group
  `U1_FANOUT`.

## U2: VRM output (supplied, do not change)

* Footprint `VRM_OUT`, reference U2, centre (75.000, 80.000), courtyard 6 x 8 mm centred on U2.
* Pad 1, net `VDD_CORE`: SMD rectangle 4.0 x 3.0 mm on F.Cu centred at (75.0, 78.0).
* Pad 2, net `GND`: SMD rectangle 4.0 x 3.0 mm on F.Cu centred at (75.0, 82.0).
* 4 through vias per pad, drill 0.3 mm, diameter 0.6 mm, same net as the pad, at
  x = 73.8 and 76.2, y = pad centre y -0.8 and +0.8, i.e. (73.8|76.2, 77.2|78.8) for pad 1 and
  (73.8|76.2, 81.2|82.8) for pad 2. These 8 vias are members of the group `U2_VIAS`.

## Via sizes

| Use | Diameter | Drill | Annular ring |
|---|---|---|---|
| U1 dog-bone vias (49) | 0.450 mm | 0.200 mm | 0.125 mm |
| U2 output vias (8) | 0.600 mm | 0.300 mm | 0.150 mm |
| `Default` net class via (for anything you add) | 0.450 mm | 0.200 mm | 0.125 mm |

## Keepouts (rule areas)

The keepouts are **named rule areas with no keepout flags of their own**; the enforcement lives in
`daedalus_core_pdn.kicad_dru` so that supplied items can be exempted while anything added later
is checked. Inside each area footprints, vias and tracks are forbidden on the listed layers.

| Name | Layers | Shape | Coordinates (mm) | Exempt supplied items |
|---|---|---|---|---|
| KO_BGA_TOP | F.Cu | 14 x 14 mm square | x 93..107, y 73..87 (centre 100,80) | U1, group U1_FANOUT |
| KO_DDR_CHANNEL | F.Cu, B.Cu | rectangle | x 108..130, y 64..96 | none |
| KO_CONNECTOR | F.Cu, B.Cu | rectangle | x 70..90, y 60..70 | H1 |
| KO_VRM | F.Cu, B.Cu | rectangle | x 70..81, y 74..86 | U2, group U2_VIAS |
| KO_MH1 | all copper | circle r 3.5 mm (72-gon) | centre (73,63) | H1 |
| KO_MH2 | all copper | circle r 3.5 mm (72-gon) | centre (127,63) | H2 |
| KO_MH3 | all copper | circle r 3.5 mm (72-gon) | centre (73,97) | H3 |
| KO_MH4 | all copper | circle r 3.5 mm (72-gon) | centre (127,97) | H4 |

Rule areas in KiCad are polygons, so each circle is a 72-sided polygon with its vertices on the
3.5 mm radius. A footprint counts as inside an area when its courtyard intersects the area
(KiCad semantics), so give your capacitors a courtyard.

## Design rules

Numeric constraints (`.kicad_pro`, Board Setup > Constraints):

| Constraint | Value |
|---|---|
| Minimum clearance | 0.100 mm |
| Minimum track width | 0.150 mm |
| Minimum via diameter | 0.450 mm |
| Minimum via drill (through hole) | 0.200 mm |
| Minimum annular ring | 0.125 mm |
| Hole-to-hole clearance | 0.250 mm |
| Copper-to-hole clearance | 0.250 mm (KiCad default) |
| Copper-to-edge clearance | 0.500 mm |
| Courtyard overlap | error |
| Silkscreen / solder-mask rules | KiCad defaults |

Net class `Default`: clearance 0.100 mm, track width 0.200 mm, via 0.450 / 0.200 mm. (The clearance
is set equal to the minimum clearance because KiCad's default of 0.2 mm would fail the specified
BGA fanout, whose via-to-neighbouring-ball gap is 0.141 mm.)

Custom rules (`.kicad_dru`, KiCad 8 syntax):

```
(rule no_via_in_pad
	(condition "A.Type == 'Via' && B.Type == 'Pad' && B.Pad_Type == 'SMD' && !B.memberOfFootprint('U2')")
	(constraint physical_clearance (min 0.1mm)))
```
No via may touch or come within 0.1 mm of any SMD pad, regardless of net. U2's pads are supplied
with vias inside them and are the only exemption.

```
(rule ko_bga_top
	(layer "F.Cu")
	(condition "A.intersectsArea('KO_BGA_TOP') && !A.memberOfFootprint('U1') && !(A.Type == 'Footprint' && A.Reference == 'U1') && !A.memberOfGroup('U1_FANOUT')")
	(constraint disallow footprint via track))
```
One such rule per keepout (`ko_bga_top`, `ko_ddr_channel`, `ko_connector`, `ko_vrm`, `ko_mh1..4`),
each restricted to the area's layers (`(layer outer)` for F.Cu + B.Cu, no layer clause for
all-copper) and exempting only the supplied items listed in the table above.

```
(rule mounting_hole_copper_keepout
	(condition "B.Pad_Type == 'NPTH, mechanical'")
	(constraint hole_clearance (min 1.9mm)))
```
Hole edge (radius 1.6 mm) + 1.9 mm = the 3.5 mm copper-free radius around each mounting hole. This
is honoured by the zone filler (the planes already have the cut-outs) and by DRC for any copper
you add.

Capacitor via proximity is checked by the grader, not by DRC.

## Capacitor footprints you may use

From the official KiCad library `Capacitor_SMD`: `C_0201_0603Metric`, `C_0402_1005Metric`,
`C_0603_1608Metric`, `C_0805_2012Metric`, `C_1210_3225Metric`. The `Value` field must be exactly
one of `0.1uF 0.22uF 0.47uF 1.0uF 2.2uF 4.7uF 10uF 22uF 47uF 100uF` (as allowed per package in the
brief).

## Supplied items

`supplied_items.json` lists every supplied object with its UUID and geometry: 6 footprints (U1, U2,
H1..H4), 49 tracks, 57 vias, 2 planes, 8 rule areas, the Edge.Cuts rectangle and the 2 groups, plus
the U1 ball map. UUIDs are deterministic (UUID v5 of the item name) so a regenerated board has the
same IDs. `python3 tools/verify_board.py daedalus_core_pdn.kicad_pcb supplied_items.json` checks
that all of them are still present and that the geometry matches this document.

## Rebuilding

```
KICAD_APP=/Applications/KiCad/KiCad.app tools/build.sh
```
`tools/generate_board.py` (stdlib Python, no KiCad needed) writes the three KiCad files and
`supplied_items.json` from the numbers above; `tools/finalize_board.py` (KiCad's bundled python,
`pcbnew`) fills the zones and re-saves in canonical KiCad 8 format; `tools/build.sh` then runs
DRC at error and warning severity, the negative keepout test, the verifier and the SVG exports.
Built and validated with KiCad 8.0.9 on macOS.

## Renders

| F.Cu | B.Cu |
|---|---|
| ![F.Cu](images/F.Cu.svg) | ![B.Cu](images/B.Cu.svg) |

| In1.Cu (GND plane) | In2.Cu (VDD_CORE plane) |
|---|---|
| ![In1.Cu](images/In1.Cu.svg) | ![In2.Cu](images/In2.Cu.svg) |

## Notes and assumptions

* The mounting-hole footprints have no courtyard on purpose: KiCad tests "footprint in area" with
  the courtyard, and the holes sit inside their own KO_MH areas and (H1) inside KO_CONNECTOR.
* Solder-mask thickness is 0 in the stackup so the total equals 1.54 mm; nothing else depends on it.
* Keepout rules use `intersectsArea` (any overlap is a violation), the same test KiCad uses for its
  own rule-area keepouts.
* Reference designators of H1..H4 are hidden; U1/U2 references are on F.SilkS outside their pads.

## Licence

CC0 1.0 Universal (public domain dedication), see `LICENSE`.
