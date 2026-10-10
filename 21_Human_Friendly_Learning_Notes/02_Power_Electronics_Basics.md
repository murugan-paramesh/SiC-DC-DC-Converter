# 02 Power-electronics basics

> Reading time: ~50 min. Prerequisites: chapter 01. Files covered:
> `SiC_6k6_Industrial_DAB/02_Topology_Comparison/topology_comparison.md`,
> `SiC_6k6_Industrial_DAB/02_Topology_Comparison/topology_comparison.json`,
> `SiC_6k6_Industrial_DAB/02_Topology_Comparison/topology_comparison.py`, `docs/01_specification.md`,
> `docs/02_design_calculations.md`, `docs/03_component_selection.md`, `hardware/kicad/drc_summary.json`,
> `SiC_6k6_Industrial_DAB/dabtools/dab/losses.py`.

## Overview

**Level 1 - Beginner:** Power electronics is the art of moving energy between voltages with switches
instead of resistors. A switch that is fully on or fully off wastes almost nothing; the trick is to open
and close it so fast (100 000 times per second) and in such a pattern that, after filtering by an
inductor and a capacitor, the output looks like a clean DC voltage. Four switches make a "full bridge"
that can produce a square wave from a DC bus; two full bridges facing each other through a transformer
make the dual active bridge (DAB) of this project, which can push energy in either direction.

**Level 2 - Engineering:** This chapter introduces the vocabulary used by every later chapter: PWM, the
bridge leg and dead time, hard versus soft switching (ZVS, ZCS), galvanic isolation, the common
isolated converter families and the loss categories (conduction, switching, gate, magnetic, capacitor,
auxiliary). It then reads the project's own topology study, `02_Topology_Comparison/`, which compared
the PSFB, DAB, CLLLC, two-phase and three-phase DAB at 6.6 kW and 650-850 V <-> 300-450 V and selected the
single-phase DAB with a weighted score of 109 against 84 for the PSFB and 82 for the CLLLC; and it uses
the 3 kW PSFB design at the repository root (`docs/`, `hardware/`) as the worked baseline.

**Level 3 - Research:** The open problems of the field show up already at this level: soft switching
that is lost at light load and at voltage ratios far from 1 (the DAB's known weakness, 24-92 % minimum
ZVS load across the corners in `02_Topology_Comparison/topology_comparison.json`); the choice between phase-shift and resonant
topologies (TI's 6.6 kW CLLC reference at 500 kHz claims 98 % peak, literature id L07); and the
question of how far analytical loss models can be trusted before a prototype exists - which is exactly
what the 2026 uncertainty-quantification module asks.

## The power switch

### The ideal and the real switch
**What is it?** An ideal switch has zero resistance when on, infinite resistance when off, changes
state instantly and needs no energy to be driven. A real switch - here a SiC MOSFET - has an on-state
resistance Rds(on), an output capacitance Coss, finite switching times, a gate that must be charged and
discharged, a body diode and a maximum junction temperature.

**Why do we need it?** A linear regulator dropping 800 V to 400 V at 16.5 A would dissipate 6.6 kW; a
switch that is either on (small I^2 R) or off (no current) dissipates only the non-ideal residues. The
whole efficiency of the converter is the sum of these residues.

**How does it work?**
**Level 1 - Beginner:** A light switch does not get warm because it is either fully closed (no voltage
across it) or fully open (no current through it). Power loss needs voltage and current at the same
time; a switch avoids that - except in the instant of switching and through its small on-resistance.
**Level 2 - Engineering:** Four residues are modelled per device in `dabtools/dab/losses.py`: conduction
I_rms_dev^2 Rds(on)(Tj); turn-off energy Eoff(V, I) x fs x k_zvs (k_zvs = 0.35, an assumption that under
ZVS most of the datasheet Eoff is recycled Coss energy); hard-switching energy (Eon + Eoff + Coss,er V^2)
x fs when the ZVS criterion fails; body-diode conduction during dead time; and the gate charge loss
Qg (Vgs,on - Vgs,off) fs. For the C3M0032120K the datasheet-typical entries are Rds 32 mOhm (25 C),
Coss,er 170 pF, Eon 270 uJ / Eoff 55 uJ at 800 V 20 A, Qg 87 nC (`dabtools/dab/devices.py`,
`verified=False`).
**Level 3 - Research:** The residues are not independent: Rds(on) depends on Tj which depends on the
losses; Coss depends on voltage non-linearly (three different capacitance figures, Coss, Coss,er and
Coss,tr, describe the same device for different purposes); and the datasheet switching energies are
measured in a double-pulse set-up that does not represent a ZVS bridge - the k_zvs = 0.35 factor is a
literature-informed guess (Krismer and Kolar 2010) to be replaced by measurement.

**Example from our converter:** `[Simulated]` At 800/400 V, 6.6 kW the HV bridge loses 6.1 W in
conduction, 2.8 W in ZVS turn-off, 0.0 W in hard switching, 0.9 W in dead-time diode conduction; the
LV bridge 12.5 / 2.0 / 0.0 / 1.2 W; gate drive 2.0 W for both bridges
(`SiC_6k6_Industrial_DAB/04_Design_Calculations/design_report.md`, section 4).

**Engineering calculations:** Gate loss per device = Qg (Vgs,on - Vgs,off) fs = 87e-9 x 19 V x 1e5 =
0.165 W (HV), 180e-9 x 19 x 1e5 = 0.342 W (LV); 4 x (0.165 + 0.342) = 2.03 W, the "Gate drive (both
bridges)" line of `04_Design_Calculations/design_values.json` (2.0292 W). Note that the model uses
-4 V for Vgs,off while the schematic bias module gives -3 V (chapter 03 discusses this discrepancy).

**Design decision made in this project:** `[Implemented]` 1200 V SiC MOSFETs on both bridges
(C3M0032120K on the HV side at 850 V = 71 % of rating, C3M0016120K on the LV side at 450 V = 38 %,
`SiC_6k6_Industrial_DAB/16_BOM/bom.md`); the LV side uses a 1200 V part rather than a 650 V part because
the DAB's LV bridge sees the full 450 V plus ringing and because a common gate-drive and footprint
design simplifies the board.

**Alternatives considered:** Si IGBTs (too slow at 100 kHz, tail current); Si superjunction MOSFETs
(poor body diode, large Coss at 800 V); GaN HEMTs (no 1200 V discrete parts in TO-247 at this current);
paralleled devices (two-phase DAB fallback in `02_Topology_Comparison/topology_comparison.md`, section 6).

