"""
PSFB board configuration for the reusable BoardGen (tools/kicad/boardgen.py).

Board: 260 x 200 mm, 4 layers, 2 oz copper.
  F.Cu  : components, high-current pours, signals
  In1.Cu: PGND plane (primary half) / SGND plane (secondary half)
  In2.Cu: VBUS plane (primary half) / SGND + VOUT planes (secondary half)
  B.Cu  : signals, SW_A/SW_B strips, secondary pours, ground fills
Isolation barrier at x = 130 mm (primary copper <= 125.5, secondary >= 134.5).
"""
import os, sys, math
import pcbnew
from . import design as D
from .boardgen import BoardConfig, BoardGen, FULL, THERM, grp, pair

OUT = os.path.join(D.ROOT, "hardware", "kicad")
LIBDIR = os.path.join(OUT, "lib", f"{D.LIB}.pretty")
BW, BH = 260.0, 200.0
BARRIER = (125.5, 134.5); BAR_X = 130.0; PS_Y_END = 47.0
KEEPOUT_RECTS = [(BARRIER[0], PS_Y_END, BARRIER[1], BH - 3), (128.4, 3, 134.2, PS_Y_END)]

PL = {}
def P(ref, x, y, r=0): PL[ref] = (x, y, r)
for q, qx in zip((1, 2, 3, 4), (40, 62, 86, 108)):
    P(f"Q{q}", qx, 14, 0)
    r0 = 22 + 3 * (q - 1); c0 = 33 + 5 * (q - 1)
    P(f"R{r0}", qx - 8, 22); P(f"R{r0+1}", qx - 3, 22); P(f"D{q+9}", qx + 3.6, 22); P(f"R{r0+2}", qx + 9, 22)
    P(f"C{c0}", qx - 7, 28); P(f"C{c0+1}", qx - 3, 28); P(f"C{c0+2}", qx + 0.5, 28); P(f"C{c0+3}", qx + 4, 28)
    P(f"PS{q}", BAR_X, 12 + 10 * (q - 1), 180)
    P(f"C{32 + 5*(q-1)}", 143, 12 + 10 * (q - 1), 0)
P("C5", 26, 24); P("C6", 116, 40)
P("C1", 16, 62, 90); P("C2", 16, 108, 90); P("C3", 38, 62, 90); P("C4", 38, 108, 90)
P("L1", 72, 70); P("D1", 60, 100, 0); P("D2", 60, 114, 180)
P("C7", 85, 100); P("C8", 85, 114)
P("T1", BAR_X, 100); P("CT1", BAR_X, 140); P("CY1", BAR_X, 158); P("CY2", BAR_X, 168)
P("U2", BAR_X, 56, 180); P("U3", BAR_X, 68, 180)
P("R20", 143, 49); P("C30", 143, 57); P("R21", 143, 61); P("C31", 143, 69)   # DT resistors clear of the +12V stub rows
P("J1", 16, 150); P("F1", 52, 150); P("J2", 16, 175); P("TP3", 40, 175); P("TP1", 50.75, 42); P("TP2", 96.6, 45)
P("H1", 7, 7); P("H2", 253, 7); P("H3", 7, 193); P("H4", 253, 193)
P("Q5", 154, 14, 0); P("Q6", 178, 14, 0); P("Q7", 154, 186, 180); P("Q8", 178, 186, 180)
P("R61", 163, 12); P("R62", 163, 8); P("R63", 169, 12); P("R64", 169, 8)
P("R65", 163, 188); P("R66", 163, 192); P("R67", 169, 188); P("R68", 169, 192)
P("R1", 176, 60); P("C9", 182.5, 60); P("R2", 176, 140); P("C10", 182.5, 140)
P("L2", 203, 100); P("TP4", 170, 100); P("TP5", 143, 45)
for i, y in zip(range(11, 17), (20, 38, 56, 144, 162, 180)):
    P(f"C{i}", 244, y, 90)
for i, y in zip(range(17, 23), (30, 36, 42, 150, 156, 162)):
    P(f"C{i}", 232, y, 0)
P("J3", 238, 100); P("R3", 200, 178); P("J4", 224, 178)
P("U1", 206, 38)
rows = {10: ["R40", "C52", "C53", "C54", "R41"], 16: ["R42", "C55", "R43", "R44", "R45"], 22: ["R46", "C56", "C57", "C58", "R47"],
        52: ["R48", "R49", "R50", "R51", "R52"], 58: ["R53", "R54", "R55", "R56", "R57"], 64: ["R58"]}
for y, refs in rows.items():
    for x, ref in zip((196, 201, 206, 211, 216), refs):
        P(ref, x, y)
