# 01 Electrical fundamentals

> Reading time: ~45 min. Prerequisites: school physics (charge, energy, force) and algebra. Files covered:
> `SiC_6k6_Industrial_DAB/04_Design_Calculations/design_values.json`,
> `SiC_6k6_Industrial_DAB/05_Simulation/switched_results.json`,
> `SiC_6k6_Industrial_DAB/06_Magnetics/magnetics_design.md`, `SiC_6k6_Industrial_DAB/16_BOM/bom.md`,
> `SiC_6k6_Industrial_DAB/dabtools/dab/dab_model.py`.

## Overview

**Level 1 - Beginner:** Everything in this repository - the 3 kW PSFB and the 6.6 kW SiC dual active
bridge (DAB) - is built from five ideas: voltage pushes, current flows, power is the product of the two,
energy is power accumulated over time, and two kinds of component (inductors and capacitors) store
energy and resist sudden change. A converter is a machine that moves energy from one voltage level to
another by switching these storage elements on and off very quickly (100 000 times per second here).
If you understand why an inductor "fights" a change of current and a capacitor "fights" a change of
voltage, you already understand half of a DAB.

**Level 2 - Engineering:** The chapter states the laws we use every day - Ohm's law, the inductor law
v = L di/dt, the capacitor law i = C dv/dt, volt-second and charge balance, rms/average/peak, the
transformer turns ratio - and applies each of them to a real number from our files: the 64 uH series
inductor at 800 V and 100 kHz (slope 25 A/us, 9.75 A peak), the 120 uF LV link with its 0.11 V ripple
and 8.4 A rms current, the 28:14 transformer at 0.13 T. All numbers are calculated or simulated
`[Simulated]`; nothing has been measured.

**Level 3 - Research:** The same laws, written as a differential equation L di/dt = v1(t) - v2'(t), are
the whole electrical model of the DAB (chapter 05). Research questions start where the ideal laws stop:
the inductance that is not constant (core saturation, +/-5 % gap tolerance, +/-20 % leakage tolerance),
the capacitor whose ESR and ESL matter at 100 kHz, the "rms" that is defined per switching period and
then used as a parameter-estimation regressor in the 2026 digital twin (`Advanced_Research_2026/Digital_Twin/`).

## Voltage, current, power and energy

### Voltage, current, power, energy and their units
**What is it?** Voltage (V, volt) is the energy given to each coulomb of charge; current (I, ampere) is
the rate at which charge flows; power (P, watt) is the rate of energy transfer, P = V I; energy (J, joule
= watt-second) is power integrated over time, E = integral of P dt. The kilowatt-hour is 3.6 MJ.

**Why do we need it?** The whole specification of the DAB is written in these units: 6.6 kW between an
800 V bus and a 400 V bus (`SiC_6k6_Industrial_DAB/00_Requirements/01_requirements_specification.md`, EL-01 to EL-03).
Every loss, every rating and every efficiency figure is a ratio or product of these four quantities.

**How does it work?**
**Level 1 - Beginner:** Think of water: voltage is the pressure, current is the flow rate, power is
pressure times flow (how fast the water wheel turns), energy is how much work the wheel has done since
morning. A 6.6 kW converter is a "pump" moving 6600 joules every second from one tank to another.
**Level 2 - Engineering:** P = V I holds for instantaneous values; for periodic waveforms the average
power is the average of v(t) i(t) over a period, not the product of the averages. At the HV port
6600 W / 800 V = 8.25 A average; at the LV port 6600 W / 400 V = 16.5 A. The `DABPoint.P` property in
`dabtools/dab/dab_model.py` literally computes `np.mean(v1 * i)` over one switching period - the
textbook definition.
**Level 3 - Research:** Instantaneous power can be negative for part of the period even when the average
is positive. In the DAB this reactive or "backflow" power (301.6 W at nominal,
`04_Design_Calculations/design_values.json` -> `nominal.backflow`) circulates between the two DC links and costs conduction
loss without delivering energy; reducing it is the purpose of the DPS/TPS modulations of chapter 04.

**Example from our converter:** `[Simulated]` At 800/400 V and 6.6 kW the model gives an HV-side rms
current of 9.23 A and a peak of 9.75 A while the average HV port current is only 8.25 A
(`SiC_6k6_Industrial_DAB/04_Design_Calculations/design_values.json`, `nominal.Irms1`, `nominal.Ipk1`).
The difference between 8.25 A (what the bus sees on average) and 9.23 A (what heats the copper) is the
first lesson of power electronics.

**Engineering calculations:** Average port currents: I1 = P/V1 = 6600/800 = 8.25 A, I2 = P/V2 =
6600/400 = 16.5 A. Energy stored in the HV link at 800 V: E = 0.5 C V^2 = 0.5 x 80 uF x 800^2 = 25.6 J
(C1 = 80 uF, `04_Design_Calculations/design_values.json` -> `dclink.C1`); in the LV link 0.5 x 120 uF x 400^2 = 9.6 J. Energy in
the series inductor at the 9.75 A peak: 0.5 x 64 uH x 9.75^2 = 3.0 mJ. The link stores about 8000 times
more energy than the inductor; this is why the links are "stiff" and the inductor is the fast element.

**Design decision made in this project:** `[Implemented]` The requirements express every limit in
these base units with explicit service conditions (`00_Requirements/01_requirements_specification.md`), and the
calculation chain (`04_Design_Calculations/dab_design.py`) reports losses in watts per element so that
efficiency (98.62 % calculated at nominal, `04_Design_Calculations/design_report.md` section 4) is traceable to each term.

**Alternatives considered:** Expressing the design in per-unit (p.u.) quantities, as in machine
theory. Rejected for readability: the engineers reviewing the schematic think in volts and amperes.

