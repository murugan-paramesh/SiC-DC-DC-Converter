"""
Schematic symbol library generator -> hardware/kicad/lib/SiC_PSFB.kicad_sym

Every symbol used by the design is defined here, so the project is fully
self-contained (no dependency on the KiCad standard libraries).

Pin geometry convention (library coordinates, y up):
  side 'L' : pin on the left of the body, orientation 0
  side 'R' : pin on the right of the body, orientation 180
  side 'T' : pin on top, orientation 270
  side 'B' : pin on bottom, orientation 90
"""
from .sexpr import f, q, font

PIN_LEN = 2.54
GRID = 2.54


class Symbol:
    def __init__(self, name, ref_prefix, desc="", power=False, hide_pin_numbers=False, hide_pin_names=False):
        self.name = name
        self.ref = ref_prefix
        self.desc = desc
        self.power = power
        self.graphics = []     # raw s-expr strings (unit 0 = common graphics)
        self.pins = []         # dict(number, name, x, y, orient, type, hide)
        self.hide_pin_numbers = hide_pin_numbers
        self.hide_pin_names = hide_pin_names
        self.ref_pos = (0, 0)
        self.val_pos = (0, 0)

    # -- graphics helpers ---------------------------------------------------
    def rect(self, x1, y1, x2, y2, fill="background", width=0.254):
        self.graphics.append(
            f"(rectangle (start {f(x1)} {f(y1)}) (end {f(x2)} {f(y2)}) "
            f"(stroke (width {f(width)}) (type default)) (fill (type {fill})))")

    def poly(self, pts, fill="none", width=0.254):
        p = " ".join(f"(xy {f(x)} {f(y)})" for x, y in pts)
        self.graphics.append(f"(polyline (pts {p}) (stroke (width {f(width)}) (type default)) (fill (type {fill})))")

    def circle(self, cx, cy, r, fill="none", width=0.254):
        self.graphics.append(f"(circle (center {f(cx)} {f(cy)}) (radius {f(r)}) (stroke (width {f(width)}) (type default)) (fill (type {fill})))")

    def arc(self, s, m, e, width=0.254):
        self.graphics.append(
            f"(arc (start {f(s[0])} {f(s[1])}) (mid {f(m[0])} {f(m[1])}) (end {f(e[0])} {f(e[1])}) "
            f"(stroke (width {f(width)}) (type default)) (fill (type none)))")

    def text(self, t, x, y, size=1.27):
        self.graphics.append(f"(text {q(t)} (at {f(x)} {f(y)} 0) (effects (font (size {f(size)} {f(size)}))))")

    # -- pins ---------------------------------------------------------------
    def pin(self, number, name, x, y, orient, ptype="passive", hide=False, length=PIN_LEN):
        self.pins.append(dict(number=str(number), name=name, x=x, y=y, orient=orient, type=ptype, hide=hide, length=length))

    def pin_point(self, number):
        """Connection point of a pin in library coordinates."""
        for p in self.pins:
            if p["number"] == number:
                return p["x"], p["y"], p["orient"]
        raise KeyError(f"{self.name}: no pin {number}")

    # -- output -------------------------------------------------------------
    def sexpr(self, lib):
        name = f"{lib}:{self.name}" if lib else self.name
        hdr = f"(symbol {q(name)}"
        if self.power:
            hdr += " (power)"
        if self.hide_pin_numbers:
            hdr += " (pin_numbers hide)"
        hdr += " (pin_names (offset 0.508)"
        if self.hide_pin_names:
            hdr += " hide"
        hdr += ") (in_bom yes) (on_board yes)"
        lines = [hdr]
        rx, ry = self.ref_pos
        vx, vy = self.val_pos
        lines.append(f'  (property "Reference" {q(self.ref)} (at {f(rx)} {f(ry)} 0) {font(1.27, hide=self.power)})')
        lines.append(f'  (property "Value" {q(self.name)} (at {f(vx)} {f(vy)} 0) {font(1.27)})')
        lines.append(f'  (property "Footprint" "" (at 0 0 0) {font(1.27, hide=True)})')
        lines.append(f'  (property "Datasheet" "" (at 0 0 0) {font(1.27, hide=True)})')
        lines.append(f'  (property "ki_description" {q(self.desc)} (at 0 0 0) {font(1.27, hide=True)})')
        lines.append(f'  (symbol "{self.name}_0_1"')
        for g in self.graphics:
            lines.append("    " + g)
        lines.append("  )")
        lines.append(f'  (symbol "{self.name}_1_1"')
        for p in self.pins:
            hide = " hide" if p["hide"] else ""
            lines.append(
                f'    (pin {p["type"]} line (at {f(p["x"])} {f(p["y"])} {p["orient"]}) (length {f(p["length"])}){hide} '
                f'(name {q(p["name"])} {font(1.27)}) (number {q(p["number"])} {font(1.27)}))')
        lines.append("  )")
        lines.append(")")
        return "\n".join(lines)


