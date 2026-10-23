#!/usr/bin/env python3
"""Generate daedalus_core_pdn.kicad_pcb / .kicad_pro / .kicad_dru / supplied_items.json
from the numbers in BOARD_ASSET_SPEC.md.  Stdlib only; writes KiCad 8 S-expressions
directly.  Zones are written UNFILLED; tools/finalize_board.py (KiCad's bundled
python + pcbnew) fills them and re-saves.

    python3 tools/generate_board.py [--out DIR] [--negative-test]

--negative-test adds deliberately illegal items (a capacitor inside KO_BGA_TOP, a
via inside KO_VRM, a track inside KO_DDR_CHANNEL, a via inside KO_MH1) so the
.kicad_dru keepout rules can be proven to fire.  Never ship that variant.
"""
import argparse
import json
import math
import os
import uuid

NAME = "daedalus_core_pdn"
NS = uuid.UUID("7d1f4d2e-5b7a-4f3c-9a0e-dae0a105c0de")  # fixed namespace for deterministic UUIDs

# ---------------------------------------------------------------- spec numbers
BOARD = (70.0, 60.0, 130.0, 100.0)          # x0 y0 x1 y1 (Edge.Cuts)
THICKNESS = 1.54
ZONE_EDGE_CLEARANCE = 1.0
ZONE_CLEARANCE = 0.1
ZONE_MIN_WIDTH = 0.2
MH_POS = [(73.0, 63.0), (127.0, 63.0), (73.0, 97.0), (127.0, 97.0)]
MH_DRILL = 3.2
MH_KEEPOUT_R = 3.5

U1_CENTER = (100.0, 80.0)
U1_PITCH = 0.8
U1_N = 15
U1_PAD = 0.4
U1_MASK = 0.05
U1_ROWS = "ABCDEFGHJKLMNPR"               # JEDEC: I, O, Q skipped
U1_CORE_ROWS = range(4, 11)                # E..L  (7 rows)
U1_CORE_COLS = range(5, 12)                # 5..11 (7 cols)
U1_TRACK_W = 0.15
U1_VIA_OFF = (0.4, 0.4)
U1_VIA_D, U1_VIA_DRILL = 0.45, 0.2
U1_CRTYD = 13.0

U2_CENTER = (75.0, 80.0)
U2_PAD = (4.0, 3.0)
U2_PAD_Y = {1: 78.0, 2: 82.0}              # pad 1 VDD_CORE, pad 2 GND (absolute y)
U2_VIA_X = (73.8, 76.2)
U2_VIA_DY = (-0.8, 0.8)
U2_VIA_D, U2_VIA_DRILL = 0.6, 0.3
U2_CRTYD = (6.0, 8.0)

NETS = {"GND": 1, "VDD_CORE": 2}

