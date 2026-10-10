# 03 SiC devices

> Reading time: ~50 min. Prerequisites: chapters 01, 02. Files covered:
> `SiC_6k6_Industrial_DAB/dabtools/dab/devices.py`, `SiC_6k6_Industrial_DAB/dabtools/dab/losses.py`,
> `SiC_6k6_Industrial_DAB/09_Component_Libraries/README.md`, `SiC_6k6_Industrial_DAB/16_BOM/bom.md`,
> `SiC_6k6_Industrial_DAB/13_Thermal_Analysis/thermal_report.md`,
> `Advanced_Research_2026/Active_Gate_Drive/README.md`, `Advanced_Research_2026/SiC_Health_Monitoring/README.md`.

## Overview

**Level 1 - Beginner:** The switches of this converter are silicon-carbide (SiC) MOSFETs: transistors
whose crystal is made of silicon and carbon instead of silicon alone. The harder crystal withstands
about ten times the electric field, so a 1200 V switch can be thin, fast and low in resistance. The
converter uses eight of them in TO-247 packages the size of a thumbnail, each bolted to a heatsink,
each with its own little isolated power supply and driver so that it can be switched on with +15 V and
held off with a negative voltage.

**Level 2 - Engineering:** The chapter walks through the datasheet-style parameters that the loss and
ZVS models consume: Rds(on) and its temperature coefficient (32 -> 52 mOhm for the C3M0032120K), the
three output-capacitance figures (Coss, Coss,er, Coss,tr) and the charge Qoss that set the ZVS current
and the dead time, the gate charge Qg and the UCC21520 driver with +15 V / -3 V (schematic) or -4 V
(model) bias, the body diode (Vsd 4.0 V) that conducts during dead time, the TO-247-4 Kelvin-source
package and the thermal chain RthJC 0.45 + TIM 0.35 + heatsink 0.22 K/W that puts Tj at 49 C. Every
device number is a datasheet-typical value entered from memory with `verified=False`
(`dabtools/dab/devices.py`), to be re-verified before procurement.

**Level 3 - Research:** Three research threads start at the device: (1) the Coss(v) non-linearity that
makes the energy-based ZVS criterion conservative and the dv/dt under ZVS independent of the gate
resistor (`Advanced_Research_2026/Active_Gate_Drive/`); (2) the drift of Rds(on) and Vth with
bond-wire fatigue and gate-oxide trapping as health indicators, and whether the on-board sensing can
see a 1 % change (`Advanced_Research_2026/SiC_Health_Monitoring/`); (3) the observability result that
Coss cannot be identified from period-average measurements at all
(`Advanced_Research_2026/Digital_Twin/README.md`, section 1).

## The device

### How a power MOSFET works, and SiC versus Si versus GaN
**What is it?** A MOSFET is a voltage-controlled switch: a positive gate-source voltage above the
threshold Vth creates a conducting channel between source and drain; below it the channel disappears
and the drift region blocks the voltage. Silicon carbide is a wide-bandgap semiconductor (about 3.3 eV
versus 1.1 eV for silicon) with roughly ten times the critical electric field, so the blocking region
can be ten times thinner for the same voltage and its resistance orders of magnitude lower. GaN HEMTs
are lateral wide-bandgap devices, excellent at 650 V and below, without mature 1200 V discrete parts
at this current.

**Why do we need it?** At 850 V DC the switch must block at least 1200 V with margin; at 100 kHz it
must switch in tens of nanoseconds; at 6.6 kW it must conduct 10-20 A with milliohm-class resistance.
Si IGBTs are too slow (tail current), Si superjunction MOSFETs have a poor body diode and large Coss at
this voltage; SiC MOSFETs do all three at once.

**How does it work?**
**Level 1 - Beginner:** A gate voltage opens a gate; current flows from drain to source through a
thin layer of crystal. In SiC the crystal is so strong that the layer can be thin, and a thin layer has
low resistance and little stored charge - so it is both efficient and fast.
**Level 2 - Engineering:** The device is characterised by: Vds rating (1200 V), Id rating (63 A /
115 A at 25 C), Rds(on) at 25 and 150 C, gate thresholds Vgs,th (2.5 V typ.), recommended Vgs,on (+15 V)
and Vgs,off (-4 V in the model), the gate charges Qg / Qgs / Qgd, the output capacitances and charge,
the switching energies Eon / Eoff at a test point, the body-diode drop Vsd, RthJC and Tj,max (175 C)
(`dabtools/dab/devices.py`). The datasheet links are given in the file; the values must be re-read from
the current datasheet revision.
**Level 3 - Research:** SiC MOSFET channels have lower mobility than Si, so the channel is a larger
share of Rds(on) and the threshold voltage shows hysteresis and drift under gate stress; this is what
makes Vth a degradation indicator (literature ids L11, L13) and what makes the -3 V / -4 V off-bias
question relevant (see the gate-drive topic).

**Example from our converter:** `[Implemented]` HV bridge Q1-Q4: Wolfspeed C3M0032120K, 1200 V,
32 mOhm, TO-247-4, used at 850 V (71 % of rating); LV bridge Q5-Q8: C3M0016120K, 1200 V, 16 mOhm, used at
450 V (38 %) (`16_BOM/bom.md`). The PSFB baseline uses the 650 V C3M0060065K at 420 V and 200 V silicon
synchronous rectifiers (`docs/03_component_selection.md`) - a reminder that the device choice follows
the port voltage.

**Engineering calculations:** Voltage margin HV: 1200 - 850 = 350 V for overshoot (loop inductance
15 nH assumed at 25 A/us... the ZVS edges have no hard di/dt, the overshoot concern is the hard-switched
light-load edge, `Advanced_Research_2026/Active_Gate_Drive/README.md`, section 2). Current margin:
9.75 A nominal peak and 19.6 A corner peak against 63 A (HV); 19.5 / 39.2 A against 115 A (LV).

**Design decision made in this project:** `[Implemented]` 1200 V C3M devices on both bridges, 32 mOhm
on the HV side (lower Coss, lower Qg, lower cost) and 16 mOhm on the LV side (twice the current); TO-247-4
with Kelvin source (MEC-03). Paralleling is not needed at 6.6 kW (`02_Topology_Comparison/topology_comparison.md`,
section 6).