**How to verify it:** The device loss lines are produced by `dabtools/dab/losses.py` from the model
currents; the only real check is a double-pulse test and a calorimetric efficiency measurement, both in
`SiC_6k6_Industrial_DAB/20_Experimental_Test_Plan/test_plan.md`. `[Simulated]`, `[Not yet tested]`

**Common mistakes:** Using the 25 C Rds(on); forgetting gate loss (small per device, 2 W for eight);
charging the full datasheet Eon to a ZVS turn-on (there is none under ZVS); assuming a MOSFET body diode
is a good diode (Vsd = 4.0 V here, so dead time costs real loss).

**Interview explanation (30 s):** A real switch loses energy four ways: resistance while on, overlap
of voltage and current while switching, charging its own capacitances and gate, and conducting through
its body diode during dead time. Our model puts numbers on each: for the HV bridge 6.1 + 2.8 + 0 + 0.9 W
at full load, with 1200 V SiC devices used at 71 % of their voltage rating.

**Research-level explanation:** The honest statement is that every one of these numbers is a
datasheet-typical value entered from memory and flagged `verified=False`; the loss model exposes its
sensitivity to them so that a corrected value can be substituted and the chain re-run (docstring of
`dabtools/dab/devices.py`).

### PWM and the bridge leg
**What is it?** Pulse-width modulation (PWM) controls the average of a switched voltage by the fraction
of time it is high. A bridge leg (half bridge) is two switches in series across the DC link whose
midpoint is the output; a full bridge is two legs whose outputs form a differential output that can be
+V, 0 or -V (three-level voltage).

**Why do we need it?** The DAB needs a square-wave voltage of +/-V1 (and optionally a zero interval)
from the 800 V bus, so it uses a full bridge; the phase shift between the two bridges is the control
variable rather than the duty cycle, but the switches are still driven by a PWM peripheral.

**How does it work?**
**Level 1 - Beginner:** Flick a switch fast between two voltages and a sluggish load sees the average.
Two switches stacked on a battery, never both on at once, let the midpoint be either terminal; four of
them let the output be flipped in polarity, which is what a transformer needs.
**Level 2 - Engineering:** In each leg the two devices are complementary with a dead time in which both
are off, so that the link is never short-circuited (shoot-through). In the DAB each leg runs at 50 %
duty; the modulation variables are the outer phase shift phi between the two bridges and the inner
shifts D1, D2 between the two legs of each bridge (`03_Mathematical_Models/dab_mathematical_model.md`,
section 1). The C2000 ePWM generates these with 10 ns resolution, 1/1000 of the period or 0.36 deg
(`11_Control_Algorithms/control_design.md`, section 2). Dead time: 150 ns set by firmware
(`04_Design_Calculations/design_values.json` -> `t_dead`) plus a ~22 ns hardware interlock in the UCC21520 driver (2.2 k on
its DT pin, `16_BOM/bom.md` R101).
**Level 3 - Research:** The dead time is not free: during it the inductor current flows through body
diodes (Vsd 4.0-4.2 V) and the effective phase shift is reduced; `dabtools/dab/control.py` compensates
with a `phi_dead_comp` term (0.047 rad, `11_Control_Algorithms/control_params.json`). Adaptive dead time
that tracks the ZVS transition is a research topic of `Advanced_Research_2026/Adaptive_MPC/` and of
the proposed transition-time sensor in `Advanced_Research_2026/Digital_Twin/README.md`.

**Example from our converter:** `[Implemented]` HV bridge: Q1-Q4, legs A (Q1/Q2) and B (Q3/Q4), outputs
SW_A and SW_B on M6 studs J3/J4; LV bridge: Q5-Q8, legs C and D, outputs SW_C/SW_D (`16_BOM/bom.md`).
Each leg has one UCC21520DW dual isolated driver (U1-U4) and each device its own isolated bias module
(PS1-PS8).

**Engineering calculations:** At 100 kHz the period is 10 us and each half period 5 us; the 150 ns
dead time is 1.5 % of the period or 5.4 deg of phase - the same order as the smallest phase shift used
at light load, which is why it must be compensated. The modulator resolution of 10 ns corresponds to
0.36 deg, or 0.1 % of the nominal 28 deg shift.

**Design decision made in this project:** `[Implemented]` Full bridges on both sides (not half
bridges) so that both ports can produce three-level voltages, which the EPS/DPS/TPS modulations of
chapter 04 require; 150 ns firmware dead time, well above the 50 ns charge-based minimum of
`dab_model.dead_time_required()` at nominal current, to be optimised later.

**Alternatives considered:** Half-bridge DAB on one side (half the devices, twice the current, only
two-level voltage); three-phase DAB (six legs, smaller capacitors, scored 97 vs 109 in the decision
matrix).

**How to verify it:** The modulator is exercised in software-in-the-loop by `10_Firmware/` (35 SIL
checks pass, `SiC_6k6_Industrial_DAB/README.md`); the plant's pulse generation is in
`dabtools/dab/sim_switched.py` (`period_voltages`). `[Verified]` for the SIL harness; `[Not yet tested]`
on the C2000 (the HAL has never been compiled).

**Common mistakes:** Zero dead time in a simulation that is then trusted for hardware; forgetting that
dead time shortens the effective phase shift; letting both devices of a leg be on for even 10 ns.

**Interview explanation (30 s):** A bridge leg is two switches across the bus with a midpoint output;
a full bridge is two legs, giving +V, 0 or -V. Our DAB has two full bridges, eight SiC devices, each
leg at 50 % duty with 150 ns dead time, and the control acts on the phase between the bridges, not on
the duty cycle.

**Research-level explanation:** The three-level capability of each bridge adds two degrees of freedom
(D1, D2) that the modulation literature uses to extend the ZVS range and reduce rms current; the cost is
that the small-signal plant becomes pattern-dependent, which the 2026 twin handles by evaluating its
regressor on the applied PWM registers rather than on the ideal phase.

### Hard switching versus soft switching (ZVS and ZCS)
**What is it?** Hard switching: the device turns on or off while both voltage and current are present,
dissipating the overlap energy plus the stored Coss energy. Zero-voltage switching (ZVS): the device
turns on only after its drain-source voltage has been brought to zero by an external current (here the
inductor current discharging Coss during the dead time). Zero-current switching (ZCS): the device turns
off when its current is already zero (resonant converters).