**How to verify it:** `python3 SiC_6k6_Industrial_DAB/04_Design_Calculations/dab_design.py`
regenerates `04_Design_Calculations/design_values.json`; the identity P = mean(v1 i) is tested implicitly by the closed-form
cross-check in chapter 05 (`03_Mathematical_Models/dab_mathematical_model.md`, section 2).
`[Verified]` in the sense that the script runs; `[Not yet tested]` on hardware.

**Common mistakes:** Multiplying average voltage by average current to get power (wrong for switched
waveforms); confusing energy (J) with power (W); writing "kW/h" for energy.

**Interview explanation (30 s):** Voltage is energy per charge, current is charge per second, so their
product is energy per second - power. Our converter moves 6.6 kW: 8.25 A at 800 V in, 16.5 A at
400 V out, and the losses are the few tens of watts that do not arrive.

**Research-level explanation:** For switched converters the useful quantity is the period-average of
v(t) i(t); its decomposition into delivered and circulating parts (Krismer and Kolar 2010,
`01_Literature_Review/literature_review.md` [6]) is what every modulation-optimisation paper minimises.

### Ohm's law and resistance
**What is it?** V = I R: the voltage across a resistor is proportional to the current through it; the
power dissipated is P = I^2 R = V^2 / R.

**Why do we need it?** Every conduction loss in the converter is an I^2 R term: MOSFET channel
(Rds(on)), winding copper, shunt, bus bars. Every voltage divider and bleeder resistor is Ohm's law.

**How does it work?**
**Level 1 - Beginner:** A resistor is a narrow pipe: for the same pressure less water flows, and the
friction heats the pipe. Doubling the current makes four times the heat (I^2).
**Level 2 - Engineering:** Resistance depends on temperature. The SiC MOSFET C3M0032120K is entered
with 32 mOhm at 25 C and 52 mOhm at 150 C (`dabtools/dab/devices.py`, datasheet-typical values,
`verified=False`); the loss model interpolates linearly (`rds_on(dev, Tj)`). Copper rises ~0.4 %/K.
**Level 3 - Research:** At 100 kHz the resistance of a winding is not its DC value: skin and proximity
effects raise it (Rac/Rdc = 1.04 primary, 1.08 secondary in the interleaved transformer,
`06_Magnetics/magnetics_design.md`). The 2026 health-monitoring module asks whether a 1 % drift of
Rds(on) is detectable through the on-board sensing chain (`Advanced_Research_2026/SiC_Health_Monitoring/`).

**Example from our converter:** `[Simulated]` HV-bridge conduction loss at nominal: 6.1 W for four
devices (`04_Design_Calculations/design_values.json` -> `nominal.losses`). Check: device rms current = I_rms1 / sqrt(2) =
9.23 / 1.414 = 6.53 A (each device conducts half the period); 4 x 6.53^2 x Rds(49 C) = 4 x 42.6 x
0.0358 = 6.1 W. The 49 C is `nominal.Tj1`.

**Engineering calculations:** LV port current shunt R7 = 1 mOhm (`16_BOM/bom.md`): at 33 A it drops
33 mV and dissipates 33^2 x 0.001 = 1.1 W (rated 2 W). HV divider: 4 x 1 MOhm upper with 499 Ohm lower
(`16_BOM/bom.md` R129-R131): 1000 V full scale -> 1000 x 499 / (4 000 499) = 0.125 V... the BOM comment says
"1000 V FS -> 250 mV" because the AMC1301 input is differential; do the arithmetic yourself with the
schematic sheet `07_KiCad_Schematics/sensing_protection.kicad_sch` before trusting either number.

**Design decision made in this project:** `[Implemented]` Low-side shunt sensing on the LV port
(1 mOhm, Kelvin connected, `16_BOM/bom.md` R7, R139/R140) and a current transformer on the HV side (CT1 1:100,
burden 6.2 Ohm: 32 A -> 2.0 V comparator trip, `16_BOM/bom.md` R141).

**Alternatives considered:** Hall-effect sensors (no dissipation, but offset drift); higher-value
shunts (more signal, more loss).

**How to verify it:** The shunt loss is included in the loss model only as part of "PCB copper and bus
bars (est.) 26.4 W" (`04_Design_Calculations/design_report.md`), which is the most uncertain line of the budget; a bench
measurement is listed in `20_Experimental_Test_Plan/`. `[Not yet tested]`

**Common mistakes:** Using the 25 C Rds(on) for the loss at operating temperature; forgetting that each
device carries the current only half of the time (rms per device = total rms / sqrt(2) for a full bridge).

**Interview explanation (30 s):** Ohm's law gives the conduction losses: each SiC device carries 6.5 A
rms through 36 mOhm at 49 C, about 1.5 W each, 6.1 W for the HV bridge. Temperature raises the
resistance by 60 % between 25 and 150 C, so the thermal design feeds back into the loss.

**Research-level explanation:** The temperature coefficient of Rds(on) in SiC MOSFETs is dominated by
the drift region (positive) with a channel contribution that can be negative at low Vgs; the linear
two-point interpolation of `dabtools/dab/devices.py` is a model assumption to be replaced by datasheet curves.

### The inductor law and volt-second balance
**What is it?** v_L = L di/dt: the voltage across an inductor equals the inductance times the rate of
change of its current. Energy stored: E = 0.5 L I^2. In periodic steady state the average inductor
voltage is zero (volt-second balance), otherwise the current would ramp away.

**Why do we need it?** The series inductor is the heart of the DAB: the phase shift between the two
bridges puts a voltage across L, the current ramps, and that current carries the power. Equation (1) of
`03_Mathematical_Models/dab_mathematical_model.md`, L di/dt = v1(t) - v2'(t), is the whole plant.

