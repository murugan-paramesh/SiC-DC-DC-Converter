# 14 Safety, insulation and FMEA

> Reading time: ~45 min. Prerequisites: chapters 10 (schematics), 11 (PCB layout), 12 (thermal).
> Files covered: `SiC_6k6_Industrial_DAB/15_Safety_Reliability/01_insulation_coordination.md`,
> `SiC_6k6_Industrial_DAB/15_Safety_Reliability/02_FMEA.md`, `SiC_6k6_Industrial_DAB/15_Safety_Reliability/02_FMEA.csv`,
> `SiC_6k6_Industrial_DAB/00_Requirements/01_requirements_specification.md` (SAF-01 to SAF-08),
> `SiC_6k6_Industrial_DAB/04_Design_Calculations/design_report.md` (protection thresholds),
> `SiC_6k6_Industrial_DAB/10_Firmware/src/dab_control.h`, `SiC_6k6_Industrial_DAB/20_Experimental_Test_Plan/test_plan.md`,
> `Advanced_Research_2026/Reliability_Engineering/` (FTA, FMEDA-lite, state-machine check).

## Overview

**Level 1 - Beginner:** Safety in a converter with an 850 V bus is about three things: keeping the
dangerous voltage away from anything a person can touch (insulation), making sure that when something
goes wrong the converter switches itself off faster than the damage can happen (protection), and
thinking in advance about what can fail and what then happens (the FMEA). Insulation is mostly
distance - through air and along surfaces - plus certified components where the distance must be
bridged. Protection is layered: a hardware comparator in under a microsecond, the firmware in ten
microseconds, the system (fuse, contactor) as the last line. None of this has been tested on
hardware, and no certification is claimed anywhere in the repository.

**Level 2 - Engineering:** The insulation study applies the IEC 62477-1 / IEC 60664-1 method:
decisive voltage class C for both power circuits, class A (SELV) for the control circuit, hence
reinforced insulation from either power circuit to control and basic insulation HV-LV and to PE.
With pollution degree 2, overvoltage category II, altitude <= 2000 m and material group II (CTI
>= 400), the recalled table values give 5.5 mm clearance and 12-17 mm creepage for HV-control
(reinforced), 3.0 / 6-8.5 mm for HV-LV and HV-PE (basic); the design uses 16 mm barriers, 12 mm DRC
rules, 8.5 / 5.0 mm to PE and milled slots under the SIP modules. Protection thresholds come from the
design calculation: hardware trip at 32 A (HV side), OV comparators 920 / 490 V, firmware OV
900 / 480 V, UV 600 / 280 V, NTC trip 95 C, DESAT as an upgrade path. The FMEA has 19 rows with
S x O x D scoring; the highest RPN items are the HV MOSFET short (96), the CT failure and the loose
connector (84 each) and the film capacitor ageing (72).

**Level 3 - Research:** The 2026 reliability module turns the FMEA into three quantitative objects:
a fault tree with minimal cut sets and Fussell-Vesely importances (top event "hazardous voltage at an
accessible part" at 1.4e-4 per year, 97 % of it from the three classes of barrier components;
"uncontrolled energy transfer" at 1.9e-4 per year, every leading cut set containing NO_DESAT), an
FMEDA-lite with diagnostic coverage per protection function (35-47 %, no SIL claimed) and an
exhaustive state-machine model check of the firmware (46,080 transitions, C conformance pass, one
literal property failing by design). All rates are stated class values; the module's value is the
structure of the argument, not the numbers.

![insulation distances](img/ch14_insulation_distances.png)

## Topics

### Circuits, decisive voltage classes and insulation types

**What is it?** The first step of insulation coordination: list every circuit with its working
voltage and its accessibility, assign a decisive voltage class (DVC) and derive the required
insulation type between each pair (`15_Safety_Reliability/01_insulation_coordination.md`
section 1). `[Implemented]` as analysis.

**Why do we need it?** The required distances depend on three things: the working voltage across the
pair, whether a person can touch one side, and whether a single failure must be tolerated. The
circuit table fixes those before any number is looked up.

**How does it work?**
**Level 1 - Beginner:** Rooms are sorted by danger: the HV bus (850 V), the LV bus (450 V) and the
control electronics (24 V, which a technician may touch through the service port). Between a
dangerous room and a touchable room the wall must survive one failure - "reinforced" - which in
practice means twice the distance or a certified double barrier. Between two dangerous rooms that
nobody touches, a single "basic" wall is enough, provided each room is protected separately.
**Level 2 - Engineering:** HV port and bridge: 850 V DC max (nominal 800 V), floating, not accessible
(enclosure, tool access): DVC C. LV port and bridge: 450 V DC, floating: DVC C. Gate-drive secondary
sides: at switch-node potential (0-850 V / 0-450 V). Control, DSP, CAN, 24 V aux: DVC A (SELV / PELV),
earthed at one point, accessible (connectors, service port). Heat sinks, core, chassis: PE,
accessible. Consequences (IEC 62477-1 4.4.7): reinforced (or double) insulation between either power
circuit and the control circuit; basic insulation between HV and LV (both DVC C, both inaccessible,
"the system must provide protection on each"); basic insulation to PE for each power circuit.
Requirement SAF-01 in `00_Requirements/01_requirements_specification.md` says the same and notes
that the user brief's single "3 kVrms" figure is reviewed in the study.
**Level 3 - Research:** The subtle point is the gate-drive secondary sides: eight floating circuits
that follow their switch nodes, each needing reinforced isolation to the control side through its
driver and its bias module. The study flags the bias modules (RECOM R12P2 / Murata MGJ2 class,
5.2 kVDC / 1 min, "basic-class component") as an open item: a reinforced-rated module or a
transformer-based bias with reinforced construction is required. The FTA (below) shows why this is
the single most important decision: the bias-module isolation is 50 % of the top-event frequency
for hazardous voltage at an accessible part.

**Example from our converter:** Test voltages derived from the pairs: HV-LV 2.5 kVrms 60 s (type) or
1 s routine, or 3.5 kV DC; HV-control 4.0 kVrms 60 s; LV-control 3.0 kVrms; HV-PE 2.5 kVrms, LV-PE
1.5 kVrms; partial-discharge extinction > 1.1 x working peak for the reinforced barriers
(`01_insulation_coordination.md` section 5; test step 3 in `20_Experimental_Test_Plan/test_plan.md`:
"2.5 kVrms HV-LV 60 s; 4 kVrms HV-CTRL; 3 kVrms LV-CTRL; PE bonding < 0.1 Ohm", leakage < 1 mA).
`[Proposed]` (a test procedure).

**Engineering calculations:** System voltage class: the next step above 850 V DC is the 1000 V class;
rated impulse withstand for OVC II 4 kV, for OVC III 6 kV. Reinforced insulation uses the clearance
of the next higher impulse level (6 kV -> 5.5 mm) and twice the creepage of basic insulation
(2 x 6.0 = 12 mm for group II, 2 x 8.5 = 17 mm for group IIIa at 850 V).

**Design decision made in this project:** The control circuit is designed as an SELV island with
reinforced isolation on every path from either power circuit (drivers, bias modules, isolated
amplifiers, isolated 5 V supplies, CAN isolator as an upgrade), and the single brief figure of 3 kVrms
is replaced by pair-specific test voltages. `[Implemented]` as a design rule.

**Alternatives considered:** Treating the whole converter as inaccessible (no SELV requirement;
rejected because the service port and connectors are touchable); double insulation by two basic
components in series (the study notes that two bias modules in series "are not used").

**How to verify it:** Review of the circuit table by an independent engineer (SAF-08, section 7 of
the study: no energisation before that review); hipot and PD type tests on the assembled board.
`[Not yet tested]`

**Common mistakes:** Assigning SELV to a circuit that is referenced to a power bus through a sensing
divider (the project uses isolated amplifiers precisely to avoid this); assuming "basic" between HV
and LV is enough without the system-level protection on each port; forgetting the PE-to-winding
insulation of the transformer core (core bonded to PE: basic to both windings).

