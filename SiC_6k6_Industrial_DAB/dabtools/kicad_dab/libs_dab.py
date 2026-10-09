"""Additional symbols and footprints for the DAB board, on top of the PSFB libraries."""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
from tools.kicad.symbols import Symbol, box_symbol, GRID, PIN_LEN
from tools.kicad.footprints import Footprint, chip, soic, dip_th


def extra_symbols():
    syms = []
    syms.append(box_symbol("AMC1301", "U", left=[("1", "VDD1", "power_in"), ("2", "INP", "input"), ("3", "INN", "input"), ("4", "GND1", "power_in")],
                           right=[("8", "VDD2", "power_in"), ("7", "OUTP", "output"), ("6", "OUTN", "output"), ("5", "GND2", "power_in")],
                           desc="AMC1301 reinforced isolated amplifier (pinout to verify)", width=17.78))
    syms.append(box_symbol("OPAMP_DUAL", "U", left=[("3", "IN1+", "input"), ("2", "IN1-", "input"), ("5", "IN2+", "input"), ("6", "IN2-", "input"), ("4", "V-", "power_in")],
                           right=[("1", "OUT1", "output"), ("7", "OUT2", "output"), ("8", "V+", "power_in")], desc="Dual op-amp, standard SOIC-8 pinout", width=17.78))
    syms.append(box_symbol("COMP_DUAL", "U", left=[("3", "IN1+", "input"), ("2", "IN1-", "input"), ("5", "IN2+", "input"), ("6", "IN2-", "input"), ("4", "GND", "power_in")],
                           right=[("1", "OUT1", "open_collector"), ("7", "OUT2", "open_collector"), ("8", "VCC", "power_in")], desc="LM393 dual comparator, open collector", width=17.78))
    syms.append(box_symbol("OR_QUAD", "U", left=[("1", "1A", "input"), ("2", "1B", "input"), ("4", "2A", "input"), ("5", "2B", "input"), ("9", "3A", "input"), ("10", "3B", "input"), ("12", "4A", "input"), ("13", "4B", "input"), ("7", "GND", "power_in")],
                           right=[("3", "1Y", "output"), ("6", "2Y", "output"), ("8", "3Y", "output"), ("11", "4Y", "output"), ("14", "VCC", "power_in")], desc="74HC32 quad OR", width=17.78))
    syms.append(box_symbol("ISO_DCDC_SIP4", "PS", left=[("1", "+VIN", "power_in"), ("2", "-VIN", "power_in")], right=[("4", "+VOUT", "power_out"), ("3", "-VOUT", "power_out")],
                           desc="1 W isolated DC-DC SIP-4 (R1SE class, pinout to verify)", width=17.78))
    syms.append(box_symbol("DCDC_SIP3", "U", left=[("1", "VIN", "power_in"), ("2", "GND", "power_in")], right=[("3", "VOUT", "power_out")], desc="TRACO TSR switching regulator SIP-3", width=15.24))
    syms.append(box_symbol("LDO_SOT223", "U", left=[("3", "VIN", "power_in"), ("1", "GND", "power_in")], right=[("2", "VOUT", "power_out")], desc="AMS1117 LDO SOT-223 (1 GND, 2 VOUT, 3 VIN)", width=15.24))
    syms.append(box_symbol("CAN_XCVR", "U", left=[("1", "TXD", "input"), ("4", "RXD", "output"), ("3", "VCC", "power_in"), ("2", "GND", "power_in"), ("8", "STB", "input")],
                           right=[("7", "CANH", "bidirectional"), ("6", "CANL", "bidirectional"), ("5", "NC", "no_connect")], desc="CAN transceiver, 8-pin standard pinout", width=17.78))
    syms.append(box_symbol("ULN2003", "U", left=[(str(i), f"IN{i}", "input") for i in range(1, 8)] + [("8", "GND", "power_in")],
                           right=[(str(17 - i), f"OUT{i}", "open_collector") for i in range(1, 8)] + [("9", "COM", "passive")], desc="ULN2003A Darlington array", width=17.78))
    syms.append(box_symbol("OPTO", "U", left=[("1", "A", "passive"), ("2", "K", "passive")], right=[("4", "C", "passive"), ("3", "E", "passive")], desc="PC817 optocoupler", width=12.7))
    s = Symbol("CONN_2x10", "J", "2x10 header (BoosterPack)", hide_pin_names=True)
    s.rect(-3.81, -27.94, 3.81, 27.94)
    for i in range(10):
        y = 24.13 - i * 5.08
        s.pin(2 * i + 1, f"P{2*i+1}", -6.35, y, 0); s.pin(2 * i + 2, f"P{2*i+2}", 6.35, y, 180)
    s.ref_pos, s.val_pos = (-3.81, 29.21), (-3.81, -29.21)
    syms.append(s)
    def gnd(name):
        g = Symbol(name, "#PWR", f"Power symbol {name}", power=True, hide_pin_names=True, hide_pin_numbers=True)
        g.poly([(0, 0), (0, -1.27)]); g.poly([(-1.27, -1.27), (1.27, -1.27)]); g.poly([(-0.635, -1.905), (0.635, -1.905)]); g.poly([(-0.254, -2.54), (0.254, -2.54)])
        g.pin(1, name, 0, 0, 270, "power_in", hide=True, length=0); g.ref_pos, g.val_pos = (0, -5.08), (0, -3.81); return g
    def vcc(name):
        v = Symbol(name, "#PWR", f"Power symbol {name}", power=True, hide_pin_names=True, hide_pin_numbers=True)
        v.poly([(0, 0), (0, 1.27)]); v.poly([(-1.27, 1.27), (1.27, 1.27)], width=0.381)
        v.pin(1, name, 0, 0, 90, "power_in", hide=True, length=0); v.ref_pos, v.val_pos = (0, -1.27), (0, 2.54); return v
    syms += [gnd("HV_N"), gnd("LV_N"), gnd("GND"), vcc("HV_P"), vcc("LV_P"), vcc("+5V"), vcc("+3V3"), vcc("+24V")]
    return {x.name: x for x in syms}