**How does it work?**
**Level 1 - Beginner:** An inductor is a heavy flywheel for current: you cannot start or stop the
current instantly. Push with a voltage and the current ramps at a steady rate; push the other way and it
ramps back. Over one full cycle the pushes must cancel, or the flywheel would spin faster every cycle.
**Level 2 - Engineering:** With V1 = 800 V on one side and n V2 = 800 V on the other, during the phase
shift interval the bridges have opposite polarity, so v_L = V1 + V2' = 1600 V and di/dt = 1600 V /
64 uH = 25 A/us; after the second bridge switches, v_L = V1 - V2' = 0 and the current is flat. Figure
`img/ch01_inductor_voltseconds.png` (script `img/fig_ch01_fundamentals.py`) shows both the voltage areas
and the trapezoidal current.
**Level 3 - Research:** A DC volt-second error per period (for example from an asymmetric modulator)
drives a DC current limited only by the loop resistance. The 2026 twin study found exactly this defect
in the switched plant: a one-time-step asymmetry between the positive and negative pulses created a
13 A DC inductor current; the fix (rolling the negative pulse by exactly N_sub/2 cells) is documented in
`Advanced_Research_2026/Digital_Twin/README.md`, section 2, and in `dabtools/dab/sim_switched.py`.

**Example from our converter:** `[Simulated]` L = 64 uH referred to the HV side (`04_Design_Calculations/design_values.json`
-> `L`), made of 59.9 uH external gapped inductor (E55/28/21 pair, 17 turns, 2.10 mm gap) plus 4.1 uH
transformer leakage (`06_Magnetics/magnetics_design.md`). At phi_nom = 28.2 deg the ramp lasts
phi / omega = 0.4916 rad / (2 pi x 100 kHz) = 0.78 us, so the current swings 25 A/us x 0.78 us = 19.6 A,
from -9.8 A to +9.8 A: the model's I_pk1 = 9.75 A (`nominal.Ipk1`).

