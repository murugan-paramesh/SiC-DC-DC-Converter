"""
PCB generator: builds hardware/kicad/SiC_PSFB_3kW.kicad_pcb with the pcbnew API.

Board: 260 x 200 mm, 4 layers, 2 oz copper.
  F.Cu  : components, high-current pours, signals
  In1.Cu: PGND plane (primary half) / SGND plane (secondary half)
  In2.Cu: VBUS plane (primary half) / SGND + VOUT planes (secondary half)
  B.Cu  : signals, secondary pours, ground fills
Isolation barrier at x = 130 mm (primary copper <= 125.5, secondary >= 134.5).

Flow: place footprints -> power pours & stub tracks -> stitching vias -> save ->
reload with project -> route signals (tools/kicad/router.py) -> fill zones ->
DRC report -> save.
"""
import os, sys, json, math, functools
import pcbnew
from . import design as D
from .router import Router, Rect, F, B, GRID

print = functools.partial(print, flush=True)
OUT = os.path.join(D.ROOT, "hardware", "kicad")
LIBDIR = os.path.join(OUT, "lib", f"{D.LIB}.pretty")
PCB = os.path.join(OUT, f"{D.PROJECT}.kicad_pcb")
PRO = os.path.join(OUT, f"{D.PROJECT}.kicad_pro")
DRU = os.path.join(OUT, f"{D.PROJECT}.kicad_dru")
MM = pcbnew.FromMM
V = lambda x, y: pcbnew.VECTOR2I_MM(x, y)

MAX_PASSES = 3
BW, BH = 260.0, 200.0
BARRIER = (125.5, 134.5)
BAR_X = 130.0
PS_Y_END = 47.0                    # the SIP-7 bias modules occupy y 6..47 on the barrier
KEEPOUT_RECTS = [(BARRIER[0], PS_Y_END, BARRIER[1], BH - 3), (128.4, 3, 134.2, PS_Y_END)]

# --------------------------------------------------------------------------
# Placement (x, y, rotation)
# --------------------------------------------------------------------------
PL = {}
def P(ref, x, y, r=0): PL[ref] = (x, y, r)

# primary bridge along the top edge, heatsink bar outside the edge
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
P("R20", 143, 52); P("C30", 143, 57); P("R21", 143, 64); P("C31", 143, 69)
P("J1", 16, 150); P("F1", 52, 150); P("J2", 16, 175); P("TP3", 40, 175); P("TP1", 50.75, 42); P("TP2", 96.6, 45)
P("H1", 7, 7); P("H2", 253, 7); P("H3", 7, 193); P("H4", 253, 193)
# secondary
P("Q5", 154, 14, 0); P("Q6", 178, 14, 0); P("Q7", 154, 186, 180); P("Q8", 178, 186, 180)
P("R61", 163, 12); P("R62", 163, 8); P("R63", 169, 12); P("R64", 169, 8)
P("R65", 163, 188); P("R66", 163, 192); P("R67", 169, 188); P("R68", 169, 192)
P("R1", 176, 60); P("C9", 182.5, 60); P("R2", 176, 140); P("C10", 182.5, 140)
P("L2", 203, 100); P("TP4", 170, 100); P("TP5", 140, 47)
for i, y in zip(range(11, 17), (20, 38, 56, 144, 162, 180)):
    P(f"C{i}", 244, y, 90)
for i, y in zip(range(17, 23), (30, 36, 42, 150, 156, 162)):
    P(f"C{i}", 232, y, 0)
P("J3", 238, 100); P("R3", 200, 178); P("J4", 224, 178)
P("U1", 198, 38)
rows = {10: ["R40", "C52", "C53", "C54", "R41"], 16: ["R42", "C55", "R43", "R44", "R45"], 22: ["R46", "C56", "C57", "C58", "R47"],
        52: ["R48", "R49", "R50", "R51", "R52"], 58: ["R53", "R54", "R55", "R56", "R57"], 64: ["R58"]}
for y, refs in rows.items():
    for x, ref in zip((188, 193, 198, 203, 208), refs):
        P(ref, x, y)
P("TP6", 184, 30); P("TP7", 184, 46); P("TP8", 212, 30); P("TP9", 212, 46)
P("U4", 200, 150); P("C60", 191, 155); P("C61", 209, 155)
P("J6", 190, 130); P("J7", 206, 130); P("R69", 206, 137); P("D6", 210, 137); P("R70", 210, 142)
P("J5", 196, 166); P("D3", 205, 162); P("C64", 214, 162); P("C65", 205, 156)
P("D4", 140, 154); P("D5", 140, 160); P("R59", 140, 166); P("R60", 140, 171); P("C59", 140, 176)