**Alternatives considered:** C3M0016120K on both sides (lower conduction loss, higher Coss -> higher
ZVS threshold on the HV side); 650 V GaN or SiC on the LV bridge (450 V + ringing leaves too little
margin, and separate drive design); modules instead of discretes (cost, layout).

**How to verify it:** Every design pin is checked to exist in the symbol `Q_NMOS_KELVIN` and the
footprint `TO-247-4_Vertical` by `SiC_6k6_Industrial_DAB/18_Verification/run_verification.py`
(`09_Component_Libraries/README.md`); the electrical parameters are not verifiable without the datasheet
and a double-pulse test. `[Verified]` for the pin check; `[Not yet tested]` for the parameters.

**Common mistakes:** Treating a SiC MOSFET like a Si MOSFET at the gate (it needs +15 V, not +10 V, for
full enhancement and a negative off-bias for noise margin); using a 650 V part on a 450 V port with
20-30 V/ns edges; mixing Id at 25 C case with the real operating temperature.

**Interview explanation (30 s):** A SiC MOSFET blocks 1200 V with a drift region a tenth as thick as
silicon would need, so it has milliohm resistance, tiny stored charge and switches in nanoseconds. We
use 32 mOhm parts at 850 V and 16 mOhm parts at 450 V, eight in total, in Kelvin-source TO-247-4.

**Research-level explanation:** The honest statement of the project is that the device data are
datasheet-typical values from memory; the loss chain exposes its sensitivity so the numbers can be
swapped; the research modules then ask what happens when they drift (health monitoring), when they are
uncertain (UQ) and whether they can be estimated in operation (twin: L yes, Coss no).

### Rds(on) and its temperature dependence
**What is it?** The on-state resistance between drain and source with the channel fully enhanced;
it rises with junction temperature.

**Why do we need it?** It sets the conduction loss I_rms_dev^2 Rds(on)(Tj), the largest semiconductor
loss term in this converter (6.1 W HV, 12.5 W LV at nominal) and the thermal feedback loop
Tj -> Rds -> loss -> Tj.

**How does it work?**
**Level 1 - Beginner:** A warm wire resists more than a cold one; the same is true of the transistor
channel. If the device heats up, it loses more, which heats it further - the heatsink must stop that
spiral early.
**Level 2 - Engineering:** `dabtools/dab/devices.py` stores Rds_25 = 32 mOhm and Rds_150 = 52 mOhm for the
C3M0032120K (ratio 1.6), 16 and 27 mOhm for the C3M0016120K (1.7), and `rds_on(dev, Tj)` interpolates
linearly between them (extrapolating above 150 C). At the design Tj of 49 C (HV) the value is 35.8
mOhm; at 51 C (LV) 17.7 mOhm. Figure `img/ch03_rds_vs_tj.png` plots the three devices of the file with
the design points (`img/fig_ch03_devices.py`).
**Level 3 - Research:** The real curve is not linear and depends on Vgs (channel share); ageing
raises Rds(on) through bond-wire lift-off and die-attach fatigue (package) and through Vth drift
(channel). `Advanced_Research_2026/SiC_Health_Monitoring/README.md` models +7.1 % after three
synthetic years, of which only ~0.6 % is the Vth share, and asks whether the on-board chain can detect
a 1 % drift.

**Example from our converter:** `[Simulated]` HV bridge conduction 6.1 W = 4 x (9.23 / sqrt 2)^2 x
0.0358 Ohm; LV bridge 12.5 W = 4 x (18.46 / sqrt 2)^2 x 0.0177 Ohm (`04_Design_Calculations/design_values.json` -> `nominal`).
At the 650/300 V corner the currents rise to 13.7 / 27.5 A rms and the losses with their squares.

**Engineering calculations:** Thermal feedback at nominal: if Tj rose from 49 C to 150 C the HV
conduction loss would rise by 52/35.8 = 1.45x; with the 0.22 K/W heatsink that cannot happen (Tj < 70 C
at 45 C ambient, < 95 C even if the losses were twice the model, `13_Thermal_Analysis/thermal_report.md`,
section 2).

**Design decision made in this project:** `[Implemented]` Loss model evaluated with Rds at the
solved Tj (the design script iterates loss and temperature), not at 25 C; Tj limit 150 C in the
derating map although the device allows 175 C (`00_Requirements/01_requirements_specification.md`
design limits, `04_Design_Calculations/dab_design.py`).

**Alternatives considered:** Datasheet Rds(Tj) curve fit instead of two-point interpolation (to do
once the datasheet is archived); a positive-temperature-coefficient argument for paralleling (not
needed here).

**How to verify it:** Bench: Vds,on at known Id and Tcase after thermal soak; in operation: the
temperature-compensated estimator of `Advanced_Research_2026/SiC_Health_Monitoring/02_estimators_and_detection.py`
(synthetic data). `[Simulated]`, `[Not yet tested]`

**Common mistakes:** Loss at 25 C; forgetting the device rms is the bridge rms / sqrt(2); using Tcase
for Tj; assuming the temperature coefficient of SiC is as large as that of superjunction silicon (it
is smaller, 1.6x versus 2-2.5x).

**Interview explanation (30 s):** Rds(on) goes from 32 to 52 mOhm between 25 and 150 C; our devices
run at about 50 C so we use 36 mOhm, giving 6.1 W for the HV bridge. The positive coefficient is a
feedback loop that the 0.22 K/W heatsinks keep harmless.

**Research-level explanation:** Separating package ageing from gate-oxide ageing needs Vth or the
body-diode drop as a second indicator (L13); Rds(on) alone cannot, and the project's synthetic study
finds that the Vth share is below the detection floor anyway.

### Output capacitance Coss, Qoss and the ZVS current
**What is it?** The drain-source capacitance of the off device, strongly voltage dependent. Three
figures summarise it: Coss (small-signal, at a given voltage), Coss,er (the constant capacitance that
stores the same energy up to Vds), Coss,tr (the constant capacitance that stores the same charge, i.e.
gives the same transition time), and the charge Qoss(V) = integral of Coss dv.