RULE_AREAS = [  # name, layers, polygon pts
    ("KO_BGA_TOP", ["F.Cu"], "rect", (93.0, 73.0, 107.0, 87.0)),
    ("KO_DDR_CHANNEL", ["F.Cu", "B.Cu"], "rect", (108.0, 64.0, 130.0, 96.0)),
    ("KO_CONNECTOR", ["F.Cu", "B.Cu"], "rect", (70.0, 60.0, 90.0, 70.0)),
    ("KO_VRM", ["F.Cu", "B.Cu"], "rect", (70.0, 74.0, 81.0, 86.0)),
] + [
    ("KO_MH%d" % (i + 1), ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"], "circle", (x, y, MH_KEEPOUT_R))
    for i, (x, y) in enumerate(MH_POS)
]

# ---------------------------------------------------------------- helpers
def uid(name):
    return str(uuid.uuid5(NS, name))

def f(x):
    s = ("%.6f" % x).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s

def pts(points):
    return "(pts " + " ".join("(xy %s %s)" % (f(x), f(y)) for x, y in points) + ")"

def rect_pts(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

def circle_pts(cx, cy, r, n=72):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]

FONT = "(effects (font (size 1 1) (thickness 0.15)))"

def fp_property(fpname, key, value, at, layer, hide=False):
    h = " (hide yes)" if hide else ""
    return '(property "%s" "%s" (at %s %s 0) (layer "%s")%s (uuid "%s") %s)' % (
        key, value, f(at[0]), f(at[1]), layer, h, uid("%s/prop/%s" % (fpname, key)), FONT)

def footprint(ref, lib_name, value, center, attr, props_extra, items, supplied):
    fpid = uid("fp/" + ref)
    supplied["footprints"].append({"reference": ref, "footprint": lib_name, "uuid": fpid,
                                   "at": [center[0], center[1]]})
    lines = ['(footprint "%s" (layer "F.Cu") (uuid "%s") (at %s %s)' % (lib_name, fpid, f(center[0]), f(center[1]))]
    lines += props_extra
    lines.append('(property "Footprint" "%s" (at 0 0 0) (layer "F.Fab") (hide yes) (uuid "%s") %s)' % (lib_name, uid("fp/%s/prop/Footprint" % ref), FONT))
    lines.append('(property "Datasheet" "" (at 0 0 0) (layer "F.Fab") (hide yes) (uuid "%s") %s)' % (uid("fp/%s/prop/Datasheet" % ref), FONT))
    lines.append('(property "Description" "%s" (at 0 0 0) (layer "F.Fab") (hide yes) (uuid "%s") %s)' % (value, uid("fp/%s/prop/Description" % ref), FONT))
    lines.append("(attr %s)" % attr)
    lines += items
    lines.append(")")
    return "\n\t".join(lines)

def courtyard(ref, w, h):
    return '(fp_rect (start %s %s) (end %s %s) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd") (uuid "%s"))' % (
        f(-w / 2), f(-h / 2), f(w / 2), f(h / 2), uid("fp/%s/crtyd" % ref))

# ---------------------------------------------------------------- U1
def build_u1(supplied):
    items = [courtyard("U1", U1_CRTYD, U1_CRTYD)]
    ball_map = {}        # pad name -> net name or None
    core = []            # (pad, net, abs_x, abs_y)
    for r in range(U1_N):
        for c in range(1, U1_N + 1):
            name = "%s%d" % (U1_ROWS[r], c)
            rx = -U1_PITCH * (U1_N - 1) / 2 + U1_PITCH * (c - 1)
            ry = -U1_PITCH * (U1_N - 1) / 2 + U1_PITCH * r
            net = None
            if r in U1_CORE_ROWS and c in U1_CORE_COLS:
                i, j = r - U1_CORE_ROWS[0], c - U1_CORE_COLS[0]
                net = "VDD_CORE" if (i + j) % 2 == 0 else "GND"
                core.append((name, net, U1_CENTER[0] + rx, U1_CENTER[1] + ry))
            ball_map[name] = net
            netclause = ' (net %d "%s")' % (NETS[net], net) if net else ""
            items.append('(pad "%s" smd circle (at %s %s) (size %s %s) (layers "F.Cu" "F.Mask" "F.Paste") (solder_mask_margin %s)%s (uuid "%s"))' % (
                name, f(rx), f(ry), f(U1_PAD), f(U1_PAD), f(U1_MASK), netclause, uid("fp/U1/pad/" + name)))
    props = [fp_property("fp/U1", "Reference", "U1", (0, -7.5), "F.SilkS"),
             fp_property("fp/U1", "Value", "SoC", (0, 7.5), "F.Fab")]
    fp = footprint("U1", "BGA-225_15x15_0.8mm", "SoC BGA-225 15x15 0.8mm, supplied item", U1_CENTER, "smd", props, items, supplied)
    return fp, ball_map, core

# ---------------------------------------------------------------- U2
def build_u2(supplied):
    items = [courtyard("U2", *U2_CRTYD)]
    for num, net in ((1, "VDD_CORE"), (2, "GND")):
        ry = U2_PAD_Y[num] - U2_CENTER[1]
        items.append('(pad "%d" smd rect (at 0 %s) (size %s %s) (layers "F.Cu" "F.Mask" "F.Paste") (net %d "%s") (uuid "%s"))' % (
            num, f(ry), f(U2_PAD[0]), f(U2_PAD[1]), NETS[net], net, uid("fp/U2/pad/%d" % num)))
    props = [fp_property("fp/U2", "Reference", "U2", (0, -5), "F.SilkS"),
             fp_property("fp/U2", "Value", "VRM_OUT", (0, 5), "F.Fab")]
    return footprint("U2", "VRM_OUT", "VRM output pads, supplied item", U2_CENTER, "smd", props, items, supplied)

# ---------------------------------------------------------------- mounting holes
def build_mh(i, pos, supplied):
    ref = "H%d" % (i + 1)
    items = ['(pad "" np_thru_hole circle (at 0 0) (size %s %s) (drill %s) (layers "*.Cu" "*.Mask") (uuid "%s"))' % (
        f(MH_DRILL), f(MH_DRILL), f(MH_DRILL), uid("fp/%s/pad" % ref))]
    props = [fp_property("fp/" + ref, "Reference", ref, (0, -2.5), "F.Fab", hide=True),
             fp_property("fp/" + ref, "Value", "MountingHole_3.2mm", (0, 2.5), "F.Fab", hide=True)]
    # Deliberately no courtyard (keepout footprint checks are courtyard based).
    return footprint(ref, "MountingHole_3.2mm", "NPTH 3.2 mm mounting hole, supplied item", pos, "through_hole exclude_from_pos_files exclude_from_bom", props, items, supplied)

# ---------------------------------------------------------------- tracks / vias
def segment(name, a, b, w, layer, net, supplied):
    u = uid("seg/" + name)
    supplied["tracks"].append({"name": name, "uuid": u, "start": list(a), "end": list(b), "width": w, "layer": layer, "net": net})
    return '(segment (start %s %s) (end %s %s) (width %s) (layer "%s") (net %d) (uuid "%s"))' % (
        f(a[0]), f(a[1]), f(b[0]), f(b[1]), f(w), layer, NETS[net], u), u

def via(name, p, d, drill, net, supplied):
    u = uid("via/" + name)
    supplied["vias"].append({"name": name, "uuid": u, "at": list(p), "diameter": d, "drill": drill, "net": net})
    return '(via (at %s %s) (size %s) (drill %s) (layers "F.Cu" "B.Cu") (net %d) (uuid "%s"))' % (
        f(p[0]), f(p[1]), f(d), f(drill), NETS[net], u), u

# ---------------------------------------------------------------- zones
def plane(name, net, layer, supplied):
    u = uid("zone/" + name)
    x0, y0, x1, y1 = BOARD
    e = ZONE_EDGE_CLEARANCE
    supplied["zones"].append({"name": name, "uuid": u, "layer": layer, "net": net})
    return ('(zone (net %d) (net_name "%s") (layer "%s") (uuid "%s") (name "%s") (hatch edge 0.5) '
            '(connect_pads yes (clearance %s)) (min_thickness %s) (filled_areas_thickness no) '
            '(fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5)) (polygon %s))') % (
        NETS[net], net, layer, u, name, f(ZONE_CLEARANCE), f(ZONE_MIN_WIDTH),
        pts(rect_pts(x0 + e, y0 + e, x1 - e, y1 - e)))

def rule_area(name, layers, kind, geom, supplied):
    u = uid("rulearea/" + name)
    if kind == "rect":
        p = rect_pts(*geom)
    else:
        p = circle_pts(*geom)
    supplied["rule_areas"].append({"name": name, "uuid": u, "layers": layers, "shape": kind, "geometry": list(geom)})
    lay = '(layer "%s")' % layers[0] if len(layers) == 1 else "(layers %s)" % " ".join('"%s"' % l for l in layers)
    # Named rule area with NO keepout flags: the keepout logic lives in the .kicad_dru rules.
    return ('(zone (net 0) (net_name "") %s (uuid "%s") (name "%s") (hatch edge 0.5) (connect_pads (clearance 0)) '
            '(min_thickness 0.25) (filled_areas_thickness no) '
            '(keepout (tracks allowed) (vias allowed) (pads allowed) (copperpour allowed) (footprints allowed)) '
            '(fill (thermal_gap 0.5) (thermal_bridge_width 0.5)) (polygon %s))') % (lay, u, name, pts(p))

def group(name, members, supplied):
    u = uid("group/" + name)
    supplied["groups"].append({"name": name, "uuid": u, "members": list(members)})
    return '(group "%s" (uuid "%s") (members %s))' % (name, u, " ".join('"%s"' % m for m in members))

# ---------------------------------------------------------------- board
HEADER = '''(kicad_pcb
	(version 20240108)
	(generator "daedalus_generate_board")
	(generator_version "8.0")
	(general
		(thickness %s)
		(legacy_teardrops no)
	)
	(paper "A4")
	(title_block
		(title "Daedalus core PDN - supplied board asset")
		(comment 1 "Generated by tools/generate_board.py from BOARD_ASSET_SPEC.md")
	)
	(layers
		(0 "F.Cu" signal)
		(1 "In1.Cu" power)
		(2 "In2.Cu" power)
		(31 "B.Cu" signal)
		(32 "B.Adhes" user "B.Adhesive")
		(33 "F.Adhes" user "F.Adhesive")
		(34 "B.Paste" user)
		(35 "F.Paste" user)
		(36 "B.SilkS" user "B.Silkscreen")
		(37 "F.SilkS" user "F.Silkscreen")
		(38 "B.Mask" user)
		(39 "F.Mask" user)
		(40 "Dwgs.User" user "User.Drawings")
		(41 "Cmts.User" user "User.Comments")
		(42 "Eco1.User" user "User.Eco1")
		(43 "Eco2.User" user "User.Eco2")
		(44 "Edge.Cuts" user)
		(45 "Margin" user)
		(46 "B.CrtYd" user "B.Courtyard")
		(47 "F.CrtYd" user "F.Courtyard")
		(48 "B.Fab" user)
		(49 "F.Fab" user)
	)
	(setup
		(stackup
			(layer "F.SilkS" (type "Top Silk Screen"))
			(layer "F.Paste" (type "Top Solder Paste"))
			(layer "F.Mask" (type "Top Solder Mask") (thickness 0))
			(layer "F.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 1" (type "prepreg") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In1.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 2" (type "core") (thickness 1) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In2.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 3" (type "prepreg") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "B.Cu" (type "copper") (thickness 0.035))
			(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0))
			(layer "B.Paste" (type "Bottom Solder Paste"))
			(layer "B.SilkS" (type "Bottom Silk Screen"))
			(copper_finish "None")
			(dielectric_constraints no)
		)
		(pad_to_mask_clearance 0)
		(allow_soldermask_bridges_in_footprints no)
	)
	(net 0 "")
	(net 1 "GND")
	(net 2 "VDD_CORE")
''' % f(THICKNESS)

def build(negative_test=False):
    supplied = {"footprints": [], "tracks": [], "vias": [], "zones": [], "rule_areas": [], "edge_cuts": [], "groups": []}
    out = [HEADER]

    u1, ball_map, core = build_u1(supplied)
    out.append(u1)
    out.append(build_u2(supplied))
    for i, p in enumerate(MH_POS):
        out.append(build_mh(i, p, supplied))

    # Edge.Cuts
    eu = uid("edge/outline")
    supplied["edge_cuts"].append({"uuid": eu, "rect": list(BOARD)})
    out.append('(gr_rect (start %s %s) (end %s %s) (stroke (width 0.05) (type default)) (fill none) (layer "Edge.Cuts") (uuid "%s"))' % (
        f(BOARD[0]), f(BOARD[1]), f(BOARD[2]), f(BOARD[3]), eu))

    # U1 dog-bones
    fanout = []
    for name, net, x, y in core:
        vx, vy = x + U1_VIA_OFF[0], y + U1_VIA_OFF[1]
        s, su = segment("U1/" + name, (x, y), (vx, vy), U1_TRACK_W, "F.Cu", net, supplied)
        v, vu = via("U1/" + name, (vx, vy), U1_VIA_D, U1_VIA_DRILL, net, supplied)
        out += [s, v]
        fanout += [su, vu]

    # U2 vias
    u2v = []
    for num, net in ((1, "VDD_CORE"), (2, "GND")):
        for vx in U2_VIA_X:
            for dy in U2_VIA_DY:
                v, vu = via("U2/pad%d/%s/%s" % (num, f(vx), f(dy)), (vx, U2_PAD_Y[num] + dy), U2_VIA_D, U2_VIA_DRILL, net, supplied)
                out.append(v)
                u2v.append(vu)

    out.append(plane("GND_PLANE", "GND", "In1.Cu", supplied))
    out.append(plane("VDD_CORE_PLANE", "VDD_CORE", "In2.Cu", supplied))
    for ra in RULE_AREAS:
        out.append(rule_area(*ra, supplied=supplied))

    out.append(group("U1_FANOUT", fanout, supplied))
    out.append(group("U2_VIAS", u2v, supplied))

    if negative_test:
        # 1) test capacitor inside KO_BGA_TOP (F.Cu), outside the U1 pad field
        cx, cy = 100.0, 73.5
        items = ['(fp_rect (start -0.9 -0.5) (end 0.9 0.5) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd") (uuid "%s"))' % uid("neg/C/crtyd"),
                 '(pad "1" smd roundrect (at -0.48 0) (size 0.56 0.62) (layers "F.Cu" "F.Mask" "F.Paste") (roundrect_rratio 0.25) (net 2 "VDD_CORE") (uuid "%s"))' % uid("neg/C/1"),
                 '(pad "2" smd roundrect (at 0.48 0) (size 0.56 0.62) (layers "F.Cu" "F.Mask" "F.Paste") (roundrect_rratio 0.25) (net 1 "GND") (uuid "%s"))' % uid("neg/C/2")]
        props = [fp_property("neg/C", "Reference", "CTEST1", (0, -1.5), "F.SilkS"), fp_property("neg/C", "Value", "0.1uF", (0, 1.5), "F.Fab")]
        out.append(footprint("CTEST1", "C_0402_1005Metric", "negative test", (cx, cy), "smd", props, items, {"footprints": []}))
        # 2) via inside KO_VRM (not in any group)
        out.append(via("neg/via_in_KO_VRM", (79.5, 85.0), U1_VIA_D, U1_VIA_DRILL, "GND", {"vias": []})[0])
        # 3) track inside KO_DDR_CHANNEL on B.Cu
        out.append(segment("neg/track_in_KO_DDR", (115.0, 80.0), (120.0, 80.0), 0.2, "B.Cu", "GND", {"tracks": []})[0])
        # 4) via inside KO_MH1 circle (2.5 mm from hole centre)
        out.append(via("neg/via_in_KO_MH1", (75.5, 63.0), U1_VIA_D, U1_VIA_DRILL, "GND", {"vias": []})[0])
        # 5) via inside an SMD pad that is not U2's (CTEST1 pad 2) -> no_via_in_pad
        out.append(via("neg/via_in_pad", (cx + 0.48, cy), U1_VIA_D, U1_VIA_DRILL, "GND", {"vias": []})[0])

    out.append(")\n")
    return "\n".join(out), supplied, ball_map

# ---------------------------------------------------------------- project / dru
def project_json():
    return {
        "board": {
            "3dviewports": [],
            "design_settings": {
                "defaults": {
                    "apply_defaults_to_fp_fields": False, "apply_defaults_to_fp_shapes": False, "apply_defaults_to_fp_text": False,
                    "board_outline_line_width": 0.05, "copper_line_width": 0.2, "copper_text_italic": False,
                    "copper_text_size_h": 1.5, "copper_text_size_v": 1.5, "copper_text_thickness": 0.3, "copper_text_upright": False,
                    "courtyard_line_width": 0.05,
                    "dimension_precision": 4, "dimension_units": 3,
                    "dimensions": {"arrow_length": 1270000, "extension_offset": 500000, "keep_text_aligned": True, "suppress_zeroes": False, "text_position": 0, "units_format": 1},
                    "fab_line_width": 0.1, "fab_text_italic": False, "fab_text_size_h": 1.0, "fab_text_size_v": 1.0, "fab_text_thickness": 0.15, "fab_text_upright": False,
                    "other_line_width": 0.1, "other_text_italic": False, "other_text_size_h": 1.0, "other_text_size_v": 1.0, "other_text_thickness": 0.15, "other_text_upright": False,
                    "pads": {"drill": 0.0, "height": 0.0, "width": 0.0},
                    "silk_line_width": 0.1, "silk_text_italic": False, "silk_text_size_h": 1.0, "silk_text_size_v": 1.0, "silk_text_thickness": 0.1, "silk_text_upright": False,
                    "zones": {"min_clearance": 0.1}
                },
                "diff_pair_dimensions": [],
                "drc_exclusions": [],
                "meta": {"version": 2},
                "rule_severities": {
                    "annular_width": "error", "clearance": "error", "connection_width": "warning", "copper_edge_clearance": "error",
                    "copper_sliver": "warning", "courtyards_overlap": "error", "diff_pair_gap_out_of_range": "error",
                    "diff_pair_uncoupled_length_too_long": "error", "drill_out_of_range": "error", "duplicate_footprints": "warning",
                    "extra_footprint": "warning", "footprint": "error", "footprint_symbol_mismatch": "warning", "footprint_type_mismatch": "ignore",
                    "hole_clearance": "error", "hole_near_hole": "error", "holes_co_located": "warning", "invalid_outline": "error",
                    "isolated_copper": "warning", "item_on_disabled_layer": "error", "items_not_allowed": "error", "length_out_of_range": "error",
                    "lib_footprint_issues": "warning", "lib_footprint_mismatch": "warning", "malformed_courtyard": "error",
                    "microvia_drill_out_of_range": "error", "missing_courtyard": "ignore", "missing_footprint": "warning",
                    "net_conflict": "warning", "npth_inside_courtyard": "ignore", "padstack": "warning", "pth_inside_courtyard": "ignore",
                    "shorting_items": "error", "silk_edge_clearance": "warning", "silk_over_copper": "warning", "silk_overlap": "warning",
                    "skew_out_of_range": "error", "solder_mask_bridge": "error", "starved_thermal": "error", "text_height": "warning",
                    "text_thickness": "warning", "through_hole_pad_without_hole": "error", "too_many_vias": "error",
                    "track_dangling": "warning", "track_width": "error", "tracks_crossing": "error", "unconnected_items": "error",
                    "unresolved_variable": "error", "via_dangling": "warning", "zones_intersect": "error"
                },
                "rules": {
                    "max_error": 0.005,
                    "min_clearance": 0.1,
                    "min_connection": 0.0,
                    "min_copper_edge_clearance": 0.5,
                    "min_hole_clearance": 0.25,
                    "min_hole_to_hole": 0.25,
                    "min_microvia_diameter": 0.2,
                    "min_microvia_drill": 0.1,
                    "min_resolved_spokes": 2,
                    "min_silk_clearance": 0.0,
                    "min_text_height": 0.8,
                    "min_text_thickness": 0.08,
                    "min_through_hole_diameter": 0.2,
                    "min_track_width": 0.15,
                    "min_via_annular_width": 0.125,
                    "min_via_diameter": 0.45,
                    "solder_mask_to_copper_clearance": 0.0,
                    "use_height_for_length_calcs": True
                },
                "teardrop_options": [{"td_onpadsmd": True, "td_onroundshapesonly": False, "td_ontrackend": False, "td_onviapad": True}],
                "teardrop_parameters": [
                    {"td_allow_use_two_tracks": True, "td_curve_segcount": 0, "td_height_ratio": 1.0, "td_length_ratio": 0.5, "td_maxheight": 2.0, "td_maxlen": 1.0, "td_on_pad_in_zone": False, "td_target_name": "td_round_shape", "td_width_to_size_filter_ratio": 0.9},
                    {"td_allow_use_two_tracks": True, "td_curve_segcount": 0, "td_height_ratio": 1.0, "td_length_ratio": 0.5, "td_maxheight": 2.0, "td_maxlen": 1.0, "td_on_pad_in_zone": False, "td_target_name": "td_rect_shape", "td_width_to_size_filter_ratio": 0.9},
                    {"td_allow_use_two_tracks": True, "td_curve_segcount": 0, "td_height_ratio": 1.0, "td_length_ratio": 0.5, "td_maxheight": 2.0, "td_maxlen": 1.0, "td_on_pad_in_zone": False, "td_target_name": "td_track_end", "td_width_to_size_filter_ratio": 0.9}
                ],
                "track_widths": [0.0, 0.15, 0.2],
                "via_dimensions": [{"diameter": 0.0, "drill": 0.0}, {"diameter": 0.45, "drill": 0.2}, {"diameter": 0.6, "drill": 0.3}],
                "zones_allow_external_fillets": False
            },
            "ipc2581": {"dist": "", "distpn": "", "internal_id": "", "mfg": "", "mpn": ""},
            "layer_presets": [],
            "viewports": []
        },
        "boards": [],
        "cvpcb": {"equivalence_files": []},
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": NAME + ".kicad_pro", "version": 1},
        "net_settings": {
            "classes": [{
                "bus_width": 12, "clearance": 0.1, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2,
                "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1, "name": "Default",
                "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
                "track_width": 0.2, "via_diameter": 0.45, "via_drill": 0.2, "wire_width": 6
            }],
            "meta": {"version": 3},
            "net_colors": None, "netclass_assignments": None, "netclass_patterns": []
        },
        "pcbnew": {"last_paths": {"gencad": "", "idf": "", "netlist": "", "plot": "", "pos_files": "", "specctra_dsn": "", "step": "", "svg": "", "vrml": ""}, "page_layout_descr_file": ""},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [],
        "text_variables": {}
    }

DRU = '''(version 1)

# Daedalus core PDN - design rules.  Numeric limits live in daedalus_core_pdn.kicad_pro
# (Board Setup > Constraints / Net Classes).  This file carries the rules that need
# conditions.  Supplied items (U1, U2, H1..H4, groups U1_FANOUT and U2_VIAS) are exempt
# from the keepouts; anything else placed in a rule area is a DRC error.

# No via-in-pad for any SMD pad.  U2's output pads are supplied with vias inside them
# and are exempt.
(rule no_via_in_pad
	(condition "A.Type == 'Via' && B.Type == 'Pad' && B.Pad_Type == 'SMD' && !B.memberOfFootprint('U2')")
	(constraint physical_clearance (min 0.1mm)))

# KO_BGA_TOP: F.Cu only, 14 x 14 mm around U1.  U1 and its supplied dog-bone fanout are exempt.
(rule ko_bga_top
	(layer "F.Cu")
	(condition "A.intersectsArea('KO_BGA_TOP') && !A.memberOfFootprint('U1') && !(A.Type == 'Footprint' && A.Reference == 'U1') && !A.memberOfGroup('U1_FANOUT')")
	(constraint disallow footprint via track))

# KO_DDR_CHANNEL: F.Cu and B.Cu, x 108..130, y 64..96.
(rule ko_ddr_channel
	(layer outer)
	(condition "A.intersectsArea('KO_DDR_CHANNEL')")
	(constraint disallow footprint via track))

# KO_CONNECTOR: F.Cu and B.Cu, x 70..90, y 60..70.  Mounting hole H1 sits in it and is exempt.
(rule ko_connector
	(layer outer)
	(condition "A.intersectsArea('KO_CONNECTOR') && !A.memberOfFootprint('H1') && !(A.Type == 'Footprint' && A.Reference == 'H1')")
	(constraint disallow footprint via track))

# KO_VRM: F.Cu and B.Cu, x 70..81, y 74..86.  U2 and its supplied vias are exempt.
(rule ko_vrm
	(layer outer)
	(condition "A.intersectsArea('KO_VRM') && !A.memberOfFootprint('U2') && !(A.Type == 'Footprint' && A.Reference == 'U2') && !A.memberOfGroup('U2_VIAS')")
	(constraint disallow footprint via track))

# KO_MH1..4: all copper layers, radius 3.5 mm around each mounting hole.  The hole footprint itself is exempt.
%s

# Copper keepout radius 3.5 mm around the 3.2 mm NPTH mounting holes, enforced for zone
# fills and for any copper added later: hole edge (r 1.6) + 1.9 mm = 3.5 mm.
(rule mounting_hole_copper_keepout
	(condition "B.Pad_Type == 'NPTH, mechanical'")
	(constraint hole_clearance (min 1.9mm)))
''' % "\n".join(
    '(rule ko_mh%d\n\t(condition "A.intersectsArea(\'KO_MH%d\') && !A.memberOfFootprint(\'H%d\') && !(A.Type == \'Footprint\' && A.Reference == \'H%d\')")\n\t(constraint disallow footprint via track))' % (i, i, i, i)
    for i in range(1, 5))

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    ap.add_argument("--negative-test", action="store_true")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    text, supplied, ball_map = build(a.negative_test)
    with open(os.path.join(out, NAME + ".kicad_pcb"), "w") as fh:
        fh.write(text)
    with open(os.path.join(out, NAME + ".kicad_pro"), "w") as fh:
        json.dump(project_json(), fh, indent=2)
        fh.write("\n")
    with open(os.path.join(out, NAME + ".kicad_dru"), "w") as fh:
        fh.write(DRU)
    if not a.negative_test:
        supplied["u1_ball_map"] = ball_map
        with open(os.path.join(out, "supplied_items.json"), "w") as fh:
            json.dump(supplied, fh, indent=2)
            fh.write("\n")
    n_v = sum(1 for b in ball_map.values() if b == "VDD_CORE")
    n_g = sum(1 for b in ball_map.values() if b == "GND")
    print("wrote %s/%s.kicad_pcb (+pro, dru%s); U1 balls VDD_CORE=%d GND=%d; vias=%d tracks=%d rule_areas=%d" % (
        out, NAME, "" if a.negative_test else ", supplied_items.json", n_v, n_g,
        len(supplied["vias"]), len(supplied["tracks"]), len(supplied["rule_areas"])))

if __name__ == "__main__":
    main()