# --------------------------------------------------------------------------
# Copper pours: (net, layer, [rects], priority, connection)
# --------------------------------------------------------------------------
FULL, THERM = "full", "thermal"
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
    ("VOUT", "F.Cu", [(214, 10, 250, 167), (233, 167, 250, 190)], 2, FULL), ("VOUT", "B.Cu", [(214, 10, 250, 167), (233, 167, 250, 190)], 2, FULL),
    ("OUT_N", "F.Cu", [(205, 170, 232, 186)], 2, FULL), ("OUT_N", "B.Cu", [(205, 170, 232, 186)], 2, FULL),
]
ZONE_NETS = {z[0] for z in ZONES}
# escape regions reserved for the nets of the listed footprints
PRIVATE = [((119.0, 6.0, 128.3, 46.5), ["PS1", "PS2", "PS3", "PS4"])]
PLANE_NETS = {"PGND", "SGND", "VBUS", "VOUT"}

# explicit tracks: (net, layer, x1, y1, x2, y2, width)
TRACKS = []
for x in (154, 178):
    TRACKS += [("SEC_A", "F.Cu", x, 14, x, 18.5, 1.6), ("SEC_A", "B.Cu", x, 14, x, 25, 1.6),
               ("SEC_B", "F.Cu", x, 186, x, 181.5, 1.6), ("SEC_B", "B.Cu", x, 186, x, 175, 1.6)]
TRACKS += [("SNUB_A", "F.Cu", 178.8, 60, 181.1, 60, 0.5), ("SNUB_B", "F.Cu", 178.8, 140, 181.1, 140, 0.5)]

# --------------------------------------------------------------------------
# Clearance rules (mirrored in the .kicad_dru file and in the router)
# --------------------------------------------------------------------------
PRI_POWER = sorted(D.PRIMARY_NETS)
def cls(net):
    return D.net_class(net) if net else "NONE"
def pair_clearance(a, b):
    ca, cb = cls(a), cls(b)
    s = {ca, cb}
    if "NONE" in s:
        return 0.3
    if ca.startswith("PRI") and cb.startswith("SEC") or cb.startswith("PRI") and ca.startswith("SEC"):
        return 5.5 if "PRI_GATE" in s else 8.0
    if s == {"PRI_POWER"}:
        return 1.0
    if s == {"PRI_POWER", "PRI_GATE"}:
        return 0.5
    if "SEC_POWER" in s:
        return 0.5
    if "PRI_GATE" in s:
        return 0.3
    return 0.2

def track_width(net):
    c = cls(net)
    if net in ("SR_A", "SR_B") or net.startswith(("G_Q5", "G_Q6", "G_Q7", "G_Q8")):
        return 0.5
    if net in ("+12V", "VDD_IC"):
        return 0.6
    if c == "PRI_GATE":
        return 0.5
    return 0.3

def write_dru(nets):
    pri_gate = sorted(n for n in nets if cls(n) == "PRI_GATE")
    sec_all = sorted(n for n in nets if cls(n).startswith("SEC"))
    sec_pow = sorted(n for n in nets if cls(n) == "SEC_POWER")
    def grp(var, names):
        return "(" + " || ".join(f"{var}.NetName == '{n}'" for n in names) + ")"
    def pair(ga, gb):
        return f"({grp('A', ga)} && {grp('B', gb)}) || ({grp('A', gb)} && {grp('B', ga)})"
    rules = [
        ("sec_power", f"{grp('A', sec_pow)} || {grp('B', sec_pow)}", 0.5),
        ("pri_gate", f"{grp('A', pri_gate)} || {grp('B', pri_gate)}", 0.3),
        ("hv_to_gate", pair(PRI_POWER, pri_gate), 0.5),
        ("hv_to_hv", f"{grp('A', PRI_POWER)} && {grp('B', PRI_POWER)}", 1.0),
        ("isolation_gate_bias", pair(pri_gate, sec_all), 5.5),
        ("isolation_primary_secondary", pair(PRI_POWER, sec_all), 8.0),
    ]
    with open(DRU, "w") as fh:
        fh.write("(version 1)\n")
        fh.write("# Generated by tools/kicad/gen_pcb.py - clearance classes by net name (KiCad 7 python DRC does not resolve netclass patterns).\n")
        fh.write("# Later rules take precedence. Isolation: reinforced 8 mm primary<->secondary; 5.5 mm + milled slot at the SIP-7 bias modules.\n")
        for name, cond, clr in rules:
            fh.write(f'(rule "{name}"\n  (condition "{cond}")\n  (constraint clearance (min {clr}mm)))\n')

