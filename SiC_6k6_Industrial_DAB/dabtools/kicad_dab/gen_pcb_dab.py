#!/usr/bin/env python3
"""
DAB power board: BoardGen configuration (placement, planes, pours, keepouts, clearance classes).

Board 340 x 250 mm, 6 layers (2 oz outer, 2 oz inner; 2.4 mm FR4 Tg170, CTI >= 400):
  F.Cu   components, HV_IN/LV_IN/SH_N pours, gate/sensing/control tracks, ground fills per region
  In1.Cu reference planes: HV_N (HV region) | GND (control region) | LV_N (LV region)
  In2.Cu power planes:     HV_P              | GND                  | LV_P
  In3.Cu reference planes (duplicate of In1 -> return path for B.Cu signals, extra copper for the links)
  In4.Cu power planes (duplicate of In2)
  B.Cu   switch-node strips (SW_A/B/C/D), signals, ground fills per region
Regions: HV x 5-118 | barrier 118-134 (16 mm) | CTRL 134-205 | barrier 205-221 | LV 221-335.
Straddling components (drivers, bias modules, isolated amplifiers, CT) sit in cut-outs of the
barrier keepouts; their own creepage is given by the certified component (+ slot under the bias
modules), see 15_Safety_Reliability/01.
"""
import os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__)); DAB = os.path.dirname(os.path.dirname(HERE)); REPO = os.path.dirname(DAB)
sys.path.insert(0, REPO); sys.path.insert(0, DAB)
import pcbnew
from tools.kicad.boardgen import BoardConfig, BoardGen, FULL, THERM, grp, pair
from dabtools.kicad_dab import design_dab as D

OUT = os.path.join(DAB, "07_KiCad_Schematics")          # single project directory (schematic + pcb)
LIBDIR = os.path.join(OUT, "lib", f"{D.LIB}.pretty")
BW, BH = 340.0, 250.0
HV_X2, C_X1, C_X2, LV_X1 = 118.0, 134.0, 205.0, 221.0
BAR1, BAR2 = 126.0, 213.0          # barrier centre lines

PL = {}
def P(ref, x, y, r=0): PL[ref] = (x, y, r)

# ------------------------------------------------------------------ HV region
for q, qx in zip((1, 2, 3, 4), (30, 52, 76, 98)):
    P(f"Q{q}", qx, 14, 0)
P("C5", 36, 38); P("C6", 46, 38); P("C7", 82, 38); P("C8", 92, 38)
P("J1", 14, 70); P("F1", 54, 70); P("J2", 14, 100)
for i, y in zip((1, 2, 3, 4), (100, 139, 178, 217)):
    P(f"C{i}", 60, y, 0)
P("J4", 104, 52); P("J3", 92, 105); P("J9", 100, 150)   # J3 west of the SW_A_CT strip (x 103-109)
P("R1", 106, 170); P("R2", 106, 177); P("R3", 106, 184); P("R4", 106, 191)
P("CY1", 24, 241, 0); P("CY2", 60, 241, 0); P("J21", 14, 125, 0)   # PE lug: >= 8.5 mm from HV pads (J2 stud, C1); the HV_N pour recedes by rule
P("TP1", 96, 118); P("TP2", 104, 64); P("TP3", 30, 56)   # TP1 below J3 (joined to the SW_A pour by a short track), TP3 clear of the fuse stud
# ------------------------------------------------------------------ HV barrier (x = 126)
P("U1", BAR1, 20, 180); P("U2", BAR1, 34, 180)
P("PS1", BAR1, 48, 180); P("PS2", BAR1, 58, 180); P("PS3", BAR1, 68, 180); P("PS4", BAR1, 78, 180)
P("CT1", BAR1, 100, 0)
P("U5", BAR1, 124, 0); P("PS9", BAR1, 136, 180)
# ------------------------------------------------------------------ LV region (mirror)
for q, qx in zip((5, 6, 7, 8), (246, 268, 292, 314)):
    P(f"Q{q}", qx, 14, 0)
