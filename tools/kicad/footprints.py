"""
Footprint library generator -> hardware/kicad/lib/SiC_PSFB.pretty/*.kicad_mod

All footprints are generated here so the project has no external library
dependencies.  Dimensions follow IPC-7351 nominal density for SMD parts and
the manufacturer drawings for the through-hole parts; large custom magnetics
footprints are documented in docs/06_magnetics_design.md.
"""
import os
from .sexpr import f, q, uid


class Footprint:
    def __init__(self, name, desc="", smd=True, tags=""):
        self.name, self.desc, self.smd, self.tags = name, desc, smd, tags
        self.items = []
        self.pads = []          # (number, x, y) for routing helpers

    def line(self, x1, y1, x2, y2, layer="F.SilkS", w=0.12):
        self.items.append(f'(fp_line (start {f(x1)} {f(y1)}) (end {f(x2)} {f(y2)}) (stroke (width {f(w)}) (type solid)) (layer {q(layer)}) (tstamp {uid()}))')

    def rect(self, x1, y1, x2, y2, layer="F.CrtYd", w=0.05):
        self.items.append(f'(fp_rect (start {f(x1)} {f(y1)}) (end {f(x2)} {f(y2)}) (stroke (width {f(w)}) (type solid)) (fill none) (layer {q(layer)}) (tstamp {uid()}))')

    def circle(self, cx, cy, r, layer="F.SilkS", w=0.12):
        self.items.append(f'(fp_circle (center {f(cx)} {f(cy)}) (end {f(cx + r)} {f(cy)}) (stroke (width {f(w)}) (type solid)) (fill none) (layer {q(layer)}) (tstamp {uid()}))')

    def text(self, t, x, y, layer="F.Fab", size=1.0):
        self.items.append(f'(fp_text user {q(t)} (at {f(x)} {f(y)}) (layer {q(layer)}) (effects (font (size {f(size)} {f(size)}) (thickness 0.15))) (tstamp {uid()}))')

    def smd_pad(self, num, x, y, w, h, shape="roundrect", ratio=0.25):
        extra = f" (roundrect_rratio {f(ratio)})" if shape == "roundrect" else ""
        self.items.append(f'(pad {q(num)} smd {shape} (at {f(x)} {f(y)}) (size {f(w)} {f(h)}) (layers "F.Cu" "F.Paste" "F.Mask"){extra} (tstamp {uid()}))')
        self.pads.append((str(num), x, y))

    def th_pad(self, num, x, y, dia, drill, shape="circle", h=None, square=False):
        if square:
            shape = "rect"
        size = f"{f(dia)} {f(h if h else dia)}"
        drl = f"(drill {f(drill)})" if not isinstance(drill, tuple) else f"(drill oval {f(drill[0])} {f(drill[1])})"
        self.items.append(f'(pad {q(num)} thru_hole {shape} (at {f(x)} {f(y)}) (size {size}) {drl} (layers "*.Cu" "*.Mask") (tstamp {uid()}))')
        self.pads.append((str(num), x, y))

    def npth(self, x, y, drill):
        self.items.append(f'(pad "" np_thru_hole circle (at {f(x)} {f(y)}) (size {f(drill)} {f(drill)}) (drill {f(drill)}) (layers "*.Cu" "*.Mask") (tstamp {uid()}))')

    def sexpr(self):
        attr = "smd" if self.smd else "through_hole"
        out = [f'(footprint {q(self.name)} (version 20221018) (generator SiC_PSFB_generator) (layer "F.Cu")',
               f'  (descr {q(self.desc)})', f'  (tags {q(self.tags)})', f'  (attr {attr})',
               f'  (fp_text reference "REF**" (at 0 -1) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))) (tstamp {uid()}))',
               f'  (fp_text value {q(self.name)} (at 0 1) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))) (tstamp {uid()}))']
        out += ["  " + i for i in self.items]
        out.append(")")
        return "\n".join(out)


# ---------------------------------------------------------------------------
def chip(name, L, W, pad_w, pad_h, pitch, desc):
    fp = Footprint(name, desc, tags="chip")
    fp.smd_pad(1, -pitch / 2, 0, pad_w, pad_h); fp.smd_pad(2, pitch / 2, 0, pad_w, pad_h)
    fp.rect(-L / 2, -W / 2, L / 2, W / 2, layer="F.Fab", w=0.1)
    cy = max(W / 2, pad_h / 2) + 0.25; cx = pitch / 2 + pad_w / 2 + 0.25
    fp.rect(-cx, -cy, cx, cy)
    gap = pitch / 2 - pad_w / 2 - 0.3
    if gap > 0.4:
        fp.line(-gap, -W / 2 - 0.1, gap, -W / 2 - 0.1); fp.line(-gap, W / 2 + 0.1, gap, W / 2 + 0.1)
    return fp


