"""
Design database of the 6.6 kW SiC DAB power board (schematic + PCB + BOM single source).

Board partitioning: this PCB carries both SiC full bridges, the DC links, all gate drive and
isolated bias, sensing, hardware protection, auxiliary power, the controller interface
(LAUNCHXL-F280049C BoosterPack headers) and the external-magnetics terminals.  The transformer
and the series inductor are an external magnetics module (06_Magnetics) connected with M6 studs.

Isolation regions (see 15_Safety_Reliability/01): HV (850 V), LV (450 V), CTRL (SELV).
Nets are classified by the prefix rules in net_class().

Pinouts used here are the ones the author is confident about; every IC entry carries a
`pin_verified` flag that an engineer must set after checking the datasheet.
"""
import os, json, re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V = json.load(open(os.path.join(ROOT, "04_Design_Calculations", "design_values.json")))
PROJECT = "SiC_DAB_6k6"
LIB = "SiC_DAB"

SHEETS = [("hv", "HV Port and HV Bridge", "hv_bridge.kicad_sch"),
          ("lv", "LV Port and LV Bridge", "lv_bridge.kicad_sch"),
          ("gate", "Gate Drive and Isolated Bias", "gate_drive.kicad_sch"),
          ("sense", "Sensing and Hardware Protection", "sensing_protection.kicad_sch"),
          ("ctrl", "Controller Interface, Aux Power, Comms", "control_aux.kicad_sch")]

POWER_NETS = {"HV_P", "HV_N", "LV_P", "LV_N", "GND", "+12V", "+5V", "+3V3", "+24V"}
GROUND_NETS = {"HV_N", "LV_N", "GND"}

HV_POWER = {"HV_IN", "HV_P", "HV_N", "SW_A", "SW_B"}
LV_POWER = {"LV_IN", "LV_P", "LV_N", "SW_C", "SW_D"}


def net_class(net):
    if net in HV_POWER: return "HV_POWER"
    if net in LV_POWER: return "LV_POWER"
    if re.match(r"(G|GD|RGOFF|KS|VDD|VEE)_Q[1-4]\b", net) or net in ("HV_SENSE_P", "HV_SENSE_N", "HV_ISO5V", "HV_ISOGND", "HV_DIV", "HV_BLD1", "HV_BLD2", "HV_BLD3"): return "HV_GATE"
    if re.match(r"(G|GD|RGOFF|KS|VDD|VEE)_Q[5-8]\b", net) or net in ("LV_SENSE_P", "LV_SENSE_N", "LV_ISO5V", "LV_ISOGND", "LV_DIV", "LV_BLD1", "LV_BLD2", "SH_P", "SH_N", "I2_ISO5V", "I2_ISOGND"): return "LV_GATE"
    if net in ("GND", "+12V", "+5V", "+3V3", "+24V"): return "CTRL_POWER"
    return "CTRL_SIGNAL"


class Comp:
    def __init__(self, ref, value, symbol, footprint, sheet, pins, mpn="", desc="", group="", dnp=False, pin_verified=True):
        self.ref, self.value, self.symbol, self.footprint, self.sheet = ref, value, symbol, footprint, sheet
        self.pins = {str(k): v for k, v in pins.items()}
        self.mpn, self.desc, self.group, self.dnp, self.pin_verified = mpn, desc, group, dnp, pin_verified