def box_symbol(name, ref, left, right, top=(), bottom=(), desc="", width=None, pin_pitch=GRID):
    """
    Generic IC/box symbol.  left/right/top/bottom are lists of (number, name, type).
    Pins are placed on the grid; the body is sized automatically.
    """
    s = Symbol(name, ref, desc)
    n_side = max(len(left), len(right), 1)
    h = (n_side + 1) * pin_pitch
    w = width or max(15.24, (max(len(top), len(bottom), 1) + 1) * pin_pitch)
    w = round(w / GRID) * GRID
    hh, hw = h / 2, w / 2
    s.rect(-hw, -hh, hw, hh)
    for i, (num, nm, tp) in enumerate(left):
        y = hh - (i + 1) * pin_pitch
        s.pin(num, nm, -hw - PIN_LEN, y, 0, tp)
    for i, (num, nm, tp) in enumerate(right):
        y = hh - (i + 1) * pin_pitch
        s.pin(num, nm, hw + PIN_LEN, y, 180, tp)
    for i, (num, nm, tp) in enumerate(top):
        x = -hw + (i + 1) * pin_pitch if len(top) > 1 else 0
        s.pin(num, nm, x, hh + PIN_LEN, 270, tp)
    for i, (num, nm, tp) in enumerate(bottom):
        x = -hw + (i + 1) * pin_pitch if len(bottom) > 1 else 0
        s.pin(num, nm, x, -hh - PIN_LEN, 90, tp)
    s.ref_pos = (-hw, hh + 1.27)
    s.val_pos = (-hw, -hh - 1.27)
    return s


