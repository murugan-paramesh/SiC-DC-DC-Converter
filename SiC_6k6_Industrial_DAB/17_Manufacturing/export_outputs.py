#!/usr/bin/env python3
"""Export gerbers, drill, pick-and-place, PDFs from the DAB (and PSFB) boards with kicad-cli 7."""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); DAB = os.path.dirname(HERE); REPO = os.path.dirname(DAB)
jobs = [(os.path.join(DAB, "07_KiCad_Schematics", "SiC_DAB_6k6.kicad_pcb"), os.path.join(HERE, "outputs")),
        (os.path.join(REPO, "hardware", "kicad", "SiC_PSFB_3kW.kicad_pcb"), os.path.join(REPO, "hardware", "outputs"))]
def run(args):
    r = subprocess.run(args, capture_output=True, text=True); return r.returncode == 0, (r.stdout + r.stderr).strip()[-200:]
for pcb, out in jobs:
    if not os.path.exists(pcb): print("missing", pcb); continue
    os.makedirs(os.path.join(out, "gerbers"), exist_ok=True); os.makedirs(os.path.join(out, "drill"), exist_ok=True)
    base = os.path.splitext(os.path.basename(pcb))[0]
    print(base, run(["kicad-cli", "pcb", "export", "gerbers", "-o", os.path.join(out, "gerbers") + "/", "--board-plot-params", pcb]))
    print(base, run(["kicad-cli", "pcb", "export", "drill", "-o", os.path.join(out, "drill") + "/", "--format", "excellon", "--generate-map", pcb]))
    print(base, run(["kicad-cli", "pcb", "export", "pos", "-o", os.path.join(out, base + "-top.pos"), "--side", "front", "--format", "csv", "--units", "mm", pcb]))
    print(base, run(["kicad-cli", "pcb", "export", "pdf", "-o", os.path.join(out, base + "-F_Fab.pdf"), "-l", "F.Fab,F.SilkS,Edge.Cuts", pcb]))
    print(base, run(["kicad-cli", "pcb", "export", "pdf", "-o", os.path.join(out, base + "-top-copper.pdf"), "-l", "F.Cu,Edge.Cuts", pcb]))
    print(base, run(["kicad-cli", "pcb", "export", "pdf", "-o", os.path.join(out, base + "-bottom-copper.pdf"), "-l", "B.Cu,Edge.Cuts", pcb]))
    print(base, run(["kicad-cli", "pcb", "export", "pdf", "-o", os.path.join(out, base + "-dimensions.pdf"), "-l", "Edge.Cuts,Dwgs.User", pcb]))
    sch = pcb.replace(".kicad_pcb", ".kicad_sch")
    print(base, run(["kicad-cli", "sch", "export", "pdf", "-o", os.path.join(out, base + "-schematic.pdf"), sch]))
