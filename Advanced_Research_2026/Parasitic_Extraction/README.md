# Parasitic_Extraction - partial-inductance extraction from the generated DAB board

Maturity: **L1** (analytical, closed-form partial inductances from the board geometry; no field solver, no
measurement). Script: `extract_parasitics.py` (runs in ~1 s, regenerates `results/` and `provenance.json`;
`--board <file>` selects the `.kicad_pcb`, default `07_KiCad_Schematics/SiC_DAB_6k6.kicad_pcb`). The board file is
parsed with a small s-expression reader (numpy/scipy/matplotlib only) and cross-checked against KiCad's `pcbnew`
module when it is importable (731 pads compared, 0.0 mm deviation for the snapshot used here).

Board state used: snapshot of the generated 6-layer board with placement, planes and switch-node strips but
**no routed tracks yet** (0 segments, 0 vias in the file; routing run in progress elsewhere). Gate-loop trace
lengths are therefore Manhattan distances between the connected pads; the script switches to the routed segment
lengths automatically when the board contains tracks on the gate nets.

## 1. Inputs

* Stack-up from `17_Manufacturing/stackup.md`: F.Cu 70 um / 0.20 prepreg / In1 (reference planes HV_N, GND, LV_N) /
  0.50 core / In2 (power planes HV_P, GND, LV_P) / 0.50 / In3 (= In1) / 0.50 / In4 (= In2) / 0.20 / B.Cu, 2.32 mm.
  Copper mid-depths: F.Cu 0.04, In1 0.31, In2 0.88, In3 1.45, In4 2.02, B.Cu 2.29 mm. HV_P/HV_N pair spacing
  (In1-In2 and In3-In4): 0.57 mm centre-to-centre.
* Geometry read from the board: TO-247-4 pads of Q1-Q8 (pitch 2.54 mm, drain = pad 2, source = pad 4, 5.08 mm apart),
  HF decoupling capacitors C5-C8 (HV, 2220 100 nF/1 kV) and C13-C16 (LV), switch-node strips SW_A-SW_D on B.Cu
  (3 mm wide bars between the top-source and bottom-drain pins, 16.9 mm), plane extents, driver U1/U3 pads,
  gate resistors R102/R116 (3.3 Ohm on), VEE-KS decoupling capacitors (C105/C106, C127/C128).
* Devices from `dabtools/dab/devices.py` (Coss,er 170 pF / 350 pF, flagged verified=False in the source);
  Ciss 1.9 / 3.4 nF and Rg,int 2.6 / 1.5 Ohm recalled datasheet-typical values (**not verified**).
* Package assumptions (`ASSUME` in the script): TO-247 effective lead + lead-frame length 15 mm (sensitivity
  10-20 mm), lead cross-section 1.5 x 0.6 mm, MLCC 2220 ESL 1.2 nH typical, via 0.8/0.4 mm, gate trace 0.5 mm
  (HV_GATE net-class width of the generator), gate go/return pair spacing 1.0 mm (sensitivity 0.5-5 mm).

## 2. Formulae (SI)

| element | partial inductance |
|---|---|
| rectangular bar, Hoer-Love 1965 / Ruehli 1972 (l >> w + t) | `L_p = mu0 l/(2 pi) [ ln(2 l/(w+t)) + 1/2 + 0.2235 (w+t)/l ]` |
| two parallel filaments, length l, distance d (Grover) | `M = mu0 l/(2 pi) [ ln(l/d + sqrt(1+(l/d)^2)) - sqrt(1+(d/l)^2) + d/l ]` |
| go/return pair of bars | `L_loop = 2 (L_p - M)` |
| strip over a reference plane at height h (image current) | `L = mu0 h l/(w + 2 h)` |
| parallel-plane pair, spacing h, length l, effective width w | `L = mu0 h l / w` |
| round conductor (pin / via), radius r | `L = mu0 l/(2 pi) [ ln(2 l/r) - 3/4 ]` (clamped at 0 for l < ~r) |
| loop total | sum of partial self-inductances of the series segments - 2 x mutual of the anti-parallel drain/source lead pairs; other mutuals neglected |

The plane-pair section runs from the device pin row (y = 14 mm) to the capacitor pads (y = 38 mm), l = 24 mm,
with 45-degree current spreading, `w_eff = span of pins/pads (27 mm) + l = 51 mm` (capped at the plane width), and the
two plane pairs (In1/In2, In3/In4) in parallel.

## 3. Results

### (a) Commutation loops (`results/loop_segments.csv`, `parasitics.json`)

All four legs have the same geometry (the generator mirrors the HV layout to the LV side), so the budgets are identical:

| segment (HV leg A: Q1/Q2, C5+C6) | l / w / t (mm) | L_partial (nH) | mutual (nH) |
|---|---|---|---|
| Q1 drain lead, Q1 source lead, Q2 drain lead, Q2 source lead (bar, 15 mm effective) | 15 / 1.5 / 0.6 | 4 x 9.57 | 4 x (-3.26) (anti-parallel pairs 5.08 mm apart) |
| SW_A strip on B.Cu, top-source pin to bottom-drain pin | 16.9 / 3.0 / 0.07 | 1.62 (image plane In4 at 0.27 mm); 10.0 free-standing (upper bound) | - |
| pins inside the board to the first plane (drain -> In2, source -> In1) | 0.88 / 0.31 | 0.02 + 0.00 | - |
| HV_P/HV_N plane pair (two pairs in parallel) | 24 / w_eff 51 / h 0.57 | 0.17 | - |
| C5 + C6 branch (ESL 1.2 nH + 2 vias each, 2 in parallel) | - | 0.85 | - |
| **loop total** | | **27.9 nH** (upper bound 36.2 nH with a free-standing strip) | packages alone 25.3 nH (91 %) |

Sensitivities (`results/sensitivity.csv`):

| parameter | values | plane-pair section (nH) | loop (nH) |
|---|---|---|---|
| plane spacing h, single pair | 0.2 / 0.5 / 1.0 / 1.6 / 2.3 mm | 0.12 / 0.30 / 0.59 / 0.94 / 1.36 | 27.9 / 28.0 / 28.3 / 28.7 / 29.1 |
| effective plane width | 51 mm (spreading) / 27 mm (pad span only) | 0.17 / 0.32 | 27.9 / 28.0 |
| TO-247 effective lead length | 10 / 15 / 20 mm | - | 18.5 / 27.9 / 37.4 |

The plane pair contributes < 1.5 nH even with a 2.3 mm (outer-layer only) spacing: on this board the loop is set by
the TO-247 packages (91 %), then by the B.Cu switch-node strip. The 0.5 mm plane spacing of the stack-up is
therefore not a limiting choice; the lever is the package (TO-247-4 is the design's choice for the Kelvin source and
the heatsink bar) and keeping the strip short.

### (b) Gate loops (`results/gate_loop_sensitivity.csv`)

| item | Q1 (HV, driver U1) | Q5 (LV, driver U3) |
|---|---|---|
| driver output -> gate resistor (GD net), Manhattan | 102.0 mm | 23.2 mm |
| VEE-KS capacitor -> driver VEE pin, Manhattan | 93.0 mm | 41.8 mm |
| go/return trace pair, 0.5 mm wide, 1.0 mm spacing | 80 nH | 26 nH |
| TO-247-4 gate + Kelvin-source leads (anti-parallel, 5.08 mm) | 12.6 nH | 12.6 nH |
| local segments (Rg -> gate pin, KS pin -> VEE-KS caps, 11.3 + 15.7 mm) | 16.0 nH | 16.0 nH |
| VEE-KS capacitor ESL (2 in parallel) | 0.6 nH | 0.6 nH |
| **gate-loop inductance** | **109 nH** | **56 nH** |
| R_total (Rg,on 3.3 + Rg,int + driver 1 Ohm), Ciss | 6.9 Ohm, 1.9 nF | 5.8 Ohm, 3.4 nF |
| damping ratio zeta = R/(2 sqrt(L/C)), ringing frequency | 0.45, 11.0 MHz | 0.72, 11.6 MHz |
| pair spacing 0.5 / 1 / 2 / 3 / 5 mm (Q1) | 82 / 109 / 136 / 151 / 170 nH | - |