**Why do we need it?** At 100 kHz and 800 V hard switching would cost (Eon + Eoff + Coss,er V^2) x fs
= (270 + 55 + 109) uJ x 1e5 = 43 W per device for the HV bridge alone - eight times the whole calculated
HV-bridge switching loss under ZVS (2.8 W). Soft switching is what makes 100 kHz at 800 V possible.

**How does it work?**
**Level 1 - Beginner:** Imagine closing a door while someone is pushing against it (hard) versus
waiting until the draught has already pulled it shut and only clicking the latch (soft). The DAB lets
the inductor current pull the switch voltage to zero before turning the switch on.
**Level 2 - Engineering:** When one device of a leg turns off, the inductor current has nowhere to go
except into the two output capacitances: it charges the one that turned off and discharges the other.
If the current is large enough to finish this within the dead time, the other device turns on at zero
voltage. The energy criterion used in this project: 0.5 L I_sw^2 >= Coss,er V^2 (+ 0.5 C_par V^2), giving
I_min = sqrt(2 E / L) = 2.0 A on the HV bridge and 3.07 A on the LV bridge (`04_Design_Calculations/design_values.json` ->
`nominal.Imin1`, `nominal.Imin2`). Figure `img/ch02_hard_vs_soft.png` sketches the two cases with the
project's edge current (9.75 A) and Coss,tr (320 pF): the capacitive transition takes about 2 Coss,tr
V / I = 52 ns.
**Level 3 - Research:** The energy criterion is conservative; the exact condition is charge based
(Everts et al. 2014, reference [14] in `01_Literature_Review/literature_review.md`) and depends on the
current trajectory during the transition. Under ZVS the node dv/dt is I_sw / (2 Coss,tr), 15 V/ns at
nominal and ~30 V/ns at the full-power corners, independent of the gate resistor - which is why an
active gate driver cannot slow a ZVS edge (`Advanced_Research_2026/Active_Gate_Drive/README.md`,
finding 1). Loss of ZVS at light load is the DAB's structural weakness: with SPS at 800/400 V ZVS
holds only above roughly 24-35 % load (24 % with L = 67.3 uH in `02_Topology_Comparison/topology_comparison.json`, 35 % with
the final 64 uH per `Advanced_Research_2026/Active_Gate_Drive/README.md`).

**Example from our converter:** `[Simulated]` ZVS margins at full power (edge current minus I_min):
HV 7.6 A and LV 8.2 A at 800/400 V, but only 0.7 A on the HV bridge at 650/450 V and 3.0 A on the LV
bridge at 850/300 V (`04_Design_Calculations/design_report.md`, section 2) - the corners of the voltage
window are where soft switching is nearly lost even at full load.

**Engineering calculations:** Coss energy per leg at 800 V: Coss,er V^2 = 170e-12 x 800^2 = 109 uJ;
inductor energy at I_min = 2.0 A: 0.5 x 64e-6 x 4 = 128 uJ >= 109 uJ + 0.5 x 60e-12 x 800^2 = 128 uJ.
Hard-switching penalty if ZVS is lost: `dabtools/dab/losses.py` adds (Eon + Eoff) x fs + Coss,er V^2 x fs per edge,
i.e. tens of watts per bridge - the thermal design (Tj < 70 C at 45 C ambient) has margin for this at
light load but not at full load.

**Design decision made in this project:** `[Implemented]` SPS as the control baseline with EPS
voltage matching (D of the higher-voltage bridge = d) as the firmware default, because it keeps ZVS at
light load without a look-up table (`11_Control_Algorithms/control_design.md`, section 3); TPS tables
as an option.

**Alternatives considered:** Resonant CLLLC with ZCS/ZVS over the whole load range - rejected for the
0.71-1.38 gain window (`02_Topology_Comparison/topology_comparison.md`, section 4); burst mode or
frequency modulation at light load (listed as needed in `Advanced_Research_2026/Digital_Twin/README.md`,
section 3).

**How to verify it:** `DABPoint.zvs_margin()` in `dabtools/dab/dab_model.py` for any modulation; the
ngspice model checks ZVS at all eight edges (`05_Simulation/gen_spice.py`,
`05_Simulation/img/spice_sps_waveforms.png`); on hardware, a drain-voltage probe at turn-on.
`[Simulated]`, `[Not yet tested]`

**Common mistakes:** Claiming ZVS from the full-load point alone; using Coss (small-signal) instead of
Coss,er (energy) or Coss,tr (time) in the wrong formula; forgetting the transformer capacitance C_par
(60 pF here) in the energy balance.

**Interview explanation (30 s):** Hard switching at 800 V and 100 kHz would cost about 43 W per device;
the DAB avoids it by letting the inductor current discharge the output capacitances in the dead time
so the device turns on at zero voltage. That needs at least 2 A of edge current on our HV bridge, which
SPS provides above about a third of full load at the nominal ratio but barely at the voltage corners.

**Research-level explanation:** ZVS boundaries over (V1, V2, P, Tj, modulation, tolerance) are mapped in
`Advanced_Research_2026/Adaptive_MPC/`; the observability study shows that Coss cannot be identified
from the period-average sensors on the board, so an adaptive ZVS law needs a transition-time sensor
that does not yet exist (`Advanced_Research_2026/Digital_Twin/README.md`, section 1).

## Isolation and converter families

### Galvanic isolation and why it is required
**What is it?** Two circuits are galvanically isolated when no conductor joins them; energy and
signals cross through magnetic (transformer), optical or capacitive couplers only. Insulation is
classed as functional, basic, double or reinforced depending on what it protects.

**Why do we need it?** The HV bus (850 V DC) and the LV port (450 V DC) are both hazardous and both
floating; the control electronics are accessible (CAN, UART, 24 V). Safety requires reinforced
insulation between either power circuit and the control circuit, and basic insulation between the two
power circuits (`SiC_6k6_Industrial_DAB/15_Safety_Reliability/01_insulation_coordination.md`, section 1).
Isolation also allows the two ports to sit at different ground references in a DC distribution system.