P("C13", 252, 38); P("C14", 262, 38); P("C15", 298, 38); P("C16", 308, 38)
P("J8", 300, 52); P("J7", 236, 60)   # SW_C stud: 5 mm from the PS6 body, clear of the U4 fan-out
for i, (x, y) in zip((9, 10, 11, 12), ((250, 95), (295, 95), (250, 122), (295, 122))):
    P(f"C{i}", x, y, 0)
P("F2", 270, 160); P("J5", 312, 160); P("R7", 280, 200); P("J6", 312, 200)
P("R5", 232, 150); P("R6", 232, 157)
P("CY3", 250, 241, 0); P("CY4", 290, 241, 0); P("J22", 270, 241, 0)
P("TP4", 232, 72); P("TP5", 300, 64); P("TP6", 232, 80)
# ------------------------------------------------------------------ LV barrier (x = 213)
P("U3", BAR2, 20, 0); P("U4", BAR2, 34, 0)
P("PS5", BAR2, 48, 0); P("PS6", BAR2, 58, 0); P("PS7", BAR2, 68, 0); P("PS8", BAR2, 78, 0)
P("U6", BAR2, 100, 180); P("U7", BAR2, 114, 180); P("PS10", BAR2, 128, 0)
# ------------------------------------------------------------------ control region (x 134-205)
P("J10", 146, 150, 0); P("J11", 199.9, 150, 0); P("J12", 170, 150, 0)
P("U8", 150, 62); P("U9", 150, 80); P("U10", 168, 62); P("U11", 168, 80); P("U12", 186, 70)
P("D30", 146, 108); P("D31", 146, 114)   # clear of the CT1 secondary pins / body
P("U13", 150, 212, 0); P("U14", 166, 212, 0); P("U15", 182, 212, 0)   # U15 tab pad clear of the y=202 passive row
P("U16", 150, 190); P("J14", 141, 232, 0); P("J15", 192, 232, 0); P("J13", 160, 232, 0)
P("U17", 176, 186, 0); P("J16", 196, 174, 0); P("U18", 150, 181, 0); P("U19", 162, 181, 0); P("J17", 140, 160, 0)   # optocouplers clear of the J10 pin rows
P("J18", 196, 232, 0); P("J19", 200, 232, 0); P("J20", 152, 242, 0)
P("D34", 140, 120); P("D35", 140, 126); P("D32", 170, 224); P("D33", 180, 224)
P("TP7", 145, 56); P("TP8", 190, 56); P("TP9", 145, 90); P("TP10", 199, 84); P("TP11", 140, 200); P("TP12", 140, 206); P("TP13", 140, 212)
for i, (x, y) in enumerate(((7, 7), (333, 7), (7, 243), (333, 243), (170, 7), (170, 243)), start=1):
    P(f"H{i}", x, y)