def build_library():
    syms = []

    # ---- passives --------------------------------------------------------
    r = Symbol("R", "R", "Resistor", hide_pin_numbers=True, hide_pin_names=True)
    r.rect(-1.016, -2.54, 1.016, 2.54, fill="none")
    r.pin(1, "~", 0, 5.08, 270); r.pin(2, "~", 0, -5.08, 90)
    r.ref_pos, r.val_pos = (2.54, 1.27), (2.54, -1.27)
    syms.append(r)

    c = Symbol("C", "C", "Capacitor (unpolarised)", hide_pin_numbers=True, hide_pin_names=True)
    c.poly([(-2.032, 0.762), (2.032, 0.762)], width=0.508)
    c.poly([(-2.032, -0.762), (2.032, -0.762)], width=0.508)
    c.pin(1, "~", 0, 3.81, 270, length=3.048); c.pin(2, "~", 0, -3.81, 90, length=3.048)
    c.ref_pos, c.val_pos = (2.54, 1.27), (2.54, -1.27)
    syms.append(c)

    cp = Symbol("C_POL", "C", "Capacitor, polarised (electrolytic)", hide_pin_numbers=True, hide_pin_names=True)
    cp.poly([(-2.032, 0.762), (2.032, 0.762)], width=0.508)
    cp.arc((-2.032, -1.27), (0, -0.508), (2.032, -1.27), width=0.508)
    cp.poly([(-2.54, 1.778), (-1.524, 1.778)], width=0.254)
    cp.poly([(-2.032, 1.27), (-2.032, 2.286)], width=0.254)
    cp.pin(1, "+", 0, 3.81, 270, length=3.048); cp.pin(2, "-", 0, -3.81, 90, length=3.048)
    cp.ref_pos, cp.val_pos = (2.54, 1.27), (2.54, -1.27)
    syms.append(cp)

    l = Symbol("L", "L", "Inductor", hide_pin_numbers=True, hide_pin_names=True)
    for k in range(4):
        y0 = 2.54 - k * 1.27
        l.arc((0, y0), (0.635, y0 - 0.635), (0, y0 - 1.27))
    l.pin(1, "~", 0, 5.08, 270); l.pin(2, "~", 0, -5.08, 90)
    l.ref_pos, l.val_pos = (2.54, 1.27), (2.54, -1.27)
    syms.append(l)

    def diode(name, desc, schottky=False, zener=False, led=False):
        d = Symbol(name, "D", desc, hide_pin_numbers=True, hide_pin_names=True)
        d.poly([(-1.27, -1.27), (1.27, -1.27), (0, 1.27), (-1.27, -1.27)], fill="none")   # triangle pointing up (A bottom -> K top)
        if schottky:
            d.poly([(-1.905, 0.635), (-1.905, 1.27), (-1.27, 1.27), (1.27, 1.27), (1.905, 1.27), (1.905, 1.905)])
        elif zener:
            d.poly([(-1.27, 1.27), (1.27, 1.27), (1.905, 1.905)])
        else:
            d.poly([(-1.27, 1.27), (1.27, 1.27)])
        if led:
            d.poly([(1.27, 0.635), (2.54, 1.905)]); d.poly([(1.905, 1.905), (2.54, 1.905), (2.54, 1.27)])
            d.poly([(2.032, -0.127), (3.302, 1.143)]); d.poly([(2.667, 1.143), (3.302, 1.143), (3.302, 0.508)])
        d.pin(1, "K", 0, 3.81, 270); d.pin(2, "A", 0, -3.81, 90)
        d.ref_pos, d.val_pos = (2.54, 1.27), (2.54, -1.27)
        return d
    syms += [diode("D", "Diode"), diode("D_SCHOTTKY", "Schottky diode", schottky=True),
             diode("D_TVS", "TVS diode (unidirectional)", zener=True), diode("LED", "LED", led=True)]

    bav = Symbol("BAV99", "D", "BAV99 dual series diode, SOT-23 (1=A1, 2=K2, 3=K1/A2)")
    bav.rect(-5.08, -3.81, 5.08, 3.81, fill="none")
    # two diodes in series from pin1 -> pin3 -> pin2, drawn horizontally
    bav.poly([(-3.81, 1.27), (-3.81, -1.27), (-1.27, 0), (-3.81, 1.27)]); bav.poly([(-1.27, 1.27), (-1.27, -1.27)])
    bav.poly([(1.27, 1.27), (1.27, -1.27), (3.81, 0), (1.27, 1.27)]); bav.poly([(3.81, 1.27), (3.81, -1.27)])
    bav.poly([(-5.08, 0), (-3.81, 0)]); bav.poly([(-1.27, 0), (1.27, 0)]); bav.poly([(3.81, 0), (5.08, 0)])
    bav.poly([(0, 0), (0, -3.81)])
    bav.pin(1, "A1", -7.62, 0, 0); bav.pin(2, "K2", 7.62, 0, 180); bav.pin(3, "K1A2", 0, -6.35, 90)
    bav.ref_pos, bav.val_pos = (-5.08, 5.08), (-5.08, -5.08)
    syms.append(bav)

    fu = Symbol("FUSE", "F", "Fuse", hide_pin_numbers=True, hide_pin_names=True)
    fu.rect(-1.016, -2.54, 1.016, 2.54, fill="none"); fu.poly([(0, 2.54), (0, -2.54)])
    fu.pin(1, "~", 0, 5.08, 270); fu.pin(2, "~", 0, -5.08, 90)
    fu.ref_pos, fu.val_pos = (2.54, 1.27), (2.54, -1.27)
    syms.append(fu)

    # ---- transistors -----------------------------------------------------
    def nmos(name, desc, kelvin):
        m = Symbol(name, "Q", desc)
        # body: vertical channel line, gate plate, drain top, source bottom
        m.poly([(-1.27, 1.905), (-1.27, -1.905)], width=0.254)          # gate plate
        m.poly([(-0.508, 2.54), (-0.508, -2.54)], width=0.508)         # channel
        m.poly([(-0.508, 1.905), (1.905, 1.905), (1.905, 5.08)])       # drain
        m.poly([(-0.508, -1.905), (1.905, -1.905), (1.905, -5.08)])    # source
        m.poly([(-0.508, 0), (1.905, 0), (1.905, -1.905)])             # body contact
        m.poly([(0.254, 0.635), (0.254, -0.635), (1.27, 0), (0.254, 0.635)], fill="outline")  # arrow
        m.circle(0.635, 0, 3.3)
        # body diode
        m.poly([(3.175, 0.762), (4.445, 0.762), (3.81, -0.508), (3.175, 0.762)]); m.poly([(3.175, -0.508), (4.445, -0.508)])
        m.poly([(1.905, 1.905), (3.81, 1.905), (3.81, 0.762)]); m.poly([(1.905, -1.905), (3.81, -1.905), (3.81, -0.508)])
        m.pin(1, "G", -5.08, 0, 0); m.pin(2, "D", 1.905, 7.62, 270); 
        if kelvin:
            m.pin(3, "KS", 7.62, -2.54, 180, length=2.54); m.poly([(5.08, -2.54), (4.445, -2.54), (1.905, -3.175)])
            m.pin(4, "S", 1.905, -7.62, 90)
        else:
            m.pin(3, "S", 1.905, -7.62, 90)
        m.ref_pos, m.val_pos = (5.08, 5.08), (5.08, 3.175)
        return m
    syms += [nmos("Q_NMOS_KELVIN", "SiC N-MOSFET with Kelvin source (TO-247-4): 1=G 2=D 3=KS 4=S", True),
             nmos("Q_NMOS", "N-MOSFET: 1=G 2=D 3=S", False)]

    # ---- magnetics -------------------------------------------------------
    t = Symbol("T_PSFB", "T", "PSFB main transformer 18:3:3, centre-tapped secondary")
    for y0 in (5.08, 2.54, 0, -2.54):           # primary coils
        t.arc((-2.54, y0 + 1.27), (-1.905, y0 + 0.635), (-2.54, y0))
        t.arc((-2.54, y0), (-1.905, y0 - 0.635), (-2.54, y0 - 1.27))
    for y0 in (5.08, 2.54, 0, -2.54):           # secondary coils
        t.arc((2.54, y0 + 1.27), (1.905, y0 + 0.635), (2.54, y0))
        t.arc((2.54, y0), (1.905, y0 - 0.635), (2.54, y0 - 1.27))
    t.poly([(-0.508, 7.62), (-0.508, -7.62)], width=0.254); t.poly([(0.508, 7.62), (0.508, -7.62)], width=0.254)
    t.poly([(-2.54, 6.35), (-5.08, 6.35)]); t.poly([(-2.54, -3.81), (-5.08, -3.81)])
    t.poly([(2.54, 6.35), (5.08, 6.35)]); t.poly([(2.54, 1.27), (5.08, 1.27)]); t.poly([(2.54, -3.81), (5.08, -3.81)])
    t.circle(-3.81, 7.62, 0.381, fill="outline"); t.circle(3.81, 7.62, 0.381, fill="outline"); t.circle(3.81, 0, 0.381, fill="outline")
    t.text("Np=18", -6.35, 0); t.text("3+3", 6.35, -1.27)
    t.pin(1, "P+", -7.62, 6.35, 0); t.pin(2, "P-", -7.62, -3.81, 0)
    t.pin(3, "S1", 7.62, 6.35, 180); t.pin(4, "CT", 7.62, 1.27, 180); t.pin(5, "S2", 7.62, -3.81, 180)
    t.ref_pos, t.val_pos = (-7.62, 10.16), (-7.62, -10.16)
    syms.append(t)

    ct = Symbol("CT_1_100", "T", "Current transformer 1:100 (primary = 1 turn flying lead through toroid)")
    ct.poly([(-2.54, 3.81), (-2.54, -3.81)], width=0.762)
    for y0 in (3.81, 1.27, -1.27):
        ct.arc((2.54, y0), (1.905, y0 - 0.635), (2.54, y0 - 1.27)); ct.arc((2.54, y0 - 1.27), (1.905, y0 - 1.905), (2.54, y0 - 2.54))
    ct.poly([(-0.508, 5.08), (-0.508, -5.08)], width=0.254); ct.poly([(0.508, 5.08), (0.508, -5.08)], width=0.254)
    ct.poly([(-2.54, 3.81), (-5.08, 3.81)]); ct.poly([(-2.54, -3.81), (-5.08, -3.81)])
    ct.poly([(2.54, 3.81), (5.08, 3.81)]); ct.poly([(2.54, -3.81), (5.08, -3.81)])
    ct.text("1:100", 0, 6.985)
    ct.pin(1, "P+", -7.62, 3.81, 0); ct.pin(2, "P-", -7.62, -3.81, 0)
    ct.pin(3, "S+", 7.62, 3.81, 180); ct.pin(4, "S-", 7.62, -3.81, 180)
    ct.ref_pos, ct.val_pos = (-7.62, 8.89), (-7.62, -8.89)
    syms.append(ct)

    # ---- ICs ---------------------------------------------------------------
    syms.append(box_symbol(
        "UCC28951", "U",
        left=[("23", "VDD", "power_in"), ("1", "VREF", "power_out"), ("2", "EA+", "input"), ("3", "EA-", "input"),
              ("4", "COMP", "output"), ("5", "SS/EN", "input"), ("15", "CS", "input"), ("16", "SYNC", "bidirectional"),
              ("10", "RT", "passive"), ("11", "RSUM", "passive"), ("12", "DCM", "passive"), ("24", "GND", "power_in")],
        right=[("22", "OUTA", "output"), ("21", "OUTB", "output"), ("20", "OUTC", "output"), ("19", "OUTD", "output"),
               ("18", "OUTE", "output"), ("17", "OUTF", "output"), ("6", "DELAB", "passive"), ("7", "DELCD", "passive"),
               ("8", "DELEF", "passive"), ("9", "TMIN", "passive"), ("14", "ADEL", "passive"), ("13", "ADELEF", "passive")],
        desc="UCC28951 phase-shifted full-bridge controller with SR outputs, TSSOP-24", width=25.4))

    syms.append(box_symbol(
        "UCC21520", "U",
        left=[("1", "INA", "input"), ("2", "INB", "input"), ("3", "VCCI", "power_in"), ("8", "VCCI", "passive"),
              ("4", "GND", "power_in"), ("5", "DIS", "input"), ("6", "DT", "passive"), ("7", "NC", "no_connect")],
        right=[("14", "VDDA", "power_in"), ("15", "OUTA", "output"), ("16", "VSSA", "power_in"), ("12", "NC", "no_connect"),
               ("11", "VDDB", "power_in"), ("10", "OUTB", "output"), ("9", "VSSB", "power_in"), ("13", "NC", "no_connect")],
        desc="UCC21520 5.7 kVrms isolated dual gate driver, SOIC-16W", width=20.32))

    syms.append(box_symbol(
        "UCC27524", "U",
        left=[("2", "INA", "input"), ("4", "INB", "input"), ("8", "ENA", "input"), ("1", "ENB", "input"), ("3", "GND", "power_in")],
        right=[("6", "VDD", "power_in"), ("7", "OUTA", "output"), ("5", "OUTB", "output")],
        desc="UCC27524 dual 5 A low-side gate driver, SOIC-8", width=17.78))

    syms.append(box_symbol(
        "R12P21503D", "PS",
        left=[("1", "+VIN", "power_in"), ("2", "-VIN", "power_in")],
        right=[("7", "+VOUT", "power_out"), ("6", "COM", "power_out"), ("5", "-VOUT", "power_out")],
        desc="RECOM R12P21503D 2 W isolated gate-drive supply, 12 V in, +15 V / -3 V out, SIP-7", width=20.32))

    # ---- connectors / misc -------------------------------------------------
    def conn(name, npins, desc):
        s = Symbol(name, "J", desc, hide_pin_names=True)
        h = (npins + 1) * GRID
        s.rect(-2.54, -h / 2, 2.54, h / 2)
        for i in range(npins):
            y = h / 2 - (i + 1) * GRID
            s.pin(i + 1, f"Pin_{i+1}", -5.08, y, 0)
            s.rect(-2.54, y - 0.508, -1.524, y + 0.508, fill="none", width=0.1524)
        s.ref_pos, s.val_pos = (-2.54, h / 2 + 1.27), (-2.54, -h / 2 - 1.27)
        return s
    syms += [conn("CONN_1x02", 2, "2-pin connector"), conn("CONN_1x08", 8, "8-pin header")]

    lug = Symbol("LUG", "J", "Bolt-down power terminal (ring lug)", hide_pin_names=True)
    lug.circle(0, -2.54, 1.524, fill="none", width=0.381); lug.poly([(0, -1.016), (0, -0)])
    lug.pin(1, "1", 0, 2.54, 270)
    lug.ref_pos, lug.val_pos = (2.54, -1.27), (2.54, -3.81)
    syms.append(lug)

    tp = Symbol("TP", "TP", "Test point", hide_pin_names=True, hide_pin_numbers=True)
    tp.circle(0, -1.27, 0.762, fill="none", width=0.254); tp.poly([(0, -0.508), (0, 0)])
    tp.pin(1, "1", 0, 2.54, 270)
    tp.ref_pos, tp.val_pos = (1.27, -1.27), (1.27, -3.81)
    syms.append(tp)

    mh = Symbol("MOUNTING_HOLE", "H", "Mounting hole (no electrical connection)", hide_pin_names=True, hide_pin_numbers=True)
    mh.circle(0, 0, 1.27, fill="none", width=0.381); mh.circle(0, 0, 0.635, fill="none", width=0.254)
    mh.ref_pos, mh.val_pos = (2.54, 1.27), (2.54, -1.27)
    syms.append(mh)

    # ---- power symbols -----------------------------------------------------
    def gnd(name):
        s = Symbol(name, "#PWR", f"Power symbol {name}", power=True, hide_pin_names=True, hide_pin_numbers=True)
        s.poly([(0, 0), (0, -1.27)]); s.poly([(-1.27, -1.27), (1.27, -1.27)]); s.poly([(-0.635, -1.905), (0.635, -1.905)]); s.poly([(-0.254, -2.54), (0.254, -2.54)])
        s.pin(1, name, 0, 0, 270, "power_in", hide=True, length=0)
        s.ref_pos, s.val_pos = (0, -5.08), (0, -3.81)
        return s

    def vcc(name):
        s = Symbol(name, "#PWR", f"Power symbol {name}", power=True, hide_pin_names=True, hide_pin_numbers=True)
        s.poly([(0, 0), (0, 1.27)]); s.poly([(-1.27, 1.27), (1.27, 1.27)], width=0.381)
        s.pin(1, name, 0, 0, 90, "power_in", hide=True, length=0)
        s.ref_pos, s.val_pos = (0, -1.27), (0, 2.54)
        return s
    syms += [gnd("PGND"), gnd("SGND"), vcc("VBUS"), vcc("VOUT"), vcc("+12V"), vcc("VREF")]
    return {s.name: s for s in syms}


def write_library(path, lib="SiC_PSFB"):
    syms = build_library()
    out = ['(kicad_symbol_lib (version 20220914) (generator SiC_PSFB_generator)']
    for s in syms.values():
        out.append(s.sexpr(None))
    out.append(")")
    with open(path, "w") as fh:
        fh.write("\n".join(out) + "\n")
    return syms


def lib_symbols_block(syms, names, lib="SiC_PSFB"):
    """The (lib_symbols ...) block embedded in a schematic for the given symbol names."""
    out = ["  (lib_symbols"]
    for n in sorted(set(names)):
        body = syms[n].sexpr(lib)
        out.append("\n".join("    " + ln for ln in body.splitlines()))
    out.append("  )")
    return "\n".join(out)
