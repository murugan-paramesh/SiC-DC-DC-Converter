"""
Design database: every component, its symbol/footprint, and its net connections.
This single description drives the schematic generator, the PCB generator and the BOM.

Sheets:  power   - Power stage (primary bridge, magnetics, rectifier, output filter)
         gate    - Primary gate drive (isolated drivers + isolated bias)
         control - Controller, SR drive, bias input, connectors
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VALS = json.load(open(os.path.join(ROOT, "design", "design_values.json")))

PROJECT = "SiC_PSFB_3kW"
LIB = "SiC_PSFB"

SHEETS = [("power", "Power Stage", "power_stage.kicad_sch"),
          ("gate", "Primary Gate Drive", "gate_drive.kicad_sch"),
          ("control", "Control and SR Drive", "control.kicad_sch")]

POWER_NETS = {"PGND", "SGND", "VBUS", "VOUT", "+12V", "VREF"}

# Net classes (used for PCB clearances and the primary/secondary isolation rule)
PRIMARY_NETS = {"VIN_RAW", "VBUS", "PGND", "SW_A", "SW_B", "LR_N", "PRI_1", "PRI_2"}
PRIMARY_GATE_PREFIXES = ("G_Q1", "G_Q2", "G_Q3", "G_Q4", "GD_Q", "RGOFF_Q", "KS_Q", "VDD_Q", "VEE_Q")


def net_class(net):
    if net in PRIMARY_NETS:
        return "PRI_POWER"
    if net.startswith(PRIMARY_GATE_PREFIXES):
        return "PRI_GATE"
    if net in ("VOUT", "SEC_A", "SEC_B", "SEC_CT", "OUT_N"):
        return "SEC_POWER"
    return "SEC_SIGNAL"


class Comp:
    def __init__(self, ref, value, symbol, footprint, sheet, pins, mpn="", desc="", dnp=False, group=""):
        self.group = group
        self.ref, self.value, self.symbol, self.footprint, self.sheet = ref, value, symbol, footprint, sheet
        self.pins = {str(k): v for k, v in pins.items()}   # pin number -> net name
        self.mpn, self.desc, self.dnp = mpn, desc, dnp

    def __repr__(self):
        return f"<{self.ref} {self.value}>"


def build():
    C = []
    V = VALS
    grp = [""]
    add = lambda *a, **k: C.append(Comp(*a, group=grp[0], **k))
    G = lambda t: grp.__setitem__(0, t)

    # ======================================================================
    # Power stage
    # ======================================================================
    G("Input: terminals, fuse, DC-link capacitors")
    add("J1", "VIN+", "LUG", "Lug_M4", "power", {1: "VIN_RAW"}, desc="Input terminal + (M4 ring lug)")
    add("J2", "VIN-", "LUG", "Lug_M4", "power", {1: "PGND"}, desc="Input terminal - (M4 ring lug)")
    add("F1", "15A/500V", "FUSE", "Fuse_6.3x32_Clips", "power", {1: "VIN_RAW", 2: "VBUS"}, mpn="Littelfuse 0215015.MXP", desc="Input fuse 6.3x32 ceramic, 15 A 500 V")
    for i in range(1, 5):
        add(f"C{i}", "10uF/450V", "C", "C_Film_P37.5", "power", {1: "VBUS", 2: "PGND"}, mpn="TDK B32778G4106K", desc="DC-link film capacitor")
    add("C5", "470nF/630V", "C", "C_2220", "power", {1: "VBUS", 2: "PGND"}, mpn="TDK CGA9P4X7T2J474K", desc="Bridge HF decoupling MLCC")
    add("C6", "470nF/630V", "C", "C_2220", "power", {1: "VBUS", 2: "PGND"}, mpn="TDK CGA9P4X7T2J474K", desc="Bridge HF decoupling MLCC")

    G("SiC full bridge Q1-Q4 (leg A = Q1/Q2 driven by OUTA/OUTB, leg B = Q3/Q4 by OUTC/OUTD)")
    sic = V["sic"]["part"]
    add("Q1", sic, "Q_NMOS_KELVIN", "TO-247-4_Vertical", "power", {1: "G_Q1", 2: "VBUS", 3: "KS_Q1", 4: "SW_A"}, mpn=f"Wolfspeed {sic}", desc="SiC MOSFET 650 V 60 mOhm, leg A high side")
    add("Q2", sic, "Q_NMOS_KELVIN", "TO-247-4_Vertical", "power", {1: "G_Q2", 2: "SW_A", 3: "KS_Q2", 4: "PGND"}, mpn=f"Wolfspeed {sic}", desc="SiC MOSFET, leg A low side")
    add("Q3", sic, "Q_NMOS_KELVIN", "TO-247-4_Vertical", "power", {1: "G_Q3", 2: "VBUS", 3: "KS_Q3", 4: "SW_B"}, mpn=f"Wolfspeed {sic}", desc="SiC MOSFET, leg B high side")
    add("Q4", sic, "Q_NMOS_KELVIN", "TO-247-4_Vertical", "power", {1: "G_Q4", 2: "SW_B", 3: "KS_Q4", 4: "PGND"}, mpn=f"Wolfspeed {sic}", desc="SiC MOSFET, leg B low side")

    G("Resonant inductor, primary clamp diodes, DC blocking, main transformer, current transformer")
    add("L1", "12uH Lr", "L", "Inductor_ETD39_Lr", "power", {1: "SW_A", 2: "LR_N"}, mpn="custom ETD39/3C95 10T litz", desc="Resonant (shim) inductor")
    add("D1", "C3D04065A", "D_SCHOTTKY", "TO-220-2_Vertical", "power", {1: "VBUS", 2: "LR_N"}, mpn="Wolfspeed C3D04065A", desc="Primary clamp diode to VBUS (SiC Schottky 650 V)")
    add("D2", "C3D04065A", "D_SCHOTTKY", "TO-220-2_Vertical", "power", {1: "LR_N", 2: "PGND"}, mpn="Wolfspeed C3D04065A", desc="Primary clamp diode to PGND")
    add("C7", "4.7uF/250V", "C", "C_Film_P22.5", "power", {1: "LR_N", 2: "PRI_1"}, mpn="TDK B32674D3475K", desc="DC blocking capacitor")
    add("C8", "4.7uF/250V", "C", "C_Film_P22.5", "power", {1: "LR_N", 2: "PRI_1"}, mpn="TDK B32674D3475K", desc="DC blocking capacitor")
    add("T1", "ETD59 18:3:3", "T_PSFB", "Transformer_ETD59_PSFB", "power", {1: "PRI_2", 2: "SW_B", 3: "SEC_A", 4: "SEC_CT", 5: "SEC_B"},
        mpn="custom, see docs/06", desc="Main transformer ETD59/3C95, 18:3:3, reinforced insulation")
    add("CT1", "CT 1:100", "CT_1_100", "CT_Toroid_Straddle", "power", {1: "PRI_1", 2: "PRI_2", 3: "CT_S1", 4: "CT_S2"},
        mpn="Magnetics ZW42908TC + 100T AWG32 (or Pulse PA3855.100NL class)", desc="Primary current transformer, 1-turn insulated primary lead")

    G("Synchronous rectifier (centre-tapped), RC snubbers")
    srp = V["sr"]["part"]
    add("Q5", srp, "Q_NMOS", "TO-220-3_Vertical", "power", {1: "G_Q5", 2: "SEC_A", 3: "SGND"}, mpn=f"Infineon {srp}", desc="Synchronous rectifier A1, 200 V 10.7 mOhm")
    add("Q6", srp, "Q_NMOS", "TO-220-3_Vertical", "power", {1: "G_Q6", 2: "SEC_A", 3: "SGND"}, mpn=f"Infineon {srp}", desc="Synchronous rectifier A2")
    add("Q7", srp, "Q_NMOS", "TO-220-3_Vertical", "power", {1: "G_Q7", 2: "SEC_B", 3: "SGND"}, mpn=f"Infineon {srp}", desc="Synchronous rectifier B1")
    add("Q8", srp, "Q_NMOS", "TO-220-3_Vertical", "power", {1: "G_Q8", 2: "SEC_B", 3: "SGND"}, mpn=f"Infineon {srp}", desc="Synchronous rectifier B2")
    add("R1", "10R/2W", "R", "R_2512", "power", {1: "SEC_A", 2: "SNUB_A"}, desc="SR snubber resistor")
    add("C9", "470pF/250V", "C", "C_1206", "power", {1: "SNUB_A", 2: "SGND"}, desc="SR snubber capacitor, C0G")
    add("R2", "10R/2W", "R", "R_2512", "power", {1: "SEC_B", 2: "SNUB_B"}, desc="SR snubber resistor")
    add("C10", "470pF/250V", "C", "C_1206", "power", {1: "SNUB_B", 2: "SGND"}, desc="SR snubber capacitor, C0G")
    G("Output filter, current shunt, output terminals, Y capacitors, test points")
    add("L2", "6.8uH/70A", "L", "Inductor_Toroid_D52_Lo", "power", {1: "SEC_CT", 2: "VOUT"}, mpn="custom 2x Magnetics 77439-A7, 5T flat wire", desc="Output inductor")
    for i in range(11, 17):
        add(f"C{i}", "470uF/63V", "C_POL", "C_Radial_D16_P7.5", "power", {1: "VOUT", 2: "SGND"}, mpn="Nichicon UHW1J471MHD", desc="Output electrolytic, low ESR")
    for i in range(17, 23):
        add(f"C{i}", "10uF/100V", "C", "C_1210", "power", {1: "VOUT", 2: "SGND"}, mpn="TDK CGA6P3X7S2A106K", desc="Output MLCC X7S")
    add("R3", "0.5mR", "R", "R_Shunt_8518", "power", {1: "SGND", 2: "OUT_N"}, mpn="Vishay WSBS8518L5000JK", desc="Output current shunt 0.5 mOhm")
    add("J3", "VOUT+", "LUG", "Lug_M5", "power", {1: "VOUT"}, desc="Output terminal + (M5 ring lug)")
    add("J4", "VOUT-", "LUG", "Lug_M5", "power", {1: "OUT_N"}, desc="Output terminal - (M5 ring lug)")
    add("CY1", "2.2nF Y1", "C", "C_Y1_P12.5", "power", {1: "PGND", 2: "SGND"}, mpn="Vishay VY1222M63Y5UQ63V0", desc="Y1 safety capacitor across the barrier")
    add("CY2", "2.2nF Y1", "C", "C_Y1_P12.5", "power", {1: "PGND", 2: "SGND"}, mpn="Vishay VY1222M63Y5UQ63V0", desc="Y1 safety capacitor across the barrier")
    add("TP1", "SW_A", "TP", "TestPoint", "power", {1: "SW_A"}, desc="Test point (primary, hazardous)")
    add("TP2", "SW_B", "TP", "TestPoint", "power", {1: "SW_B"}, desc="Test point (primary, hazardous)")
    add("TP3", "PGND", "TP", "TestPoint", "power", {1: "PGND"}, desc="Test point (primary, hazardous)")
    add("TP4", "SEC_CT", "TP", "TestPoint", "power", {1: "SEC_CT"}, desc="Test point")
    add("TP5", "SGND", "TP", "TestPoint", "power", {1: "SGND"}, desc="Test point")
    for i in range(1, 5):
        add(f"H{i}", "M4", "MOUNTING_HOLE", "MountingHole_M4", "power", {}, desc="Mounting hole M4")

    # ======================================================================
    # Primary gate drive
    # ======================================================================
    G("Isolated gate drivers UCC21520 (logic side = secondary ground, driver side = per-MOSFET Kelvin source)")
    drv = {"U2": ("OUTA", "OUTB", 1, 2), "U3": ("OUTC", "OUTD", 3, 4)}
    for ref, (ina, inb, qh, ql) in drv.items():
        add(ref, "UCC21520DW", "UCC21520", "SOIC-16W", "gate",
            {1: ina, 2: inb, 3: "+12V", 4: "SGND", 5: "SGND", 6: f"DT_{ref}", 7: f"NC_{ref}_7", 8: "+12V",
             9: f"VEE_Q{ql}", 10: f"GD_Q{ql}", 11: f"VDD_Q{ql}", 12: f"NC_{ref}_12", 13: f"NC_{ref}_13",
             14: f"VDD_Q{qh}", 15: f"GD_Q{qh}", 16: f"VEE_Q{qh}"},
            mpn="TI UCC21520DW", desc=f"Isolated dual gate driver, Q{qh}/Q{ql}")
    add("R20", "2.2k", "R", "R_0603", "gate", {1: "DT_U2", 2: "SGND"}, desc="Driver dead-time (22 ns safety)")
    add("R21", "2.2k", "R", "R_0603", "gate", {1: "DT_U3", 2: "SGND"}, desc="Driver dead-time (22 ns safety)")
    add("C30", "1uF/25V", "C", "C_0603", "gate", {1: "+12V", 2: "SGND"}, desc="U2 VCCI decoupling")
    add("C31", "1uF/25V", "C", "C_0603", "gate", {1: "+12V", 2: "SGND"}, desc="U3 VCCI decoupling")
    rn, cn = 22, 32
    for q in range(1, 5):
        G(f"Q{q} isolated bias (+15 V / -3 V) and gate network")
        add(f"PS{q}", "R12P21503D", "R12P21503D", "SIP-7_IsoDCDC", "gate", {1: "+12V", 2: "SGND", 5: f"VEE_Q{q}", 6: f"KS_Q{q}", 7: f"VDD_Q{q}"},
            mpn="RECOM R12P21503D", desc=f"Isolated +15/-3 V gate bias for Q{q}")
        add(f"C{cn}", "10uF/25V", "C", "C_1206", "gate", {1: "+12V", 2: "SGND"}, desc=f"PS{q} input capacitor"); cn += 1
        add(f"C{cn}", "10uF/25V", "C", "C_1206", "gate", {1: f"VDD_Q{q}", 2: f"KS_Q{q}"}, desc=f"Q{q} +15 V bias bulk"); cn += 1
        add(f"C{cn}", "1uF/50V", "C", "C_0603", "gate", {1: f"VDD_Q{q}", 2: f"KS_Q{q}"}, desc=f"Q{q} +15 V bias HF"); cn += 1
        add(f"C{cn}", "4.7uF/25V", "C", "C_0805", "gate", {1: f"KS_Q{q}", 2: f"VEE_Q{q}"}, desc=f"Q{q} -3 V bias bulk"); cn += 1
        add(f"C{cn}", "1uF/50V", "C", "C_0603", "gate", {1: f"KS_Q{q}", 2: f"VEE_Q{q}"}, desc=f"Q{q} -3 V bias HF"); cn += 1
        add(f"R{rn}", f'{V["R_g_on"]}R', "R", "R_1206", "gate", {1: f"GD_Q{q}", 2: f"G_Q{q}"}, desc=f"Q{q} turn-on gate resistor"); rn += 1
        add(f"R{rn}", f'{V["R_g_off"]}R', "R", "R_1206", "gate", {1: f"GD_Q{q}", 2: f"RGOFF_Q{q}"}, desc=f"Q{q} turn-off gate resistor"); rn += 1
        add(f"D{q+9}", "SS14", "D_SCHOTTKY", "D_SMA", "gate", {1: f"RGOFF_Q{q}", 2: f"G_Q{q}"}, mpn="Vishay SS14", desc=f"Q{q} turn-off steering diode")
        add(f"R{rn}", "10k", "R", "R_0603", "gate", {1: f"G_Q{q}", 2: f"KS_Q{q}"}, desc=f"Q{q} gate-source bleed"); rn += 1

    # ======================================================================
    # Control + SR drive
    # ======================================================================
    G("Auxiliary 12 V bias input")
    add("J5", "+12V AUX", "CONN_1x02", "TerminalBlock_1x02_P5.08", "control", {1: "+12V", 2: "SGND"}, desc="Auxiliary 12 V bias input (secondary referenced)")
    add("D3", "SMAJ15A", "D_TVS", "D_SMA", "control", {1: "+12V", 2: "SGND"}, mpn="Littelfuse SMAJ15A", desc="Bias input TVS")
    add("C64", "100uF/25V", "C_POL", "C_Radial_D8_P3.5", "control", {1: "+12V", 2: "SGND"}, desc="Bias bulk capacitor")
    add("C65", "1uF/25V", "C", "C_0603", "control", {1: "+12V", 2: "SGND"}, desc="Bias HF capacitor")

    G("UCC28951 PSFB controller: supply, reference, voltage loop, timing")
    add("U1", "UCC28951PW", "UCC28951", "TSSOP-24", "control",
        {1: "VREF", 2: "EA_P", 3: "EA_N", 4: "COMP", 5: "SS_EN", 6: "DELAB", 7: "DELCD", 8: "DELEF", 9: "TMIN", 10: "RT",
         11: "RSUM", 12: "DCM", 13: "ADELEF", 14: "ADEL", 15: "CS", 16: "SYNC", 17: "OUTF", 18: "OUTE", 19: "OUTD",
         20: "OUTC", 21: "OUTB", 22: "OUTA", 23: "VDD_IC", 24: "SGND"}, mpn="TI UCC28951PW", desc="PSFB controller")
    add("R40", "10R", "R", "R_0805", "control", {1: "+12V", 2: "VDD_IC"}, desc="VDD filter")
    add("C52", "10uF/25V", "C", "C_1206", "control", {1: "VDD_IC", 2: "SGND"}, desc="VDD bulk")
    add("C53", "100nF", "C", "C_0603", "control", {1: "VDD_IC", 2: "SGND"}, desc="VDD HF")
    add("C54", "1uF/25V", "C", "C_0603", "control", {1: "VREF", 2: "SGND"}, desc="VREF capacitor")
    add("R41", "10k", "R", "R_0603", "control", {1: "VREF", 2: "EA_P"}, desc="EA+ reference divider (2.5 V)")
    add("R42", "10k", "R", "R_0603", "control", {1: "EA_P", 2: "SGND"}, desc="EA+ reference divider")
    add("C55", "100nF", "C", "C_0603", "control", {1: "EA_P", 2: "SGND"}, desc="EA+ filter")
    add("R43", "10k", "R", "R_0805", "control", {1: "VOUT", 2: "FB_MID"}, desc="Output voltage divider upper 1")
    add("R44", "10k", "R", "R_0805", "control", {1: "FB_MID", 2: "EA_N"}, desc="Output voltage divider upper 2")
    add("R45", "1.1k", "R", "R_0603", "control", {1: "EA_N", 2: "SGND"}, desc="Output voltage divider lower")
    add("R46", f'{V["Rz"]/1e3:.0f}k', "R", "R_0603", "control", {1: "COMP", 2: "COMP_Z"}, desc="Type-II compensation Rz")
    add("C56", f'{V["Cz"]*1e9:.1f}nF', "C", "C_0603", "control", {1: "COMP_Z", 2: "EA_N"}, desc="Type-II compensation Cz")
    add("C57", f'{V["Cp"]*1e12:.0f}pF', "C", "C_0603", "control", {1: "COMP", 2: "EA_N"}, desc="Type-II compensation Cp")
    add("C58", "100nF", "C", "C_0603", "control", {1: "SS_EN", 2: "SGND"}, desc="Soft-start capacitor (~20 ms)")
    add("R47", "13k", "R", "R_0603", "control", {1: "DELAB", 2: "SGND"}, desc="A/B leg delay")
    add("R48", "13k", "R", "R_0603", "control", {1: "DELCD", 2: "SGND"}, desc="C/D leg delay")
    add("R49", "20k", "R", "R_0603", "control", {1: "DELEF", 2: "SGND"}, desc="SR (E/F) delay")
    add("R50", "20k", "R", "R_0603", "control", {1: "TMIN", 2: "SGND"}, desc="Minimum on-time")
    add("R51", "60.4k", "R", "R_0603", "control", {1: "VREF", 2: "RT"}, desc="Oscillator: 100 kHz (verify against datasheet equation)")
    add("R52", "100k", "R", "R_0603", "control", {1: "RSUM", 2: "SGND"}, desc="Slope compensation")
    add("R53", "100k", "R", "R_0603", "control", {1: "VREF", 2: "DCM"}, desc="DCM threshold divider")
    add("R54", "10k", "R", "R_0603", "control", {1: "DCM", 2: "SGND"}, desc="DCM threshold divider")
    add("R55", "100k", "R", "R_0603", "control", {1: "VREF", 2: "ADEL"}, desc="Adaptive delay A/B,C/D divider")
    add("R56", "10k", "R", "R_0603", "control", {1: "ADEL", 2: "SGND"}, desc="Adaptive delay divider")
    add("R57", "100k", "R", "R_0603", "control", {1: "VREF", 2: "ADELEF"}, desc="Adaptive delay E/F divider")
    add("R58", "10k", "R", "R_0603", "control", {1: "ADELEF", 2: "SGND"}, desc="Adaptive delay E/F divider")
    G("Primary current sense: CT bridge rectifier and burden")
    add("D4", "BAV99", "BAV99", "SOT-23", "control", {1: "SGND", 2: "CT_RECT", 3: "CT_S1"}, desc="CT rectifier bridge half")
    add("D5", "BAV99", "BAV99", "SOT-23", "control", {1: "SGND", 2: "CT_RECT", 3: "CT_S2"}, desc="CT rectifier bridge half")
    add("R59", f'{V["R_burden"]:.0f}R', "R", "R_0805", "control", {1: "CT_RECT", 2: "SGND"}, desc="CT burden resistor")
    add("R60", "100R", "R", "R_0603", "control", {1: "CT_RECT", 2: "CS"}, desc="CS filter")
    add("C59", "100pF", "C", "C_0603", "control", {1: "CS", 2: "SGND"}, desc="CS filter, C0G")
    G("Synchronous rectifier gate drive UCC27524")
    add("U4", "UCC27524D", "UCC27524", "SOIC-8", "control", {1: "+12V", 2: "OUTE", 3: "SGND", 4: "OUTF", 5: "SR_B", 6: "+12V", 7: "SR_A", 8: "+12V"},
        mpn="TI UCC27524D", desc="Dual 5 A SR gate driver")
    add("C60", "1uF/25V", "C", "C_0603", "control", {1: "+12V", 2: "SGND"}, desc="U4 decoupling HF")
    add("C61", "10uF/25V", "C", "C_1206", "control", {1: "+12V", 2: "SGND"}, desc="U4 decoupling bulk")
    rn = 61
    for q, src in ((5, "SR_A"), (6, "SR_A"), (7, "SR_B"), (8, "SR_B")):
        add(f"R{rn}", "4.7R", "R", "R_0805", "control", {1: src, 2: f"G_Q{q}"}, desc=f"Q{q} gate resistor"); rn += 1
        add(f"R{rn}", "10k", "R", "R_0603", "control", {1: f"G_Q{q}", 2: "SGND"}, desc=f"Q{q} gate bleed"); rn += 1
    G("Signal connector, NTC, indicator, test points")
    add("J6", "SIGNAL", "CONN_1x08", "PinHeader_1x08_P2.54", "control",
        {1: "VREF", 2: "SS_EN", 3: "TEMP", 4: "OUT_N", 5: "SGND", 6: "COMP", 7: "SYNC", 8: "SGND"},
        desc="Signal header: 1 VREF, 2 EN, 3 TEMP, 4 IMON- (shunt), 5 IMON+ (SGND), 6 COMP, 7 SYNC, 8 GND")
    add("J7", "NTC", "CONN_1x02", "PinHeader_1x02_P2.54", "control", {1: "TEMP", 2: "SGND"}, desc="Heatsink NTC 10k")
    add("R69", "10k", "R", "R_0603", "control", {1: "VREF", 2: "TEMP"}, desc="NTC pull-up")
    add("D6", "LED GRN", "LED", "LED_0805", "control", {1: "SGND", 2: "LED_A"}, desc="VREF OK indicator")
    add("R70", "1k", "R", "R_0603", "control", {1: "VREF", 2: "LED_A"}, desc="LED resistor")
    add("TP6", "CS", "TP", "TestPoint", "control", {1: "CS"}, desc="Test point")
    add("TP7", "COMP", "TP", "TestPoint", "control", {1: "COMP"}, desc="Test point")
    add("TP8", "OUTA", "TP", "TestPoint", "control", {1: "OUTA"}, desc="Test point")
    add("TP9", "OUTC", "TP", "TestPoint", "control", {1: "OUTC"}, desc="Test point")
    return C


def nets_of(comps):
    nets = {}
    for c in comps:
        for pin, net in c.pins.items():
            nets.setdefault(net, []).append((c.ref, pin))
    return nets


if __name__ == "__main__":
    comps = build()
    nets = nets_of(comps)
    print(len(comps), "components,", len(nets), "nets")
    singles = {n: p for n, p in nets.items() if len(p) < 2 and not n.startswith("NC_")}
    print("single-pin nets:", singles)