# ------------------------------------------------------------------ small parts: generated refs placed in rows by sheet/group
def place_generated(comps):
    """Gate clusters next to their MOSFET, control passives in rows; deterministic from the design order."""
    # gate clusters: find parts whose nets reference G_Qn / KS_Qn / VDD_Qn / VEE_Qn / GD_Qn
    qx = {1: 30, 2: 52, 3: 76, 4: 98, 5: 246, 6: 268, 7: 292, 8: 314}
    cluster = {q: [] for q in qx}
    for c in comps:
        if c.ref in PL or c.sheet != "gate" or c.ref.startswith(("U", "PS")):
            continue
        for q in qx:
            if any(n.endswith(f"_Q{q}") for n in c.pins.values()):
                cluster[q].append(c); break
    for q, parts in cluster.items():
        x0 = qx[q]
        # row 1 (y = 22): Rg_on, Rg_off, D, Rgs ; row 2 (y = 28): caps
        r1 = [c for c in parts if c.footprint in ("R_1206", "D_SMA", "R_0603") and c.symbol in ("R", "D_SCHOTTKY")]
        r2 = [c for c in parts if c.symbol == "C"]
        xs1 = (x0 - 8.5, x0 - 3.0, x0 + 3.0, x0 + 8.5)    # fits the 22 mm MOSFET pitch; SMA inside
        rs = sorted([c for c in r1 if c.symbol == "R"], key=lambda c: c.ref); ds = [c for c in r1 if c.symbol != "R"]
        for c, x in zip(rs[:2] + ds + rs[2:], xs1):
            P(c.ref, x, 22)
        for c, x in zip(r2, (x0 - 7, x0 - 3, x0 + 0.5, x0 + 4)):
            P(c.ref, x, 28)
    # driver-side parts (DT resistors, VCCI caps) and bias input caps: along the barriers on the control side
    yb = {"U1": 20, "U2": 34, "U3": 20, "U4": 34}
    for c in comps:
        if c.ref in PL or c.sheet != "gate": continue
        nets = list(c.pins.values())
        for u, y in yb.items():
            if f"DT_{u}" in nets:
                P(c.ref, 140 if u in ("U1", "U2") else 199, y - 2); break   # clear of the driver fan-out corridors
        else:
            if "+5V" in nets and "GND" in nets:          # VCCI caps: assign to drivers in order
                k = sum(1 for r in PL if r.startswith("C") and PL[r][1] in (23, 37) and PL[r][0] in (140, 199))
                u = ["U1", "U2", "U3", "U4"][k % 4]; P(c.ref, 140 if u in ("U1", "U2") else 199, yb[u] + 3)
            elif "+12V" in nets and "GND" in nets:       # bias input caps next to each module
                k = sum(1 for r in PL if r.startswith("C") and PL[r][0] in (139, 199))
                side, y = (139, 48 + 10 * k) if k < 4 else ((199, 48 + 10 * (k - 4)) if k < 8 else (145, 98 + 6 * (k - 8)))
                P(c.ref, side, y)   # x = 138 / 199: clear of the driver and sense-amplifier fan-out corridors
    # sensing sheet passives: rows in the control region near their function
    rows = {"hv": (x for x in [108, 108, 108, 108, 108, 108, 108, 108]), }
    hv_y = iter(range(200, 236, 5)); lv_y = iter(range(170, 236, 5)); ctrl_slots = iter([(x, y) for y in (100, 106, 112, 118, 124, 130) for x in (150, 155, 160, 165, 170, 175, 180, 185, 190, 195)])
    for c in comps:
        if c.ref in PL or c.sheet != "sense": continue
        cl = {D.net_class(n) for n in c.pins.values()}
        if "HV_GATE" in cl or "HV_POWER" in cl:
            P(c.ref, 108, next(hv_y))
        elif "LV_GATE" in cl or "LV_POWER" in cl:
            P(c.ref, 232, next(lv_y))
        else:
            x, y = next(ctrl_slots); P(c.ref, x, y)
    ctrl_slots2 = iter([(x, y) for y in (196, 202, 218, 224) for x in (146, 151, 156, 161, 166, 171, 176, 181, 186, 191)])
    tht_row = iter([(150 + 10 * k, 90) for k in range(5)])
    for c in comps:
        if c.ref in PL: continue
        if c.sheet == "ctrl":
            if c.footprint.startswith("C_Radial"):
                x, y = next(tht_row)
            else:
                x, y = next(ctrl_slots2)
            P(c.ref, x, y)
        else:
            raise SystemExit(f"unplaced {c.ref} ({c.sheet})")