def soic(name, npins, pitch, body_w, body_l, pad_span, pad_w, pad_h, desc):
    fp = Footprint(name, desc, tags="soic")
    n2 = npins // 2
    for i in range(n2):
        y = (i - (n2 - 1) / 2) * pitch
        fp.smd_pad(i + 1, -pad_span / 2, y, pad_w, pad_h)
        fp.smd_pad(npins - i, pad_span / 2, y, pad_w, pad_h)
    fp.rect(-body_w / 2, -body_l / 2, body_w / 2, body_l / 2, layer="F.Fab", w=0.1)
    cx = pad_span / 2 + pad_w / 2 + 0.3; cy = body_l / 2 + 0.3
    fp.rect(-cx, -cy, cx, cy)
    fp.line(-body_w / 2, -body_l / 2 - 0.2, body_w / 2, -body_l / 2 - 0.2); fp.line(-body_w / 2, body_l / 2 + 0.2, body_w / 2, body_l / 2 + 0.2)
    fp.circle(-pad_span / 2 - pad_w / 2 - 0.6, -(n2 - 1) / 2 * pitch, 0.25)   # pin 1 marker
    return fp


def dip_th(name, npins, pitch, row, drill, pad, body_w, body_l, desc, square1=True):
    fp = Footprint(name, desc, smd=False)
    n2 = npins // 2
    for i in range(n2):
        y = (i - (n2 - 1) / 2) * pitch
        fp.th_pad(i + 1, -row / 2, y, pad, drill, square=(square1 and i == 0))
        fp.th_pad(npins - i, row / 2, y, pad, drill)
    fp.rect(-body_w / 2, -body_l / 2, body_w / 2, body_l / 2, layer="F.Fab", w=0.1)
    fp.rect(-body_w / 2 - 0.5, -body_l / 2 - 0.5, body_w / 2 + 0.5, body_l / 2 + 0.5)
    fp.rect(-body_w / 2, -body_l / 2, body_w / 2, body_l / 2, layer="F.SilkS", w=0.12)
    return fp