**How does it work?**
**Level 1 - Beginner:** A transformer passes energy through a magnetic field across a gap of
insulation, so a fault on one side cannot put dangerous voltage on the other. The same idea protects
the control board: the gate signals cross the barrier inside the driver chip, the measurements cross
inside the isolated amplifier.
**Level 2 - Engineering:** Barriers in this design: transformer HV-LV (basic, 850 V working, three
layers of 50 um polyimide, 2.5 kVrms test); eight UCC21520 gate drivers (5.7 kVrms reinforced); eight
isolated gate bias modules (currently a basic-class part, open item); three AMC1301 isolated amplifiers
(7 kVpk reinforced); CAN transceiver non-isolated in rev A with ISO1042 as upgrade (`16_BOM/bom.md`,
`15_Safety_Reliability/01_insulation_coordination.md`, section 4). PCB distances: 9 mm HV-LV barrier,
16 mm HV-control, 10 mm LV-control, with routed slots under the isolators.
**Level 3 - Research:** The barrier is also the EMI path: 631 pF of transformer interwinding
capacitance and the isolator parasitics carry common-mode current at every 15-30 V/ns edge; the Y
capacitors (4 x 4.7 nF Y1) return it. The reinforced rating of the bias modules is the one open safety
item that no simulation can close (`15_Safety_Reliability/01_insulation_coordination.md`, section 4).

**Example from our converter:** `[Implemented]` Three PE lugs (J20 PE, J21 PE_HV, J22 PE_LV) because
no copper may cross the two 16 mm barriers on the board; they are bonded through the chassis
(`16_BOM/bom.md`). The PSFB baseline used the same principle with a single 8 mm barrier at x = 130 mm
on a 260 x 200 mm board (`docs/01_specification.md`, Mechanical).

**Engineering calculations:** From the insulation study (recalled IEC 60664-1 values, to verify):
1000 V system, OVC II -> 4 kV impulse -> 3.0 mm clearance basic; reinforced uses the next impulse level
(6 kV -> 5.5 mm) and twice the creepage. The 850 V HV-control pair therefore needs 12-17 mm creepage
depending on the material group; the board uses 16 mm.

**Design decision made in this project:** `[Implemented]` Three isolation regions (HV, LV, control)
on a 6-layer board with reinforced isolators toward the control side and a basic transformer barrier;
the earlier PSFB had only two regions because its 48 V output is SELV.

**Alternatives considered:** Non-isolated bidirectional buck-boost (cheaper, no transformer) - fails the
isolation requirement SAF-01 and the 2:1 ratio with 850 V devices; a separate isolated DC-DC per
sensor instead of isolated amplifiers.

**How to verify it:** DRC rules `pe_to_hv`, `pe_to_lv` and the barrier rule areas
(`SiC_6k6_Industrial_DAB/07_KiCad_Schematics/SiC_DAB_6k6.kicad_dru`); hipot tests in
`20_Experimental_Test_Plan/test_plan.md`. `[Verified]` for the DRC rules that run; `[Not yet tested]`
for the withstand tests.

**Common mistakes:** Quoting one isolation voltage for the whole converter (the brief's 3 kVrms was
shown to be wrong for the reinforced barrier and unnecessary for the basic one); routing a ground pour
under an isolator; forgetting that the heatsink is at PE and therefore a third party to every barrier.

**Interview explanation (30 s):** Both ports are hazardous and floating, the control is touchable, so
the transformer provides basic insulation between the ports and the gate drivers and isolated
amplifiers provide reinforced insulation to the control side. On the board that is a 9 mm barrier
between HV and LV and 16 mm to the control region, with slots under every isolator.

**Research-level explanation:** Insulation coordination for 850 V DC in IEC 62477-1 terms (DVC C) is a
documented analysis here, not a certification; partial-discharge behaviour of the 150 um polyimide
barrier at 100 kHz square-wave stress is an open experimental question.

### Converter families: buck/boost, flyback, PSFB, LLC/CLLC, DAB
**What is it?** Non-isolated converters (buck, boost, buck-boost) use one inductor and one or two
switches; isolated converters put a transformer in the path: flyback (energy stored in the transformer
gap), forward and full-bridge PWM converters (PSFB = phase-shifted full bridge with a rectifier),
resonant converters (LLC, CLLC/CLLLC, gain set by frequency) and the dual active bridge (two active
bridges, gain set by phase shift).

**Why do we need it?** The topology decides what the hardware can do at all - direction of power flow,
voltage-ratio range, how soft switching is obtained, how the current is limited - before any component
is chosen. The project ran a quantitative comparison at the 6.6 kW specification and documented the
decision.

**How does it work?**
**Level 1 - Beginner:** A buck converter is a chopper plus a filter: lower voltage out. A flyback stores
a packet of energy in a coil and releases it on the other side. A full bridge makes an AC square wave
for a transformer and rectifies it afterwards (PSFB). A resonant converter lets an L-C tank ring and
picks the frequency that gives the right voltage. A DAB puts active bridges on both sides so that
either side can be the sender.
**Level 2 - Engineering:** The PSFB regulates by effective duty D_eff (0.56-0.85 needed over our window)
and loses duty to the current reversal in the resonant inductor (dD = 4 I_p L_r f / V_in, 0.12-0.16 in
the 3 kW design, `docs/02_design_calculations.md`, section 2). The CLLLC regulates by frequency; with
L_n = 5 and Q = 0.4 the first-harmonic gain cannot reach 1.38 at acceptable Q and reaching 0.71 needs
f/f_r = 2.0, far above resonance (`02_Topology_Comparison/topology_comparison.md`, section 4). The DAB
regulates by phase shift: d = 0.71-1.38 is reached with phi <= 63 deg at full power everywhere, and the
current is limited by the series inductor's di/dt.
**Level 3 - Research:** Resonant CLLC topologies win on efficiency at a fixed ratio (TI PMP21495, 6.6 kW,
500 kHz, 98 % peak vendor figure, literature id L07) but need a wide frequency sweep for a wide ratio;
phase-shift DABs win on ratio range and control simplicity but pay in circulating current at d != 1.
Reconfigurable DABs (APEC 2025, id L06) try to get both. The comparison in this repository is
analytical; its decision matrix weights are engineering judgement.

**Example from our converter:** `[Simulated]` Requirement filter (`02_Topology_Comparison/topology_comparison.md`, section 1):
the PSFB fails EL-01 (not bidirectional); the CLLLC fails EL-02/03 (gain range 0.71-1.38 needs
f/f_r = 2.00..0.48); the DAB passes; the two-phase DAB passes at 2x cost, the three-phase at 1.5x.
Decision matrix (section 5): PSFB 84, DAB 109, CLLLC 82, two-phase DAB 97, three-phase DAB 97.