# ------------------------------------------------------------------ zones
HVR = (5, 5, HV_X2, BH - 5); CR = (C_X1, 5, C_X2, BH - 5); LVR = (LV_X1, 5, BW - 5, BH - 5)
ZONES = [
    ("HV_N", "F.Cu", [HVR], 0, THERM), ("HV_N", "B.Cu", [HVR], 0, THERM), ("HV_N", "In1.Cu", [HVR], 0, THERM), ("HV_N", "In3.Cu", [HVR], 0, THERM),
    ("HV_P", "In2.Cu", [HVR], 0, FULL), ("HV_P", "In4.Cu", [HVR], 0, FULL),
    ("GND", "F.Cu", [CR], 0, THERM), ("GND", "B.Cu", [CR], 0, THERM), ("GND", "In1.Cu", [CR], 0, THERM), ("GND", "In2.Cu", [CR], 0, THERM), ("GND", "In3.Cu", [CR], 0, THERM), ("GND", "In4.Cu", [CR], 0, THERM),
    ("LV_N", "F.Cu", [LVR], 0, THERM), ("LV_N", "B.Cu", [LVR], 0, THERM), ("LV_N", "In1.Cu", [LVR], 0, THERM), ("LV_N", "In3.Cu", [LVR], 0, THERM),
    ("LV_P", "In2.Cu", [LVR], 0, FULL), ("LV_P", "In4.Cu", [LVR], 0, FULL),
    # switch-node strips on B.Cu (10 A rms HV side, 20 A rms LV side)
    ("SW_A", "B.Cu", [(32, 11, 36.2, 20), (49, 11, 52.6, 20), (32, 17, 52.6, 20), (43.5, 17, 48, 100), (84, 97, 100, 113)], 2, FULL),
    ("SW_A", "B.Cu", [(43.5, 97, 100, 103)], 2, FULL),
    ("SW_B", "B.Cu", [(78, 11, 82.2, 20), (95, 11, 98.6, 20), (78, 17, 98.6, 20), (86, 17, 90, 46), (86, 44, 112, 60)], 2, FULL),
    ("SW_C", "B.Cu", [(248, 11, 252.2, 20), (265, 11, 268.6, 20), (248, 17, 268.6, 20), (254, 17, 260, 54), (224, 52, 260, 68)], 2, FULL),
    ("SW_D", "B.Cu", [(294, 11, 298.2, 20), (311, 11, 314.6, 20), (294, 17, 314.6, 20), (300, 17, 306, 46), (292, 44, 308, 60)], 2, FULL),
    ("HV_IN", "F.Cu", [(8, 64, 40, 76)], 2, FULL), ("HV_IN", "B.Cu", [(8, 64, 40, 76)], 2, FULL),
    ("LV_IN", "F.Cu", [(244, 154, 320, 166), (276, 166, 304, 174)], 2, FULL), ("LV_IN", "B.Cu", [(244, 154, 320, 166), (276, 166, 304, 174)], 2, FULL),   # loop below the fuse LV_P stud keeps the pour in one piece
    ("SH_N", "F.Cu", [(286, 194, 320, 206)], 2, FULL), ("SH_N", "B.Cu", [(286, 194, 320, 206)], 2, FULL),
    ("SW_A_CT", "F.Cu", [(92, 90, 114, 100)], 2, FULL),   # CT primary pad 2 (SW_A_CT) -> J9 stud via pour; pad1 (SW_A) joins the SW_A pour by via stitching
    ("SW_A_CT", "F.Cu", [(92, 142, 108, 158)], 2, FULL), ("SW_A_CT", "F.Cu", [(103, 95, 109, 150)], 2, FULL),   # strip between J3 (SW_A) and CT pad 1
]
TRACKS = []

# barrier keepouts (all copper layers) with cut-outs for the straddling components
def barrier_keepouts(x1, x2, straddlers):
    """straddlers: list of (y_center, half_height) occupied by components allowed to cross."""
    cuts = sorted((y - h - 0.5, y + h + 0.5) for y, h in straddlers)
    rects, y0 = [], 3.0
    for a, b in cuts:
        if a > y0: rects.append((x1, y0, x2, a))
        y0 = max(y0, b)
    rects.append((x1, y0, x2, BH - 3))
    return rects
STRADDLE_HV = [(20, 5.5), (34, 5.5), (48, 4.2), (58, 4.2), (68, 4.2), (78, 4.2), (100, 11.5), (124, 4.5), (136, 4.2)]
STRADDLE_LV = [(20, 5.5), (34, 5.5), (48, 4.2), (58, 4.2), (68, 4.2), (78, 4.2), (100, 4.5), (114, 4.5), (128, 4.2)]
KEEPOUTS = barrier_keepouts(HV_X2, C_X1, STRADDLE_HV) + barrier_keepouts(C_X2, LV_X1, STRADDLE_LV)
# the switch-node pours of the HV region must not reach the SW_A CT pour: handled by distinct rectangles above

# ------------------------------------------------------------------ clearance classes
def cls(net):
    return D.net_class(net) if net else "NONE"
