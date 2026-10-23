#!/usr/bin/env python3
"""Independent structural check of daedalus_core_pdn.kicad_pcb (stdlib only, any python3).

    python3 tools/verify_board.py daedalus_core_pdn.kicad_pcb supplied_items.json

Checks: outline, stackup thicknesses, nets, U1 ball nets (25 VDD_CORE / 24 GND), the 49
dog-bone tracks + vias, the 8 U2 vias, zone fills present on In1.Cu/In2.Cu, the 8 named
rule areas, groups, and that every UUID in supplied_items.json is still in the board.
Exit code 1 on any failure.
"""
import json
import re
import sys

# ------------------------------------------------------------ tiny S-expression reader
def parse(text):
    tok = re.compile(r'"(?:[^"\\]|\\.)*"|\(|\)|[^\s()"]+')
    stack = [[]]
    for m in tok.finditer(text):
        t = m.group(0)
        if t == "(":
            stack.append([])
        elif t == ")":
            n = stack.pop()
            stack[-1].append(n)
        else:
            stack[-1].append(t[1:-1] if t.startswith('"') else t)
    return stack[0][0]

def kids(node, key):
    return [n for n in node[1:] if isinstance(n, list) and n and n[0] == key]

def kid(node, key, default=None):
    k = kids(node, key)
    return k[0] if k else default

def num(s):
    return float(s)

fails = []
def check(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)

board = parse(open(sys.argv[1]).read())
supplied = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else None
text = open(sys.argv[1]).read()

# outline
rects = [r for r in kids(board, "gr_rect") if kid(r, "layer")[1] == "Edge.Cuts"]
check(len(rects) == 1 and [num(x) for x in kid(rects[0], "start")[1:]] == [70, 60] and [num(x) for x in kid(rects[0], "end")[1:]] == [130, 100],
      "Edge.Cuts rectangle (70,60)-(130,100)")
check(num(kid(kid(board, "general"), "thickness")[1]) == 1.54, "board thickness 1.54")

# stackup
st = kid(kid(board, "setup"), "stackup")
cu = {l[1]: num(kid(l, "thickness")[1]) for l in kids(st, "layer") if kid(l, "type")[1] == "copper"}
diel = [(kid(l, "type")[1], num(kid(l, "thickness")[1])) for l in kids(st, "layer") if kid(l, "type")[1] in ("prepreg", "core")]
check(cu == {"F.Cu": 0.035, "In1.Cu": 0.035, "In2.Cu": 0.035, "B.Cu": 0.035}, "copper 4 x 0.035: %s" % cu)
check(diel == [("prepreg", 0.2), ("core", 1.0), ("prepreg", 0.2)], "dielectrics prepreg 0.2 / core 1.0 / prepreg 0.2: %s" % diel)
check(abs(sum(cu.values()) + sum(t for _, t in diel) - 1.54) < 1e-9, "stackup sums to 1.54")

# nets
nets = {int(n[1]): n[2] for n in kids(board, "net")}
check(nets == {0: "", 1: "GND", 2: "VDD_CORE"}, "nets: %s" % nets)

# footprints
fps = {}
for fp in kids(board, "footprint"):
    ref = [p for p in kids(fp, "property") if p[1] == "Reference"][0][2]
    fps[ref] = fp
check(sorted(fps) == ["H1", "H2", "H3", "H4", "U1", "U2"], "footprints: %s" % sorted(fps))

u1 = fps["U1"]
check(u1[1] == "BGA-225_15x15_0.8mm" and [num(x) for x in kid(u1, "at")[1:3]] == [100, 80], "U1 BGA-225_15x15_0.8mm at (100,80)")
pads = kids(u1, "pad")
check(len(pads) == 225, "U1 has 225 pads")
ball = {}
for p in pads:
    n = kid(p, "net")
    ball[p[1]] = n[2] if n else None
    size = [num(x) for x in kid(p, "size")[1:3]]
    if size != [0.4, 0.4] or p[2] != "smd" or p[3] != "circle" or num(kid(p, "solder_mask_margin")[1]) != 0.05:
        fails.append("U1 pad %s geometry" % p[1])