**Engineering calculations:** PSFB at the 6.6 kW specification would need n = 1.51, cannot reach
650/400 V or 650/450 V (D_eff > 0.9) and stresses the synchronous rectifiers at 430-562 V plus ringing,
requiring 1200 V SiC on the secondary too (`02_Topology_Comparison/topology_comparison.md`, section 3). The 3 kW PSFB at
400 V -> 48 V uses n = 6 (18:3:3), L_r = 12 uH, 140 V rectifier stress, and reaches ZVS down to about
9 % load thanks to the 1.83 A minimum primary current (`docs/02_design_calculations.md`, sections 2-4).

**Design decision made in this project:** `[Implemented]` Single-phase DAB with SiC full bridges on
both ports, n = 2, external inductor plus leakage, SPS baseline with DPS/TPS extensions; PSFB retained as
the comparative baseline in `SiC_6k6_Industrial_DAB/Legacy_PSFB_Baseline/README.md`; two-phase DAB as
the fallback if the thermal budget had not closed (it did: Tj < 70 C).

**Alternatives considered:** All of the above, with scores; plus the three-phase DAB (smaller link
capacitors, three-phase magnetics, 2 in the transformer-requirements row).

**How to verify it:** `python3 SiC_6k6_Industrial_DAB/02_Topology_Comparison/topology_comparison.py`
regenerates the tables and figures (`02_Topology_Comparison/img/dab_sps_maps.png`,
`02_Topology_Comparison/img/clllc_gain.png`). `[Simulated]`

**Common mistakes:** Comparing topologies at their own best operating point instead of over the whole
required window; treating a synchronous-rectifier PSFB as bidirectional (its SR bridge cannot regulate
reverse flow without becoming a DAB); reading a vendor's 98 % as comparable to an analytical 98.6 %.

**Interview explanation (30 s):** At 6.6 kW with a 0.71-1.38 voltage-ratio window and bidirectional
flow, the PSFB fails on direction, the CLLC fails on gain range, and the DAB passes both with phase
shift below 63 deg everywhere; the weighted matrix gave it 109 points against 84 and 82. The 3 kW PSFB
at the repo root remains the baseline we compare against.

**Research-level explanation:** The comparison is first-harmonic and analytical; a research-grade
comparison would optimise each topology over its own design space (frequency, magnetics, devices)
before scoring, which `12_Optimization/` does for the DAB only.

### Bidirectional operation
**What is it?** A bidirectional converter can transfer power from port 1 to port 2 and from port 2 to
port 1 with the same hardware. In a DAB the direction is the sign of the phase shift: bridge 2 lagging
bridge 1 sends power 1 -> 2; leading sends it back.

**Why do we need it?** Requirement EL-01 (6.6 kW both directions) and EL-11 (0 -> full reverse in
< 20 ms without > 5 % over-voltage) come from the application: a battery string or LVDC port on one
side of an industrial DC bus that charges and discharges (APP-01, APP-03 in
`00_Requirements/01_requirements_specification.md`).

**How does it work?**
**Level 1 - Beginner:** Two people pushing a revolving door from opposite sides: whoever pushes
slightly ahead of the other drives the door. In the DAB the bridge that switches first "pushes".
**Level 2 - Engineering:** P = V1 V2' phi (pi - |phi|) / (2 pi^2 fs L) is odd in phi, so the same
equation gives negative power for negative phi. In CP (constant-power) mode the firmware feeds the
signed power reference through the modulator inverse, which returns a signed phi; the same PI trims the
regulated port (`11_Control_Algorithms/control_design.md`, section 5). The supervisory system commands
the direction over CAN; the converter never reverses autonomously (APP-03).
**Level 3 - Research:** Reversal is a transient in which both DC links must stay within limits while
the inductor current changes sign over a few periods; the switched simulation ramps the reference at
2 kW/ms. Which port is regulated in each direction, and how two converters on one bus avoid fighting,
is a system-level control question outside the converter model.

**Example from our converter:** `[Simulated]` Power reversal from +6.6 kW to -6.6 kW with a battery
(400 V, 0.1 Ohm) on the LV port: V1 stays within 797.2-802.6 V, V2 within 398.2-401.8 V, no fault
(`05_Simulation/switched_results.json` -> `reversal`; figure `05_Simulation/img/sim_reversal.png`); the
ramp takes 6.6 ms at the 2 kW/ms slew limit, inside the 20 ms of EL-11 with < 0.7 % excursion.

**Engineering calculations:** At the 2 kW/ms slew, 13.2 kW of change takes 6.6 ms = 660 switching
periods; the phase shift moves from +28 deg to -28 deg at 0.085 deg per period, 4 steps of the 0.36 deg
modulator resolution every 5 periods - smooth enough that the links barely notice.

**Design decision made in this project:** `[Implemented]` CV/CC regulation of the LV port in forward
mode, CP or HV-voltage regulation in reverse mode under supervisory command; power-reference slew
limited to 2 kW/ms (`11_Control_Algorithms/control_params.json` -> `slew_W_per_s`).

**Alternatives considered:** Autonomous droop-based reversal (rejected by APP-03 to avoid conflicting
regulators on a shared bus); a unidirectional PSFB plus a second converter for the return path (two
boxes, scored 1 for bidirectionality).

**How to verify it:** `05_Simulation/run_switched_sim.py`, case 3 ("reversal"); on hardware the
staged plan requires a bidirectional source/sink. `[Simulated]`, `[Not yet tested]`

**Common mistakes:** Assuming the converter can simply be "run backwards" without re-deciding which
port is regulated; ignoring the sign of the dead-time compensation on reversal; letting the reference
step instead of ramp.

**Interview explanation (30 s):** The DAB is bidirectional because power is odd in the phase shift:
make bridge 2 lead instead of lag and energy flows back. Our simulation reverses 6.6 kW in 6.6 ms with
less than 0.7 % bus excursion, under a supervisory CAN command, never autonomously.

**Research-level explanation:** Model-predictive control of the reversal transient, and the
estimation of the L and Coss that shift the ZVS boundaries differently in the two directions, are the
subjects of `Advanced_Research_2026/Adaptive_MPC/` and `Advanced_Research_2026/Digital_Twin/`.

### Efficiency and the loss types
**What is it?** Efficiency eta = P_out / P_in. Losses are grouped as semiconductor conduction,
semiconductor switching, gate drive, magnetic core and copper, capacitor ESR, auxiliary/bias/fans and
interconnect copper.