def pair_clearance(a, b):
    ca, cb = cls(a), cls(b); s = {ca, cb}
    if "NONE" in s: return 0.3
    hv = {"HV_POWER", "HV_GATE"}; lv = {"LV_POWER", "LV_GATE"}; ct = {"CTRL_POWER", "CTRL_SIGNAL"}
    if "PE" in s:                                   # basic insulation power -> PE (01_insulation_coordination.md table 3)
        if ca in hv or cb in hv: return 8.5
        if ca in lv or cb in lv: return 5.0
        return 0.5
    if (ca in hv and cb in lv) or (cb in hv and ca in lv): return 12.0
    if (ca in hv and cb in ct) or (cb in hv and ca in ct):
        if "HV_POWER" in s: return 12.0
        return 5.5 if "CTRL_POWER" in s else 8.0
    if (ca in lv and cb in ct) or (cb in lv and ca in ct):
        if "LV_POWER" in s: return 10.0
        return 5.5 if "CTRL_POWER" in s else 8.0
    if s == {"HV_POWER"} or s == {"LV_POWER"}: return 1.5
    if s == {"HV_POWER", "HV_GATE"} or s == {"LV_POWER", "LV_GATE"}: return 0.5
    if "HV_GATE" in s or "LV_GATE" in s: return 0.3
    if "CTRL_POWER" in s: return 0.3
    return 0.2
def track_width(net):
    c = cls(net)
    if net in ("+12V", "+24V", "+5V"): return 0.5   # <= 2 A on 70 um Cu (IPC-2221 ~2.6 A at 20 K); fits the 1.27 mm SOIC fan-out
    if c in ("HV_GATE", "LV_GATE"): return 0.5
    if net.startswith(("RELAY", "FAN_OUT")): return 0.8
    return 0.3
def dru_rules(nets):
    by = lambda k: sorted(n for n in nets if cls(n) == k)
    hvp, hvg, lvp, lvg, cp, cs, pe = by("HV_POWER"), by("HV_GATE"), by("LV_POWER"), by("LV_GATE"), by("CTRL_POWER"), by("CTRL_SIGNAL"), by("PE")
    hv, lv, ct = hvp + hvg, lvp + lvg, cp + cs
    return [("pe_to_lv", pair(lv, pe), 5.0), ("pe_to_hv", pair(hv, pe), 8.5),
            ("ctrl_power", f"{grp('A', cp)} || {grp('B', cp)}", 0.3),
            ("gate", f"{grp('A', hvg + lvg)} || {grp('B', hvg + lvg)}", 0.3),
            ("power_to_gate", pair(hvp, hvg) + " || " + pair(lvp, lvg), 0.5),
            ("hv_to_hv", f"{grp('A', hvp)} && {grp('B', hvp)}", 1.5),
            ("lv_to_lv", f"{grp('A', lvp)} && {grp('B', lvp)}", 1.5),
            ("iso_gate_bias_modules", pair(hvg + lvg, cp), 5.5),
            ("iso_gate_signal", pair(hvg + lvg, cs), 8.0),
            ("iso_lv_power_ctrl", pair(lvp, ct), 10.0),
            ("iso_hv_power_ctrl", pair(hvp, ct), 12.0),
            ("iso_hv_lv", pair(hv, lv), 12.0)]