# --------------------------------------------------------------------------
def layer_id(name):
    return {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu, "In1.Cu": pcbnew.In1_Cu, "In2.Cu": pcbnew.In2_Cu}[name]

def add_track(board, net, layer, x1, y1, x2, y2, w):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(V(x1, y1)); t.SetEnd(V(x2, y2)); t.SetWidth(MM(w)); t.SetLayer(layer_id(layer) if isinstance(layer, str) else layer)
    t.SetNet(net); board.Add(t); return t

def add_via(board, net, x, y, size=0.8, drill=0.4):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(V(x, y)); v.SetDrill(MM(drill)); v.SetWidth(MM(size)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(net); board.Add(v); return v

def add_zone(board, net, layer, rect, prio, conn, name=""):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer_id(layer)); z.SetNet(net)
    ol = z.Outline(); ol.NewOutline()
    x1, y1, x2, y2 = rect
    for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
        ol.Append(MM(x), MM(y))
    if hasattr(z, "SetAssignedPriority"): z.SetAssignedPriority(prio)
    else: z.SetPriority(prio)
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if conn == FULL else pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetMinThickness(MM(0.25)); z.SetLocalClearance(MM(0.5 if prio else 0.3))
    z.SetThermalReliefGap(MM(0.5)); z.SetThermalReliefSpokeWidth(MM(0.8))
    z.SetZoneName(name or f"{net.GetNetname()}_{layer}")
    board.Add(z); return z

def add_rule_area(board, rect, layers):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True); z.SetDoNotAllowCopperPour(True); z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True)
    z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET()
    for L in layers: ls.addLayer(L)
    z.SetLayerSet(ls)
    ol = z.Outline(); ol.NewOutline()
    x1, y1, x2, y2 = rect
    for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
        ol.Append(MM(x), MM(y))
    z.SetZoneName("isolation_barrier_keepout"); board.Add(z); return z

def add_edge_rect(board, x1, y1, x2, y2):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_RECT); s.SetStart(V(x1, y1)); s.SetEnd(V(x2, y2))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); board.Add(s); return s

def add_text(board, txt, x, y, layer=pcbnew.F_SilkS, size=2.0, thick=0.3, rot=0):
    t = pcbnew.PCB_TEXT(board); t.SetText(txt); t.SetPosition(V(x, y)); t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size))); t.SetTextThickness(MM(thick)); t.SetTextAngleDegrees(rot)
    board.Add(t); return t

def add_line(board, x1, y1, x2, y2, layer, w=0.3):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(V(x1, y1)); s.SetEnd(V(x2, y2))
    s.SetLayer(layer); s.SetWidth(MM(w)); board.Add(s); return s

def set_severities(ds):
    ignore = ["DRCE_OVERLAPPING_SILK", "DRCE_SILK_CLEARANCE", "DRCE_SILK_EDGE_CLEARANCE", "DRCE_LIB_FOOTPRINT_ISSUES",
              "DRCE_LIB_FOOTPRINT_MISMATCH", "DRCE_SILK_MASK_CLEARANCE"]
    warn = ["DRCE_STARVED_THERMAL", "DRCE_DANGLING_TRACK", "DRCE_ISOLATED_COPPER", "DRCE_COPPER_SLIVER"]
    try:
        for n in ignore:
            if hasattr(pcbnew, n):
                ds.m_DRCSeverities[getattr(pcbnew, n)] = pcbnew.RPT_SEVERITY_IGNORE
        for n in warn:
            if hasattr(pcbnew, n):
                ds.m_DRCSeverities[getattr(pcbnew, n)] = pcbnew.RPT_SEVERITY_WARNING
    except Exception as e:
        print("severity setup:", e)