P("TP6", 221, 10); P("TP7", 221, 16); P("TP8", 221, 22); P("TP9", 221, 52)
P("U4", 204, 150); P("C60", 195, 155); P("C61", 213, 155)
P("J6", 190, 130); P("J7", 206, 130); P("R69", 206, 137); P("D6", 210, 137); P("R70", 210, 142)
P("J5", 196, 166); P("D3", 205, 162); P("C64", 214, 162); P("C65", 205, 156)
P("D4", 140, 154); P("D5", 140, 160); P("R59", 140, 166); P("R60", 140, 171); P("C59", 140, 176)

ZONES = [
    ("PGND", "F.Cu", [(5, 5, 125.5, 195)], 0, THERM), ("PGND", "B.Cu", [(5, 5, 125.5, 195)], 0, THERM),
    ("SGND", "F.Cu", [(134.5, 5, 255, 195)], 0, THERM), ("SGND", "B.Cu", [(134.5, 5, 255, 195)], 0, THERM),
    ("PGND", "In1.Cu", [(5, 5, 125.5, 195)], 0, THERM), ("SGND", "In1.Cu", [(134.5, 5, 255, 195)], 0, THERM),
    ("VBUS", "In2.Cu", [(5, 5, 125.5, 195)], 0, FULL), ("SGND", "In2.Cu", [(134.5, 5, 186, 195)], 0, THERM),
    ("VOUT", "In2.Cu", [(186, 5, 255, 195)], 0, FULL),
    ("SW_A", "B.Cu", [(42, 11, 46.2, 20), (59, 11, 62.6, 20), (42, 17, 62.6, 20), (49, 17, 52.5, 66), (49, 64, 59, 75.5)], 2, FULL),
    ("SW_B", "B.Cu", [(88, 11, 92.2, 20), (105, 11, 108.6, 20), (88, 17, 108.6, 20), (95, 17, 98.2, 92), (95, 80, 110.5, 89.5)], 2, FULL),
    ("LR_N", "F.Cu", [(84, 64, 90, 78), (60.5, 76, 90, 118)], 2, FULL),
    ("PRI_1", "F.Cu", [(93, 96, 99, 150), (93, 142, 119, 150)], 2, FULL),
    ("PRI_2", "F.Cu", [(104, 110, 119, 138)], 2, FULL),
    ("VIN_RAW", "F.Cu", [(13, 147, 38.5, 153)], 2, FULL),
    ("SEC_A", "F.Cu", [(146, 17, 184, 95.2)], 2, FULL), ("SEC_A", "B.Cu", [(146, 24, 184, 95.2)], 2, FULL),
    ("SEC_CT", "F.Cu", [(146, 96.2, 194, 103.8)], 2, FULL), ("SEC_CT", "B.Cu", [(146, 96.2, 194, 103.8)], 2, FULL),
    ("SEC_B", "F.Cu", [(146, 104.8, 184, 183)], 2, FULL), ("SEC_B", "B.Cu", [(146, 104.8, 184, 176)], 2, FULL),
    ("VOUT", "F.Cu", [(226, 10, 250, 167), (233, 167, 250, 190)], 2, FULL), ("VOUT", "B.Cu", [(226, 10, 250, 167), (233, 167, 250, 190)], 2, FULL),
    ("OUT_N", "F.Cu", [(205, 170, 232, 186)], 2, FULL), ("OUT_N", "B.Cu", [(205, 170, 232, 186)], 2, FULL),
]
TRACKS = []
for x in (154, 178):
    TRACKS += [("SEC_A", "F.Cu", x, 14, x, 18.5, 1.6), ("SEC_A", "B.Cu", x, 14, x, 25, 1.6),
               ("SEC_B", "F.Cu", x, 186, x, 181.5, 1.6), ("SEC_B", "B.Cu", x, 186, x, 175, 1.6)]
TRACKS += [("SNUB_A", "F.Cu", 178.8, 60, 181.1, 60, 0.5), ("SNUB_B", "F.Cu", 178.8, 140, 181.1, 140, 0.5)]

PRI_POWER = sorted(D.PRIMARY_NETS)
def cls(net):
    return D.net_class(net) if net else "NONE"
def pair_clearance(a, b):
    ca, cb = cls(a), cls(b); s = {ca, cb}
    if "NONE" in s: return 0.3
    if ca.startswith("PRI") and cb.startswith("SEC") or cb.startswith("PRI") and ca.startswith("SEC"):
        return 5.5 if "PRI_GATE" in s else 8.0
    if s == {"PRI_POWER"}: return 1.0
    if s == {"PRI_POWER", "PRI_GATE"}: return 0.5
    if "SEC_POWER" in s: return 0.5
    if "PRI_GATE" in s: return 0.3
    return 0.2