**Why do we need it?** The loss budget decides the heatsink (chapter 12), the enclosure, the fans and
the economics; its structure decides what to optimise. Requirements: >= 97.5 % peak and >= 96.5 % at
full load, calculated (EL-06, EL-07).

**How does it work?**
**Level 1 - Beginner:** Of every 100 W you put in, about 98.6 W come out and 1.4 W become heat in a
dozen places. Knowing where each tenth of a watt goes tells you which part to improve.
**Level 2 - Engineering:** The full-load budget at 800/400 V (`04_Design_Calculations/design_report.md`,
section 4): HV bridge 9.8 W, LV bridge 15.7 W, gate drive 2.0 W, transformer 18.8 W (11.4 core + 7.4
copper), series inductor 7.0 W (4.6 + 2.5), DC-link capacitors 0.4 W, auxiliary 12 W, PCB copper and bus
bars 26.4 W (estimate): total 92.2 W, 98.62 %. Peak 98.66 % at 80 % load; 89.2 % at 10 % load because the
38 W of fixed terms dominate there (`04_Design_Calculations/design_values.json` -> `eff_curves`).
**Level 3 - Research:** The 3 kW PSFB budget at the root (`docs/02_design_calculations.md`, section 9)
totals 91.1 W for 97.1 %: SR conduction 28.6 W and primary SiC conduction 18.2 W dominate, which is why
the 48 V output of a PSFB needs paralleled synchronous rectifiers and why a 400 V LV port (DAB) is so
much easier. Both budgets are analytical; their largest uncertainties are different (SR and snubbers in
the PSFB, PCB copper and device data in the DAB). The 2026 modules propagate the device-data
uncertainty (`Advanced_Research_2026/Uncertainty_Quantification/README.md`) and couple losses to
temperature and ageing (`Advanced_Research_2026/Multiphysics_Models/`).

**Example from our converter:** `[Simulated]` Worst-corner losses: 140 W at 650/300 V and 850/300 V
(97.9 %), because the triangular current raises the rms by 30 % and the backflow power to 1.3-1.5 kW
(`04_Design_Calculations/design_report.md`, section 2; `02_Topology_Comparison/topology_comparison.md`, section 2).

**Engineering calculations:** Semiconductor share at nominal: (9.8 + 15.7 + 2.0) / 92.2 = 30 %;
magnetics 28 %; fixed terms 42 %. The thermal chain scales the nominal split to the worst corner (HV
bridge 21.7 W, LV 34.9 W, transformer 41.7 W, `13_Thermal_Analysis/thermal_report.md`, section 1).

**Design decision made in this project:** `[Implemented]` Efficiency objectives met with margin on
paper; the design keeps 100 kHz (not higher) because magnetic and switching losses, not silicon cost,
set the optimum in `12_Optimization/optimization_report.md`.