# --------------------------------------------------------------------------
def build_board(comps, uuids):
    board = pcbnew.CreateEmptyBoard()
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(4)
    ds.m_MinClearance = MM(0.2); ds.m_TrackMinWidth = MM(0.2); ds.m_ViasMinSize = MM(0.5); ds.m_ViasMinAnnularWidth = MM(0.15)
    ds.m_CopperEdgeClearance = MM(0.5); ds.m_HoleClearance = MM(0.25); ds.m_HoleToHoleMin = MM(0.25); ds.m_MinThroughDrill = MM(0.3)
    try:
        ds.SetBoardThickness(MM(2.0))
    except Exception:
        pass
    board.SetLayerName(pcbnew.In1_Cu, "In1.Cu"); board.SetLayerName(pcbnew.In2_Cu, "In2.Cu")
    set_severities(ds)
    # outline + slots under the SIP-7 bias modules (creepage) + mounting
    add_edge_rect(board, 0, 0, BW, BH)
    slots = []
    for q in range(4):
        y = 12 + 10 * q
        add_edge_rect(board, 130.5, y - 4, 132.1, y + 4); slots.append((130.5, y - 4, 132.1, y + 4))
    # nets
    nets = {}
    for net in sorted(D.nets_of(comps)):
        if net.startswith("NC_"):
            continue
        ni = pcbnew.NETINFO_ITEM(board, net); board.Add(ni); nets[net] = ni
    # footprints
    fps = {}
    for c in comps:
        if c.ref not in PL:
            raise SystemExit(f"no placement for {c.ref}")
        fp = pcbnew.FootprintLoad(LIBDIR, c.footprint)
        if fp is None:
            raise SystemExit(f"footprint {c.footprint} not found")
        x, y, rot = PL[c.ref]
        fp.SetReference(c.ref); fp.SetValue(c.value)
        fp.SetPosition(V(x, y)); fp.SetOrientationDegrees(rot)
        sheet_uuid, sym_uuid = uuids["symbols"][c.ref]
        fp.SetPath(pcbnew.KIID_PATH(f"/{sheet_uuid}/{sym_uuid}"))
        fp.Value().SetVisible(False)
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.9), MM(0.9))); fp.Reference().SetTextThickness(MM(0.15))
        for pad in fp.Pads():
            net = c.pins.get(pad.GetNumber())
            if net and not net.startswith("NC_"):
                pad.SetNet(nets[net])
        board.Add(fp); fps[c.ref] = fp
    # pours
    for net, layer, rects, prio, conn in ZONES:
        for k, r in enumerate(rects):
            add_zone(board, nets[net], layer, r, prio, conn, name=f"{net}_{layer}_{k}")
    for rct in KEEPOUT_RECTS:
        add_rule_area(board, rct, [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu])
    for net, layer, x1, y1, x2, y2, w in TRACKS:
        add_track(board, nets[net], layer, x1, y1, x2, y2, w)
    # texts
    add_text(board, "SiC ZVS PHASE-SHIFTED FULL BRIDGE  3 kW  400 V -> 48 V", 70, 190, size=2.5, thick=0.4)
    add_text(board, "DANGER: PRIMARY SIDE 420 VDC", 70, 185, size=2.0, thick=0.35)
    add_text(board, "ISOLATION BARRIER - NO COPPER", BAR_X, 190, size=1.2, thick=0.2, rot=90)
    add_text(board, "SECONDARY 48 V / 62.5 A", 200, 192, size=2.0, thick=0.35)
    add_text(board, "rev A  2026-10  open hardware", 200, 196, size=1.2, thick=0.2)
    add_line(board, BAR_X, 2, BAR_X, BH - 2, pcbnew.Dwgs_User, 0.2)
    add_text(board, "PRIMARY", 118, 190, layer=pcbnew.Dwgs_User, size=1.5, thick=0.2, rot=90)
    add_text(board, "SECONDARY", 142, 190, layer=pcbnew.Dwgs_User, size=1.5, thick=0.2, rot=90)
    return board, nets, fps, slots

# --------------------------------------------------------------------------
def pad_info(board):
    """List of (ref, number, net, Rect, layers, (cx, cy), is_tht, is_npth, (fx, fy))."""
    out = []
    for fp in board.GetFootprints():
        fx, fy = pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            r = Rect(pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))
            layers = set()
            if pad.IsOnLayer(pcbnew.F_Cu): layers.add(F)
            if pad.IsOnLayer(pcbnew.B_Cu): layers.add(B)
            npth = pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH
            tht = pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH
            c = (pcbnew.ToMM(pad.GetPosition().x), pcbnew.ToMM(pad.GetPosition().y))
            out.append((fp.GetReference(), pad.GetNumber(), pad.GetNetname(), r, layers if not npth else {F, B}, c, tht, npth, (fx, fy)))
    return out