def extra_footprints():
    fps = []
    st = Footprint("Stud_M6", "M6 press-fit / bolt stud terminal, 6.5 mm hole, 16 mm pad", smd=False, tags="terminal")
    st.th_pad(1, 0, 0, 16.0, 6.5); st.circle(0, 0, 9.0); st.circle(0, 0, 9.5, layer="F.CrtYd", w=0.05)
    fps.append(st)
    ft = Footprint("Fuse_Terminal_M6", "Two M6 stud terminals for an external semiconductor fuse, 40 mm pitch", smd=False, tags="fuse")
    ft.th_pad(1, -20, 0, 16.0, 6.5); ft.th_pad(2, 20, 0, 16.0, 6.5); ft.rect(-30, -9, 30, 9, layer="F.SilkS"); ft.rect(-30.5, -9.5, 30.5, 9.5)
    fps.append(ft)
    f = Footprint("C_Film_P52.5", "Film capacitor 52.5 mm pitch, 57.5 x 35 mm body (TDK B32778 1100 V class)", smd=False, tags="film")
    f.th_pad(1, -26.25, 0, 3.0, 1.5, square=True); f.th_pad(2, 26.25, 0, 3.0, 1.5)
    f.rect(-29, -17.5, 29, 17.5, layer="F.Fab", w=0.1); f.rect(-29, -17.5, 29, 17.5, layer="F.SilkS"); f.rect(-29.5, -18, 29.5, 18)
    fps.append(f)
    fps.append(soic("SOIC-8W", 8, 1.27, 5.85, 7.5, 11.0, 2.0, 0.6, "SOIC-8 wide body (AMC1301 DWV), pads extended for 8.5 mm creepage"))
    fps.append(soic("SOIC-14", 14, 1.27, 3.9, 8.65, 5.4, 1.55, 0.6, "SOIC-14 narrow"))
    fps.append(soic("SOIC-16", 16, 1.27, 3.9, 9.9, 5.4, 1.55, 0.6, "SOIC-16 narrow"))
    sip = Footprint("SIP-4_IsoDCDC", "1 W isolated DC-DC SIP-4, 2.54 pitch (R1SE class), slot between pins 2 and 3 for creepage", smd=False, tags="dcdc")
    for i in range(4):
        sip.th_pad(i + 1, (i - 1.5) * 2.54, 0, 1.7, 1.0, shape="oval", h=2.2, square=(i == 0))
    sip.rect(-5.9, -3.0, 5.9, 2.5, layer="F.SilkS"); sip.rect(-6.4, -3.5, 6.4, 3.0); sip.rect(-5.9, -3.0, 5.9, 2.5, layer="F.Fab", w=0.1)
    fps.append(sip)
    t = Footprint("SIP-3_TSR", "TRACO TSR 1/3 series SIP-3, 2.54 pitch", smd=False, tags="dcdc")
    for i in range(3):
        t.th_pad(i + 1, (i - 1) * 2.54, 0, 1.7, 1.0, shape="oval", h=2.2, square=(i == 0))
    t.rect(-5.9, -3.0, 5.9, 2.5, layer="F.SilkS"); t.rect(-6.4, -3.5, 6.4, 3.0); t.rect(-5.9, -3.0, 5.9, 2.5, layer="F.Fab", w=0.1)
    fps.append(t)
    so = Footprint("SOT-223", "SOT-223 (1 GND/ADJ, 2 VOUT, 3 VIN, tab = VOUT)", tags="sot223")
    so.smd_pad(1, -2.3, 3.0, 1.2, 2.2); so.smd_pad(2, 0, 3.0, 1.2, 2.2); so.smd_pad(3, 2.3, 3.0, 1.2, 2.2); so.smd_pad(2, 0, -3.0, 3.6, 2.2)
    so.rect(-3.3, -3.6, 3.3, 3.6, layer="F.Fab", w=0.1); so.rect(-3.8, -4.4, 3.8, 4.4); so.line(-3.3, -1.5, 3.3, -1.5); so.line(-3.3, 1.5, 3.3, 1.5)
    fps.append(so)
    fps.append(dip_th("DIP-4", 4, 2.54, 7.62, 0.8, 1.6, 4.6, 4.6, "DIP-4 (PC817)"))
    ph = Footprint("PinHeader_2x10_P2.54", "Pin header 2x10, 2.54 mm", smd=False)
    for i in range(10):
        ph.th_pad(2 * i + 1, 0, i * 2.54, 1.7, 1.0, shape="oval", h=1.7, square=(i == 0)); ph.th_pad(2 * i + 2, 2.54, i * 2.54, 1.7, 1.0, shape="oval", h=1.7)
    ph.rect(-1.27, -1.27, 3.81, 9 * 2.54 + 1.27, layer="F.SilkS"); ph.rect(-1.77, -1.77, 4.31, 9 * 2.54 + 1.77)
    fps.append(ph)
    return {x.name: x for x in fps}