**Why do we need it?** The ZVS condition is an energy (or charge) balance between the inductor and the
two output capacitances of a leg; the dead time must be long enough for the inductor current to move
2 Qoss; and under ZVS the switching-node dv/dt equals I / (2 Coss,tr). Coss therefore sets the
light-load limit of soft switching, the dead time and the EMI slope.

**How does it work?**
**Level 1 - Beginner:** Each switch carries a small invisible capacitor across it. Before a switch can
turn on without a bang, that capacitor must be emptied - by the inductor current, during the dead time.
Little current, slow emptying; too little current, not emptied in time, bang.
**Level 2 - Engineering:** HV device: Coss 100 pF at 800 V, Coss,er 170 pF, Coss,tr 320 pF, Qoss 200 nC
at 800 V; LV device: 200 / 350 / 650 pF, Qoss 420 nC (`dabtools/dab/devices.py`). Energy criterion (`dab_model.zvs_current_min`):
I_min = sqrt(2 (Coss,er V^2 + 0.5 C_par V^2) / L) = 2.0 A at 800 V with L = 64 uH and C_par = 60 pF;
3.07 A on the LV bridge (`04_Design_Calculations/design_values.json` -> `nominal.Imin1/2`). Charge-based dead time
(`dab_model.dead_time_required`): t_d >= 2 Qoss / I = 2 x 200 nC / 9.75 A = 41 ns at nominal; the
function floors it at 50 ns and the firmware uses 150 ns. Figure `img/ch03_zvs_current_min.png` shows
I_min over the voltage range of each bridge.
**Level 3 - Research:** The energy criterion is conservative against the exact charge-based condition
(Everts et al. 2014, reference [14]); the relevant capacitance includes the transformer winding
capacitance referred to the bridge (C_par) and the heatsink/PCB stray capacitance, which the
`Advanced_Research_2026/Parasitic_Extraction/` module estimates from the board geometry. The
observability study of the twin finds that period-average measurements have zero sensitivity to Coss,
so an online Coss estimate requires a transition-time sensor (proposed, not built).

**Example from our converter:** `[Simulated]` ZVS margins at nominal 7.6 A (HV) and 8.2 A (LV); the
tightest full-power corners are 0.7 A (HV at 650/450 V) and 3.0 A (LV at 850/300 V)
(`04_Design_Calculations/design_report.md`, section 2). Under ZVS the node slope is I / (2 Coss,tr) =
9.75 / (2 x 320 pF) = 15 V/ns at nominal and ~30 V/ns at the corners, on both bridges
(`Advanced_Research_2026/Active_Gate_Drive/README.md`, section 3).

**Engineering calculations:** Coss energy per leg at 800 V: 170 pF x 800^2 = 109 uJ; dumped at every
hard-switched turn-on it costs 10.9 W per leg at 100 kHz, which `dabtools/dab/losses.py` adds whenever the edge
current is below I_min. Transition time by charge: 2 Qoss / I = 41 ns at 9.75 A, 20 ns at 19.6 A, 200 ns
at 2 A (just at the ZVS limit, the 150 ns dead time is then too short - the energy criterion and the
dead time must be checked together).

**Design decision made in this project:** `[Implemented]` Fixed 150 ns dead time with energy-based
ZVS maps for the envelope; EPS voltage matching in firmware to keep the edge currents above I_min at
light load; adaptive dead time left to research (`Advanced_Research_2026/Adaptive_MPC/`).

**Alternatives considered:** Larger L (more ZVS energy, less power capability); devices with smaller
Coss on the LV side (C3M0032120K: 170 pF Coss,er versus 350 pF, at twice the conduction loss); external
snubber capacitors to slow dv/dt (would raise I_min further).

**How to verify it:** `DABPoint.zvs_margin()` per edge in `dabtools/dab/dab_model.py`; the ngspice
model with Coss (`05_Simulation/gen_spice.py`); on hardware a drain-voltage probe at turn-on and a
transition-time measurement. `[Simulated]`, `[Not yet tested]`

**Common mistakes:** Using Coss at 800 V (100 pF) in the energy balance instead of Coss,er (170 pF);
forgetting that two devices per leg take part (one charging, one discharging); fixing a dead time
without checking the slowest (lowest-current) edge in the envelope.

**Interview explanation (30 s):** Each SiC device has about 100-300 pF of output capacitance holding
109 uJ at 800 V. The inductor current must discharge it in the dead time: that needs at least 2 A on
the HV bridge and gives a 15 V/ns edge at nominal current, independent of the gate resistor. Below
roughly a third of full load the current is too small and ZVS is lost.

**Research-level explanation:** Coss(v) is the quantity that no sensor on the board can identify; the
Fisher-information study ranks the sensors and shows a transition-time sensor would make Coss
identifiable to 0.03 % after 1000 periods, which is the hardware proposal E3 of the twin.

## Driving and protecting the device

### Gate charge, the UCC21520 driver and the +15 V / negative bias
**What is it?** Qg is the charge that must be moved into the gate to swing it from Vgs,off to Vgs,on
(87 nC for the C3M0032120K, 180 nC for the C3M0016120K, at +15 / -4 V in `dabtools/dab/devices.py`); Qgs and Qgd are
the gate-source and Miller (gate-drain) portions. The gate driver supplies this charge quickly from an
isolated bias supply; the UCC21520DW is a dual-channel reinforced-isolated driver (5.7 kVrms, 4 A source
/ 6 A sink) with a programmable interlock dead time.

**Why do we need it?** The gate must move 87-180 nC in a few tens of nanoseconds (amperes of peak
current) from a supply that floats at the switch-node potential (0-850 V), with reinforced isolation to
the controller; and SiC gates need +15 V for full enhancement and a negative off-bias so that the Miller
current at 15-30 V/ns cannot lift the gate above threshold (crosstalk).