Finding: the drivers sit in the isolation barrier (x = 118-134 mm) and the HV gate resistors next to the devices at
x = 20-28 mm, so the Q1-Q4 gate loops are ~100 mm long one way; the VDD/VEE decoupling capacitors are placed at the
device, not at the driver, which puts the full trace pair inside the high-frequency gate loop. Even with a
tightly coupled pair the loop stays ~80-110 nH, 3-5 x the 10-30 nH typically reported for TO-247-4 layouts with the
driver within 20 mm, and the turn-on damping ratio is ~0.45 (under-damped, 11 MHz ringing; with Rg,off 1.5 Ohm the
turn-off loop is less damped still). The LV side (U3 at x = 213 mm, Q5 at x = 246 mm) is 2 x better. Recommendations
for the next board revision (not implemented here, outside this module's scope): place the driver secondary side
within 20 mm of the TO-247 (the barrier only has to be crossed by the driver's isolation), add the VDD/VEE
decoupling at the driver pins, route GD and VEE as a tight pair, or increase Rg,on / add a ferrite bead.

### (c) Drain-voltage overshoot (`results/overshoot.csv`, `fig_overshoot.png`)

Estimate `V_os = min(L_loop di/dt, I sqrt(L_loop/Coss,er))` with `di/dt = I_pk / t_f` (hard turn-off current fall
time t_f = 5 / 10 / 20 / 40 ns; the second term is the resonant bound `1/2 L I^2 = 1/2 Coss V^2`). In normal DAB
operation all eight edges are ZVS, i.e. the loop current does not step at turn-off (it commutates into Coss over the
dead time), so the entries below are the **hard-switched worst case** (ZVS loss, protection trip, start-up):

| leg, L = 28 nH | Vdc (V) | I (A) | t_f = 10 ns: V_os / Vds,pk / margin to 1200 V | t_f = 5 ns: V_os / Vds,pk / margin |
|---|---|---|---|---|
| HV (C3M0032120K, Coss,er 170 pF, ringing 73 MHz) | 850 | 9.8 (nominal peak) | 27 V / 877 V / 323 V | 54 V / 904 V / 296 V |
| HV | 850 | 19.6 (worst corner peak) | 55 V / 905 V / 295 V | 109 V / 959 V / 241 V |
| HV | 850 | 32 (hardware trip) | 89 V / 939 V / 261 V | 179 V / 1029 V / 171 V |
| LV (C3M0016120K, Coss,er 350 pF, ringing 51 MHz) | 450 | 19.5 | 54 V / 504 V / 696 V | 109 V / 559 V / 641 V |
| LV | 450 | 64 (trip, LV side) | 179 V / 629 V / 571 V | 357 V / 807 V / 393 V |

The resonant bound (I sqrt(L/C) = 125 / 251 / 410 V at 9.8 / 19.6 / 32 A on the HV side) is only reached for
t_f below ~2 ns, so the overshoot stays below 180 V and the 1200 V rating keeps >= 170 V margin at the 32 A trip with
an aggressive 5 ns fall - provided the loop really is ~28 nH; with the free-standing-strip upper bound (36 nH) and
20 mm effective leads (37 nH) the trip-case overshoot at 5 ns grows to ~240 V (margin ~110 V). A soft (two-level or
high-Rg) turn-off for the protection trip, as proposed in `Active_Gate_Drive/`, removes this case.

### (d) Comparison with typical published values (`results/literature_comparison.csv`)

| item | typical range reported in literature (not measured here) | this work |
|---|---|---|
| TO-247 package drain-source partial inductance, one device | 7 - 15 nH | 12.6 nH (15 mm effective leads) |
| discrete TO-247 half-bridge commutation loop on a PCB with MLCC decoupling | 20 - 60 nH | 28 - 36 nH |
| TO-247-4 (Kelvin source) gate loop, driver within ~20 mm | 10 - 30 nH | 109 nH (HV), 56 nH (LV) |
| SMD TO-263-7 / D2PAK-7 half-bridge loop | 5 - 15 nH | n/a |
| power module with integrated DC link | 2 - 10 nH | n/a |

The ranges are the author's recollection of application notes and papers on TO-247 SiC layout; they are stated as
typical ranges, were not re-checked against sources in this environment and nothing here was measured.

## 4. Figures

* `results/fig_loop_geometry_HV.png` - top view of Q1/Q2, C5/C6, the SW_A strip and the plane-pair section
* `results/fig_overshoot.png` - hard turn-off overshoot vs loop inductance for nominal, corner and trip currents

## 5. Limitations and what was NOT verified

* Closed-form partial inductances only (no PEEC, no 3-D field solver): mutual terms other than the drain/source
  (gate/Kelvin) lead pairs are neglected; current spreading in the planes is a 45-degree assumption; skin/proximity
  redistribution at 10-100 MHz is not modelled beyond the image-plane bound for the strip.
* TO-247 lead/lead-frame geometry (15 mm effective, 1.5 x 0.6 mm) and the MLCC ESL are assumptions; vendor package
  models were not available. Sensitivity to the lead length is +/-10 nH.
* The board has no routed tracks yet: gate-loop lengths are Manhattan pad-to-pad estimates with an assumed 1.0 mm
  pair spacing (sensitivity table given); the result must be re-run on the routed board (`--board`).
* Ciss, Rg,int, Coss,er are recalled datasheet-typical values (`devices.py` flags verified=False).
* Overshoot: linear L di/dt with assumed current fall times; no device switching model, no diode reverse recovery
  (SiC body diode), no damping by the loop resistance, no measurement.
* Literature ranges are recollections, not verified citations.
