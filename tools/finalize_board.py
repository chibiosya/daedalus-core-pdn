#!/usr/bin/env python3
"""Load the generated board with KiCad 8's pcbnew, fill the copper zones and save it
back in canonical KiCad 8 format.  Run with KiCad's bundled interpreter:

    /path/to/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
        tools/finalize_board.py daedalus_core_pdn.kicad_pcb
"""
import sys
import pcbnew

path = sys.argv[1]
board = pcbnew.LoadBoard(path)          # also loads the .kicad_pro next to it
zones = [z for z in board.Zones() if not z.GetIsRuleArea()]
filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())
for z in zones:
    print("zone %-15s layer %-7s net %-9s filled=%s" % (
        z.GetZoneName(), board.GetLayerName(z.GetFirstLayer()), z.GetNetname(), z.IsFilled()))
pcbnew.SaveBoard(path, board)
print("saved", path)