**Interview explanation (30 s):** "Two power circuits at 850 and 450 V, DVC C, inaccessible; one SELV
control circuit, DVC A, accessible. So: reinforced from each power circuit to control, basic HV-LV and
basic to PE. Test voltages 4 kV, 3 kV and 2.5 kV rms respectively, not the single 3 kV of the brief.
The eight floating gate-drive secondaries make the bias modules the critical components."

**Research-level explanation:** Insulation coordination of multi-port isolated converters is a
graph problem - circuits as nodes, insulation types as edges - and the project's open item (basic-class
bias modules) is a missing reinforced edge that the FTA identifies as the dominant hazard path.

### Overvoltage category, pollution degree, altitude and material group

**What is it?** The environmental inputs of IEC 60664-1 as fixed in section 2 of the study: pollution
degree 2 (cabinet, no conductive pollution), overvoltage category II assumed for the DC ports
(sources are converters with surge limitation), altitude <= 2000 m (APP-07; correction factor 1.29 on
clearances for 4000 m), material group II for FR4 with CTI >= 400 (IIIa if only CTI >= 175 is
guaranteed). `[Implemented]` as assumptions.

**Why do we need it?** Each input moves a table column: OVC sets the impulse voltage (4 kV vs 6 kV),
pollution degree sets the creepage row, the material group sets the creepage column, altitude scales
the clearance.

**How does it work?**
**Level 1 - Beginner:** Dirt and humidity make surfaces conductive (pollution degree); lightning and
switching surges set how big a spike the air gap must survive (overvoltage category); thin air at
altitude breaks down more easily (altitude correction); some plastics track more easily than others
(material group). Each assumption makes the required distance larger or smaller.
**Level 2 - Engineering:** OVC II at 1000 V system voltage: 4 kV impulse; clearance for 4 kV in an
inhomogeneous field at PD2: 3.0 mm; for 6 kV (reinforced, or OVC III): 5.5 mm. Creepage at 850 V,
PD2: 6.0 mm (group II) / 8.5 mm (group IIIa); at 450 V: 3.2 / 4.5 mm. If the HV bus were fed from a
mains rectifier without surge limitation, OVC III would apply and the impulse level would step from
6 kV to 8 kV for the 1000 V class - "clearances below would then need recalculation". The stack-up
specifies FR4 with CTI >= 400 (`17_Manufacturing/stackup.md`; MEC-02 in the requirements), i.e.
material group II, and the study designs for the IIIa column anyway (17 mm reinforced creepage
against a 16 mm barrier plus slots).
**Level 3 - Research:** The study is explicit that its table values are "recalled from the standard's
tables (F.1, F.2, F.4, F.5) and must be re-checked against the current edition before release". This
is the correct research posture: the method is reproducible, the constants are flagged. A second
research-level question is the DC working voltage: IEC 60664-1 creepage tables are written for rms
values and the treatment of DC with ripple, and of the 100 kHz square voltage on the gate-drive
barriers (high-frequency stress, partial discharge), goes beyond the base tables - the magnetics
design notes that "partial-discharge inception is not expected below 1 kV peak across 150 um
polyimide but must be tested".

**Example from our converter:** APP-07: "<= 2000 m without derating; 2000-4000 m with clearance
correction factor per IEC 60664-1 Table A.2 (1.29 at 4000 m) and 10 % power derating per 1000 m"
(`00_Requirements/01_requirements_specification.md`). `[Implemented]` as a requirement.

**Engineering calculations:** Altitude scaling of the reinforced clearance: 5.5 mm x 1.29 = 7.1 mm
at 4000 m - still far inside the 16 mm barrier; the 3.0 mm basic clearance becomes 3.9 mm, inside
the 8.5 mm PE rule. The barrier therefore has altitude margin; the component packages (8 mm driver
creepage) are the tighter constraint.

**Design decision made in this project:** PD2, OVC II, <= 2000 m, group II material but designed to
the IIIa creepage column. `[Implemented]`

**Alternatives considered:** OVC III (would require 5.5 mm basic clearance and 8 kV reinforced
impulse - the study records the consequence); conformal coating as a means to claim PD1 (the
manufacturing notes specify acrylic coating 50 um over the HV and LV regions, but the study does not
take credit for it in the tables).

**How to verify it:** Re-check of the table values against the standard (study section 3 heading:
"recalled table values, to verify"); CTI of the chosen laminate from the fabricator's data sheet;
the DRC rules carry the resulting numbers (chapter 11). `[Not yet tested]`

**Common mistakes:** Taking the OVC from the equipment class instead of from the port's source;
mixing the rms-based creepage table with DC peak values without care; claiming a material group
from "FR4" without a CTI figure.

**Interview explanation (30 s):** "Pollution degree 2 in a cabinet, overvoltage category II on the DC
ports, altitude to 2000 m, FR4 with CTI 400 - group II, but we design to the group IIIa creepage
column for margin. That gives 4 kV basic and 6 kV reinforced impulse levels, 3.0 and 5.5 mm
clearance, 6-8.5 mm basic and 12-17 mm reinforced creepage at 850 V - with the standard's tables
still to be re-checked before release."

**Research-level explanation:** The high-frequency, DC-biased stress across the gate-drive barriers
is where the base tables are least adequate; PD testing at > 1.1 x working peak is the project's
answer, and the literature on HF insulation ageing of PCB-embedded barriers is the research context.

### Required distances and how the board implements them

**What is it?** Table 3 of the study (required clearance and creepage per circuit pair and the
design value used) and the corresponding board features: the 16 mm barriers, the 12 / 10 / 8 /
5.5 mm DRC rules, the 8.5 / 5.0 mm PE rules, the milled slots under the SIP modules, the SIP-7 outline
for PS9/PS10 (`01_insulation_coordination.md` sections 3-4; `dabtools/kicad_dab/gen_pcb_dab.py`
`pair_clearance()`, `slots`; `07_KiCad_Schematics/SiC_DAB_6k6.kicad_dru`). `[Implemented]` and
`[Verified]` by DRC for the clearance part.

**Why do we need it?** A distance that lives only in a document is not a design; the project's
method is to make every distance a DRC rule, so that the generated board cannot violate it without
the checker saying so.

**How does it work?**
**Level 1 - Beginner:** The required gaps are written into the board checker as rules: "any HV
copper must stay 12 mm from any LV copper", "any power copper must stay 12 or 10 mm from control
copper", "earth copper must stay 8.5 mm from HV". Where a small component cannot provide the gap
between its own pins, a slot is milled through the board under it, so the surface path becomes
longer.
**Level 2 - Engineering:** Table 3 (clearance / creepage required, design value): HV-PE basic,
4 kV, 3.0 mm / 6.0-8.5 mm, design 8.5 mm (slot/edge), 3.5 mm minimum clearance; HV-LV basic, 3.0 mm /
6.0-8.5 mm, design 9.0 mm (PCB barrier, rule area), 9.0 mm clearance; LV-PE basic, 2.5 kV, 1.5 mm /
3.2-4.5 mm, design 5.0 mm; HV-control reinforced, 6 kV, 5.5 mm / 12-17 mm, design 16.0 mm barrier,
component rating at isolator footprints; LV-control reinforced, 4 kV, 3.0 mm / 6.4-9 mm, design
10.0 mm; gate-drive secondary to control: isolator plus bias-module rating plus PCB slot; within the
HV circuit (functional): 1.0 mm track/pour, TO-247 pin pitch 2.54 mm (0.64 mm pad gap with coating).
The DRC file (chapter 11) enforces: `iso_hv_lv` 12.0 mm (more than the 9.0 mm design value of
table 3, because the board's barrier is 16 mm and the HV-LV pairs only meet across a barrier plus
the control region), `iso_hv_power_ctrl` 12.0, `iso_lv_power_ctrl` 10.0, `iso_gate_signal` 8.0,
`iso_gate_bias_modules` 5.5, `pe_to_hv` 8.5, `pe_to_lv` 5.0, `hv_to_hv` and `lv_to_lv` 1.5 (above the
1.0 mm functional value), `power_to_gate` 0.5 mm. Slots: 1.6 mm wide, 8 mm long, centred in the pin
gap of each SIP-7 bias module PS1-PS8 (between pins 2 and 5) and of the 1 W modules PS9/PS10
(between positions 2 and 6), at least 2 mm from the pads (`gen_pcb_dab.py` `slots`). PS9/PS10: a
2.54 mm pitch SIP-4 part (R1SE class) was rejected because its pad-to-pad spacing (< 1 mm) cannot
meet the 5.5 mm module rule; the footprint is `SIP-7_IsoDCDC_1W` with a >= 7.6 mm pin gap and a
milled slot (`dabtools/kicad_dab/libs_dab.py`, footprint description; `16_BOM/bom.md` rows PS9/PS10,
part "TBD, reinforced-rated part to be selected").
**Level 3 - Research:** The barrier is wider than any table requires, so the real questions are
local: the straddler cut-outs, where the certified package creepage (8 mm on the SOIC-16W drivers)
is extended by the slot to > 12 mm, and the TO-247 pin field, where 0.64 mm pad gaps at 850 V
working voltage rely on conformal coating (IPC-2221 B4 0.6 mm external coated). Both are places where
a field calculation and a PD test would add knowledge that no table gives.