def in_rects(x, y, rects):
    return any(x1 <= x <= x2 and y1 <= y <= y2 for (x1, y1, x2, y2) in rects)

def stitch_vias(board, nets, pads, router, extra_occupied=()):
    """Through vias for SMD pads on plane nets (connect to In1/In2)."""
    occupied = [p[3] for p in pads] + list(extra_occupied)
    placed = []
    def free(x, y, r=0.45):
        rr = Rect(x - r, y - r, x + r, y + r)
        for o in occupied:
            if not (rr.x2 < o.x1 - 0.25 or rr.x1 > o.x2 + 0.25 or rr.y2 < o.y1 - 0.25 or rr.y1 > o.y2 + 0.25):
                return False
        if BARRIER[0] - 0.6 < x < BARRIER[1] + 0.6 and y > PS_Y_END - 1:
            return False
        if 127.8 < x < 134.8 and y <= PS_Y_END:
            return False
        return True
    count = 0
    for ref, num, net, r, layers, (cx, cy), tht, npth, (fx, fy) in pads:
        if tht or npth or net not in PLANE_NETS or ref in FANOUT:
            continue
        w, h = r.x2 - r.x1, r.y2 - r.y1
        if w >= 5 and h >= 5:                    # large pad (shunt): row of 3 vias just outside the pad
            dx = 1 if cx > fx else -1
            cands = [((cx + dx * (w / 2 + 0.8)), cy + k) for k in (-2, 0, 2)]
        else:
            vert = abs(cy - fy) > abs(cx - fx)
            d = 0.95
            if vert:
                cands = [(cx + w / 2 + d, cy), (cx - w / 2 - d, cy), (cx, cy + (h / 2 + d) * (1 if cy >= fy else -1))]
            else:
                cands = [(cx, cy + h / 2 + d), (cx, cy - h / 2 - d), (cx + (w / 2 + d) * (1 if cx >= fx else -1), cy)]
        for (vx, vy) in cands:
            if not free(vx, vy):
                continue
            add_via(board, nets[net], vx, vy)
            add_track(board, nets[net], "F.Cu", cx, cy, vx, vy, min(0.6, max(0.3, min(w, h) - 0.1)))
            occupied.append(Rect(vx - 0.4, vy - 0.4, vx + 0.4, vy + 0.4))
            router.register_via(net, vx, vy)
            router.add_item(net, [F], Rect(min(cx, vx) - 0.3, min(cy, vy) - 0.3, max(cx, vx) + 0.3, max(cy, vy) + 0.3))
            placed.append((net, vx, vy)); count += 1
            if not (w >= 5 and h >= 5):
                break
    print(f"stitching vias: {count}")
    return placed

FANOUT = {"U1": (3.4, 5.8, 0.25), "U2": (2.2, 4.4, 0.3), "U3": (2.2, 4.4, 0.3), "U4": (1.8, 3.6, 0.3)}

def fanout_stubs(board, nets, pads, router):
    """
    Fan-out stubs for fine-pitch ICs: every pad gets a straight stub away from the body,
    alternating short/long so the stub ends sit on two columns outside the pad field.  The pad
    field itself (pads + short stubs) becomes a hard keepout, so no net can fence another one.
    """
    terminals = {}
    stub_rects = []
    cols = {}
    for ref, num, net, r, layers, (cx, cy), tht, npth, (fx, fy) in pads:
        if ref in FANOUT:
            cols.setdefault((ref, -1 if cx < fx else 1), []).append((cy, cx, num, net))
    for (ref, d), plist in cols.items():
        short, long_, w = FANOUT[ref]
        plist.sort()
        xs, ys = [], []
        for k, (cy, cx, num, net) in enumerate(plist):
            L = short if k % 2 == 0 else long_
            ex = cx + d * L
            if net:
                add_track(board, nets[net], "F.Cu", cx, cy, ex, cy, w)
                rr = Rect(min(cx, ex) - w / 2, cy - w / 2, max(cx, ex) + w / 2, cy + w / 2)
                router.add_item(net, [F], rr); stub_rects.append(rr)
                if net in PLANE_NETS:          # plane-net pad: via at the stub end instead of routing
                    vx = ex + d * 0.6
                    add_via(board, nets[net], vx, cy); router.register_via(net, vx, cy)
                    add_track(board, nets[net], "F.Cu", ex, cy, vx, cy, w)
                    stub_rects.append(Rect(vx - 0.5, cy - 0.5, vx + 0.5, cy + 0.5))
                else:
                    terminals[(ref, num)] = (ex, cy, {F})
            xs.append(cx); ys.append(cy)
        pad_half = max(abs(p[3].x2 - p[3].x1) for p in pads if p[0] == ref) / 2
        inner = min(xs) - d * pad_half if d < 0 else max(xs) + d * pad_half   # body side edge of the pad field
        outer = (min(xs) if d < 0 else max(xs)) + d * (short - 0.7)             # just inside the short stub ends
        x1, x2 = sorted((inner - d * 0.0, outer))
        router.keepouts.append(Rect(x1, min(ys) - 0.6, x2, max(ys) + 0.6))
        # corridor in front of the stub ends: horizontal moves only on F.Cu (prevents fencing)
        far = (min(xs) if d < 0 else max(xs)) + d * (long_ + 3.0)
        cx1, cx2 = sorted((outer, far))
        router.h_only.append(Rect(cx1, min(ys) - 1.0, cx2, max(ys) + 1.0))
    return terminals, stub_rects