def build_library():
    fps = []
    # SMD chips
    fps.append(chip("R_0603", 1.6, 0.8, 0.9, 0.95, 1.6, "Resistor 0603 (1608 metric)"))
    fps.append(chip("C_0603", 1.6, 0.8, 0.9, 0.95, 1.6, "Capacitor 0603 (1608 metric)"))
    fps.append(chip("R_0805", 2.0, 1.25, 1.0, 1.45, 1.9, "Resistor 0805 (2012 metric)"))
    fps.append(chip("C_0805", 2.0, 1.25, 1.0, 1.45, 1.9, "Capacitor 0805 (2012 metric)"))
    fps.append(chip("R_1206", 3.2, 1.6, 1.15, 1.8, 2.8, "Resistor 1206 (3216 metric)"))
    fps.append(chip("C_1206", 3.2, 1.6, 1.15, 1.8, 2.8, "Capacitor 1206 (3216 metric)"))
    fps.append(chip("C_1210", 3.2, 2.5, 1.15, 2.7, 2.8, "Capacitor 1210 (3225 metric)"))
    fps.append(chip("R_2512", 6.3, 3.2, 1.5, 3.5, 5.6, "Resistor 2512 (6332 metric), 2 W"))
    fps.append(chip("C_2220", 5.7, 5.0, 1.6, 5.2, 5.0, "Capacitor 2220 (5750 metric), 630 V MLCC"))
    fps.append(chip("LED_0805", 2.0, 1.25, 1.0, 1.45, 1.9, "LED 0805"))

    d = chip("D_SOD-123", 2.7, 1.6, 1.0, 1.2, 3.2, "SOD-123 diode, pad 1 = cathode")
    d.line(-0.9, -0.9, -0.9, 0.9, w=0.3)   # cathode bar
    fps.append(d)
    d = chip("D_SMA", 4.3, 2.6, 2.0, 1.9, 4.2, "SMA / DO-214AC diode, pad 1 = cathode")
    d.line(-1.6, -1.5, -1.6, 1.5, w=0.3)
    fps.append(d)

    s = Footprint("SOT-23", "SOT-23 (BAV99 etc.)", tags="sot23")
    s.smd_pad(1, -0.95, 1.0, 0.8, 0.9); s.smd_pad(2, 0.95, 1.0, 0.8, 0.9); s.smd_pad(3, 0, -1.0, 0.8, 0.9)
    s.rect(-0.7, -1.45, 0.7, 1.45, layer="F.Fab", w=0.1); s.rect(-1.65, -1.75, 1.65, 1.75)
    s.line(-0.7, -1.55, 0.7, -1.55); s.line(-0.7, 1.55, -0.3, 1.55); s.line(0.3, 1.55, 0.7, 1.55)
    fps.append(s)

    fps.append(soic("SOIC-8", 8, 1.27, 3.9, 4.9, 5.4, 1.55, 0.6, "SOIC-8, 3.9 mm body"))
    fps.append(soic("SOIC-16W", 16, 1.27, 7.5, 10.3, 10.2, 1.8, 0.6, "SOIC-16 wide body 7.5 mm (UCC21520DW), pads extended to give >= 8 mm creepage between pin rows"))
    fps.append(soic("TSSOP-24", 24, 0.65, 4.4, 7.8, 5.9, 1.45, 0.4, "TSSOP-24, 4.4 mm body, 0.65 mm pitch"))

    tp = Footprint("TestPoint", "Test point, 1.5 mm pad", tags="testpoint")
    tp.smd_pad(1, 0, 0, 1.5, 1.5, shape="circle"); tp.circle(0, 0, 1.0); tp.rect(-1.2, -1.2, 1.2, 1.2)
    fps.append(tp)

    # Through hole power semiconductors (vertical mounting, leads in a row)
    def to_vertical(name, npins, pitch, drill, pad, body_w, body_t, desc):
        fp = Footprint(name, desc, smd=False, tags="power")
        for i in range(npins):
            x = (i - (npins - 1) / 2) * pitch
            fp.th_pad(i + 1, x, 0, pad, drill, shape="oval", h=pad + 0.9, square=(i == 0))
        # body (tab side towards -y, heatsink outside the board edge)
        fp.rect(-body_w / 2, -body_t - 1.0, body_w / 2, -1.0, layer="F.Fab", w=0.1)
        fp.rect(-body_w / 2, -body_t - 1.0, body_w / 2, -1.0, layer="F.SilkS", w=0.12)
        fp.rect(-body_w / 2 - 0.5, -body_t - 1.5, body_w / 2 + 0.5, pad / 2 + 1.0)
        fp.text("heatsink side", 0, -body_t - 2.2, layer="F.Fab", size=0.8)
        return fp
    fps.append(to_vertical("TO-247-4_Vertical", 4, 2.54, 1.5, 1.9, 15.9, 5.3, "TO-247-4 vertical (Wolfspeed C3M Kelvin): 1=G 2=D 3=KS 4=S"))
    fps.append(to_vertical("TO-220-3_Vertical", 3, 2.54, 1.3, 1.9, 10.4, 4.6, "TO-220-3 vertical: 1=G 2=D(tab) 3=S"))
    fps.append(to_vertical("TO-220-2_Vertical", 2, 5.08, 1.4, 2.2, 10.4, 4.6, "TO-220-2 vertical: 1=A 2=K(tab)"))

    # SIP-7 isolated DC-DC (RECOM R12P2 / Murata MGJ2)
    sip = Footprint("SIP-7_IsoDCDC", "SIP-7 isolated DC/DC module (RECOM R12P2xxxx), 2.54 mm pitch, 19.6 x 6.2 x 10.2 mm body; pin positions 3,4 not populated. Mill a 1.6 mm slot between pins 2 and 5 for creepage.", smd=False, tags="dcdc")
    for i in (0, 1, 4, 5, 6):
        x = (i - 3) * 2.54
        sip.th_pad(i + 1, x, 0, 1.7, 1.0, shape="oval", h=2.2, square=(i == 0))
    sip.rect(-9.8, -3.6, 9.8, 2.6, layer="F.Fab", w=0.1); sip.rect(-9.8, -3.6, 9.8, 2.6, layer="F.SilkS"); sip.rect(-10.3, -4.1, 10.3, 3.1)
    sip.text("iso slot", 0, -5.0, size=0.7)
    fps.append(sip)

    # Capacitors
    def film(name, pitch, L, W, drill, pad, desc):
        fp = Footprint(name, desc, smd=False, tags="film")
        fp.th_pad(1, -pitch / 2, 0, pad, drill, square=True); fp.th_pad(2, pitch / 2, 0, pad, drill)
        fp.rect(-L / 2, -W / 2, L / 2, W / 2, layer="F.Fab", w=0.1); fp.rect(-L / 2, -W / 2, L / 2, W / 2, layer="F.SilkS")
        fp.rect(-L / 2 - 0.5, -W / 2 - 0.5, L / 2 + 0.5, W / 2 + 0.5)
        return fp
    fps.append(film("C_Film_P37.5", 37.5, 42.0, 20.5, 1.3, 2.6, "Film capacitor 37.5 mm pitch, 41.5 x 20 x 39.5 mm (TDK B32778 10uF/450V)"))
    fps.append(film("C_Film_P22.5", 22.5, 27.0, 11.0, 1.2, 2.4, "Film capacitor 22.5 mm pitch, 26.5 x 10.5 mm (TDK B32674 4.7uF/250V)"))
    fps.append(film("C_Y1_P12.5", 12.5, 14.0, 6.0, 1.2, 2.4, "Y1 safety capacitor disc, 12.5 mm pitch"))

    def radial(name, dia, pitch, drill, pad, desc):
        fp = Footprint(name, desc, smd=False, tags="electrolytic")
        fp.th_pad(1, -pitch / 2, 0, pad, drill, square=True); fp.th_pad(2, pitch / 2, 0, pad, drill)
        fp.circle(0, 0, dia / 2, layer="F.Fab", w=0.1); fp.circle(0, 0, dia / 2 + 0.2); fp.circle(0, 0, dia / 2 + 0.6, layer="F.CrtYd", w=0.05)
        fp.text("+", -pitch / 2, -dia / 2 - 1.2, layer="F.SilkS", size=1.0)
        return fp
    fps.append(radial("C_Radial_D16_P7.5", 16.0, 7.5, 1.2, 2.4, "Electrolytic radial 16 mm dia, 7.5 mm pitch (470uF/63V low-ESR)"))
    fps.append(radial("C_Radial_D8_P3.5", 8.0, 3.5, 0.9, 1.8, "Electrolytic radial 8 mm dia, 3.5 mm pitch"))

    # Fuse
    fu = Footprint("Fuse_6.3x32_Clips", "Fuse 6.3 x 32 mm in PCB clips, 32 mm pitch", smd=False)
    fu.th_pad(1, -16, 0, 3.0, 1.6, shape="oval", h=4.0, square=True); fu.th_pad(2, 16, 0, 3.0, 1.6, shape="oval", h=4.0)
    fu.rect(-19, -4, 19, 4, layer="F.SilkS"); fu.rect(-19.5, -4.5, 19.5, 4.5); fu.rect(-16, -3.2, 16, 3.2, layer="F.Fab", w=0.1)
    fps.append(fu)

    # Power lugs and connectors
    for nm, drill, dia, desc in (("Lug_M4", 4.5, 11.0, "M4 bolt terminal for ring lug"), ("Lug_M5", 5.5, 13.0, "M5 bolt terminal for ring lug")):
        lg = Footprint(nm, desc, smd=False, tags="terminal")
        lg.th_pad(1, 0, 0, dia, drill); lg.circle(0, 0, dia / 2 + 0.5); lg.circle(0, 0, dia / 2 + 1.0, layer="F.CrtYd", w=0.05)
        fps.append(lg)
    tb = Footprint("TerminalBlock_1x02_P5.08", "Screw terminal block 2 pins, 5.08 mm pitch", smd=False)
    tb.th_pad(1, -2.54, 0, 2.6, 1.3, square=True); tb.th_pad(2, 2.54, 0, 2.6, 1.3)
    tb.rect(-5.08, -4.0, 5.08, 4.0, layer="F.SilkS"); tb.rect(-5.58, -4.5, 5.58, 4.5); tb.rect(-5.08, -4.0, 5.08, 4.0, layer="F.Fab", w=0.1)
    fps.append(tb)
    for n in (2, 8):
        ph = Footprint(f"PinHeader_1x{n:02d}_P2.54", f"Pin header 1x{n}, 2.54 mm", smd=False)
        for i in range(n):
            ph.th_pad(i + 1, 0, i * 2.54, 1.7, 1.0, shape="oval", h=1.7, square=(i == 0))
        ph.rect(-1.27, -1.27, 1.27, (n - 1) * 2.54 + 1.27, layer="F.SilkS"); ph.rect(-1.77, -1.77, 1.77, (n - 1) * 2.54 + 1.77)
        fps.append(ph)

    # Magnetics (custom bobbins) -----------------------------------------------
    t = Footprint("Transformer_ETD59_PSFB", "ETD59 vertical bobbin, 2 rows x 8 pins, 5.08 mm pitch, 44 mm row spacing. "
                  "Primary: pad 1 (P+) = two lowest pins, pad 2 (P-) = two highest pins; secondary: pad 3 = 3 pins, pad 4 (CT) = 2 pins, pad 5 = 3 pins. Adapt the pin map to the chosen bobbin.", smd=False, tags="transformer")
    ys = [(i - 3.5) * 5.08 for i in range(8)]
    for i, y in enumerate(ys):
        num = {0: "2", 1: "2", 6: "1", 7: "1"}.get(i, "")
        if num:
            t.th_pad(num, -22, y, 3.0, 1.5, square=(i == 0))
        else:
            t.npth(-22, y, 1.5)
    for i, y in enumerate(ys):
        num = "3" if i < 3 else ("4" if i < 5 else "5")
        t.th_pad(num, 22, y, 3.0, 1.5)
    t.rect(-30, -24, 30, 24, layer="F.SilkS"); t.rect(-30.5, -24.5, 30.5, 24.5); t.rect(-30, -24, 30, 24, layer="F.Fab", w=0.1)
    t.text("PRI", -22, -22, layer="F.SilkS"); t.text("SEC", 22, -22, layer="F.SilkS")
    t.line(0, -24, 0, 24, layer="F.Fab", w=0.1)
    fps.append(t)

    lr = Footprint("Inductor_ETD39_Lr", "ETD39 bobbin resonant inductor, 2 x 2 paralleled pins per terminal, 30 mm row spacing", smd=False, tags="inductor")
    for y in (-2.5, 2.5):
        lr.th_pad("1", -15, y, 3.0, 1.5); lr.th_pad("2", 15, y, 3.0, 1.5)
    lr.rect(-20.5, -20.5, 20.5, 20.5, layer="F.SilkS"); lr.rect(-21, -21, 21, 21); lr.rect(-20.5, -20.5, 20.5, 20.5, layer="F.Fab", w=0.1)
    fps.append(lr)

    lo = Footprint("Inductor_Toroid_D52_Lo", "Toroid output inductor, 2 stacked 77439 cores, OD 52 mm, flat-wire terminals in 2 x 3.2 mm holes", smd=False, tags="inductor")
    for y in (-4, 4):
        lo.th_pad("1", -15, y, 5.5, 3.2); lo.th_pad("2", 15, y, 5.5, 3.2)
    lo.circle(0, 0, 26, layer="F.SilkS"); lo.circle(0, 0, 26.5, layer="F.CrtYd", w=0.05); lo.circle(0, 0, 26, layer="F.Fab", w=0.1)
    fps.append(lo)

    ct = Footprint("CT_Toroid_Straddle", "Current transformer toroid straddling the isolation barrier: primary = 1-turn insulated flying lead "
                   "between pads 1-2 (primary side), secondary winding pads 3-4 (secondary side)", smd=False, tags="transformer")
    ct.th_pad(1, -14, 5, 2.6, 1.5, square=True); ct.th_pad(2, -14, -5, 2.6, 1.5)
    ct.th_pad(3, 14, -2.5, 1.8, 0.9, square=True); ct.th_pad(4, 14, 2.5, 1.8, 0.9)
    ct.circle(0, 0, 10, layer="F.SilkS"); ct.circle(0, 0, 5, layer="F.SilkS"); ct.rect(-16, -11, 16, 11)
    ct.text("PRI loop", -14, -7.5, layer="F.SilkS", size=0.8); ct.text("SEC", 14, -4.5, layer="F.SilkS", size=0.8)
    fps.append(ct)

    sh = Footprint("R_Shunt_8518", "4-terminal power shunt WSBS8518 size (21.6 x 4.6 mm), 0.5 mOhm", tags="shunt")
    sh.smd_pad(1, -8.0, 0, 7.0, 6.0); sh.smd_pad(2, 8.0, 0, 7.0, 6.0)
    sh.rect(-10.8, -2.3, 10.8, 2.3, layer="F.Fab", w=0.1); sh.rect(-12, -3.5, 12, 3.5)
    fps.append(sh)
    mh = Footprint("MountingHole_M4", "M4 mounting hole, 4.3 mm, no copper", smd=False, tags="mounting")
    mh.npth(0, 0, 4.3); mh.circle(0, 0, 3.0, layer="F.SilkS"); mh.circle(0, 0, 4.0, layer="F.CrtYd", w=0.05)
    fps.append(mh)
    return {fp.name: fp for fp in fps}


def write_library(pretty_dir, extra=None):
    os.makedirs(pretty_dir, exist_ok=True)
    for old in os.listdir(pretty_dir):
        if old.endswith(".kicad_mod"):
            os.remove(os.path.join(pretty_dir, old))
    fps = build_library()
    if extra:
        fps.update(extra)
    for fp in fps.values():
        with open(os.path.join(pretty_dir, fp.name + ".kicad_mod"), "w") as fh:
            fh.write(fp.sexpr() + "\n")
    return fps