**Example from our converter:** "the PCB creepage between pin rows (~8.5 mm) relies on the certified
component; a 1.6 mm slot is routed under each driver to raise the PCB creepage to > 12 mm"
(`01_insulation_coordination.md` table 4, driver row). On the generated board the slots are placed
under the bias modules (PS1-PS10); the driver footprints U1-U4 are in barrier cut-outs with their
pads spread across the 16 mm strip. `[Implemented]`

**Engineering calculations:** Creepage gained by a through-slot of width w and board thickness t:
the surface path goes down one wall and up the other, adding 2 t = 4.8 mm for the 2.4 mm board, so a
5.9 mm pin gap minus the 1.6 mm slot plus 4.8 mm = 9.1 mm along the surface, and more if the pads are
set back from the slot edges (the generator keeps >= 2 mm): the study's "> 12 mm" figure assumes the
set-back is counted. PE-to-HV rule 8.5 mm equals the group IIIa basic creepage at 850 V; the 3.5 mm
minimum clearance of table 3 is above the 3.0 mm requirement.

**Design decision made in this project:** Distances as DRC rules, barriers as rule areas on all
layers, slots under all SIP modules, SIP-7 outline for the 1 W modules, three PE nets. `[Implemented]`
and `[Verified]` (zero clearance violations in every DRC run quoted in chapter 11).

**Alternatives considered:** Narrower barrier (12 mm would meet group II reinforced creepage, but
not IIIa); no slots with reinforced-rated modules of larger pin gap (a part-selection problem the BOM
still carries as open); potting the module area (service and inspection drawbacks).

**How to verify it:** KiCad DRC (`07_KiCad_Schematics/drc_summary.json`: 0 errors in run 27);
surface creepage must be measured on the fabricated board (the slots are Edge.Cuts features);
hipot and PD tests of test step 3. `[Verified]` / `[Not yet tested]`

**Common mistakes:** Measuring creepage straight across a slot; forgetting that solder mask does not
count as insulation for creepage; letting a component's own pin spacing (SIP-4) define the barrier.

**Interview explanation (30 s):** "Every insulation distance is a DRC rule written by the generator:
12 mm HV-LV and HV-control, 10 mm LV-control, 8 mm gate-to-signal, 5.5 mm at the bias modules with a
1.6 mm milled slot that stretches the surface path past 12 mm, 8.5 and 5 mm to earth. The barriers
are 16 mm copper-free on all six layers, more than the 17 mm-minus-slot reinforced creepage for the
worst material group. The DRC passes with zero clearance violations."

**Research-level explanation:** Table-based coordination gives sufficient conditions; the project's
remaining uncertainty is concentrated at the straddler cut-outs and the TO-247 pin field, which are
candidates for field simulation and PD testing before an independent reviewer signs the energisation
release.

### Isolating components across the barriers and the open item

**What is it?** Table 4 of the study: the components whose bodies cross the barriers and their
isolation ratings - gate drivers (listed as UCC21710, 5.7 kVrms reinforced, 8 mm package creepage),
isolated gate bias modules (8 x 2 W, +15 / -4 V, R12P2 / MGJ2 class, 5.2 kVDC basic class - open
item), AMC1311 (7 kVpk reinforced, listed; the schematic uses AMC1301 DWV), PS9/PS10 (to be selected,
reinforced, SIP-7), CT (one-turn triple-insulated wire, 8 mm), CAN isolator ISO1042 (5 kVrms, listed as
an upgrade of the non-isolated TCAN332 in the schematic), transformer (basic, 3 x 50 um polyimide,
6 mm margins, 2.5 kVrms test) (`01_insulation_coordination.md` section 4;
`dabtools/kicad_dab/design_dab.py`; `16_BOM/bom.md`). `[Implemented]` in the schematic with the
noted differences.

**Why do we need it?** Across a barrier the PCB cannot provide the distance; the component must, and
only a certified rating (VDE 0884-11 / UL 1577 for the drivers) can be cited for reinforced insulation.