# --------------------------------------------------------------------------
def route(board, nets, comps):
    pads = pad_info(board)
    router = Router(BW, BH, pair_clearance, track_width,
                    keepouts=KEEPOUT_RECTS + [(130.0, 12 + 10 * q - 4.5, 132.6, 12 + 10 * q + 4.5) for q in range(4)]
                             + [(x - 3.2, y - 3.2, x + 3.2, y + 3.2) for (x, y) in ((7, 7), (253, 7), (7, 193), (253, 193))])
    # static obstacles: pads
    for ref, num, net, r, layers, c, tht, npth, fc in pads:
        router.add_item(net if net else "", layers, r)
    # zone rectangles (non-GND fills) are obstacles on their layer
    for net, layer, rects, prio, conn in ZONES:
        if prio == 0:
            continue
        L = F if layer == "F.Cu" else (B if layer == "B.Cu" else None)
        if L is None:
            continue
        for rct in rects:
            router.add_item(net, [L], Rect(*rct))
    for net, layer, x1, y1, x2, y2, w in TRACKS:
        router.add_item(net, [F if layer == "F.Cu" else B], Rect(min(x1, x2) - w / 2, min(y1, y2) - w / 2, max(x1, x2) + w / 2, max(y1, y2) + w / 2))
    stubs, stub_rects = fanout_stubs(board, nets, pads, router)
    stitch_vias(board, nets, pads, router, extra_occupied=stub_rects)
    # private escape regions: only nets with a pad inside may route through (prevents fencing of fine-pitch pads)
    fp_nets = {}
    for ref, num, net, r, layers, c, tht, npth, fc in pads:
        if net:
            fp_nets.setdefault(ref, set()).add(net)
    for rct, refs in PRIVATE:
        allowed = set()
        for ref in refs:
            allowed |= fp_nets.get(ref, set())
        router.add_private(rct, allowed)
    # routing tasks
    netpads = {}
    for ref, num, net, r, layers, c, tht, npth, fc in pads:
        if net and not npth:
            netpads.setdefault(net, []).append((ref, num, c, layers, tht, r))
    zone_rects = {}
    for net, layer, rects, prio, conn in ZONES:
        L = F if layer == "F.Cu" else (B if layer == "B.Cu" else None)
        for rct in rects:
            zone_rects.setdefault(net, []).append((rct, L))
    tasks = []
    for net, plist in netpads.items():
        if net in ZONE_NETS or net in ("SNUB_A", "SNUB_B"):
            # pads not covered by a pour of this net and not through-hole-on-plane need a route into the pour
            uncovered = []
            for ref, num, c, layers, tht, r in plist:
                covered = any(x1 <= c[0] <= x2 and y1 <= c[1] <= y2 and (L in layers or (tht and L is None))
                              for (x1, y1, x2, y2), L in zone_rects.get(net, [])) \
                          or (net in PLANE_NETS)
                if net in ("SNUB_A", "SNUB_B"):
                    covered = True
                if not covered:
                    uncovered.append((ref, num, c, layers))
            for ref, num, c, layers in uncovered:
                # goal: nearest point inside the net's F.Cu pour
                best = None
                for (x1, y1, x2, y2), L in zone_rects.get(net, []):
                    if L is None:
                        continue
                    gx = min(max(c[0], x1 + 1), x2 - 1); gy = min(max(c[1], y1 + 1), y2 - 1)
                    d = abs(gx - c[0]) + abs(gy - c[1])
                    if best is None or d < best[0]:
                        best = (d, gx, gy, L)
                if best:
                    tasks.append((net, [(c[0], c[1], layers), (best[1], best[2], {best[3]})]))
            continue
        terms = []
        for ref, num, c, layers, tht, r in plist:
            if (ref, num) in stubs:
                terms.append(stubs[(ref, num)])
            else:
                terms.append((c[0], c[1], layers))
        tasks.append((net, terms))
    # route short nets first
    def span(t):
        xs = [p[0] for p in t[1]]; ys = [p[1] for p in t[1]]
        return (max(xs) - min(xs)) + (max(ys) - min(ys))
    prio = {"+12V": 0, "VDD_IC": 1, "VREF": 2}
    failed_prev = set()
    base_items = list(router.items)
    for npass in range(1, MAX_PASSES + 1):
        router.items = list(base_items); router.tracks_out = []; router.vias_out = []; router.failed = []
        tasks.sort(key=lambda t: (0 if t[0] in failed_prev else 1, prio.get(t[0], 10), span(t)))
        done = 0
        for net, terms in tasks:
            ok = router.route_net(net, terms)
            done += 1
            if not ok:
                print(f"  pass {npass} [{done}/{len(tasks)}] {net}: {len(terms)} terminals -> FAILED")
        failed_now = {f_[0] for f_ in router.failed}
        print(f"pass {npass}: {len(router.failed)} failed terminals in {len(failed_now)} nets")
        if not failed_now:
            break
        failed_prev = failed_now | failed_prev
    for net, L, x1, y1, x2, y2, w in router.tracks_out:
        add_track(board, nets[net], pcbnew.F_Cu if L == F else pcbnew.B_Cu, x1, y1, x2, y2, w)
    for net, x, y in router.vias_out:
        add_via(board, nets[net], x, y)
    print(f"routed tracks: {len(router.tracks_out)}, vias: {len(router.vias_out)}, failed terminals: {len(router.failed)}")
    for f_ in router.failed:
        print("   FAILED:", f_)
        print(router.debug_dump(f_[0], f_[1][0], f_[1][1], 3.0))
    return router.failed