**How does it work?**
**Level 1 - Beginner:** The gate is a small bucket that must be filled to turn the switch on and
emptied to turn it off; the driver is a fast pump, with its own little floating battery, controlled
through an insulating window by the controller.
**Level 2 - Engineering:** Each leg has one UCC21520DW (U1-U4) powered from +5 V on the logic side and
from an isolated module per device on the output side: RECOM R12P21503D, 12 V in, +15 V / -3 V out, 2 W
(PS1-PS8, pinout not yet verified), with 10 uF / 1 uF on +15 V and 4.7 uF / 1 uF on -3 V (`16_BOM/bom.md`).
Gate network: Rg,on 3.3 Ohm, Rg,off 1.5 Ohm through an SS14 steering diode, 10 k gate-source bleed;
interlock dead time ~22 ns from a 2.2 k resistor on DT. Gate loss per device Qg (Vgs,on - Vgs,off) fs =
0.165 W (HV) and 0.342 W (LV) with the model's 19 V swing; 2.03 W total in the budget. Average gate
current at 100 kHz: 87 nC x 1e5 = 8.7 mA; peak during the 50 ns edge about 1.7 A, within the 4/6 A driver.
**Level 3 - Research:** Discrepancy to resolve: the schematic bias is +15 / -3 V while the loss model
assumes -4 V (`Advanced_Research_2026/Active_Gate_Drive/README.md`, section 1 lists it). The gate-drive
study shows why it matters: with -3 V the crosstalk margin at the worst ZVS corner is -0.1 V on the HV
bridge and -3.0 V on the LV bridge (the induced gate voltage reaches the 1.8 V minimum threshold at
150 C), while -4 V or a Miller clamp restores a positive margin; the LV bridge self-limits its dv/dt at
12 V/ns with -3 V. Active gate drive (multi-level, adaptive, L21 / L22) cannot help under ZVS because
dv/dt is set by I / (2 Coss,tr), not by the gate.

**Example from our converter:** `[Implemented]` Four UCC21520DW, eight R12P21503D, sixteen gate
resistors (R102.., R103..), eight SS14, 2.2 k DT resistors (`16_BOM/bom.md`); the driver is described as
"DESAT-type driver (UCC21710) is the documented upgrade path" because the UCC21520 has no DESAT and no
Miller clamp.

**Engineering calculations:** Gate resistor power is the same 0.165 W per HV device (it is where the
Qg x V x fs energy ends up, split between on and off resistors and the driver); bias module load 0.17-0.34 W
plus the driver's own quiescent, well inside 2 W. Miller-induced gate voltage at the worst corner:
V_off + R_off (Qgd / V) dv/dt (1 - exp(-t_tr / tau)) as in the study - the sign of the result is what the
-3 V / -4 V choice decides.

**Design decision made in this project:** `[Implemented]` Asymmetric 3.3 / 1.5 Ohm gate network with
negative off-bias; reinforced-isolated drivers; one bias module per device referenced to the Kelvin
source. `[Proposed]` upgrade to a DESAT / Miller-clamp driver (UCC21710) and to a reinforced-rated bias
module (open safety item 15.1).

**Alternatives considered:** -5 V bias (Murata MGJ2D121505SC is a drop-in with -5 V,
`docs/03_component_selection.md`); Miller-clamp drivers; slower 10 / 10 Ohm resistors (worse crosstalk
margin, more hard-switching loss - option D of the study); transformer-coupled gate drive.

**How to verify it:** `python3 Advanced_Research_2026/Active_Gate_Drive/gate_drive_analysis.py`
(analytic, datasheet-model based, < 5 s); on hardware, gate-voltage probing at the Kelvin pins during
the fastest edge. `[Simulated]`, `[Not yet tested]`

**Common mistakes:** Referencing the gate return to the power source instead of the Kelvin source;
counting gate loss in the device (it is in the resistors and driver); forgetting that the bias module's
isolation must match the barrier class; assuming a slower gate resistor slows a ZVS edge.

**Interview explanation (30 s):** Each SiC gate needs 87-180 nC moved in tens of nanoseconds from a
supply floating at up to 850 V, so every device has its own isolated +15 / -3 V module and shares a
reinforced-isolated UCC21520 with its leg partner, through 3.3 Ohm on and 1.5 Ohm off. The whole gate
budget is 2 W; the open question is whether -3 V is enough off-bias at 30 V/ns, where the model says
the margin is slightly negative.

**Research-level explanation:** The gate-drive study is a datasheet-model analysis (L1 maturity): its
conclusion that under ZVS the gate resistor has no influence on dv/dt, and that the crosstalk margin
rather than switching loss is the design driver, should be tested with a gate-loop SPICE model
including the extracted loop inductance before a hardware decision on the bias voltage.

### The body diode and dead time
**What is it?** Every MOSFET contains a p-n body diode from source to drain. In SiC it has a high
forward drop (Vsd = 4.0 V at 20 A for the C3M0032120K, 4.2 V for the C3M0016120K, with Vgs = -4 V) but
negligible reverse recovery. It conducts during the dead time, when the inductor current must flow
through the leg while both channels are off.

**Why do we need it?** We do not want it, but it is there and it is useful: it clamps the switch node
after the ZVS transition so that the channel can be turned on at zero voltage; the price is Vsd x I for
the remainder of the dead time.

**How does it work?**
**Level 1 - Beginner:** When both switches of a leg are off for a moment, the inductor current still
has to go somewhere; it pushes open a one-way valve inside the switch. That valve drops 4 V, like
pushing water through a stiff flap, so the dead time should be as short as safely possible.
**Level 2 - Engineering:** `dabtools/dab/losses.py` charges P_diode = Vsd x I x t_dead x fs x 0.5 per ZVS edge:
0.87 W for the HV bridge and 1.23 W for the LV bridge at nominal with t_dead = 150 ns
(`04_Design_Calculations/design_values.json` -> `nominal.losses`). The dead time also reduces the effective phase shift, which
the controller compensates (phi_dead_comp = 0.047 rad). The charge-based minimum dead time is
2 Qoss / I (41 ns at nominal, 200 ns at the 2 A ZVS limit).
**Level 3 - Research:** With a trapezoidal current the diode conduction interval is the dead time
minus the transition time, both current dependent; an adaptive dead time (per edge, per operating
point) would recover most of the 2.1 W and extend the ZVS range at light load, but needs either a map
(Adaptive_MPC zvs maps) or a transition-time sensor (Digital_Twin E3). Reverse recovery of the SiC body
diode is small but not zero and is not in the model.