def config():
    comps = D.build()
    place_generated(comps)
    all_nets = [n for n in D.nets_of(comps) if not n.startswith("NC_")]
    # milled 1.6 mm slots centred in the pin gap of each module (SIP-7 bias modules: between pin 2 and pin 5;
    # 1 W SIP-7 modules PS9/PS10: between positions 2 and 6), >= 2 mm from the pads (copper-edge rule)
    slots = [(BAR1 + 0.47, y - 4, BAR1 + 2.07, y + 4) for y in (48, 58, 68, 78)] + [(BAR1 - 0.8, 132, BAR1 + 0.8, 140)] + \
            [(BAR2 - 2.07, y - 4, BAR2 - 0.47, y + 4) for y in (48, 58, 68, 78)] + [(BAR2 - 0.8, 124, BAR2 + 0.8, 132)]
    texts = [("SiC 6.6 kW BIDIRECTIONAL DUAL ACTIVE BRIDGE  800 V <-> 400 V", 60, 245, pcbnew.F_SilkS, 2.5, 0.4, 0),
             ("DANGER: HV LINK 850 VDC", 60, 241, pcbnew.F_SilkS, 2.0, 0.35, 0), ("DANGER: LV LINK 450 VDC", 280, 241, pcbnew.F_SilkS, 2.0, 0.35, 0),
             ("CONTROL (SELV)", 170, 245, pcbnew.F_SilkS, 1.5, 0.25, 0), ("rev A  2026-10  open hardware", 170, 241, pcbnew.F_SilkS, 1.2, 0.2, 0),
             ("16 mm ISOLATION BARRIER", BAR1, 190, pcbnew.Dwgs_User, 1.5, 0.2, 90), ("16 mm ISOLATION BARRIER", BAR2, 190, pcbnew.Dwgs_User, 1.5, 0.2, 90)]
    lines = [(HV_X2, 2, HV_X2, BH - 2, pcbnew.Dwgs_User, 0.2), (C_X1, 2, C_X1, BH - 2, pcbnew.Dwgs_User, 0.2), (C_X2, 2, C_X2, BH - 2, pcbnew.Dwgs_User, 0.2), (LV_X1, 2, LV_X1, BH - 2, pcbnew.Dwgs_User, 0.2)]
    fan = {f"U{i}": (2.2, 4.4, 0.3) for i in range(1, 5)}
    fan.update({"U5": (2.2, 4.4, 0.3), "U6": (2.2, 4.4, 0.3), "U7": (2.2, 4.4, 0.3), "U8": (1.8, 3.6, 0.3), "U9": (1.8, 3.6, 0.3), "U10": (1.8, 3.6, 0.3), "U11": (1.8, 3.6, 0.3), "U12": (1.8, 3.6, 0.3), "U16": (1.8, 3.6, 0.3), "U17": (1.8, 3.6, 0.3)})
    priv = [((118.5, 42, 133.5, 84), ["PS1", "PS2", "PS3", "PS4"]), ((205.5, 42, 220.5, 84), ["PS5", "PS6", "PS7", "PS8"]),
            ((118.5, 131, 133.5, 141), ["PS9"]), ((205.5, 123, 220.5, 133), ["PS10"])]
    def via_forbidden(x, y):
        return (HV_X2 - 0.6 < x < C_X1 + 0.6) or (C_X2 - 0.6 < x < LV_X1 + 0.6)
    return BoardConfig(project=D.PROJECT, lib=D.LIB, outdir=OUT, libdir=LIBDIR, design=D, BW=BW, BH=BH, layers=6,
                       placement=PL, zones=ZONES, tracks=TRACKS, keepout_rects=KEEPOUTS,
                       router_keepouts=[(x - 3.2, y - 3.2, x + 3.2, y + 3.2) for (x, y) in ((7, 7), (333, 7), (7, 243), (333, 243), (170, 7), (170, 243))] + slots,
                       private=priv, fanout=fan, plane_nets=["HV_N", "HV_P", "LV_N", "LV_P", "GND"],
                       pair_clearance=pair_clearance, track_width=track_width, dru_rules=dru_rules(all_nets),
                       dru_header="# Generated by dabtools/kicad_dab/gen_pcb_dab.py. Clearance classes by net name; later rules take precedence.\n# Isolation design values from 15_Safety_Reliability/01_insulation_coordination.md.\n",
                       via_forbidden=via_forbidden, edge_slots=slots, texts=texts, lines=lines, max_passes=14,
                       route_priority={"+12V": 0, "+5V": 1, "+3V3": 2, "+24V": 3, "PROT_DIS": 4}, zone_fallback_nets=[], board_thickness=2.4,
                       solid_zone_pads=[("U13", "2"), ("U14", "2"), ("U15", "1"), ("J12", "5"), ("J12", "7")])

def main(do_route=True):
    return BoardGen(config()).main(do_route=do_route)

if __name__ == "__main__":
    main(do_route="--noroute" not in sys.argv)