**How does it work?**
**Level 1 - Beginner:** Where a signal or a supply must cross the wall, you use a certified door:
a chip with an internal insulating layer rated for the voltage, or a small transformer in a module.
If the door is only rated for "basic", the wall is not reinforced any more, however wide the gap
around it.
**Level 2 - Engineering:** The schematic database (`design_dab.py`) instantiates UCC21520DW drivers
("5.7 kVrms reinforced isolated dual gate driver ... DESAT-type driver (UCC21710) is the documented
upgrade path"), R12P21503D bias modules (BOM: "basic-class isolation; reinforced-rated module is an
open item, see 15.1"), AMC1301DWV isolated amplifiers for V1, V2 and the LV shunt (U5-U7), PS9/PS10
as "ISO 5V/5V 1W SIP-7, TBD", a TCAN332 non-isolated CAN transceiver ("ISO1042 is the upgrade for a
galvanically isolated bus"). The study's table was written against the intended parts (UCC21710,
AMC1311); the generated schematic uses UCC21520 and AMC1301. Both driver types carry the same 5.7 kVrms
reinforced rating class, so the insulation argument holds; the functional difference (DESAT) belongs
to the protection topic below. The bias modules are the real gap: eight basic-class parts on the
reinforced HV-control and LV-control paths.
**Level 3 - Research:** The FTA quantifies the gap with its class-value rates: the ISO_BIAS basic
event alone is 50 % of TE1 (hazardous voltage at an accessible part), ISO_DRV 25 %, ISO_AMC 22 %,
ISO_PCB 3 % (`Advanced_Research_2026/Reliability_Engineering/results/fta_cutsets.md`). Even with a
reinforced-rated module the single-component cut sets remain first order; the research-level answer
is either true double insulation (two independent barriers in series on each path) or a monitored
barrier (insulation-resistance supervision on the control side), neither of which is in the design.

**Example from our converter:** Bias module footprint `SIP-7_IsoDCDC` with the slot between pins 2
and 5 (`gen_pcb_dab.py` comment on `slots`); pin map of PS1: 1 +12V, 2 GND (control side), 5 VEE_Q1,
6 KS_Q1, 7 VDD_Q1 (gate side) (`design_dab.py`). `[Implemented]`

**Engineering calculations:** Reinforced requirement for HV-control at OVC II: 6 kV impulse, 4 kVrms
type test; the driver's 5.7 kVrms rating exceeds it; a 5.2 kVDC / 1 min module rating is roughly a
3.7 kVrms-equivalent withstand and is classified basic by its manufacturer - the number is not the
issue, the certification class is.

**Design decision made in this project:** Keep the basic-class module in the BOM with the open-item
flag, specify the SIP-7 outline and slot so that a reinforced-rated part of the same outline can
replace it, and name the reinforced CAN isolator and the DESAT driver as upgrade paths.
`[Implemented]` / open.

**Alternatives considered:** Transformer-based gate bias with reinforced construction (one bias
transformer per bridge, the study's second option); bootstrap supplies for the high-side gates (not
usable for the negative turn-off bias and the DAB's duty); optical gate drive (cost).

**How to verify it:** Component certificates (VDE 0884-11 reports) at the review; type tests of
section 5; the FTA's importance ranking as the review agenda. `[Not yet tested]`

**Common mistakes:** Reading "5.2 kVDC" as reinforced; assuming the PCB slot can upgrade a basic
component to reinforced; forgetting the sensor-side 5 V supplies (PS9/PS10) as barrier crossers.

**Interview explanation (30 s):** "Barrier crossers: drivers at 5.7 kVrms reinforced, isolated
amplifiers at 7 kVpk reinforced, the CT with triple-insulated wire, the transformer at basic 2.5 kVrms,
and eight gate-bias modules that are only basic class - the open item of the safety review. The FTA
puts half of the accessible-voltage hazard on exactly those modules."

**Research-level explanation:** In a multi-barrier converter the weakest certified component defines
the insulation class of the whole path; quantitative FTA with importance measures is the tool to
rank the components for upgrade and to argue for double or monitored barriers.

### Protection coordination: hardware, firmware, system

**What is it?** The three-line protection table of the study (section 6) and its numbers from the
design calculation and the firmware: shoot-through / short circuit, inductor over-current, DC-link
over-voltage, loss of gate bias, over-temperature, loss of control or communication, residual energy,
precharge failure (`01_insulation_coordination.md` section 6; `04_Design_Calculations/design_report.md`
section 8; `10_Firmware/src/dab_control.h`; SAF-06 / SAF-07). `[Implemented]` in schematic and
firmware; `[Verified]` for the firmware state machine (SIL and model check).

**Why do we need it?** IEC 62477-1 requires that a single fault does not create a hazard; the project
answers with a hardware path independent of firmware (SAF-06) plus a firmware path (SAF-07) plus
system measures (fuse, contactor, chopper).

**How does it work?**
**Level 1 - Beginner:** Three guards with different reaction times: a comparator that pulls the
gates low in less than a microsecond, the controller that checks everything every ten microseconds and
latches a fault, and the fuse or the contactor outside that can take milliseconds but handles the
energy. Each guard works even if the others fail.
**Level 2 - Engineering:** Thresholds from `design_report.md` section 8: envelope peak-current limit
24 A (HV side); hardware comparator trip 32 A HV side = 64 A LV side (60 % above the worst-corner peak,
below the device pulsed rating); DC-link OV trip 900 V (HV) / 480 V (LV) in firmware, UV 600 / 280 V;
Tj model limit 150 C -> heat-sink NTC trip at 95 C. The study's table: shoot-through - DESAT (< 1 us,
soft turn-off) -> FLT wired-OR -> EPWM TZ2, firmware FLT_DRIVER latch, HV fuse 16 A semiconductor
class (I2t coordinated); inductor over-current - CMPSS on the CT signal -> TZ1 cycle-by-cycle at 32 A,
FLT_I_PK; link OV - comparator 920 V / 490 V -> TZ3, firmware FLT_V1_OV 900 V / FLT_V2_OV 480 V,
external chopper / contactor; gate-bias loss - driver UVLO (12 V) -> FLT; over-temperature - NTC 95 C
-> FLT_OT, derating from 55 C; loss of control - watchdog -> gates off, FLT_COMM after 500 ms;
residual energy - bleeders to < 60 V in 5 min (SAF-04), active discharge command; precharge - 5 s
timeout -> FLT_PRECHARGE. The schematic's hardware path is U10/U11 LM393 comparators (OC on I_L at
2.0 V = 32 A, OV on V1_SE / V2_SE) wired-OR into PROT_DIS, which disables the drivers and feeds the DSP
trip zone (`design_dab.py`, "Hardware protection" group). The firmware fault enumeration
`dab_fault_t` holds FLT_V1_OV, FLT_V1_UV, FLT_V2_OV, FLT_V2_UV, FLT_I_PK, FLT_OT, FLT_DRIVER,
FLT_HW_TRIP, FLT_COMM, FLT_PRECHARGE; the state machine ST_INIT, ST_PRECHARGE_WAIT, ST_SOFTSTART,
ST_RUN, ST_FAULT (`dab_control.h`).
**Level 3 - Research:** One honest discrepancy must be stated: the study's first line against
shoot-through is the driver's DESAT detection, and the FMEA row "HV SiC MOSFET short" cites "DESAT
soft turn-off < 1 us" as mitigation, but the rev A schematic uses UCC21520 drivers without DESAT (the
UCC21710 is "the documented upgrade path"). The reliability module treats this correctly as a
"house" event NO_DESAT ("rev A: no DESAT driver"), and every leading cut set of TE2 contains it:
Fussell-Vesely importance 1.00. In rev A, a device short is therefore caught only by the CT
comparator (if the inductor current rises through 32 A) and by the fuse. The FMEDA-lite's DESAT_SC
function row shows DC = 0 for the same reason. This is the clearest example in the repository of a
document-level claim that the quantitative model exposes.

**Example from our converter:** Test step 5 of `20_Experimental_Test_Plan/test_plan.md`: inject
I_L and V1_SE / V2_SE signals without link voltage; expected PROT_DIS at 2.0 V (32 A), 920 V, 490 V;
TZ latches, FLT LED, telemetry; "all trips within 1 us (hardware) / 10 us (firmware)". `[Proposed]`

**Engineering calculations:** Comparator threshold: CT 1:100 into its burden gives 2.0 V at 32 A;
the OV comparator references 920 V on V1_SE against the firmware's 900 V so that the firmware trips
first on a slow rise and the comparator catches a fast one. Time scales: hardware < 1 us, firmware
10 us (control period 100 kHz = 10 us), fuse milliseconds, contactor tens of milliseconds.

**Design decision made in this project:** Hardware trips independent of the firmware (SAF-06), a
latched firmware fault state with all gates off, and the DESAT driver deferred to a revision.
`[Implemented]`; the DESAT line `[Proposed]`.

**Alternatives considered:** DESAT drivers in rev A (the pin-compatible upgrade exists); shunt-based
OC on the HV side (the CT was chosen for isolation); redundant AMC channels for OV (the FMEDA shows
both the hardware and firmware OV use the same AMC1301 channel - a common-cause weakness, DC 35 %).

**How to verify it:** Firmware: 30 SIL checks pass (`Advanced_Research_2026/Reliability_Engineering/results/state_machine_report.md`,
SIL harness line; chapter 09) `[Verified]`; model check below `[Verified]`; hardware: test step 5
`[Not yet tested]`.

**Common mistakes:** Letting the firmware be the only OC path; sharing one sensor between the
hardware and firmware OV trips without a plausibility check (the FMEDA flags it); setting the
hardware OV above the capacitor rating (920 V against 1100 V parts is fine).

**Interview explanation (30 s):** "Protection is three lines: LM393 comparators trip the drivers and
the DSP trip zone within a microsecond at 32 A and 920 / 490 V; the firmware checks OV, UV, peak
current, temperature, driver fault, communication and precharge every 10 us and latches a fault
state; the fuse and the contactor handle the energy. Rev A has no DESAT - the FTA shows that every
leading shoot-through cut set contains that gap."

**Research-level explanation:** Protection coordination is a timing and independence argument; the
FMEDA's diagnostic-coverage figures (35-47 %) and the FTA's NO_DESAT importance give the review a
quantitative agenda: add DESAT, break the common AMC channel, add a plausibility check.

### Earthing, PE bonding, precharge and discharge