# --------------------------------------------------------------------------
def drc(board, report):
    pcbnew.WriteDRCReport(board, report, pcbnew.EDA_UNITS_MILLIMETRES, True)
    txt = open(report).read()
    import re, collections
    kinds = collections.Counter(re.findall(r"^\[(\w+)\]", txt, re.M))
    errors = collections.Counter()
    for m in re.finditer(r"^\[(\w+)\].*?\n(?:.*?Severity: (\w+))?", txt, re.M):
        pass
    sev = collections.Counter(re.findall(r"Severity: (\w+)", txt))
    unconnected = re.search(r"Found (\d+) unconnected", txt)
    return kinds, sev, int(unconnected.group(1)) if unconnected else -1, txt

def main(do_route=True):
    comps = D.build()
    uuids = json.load(open(os.path.join(OUT, "uuids.json")))
    all_nets = [n for n in D.nets_of(comps) if not n.startswith("NC_")]
    write_dru(all_nets)
    board, nets, fps, slots = build_board(comps, uuids)
    pcbnew.SaveBoard(PCB, board)
    print("board placed & saved; reloading with project")
    sm = pcbnew.GetSettingsManager(); sm.LoadProject(PRO)
    board = pcbnew.LoadBoard(PCB)
    try:
        board.SetProject(sm.GetProject(PRO))
    except Exception as e:
        print("SetProject:", e)
    nets = {n: board.FindNet(n) for n in all_nets}
    failed = route(board, nets, comps) if do_route else []
    board.BuildConnectivity()
    filler = pcbnew.ZONE_FILLER(board); filler.Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board)
    print("zones filled, board saved. running DRC ...")
    rpt = os.path.join(OUT, "drc_report.txt")
    kinds, sev, unconnected, txt = drc(board, rpt)
    print("DRC summary:", dict(kinds)); print("severities:", dict(sev)); print("unconnected:", unconnected)
    return failed, kinds, unconnected

if __name__ == "__main__":
    main(do_route="--noroute" not in sys.argv)