**Engineering calculations:** di/dt = (V1 + V2') / L = (800 + 800) / 64e-6 = 25.0 A/us during the shift
interval; (V1 - V2') / L = 0 outside it (d = 1). At the 850/300 V corner the second slope is
(850 - 600)/64e-6 = 3.9 A/us and the current becomes triangular with 19.6 A peak
(`04_Design_Calculations/design_report.md`, section 2). Stored energy at 1.2 x I_pk: 4.1 mJ (`04_Design_Calculations/design_values.json` ->
`inductor.E`), which sets the gapped core size.

**Design decision made in this project:** `[Implemented]` The baseline keeps the transformer leakage
small (interleaved winding, 4.1 uH) and sets L with a discrete gapped inductor whose value is defined by
the gap (+/-5 %) rather than by winding geometry (+/-20 %), because a 20 % error in L is a 20 % error in
the power capability (`06_Magnetics/magnetics_design.md`, section 3).

**Alternatives considered:** Integrated-leakage transformer (16.4 uH non-interleaved, ~40 uH with a
spacer) - kept as an optimisation variable in `12_Optimization/`.

**How to verify it:** Simulation: `05_Simulation/run_switched_sim.py` integrates the inductor law step
by step (`DABPlant.run_period` in `dabtools/dab/sim_switched.py`) and reproduces the trapezoid
(`05_Simulation/img/sim_switching_waveforms.png`). Bench: inductance at 0/10/20 A bias and gap
measurement (`06_Magnetics/magnetics_design.md`, section 6, item 7). `[Simulated]`, `[Not yet tested]`

**Common mistakes:** Forgetting that the LV-side quantities must be referred through n before they are
subtracted from V1; assuming the inductor "limits" current like a resistor (it limits di/dt, not i).

**Interview explanation (30 s):** The DAB works by putting a voltage across a 64 uH inductor for a short
time: 1600 V across it ramps the current at 25 A/us, and after 0.78 us the current has reached about
10 A, which the transformer carries to the other side. Volt-second balance keeps the average current
zero.

**Research-level explanation:** The inductor is linear only while the core is well below saturation
(Bpk = 0.116 T at 1.2 x I_pk against 0.41 T Bsat, `06_Magnetics/magnetics_design.md`); gap fringing and DC bias
change L by a few percent, which is why the 2026 twin estimates 1/L online (chapter 05, Level 3).

### The capacitor law and charge balance
**What is it?** i_C = C dv/dt; energy 0.5 C V^2. In periodic steady state the average capacitor
current is zero (charge balance), so the capacitor's job is to absorb the AC part of a pulsating current
and keep its voltage nearly constant.

**Why do we need it?** Both DC links of the DAB are fed by bridges that draw a pulsating current at
twice the switching frequency; the link capacitors convert that into a small voltage ripple.

**How does it work?**
**Level 1 - Beginner:** A capacitor is a water tank: a pulsating inflow and a steady outflow give a
level that wobbles a little. A bigger tank wobbles less.
**Level 2 - Engineering:** The ripple is the peak-to-peak integral of the AC capacitor current divided
by C: Delta V = max(integral of i_C dt) / C (`03_Mathematical_Models/dab_mathematical_model.md`,
section 8). The rms current heats the capacitor through its ESR: P = I_rms^2 ESR.
**Level 3 - Research:** At 100 kHz the equivalent series inductance of film capacitors and the loop
inductance to the bridge dominate the high-frequency behaviour; that is why each leg has a pair of
MLCC decoupling capacitors next to the devices (`16_BOM/bom.md`, C5-C8 100 nF/1 kV, C13-C16
220 nF/630 V) in addition to the bulk film capacitors.

**Example from our converter:** `[Simulated]` LV link C2 = 120 uF (4 x 30 uF / 700 V film, `16_BOM/bom.md`
C9-C12) with ESR 4 mOhm: capacitor rms current 8.38 A, ripple 0.108 V = 0.027 % at nominal and 0.09 %
at the worst corner, ESR loss 0.28 W (`04_Design_Calculations/design_values.json` -> `dclink.nom2`,
`dclink.worst_dV_pct_2`). The closed-loop switched simulation at 50 % load, with the 1 mF external bus
capacitance of APP-04 added to the 120 uF, reports a 6.1 mV peak-to-peak ripple on V2
(`05_Simulation/switched_results.json` -> `switching_50pct.v2_ripple_mV`). Requirement EL-13 asks for
<= 2 %: both numbers are two orders of magnitude inside it.

**Engineering calculations:** HV link C1 = 80 uF (4 x 20 uF / 1100 V film): I_rms = 4.17 A, ripple
0.081 V = 0.010 %, ESR loss 0.07 W (`dclink.nom1`). Voltage derating: 850 V on 1100 V = 77 % (HV),
450 V on 700 V = 64 % (LV) (`16_BOM/bom.md`, `13_Thermal_Analysis/thermal_report.md`, section 3).

**Design decision made in this project:** `[Implemented]` Film capacitors, not electrolytics, on both
links: low ESR at 100 kHz, no wear-out from electrolyte drying, 850 V capability; the bulk capacitance
required by the system (>= 500 uF HV, >= 1 mF LV) is external (APP-04), so the on-board links only
carry the switching ripple.

**Alternatives considered:** Electrolytic bulk capacitors (cheaper per joule, but ESR and lifetime at
100 kHz), larger MLCC banks (DC-bias derating, cracking risk on a 260 mm board).

**How to verify it:** `04_Design_Calculations/dab_design.py` computes the ripple from the waveform;
`05_Simulation/run_switched_sim.py` reproduces it in closed loop; the lab plan measures link ripple
with a differential probe (`20_Experimental_Test_Plan/`). `[Simulated]`, `[Not yet tested]`

**Common mistakes:** Sizing the link for energy (hold-up) when the requirement is ripple current and
rms heating; ignoring the ESL path and placing decoupling far from the switch node.

**Interview explanation (30 s):** The bridge draws its 8-16 A in 100 kHz pulses; the 120 uF film bank
absorbs the pulsating part with 8.4 A rms and keeps the 400 V bus within 0.1 V. The capacitor is sized
by ripple current and ESR heating, not by stored energy, because the bus itself holds the bulk energy.

**Research-level explanation:** The pulsating bridge current i1(t) = i(t) sgn(v1(t)) has a spectrum at
multiples of 2 fs; its distribution between the on-board film bank, the MLCC decoupling and the
external bus depends on the impedance of each path - a parasitic-extraction problem addressed in
`Advanced_Research_2026/Parasitic_Extraction/`.

### rms, average and peak values
**What is it?** For a periodic waveform x(t): peak is the maximum magnitude, average is the mean over a
period, rms (root mean square) is sqrt(mean(x^2)) - the DC value that would produce the same heating in
a resistor.

**Why do we need it?** Conduction loss uses rms, voltage and current ratings use peak, delivered power
uses the average of the product - three different numbers from one waveform.

**How does it work?**
**Level 1 - Beginner:** Peak is the highest wave; average is the water level; rms is the "effective"
height that would do the same work as the waves. For a steady DC current all three are equal.
**Level 2 - Engineering:** Sine: rms = peak / sqrt(2) = 0.707 peak. Square: rms = peak. Triangle: rms =
peak / sqrt(3) = 0.577 peak (`img/ch01_rms_avg_peak.png`). The DAB current is trapezoidal at d = 1
(rms close to the peak: 9.23 A vs 9.75 A) and triangular at d far from 1 (12.2 A rms vs 19.6 A peak at
850/300 V, `04_Design_Calculations/design_report.md`, section 2) - the second case has 60 % more peak for 32 % more rms, and
it is the peak that sets the inductor core and the device pulsed rating.
**Level 3 - Research:** The rms current per operating point is the objective of every modulation
optimisation (Krismer and Kolar 2012, closed-form minimum-conduction-loss modulation, reference [8] of
`01_Literature_Review/literature_review.md`); `dab_model.tps_search()` minimises `I_rms1` numerically.

**Example from our converter:** `[Simulated]` Nominal point: I_rms1 = 9.23 A, I_pk1 = 9.75 A, I_rms2 =
18.46 A, I_pk2 = 19.5 A (`04_Design_Calculations/design_values.json` -> `nominal`). The switched closed-loop model at 50 %
load gives I_pk = 4.96 A, I_rms = 4.42 A (`05_Simulation/switched_results.json` -> `switching_50pct`), close to the
analytical 4.44 A / 4.33 A at the same power from `dabtools/dab/dab_model.py` (the small difference is the 0.3 Ohm
loop resistance and the dead-time compensation of the closed-loop plant).

**Engineering calculations:** Device rms = bridge rms / sqrt(2): 6.53 A (HV), 13.05 A (LV). Ratings:
C3M0032120K Id = 63 A at 25 C, C3M0016120K 115 A (`dabtools/dab/devices.py`), used at a 9.75 / 19.5 A peak -
comfortable, which is why the cheaper 32 mOhm part is enough on the HV side.

**Design decision made in this project:** `[Implemented]` The protection chain uses peaks (24 A design
limit, 32 A hardware trip on the HV side, `04_Design_Calculations/design_report.md`, section 8), while the loss and thermal
chain uses rms; the firmware limiter works on the peak estimate per period (`dabtools/dab/control.py`).

**Alternatives considered:** Average-current limiting only (simpler, but it does not protect the
inductor core from saturation on a transient).

**How to verify it:** `DABPoint.I_rms1` / `I_peak1` in `dabtools/dab/dab_model.py` (numerical from the 4000-point
grid), cross-checked against the trapezoid integral in `03_Mathematical_Models`. `[Simulated]`

**Common mistakes:** Quoting an rms current without saying over which period; using the sine factor
0.707 for a non-sinusoidal waveform; using rms for a magnetic-saturation check (must be peak).

**Interview explanation (30 s):** Peak sizes the magnetics and the trip levels, rms sizes the copper
and the silicon, average times voltage is the power. Our inductor current is 9.75 A peak and 9.23 A rms
at nominal but 19.6 A peak and 12.2 A rms at the worst corner - the corner, not the nominal point,
sizes the hardware.

**Research-level explanation:** For a piecewise-linear current the rms has a closed form in (V1, V2',
phi, D1, D2); its gradient with respect to the modulation variables is what efficiency-optimal
modulation schemes set to zero subject to the ZVS constraints.

### AC, DC and the transformer turns ratio
**What is it?** DC is a constant voltage or current; AC changes sign periodically. A transformer couples
two windings through a shared magnetic flux: v1/v2 = N1/N2 = n, i2/i1 = n (ideal), and it transfers AC
only - the flux must alternate, so the average winding voltage must be zero.

**Why do we need it?** The ports are DC (800 V and 400 V), but galvanic isolation needs a transformer,
so each bridge first turns DC into a 100 kHz square wave, the transformer couples it, and the other
bridge turns it back. The turns ratio sets the voltage match d = n V2 / V1.

**How does it work?**
**Level 1 - Beginner:** A transformer is two coils on one iron (here ferrite) ring; a changing current
in one makes a changing magnetic field that pushes current in the other. It only works for changing
currents - a steady current makes a steady field, which pushes nothing. More turns on one side means
more volts on that side, in proportion.
**Level 2 - Engineering:** The flux density swing is set by the applied volt-seconds: Delta B = V T_half
/ (N1 Ae). With 800 V for 5 us on 28 turns and Ae = 540 mm^2: Delta B = 800 x 5e-6 / (28 x 5.4e-4) =
0.265 T, Bpk = 0.132 T (`04_Design_Calculations/design_values.json` -> `transformer.Bpk` = 0.1323 T; Bsat 0.41 T at 100 C).
Referring LV quantities to the HV side: V2' = n V2, I2 = n I1', L2' = L / n^2.
**Level 3 - Research:** The leakage inductance (flux that links only one winding) is the part of the
series inductance that the transformer contributes (4.1 uH interleaved, 16.4 uH non-interleaved); the
interwinding capacitance (631 pF) carries common-mode displacement current at every edge (20 V/ns ->
~12 A pulses, `06_Magnetics/magnetics_design.md`, section 5) - the EMI chapter starts here.

**Example from our converter:** `[Implemented]` n = N1/N2 = 28/14 = 2 on an E65/32/27 pair in 3C95
(`06_Magnetics/magnetics_design.md`, section 2). With n = 2, the nominal 800/400 V pair gives d = 1.00
(flat-topped current, minimum rms); the extreme corners give d = 0.71 (850/300 V) and d = 1.38
(650/450 V) (`02_Topology_Comparison/topology_comparison.md`, section 2).

**Engineering calculations:** Magnetising inductance ~10.9 mH ungapped, so the magnetising current
at 800 V for 5 us is 800 x 5e-6 / 10.9e-3 = 0.37 A peak - negligible against 9.75 A, which is why the
power model neglects it (`03_Mathematical_Models/dab_mathematical_model.md`, section 1). Core loss 11.4 W
(Steinmetz with an iGSE factor 1.22), copper loss 7.4 W, 36 K rise at 3 m/s.

**Design decision made in this project:** `[Implemented]` n = 2 chosen so that the nominal point sits
at d = 1 and the full 650-850 / 300-450 V window maps to 0.71 <= d <= 1.38
(`02_Topology_Comparison/topology_comparison.md`).

**Alternatives considered:** n = 1.51 would be the PSFB choice at the same specification (set by the
450 V output at 650 V input with 15 % duty loss) - see `02_Topology_Comparison/topology_comparison.md`, section 3; non-integer
ratios (e.g. 27:14) shift the d = 1 point but cost a non-symmetric winding.

**How to verify it:** Turns ratio and polarity test at 1 kHz (N1/N2 = 2.00 +/- 1 %), Lm and leakage
measurement, hipot 2.5 kVrms (`06_Magnetics/magnetics_design.md`, section 6). `[Not yet tested]`

**Common mistakes:** Treating the transformer as a DC converter; forgetting to refer L, C and V to the
same side before combining them; applying DC volt-seconds (flux walking) through an asymmetric
modulator.

**Interview explanation (30 s):** The transformer turns the 800 V and 400 V DC ports into two 100 kHz
square waves that see each other through n = 2; the voltage ratio d = n V2/V1 is 1 at the nominal point
and 0.71-1.38 over the window, and that ratio decides how much reactive current flows.

**Research-level explanation:** Flux-density swing, leakage, capacitance and loss are coupled through
the winding geometry; the 2026 FEM module (`Advanced_Research_2026/FEM_Magnetics/`) replaces the
analytical Dowell/leakage estimates by a 2-D field solution of the window.

### Basic circuit analysis: Kirchhoff's laws and energy bookkeeping
**What is it?** KCL: currents into a node sum to zero. KVL: voltages around a loop sum to zero. Energy
conservation: input power = output power + losses.

**Why do we need it?** The DAB has exactly one loop that matters (bridge 1 - inductor - transformer -
bridge 2) and two nodes that matter (the two DC links). KVL on the loop is the inductor equation; KCL
at the links is the capacitor equation; energy conservation is the efficiency.

**How does it work?**
**Level 1 - Beginner:** What flows in must flow out (KCL); going round a circuit and back to the start
you are at the same voltage (KVL). These two rules plus the component laws solve any circuit.
**Level 2 - Engineering:** KVL on the AC loop: v1(t) - L di/dt - R_s i - v2'(t) = 0, with R_s = 0.3 Ohm
the HV-referred loop resistance (two Rds of each bridge referred plus windings,
`dabtools/dab/sim_switched.py`). KCL at the LV link: C2 dv2/dt = n i(t) s2(t) - i_load. The switched
plant integrates exactly these two equations with a fixed step (200 sub-steps per period).
**Level 3 - Research:** Writing the plant as these two equations is the "L1 electrical layer" of the
digital twin; the lossy version solves the periodic steady state exactly as a geometric series
(`discrete_model_lossy` in `Advanced_Research_2026/Digital_Twin/twin.py`).

**Example from our converter:** `[Simulated]` Loss budget at 800/400 V, 6.6 kW: 92.2 W total, of which
semiconductors 25.5 W, magnetics 25.9 W, capacitors 0.4 W, auxiliary 12 W, PCB copper 26.4 W (estimate)
(`04_Design_Calculations/design_report.md`, section 4). Efficiency 6600 / (6600 + 92.2) = 98.62 %.

**Engineering calculations:** Efficiency eta = P_out / (P_out + P_loss). Peak calculated 98.66 % at
80 % load (`04_Design_Calculations/design_values.json` -> `eff_curves["800/400"]`); 89.2 % at 10 % load because the 12 W
auxiliary and the 26.4 W fixed estimate do not scale with power.

**Design decision made in this project:** `[Implemented]` The design targets (EL-06 >= 97.5 % peak,
EL-07 >= 96.5 % full load) are met on paper with margin; the margin is deliberately kept because the
device data are unverified and the copper estimate is coarse.

**Alternatives considered:** Not applicable - these are laws, not choices.

**How to verify it:** The loss budget is produced by `04_Design_Calculations/dab_design.py`; the thermal consequence by
`13_Thermal_Analysis/thermal_analysis.py`; a calorimetric or input-output power measurement is the
only real verification (`20_Experimental_Test_Plan/`). `[Simulated]`, `[Not yet tested]`

**Common mistakes:** Summing voltages with inconsistent sign conventions; forgetting the auxiliary
power when quoting efficiency; quoting "98.6 %" without the words "calculated, not measured".

**Interview explanation (30 s):** Two equations describe the converter: KVL round the AC loop gives the
inductor current, KCL at each DC link gives the bus voltages. Energy conservation closes the budget:
92 W of calculated loss on 6.6 kW is 98.6 % - on paper.

**Research-level explanation:** The two-equation plant is low-order enough for exact periodic
solutions, which makes it an ideal test bed for estimation and control research; its weakness is that
it hides the parasitics (device capacitance, loop inductance) that the hardware will not hide.

## Worked example(s) with real numbers

**Example 1 - the inductor ramp (inductor law).** `[Simulated]` From `04_Design_Calculations/design_values.json`: L = 64 uH,
fs = 100 kHz, phi_nom = 0.4916 rad (28.2 deg). The shift interval lasts t = phi / (2 pi fs) = 0.4916 /
628 318 = 0.782 us. The voltage across L in that interval is V1 + n V2 = 800 + 800 = 1600 V. The current
swing is 1600 V x 0.782 us / 64 uH = 19.6 A, symmetric about zero: +/-9.8 A. The file says I_pk1 = 9.75 A
(the 0.05 A difference is the 4000-point grid). Energy at the peak: 0.5 x 64e-6 x 9.75^2 = 3.0 mJ. At 100 kHz
that energy is exchanged twice per period, so the inductor handles 2 x 3.0 mJ x 100 kHz = 608 VA of
reactive throughput - a quarter of the number for the transformer, which is why the inductor core (E55) is
smaller than the transformer core (E65).

**Example 2 - the LV link ripple (capacitor law).** `[Simulated]` The LV bridge delivers a pulsating
current; its AC part has 8.38 A rms (`dclink.nom2.I_rms`). The charge moved into the capacitor in one
half period is roughly I_rms x T/4 = 8.38 x 2.5 us = 21 uC; divided by 120 uF that is 0.17 V, the same
order as the exact 0.108 V from the waveform integral in `04_Design_Calculations/dab_design.py`. ESR loss 8.38^2 x 0.004 =
0.28 W (`dclink.nom2.P_esr`). In the closed-loop switched model the external 1 mF bus (APP-04) is added:
C = 1.12 mF, and at 50 % load the simulated ripple is 6.1 mV (`05_Simulation/switched_results.json`).

**Example 3 - checking a BOM value with Ohm's law.** `[Implemented]` The HV bleeder chain is 4 x
680 kOhm, 2 W, 2512 (`16_BOM/bom.md`, R1-R4): 850 V / 4 = 212 V per resistor, below the 500 V rating;
current 850 / 2.72 MOhm = 0.31 mA; power 0.27 W total, 0.07 W per resistor. `04_Design_Calculations/design_values.json` ->
`dclink.R_bleed1` gives 1.41 MOhm as the value that discharges 80 uF to < 60 V in 5 min (SAF-04). With
2.72 MOhm the time constant is 2.72e6 x 80e-6 = 218 s and 850 -> 60 V takes ln(850/60) x 218 s = 578 s,
about 9.6 min. This is a real discrepancy between the calculated requirement and the BOM chain that a
reviewer should raise (the external active discharge of SAF-04, < 10 s, is a separate path). Nothing in
this note resolves it; it is listed so that the reader practises checking numbers rather than copying them.

## How this chapter connects to the files

| File | What it contains | Status |
|---|---|---|
| `SiC_6k6_Industrial_DAB/04_Design_Calculations/design_values.json` | L, phi_nom, currents, DC-link ripple, loss budget, transformer and inductor data | `[Simulated]` |
| `SiC_6k6_Industrial_DAB/04_Design_Calculations/design_report.md` | the same numbers as tables with the corner analysis | `[Simulated]` |
| `SiC_6k6_Industrial_DAB/05_Simulation/switched_results.json` | closed-loop switched results: 50 % load peak/rms current, V2 ripple 6.1 mV | `[Simulated]` |
| `SiC_6k6_Industrial_DAB/05_Simulation/run_switched_sim.py` | the simulation script (bus capacitances C1 + 500 uF, C2 + 1 mF) | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/dabtools/dab/dab_model.py` | waveforms(), DABPoint: numerical v, i, P, rms, peak | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/dabtools/dab/sim_switched.py` | DABPlant: KVL/KCL integration with R_s = 0.3 Ohm | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/dabtools/dab/devices.py` | Rds(on) at 25/150 C, datasheet-typical, verified=False | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/06_Magnetics/magnetics_design.md` | transformer 28:14, Bpk, leakage, inductor 59.9 uH | `[Simulated]` |
| `SiC_6k6_Industrial_DAB/16_BOM/bom.md` | capacitors, bleeders, shunt, CT burden | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/00_Requirements/01_requirements_specification.md` | EL-01..EL-16, APP-04 bus capacitances, SAF-04 discharge | `[Implemented]` |
| `21_Human_Friendly_Learning_Notes/img/fig_ch01_fundamentals.py` | generates the two figures of this chapter from dab_model.py | `[Implemented]` |

## Viva / interview questions

### Basic (10)
1. What is the difference between power and energy?
   Power is the rate of energy transfer (W = J/s); energy is power accumulated over time (J). The DAB
   transfers 6600 J every second; its 80 uF HV link stores 25.6 J at 800 V.
2. State Ohm's law and give one use of it in this converter.
   V = I R. The 1 mOhm LV shunt drops 33 mV at 33 A (`16_BOM/bom.md` R7), which the AMC1301 isolated amplifier
   measures.
3. Why does an inductor resist a change of current?
   Because v = L di/dt: a finite voltage can only change the current at a finite rate. With 1600 V across
   64 uH the rate is 25 A/us.
4. Why does a capacitor resist a change of voltage?
   Because i = C dv/dt: a finite current can only change the voltage at a finite rate; the 120 uF LV link
   moves only 0.1 V under 8.4 A rms of ripple current.
5. What is volt-second balance?
   In steady state the average voltage across an inductor is zero over a period; otherwise the current
   would ramp up every cycle. The positive and negative areas in `img/ch01_inductor_voltseconds.png` are
   equal.
6. What are peak, average and rms, and which one heats a resistor?
   Peak is the maximum, average the mean, rms the square root of the mean square; rms heats the
   resistor (P = I_rms^2 R). Nominal inductor current: 9.75 A peak, 9.23 A rms, 0 A average.
7. Why does the DAB need a transformer if both ports are DC?
   For galvanic isolation (the HV bus and the LV port must not share a conductor) and to match 800 V
   to 400 V with n = 2. The bridges make the AC that the transformer needs.
8. What is the average HV port current at 6.6 kW and 800 V?
   8.25 A. The rms inductor current (9.23 A) is larger because the waveform is trapezoidal, not DC.
9. What is the turns ratio of our transformer and why?
   N1:N2 = 28:14, n = 2, so that 800 V / 400 V gives d = n V2 / V1 = 1 at the nominal point.
10. How much energy does the series inductor store at its nominal peak current?
    0.5 x 64 uH x 9.75^2 = 3.0 mJ; at 1.2 x I_pk the design file reports 4.1 mJ, which sizes the gapped
    E55 core.

### Intermediate (10)
1. Derive the inductor current slope during the phase-shift interval at 800/400 V.
   v_L = V1 + n V2 = 1600 V (bridges in anti-phase), di/dt = 1600 / 64e-6 = 25 A/us; after the LV bridge
   switches v_L = V1 - n V2 = 0 and the current is flat (d = 1).
2. Why is the current triangular at 850/300 V and trapezoidal at 800/400 V?
   At 850/300 V, V1 - n V2 = 250 V, so the second slope is 3.9 A/us instead of zero; the current keeps
   rising to 19.6 A peak and falls back, a triangle with 12.2 A rms (`04_Design_Calculations/design_report.md`).
3. Compute the HV-bridge conduction loss from the file values.
   Device rms 9.23 / sqrt(2) = 6.53 A; Rds(49 C) = 0.032 + 0.020 x 24/125 = 35.8 mOhm; 4 x 6.53^2 x
   0.0358 = 6.1 W, matching `nominal.losses`.
4. Why is the capacitor sized for ripple current rather than energy?
   The external bus (>= 500 uF / >= 1 mF per APP-04) holds the energy; the on-board film bank must
   survive 8.4 A rms at 100 kHz with low ESR (0.28 W) and keep the ripple (0.03 %) far below EL-13's 2 %.
5. Explain how the switched simulation applies KVL and KCL.
   `DABPlant.run_period` updates iL += (va - vb - R_s iL)/L dt (KVL on the AC loop) and v1, v2 with
   (i_source - i_bridge)/C dt (KCL at each link), 200 sub-steps per 10 us period.
6. What flux density does 800 V for a half period produce in the 28-turn primary?
   Delta B = V t / (N Ae) = 800 x 5e-6 / (28 x 5.4e-4) = 0.265 T, Bpk = 0.132 T, a third of Bsat.
7. Why does the model neglect the magnetising current?
   Lm ~ 10.9 mH gives 0.37 A peak against 9.75 A load current; it is kept only in the core-loss model.
8. The switched simulation gives 4.96 A peak at 50 % load; the analytical model 4.44 A. Why?
   The plant includes R_s = 0.3 Ohm, a dead-time compensation term and a time-quantised modulator, and
   the controller regulates to 400 V rather than fixing phi; the 12 % difference is the expected
   model-to-plant gap, not an error of either.
9. What is the relation between the leakage inductance and the series inductor?
   They add: L = L_lk + L_ext = 4.1 + 59.9 = 64 uH referred to the HV side; the gapped inductor is used
   because its tolerance (+/-5 %) is much better than that of leakage (+/-20 %).
10. Check the bleeder resistor against SAF-04.
    Time constant 2.72 MOhm x 80 uF = 218 s; 850 -> 60 V needs ln(14.2) = 2.65 time constants = 578 s,
    above the 5 min of SAF-04, whereas `R_bleed1` = 1.41 MOhm in `04_Design_Calculations/design_values.json` meets it. A real
    inconsistency to raise in review.

### Advanced / research (10)
1. Why is the period-average of v i the right definition of power, and when does it fail?
   It is the energy per period divided by the period; it fails only when the waveform is not periodic
   (transients), where energy bookkeeping per period must include the change of stored energy.
2. How does a DC volt-second asymmetry appear in a simulation, and how was it found here?
   It produces a DC inductor current limited by R_s; the 2026 twin study saw 13 A DC when the inner
   phase shift was below 1, traced it to a one-cell asymmetry in the plant's pulse generation, and fixed
   it (`Advanced_Research_2026/Digital_Twin/README.md`, section 2).
3. Why does "every current scales with 1/L" make L easy to estimate?
   The lossless plant is linear in 1/L for a fixed switching pattern, so the measured period-average
   current is a linear regression on 1/L with a known regressor - RLS converges in one sample
   (`Advanced_Research_2026/Digital_Twin/results/twin_study.json`, E1).
4. What limits the validity of the constant-L assumption?
   Core saturation (Bpk 0.116 T at 1.2 I_pk against 0.41 T), gap fringing, DC bias and temperature; a
   +/-5 % gap tolerance is assumed, which the online estimator is meant to absorb.
5. How would you measure Rac/Rdc = 1.04 of the primary and what does it tell you?
   Impedance analyser at 100 kHz vs DC on the assembled winding; the ratio quantifies skin and proximity
   loss (Dowell), and 1.04 means the 294 x 0.1 mm litz is well below the 0.24 mm skin depth.
6. The interwinding capacitance is 631 pF; what does 20 V/ns do to it?
   i = C dv/dt = 631e-12 x 20e9 = 12.6 A displacement-current pulses that return through the Y
   capacitors and chassis - the source of the common-mode EMI estimated in `14_EMI_EMC/`.
7. How is the rms current a research objective?
   The minimum-rms modulation (Krismer and Kolar 2012) chooses (D1, D2, phi) for a given power subject to
   ZVS; `tps_search()` does this numerically, and the twin's supervisor does it on the estimated L.
8. Why is the energy-per-period view central to reactive-power definitions in DC-DC converters?
   Because there is no sinusoid to define a phase angle; "reactive" power is defined as the energy that
   flows backwards within a period (Q_back in `DABPoint.Q_backflow`), 301.6 W at nominal.
9. What is the uncertainty on the 98.62 % calculated efficiency?
   The two largest and least verified lines are PCB copper (26.4 W, estimate) and device data
   (`verified=False`); `Advanced_Research_2026/Uncertainty_Quantification/` propagates these to an
   efficiency distribution.
10. How would you validate the capacitor-law ripple calculation on hardware without energising at
    850 V?
    Reduced-voltage back-to-back test with the same current (the ripple is current-driven), differential
    probe on the film bank, compare the waveform integral with `04_Design_Calculations/dab_design.py` at the same operating
    point (`20_Experimental_Test_Plan/`, staged plan).

## Pitches

**30 s:** A DC-DC converter moves energy with five laws: P = V I, V = I R, v = L di/dt, i = C dv/dt and
the transformer ratio. In our 6.6 kW DAB the series inductor of 64 uH sees 1600 V for 0.78 us and ramps
to 9.75 A, the transformer couples it at n = 2, and the 120 uF film link smooths the 100 kHz pulses to
0.1 V of ripple - all calculated, none yet measured.

**2 min:** Start from power and energy: 6.6 kW is 8.25 A at 800 V or 16.5 A at 400 V, while the links
store tens of joules and the inductor only millijoules - the links are the slow, stiff elements and the
inductor the fast one. Ohm's law turns rms currents into heat: 6.5 A rms per SiC device through 36 mOhm
at 49 C is 6.1 W for the HV bridge. The inductor law explains the DAB in one line: a phase shift puts
V1 + n V2 = 1600 V across 64 uH, the current ramps at 25 A/us for 0.78 us, and volt-second balance makes
the waveform a symmetric trapezoid with 9.23 A rms. The capacitor law sizes the links by ripple current,
8.4 A rms into 120 uF with 4 mOhm ESR, giving 0.1 V ripple and 0.3 W. The transformer couples two square
waves, 28:14 turns at 0.13 T peak flux, and its 4.1 uH leakage is part of the 64 uH. Everything is
traceable to `04_Design_Calculations/design_values.json` and `05_Simulation/switched_results.json`; the lab plan says how each number would
be measured.

**10 min outline:**
* Units and the four base quantities; average port currents 8.25 A / 16.5 A.
* Ohm's law and temperature: Rds(on) 32 -> 52 mOhm, device rms = bridge rms / sqrt(2), 6.1 W.
* Inductor law: 25 A/us, 0.78 us, +/-9.75 A, volt-second balance, 3.0 mJ; figure
  `img/ch01_inductor_voltseconds.png`.
* Capacitor law: 120 uF / 4 mOhm, 8.4 A rms, 0.108 V, 6.1 mV in closed loop with the 1 mF bus.
* rms/average/peak for sine, square, triangle, trapezoid; corner point 19.6 A peak vs 12.2 A rms.
* Transformer: 28:14, 0.132 T, Lm 10.9 mH, leakage 4.1 uH, interwinding 631 pF.
* KVL/KCL as the plant equations; loss budget 92.2 W, 98.62 % calculated.
* Worked example 3: the bleeder discrepancy - how to check a number.
* Status: all `[Simulated]` / `[Implemented]`; nothing measured.

## Further reading

* `SiC_6k6_Industrial_DAB/03_Mathematical_Models/dab_mathematical_model.md` - equation (1) and the
  period-average definitions used above.
* `SiC_6k6_Industrial_DAB/01_Literature_Review/literature_review.md` [2] Kheraluwala et al. 1992
  (the SPS power equation), [6] Krismer and Kolar 2010 (loss model structure).
* `Advanced_Research_2026/Literature_Database/literature_2022_2026.csv` L28, L29 (parameter
  estimation of converters, preprints, accessible) for the research view of "which L is really there".
