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
    import shutil
    shutil.rmtree(os.path.join(out, "gerbers"), ignore_errors=True); shutil.rmtree(os.path.join(out, "drill"), ignore_errors=True)
    os.makedirs(os.path.join(out, "gerbers"), exist_ok=True); os.makedirs(os.path.join(out, "drill"), exist_ok=True)
    base = os.path.splitext(os.path.basename(pcb))[0]
    # only the copper layers the board actually has (kicad-cli would otherwise plot all 32)
    import pcbnew
    n_cu = pcbnew.LoadBoard(pcb).GetCopperLayerCount()
    layers = ["F.Cu"] + [f"In{i}.Cu" for i in range(1, n_cu - 1)] + ["B.Cu", "F.Mask", "B.Mask", "F.Paste", "B.Paste", "F.SilkS", "B.SilkS", "Edge.Cuts", "F.Fab", "Dwgs.User"]
    print(base, run(["kicad-cli", "pcb", "export", "gerbers", "-o", os.path.join(out, "gerbers") + "/", "-l", ",".join(layers), "--subtract-soldermask", pcb]))
    print(base, run(["kicad-cli", "pcb", "export", "drill", "-o", os.path.join(out, "drill") + "/", "--format", "excellon", "--generate-map", pcb]))
    print(base, run(["kicad-cli", "pcb", "export", "pos", "-o", os.path.join(out, base + "-top.pos"), "--side", "front", "--format", "csv", "--units", "mm", pcb]))
    print(base, run(["kicad-cli", "pcb", "export", "pdf", "-o", os.path.join(out, base + "-F_Fab.pdf"), "-l", "F.Fab,F.SilkS,Edge.Cuts", pcb]))
    print(base, run(["kicad-cli", "pcb", "export", "pdf", "-o", os.path.join(out, base + "-top-copper.pdf"), "-l", "F.Cu,Edge.Cuts", pcb]))
    print(base, run(["kicad-cli", "pcb", "export", "pdf", "-o", os.path.join(out, base + "-bottom-copper.pdf"), "-l", "B.Cu,Edge.Cuts", pcb]))
    print(base, run(["kicad-cli", "pcb", "export", "pdf", "-o", os.path.join(out, base + "-dimensions.pdf"), "-l", "Edge.Cuts,Dwgs.User", pcb]))
    sch = pcb.replace(".kicad_pcb", ".kicad_sch")
    print(base, run(["kicad-cli", "sch", "export", "pdf", "-o", os.path.join(out, base + "-schematic.pdf"), sch]))