def track_width(net):
    c = cls(net)
    if net in ("SR_A", "SR_B") or net.startswith(("G_Q5", "G_Q6", "G_Q7", "G_Q8")): return 0.5
    if net == "+12V": return 0.6          # VDD_IC (controller supply, < 50 mA) stays 0.3 mm: a 0.6 mm track cannot leave the 0.65 mm pitch fan-out
    if c == "PRI_GATE": return 0.5
    return 0.3

def dru_rules(nets):
    pri_gate = sorted(n for n in nets if cls(n) == "PRI_GATE")
    sec_all = sorted(n for n in nets if cls(n).startswith("SEC"))
    sec_pow = sorted(n for n in nets if cls(n) == "SEC_POWER")
    return [("sec_power", f"{grp('A', sec_pow)} || {grp('B', sec_pow)}", 0.5),
            ("pri_gate", f"{grp('A', pri_gate)} || {grp('B', pri_gate)}", 0.3),
            ("hv_to_gate", pair(PRI_POWER, pri_gate), 0.5),
            ("hv_to_hv", f"{grp('A', PRI_POWER)} && {grp('B', PRI_POWER)}", 1.0),
            ("isolation_gate_bias", pair(pri_gate, sec_all), 5.5),
            ("isolation_primary_secondary", pair(PRI_POWER, sec_all), 8.0)]

def config():
    comps = D.build()
    all_nets = [n for n in D.nets_of(comps) if not n.startswith("NC_")]
    return BoardConfig(
        project=D.PROJECT, lib=D.LIB, outdir=OUT, libdir=LIBDIR, design=D, BW=BW, BH=BH, layers=4,
        placement=PL, zones=ZONES, tracks=TRACKS, keepout_rects=KEEPOUT_RECTS,
        router_keepouts=[(130.0, 12 + 10 * q - 4.5, 132.6, 12 + 10 * q + 4.5) for q in range(4)] + [(x - 3.2, y - 3.2, x + 3.2, y + 3.2) for (x, y) in ((7, 7), (253, 7), (7, 193), (253, 193))],
        private=[((119.0, 6.0, 128.3, 46.5), ["PS1", "PS2", "PS3", "PS4"])],
        fanout={"U1": (3.4, 5.8, 0.25), "U2": (2.2, 4.4, 0.3), "U3": (2.2, 4.4, 0.3), "U4": (1.8, 3.6, 0.3)},
        plane_nets=["PGND", "SGND", "VBUS", "VOUT"], pair_clearance=pair_clearance, track_width=track_width,
        dru_rules=dru_rules(all_nets),
        dru_header="# Generated by tools/kicad/gen_pcb.py - clearance classes by net name. Later rules take precedence.\n# Isolation: reinforced 8 mm primary<->secondary; 5.5 mm + milled slot at the SIP-7 bias modules.\n",
        via_forbidden=lambda x, y: (BARRIER[0] - 0.6 < x < BARRIER[1] + 0.6 and y > PS_Y_END - 1) or (127.8 < x < 134.8 and y <= PS_Y_END),
        edge_slots=[(130.5, 12 + 10 * q - 4, 132.1, 12 + 10 * q + 4) for q in range(4)],
        texts=[("SiC ZVS PHASE-SHIFTED FULL BRIDGE  3 kW  400 V -> 48 V", 70, 190, pcbnew.F_SilkS, 2.5, 0.4, 0),
               ("DANGER: PRIMARY SIDE 420 VDC", 70, 185, pcbnew.F_SilkS, 2.0, 0.35, 0),
               ("ISOLATION BARRIER - NO COPPER", BAR_X + 2.5, 190, pcbnew.F_SilkS, 1.2, 0.2, 90),
               ("SECONDARY 48 V / 62.5 A", 200, 192, pcbnew.F_SilkS, 2.0, 0.35, 0),
               ("rev A  2026-10  open hardware", 200, 196, pcbnew.F_SilkS, 1.2, 0.2, 0),
               ("PRIMARY", 118, 190, pcbnew.Dwgs_User, 1.5, 0.2, 90), ("SECONDARY", 142, 190, pcbnew.Dwgs_User, 1.5, 0.2, 90)],
        lines=[(BAR_X, 2, BAR_X, BH - 2, pcbnew.Dwgs_User, 0.2)],
        max_passes=14, route_priority={"+12V": 0, "VDD_IC": 1, "VREF": 2}, zone_fallback_nets=["SNUB_A", "SNUB_B"],
        solid_zone_pads=[("PS4", "2"), ("Q8", "3")])   # pads at a pour edge: solid connection instead of starved thermal spokes

def main(do_route=True):
    return BoardGen(config()).main(do_route=do_route)

if __name__ == "__main__":
    main(do_route="--noroute" not in sys.argv)