**Example from our converter:** `[Simulated]` Dead time 150 ns (`04_Design_Calculations/design_values.json` -> `t_dead`) is
1.5 % of the period; at the 2 A HV ZVS limit the charge-based transition alone takes 2 x 200 nC / 2 A =
200 ns, longer than the dead time - so at the ZVS boundary the device turns on with residual voltage
even though the energy criterion is just met. This is why the derating map's ZVS boundary should be
read with a margin.

**Engineering calculations:** Diode energy per edge at nominal: 4.0 V x 9.75 A x (150 - 41) ns ~ 4.3 uJ;
two edges per device per period... the model's 0.5 factor approximates the share of the dead time in
diode conduction; 0.87 W per bridge is the result. Not large, but comparable to the ZVS turn-off loss
(2.8 W) and larger than the gate loss per bridge.

**Design decision made in this project:** `[Implemented]` 150 ns firmware dead time plus 22 ns hardware
interlock; dead-time compensation in the modulator inverse (`dabtools/dab/control.py`).
`[Proposed]` adaptive dead time.

**Alternatives considered:** Anti-parallel SiC Schottky diodes (lower drop, extra Coss and cost -
used in the PSFB only as clamp diodes); synchronous turn-on earlier (channel conducts in reverse at
I x Rds instead of 4 V, which is exactly what happens after the dead time ends).

**How to verify it:** Body-diode conduction appears in the ngspice model (`05_Simulation/gen_spice.py`);
on hardware, the Vds waveform during dead time shows the -4 V plateau. `[Simulated]`, `[Not yet tested]`

**Common mistakes:** Dead time so long that the body diode conducts for most of the transition (loss)
or so short that the leg is not fully commutated (partial hard switching); forgetting that the SiC body
diode drop is 4 V, not 0.7 V, when estimating dead-time loss.

**Interview explanation (30 s):** During the 150 ns dead time the inductor current flows through the
SiC body diode at about 4 V, costing roughly 2 W for both bridges and slightly shortening the phase
shift, which the controller compensates. The minimum dead time is set by the charge 2 Qoss / I: 41 ns at
full load but 200 ns at the ZVS limit.

**Research-level explanation:** The charge-based dead-time rule and the energy-based ZVS rule disagree
exactly at light load, where the DAB is weakest; a per-edge adaptive dead time driven by an estimated
or measured transition time is the research item that links the gate drive, the twin and the MPC
modules.

### TO-247-4 Kelvin source, mounting and thermal resistance
**What is it?** The TO-247-4 package has a fourth pin, the Kelvin source, connected to the die's source
separately from the power source pin so that the gate loop does not include the power lead's
inductance. The thermal path is die -> case (RthJC 0.45 K/W HV, 0.30 K/W LV) -> thermal interface pad
(0.35 K/W) -> heatsink (0.22 K/W per bridge at 3 m/s) -> ambient (45 C).

**Why do we need it?** At 10-20 A changing in tens of nanoseconds, a few nanohenries of common
source inductance would induce volts of negative feedback into the gate loop and slow or destabilise
switching; the Kelvin pin removes this. Thermally, each device must stay below 150 C (design limit)
with margin for the unverified loss data.

**How does it work?**
**Level 1 - Beginner:** The chip sits on a metal tab that is screwed to a finned aluminium bar with a
soft heat-conducting pad in between; a fan blows air over the fins. The fourth pin is a "quiet" wire
to the chip for the gate signal, separate from the "noisy" wire that carries the big current.
**Level 2 - Engineering:** Steady-state temperatures: T_sink = T_amb + P_bridge x 0.22; T_j = T_sink +
P_device x (0.35 + RthJC). HV: 45 + 9.8 x 0.22 = 47.2 C; + 2.45 x 0.80 = 49.1 C (`04_Design_Calculations/design_values.json`
-> `nominal.Tj1` = 49.1). LV: 45 + 15.7 x 0.22 = 48.5 C; + 3.93 x 0.65 = 51.0 C (`nominal.Tj2` = 51.0).
Worst corner at 55 C ambient: 64 / 68 C (`13_Thermal_Analysis/thermal_report.md`, section 2). Symbol
pins: 1 G, 2 D, 3 KS, 4 S (`dabtools/kicad_dab/design_dab.py`); footprint `TO-247-4_Vertical`; the
devices stand vertically along the heatsink bars (two 150 x 60 x 40 mm extrusions).
**Level 3 - Research:** The thermal numbers are catalogue-class assumptions; the 2026 thermal twin
(E4) finds a 1.1 K rms / 14 K peak Tj estimation error dominated by a +15 % RthJC and +10 % loss-model
error, not by sensor noise - only hardware calibration can reduce it
(`Advanced_Research_2026/Digital_Twin/results/twin_study.json`, E4). Power-cycling lifetime is not a
concern at dTj ~ 4 K per cycle (`13_Thermal_Analysis/thermal_report.md`, section 4).

**Example from our converter:** `[Simulated]` Cooling options compared: natural convection gives Tj
71 / 86 C at 45 C ambient and is insufficient at 55 C; forced air 3 m/s gives 54 / 58 C; a cold plate
50 / 52 C. Selected: forced air 3 m/s, two 80 mm fans (`13_Thermal_Analysis/thermal_report.md`, sections 2 and 6). Heatsink
NTCs (J18, J19) trip at 95 C sink temperature, about 110 C junction at the modelled losses.

**Engineering calculations:** Thermal margin: if the real losses were twice the model, Tj would be
45 + 19.6 x 0.22 + 4.9 x 0.80 = 53 C for the HV bridge at nominal - the report's "< 95 C" statement is for
the worst corner at 55 C ambient. Per-device junction-to-ambient resistance (sharing the sink): 0.80 +
4 x 0.22 = 1.68 K/W (HV).