**Alternatives considered:** Higher frequency for smaller magnetics (TI's CLLC at 500 kHz); lower
frequency for lower switching loss (the Inoue-Akagi DAB at 20 kHz, reference [3]).

**How to verify it:** `04_Design_Calculations/dab_design.py` (budget), `13_Thermal_Analysis/thermal_analysis.py`
(temperatures), input-output power measurement with class-0.1 power analysers in
`20_Experimental_Test_Plan/test_plan.md`. `[Simulated]`, `[Not yet tested]`

**Common mistakes:** Quoting efficiency without the operating point; including or excluding the
auxiliary power inconsistently; comparing a vendor's measured peak with an analytical full-load number.

**Interview explanation (30 s):** Our calculated full-load efficiency is 98.6 %: 92 W of loss, a third
in silicon, a third in magnetics, a third in fixed terms like fans and PCB copper. At the voltage
corners the triangular current adds 50 W. The PSFB baseline at 48 V loses 91 W on 3 kW - its rectifier
alone costs more than our whole LV bridge.

**Research-level explanation:** The calculated-versus-measured gap of DAB loss models is typically
dominated by magnetics (iGSE, fringing) and by the k_zvs assumption; the honest research path is to
report the model with its uncertainty bands, which the UQ module does, and to resist claiming the peak
value as a property of the converter.

## Worked example(s) with real numbers

**Example 1 - the price of hard switching.** `[Simulated]` HV device at 800 V and 20 A: Eon + Eoff =
270 + 55 = 325 uJ (datasheet test conditions, `dabtools/dab/devices.py`), plus the leg's Coss energy
Coss,er V^2 = 170e-12 x 640 000 = 109 uJ dumped at turn-on. Per edge, per device: 434 uJ; at 100 kHz:
43.4 W. Four devices: 174 W - nearly twice the whole calculated converter loss. Under ZVS the model
charges only Eoff x fs x k_zvs = 55e-6 x 1e5 x 0.35 = 1.9 W per device at 20 A; scaled linearly to the
9.75 A edge current and summed over the bridge this is the 2.8 W line of the budget. This is why a 2 A
ZVS threshold (I_min) matters more than a 2 mOhm change of Rds(on).

**Example 2 - reading the topology comparison.** `[Simulated]` At the 850/300 V corner
(`02_Topology_Comparison/topology_comparison.json`, row V1 = 850, V2 = 300, with L = 67.3 uH): d = 0.71,
P_max = 9.47 kW, phi at 6.6 kW = 40.5 deg, I_rms HV 12.2 A, I_pk 19.3 A, backflow 1464 W, ZVS on both
bridges only above 80 % load. At 800/400 V: d = 1.00, P_max = 11.9 kW, phi = 30.0 deg, 9.3 A rms, 9.9 A
peak, 327 W backflow, ZVS above 24 % load. The final design (`04_Design_Calculations/design_values.json`) lowered L to 64 uH,
which moves phi_nom to 28.2 deg and P_max to 12.5 kW; the pattern is unchanged.

**Example 3 - PSFB baseline sanity check.** `[Simulated]` 3 kW, 400 V -> 48 V, n = 6: reflected load
current 62.5/6 = 10.4 A, plus 0.85 A magnetising = 12.3 A primary peak, 10.1 A rms
(`docs/02_design_calculations.md`, section 3); ZVS energy for the lagging leg 20 uJ, I_zvs = 1.83 A,
ZVS down to ~9 % load; budget 91.1 W, 97.1 %; the PCB is generated, fully routed, 0 unconnected, 40
warnings all silkscreen (`hardware/kicad/drc_summary.json`). Everything is calculated or DRC-checked;
nothing is built.

## How this chapter connects to the files

| File | What it contains | Status |
|---|---|---|
| `SiC_6k6_Industrial_DAB/02_Topology_Comparison/topology_comparison.md` | requirement filter, DAB stress map, PSFB and CLLLC at the 6.6 kW spec, decision matrix, decision | `[Simulated]` |
| `SiC_6k6_Industrial_DAB/02_Topology_Comparison/topology_comparison.json` | the same numbers machine-readable (L = 67.3 uH baseline) | `[Simulated]` |
| `SiC_6k6_Industrial_DAB/02_Topology_Comparison/topology_comparison.py` | generator script | `[Implemented]` |
| `docs/01_specification.md` | PSFB 3 kW specification and architecture | `[Implemented]` |
| `docs/02_design_calculations.md` | PSFB duty, currents, ZVS boundary, magnetics, loss budget 91.1 W | `[Simulated]` |
| `docs/03_component_selection.md` | PSFB parts: C3M0060065K, IPP110N20N3 G, UCC28951, UCC21520, R12P21503D | `[Implemented]` |
| `hardware/kicad/drc_summary.json` | PSFB PCB DRC: 0 unconnected, 40 silkscreen warnings | `[Verified]` |
| `SiC_6k6_Industrial_DAB/dabtools/dab/losses.py` | the four semiconductor loss residues, k_zvs = 0.35 | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/dabtools/dab/devices.py` | device parameters, verified=False | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/04_Design_Calculations/design_report.md` | loss budget, ZVS margins at the corners | `[Simulated]` |
| `SiC_6k6_Industrial_DAB/11_Control_Algorithms/control_design.md` | modulation comparison, reverse power flow | `[Simulated]` |
| `SiC_6k6_Industrial_DAB/15_Safety_Reliability/01_insulation_coordination.md` | barriers, distances, open items | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/05_Simulation/switched_results.json` | reversal transient results | `[Simulated]` |
| `21_Human_Friendly_Learning_Notes/img/fig_ch02_switching.py` | hard vs soft switching sketch | `[Implemented]` |

## Viva / interview questions

### Basic (10)
1. Why does a switching converter waste less than a linear regulator?
   A switch is either on (little voltage) or off (no current), so the v x i product is small except
   during the brief transitions; a linear regulator carries the full current with the full voltage
   difference across it.
2. What is PWM?
   Controlling the average of a chopped voltage through the fraction of time it is high. In the DAB
   each leg stays at 50 %; the control variable is the phase between bridges.
3. What is a half bridge and what is a full bridge?
   A half bridge is two switches in series across the DC link with the midpoint as output; a full
   bridge is two half bridges whose outputs together give +V, 0 or -V.
4. What is dead time and why is it needed?
   A short interval (150 ns here) in which both switches of a leg are off, so that they never conduct
   simultaneously and short the link.
5. What does ZVS mean?
   Zero-voltage switching: the switch turns on after its voltage has already been brought to zero by
   the inductor current discharging its output capacitance.
6. Why does the converter need a transformer?
   Galvanic isolation between the hazardous HV and LV ports (and both from the control circuits) and
   the 2:1 voltage match.
7. Name three isolated converter topologies.
   Flyback, phase-shifted full bridge (PSFB), LLC/CLLC resonant, dual active bridge (DAB).
8. What does bidirectional mean for the DAB?
   The sign of the phase shift sets the direction: bridge 2 lagging sends power HV -> LV, leading
   sends it LV -> HV, same hardware.
9. What is efficiency and what is ours on paper?
   P_out / P_in; 98.62 % calculated at 800/400 V full load, 98.66 % peak at 80 % load, nothing measured.
10. Name the loss types in a switching converter.
    Conduction, switching, gate drive, magnetic core and copper, capacitor ESR, auxiliary/bias/fans,
    interconnect copper.

### Intermediate (10)
1. Estimate the hard-switching loss of one HV device at 800 V, 20 A, 100 kHz.
   (Eon + Eoff + Coss,er V^2) fs = (270 + 55 + 109) uJ x 1e5 = 43 W, versus about 2 W under ZVS; this is
   why ZVS is mandatory at 800 V / 100 kHz.
2. State the ZVS energy criterion and the resulting minimum current for our HV bridge.
   0.5 L I^2 >= Coss,er V^2 + 0.5 C_par V^2; with L = 64 uH, Coss,er = 170 pF, C_par = 60 pF, V = 800 V:
   I_min = 2.0 A (`04_Design_Calculations/design_values.json` nominal.Imin1).
3. Why does the PSFB fail the 6.6 kW requirement filter?
   It is unidirectional (EL-01); the SR bridge cannot regulate reverse flow without becoming a DAB.
   It also cannot reach 650/400 V and 650/450 V with D_eff <= 0.9.
4. Why does the CLLLC fail?
   With L_n = 5, Q = 0.4 the FHA gain cannot reach 1.38, and 0.71 needs f/f_r = 2.0, far above
   resonance with poor regulation and ZVS loss on the LV bridge.
5. What is backflow power and where is it largest?
   The period-average of the negative part of v1 i, energy circulating back to the HV link; 327 W at
   800/400 V but 1464 W at 850/300 V (`02_Topology_Comparison/topology_comparison.json`), where d = 0.71.
6. Explain the dead-time compensation term in the controller.
   During the 150 ns dead time body diodes conduct and the effective phase shift is reduced by about
   0.5 x omega x t_dead = 0.047 rad; `dabtools/dab/control.py` adds this to the commanded phi.
7. Why are three PE lugs needed on the DAB board?
   No copper may cross the two 16 mm reinforced barriers, so each isolation region has its own PE lug
   and the three are bonded through the chassis.
8. How does the simulation show that the reversal requirement EL-11 is met?
   `05_Simulation/run_switched_sim.py` ramps +6.6 kW to -6.6 kW at 2 kW/ms with a 400 V / 0.1 Ohm battery: V1 within
   797-803 V, V2 within 398-402 V (< 0.7 %), no fault, 6.6 ms < 20 ms.
9. Compare the 3 kW PSFB and 6.6 kW DAB loss budgets.
   PSFB 91.1 W (97.1 %), dominated by SR conduction 28.6 W and primary SiC 18.2 W; DAB 92.2 W (98.62 %),
   dominated by the 26.4 W copper estimate, transformer 18.8 W and LV bridge 15.7 W.
10. What is k_zvs and why is it an assumption?
    The share of the datasheet turn-off energy really dissipated under ZVS (0.35); the datasheet Eoff is
    measured hard-switched in a double-pulse test, so under ZVS most of it is recycled Coss energy.

### Advanced / research (10)
1. Why is the energy-based ZVS criterion conservative, and what is the exact one?
   It requires the inductor energy to exceed the capacitor energy; the exact criterion is charge based
   (Everts et al. 2014) and accounts for the current changing during the transition.
2. Why can an active gate driver not slow a ZVS edge?
   Under ZVS the node slope is I_sw / (2 Coss,tr), set by the load current and the device
   capacitance, not by the gate resistor (`Advanced_Research_2026/Active_Gate_Drive/README.md`, finding 1): 15 V/ns nominal,
   ~30 V/ns at the corners.
3. What light-load strategy does the DAB need and why?
   SPS/EPS lose ZVS below roughly 25-35 % load even at d = 1 because the edge current scales with
   power; TPS search, frequency modulation or burst mode are the candidates
   (`Advanced_Research_2026/Digital_Twin/README.md`, section 3).
4. Discuss the fairness of the decision matrix.
   Weights and scores are engineering judgement; a fair comparison would optimise each topology over
   its own design space; the repository states the matrix is analytical and not measured.
5. How would you compare our 100 kHz phase-shift DAB with TI's 500 kHz CLLC?
   State the difference in topology and frequency first (L07); compare efficiency over the whole ratio
   window, not at the CLLC's resonant point; note that 98 % vendor-measured and 98.6 % calculated are
   not commensurable.
6. What makes the LV bridge of the DAB easier than the PSFB's rectifier?
   A 400 V port at 16.5 A instead of 48 V at 62.5 A: conduction loss scales with I^2, so 16 mOhm
   devices at 13 A rms each dissipate 12.5 W total versus 28.6 W in the PSFB's paralleled SRs.
7. Which loss lines carry the largest uncertainty and how is that treated?
   PCB copper (26.4 W, estimate) and device data (verified=False); `Uncertainty_Quantification/`
   propagates them to efficiency, ZVS margin and Tj distributions.
8. Why is the bias-module isolation an open safety item?
   The R12P21503D is a basic-class 5.2 kVDC part on a barrier that must be reinforced; no simulation can
   close this, only a reinforced-rated part or a certified transformer bias
   (`15_Safety_Reliability/01_insulation_coordination.md`, section 4).
9. How does the twin handle the pattern dependence of the plant?
   It evaluates the regressor on the applied PWM registers (the controller knows its own registers),
   removing the modulator's time quantisation; without it the estimate was 4-7 % off at small phase
   shifts (`Advanced_Research_2026/Digital_Twin/README.md`, section 2).
10. Where does the k_zvs = 0.35 assumption come from and how would you replace it?
    From the Krismer-Kolar loss-model structure (reference [6]); replace it by a calorimetric
    measurement of the bridge under ZVS at several edge currents, or by a transition-level SPICE model
    with the real Coss(v) curve.

## Pitches

**30 s:** Power electronics moves energy with switches: a full bridge turns DC into a 100 kHz square
wave, a transformer isolates it, and soft switching keeps the losses small. Our project compared five
isolated topologies at 6.6 kW and chose the dual active bridge because it is natively bidirectional
and covers the 0.71-1.38 voltage-ratio window with a phase shift below 63 deg; the 3 kW PSFB at the
repo root is the baseline it is measured against.

**2 min:** A real switch loses energy in conduction, switching, gate charge and body-diode conduction;
at 800 V and 100 kHz hard switching would cost about 43 W per SiC device, so the whole design rests on
zero-voltage switching, which needs at least 2 A of inductor current at every edge of the HV bridge and
3.1 A on the LV bridge. Two full bridges, each leg at 50 % duty with 150 ns dead time, make a DAB whose
power is odd in the phase shift and hence bidirectional; the simulation reverses 6.6 kW in 6.6 ms with
under 0.7 % bus excursion. Isolation is structured as basic between the two hazardous ports and
reinforced to the control side: 9 mm and 16 mm barriers on the board, 5.7 kVrms drivers, one open item
on the bias modules. The topology study scored PSFB 84, DAB 109, CLLLC 82: the PSFB cannot return
power, the CLLLC cannot span the gain range. The loss budget at nominal is 92 W, 98.6 % calculated, a
third silicon, a third magnetics, a third fixed terms; at the voltage corners the triangular current and
1.3-1.5 kW of backflow power add 50 W. Every number is calculated or simulated; the lab plan says how
each would be measured.

**10 min outline:**
* Ideal vs real switch; the four loss residues in `dabtools/dab/losses.py`; HV bridge 6.1 + 2.8 + 0 + 0.9 W.
* PWM, bridge leg, full bridge, dead time 150 ns + 22 ns interlock, modulator resolution 0.36 deg.
* Hard vs soft switching: 43 W vs 2 W per device; I_min 2.0 / 3.07 A; figure `img/ch02_hard_vs_soft.png`;
  dv/dt = I / (2 Coss,tr) under ZVS; light-load loss of ZVS.
* Isolation: DVC classes, basic HV-LV, reinforced to control, 9 / 16 / 10 mm, three PE lugs, open item.
* Families: buck/boost, flyback, PSFB (duty loss, 140 V SR stress at 3 kW), LLC/CLLC (gain by
  frequency), DAB (gain by phase); requirement filter and decision matrix 84 / 109 / 82 / 97 / 97.
* Bidirectional: sign of phi, CP mode, reversal simulation 797-803 V / 398-402 V.
* Efficiency: 92.2 W budget, corners 140 W, PSFB 91.1 W at 3 kW; uncertainty of the copper estimate.
* Status: everything `[Simulated]` or `[Implemented]`, PSFB PCB `[Verified]` by DRC only.

## Further reading

* `SiC_6k6_Industrial_DAB/01_Literature_Review/literature_review.md` [1], [2] De Doncker / Kheraluwala
  (DAB origin), [6] Krismer and Kolar 2010 (loss model), [14] Everts et al. 2014 (ZVS conditions),
  [15] Redl et al. 1991 (PSFB clamp), [18] Jung et al. 2013 (bidirectional CLLC).
* `Advanced_Research_2026/Literature_Database/literature_2022_2026.csv` L06 (6.6 kW reconfigurable DAB,
  APEC 2025, existence confirmed), L07 (TI PMP21495 6.6 kW CLLC, vendor page confirmed), L21 and L22
  (active gate drive).
* `docs/02_design_calculations.md` - the complete PSFB design chain at 3 kW as a worked contrast.