rows = "ABCDEFGHJKLMNPR"
exp = {}
for r in range(15):
    for c in range(1, 16):
        n = None
        if 4 <= r <= 10 and 5 <= c <= 11:
            n = "VDD_CORE" if ((r - 4) + (c - 5)) % 2 == 0 else "GND"
        exp["%s%d" % (rows[r], c)] = n
check(ball == exp, "U1 ball map: %d VDD_CORE, %d GND, %d no-net" % (
    sum(v == "VDD_CORE" for v in ball.values()), sum(v == "GND" for v in ball.values()), sum(v is None for v in ball.values())))
a1 = [p for p in pads if p[1] == "A1"][0]
check([num(x) for x in kid(a1, "at")[1:3]] == [-5.6, -5.6], "U1 A1 at (-5.6,-5.6) rel = (94.4,74.4) abs")
cy = [r for r in kids(u1, "fp_rect") if kid(r, "layer")[1] == "F.CrtYd"]
check(len(cy) == 1 and [num(x) for x in kid(cy[0], "start")[1:]] == [-6.5, -6.5], "U1 courtyard 13x13")

u2 = fps["U2"]
u2pads = {p[1]: p for p in kids(u2, "pad")}
check(u2[1] == "VRM_OUT" and [num(x) for x in kid(u2, "at")[1:3]] == [75, 80], "U2 VRM_OUT at (75,80)")
check(kid(u2pads["1"], "net")[2] == "VDD_CORE" and [num(x) for x in kid(u2pads["1"], "at")[1:3]] == [0, -2] and [num(x) for x in kid(u2pads["1"], "size")[1:3]] == [4, 3], "U2 pad 1 VDD_CORE 4x3 at (75,78)")
check(kid(u2pads["2"], "net")[2] == "GND" and [num(x) for x in kid(u2pads["2"], "at")[1:3]] == [0, 2] and [num(x) for x in kid(u2pads["2"], "size")[1:3]] == [4, 3], "U2 pad 2 GND 4x3 at (75,82)")

for h, pos in zip(["H1", "H2", "H3", "H4"], [[73, 63], [127, 63], [73, 97], [127, 97]]):
    fp = fps[h]
    p = kids(fp, "pad")[0]
    check([num(x) for x in kid(fp, "at")[1:3]] == pos and p[2] == "np_thru_hole" and num(kid(p, "drill")[1]) == 3.2, "%s NPTH 3.2 at %s" % (h, pos))

# tracks and vias
segs = kids(board, "segment")
vias = kids(board, "via")
u1v = [v for v in vias if num(kid(v, "size")[1]) == 0.45]
u2v = [v for v in vias if num(kid(v, "size")[1]) == 0.6]
check(len(segs) == 49 and all(num(kid(s, "width")[1]) == 0.15 and kid(s, "layer")[1] == "F.Cu" for s in segs), "49 F.Cu tracks, width 0.15")
check(len(vias) == 57, "57 vias total")
check(len(u1v) == 49 and all(num(kid(v, "drill")[1]) == 0.2 for v in u1v), "49 U1 vias 0.45/0.2")
vn = lambda vs, n: sum(int(kid(v, "net")[1]) == n for v in vs)
check(vn(u1v, 2) == 25 and vn(u1v, 1) == 24, "U1 vias: %d VDD_CORE, %d GND" % (vn(u1v, 2), vn(u1v, 1)))
check(len(u2v) == 8 and all(num(kid(v, "drill")[1]) == 0.3 for v in u2v) and vn(u2v, 2) == 4 and vn(u2v, 1) == 4, "8 U2 vias 0.6/0.3: 4 VDD_CORE, 4 GND")
u2pos = sorted(tuple(num(x) for x in kid(v, "at")[1:3]) for v in u2v)
check(u2pos == sorted([(x, y) for x in (73.8, 76.2) for y in (77.2, 78.8, 81.2, 82.8)]), "U2 via positions x 73.8/76.2, y pad +-0.8")
# each U1 via sits at ball + (0.4,0.4) with a track joining them and the right net
pad_abs = {name: (100 + (-5.6 + 0.8 * (c - 1)), 80 + (-5.6 + 0.8 * r)) for r in range(15) for c in range(1, 16) for name in ["%s%d" % (rows[r], c)]}
okdb = 0
for name, net in exp.items():
    if not net:
        continue
    x, y = pad_abs[name]
    vx, vy = round(x + 0.4, 6), round(y + 0.4, 6)
    v = [v for v in u1v if [round(num(t), 6) for t in kid(v, "at")[1:3]] == [vx, vy]]
    s = [s for s in segs if [round(num(t), 6) for t in kid(s, "start")[1:3]] == [round(x, 6), round(y, 6)] and [round(num(t), 6) for t in kid(s, "end")[1:3]] == [vx, vy]]
    if len(v) == 1 and len(s) == 1 and nets[int(kid(v[0], "net")[1])] == net and nets[int(kid(s[0], "net")[1])] == net:
        okdb += 1