**Design decision made in this project:** `[Implemented]` TO-247-4 Kelvin source required by MEC-03;
one extruded heatsink per bridge with 0.35 K/W silicone pads (electrically insulating, heatsink at PE);
no thermal vias needed under the devices because they sit on the bar (`13_Thermal_Analysis/thermal_report.md`, section 2).

**Alternatives considered:** Cold plate (only for a sealed enclosure); natural convection (fails at
55 C); SMD packages (TOLL, D2PAK-7) with PCB cooling - rejected for the heatsink-bar mechanical
concept and the 850 V creepage.

**How to verify it:** `13_Thermal_Analysis/thermal_analysis.py` (steady state);
`Advanced_Research_2026/Multiphysics_Models/` (transient Foster network); thermocouple under the pad
and NTC readings in the lab plan. `[Simulated]`, `[Not yet tested]`

**Common mistakes:** Returning the gate driver to the power source pin on a TO-247-4; forgetting the
pad's 0.35 K/W (comparable to RthJC); using the heatsink's 0.22 K/W per device instead of per bridge;
confusing Tj,max (175 C) with the design limit (150 C) and the NTC trip (95 C sink).

**Interview explanation (30 s):** The Kelvin-source pin keeps the big current's lead inductance out
of the gate loop, essential at 15-30 V/ns. Thermally each device sees 0.45 K/W to its case, 0.35 K/W
through the pad and a shared 0.22 K/W heatsink at 3 m/s, which puts the junctions at about 49-51 C at
45 C ambient - far below the 150 C design limit.

**Research-level explanation:** The junction temperature is not measurable on hardware; it is
estimated. The twin's thermal observer error is dominated by model parameters, which makes RthJC
calibration (a controlled power-cycling measurement with the body-diode drop as a temperature-sensitive
parameter) the first experimental task for any health-monitoring claim.

## Worked example(s) with real numbers

**Example 1 - from datasheet numbers to the loss lines.** `[Simulated]` HV device: I_rms_dev = 9.23 /
sqrt(2) = 6.53 A; Rds(49.1 C) = 0.032 + (0.052 - 0.032) x (49.1 - 25)/125 = 35.9 mOhm; P_cond = 6.53^2 x
0.0359 = 1.53 W per device, 6.1 W per bridge. Turn-off: Eoff scaled from 55 uJ at 800 V / 20 A to the
9.75 A edge: 55 x 9.75/20 = 26.8 uJ; x fs x k_zvs = 26.8e-6 x 1e5 x 0.35 = 0.94 W per edge-device; the
model sums over the edges of the bridge to 2.8 W. Diode: 0.87 W. Gate: 4 x 0.165 = 0.66 W (in the
resistors). Bridge total 9.8 W; the loss file agrees (`04_Design_Calculations/design_report.md`).

**Example 2 - is 150 ns the right dead time?** `[Simulated]` Charge-based transition time
2 Qoss / I: at 19.6 A (850/300 V corner) 20 ns; at 9.75 A 41 ns; at 4.4 A (50 % load, `05_Simulation/switched_results.json`
gives 4.96 A peak at 50 %) 90 ns; at the 2.0 A ZVS limit 200 ns. The 150 ns dead time therefore covers
ZVS down to about 2.7 A of edge current (2 x 200 nC / 150 ns), slightly above the energy-criterion
limit of 2.0 A. The LV bridge, with Qoss 420 nC at 800 V (less at 400 V, value not in the file), needs
2 x 420 / 19.5 = 43 ns at nominal and 150 ns at 5.6 A. Conclusion: 150 ns is reasonable for the
full-power envelope and slightly short at the ZVS boundary - exactly where an adaptive dead time
would help.

**Example 3 - the thermal chain.** `[Simulated]` Worst corner (650/300 V, 140 W total): HV bridge 21.7 W,
LV bridge 34.9 W (`13_Thermal_Analysis/thermal_report.md`, section 1). At 55 C ambient: HV sink 55 +
21.7 x 0.22 = 59.8 C, Tj = 59.8 + 5.4 x 0.80 = 64 C; LV sink 55 + 34.9 x 0.22 = 62.7 C, Tj = 62.7 + 8.7 x
0.65 = 68 C. The report's table gives 64 / 68 C. The NTC trip at 95 C sink would need about 180 W in one
bridge - a fault, not an operating point.

## How this chapter connects to the files