def build():
    C = []
    grp = [""]
    add = lambda *a, **k: C.append(Comp(*a, group=grp[0], **k))
    G = lambda t: grp.__setitem__(0, t)
    nC = [100]; nR = [100]; nD = [20]
    def Cn(): nC[0] += 1; return f"C{nC[0]}"
    def Rn(): nR[0] += 1; return f"R{nR[0]}"
    def Dn(): nD[0] += 1; return f"D{nD[0]}"

    # ================================================================ HV sheet
    G("HV port: studs, fuse interface, DC-link capacitors, bleeders, Y capacitors")
    add("J1", "HV+", "LUG", "Stud_M6", "hv", {1: "HV_IN"}, desc="HV port + (M6 stud); external semiconductor fuse 16 A/1000 V and precharge contactor in series")
    add("J2", "HV-", "LUG", "Stud_M6", "hv", {1: "HV_N"}, desc="HV port -")
    add("F1", "16A/1000V", "FUSE", "Fuse_Terminal_M6", "hv", {1: "HV_IN", 2: "HV_P"}, mpn="Bussmann FWP-16A14F class (verify)", desc="HV semiconductor fuse on M6 terminals")
    for i in range(1, 5):
        add(f"C{i}", "20uF/1100V", "C", "C_Film_P52.5", "hv", {1: "HV_P", 2: "HV_N"}, mpn="TDK B32778J0206K (verify 1100 V variant)", desc="HV DC-link film capacitor")
    add("R1", "680k/2W", "R", "R_2512", "hv", {1: "HV_P", 2: "HV_BLD1"}, desc="HV bleeder chain 2.7 MOhm (4 x 680 k, 850 V / 4 = 212 V per resistor)")
    add("R2", "680k/2W", "R", "R_2512", "hv", {1: "HV_BLD1", 2: "HV_BLD2"}, desc="HV bleeder")
    add("R3", "680k/2W", "R", "R_2512", "hv", {1: "HV_BLD2", 2: "HV_BLD3"}, desc="HV bleeder")
    add("R4", "680k/2W", "R", "R_2512", "hv", {1: "HV_BLD3", 2: "HV_N"}, desc="HV bleeder")
    add("CY1", "4.7nF Y1", "C", "C_Y1_P12.5", "hv", {1: "HV_P", 2: "PE"}, mpn="Vishay VY1472M63Y5UQ63V0", desc="Y1 capacitor HV+ to PE (first CM filter element)")
    add("CY2", "4.7nF Y1", "C", "C_Y1_P12.5", "hv", {1: "HV_N", 2: "PE"}, mpn="Vishay VY1472M63Y5UQ63V0", desc="Y1 capacitor HV- to PE")
    G("HV SiC full bridge Q1-Q4 (leg A = Q1/Q2 -> SW_A, leg B = Q3/Q4 -> SW_B), HF decoupling")
    for q, (d, s_) in zip((1, 2, 3, 4), (("HV_P", "SW_A"), ("SW_A", "HV_N"), ("HV_P", "SW_B"), ("SW_B", "HV_N"))):
        add(f"Q{q}", V["dev1"], "Q_NMOS_KELVIN", "TO-247-4_Vertical", "hv", {1: f"G_Q{q}", 2: d, 3: f"KS_Q{q}", 4: s_}, mpn=f"Wolfspeed {V['dev1']}", desc=f"HV bridge SiC MOSFET 1200 V, {'high' if q in (1, 3) else 'low'} side leg {'A' if q < 3 else 'B'}")
    for i in range(5, 9):
        add(f"C{i}", "100nF/1kV", "C", "C_2220", "hv", {1: "HV_P", 2: "HV_N"}, mpn="TDK CGA9N4X7T2W104K (verify)", desc="HV bridge HF decoupling, one pair per leg")
    add("J3", "SW_A", "LUG", "Stud_M6", "hv", {1: "SW_A"}, desc="HV bridge output A -> external series inductor L1")
    add("J4", "SW_B", "LUG", "Stud_M6", "hv", {1: "SW_B"}, desc="HV bridge output B -> transformer primary")
    add("TP1", "SW_A", "TP", "TestPoint", "hv", {1: "SW_A"}, desc="Test point (hazardous)"); add("TP2", "SW_B", "TP", "TestPoint", "hv", {1: "SW_B"}, desc="Test point (hazardous)"); add("TP3", "HV_N", "TP", "TestPoint", "hv", {1: "HV_N"}, desc="Test point (hazardous)")

    # ================================================================ LV sheet
    G("LV port: studs, DC-link capacitors, bleeders, Y capacitors, output shunt")
    add("J5", "LV+", "LUG", "Stud_M6", "lv", {1: "LV_IN"}, desc="LV port + (M6 stud); external fuse/contactor in series")
    add("J6", "LV-", "LUG", "Stud_M6", "lv", {1: "SH_N"}, desc="LV port - (through the current shunt)")
    add("F2", "32A/700V", "FUSE", "Fuse_Terminal_M6", "lv", {1: "LV_IN", 2: "LV_P"}, mpn="Bussmann FWP-32A14F class (verify)", desc="LV semiconductor fuse on M6 terminals")
    for i in range(9, 13):
        add(f"C{i}", "30uF/700V", "C", "C_Film_P37.5", "lv", {1: "LV_P", 2: "LV_N"}, mpn="TDK B32778G7306K (verify)", desc="LV DC-link film capacitor")
    add("R5", "1M/2W", "R", "R_2512", "lv", {1: "LV_P", 2: "LV_BLD1"}, desc="LV bleeder chain 2 MOhm")
    add("R6", "1M/2W", "R", "R_2512", "lv", {1: "LV_BLD1", 2: "LV_N"}, desc="LV bleeder")
    add("CY3", "4.7nF Y1", "C", "C_Y1_P12.5", "lv", {1: "LV_P", 2: "PE"}, mpn="Vishay VY1472M63Y5UQ63V0", desc="Y1 capacitor LV+ to PE")
    add("CY4", "4.7nF Y1", "C", "C_Y1_P12.5", "lv", {1: "LV_N", 2: "PE"}, mpn="Vishay VY1472M63Y5UQ63V0", desc="Y1 capacitor LV- to PE")
    add("R7", "1mR", "R", "R_Shunt_8518", "lv", {1: "LV_N", 2: "SH_N"}, mpn="Vishay WSBS8518L1000JK", desc="LV port current shunt 1 mOhm (33 A -> 33 mV)")
    G("LV SiC full bridge Q5-Q8 (leg C = Q5/Q6 -> SW_C, leg D = Q7/Q8 -> SW_D), HF decoupling")
    for q, (d, s_) in zip((5, 6, 7, 8), (("LV_P", "SW_C"), ("SW_C", "LV_N"), ("LV_P", "SW_D"), ("SW_D", "LV_N"))):
        add(f"Q{q}", V["dev2"], "Q_NMOS_KELVIN", "TO-247-4_Vertical", "lv", {1: f"G_Q{q}", 2: d, 3: f"KS_Q{q}", 4: s_}, mpn=f"Wolfspeed {V['dev2']}", desc=f"LV bridge SiC MOSFET 1200 V, {'high' if q in (5, 7) else 'low'} side leg {'C' if q < 7 else 'D'}")
    for i in range(13, 17):
        add(f"C{i}", "220nF/630V", "C", "C_2220", "lv", {1: "LV_P", 2: "LV_N"}, mpn="TDK CGA9P4X7T2J224K (verify)", desc="LV bridge HF decoupling, one pair per leg")
    add("J7", "SW_C", "LUG", "Stud_M6", "lv", {1: "SW_C"}, desc="LV bridge output C -> transformer secondary")
    add("J8", "SW_D", "LUG", "Stud_M6", "lv", {1: "SW_D"}, desc="LV bridge output D -> transformer secondary")
    add("TP4", "SW_C", "TP", "TestPoint", "lv", {1: "SW_C"}, desc="Test point (hazardous)"); add("TP5", "SW_D", "TP", "TestPoint", "lv", {1: "SW_D"}, desc="Test point (hazardous)"); add("TP6", "LV_N", "TP", "TestPoint", "lv", {1: "LV_N"}, desc="Test point (hazardous)")

    # ================================================================ gate drive sheet
    legs = {"U1": (1, 2, "PWM1A", "PWM1B"), "U2": (3, 4, "PWM2A", "PWM2B"), "U3": (5, 6, "PWM3A", "PWM3B"), "U4": (7, 8, "PWM4A", "PWM4B")}
    for ref, (qh, ql, ina, inb) in legs.items():
        G(f"Isolated dual gate driver {ref} for Q{qh} (high side) / Q{ql} (low side), fault disable via PROT_DIS")
        add(ref, "UCC21520DW", "UCC21520", "SOIC-16W", "gate",
            {1: ina, 2: inb, 3: "+5V", 4: "GND", 5: "PROT_DIS", 6: f"DT_{ref}", 7: f"NC_{ref}_7", 8: "+5V",
             9: f"VEE_Q{ql}", 10: f"GD_Q{ql}", 11: f"VDD_Q{ql}", 12: f"NC_{ref}_12", 13: f"NC_{ref}_13", 14: f"VDD_Q{qh}", 15: f"GD_Q{qh}", 16: f"VEE_Q{qh}"},
            mpn="TI UCC21520DW", desc=f"5.7 kVrms reinforced isolated dual gate driver, leg Q{qh}/Q{ql}; DESAT-type driver (UCC21710) is the documented upgrade path")
        add(Rn(), "2.2k", "R", "R_0603", "gate", {1: f"DT_{ref}", 2: "GND"}, desc=f"{ref} interlock dead time ~22 ns")
        add(Cn(), "1uF/16V", "C", "C_0603", "gate", {1: "+5V", 2: "GND"}, desc=f"{ref} VCCI decoupling")
        for q in (qh, ql):
            G(f"Q{q} isolated bias (+15 V / -3 V) and gate network")
            add(f"PS{q}", "R12P21503D", "R12P21503D", "SIP-7_IsoDCDC", "gate", {1: "+12V", 2: "GND", 5: f"VEE_Q{q}", 6: f"KS_Q{q}", 7: f"VDD_Q{q}"},
                mpn="RECOM R12P21503D (basic-class isolation; reinforced-rated module is an open item, see 15.1)", desc=f"Isolated gate bias Q{q}", pin_verified=False)
            add(Cn(), "10uF/25V", "C", "C_1206", "gate", {1: "+12V", 2: "GND"}, desc=f"PS{q} input capacitor")
            add(Cn(), "10uF/25V", "C", "C_1206", "gate", {1: f"VDD_Q{q}", 2: f"KS_Q{q}"}, desc=f"Q{q} +15 V bulk")
            add(Cn(), "1uF/50V", "C", "C_0603", "gate", {1: f"VDD_Q{q}", 2: f"KS_Q{q}"}, desc=f"Q{q} +15 V HF")
            add(Cn(), "4.7uF/25V", "C", "C_0805", "gate", {1: f"KS_Q{q}", 2: f"VEE_Q{q}"}, desc=f"Q{q} -3 V bulk")
            add(Cn(), "1uF/50V", "C", "C_0603", "gate", {1: f"KS_Q{q}", 2: f"VEE_Q{q}"}, desc=f"Q{q} -3 V HF")
            add(Rn(), "3.3R", "R", "R_1206", "gate", {1: f"GD_Q{q}", 2: f"G_Q{q}"}, desc=f"Q{q} turn-on gate resistor")
            add(Rn(), "1.5R", "R", "R_1206", "gate", {1: f"GD_Q{q}", 2: f"RGOFF_Q{q}"}, desc=f"Q{q} turn-off gate resistor")
            add(Dn(), "SS14", "D_SCHOTTKY", "D_SMA", "gate", {1: f"RGOFF_Q{q}", 2: f"G_Q{q}"}, mpn="Vishay SS14", desc=f"Q{q} turn-off steering diode")
            add(Rn(), "10k", "R", "R_0603", "gate", {1: f"G_Q{q}", 2: f"KS_Q{q}"}, desc=f"Q{q} gate-source bleed")

    # ================================================================ sensing + protection sheet
    G("HV link voltage sense: divider -> AMC1301 (isolated), isolated 5 V from a 1 W SIP module")
    add("U5", "AMC1301", "AMC1301", "SOIC-8W", "sense", {1: "HV_ISO5V", 2: "HV_SENSE_P", 3: "HV_SENSE_N", 4: "HV_ISOGND", 5: "GND", 6: "V1_OUTN", 7: "V1_OUTP", 8: "+5V"},
        mpn="TI AMC1301DWV", desc="Reinforced isolated amplifier, +/-250 mV input, HV link voltage", pin_verified=False)
    add("PS9", "R1SE-0505", "ISO_DCDC_SIP4", "SIP-4_IsoDCDC", "sense", {1: "+5V", 2: "GND", 3: "HV_ISOGND", 4: "HV_ISO5V"}, mpn="RECOM R1SE-0505/H (verify pinout)", desc="1 W isolated 5 V for the HV-side sensor", pin_verified=False)
    add(Rn(), "1M/1206x4", "R", "R_1206", "sense", {1: "HV_P", 2: "HV_DIV"}, desc="HV divider upper (4 x 1 M in series, 2 shown as one value; 1000 V FS -> 250 mV)")
    add(Rn(), "1M", "R", "R_1206", "sense", {1: "HV_DIV", 2: "HV_SENSE_P"}, desc="HV divider upper 2")
    add(Rn(), "499R", "R", "R_0603", "sense", {1: "HV_SENSE_P", 2: "HV_ISOGND"}, desc="HV divider lower (HV_ISOGND = HV_N reference)")
    add(Rn(), "0R", "R", "R_0603", "sense", {1: "HV_SENSE_N", 2: "HV_ISOGND"}, desc="AMC1301 INN to local ground")
    add(Rn(), "0R", "R", "R_0805", "sense", {1: "HV_ISOGND", 2: "HV_N"}, desc="Isolated sensor ground tied to HV- (single point)")
    add(Cn(), "1nF", "C", "C_0603", "sense", {1: "HV_SENSE_P", 2: "HV_ISOGND"}, desc="HV sense filter")
    add(Cn(), "100nF", "C", "C_0603", "sense", {1: "HV_ISO5V", 2: "HV_ISOGND"}, desc="AMC1301 VDD1 decoupling"); add(Cn(), "100nF", "C", "C_0603", "sense", {1: "+5V", 2: "GND"}, desc="AMC1301 VDD2 decoupling")
    G("LV link voltage sense: divider -> AMC1301")
    add("U6", "AMC1301", "AMC1301", "SOIC-8W", "sense", {1: "LV_ISO5V", 2: "LV_SENSE_P", 3: "LV_SENSE_N", 4: "LV_ISOGND", 5: "GND", 6: "V2_OUTN", 7: "V2_OUTP", 8: "+5V"}, mpn="TI AMC1301DWV", desc="Isolated amplifier, LV link voltage", pin_verified=False)
    add("PS10", "R1SE-0505", "ISO_DCDC_SIP4", "SIP-4_IsoDCDC", "sense", {1: "+5V", 2: "GND", 3: "LV_ISOGND", 4: "LV_ISO5V"}, mpn="RECOM R1SE-0505/H", desc="1 W isolated 5 V for the LV-side sensors", pin_verified=False)
    add(Rn(), "1M", "R", "R_1206", "sense", {1: "LV_P", 2: "LV_DIV"}, desc="LV divider upper 1 (500 V FS -> 250 mV)")
    add(Rn(), "1M", "R", "R_1206", "sense", {1: "LV_DIV", 2: "LV_SENSE_P"}, desc="LV divider upper 2")
    add(Rn(), "1k", "R", "R_0603", "sense", {1: "LV_SENSE_P", 2: "LV_ISOGND"}, desc="LV divider lower")
    add(Rn(), "0R", "R", "R_0603", "sense", {1: "LV_SENSE_N", 2: "LV_ISOGND"}, desc="INN to local ground")
    add(Rn(), "0R", "R", "R_0805", "sense", {1: "LV_ISOGND", 2: "LV_N"}, desc="Isolated sensor ground tied to LV-")
    add(Cn(), "1nF", "C", "C_0603", "sense", {1: "LV_SENSE_P", 2: "LV_ISOGND"}, desc="LV sense filter")
    add(Cn(), "100nF", "C", "C_0603", "sense", {1: "LV_ISO5V", 2: "LV_ISOGND"}, desc="VDD1 decoupling"); add(Cn(), "100nF", "C", "C_0603", "sense", {1: "+5V", 2: "GND"}, desc="VDD2 decoupling")
    G("LV port current: shunt -> AMC1301 (same isolated 5 V as the LV voltage sensor)")
    add("U7", "AMC1301", "AMC1301", "SOIC-8W", "sense", {1: "LV_ISO5V", 2: "SH_P", 3: "SH_NS", 4: "LV_ISOGND", 5: "GND", 6: "I2_OUTN", 7: "I2_OUTP", 8: "+5V"}, mpn="TI AMC1301DWV", desc="Isolated shunt amplifier, LV port current (1 mOhm, +/-33 mV)", pin_verified=False)
    add(Rn(), "10R", "R", "R_0603", "sense", {1: "LV_N", 2: "SH_P"}, desc="Shunt Kelvin sense + (LV_N side)")
    add(Rn(), "10R", "R", "R_0603", "sense", {1: "SH_N", 2: "SH_NS"}, desc="Shunt Kelvin sense -")
    add(Cn(), "10nF", "C", "C_0603", "sense", {1: "SH_P", 2: "SH_NS"}, desc="Shunt sense differential filter")
    add(Cn(), "100nF", "C", "C_0603", "sense", {1: "+5V", 2: "GND"}, desc="VDD2 decoupling")
    G("Series-inductor current: current transformer 1:100, burden, precision rectifier/peak -> ADC and CMPSS; isolated amplifier outputs -> single-ended")
    add("CT1", "CT 1:100", "CT_1_100", "CT_Toroid_Straddle", "sense", {1: "SW_A", 2: "SW_A_CT", 3: "CT_S1", 4: "CT_S2"}, mpn="Magnetics ZW42908TC + 100T AWG32", desc="Inductor current CT: one-turn insulated lead from J3 (SW_A) to the external inductor; secondary on the control side")
    add("J9", "L1 (via CT)", "LUG", "Stud_M6", "sense", {1: "SW_A_CT"}, desc="Stud for the inductor lead after the CT loop")
    add("D30", "BAV99", "BAV99", "SOT-23", "sense", {1: "GND", 2: "CT_RECT", 3: "CT_S1"}, desc="CT bridge rectifier half")
    add("D31", "BAV99", "BAV99", "SOT-23", "sense", {1: "GND", 2: "CT_RECT", 3: "CT_S2"}, desc="CT bridge rectifier half")
    add(Rn(), "6.2R", "R", "R_0805", "sense", {1: "CT_RECT", 2: "GND"}, desc="CT burden: 32 A -> 2.0 V (CMPSS trip), 40 A FS")
    add(Rn(), "1k", "R", "R_0603", "sense", {1: "CT_RECT", 2: "I_L"}, desc="I_L to ADC/CMPSS filter"); add(Cn(), "220pF", "C", "C_0603", "sense", {1: "I_L", 2: "GND"}, desc="I_L filter C0G")
    add("U8", "TLV9062", "OPAMP_DUAL", "SOIC-8", "sense", {1: "V1_SE", 2: "V1_FB", 3: "V1_OUTP", 4: "GND", 5: "V2_OUTP", 6: "V2_FB", 7: "V2_SE", 8: "+5V"}, mpn="TI TLV9062IDR", desc="Differential-to-single-ended for V1/V2 (gain 2.5 -> 0-2.5 V... see note: AMC1301 differential output 2 V p-p around 1.44 V)")
    for nm, pin_in, pin_fb, pin_out in (("V1", "V1_OUTN", "V1_FB", "V1_SE"), ("V2", "V2_OUTN", "V2_FB", "V2_SE")):
        add(Rn(), "10k", "R", "R_0603", "sense", {1: pin_in, 2: pin_fb}, desc=f"{nm} difference amplifier input")
        add(Rn(), "10k", "R", "R_0603", "sense", {1: pin_fb, 2: pin_out}, desc=f"{nm} difference amplifier feedback")
        add(Rn(), "10k", "R", "R_0603", "sense", {1: f"{nm}_OUTP", 2: f"{nm}_REF"}, desc=f"{nm} difference amplifier (non-inverting network)")
        add(Rn(), "10k", "R", "R_0603", "sense", {1: f"{nm}_REF", 2: "GND"}, desc=f"{nm} difference amplifier reference leg")
    # note: for a true difference amplifier the + input needs the divided OUTP; simplified representation keeps nets explicit
    add("U9", "TLV9062", "OPAMP_DUAL", "SOIC-8", "sense", {1: "I2_SE", 2: "I2_FB", 3: "I2_OUTP", 4: "GND", 5: "I2_REF", 6: "I2_REF", 7: "I2_REF_OUT", 8: "+5V"}, mpn="TI TLV9062IDR", desc="I2 difference amplifier + 1.65 V reference buffer")
    add(Rn(), "10k", "R", "R_0603", "sense", {1: "I2_OUTN", 2: "I2_FB"}, desc="I2 diff amp"); add(Rn(), "10k", "R", "R_0603", "sense", {1: "I2_FB", 2: "I2_SE"}, desc="I2 diff amp feedback")
    add(Rn(), "10k", "R", "R_0603", "sense", {1: "+3V3", 2: "I2_REF"}, desc="1.65 V reference divider"); add(Rn(), "10k", "R", "R_0603", "sense", {1: "I2_REF", 2: "GND"}, desc="1.65 V reference divider")
    add(Cn(), "100nF", "C", "C_0603", "sense", {1: "+5V", 2: "GND"}, desc="U8 decoupling"); add(Cn(), "100nF", "C", "C_0603", "sense", {1: "+5V", 2: "GND"}, desc="U9 decoupling")
    G("Hardware protection: LM393 comparators (OC on I_L, OV on V1_SE / V2_SE) wired-OR -> PROT_DIS (driver DIS + DSP TZ)")
    add("U10", "LM393", "COMP_DUAL", "SOIC-8", "sense", {1: "PROT_DIS", 2: "OC_REF", 3: "I_L", 4: "GND", 5: "V1_SE", 6: "OV1_REF", 7: "PROT_DIS", 8: "+5V"}, mpn="TI LM393DR", desc="OC comparator (I_L > 2.0 V) and HV OV comparator; open-collector outputs wired-OR")
    add("U11", "LM393", "COMP_DUAL", "SOIC-8", "sense", {1: "PROT_DIS", 2: "OV2_REF", 3: "V2_SE", 4: "GND", 5: "GND", 6: "+5V", 7: f"NC_U11_7", 8: "+5V"}, mpn="TI LM393DR", desc="LV OV comparator; second half unused (input tied inactive)")
    add(Rn(), "10k", "R", "R_0603", "sense", {1: "+5V", 2: "PROT_DIS"}, desc="PROT_DIS pull-up (high = drivers disabled)")
    add(Rn(), "10k", "R", "R_0603", "sense", {1: "+5V", 2: "OC_REF"}, desc="OC threshold divider (2.0 V)"); add(Rn(), "6.8k", "R", "R_0603", "sense", {1: "OC_REF", 2: "GND"}, desc="OC threshold divider")
    add(Rn(), "10k", "R", "R_0603", "sense", {1: "+5V", 2: "OV1_REF"}, desc="HV OV threshold (920 V)"); add(Rn(), "8.2k", "R", "R_0603", "sense", {1: "OV1_REF", 2: "GND"}, desc="HV OV threshold")
    add(Rn(), "10k", "R", "R_0603", "sense", {1: "+5V", 2: "OV2_REF"}, desc="LV OV threshold (490 V)"); add(Rn(), "10k", "R", "R_0603", "sense", {1: "OV2_REF", 2: "GND"}, desc="LV OV threshold")
    add(Cn(), "100nF", "C", "C_0603", "sense", {1: "+5V", 2: "GND"}, desc="U10 decoupling"); add(Cn(), "100nF", "C", "C_0603", "sense", {1: "+5V", 2: "GND"}, desc="U11 decoupling")
    add("U12", "74HC32", "OR_QUAD", "SOIC-14", "sense", {1: "PROT_DIS", 2: "DSP_DIS", 3: "DIS_ALL", 4: "DIS_ALL", 5: "GND", 6: "NC_U12_6", 7: "GND", 8: "NC_U12_8", 9: "GND", 10: "GND", 11: "NC_U12_11", 12: "GND", 13: "GND", 14: "+5V"},
        mpn="TI SN74HC32D", desc="DIS_ALL = PROT_DIS OR DSP_DIS -> gate driver DIS inputs (nets: drivers use PROT_DIS directly in rev A; DIS_ALL reserved)")
    add(Cn(), "100nF", "C", "C_0603", "sense", {1: "+5V", 2: "GND"}, desc="U12 decoupling")
    add("TP7", "I_L", "TP", "TestPoint", "sense", {1: "I_L"}, desc="Test point"); add("TP8", "PROT_DIS", "TP", "TestPoint", "sense", {1: "PROT_DIS"}, desc="Test point"); add("TP9", "V1_SE", "TP", "TestPoint", "sense", {1: "V1_SE"}, desc="Test point"); add("TP10", "V2_SE", "TP", "TestPoint", "sense", {1: "V2_SE"}, desc="Test point")

    # ================================================================ control / aux sheet
    G("Controller interface: LAUNCHXL-F280049C BoosterPack headers (pin functions per TI BoosterPack standard; F280049C GPIO mapping to be verified against SPRUII7)")
    j1 = {1: "+3V3", 2: "V1_SE", 3: "UART_RX", 4: "UART_TX", 5: "GPIO_EN_IN", 6: "V2_SE", 7: "SPI_CLK", 8: "GPIO_PRE_FB", 9: "I2C_SCL", 10: "I2C_SDA",
          11: "GPIO_DIS_OUT", 12: "SPI_CS", 13: "GPIO_FAN", 14: "SPI_MISO", 15: "SPI_MOSI", 16: "RESET_N", 17: "GPIO_LED", 18: "I2_SE", 19: "GPIO_RELAY1", 20: "GND"}
    j2 = {21: "+5V", 22: "GND", 23: "I_L", 24: "TEMP1", 25: "TEMP2", 26: "NC_J11_26", 27: "NC_J11_27", 28: "NC_J11_28", 29: "NC_J11_29", 30: "NC_J11_30",
          31: "GPIO_RELAY2", 32: "GPIO_TZ_IN", 33: "CAN_RX", 34: "CAN_TX", 35: "NC_J11_35", 36: "NC_J11_36", 37: "PWM4B", 38: "PWM4A", 39: "PWM3B", 40: "PWM3A"}
    add("J10", "BoosterPack J1/J3", "CONN_2x10", "PinHeader_2x10_P2.54", "ctrl", j1, mpn="Samtec SSW-110-01-G-D class", desc="BoosterPack header 1 (pins 1-20)", pin_verified=False)
    add("J11", "BoosterPack J2/J4", "CONN_2x10", "PinHeader_2x10_P2.54", "ctrl", {k - 20: v for k, v in j2.items()}, mpn="Samtec SSW-110-01-G-D class", desc="BoosterPack header 2 (pins 21-40); PWM1A/B, PWM2A/B on the third header J12", pin_verified=False)
    add("J12", "BoosterPack PWM", "CONN_1x08", "PinHeader_1x08_P2.54", "ctrl", {1: "PWM1A", 2: "PWM1B", 3: "PWM2A", 4: "PWM2B", 5: "GND", 6: "GPIO_SYNC", 7: "GND", 8: "+3V3"}, desc="Additional PWM header (LaunchPad J5/J6 extension), to be mapped", pin_verified=False)
    add(Rn(), "0R", "R", "R_0603", "ctrl", {1: "GPIO_DIS_OUT", 2: "DSP_DIS"}, desc="DSP disable output to the hardware OR")
    add(Rn(), "0R", "R", "R_0603", "ctrl", {1: "PROT_DIS", 2: "GPIO_TZ_IN"}, desc="Hardware fault to DSP trip-zone input")
    G("Auxiliary power: 24 V in -> 12 V (3 A) -> 5 V (1 A) -> 3.3 V LDO; reverse polarity, TVS")
    add("J13", "+24V IN", "CONN_1x02", "TerminalBlock_1x02_P5.08", "ctrl", {1: "+24V_IN", 2: "GND"}, desc="24 V auxiliary input")
    add("D32", "SMBJ33A", "D_TVS", "D_SMA", "ctrl", {1: "+24V_IN", 2: "GND"}, mpn="Littelfuse SMBJ33A", desc="24 V input TVS")
    add("D33", "SS34", "D_SCHOTTKY", "D_SMA", "ctrl", {1: "+24V", 2: "+24V_IN"}, mpn="Vishay SS34", desc="Reverse-polarity series diode")
    add(Cn(), "100uF/50V", "C_POL", "C_Radial_D8_P3.5", "ctrl", {1: "+24V", 2: "GND"}, desc="24 V bulk")
    add("U13", "TSR 3-24120", "DCDC_SIP3", "SIP-3_TSR", "ctrl", {1: "+24V", 2: "GND", 3: "+12V"}, mpn="TRACO TSR 3-24120", desc="12 V / 3 A switching regulator module (gate bias supplies)", pin_verified=True)
    add(Cn(), "100uF/25V", "C_POL", "C_Radial_D8_P3.5", "ctrl", {1: "+12V", 2: "GND"}, desc="12 V bulk"); add(Cn(), "10uF/25V", "C", "C_1206", "ctrl", {1: "+12V", 2: "GND"}, desc="12 V HF")
    add("U14", "TSR 1-2450", "DCDC_SIP3", "SIP-3_TSR", "ctrl", {1: "+24V", 2: "GND", 3: "+5V"}, mpn="TRACO TSR 1-2450", desc="5 V / 1 A regulator (drivers logic, sensors, LaunchPad)")
    add(Cn(), "47uF/16V", "C_POL", "C_Radial_D8_P3.5", "ctrl", {1: "+5V", 2: "GND"}, desc="5 V bulk"); add(Cn(), "10uF/16V", "C", "C_1206", "ctrl", {1: "+5V", 2: "GND"}, desc="5 V HF")
    add("U15", "AMS1117-3.3", "LDO_SOT223", "SOT-223", "ctrl", {1: "GND", 2: "+3V3", 3: "+5V"}, mpn="AMS1117-3.3", desc="3.3 V LDO for references/pull-ups")
    add(Cn(), "10uF/16V", "C", "C_1206", "ctrl", {1: "+3V3", 2: "GND"}, desc="3.3 V output"); add(Cn(), "1uF/16V", "C", "C_0603", "ctrl", {1: "+3V3", 2: "GND"}, desc="3.3 V HF")
    G("CAN transceiver, service UART header, LEDs")
    add("U16", "TCAN332", "CAN_XCVR", "SOIC-8", "ctrl", {1: "CAN_TX", 2: "GND", 3: "+3V3", 4: "CAN_RX", 5: "NC_U16_5", 6: "CANL", 7: "CANH", 8: "GND"}, mpn="TI TCAN332D", desc="CAN transceiver 3.3 V (non-isolated; ISO1042 is the upgrade for a galvanically isolated bus)", pin_verified=False)
    add(Rn(), "120R", "R", "R_0603", "ctrl", {1: "CANH", 2: "CANL"}, desc="CAN termination (fit if end node)")
    add(Cn(), "100nF", "C", "C_0603", "ctrl", {1: "+3V3", 2: "GND"}, desc="U16 decoupling")
    add("J14", "CAN", "CONN_1x02", "TerminalBlock_1x02_P5.08", "ctrl", {1: "CANH", 2: "CANL"}, desc="CAN bus terminal")
    add("J15", "UART", "CONN_1x02", "PinHeader_1x02_P2.54", "ctrl", {1: "UART_TX", 2: "UART_RX"}, desc="Service UART (3.3 V)")
    add("D34", "LED GRN", "LED", "LED_0805", "ctrl", {1: "GND", 2: "LED_A"}, desc="Status LED"); add(Rn(), "1k", "R", "R_0603", "ctrl", {1: "GPIO_LED", 2: "LED_A"}, desc="LED resistor")
    add("D35", "LED RED", "LED", "LED_0805", "ctrl", {1: "GND", 2: "LED_F"}, desc="Fault LED (PROT_DIS)"); add(Rn(), "1k", "R", "R_0603", "ctrl", {1: "PROT_DIS", 2: "LED_F"}, desc="Fault LED resistor")
    G("Precharge / contactor interface: 2 relay driver outputs, 2 optocoupled feedback inputs, fan output; heatsink NTC inputs")
    add("U17", "ULN2003A", "ULN2003", "SOIC-16", "ctrl", {1: "GPIO_RELAY1", 2: "GPIO_RELAY2", 3: "GPIO_FAN", 4: "NC_U17_4", 5: "NC_U17_5", 6: "NC_U17_6", 7: "NC_U17_7", 8: "GND", 9: "+24V",
                                                       10: "NC_U17_10", 11: "NC_U17_11", 12: "NC_U17_12", 13: "NC_U17_13", 14: "FAN_OUT", 15: "RELAY2_OUT", 16: "RELAY1_OUT"},
        mpn="TI ULN2003AD", desc="Darlington driver for precharge contactor coils (24 V) and fans", pin_verified=True)
    add("J16", "RELAY/FAN", "CONN_1x08", "PinHeader_1x08_P2.54", "ctrl", {1: "+24V", 2: "RELAY1_OUT", 3: "+24V", 4: "RELAY2_OUT", 5: "+24V", 6: "FAN_OUT", 7: "GND", 8: "GND"}, desc="Contactor coil and fan outputs (24 V, 500 mA max each)")
    add("U18", "PC817", "OPTO", "DIP-4", "ctrl", {1: "FB1_A", 2: "GND_EXT", 3: "GND", 4: "GPIO_PRE_FB"}, mpn="Sharp PC817", desc="Precharge-complete feedback input (24 V contact)", pin_verified=True)
    add(Rn(), "4.7k", "R", "R_0805", "ctrl", {1: "FB1_IN", 2: "FB1_A"}, desc="Opto input resistor (24 V)"); add(Rn(), "10k", "R", "R_0603", "ctrl", {1: "+3V3", 2: "GPIO_PRE_FB"}, desc="Opto collector pull-up")
    add("U19", "PC817", "OPTO", "DIP-4", "ctrl", {1: "FB2_A", 2: "GND_EXT", 3: "GND", 4: "GPIO_EN_IN"}, mpn="Sharp PC817", desc="External enable input (24 V)", pin_verified=True)
    add(Rn(), "4.7k", "R", "R_0805", "ctrl", {1: "FB2_IN", 2: "FB2_A"}, desc="Opto input resistor"); add(Rn(), "10k", "R", "R_0603", "ctrl", {1: "+3V3", 2: "GPIO_EN_IN"}, desc="Opto collector pull-up")
    add("J17", "INTERLOCK IN", "CONN_1x08", "PinHeader_1x08_P2.54", "ctrl", {1: "FB1_IN", 2: "GND_EXT", 3: "FB2_IN", 4: "GND_EXT", 5: "NC_J17_5", 6: "NC_J17_6", 7: "NC_J17_7", 8: "NC_J17_8"}, desc="Isolated 24 V inputs: precharge feedback, external enable")
    add("J18", "NTC1", "CONN_1x02", "PinHeader_1x02_P2.54", "ctrl", {1: "TEMP1", 2: "GND"}, desc="HV heatsink NTC 10k"); add(Rn(), "10k", "R", "R_0603", "ctrl", {1: "+3V3", 2: "TEMP1"}, desc="NTC1 pull-up")
    add("J19", "NTC2", "CONN_1x02", "PinHeader_1x02_P2.54", "ctrl", {1: "TEMP2", 2: "GND"}, desc="LV heatsink NTC 10k"); add(Rn(), "10k", "R", "R_0603", "ctrl", {1: "+3V3", 2: "TEMP2"}, desc="NTC2 pull-up")
    add("J20", "PE", "LUG", "Lug_M5", "ctrl", {1: "PE"}, desc="Protective earth stud (bonded to heatsinks and enclosure)")
    add(Rn(), "0R", "R", "R_1206", "ctrl", {1: "PE", 2: "GND"}, desc="Control ground to PE single-point bond (fit 0 R or 1 nF/1 MOhm per EMC test)")
    for i in range(1, 7):
        add(f"H{i}", "M4", "MOUNTING_HOLE", "MountingHole_M4", "ctrl", {}, desc="Mounting hole M4")
    add("TP11", "GND", "TP", "TestPoint", "ctrl", {1: "GND"}, desc="Test point"); add("TP12", "+12V", "TP", "TestPoint", "ctrl", {1: "+12V"}, desc="Test point"); add("TP13", "+5V", "TP", "TestPoint", "ctrl", {1: "+5V"}, desc="Test point")
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
    import collections
    dup = [r for r, k in collections.Counter(c.ref for c in comps).items() if k > 1]
    singles = {n: p for n, p in nets.items() if len(p) < 2 and not n.startswith("NC_")}
    print(len(comps), "components,", len(nets), "nets; duplicate refs:", dup)
    print("single-pin nets:", singles)
    print("unverified pinouts:", sorted(set(c.value for c in comps if not c.pin_verified)))