check(okdb == 49, "49 dog-bones (track ball->via at +0.4,+0.4, matching net): %d" % okdb)

# zones
zones = kids(board, "zone")
planes = [z for z in zones if not kids(z, "keepout")]
areas = [z for z in zones if kids(z, "keepout")]
pl = {kid(z, "layer")[1]: z for z in planes}
check(sorted(pl) == ["In1.Cu", "In2.Cu"] and kid(pl["In1.Cu"], "net_name")[1] == "GND" and kid(pl["In2.Cu"], "net_name")[1] == "VDD_CORE", "planes: In1.Cu GND, In2.Cu VDD_CORE")
for z in planes:
    fp_ = kids(z, "filled_polygon")
    npts = sum(len(kid(f, "pts")[1:]) for f in fp_)
    cp = kid(z, "connect_pads")
    check(len(fp_) >= 1 and npts > 100, "%s zone filled (%d polygons, %d points)" % (kid(z, "net_name")[1], len(fp_), npts))
    check(cp[1] == "yes" and num(kid(cp, "clearance")[1]) == 0.1 and num(kid(z, "min_thickness")[1]) == 0.2, "%s zone: solid connection, clearance 0.1, min width 0.2" % kid(z, "net_name")[1])
    poly = [tuple(num(t) for t in p[1:]) for p in kid(kid(z, "polygon"), "pts")[1:]]
    check(sorted(poly) == sorted([(71, 61), (129, 61), (129, 99), (71, 99)]), "%s zone outline 1.0 mm inside board edge" % kid(z, "net_name")[1])

names = {kid(z, "name")[1]: z for z in areas}
check(sorted(names) == ["KO_BGA_TOP", "KO_CONNECTOR", "KO_DDR_CHANNEL", "KO_MH1", "KO_MH2", "KO_MH3", "KO_MH4", "KO_VRM"], "8 rule areas: %s" % sorted(names))
def layers_of(z):
    l = kid(z, "layer")
    return [l[1]] if l else kid(z, "layers")[1:]
expect_layers = {"KO_BGA_TOP": ["F.Cu"], "KO_DDR_CHANNEL": ["F.Cu", "B.Cu"], "KO_CONNECTOR": ["F.Cu", "B.Cu"], "KO_VRM": ["F.Cu", "B.Cu"]}
for n, z in names.items():
    ls = layers_of(z)
    want = expect_layers.get(n, ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"])
    ko = kid(z, "keepout")
    flags = {k[0]: k[1] for k in ko[1:]}
    check(sorted(ls) == sorted(want) and all(v == "allowed" for v in flags.values()), "%s layers %s, no keepout flags (rules live in .kicad_dru)" % (n, ls))
groups = {g[1]: g for g in kids(board, "group")}
check(sorted(groups) == ["U1_FANOUT", "U2_VIAS"] and len(kid(groups["U1_FANOUT"], "members")[1:]) == 98 and len(kid(groups["U2_VIAS"], "members")[1:]) == 8, "groups U1_FANOUT (98 members), U2_VIAS (8 members)")

if supplied:
    want = set()
    for k in ("footprints", "tracks", "vias", "zones", "rule_areas", "edge_cuts", "groups"):
        want |= {d["uuid"] for d in supplied[k]}
    missing = [u for u in want if u not in text]
    check(not missing, "all %d supplied-item UUIDs present in board (%d missing)" % (len(want), len(missing)))

print("\n%d check(s) failed" % len(fails) if fails else "\nALL CHECKS PASSED")
sys.exit(1 if fails else 0)