| File | What it contains | Status |
|---|---|---|
| `SiC_6k6_Industrial_DAB/dabtools/dab/devices.py` | C3M0032120K, C3M0016120K, C3M0060065K parameters, datasheet-typical, verified=False; rds_on(Tj) | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/dabtools/dab/losses.py` | conduction, ZVS turn-off (k_zvs 0.35), hard switching, dead-time diode, gate loss | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/dabtools/dab/dab_model.py` | zvs_current_min(), dead_time_required() | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/04_Design_Calculations/design_values.json` | Imin1/2, ZVS margins, Tj1/2, loss lines, t_dead | `[Simulated]` |
| `SiC_6k6_Industrial_DAB/16_BOM/bom.md` | Q1-Q8, U1-U4 UCC21520DW, PS1-PS8 R12P21503D, gate resistors, SS14, DT resistors, NTC headers | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/09_Component_Libraries/README.md` | symbol/footprint generation and the pin-existence check | `[Verified]` |
| `SiC_6k6_Industrial_DAB/dabtools/kicad_dab/design_dab.py` | pin map G/D/KS/S, bias +15/-3 V text, driver description | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/13_Thermal_Analysis/thermal_report.md` | heat sources, cooling options, Tj, capacitors, cycling | `[Simulated]` |
| `SiC_6k6_Industrial_DAB/15_Safety_Reliability/01_insulation_coordination.md` | isolator ratings, bias-module open item | `[Implemented]` |
| `Advanced_Research_2026/Active_Gate_Drive/README.md` | Rg / bias / Miller-clamp trade-off, dv/dt under ZVS, -3 V vs -4 V discrepancy | `[Simulated]` |
| `Advanced_Research_2026/SiC_Health_Monitoring/README.md` | Rds_on / Vth drift indicators on synthetic data | `[Simulated]` |
| `Advanced_Research_2026/Digital_Twin/README.md` | Coss not observable; E3 transition-time sensor proposal; E4 thermal twin | `[Simulated]` / `[Proposed]` |
| `docs/03_component_selection.md` | PSFB devices and bias modules for comparison | `[Implemented]` |
| `21_Human_Friendly_Learning_Notes/img/fig_ch03_devices.py` | Rds(Tj) and I_min figures from devices.py | `[Implemented]` |

## Viva / interview questions

### Basic (10)
1. What does "SiC" change compared with silicon in a power MOSFET?
   A wider bandgap and about ten times the critical field: the blocking layer can be ten times thinner,
   so a 1200 V device has milliohm resistance, little stored charge and fast switching.
2. Which devices does the DAB use and at what voltage?
   C3M0032120K (1200 V, 32 mOhm) on the HV bridge at up to 850 V; C3M0016120K (1200 V, 16 mOhm) on the LV
   bridge at up to 450 V; four of each.
3. What is Rds(on) and how does it change with temperature?
   The on-state resistance; 32 mOhm at 25 C rising to 52 mOhm at 150 C for the HV device (1.6x).
4. What is Coss and why does it matter?
   The output capacitance of the off device; the inductor current must discharge it during the dead
   time for ZVS, and it sets the dv/dt of the switching edge.
5. What gate voltages does a SiC MOSFET need?
   About +15 V on for full enhancement and a negative off-bias (-3 V in our schematic, -4 V in the
   model) for noise margin against the Miller effect.
6. What is the gate driver in this design?
   TI UCC21520DW: dual channel, reinforced isolated (5.7 kVrms), 4 A source / 6 A sink, with a
   programmable interlock dead time (~22 ns here).
7. What is the body diode and when does it conduct?
   The internal source-drain p-n diode (Vsd about 4 V in SiC); it carries the inductor current during
   the 150 ns dead time.
8. What is the Kelvin source pin for?
   It gives the gate loop its own return to the die, removing the power lead's inductance from the gate
   circuit so that fast edges do not feed back into the gate.
9. What are the thermal resistances in the chain?
   RthJC 0.45 K/W (HV) / 0.30 K/W (LV), thermal pad 0.35 K/W, heatsink 0.22 K/W per bridge at 3 m/s.
10. Are the device numbers in this project verified?
    No: `dabtools/dab/devices.py` marks them `verified=False`; they are datasheet-typical values from memory to be
    re-read from the current datasheet before procurement or test.

### Intermediate (10)
1. Compute the HV-bridge conduction loss at the design Tj.
   Rds(49 C) = 35.9 mOhm; I_dev = 9.23 / sqrt 2 = 6.53 A; 4 x 6.53^2 x 0.0359 = 6.1 W.
2. Why are three different Coss figures given, and which one goes where?
   Coss (small-signal, for impedance), Coss,er (energy-equivalent, for the ZVS energy criterion and the
   hard-switching loss Coss,er V^2 fs), Coss,tr (time-equivalent, for the transition time and dv/dt =
   I / (2 Coss,tr)).
3. Derive the minimum ZVS current for the HV bridge.
   E = Coss,er V^2 + 0.5 C_par V^2 = 170 pF x 640 kV^2 + 0.5 x 60 pF x 640 kV^2 = 109 + 19 = 128 uJ;
   I_min = sqrt(2 x 128e-6 / 64e-6) = 2.0 A.
4. How long is the charge-based transition at nominal and at the ZVS limit?
   2 Qoss / I = 2 x 200 nC / 9.75 A = 41 ns; at 2.0 A, 200 ns - longer than the 150 ns dead time.
5. What is the gate-drive loss and where is it dissipated?
   Qg (Vgs,on - Vgs,off) fs per device: 0.165 W (HV), 0.342 W (LV), 2.03 W total, dissipated in the gate
   resistors and the driver output stage, supplied by the bias modules.
6. Why is there a discrepancy between -3 V and -4 V and why does it matter?
   The R12P21503D module gives +15 / -3 V (schematic, BOM) while `dabtools/dab/devices.py` assumes -4 V; the gate-drive
   study finds the crosstalk margin at the worst ZVS corner is -0.1 V (HV) and -3.0 V (LV) with -3 V and
   positive with -4 V or a Miller clamp.
7. Why does the gate resistor not set dv/dt under ZVS?
   The node is discharged by the inductor current through the two Coss before the channel turns on:
   dv/dt = I_sw / (2 Coss,tr) = 15 V/ns at 9.75 A, 320 pF; the gate only affects hard-switched edges.
8. Explain the dead-time diode loss line.
   Vsd x I x t_dead x fs x 0.5 per edge; 0.87 W (HV) and 1.23 W (LV) at nominal with 4.0 / 4.2 V and
   150 ns; it is comparable to the ZVS turn-off loss.
9. Compute Tj of the LV devices at nominal.
   T_sink = 45 + 15.7 x 0.22 = 48.5 C; T_j = 48.5 + 3.93 x (0.35 + 0.30) = 51.0 C.
10. Why is the UCC21710 named as the upgrade path?
    It adds DESAT short-circuit detection, a Miller clamp and isolated analog sensing; the UCC21520 has
    none, so short-circuit protection relies on the shunt/CT comparators (32 A trip).

### Advanced / research (10)
1. Why is the energy-based ZVS criterion conservative and when does it fail on the unsafe side?
   It ignores the current change during the transition (charge criterion, Everts 2014); it fails
   unsafely when the dead time is shorter than 2 Qoss / I even though the energy balance holds - the
   light-load case shown in worked example 2.
2. Why can Coss not be estimated from the on-board sensors?
   Period-average currents and voltages have zero sensitivity to Coss (Fisher information rank 2 with
   all board sensors, `Advanced_Research_2026/Digital_Twin/README.md`, section 1); only a transition-time measurement adds the
   Coss direction.
3. How would the proposed transition-time sensor estimate Coss, and what limits it?
   t_tr = 2 Coss,er V / |I_edge| with I_edge from the model using the estimated L; E3 shows +4.5 % error
   with the estimated L and -11.6 % with the nominal L, so the two estimators must run together.
4. Which degradation mechanisms raise Rds(on) and how could they be separated?
   Bond-wire / die-attach fatigue (package) and gate-oxide trapping (Vth drift); Rds(on) alone cannot
   separate them; Vth or the body-diode drop is the second indicator (L13); the Vth share here is ~0.6 %
   of 7.1 %, below detection.
5. What is the self-limiting dv/dt and why is it different for the two bridges?
   The slope at which the Miller-induced gate voltage reaches Vth,min and the channel re-conducts,
   slowing the edge: 29 V/ns HV, 12 V/ns LV at -3 V, because the LV device has a larger Qgd/Coss ratio
   and lower Rds; it converts a shoot-through risk into loss in a ZVS leg.
6. Critically assess the k_zvs = 0.35 factor.
   It assigns 35 % of the double-pulse Eoff to real dissipation under ZVS; the rest is Coss energy
   recycled to the link. It is an assumption from the Krismer-Kolar model structure; its true value
   depends on the current tail during the capacitive transition and needs calorimetry.
7. How does the thermal twin estimate Tj and what dominates its error?
   A 2-node Foster network per bridge with a Kalman observer from the case NTC and the loss estimate;
   E4 gives 1.1 K rms, 14 K peak during a loss step, dominated by RthJC (+15 %) and loss-model (+10 %)
   errors, not by the 1 K NTC noise.
8. What would an adaptive dead time need and what would it gain?
   Either a ZVS map over the envelope (Adaptive_MPC) or a measured transition time per edge
   (Digital_Twin E3); gain: most of the 2.1 W of diode loss and a few percent of ZVS range at light
   load, plus removal of the partial-hard-switching band at the boundary.
9. Should the LV bridge use a 650 V device?
   450 V plus 30 V/ns ringing and a 32 A trip leave too little margin on a 650 V part, and separate drive
   and footprint design would be needed; the 1200 V C3M0016120K at 38 % of rating is the conservative
   choice, at the cost of higher Coss (350 pF Coss,er) and a 3.07 A ZVS threshold.
10. Which single measurement would most reduce the uncertainty of this chapter?
    A double-pulse test of each device type at 800 V / 400 V with the project's gate network,
    yielding Eon/Eoff, Coss(v), Qoss and the transition time, followed by a calorimetric bridge
    measurement under ZVS to fix k_zvs.

## Pitches

**30 s:** Eight 1200 V SiC MOSFETs switch this converter: 32 mOhm parts at 850 V and 16 mOhm parts at
450 V, in Kelvin-source TO-247-4 on two fan-cooled heatsinks that keep the junctions near 50 C. Each has
its own isolated +15 / -3 V supply and a reinforced-isolated driver. The device numbers in the model are
datasheet-typical and flagged unverified; the open items are the off-bias voltage and the dead time at
light load.

**2 min:** SiC's tenfold critical field gives a 1200 V MOSFET with milliohm resistance and nanosecond
switching, which is why 100 kHz at 800 V is possible at all. The loss model reads six numbers per
device from `dabtools/dab/devices.py` - Rds(on) at 25 and 150 C, Coss,er / Coss,tr / Qoss, Eon / Eoff, Qg, Vsd, RthJC
- and turns them into 9.8 W for the HV bridge and 15.7 W for the LV bridge at nominal: conduction 6.1 /
12.5 W, ZVS turn-off 2.8 / 2.0 W, dead-time diode 0.9 / 1.2 W, gate drive 2 W. Coss decides the ZVS
threshold (2.0 A HV, 3.07 A LV) and the 15-30 V/ns edge slope, which the gate resistor cannot change
under ZVS; the gate-drive study shows the -3 V schematic bias leaves a slightly negative crosstalk
margin at the worst corner, where -4 V or a Miller clamp would fix it. The 150 ns dead time covers
the full-power envelope but is shorter than the 200 ns charge-based transition at the ZVS limit.
Thermally, 0.45 + 0.35 + 0.22 K/W put Tj at 49 / 51 C with margin for a twofold loss error. All of
this is model; the first experiments would be a double-pulse test and RthJC calibration.

**10 min outline:**
* MOSFET operation; SiC vs Si vs GaN; why 1200 V SiC on both bridges; PSFB contrast (650 V SiC + 200 V Si).
* `dabtools/dab/devices.py` parameters, `verified=False`; the sensitivity argument.
* Rds(on)(Tj): 32 -> 52 mOhm; 6.1 / 12.5 W; thermal feedback; figure `img/ch03_rds_vs_tj.png`.
* Coss, Coss,er, Coss,tr, Qoss: I_min 2.0 / 3.07 A; dv/dt 15 / 30 V/ns; figure `img/ch03_zvs_current_min.png`;
  Coss unobservable from period averages.
* Gate: Qg 87 / 180 nC, UCC21520, R12P21503D, 3.3 / 1.5 Ohm, 2 W; -3 V vs -4 V; crosstalk margins.
* Body diode 4.0 V, dead time 150 ns vs 41-200 ns charge-based; 2.1 W; adaptive dead time.
* TO-247-4 Kelvin source; thermal chain; 49 / 51 C nominal, 64 / 68 C worst; cooling options.
* Research: health monitoring (+7.1 % synthetic), gate-drive study, thermal twin E4.
* Status: `[Implemented]` parts, `[Simulated]` numbers, `[Proposed]` sensor and driver upgrade.

## Further reading

* `SiC_6k6_Industrial_DAB/01_Literature_Review/literature_review.md` [20] Millan et al. 2014 (wide
  bandgap survey), [21] [22] Wolfspeed datasheets (to be archived), [23] UCC21710 datasheet, [14] Everts
  et al. 2014 (charge-based ZVS).
* `Advanced_Research_2026/Literature_Database/literature_2022_2026.csv` L11 (SiC prognosis review,
  accessible), L13 (Ugur et al. 2020, condition monitoring, confirmed), L21 and L22 (active gate drive).
* `Advanced_Research_2026/Active_Gate_Drive/README.md` - the full option table and the dv/dt argument.