**What is it?** The protective-earth structure (three PE nets, heat sinks and enclosure bonded, PCB
mounting holes bonded to the chassis - SAF-05), the precharge interface (relay driver outputs,
opto-coupled feedback, 5 s timeout) and the residual-energy discharge (bleeder chains R1-R4 on the HV
link, R5-R6 on the LV link; SAF-04: < 60 V within 5 min passively, < 10 s by external active
discharge) (`01_insulation_coordination.md` sections 4 and 6; `design_dab.py`; `16_BOM/bom.md`;
`design_values.json` `dclink`). `[Implemented]` with one calculation discrepancy noted below.

**Why do we need it?** Touchable metal must be at earth potential even under a fault (basic
insulation to PE plus bonding); the link capacitors store energy that must be removed before service;
precharge limits the inrush into 80 / 120 uF of film capacitance.

**How does it work?**
**Level 1 - Beginner:** Everything metal that can be touched is tied together and to the earth
wire, so a fault blows the fuse instead of raising the case to 850 V. After switch-off, resistors
slowly drain the capacitors, like letting the air out of a tyre; before switch-on, a small resistor
path fills them gently before the main contactor closes.
**Level 2 - Engineering:** PE: J21 (PE_HV, Y-capacitor return, bonded to the HV heat sink), J20 (PE,
control region, with the single-point GND bond R173), J22 (PE_LV); bonding resistance test < 0.1 ohm
(test step 3). Precharge: two relay driver outputs (ULN2003), PC817 opto inputs for precharge-complete
feedback and external enable (`design_dab.py`, "Precharge / contactor interface"), firmware
ST_PRECHARGE_WAIT with a 5 s timeout to FLT_PRECHARGE. Discharge: the design calculation sizes the HV
bleeder at 1.41 Mohm (0.51 W at 850 V) and the LV bleeder at 1.24 Mohm (0.16 W), each "discharges to
< 60 V in 5 min" (`design_report.md` section 7; `design_values.json` `dclink.R_bleed1`,
`R_bleed2`). The BOM, however, lists the HV chain as 4 x 680 kohm = 2.72 Mohm (R1-R4, 2512, 212 V
per resistor) and the LV chain as 2 x 1 Mohm = 2 Mohm (R5, R6) (`16_BOM/bom.md`).
**Level 3 - Research:** Working the BOM values through the time constant: HV tau = 2.72e6 x 80e-6 =
218 s, time to 60 V = tau x ln(850 / 60) = 218 x 2.65 = 577 s = 9.6 min; LV tau = 2e6 x 120e-6 =
240 s, time to 60 V = 240 x ln(450 / 60) = 240 x 2.01 = 484 s = 8.1 min. Both exceed the 5 min of
SAF-04, whereas the design values (1.41 / 1.24 Mohm) give 299 s and 300 s. The schematic database
and the BOM therefore do not implement the calculated bleeder; this is an inconsistency between
`04_Design_Calculations` and `dabtools/kicad_dab/design_dab.py` that the notes record as an open
item for the review (the fix is 2 x 680 k in series per two resistors, or 4 x 330 k, with the per-
resistor voltage re-checked against the 500 V rating).

**Example from our converter:** Film capacitance HV 80 uF at 850 V stores 0.5 x 80e-6 x 850^2 =
28.9 J; LV 120 uF at 450 V stores 12.2 J. An active discharge to < 10 s needs an external resistor
of about R = 10 s / (ln(850/60) x 80e-6) = 47 kohm with 15 W average over the first seconds - the
"external active discharge (interface signal)" of SAF-04. `[Implemented]` as an interface;
`[Proposed]` as hardware.

**Engineering calculations:** Bleeder dissipation at the BOM values: 850^2 / 2.72e6 = 0.27 W (HV),
450^2 / 2e6 = 0.10 W (LV) - lower than the design's 0.51 / 0.16 W because the resistance is higher;
the voltage per resistor 212 V (HV) and 225 V (LV) against 500 V rated 2512 parts.

**Design decision made in this project:** Passive bleeders on board plus an external active
discharge; PE lug per region; precharge by external contactor with on-board relay driver and
feedback interlock. `[Implemented]`

**Alternatives considered:** On-board active discharge (switch plus power resistor - thermal and
space cost); a single PE lug (rejected by the barrier rule); precharge resistor on board (external by
system design).

**How to verify it:** Bonding resistance test and discharge-time measurement (test step 3 and the
energisation sequence of section 7); the bleeder arithmetic above can be verified from the two files
today. `[Not yet tested]`

**Common mistakes:** Specifying a bleeder by power only and forgetting the time constant; counting
the LV side's lower voltage as "safe" (450 V is DVC C); bonding the control ground at more than one
point (EMC and safety interact here, chapter 13).

**Interview explanation (30 s):** "Three PE lugs bonded through the chassis, heat sinks on PE, a
single control-ground bond; precharge through an external contactor with feedback and a 5 s
timeout; bleeders to below 60 V in 5 min plus an external active discharge. One finding: the BOM's
bleeder chains (2.72 and 2 Mohm) give 9.6 and 8.1 min by the time constant, while the design
calculation asked for 1.41 and 1.24 Mohm - an open item."

**Research-level explanation:** Safety requirements must be traced from calculation to BOM
automatically; the bleeder discrepancy is a traceability failure that a requirements-to-BOM check
(like the netlist and DRC checks of chapter 11) would catch, which is the kind of tool the
verification module (chapter 19) should grow.

### The FMEA: structure and the highest-RPN items

**What is it?** The design FMEA of rev A: 19 rows with item, failure mode, effect, detection /
mitigation, severity S, occurrence O, detection D (1-10 each, "10 = undetectable"), RPN = S x O x D
and notes / open items; RPN > 60 items carry an action (`15_Safety_Reliability/02_FMEA.md`;
machine-readable `02_FMEA.csv` with the same columns). `[Implemented]` as analysis ("engineering
judgement, no field data").

**Why do we need it?** It is the systematic list of what can fail and what then happens; it feeds
the protection coordination, the test plan and - in the 2026 module - the fault tree and the FMEDA.

**How does it work?**
**Level 1 - Beginner:** For each part you ask three questions: how bad is it if it fails this way,
how likely is that, and would we notice in time? Multiply the three scores; the biggest products are
where to put effort.
**Level 2 - Engineering:** The ranked rows: HV SiC MOSFET short circuit - shoot-through, DC-link short,
fuse operation, possible case rupture; mitigation DESAT soft turn-off, semiconductor fuse, 850 / 1200 V
margin, derated Tj; S8 O2 D6, RPN 96; note "add explosion-safe enclosure". Current transformer open
secondary / drift - loss of OC protection; burden on PCB, plausibility check vs power model in
firmware; S7 O2 D6, RPN 84; "firmware plausibility check is an open item". Connectors / bus bars loose
joint - hot spot, arcing; torque spec, thermal inspection; S7 O2 D6, RPN 84. DC-link film capacitor
loss of capacitance - ripple increase, EMI, OV trip; 77 % derating, < 60 C, capacitance monitoring via
ripple; S4 O3 D6, RPN 72. AMC1311 drift / fail-low - wrong regulation, OV undetected by firmware;
independent hardware OV comparator; S8 O2 D4, RPN 64. Gate driver UVLO / supply loss - S7 O3 D3,
RPN 63. HV MOSFET open (bond-wire lift) and series inductor overheating - RPN 60 each. The
safety-critical rows have low RPN because O = 1: driver isolation breakdown (S10 O1 D4, 40), bias
module isolation breakdown (40, "open item 15.1-4"), transformer interwinding failure (S9, 45), PCB
contamination / creepage reduction (S9 O1 D6, 54). The reliability assessment refuses an MTBF: "a
parts-count prediction (IEC 61709 / MIL-HDBK-217F) requires the final BOM with manufacturer FIT
data"; dominant contributors expected: film capacitors, the eight bias modules, the fans.
**Level 3 - Research:** RPN is known to hide severity-10 items behind low occurrence scores - exactly
what happens here, where the S10 isolation rows score 40 while a loose connector scores 84. The 2026
module answers with a fault tree, where the isolation events become first-order cut sets of TE1 and
dominate it, and with an FMEDA that classifies failures as safe, dangerous-detected and
dangerous-undetected per protection function. The FMEA also carries a row that the schematic does not
support (DESAT as mitigation for the MOSFET short), see the protection topic.

**Example from our converter:** CSV header: `item,failure mode,effect,detection / mitigation,
severity(1-10),occurrence(1-10),"detection(1-10, 10=undetectable)",RPN,notes / open items`
(`02_FMEA.csv`). `[Implemented]`

**Engineering calculations:** RPN range used: 9 (CAN link loss: S3 O3 D1) to 96; the mean over the
19 rows is about 55; seven rows exceed 60 and carry actions. Changing the MOSFET-short detection
score from 6 to 3 (with DESAT, "detectable: FLT") would halve its RPN to 48 - the quantitative
argument for the driver upgrade in RPN terms.

**Design decision made in this project:** A design FMEA at rev A with explicit open items (flux
balance check, CT plausibility check, reinforced bias module, explosion-safe enclosure, fan
tachometer), and no MTBF claim. `[Implemented]`

**Alternatives considered:** Process FMEA (manufacturing) - not yet; FMECA with criticality from FIT
data - deferred to the FMEDA-lite with class values.

**How to verify it:** The FMEA is reviewed, not tested; its actions become test-plan items (steps 5,
11, 13) and firmware features. `[Not yet tested]` for the actions.

**Common mistakes:** Ranking only by RPN and ignoring S = 10 rows; scoring detection for a diagnostic
that the schematic does not contain; omitting the "no field data" caveat.

**Interview explanation (30 s):** "Nineteen rows, S x O x D. Top of the list: MOSFET short at 96,
CT failure and loose connectors at 84, film-capacitor ageing at 72, sensor drift at 64. The
severity-10 isolation failures score only 40 because occurrence is 1 - which is why the 2026 module
re-does the analysis as a fault tree, where those same items dominate the hazardous-voltage top
event."

**Research-level explanation:** The FMEA is the qualitative input; its quantitative successors
(FTA with importance measures, FMEDA with diagnostic coverage, exhaustive state-machine checking) are
the research-grade safety argument, and the repository provides all three with explicit assumptions.

### Formal safety analysis (Level 3): FTA, FMEDA-lite, state-machine verification

**What is it?** `Advanced_Research_2026/Reliability_Engineering/`: `fta.py` (three top events,
minimal cut sets by boolean expansion, rare-event quantification, Fussell-Vesely importances),
`fmeda_lite.py` (protection functions with S / DD / DU classification, diagnostic coverage, safe
failure fraction), `sm_conformance.c` (drives the unmodified firmware core through every state and
abstract input combination), with results and provenance files in `results/`. `[Simulated]` /
`[Verified]` for the model check.

**Why do we need it?** The FMEA ranks; it cannot combine failures, cannot quantify a hazard rate and
cannot prove a property of the firmware. The three tools do exactly those three things, with every
rate declared an assumption.

**How does it work?**
**Level 1 - Beginner:** A fault tree asks "which combinations of failures lead to this hazard?" and
how often each combination happens. An FMEDA asks "if this protection circuit fails, do we notice?".
A state-machine check tries every possible input in every state of the controller and confirms rules
like "once in FAULT, the gates stay off".
**Level 2 - Engineering:** FTA (`results/fta_cutsets.md`): TE1 hazardous voltage at an accessible
part - 6 minimal cut sets, lowest order 1, 1.40e-4 per year, P(10 y) = 1.4e-3; cut sets ISO_BIAS
50.0 %, ISO_DRV 25.0 %, ISO_AMC 21.9 %, ISO_PCB 3.1 %, then second- and third-order sets at 1e-9 and
below (DEV_PAD and PE_BOND; ACCESS and ACT_DIS and BLEED). TE2 uncontrolled energy / over-current not
interrupted in time - 21 cut sets, lowest order 2, 1.93e-4 per year; leading sets DRV_HIGH and
NO_DESAT 36 %, MCU and NO_DESAT 23 %, NO_DESAT and XTALK 23 %, DRV_UVLO_LOSS and NO_DESAT 18 %;
importance NO_DESAT 1.00. TE2b (TE2 and fuse fails to clear) 1.73e-9 per year; TE3 thermal runaway
1.68e-9 per year. Rates are "ORDER-OF-MAGNITUDE class values in the style of IEC TR 62380 / SN 29500
tables, entered as ASSUMPTIONS"; mission time 10 years, MTTR 48 h, proof-test interval 8760 h
(`fta.py` docstring). FMEDA-lite (`results/fmeda_summary.json`): OV_HV lambda_S 6.5, lambda_DD 19.9,
lambda_DU 36.8 FIT, DC 0.35, SFF 0.42; OV_LV DC 0.35; OC DC 0.38, SFF 0.45; OT DC 0.47; INTERLOCK
DC 0.0, SFF 0.69; DESAT_SC DC 0.0, SFF 0.73 (no DESAT in rev A); "NO SIL claim, no PFD/PFH target".
State-machine check (`results/state_machine_report.md`): 5 reachable states, 46,080 transitions
checked; P1_literal FAIL with 456 violations (INIT with v1_low / v2_low / comm_lost inputs - the
literal reading of "any fault input leads to FAULT" is not how INIT behaves, by design) while
P1_conditional, P2_fault_latched, P3_gates_off_outside_run_softstart, P4_no_deadlock,
P5_gates_imply_enable all PASS; C-code conformance of `sm_conformance.c` against the unmodified
`10_Firmware/src/dab_control.c`: PASS, 46,080 cases, 0 mismatches; the Python reference controller
differs from the C model in 71 mismatch classes (e.g. INIT with driver_fault: C goes to FAULT, Python
stays in INIT) - a documented divergence between the two implementations; the SIL harness passes
30 of 30.
**Level 3 - Research:** Three observations for the researcher. First, the FTA's TE1 is dominated by
first-order cut sets, which means no amount of protection logic helps - only better barriers (double
or monitored) move the number. Second, TE2's NO_DESAT importance of 1.00 is a design statement, not a
statistic: the house event is on. Third, the model check's P1_literal failure and the Python-vs-C
mismatch list are the kind of result that makes exhaustive checking worthwhile - they show where the
specification was ambiguous and where two implementations of "the same" controller diverge. The
module claims no SIL and no certification, and says so in its docstrings.

![FTA cut sets](../Advanced_Research_2026/Reliability_Engineering/results/fig_fta_cutsets.png)

**Example from our converter:** FMEDA row "OV_HV / isolated 5 V PS9 / output loss / 20 FIT /
AMC output to common-mode level: reads mid-scale / DU / mid-scale reading is inside the UV/OV window"
(`fmeda_lite.py` `ROWS`): a supply failure that silently disables both the hardware and firmware
OV trips - the kind of dangerous-undetected mode the method is designed to find. `[Simulated]`

**Engineering calculations:** Diagnostic coverage DC = lambda_DD / (lambda_DD + lambda_DU) = 19.9 /
(19.9 + 36.8) = 0.351 for OV_HV; SFF = (lambda_S + lambda_DD) / lambda_total = (6.5 + 19.9) / 63.2 =
0.418. Rare-event FTA: cut-set frequency F_c = sum_i lambda_i prod_(j != i) q_j; for a first-order
set F = lambda; TE1 = 1.40e-4 per year corresponds to 16 FIT in total across the four isolation
classes at the assumed rates.

**Design decision made in this project:** Keep the three analyses as scripts with provenance files
(`results/provenance_fta.json`, `provenance_fmeda.json`, `provenance_sm.json`) so that any rate
change re-runs the whole argument; claim nothing beyond "ranks where diagnostics are missing".
`[Implemented]`

**Alternatives considered:** Markov models for the repairable protection chain (would add
proof-test dynamics); a SIL assessment (explicitly refused: needs certified data and an independent
assessor); fuzzing instead of exhaustive enumeration for the state machine (the abstract input space
is small enough to enumerate).

**How to verify it:** Run the three scripts; the state-machine check compiles the firmware with gcc
and compares 46,080 cases (`[Verified]`); the FTA and FMEDA numbers can only be validated against
field data that does not exist (`[Simulated]`).

**Common mistakes:** Quoting the FTA frequencies as predictions (they are class-value assumptions);
reading DC = 0.35 as a SIL statement; treating the P1_literal failure as a firmware bug (it is a
property written too literally).

**Interview explanation (30 s):** "The reliability module has a fault tree - hazardous voltage at an
accessible part at 1.4e-4 per year under assumed rates, 97 % from the barrier components; energy
hazard at 1.9e-4 per year with every leading cut set containing 'no DESAT' - an FMEDA-lite with
35-47 % diagnostic coverage and no SIL claim, and an exhaustive state-machine check of the real C
code: 46,080 transitions, latching and gates-off properties pass, conformance passes."

**Research-level explanation:** Formal and quantitative safety analysis of a converter design before
hardware exists is feasible and useful when every rate is declared an assumption; the outputs that
matter are structural - importance rankings, undetected modes, specification ambiguities - and those
are what the independent review should act on.

## Worked example(s) with real numbers

**1. HV-to-control reinforced insulation.** Working voltage 850 V DC -> 1000 V system class; OVC II
-> 4 kV impulse (basic); reinforced -> next level 6 kV -> 5.5 mm clearance (PD2, inhomogeneous
field); creepage basic at 850 V, PD2: 6.0 mm (group II) or 8.5 mm (IIIa); reinforced = 2x: 12 or
17 mm. Design: 16 mm barrier on all layers plus slots; DRC rule 12 mm for HV_POWER to control; at
the driver footprint the certified 5.7 kVrms component with 8 mm package creepage plus a slot. Type
test 4.0 kVrms 60 s, PD extinction > 1.1 x 850 x (peak factor) - all `[Implemented]` as rules and
`[Not yet tested]` as withstand.

**2. Bleeder discharge time (the open item).** HV: C = 80 uF; design R = 1.41 Mohm: tau = 113 s,
t(60 V) = 113 x ln(850 / 60) = 113 x 2.65 = 299 s (5.0 min, meets SAF-04); BOM R = 4 x 680 k =
2.72 Mohm: tau = 218 s, t = 577 s (9.6 min, fails). LV: C = 120 uF; design 1.24 Mohm: tau = 149 s,
t = 149 x ln(450 / 60) = 149 x 2.01 = 300 s; BOM 2 Mohm: 240 s x 2.01 = 484 s (8.1 min, fails).
`[Simulated]` arithmetic from `design_values.json` and `16_BOM/bom.md`.

**3. RPN sensitivity to the DESAT upgrade.** MOSFET short: S8 x O2 x D6 = 96 today; with DESAT the
detection score could drop to 3 (fault flagged within 1 us): 8 x 2 x 3 = 48. In the FTA the same change
switches off the NO_DESAT house event and removes the four leading TE2 cut sets (100 % of the
quantified frequency at the assumed rates), leaving the 1e-9-class sets. `[Simulated]`

## How this chapter connects to the files

| File | What it contains | Status |
|---|---|---|
| `SiC_6k6_Industrial_DAB/15_Safety_Reliability/01_insulation_coordination.md` | circuits, DVC, OVC/PD/altitude/material, required distances, barrier components, PE bonding, test voltages, protection table, energisation policy | `[Implemented]` (analysis; table values to re-check) |
| `SiC_6k6_Industrial_DAB/15_Safety_Reliability/02_FMEA.md`, `02_FMEA.csv` | 19-row design FMEA with S/O/D/RPN and open items; reliability assessment without MTBF | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/00_Requirements/01_requirements_specification.md` | SAF-01 to SAF-08, APP-07, MEC-02 | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/04_Design_Calculations/design_report.md`, `design_values.json` | protection thresholds (24 / 32 A, 900 / 480 V, 600 / 280 V, 95 C), bleeder sizing, link energies | `[Simulated]` |
| `SiC_6k6_Industrial_DAB/dabtools/kicad_dab/design_dab.py` | drivers (UCC21520), bias modules, AMC1301, comparators, PE nets, relay/opto interface, bleeder chains | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/dabtools/kicad_dab/gen_pcb_dab.py`, `07_KiCad_Schematics/SiC_DAB_6k6.kicad_dru` | distances as DRC rules, barrier keep-outs, slots | `[Implemented]` / `[Verified]` |
| `SiC_6k6_Industrial_DAB/16_BOM/bom.md` | isolation ratings and open-item flags per part, bleeder values | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/10_Firmware/src/dab_control.h`, `10_Firmware/src/dab_params.h` | fault enumeration, states, `LIM_T_MAX_C` | `[Verified]` (SIL) |
| `SiC_6k6_Industrial_DAB/17_Manufacturing/manufacturing_notes.md` | conformal coating, production hipot sequence | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/20_Experimental_Test_Plan/test_plan.md` | step 3 insulation and bonding, step 5 protection functions, safety controls | `[Proposed]` |
| `Advanced_Research_2026/Reliability_Engineering/fta.py`, `results/fta_cutsets.md`, `results/fig_fta_cutsets.png` | three top events, cut sets, importances | `[Simulated]` |
| `Advanced_Research_2026/Reliability_Engineering/fmeda_lite.py`, `results/fmeda_summary.json` | DC and SFF per protection function | `[Simulated]` |
| `Advanced_Research_2026/Reliability_Engineering/sm_conformance.c`, `results/state_machine_report.md` | exhaustive state-machine check and C conformance | `[Verified]` |
| `21_Human_Friendly_Learning_Notes/img/make_figures_ch11_14.py` | the insulation-distance chart | `[Implemented]` |

## Viva / interview questions

### Basic (10)

1. What is the difference between basic and reinforced insulation?
   Basic protects against shock as long as it is intact; reinforced (or double) must still protect
   after one failure - roughly twice the creepage and a higher impulse level, or a certified double
   barrier.
2. Which circuit pairs need reinforced insulation here?
   HV-control and LV-control (power circuit to the accessible SELV control circuit); HV-LV and
   power-to-PE are basic.
3. What is creepage and why does pollution degree matter?
   The surface path between conductors; dirt and humidity make surfaces conductive, so PD2 requires
   longer paths than PD1.
4. How wide are the barriers and the DRC rules?
   16 mm copper-free barriers on all six layers; DRC 12 mm HV-LV and HV-control, 10 mm LV-control,
   8 mm gate-to-signal, 5.5 mm at the bias modules, 8.5 / 5 mm to PE.
5. Why are slots milled under the SIP modules?
   The modules' pin rows are only about 5.9 mm apart; the slot lengthens the surface path past 12 mm.
6. What are the three lines of protection?
   Hardware comparators (< 1 us), firmware (10 us, latched fault state), system (fuse, contactor,
   chopper).
7. What are the trip levels?
   32 A hardware OC (HV side), 920 / 490 V hardware OV, 900 / 480 V firmware OV, 600 / 280 V UV, 95 C
   heat-sink NTC.
8. What does the FMEA's RPN mean?
   Severity x occurrence x detection on 1-10 scales; items above 60 carry an action; the top item is
   the MOSFET short at 96.
9. What is the bleeder for?
   To discharge the link capacitors to < 60 V within 5 min after switch-off (SAF-04); an external
   active discharge does it in < 10 s.
10. Is the converter certified or tested for safety?
    No. The study says "nothing here is a certification", the energisation policy requires an
    independent review first, and no hardware exists.

### Intermediate (10)

1. Derive the reinforced creepage for HV-control.
   850 V, PD2: basic creepage 6.0 mm (group II) / 8.5 mm (IIIa); reinforced = twice: 12 / 17 mm; the
   design uses a 16 mm barrier plus slots and designs to the IIIa column.
2. Why is the HV-LV DRC rule 12 mm when the design value in table 3 is 9 mm?
   On this board HV and LV copper never meet directly - the control region lies between - so the
   generator uses the HV-control distance (12 mm) for the HV-LV class pair as well; 9 mm was the
   PSFB-style single-barrier value.
3. Why does OVC III change the picture?
   The impulse level steps from 4 to 6 kV (basic) and to 8 kV for reinforced; clearances would rise to
   5.5 mm basic and the reinforced value would need recalculation.
4. What is the open item on the bias modules?
   The R12P2 / MGJ2-class modules are basic class (5.2 kVDC / 1 min) on paths that must be reinforced;
   a reinforced-rated SIP-7 part or a transformer-based bias is required.
5. Explain the DESAT discrepancy.
   The study and the FMEA cite DESAT soft turn-off as the first line against shoot-through, but rev A
   uses UCC21520 drivers without DESAT; the FTA models it as a house event with importance 1.00 for
   the energy hazard.
6. Check the BOM bleeders against SAF-04.
   HV 2.72 Mohm x 80 uF: 577 s to 60 V; LV 2 Mohm x 120 uF: 484 s; both exceed 5 min, while the
   design values 1.41 / 1.24 Mohm give 300 s.
7. Why are the severity-10 FMEA rows low in RPN?
   Occurrence is scored 1 and detection 4, giving 40; RPN hides high-severity, low-occurrence
   hazards, which is why the FTA treats them as first-order cut sets.
8. What does the FMEDA's DC of 0.35 for OV_HV say?
   Only 35 % of the dangerous failure rate of the OV chain is detected by an existing diagnostic (the
   UV window in RUN); divider drift, AMC gain drift and the PS9 supply loss are undetected.
9. What does the state-machine check prove and not prove?
   It proves five properties over all 46,080 abstract transitions of the real C code (latching,
   gates off outside RUN/SOFTSTART, no deadlock, gates imply enable, conditional fault entry); it does
   not prove timing, numerical behaviour or the hardware trip path.
10. What is the single-point ground bond and why is it a safety topic?
    R173 ties the control GND to PE at one point; it defines the SELV reference (PELV) and the CM
    current path; its value is a test option.

### Advanced / research (10)

1. Why can protection logic not reduce the FTA's TE1 frequency?
   TE1 is dominated by first-order cut sets (single barrier failures); only barrier design (double or
   monitored insulation) changes it - a structural result independent of the assumed rates.
2. How would you make the gate-drive isolation "monitored"?
   Insulation-resistance supervision between the gate-side rails and control ground, or a guard
   track around each straddler connected to a leakage detector; both convert DU barrier failures into
   DD events.
3. What is the common-cause weakness in the OV protection?
   Hardware and firmware OV use the same AMC1301 channel and the same PS9 supply; a supply loss
   reads mid-scale, inside the UV/OV window - DU. A second channel or a plausibility check against the
   LV side breaks it.
4. How should the 100 kHz stress on the gate-drive barriers be assessed?
   Beyond the 60664-1 tables: partial-discharge inception at the working peak with a square waveform,
   ageing of the polyimide and the mould compound under HF stress; the test plan's PD option is the
   entry point.
5. Discuss the use of RPN vs FTA importance for prioritisation.
   RPN mixes ordinal scales and hides severity; Fussell-Vesely importance ranks events by their share
   of a top-event frequency and exposes structure (first-order sets). The repository shows both and
   the differences in ranking.
6. What does the Python-vs-C mismatch list tell a researcher?
   Two implementations of the same specification diverged in 71 classes (e.g. fault inputs in INIT);
   exhaustive checking found what tests missed - an argument for model-based specification of the
   controller.
7. Why is no SIL claimed, and what would be needed?
   Certified failure data, a systematic-capability assessment, hardware fault tolerance analysis and an
   independent assessor; the FMEDA-lite "only ranks where diagnostics are missing".
8. How do the insulation, EMI and layout chapters interact at the Y capacitors?
   Y1 parts sit across a basic barrier (power to PE) and must keep the 8.5 / 5 mm PE rules; their
   value is bounded by the PE displacement current (12.6 A pulses through C_iw) and the pulse rating;
   their position at the port fixes the CM loop.
9. What is the right verification sequence before energisation?
   Independent review of the study and PCB (SAF-08), magnetics hipot, bare-board netlist test,
   assembled-board hipot and PD (step 3), protection injection tests (step 5), then low-voltage
   functional tests - the order in section 7 and the test plan.
10. Which repository inconsistencies did this chapter surface, and how should they be closed?
    DESAT cited but absent in rev A; AMC1311 / UCC21710 in the study vs AMC1301 / UCC21520 in the
    schematic; bleeder values in the BOM vs the design calculation; they should be closed by a
    requirements-to-BOM check and a revision of the study against the generated schematic.

## Pitches

**30 s:** "Safety here is insulation coordination by the IEC 62477-1 / 60664-1 method - reinforced
to the SELV control circuit, basic HV-LV and to PE, 16 mm barriers, 12 / 10 / 8 / 5.5 mm DRC rules,
slots under the modules - plus three-line protection at 32 A and 920 / 490 V, and a 19-row FMEA whose
top items are the MOSFET short, the CT and the connectors. The 2026 module adds a fault tree, an
FMEDA and an exhaustive model check of the firmware. Open items: basic-class bias modules, no DESAT in
rev A, bleeder values. Nothing is certified or tested."

**2 min:** Start with the circuit table and DVC logic; then the environmental inputs and the recalled
table values (to re-check); then the distances and how the generator turns them into DRC rules,
barriers and slots (figure `img/ch14_insulation_distances.png`); then the barrier components and the
bias-module open item; then protection coordination with the DESAT discrepancy; then PE, precharge and
the bleeder arithmetic; then the FMEA structure and its top RPNs and why severity-10 rows score low;
close with the FTA (TE1 97 % barrier components, TE2 NO_DESAT importance 1.0), the FMEDA coverage
figures and the 46,080-transition model check, all with declared assumptions and no certification
claim.

**10 min outline:**
* Circuits, working voltages, accessibility, DVC classes; reinforced vs basic per pair
* PD2, OVC II, altitude, material group; impulse levels; table values flagged "to re-check"
* Required distances per pair; design values; DRC rules; barriers; slots; SIP-7 for PS9/PS10
* Barrier components and ratings; the basic-class bias module open item; study vs schematic part names
* Test voltages and PD; test plan step 3; energisation policy (SAF-08)
* Protection coordination: thresholds, hardware path (LM393, PROT_DIS, trip zones), firmware faults and states, system line; the DESAT gap
* PE structure, control-ground bond, precharge interface, discharge: the bleeder discrepancy with arithmetic
* FMEA: structure, top RPN items, open items, RPN's blind spot
* Reliability module: FTA cut sets and importances, FMEDA DC/SFF, state-machine check results and the P1_literal lesson
* What is verified (DRC, SIL, model check), what is simulated (rates), what is untested (everything physical)

## Further reading

* `SiC_6k6_Industrial_DAB/15_Safety_Reliability/01_insulation_coordination.md` - the primary
  analysis, including its own list of values to re-check.
* `Advanced_Research_2026/Reliability_Engineering/fta.py` and `fmeda_lite.py` docstrings - the
  quantification method and the assumption policy.
* `Advanced_Research_2026/Reliability_Engineering/results/state_machine_report.md` - properties,
  violations, conformance.
* `SiC_6k6_Industrial_DAB/20_Experimental_Test_Plan/test_plan.md` - safety controls and the staged
  sequence.
* Literature database `Advanced_Research_2026/Literature_Database/literature_2022_2026.csv`: L11
  (SiC prognosis review) and L13 (complete condition monitoring of SiC MOSFETs) for the
  health-monitoring side of reliability; no entry in the database covers insulation standards,
  which is a gap to fill.
