# 04 Topology and DAB operation

> Reading time: ~55 min. Prerequisites: chapters 01-03. Files covered:
> `SiC_6k6_Industrial_DAB/03_Mathematical_Models/dab_mathematical_model.md`,
> `SiC_6k6_Industrial_DAB/dabtools/dab/dab_model.py`, `SiC_6k6_Industrial_DAB/dabtools/dab/control.py`,
> `SiC_6k6_Industrial_DAB/04_Design_Calculations/design_report.md`,
> `SiC_6k6_Industrial_DAB/11_Control_Algorithms/control_design.md`,
> `SiC_6k6_Industrial_DAB/05_Simulation/switched_results.json`.

## Overview

**Level 1 - Beginner:** A dual active bridge is two identical "square-wave makers" (full bridges)
facing each other through a transformer, with a coil (the series inductor) in between. Both make the
same 100 kHz square wave; the only thing the controller changes is the small delay between them.
Delay the second bridge and energy flows from the first to the second; let it run ahead and energy
flows back. The coil is what turns a delay into a current, and the current into power.

**Level 2 - Engineering:** With single phase shift (SPS) the power is P = V1 V2' phi (pi - |phi|) /
(2 pi^2 fs L), maximum at phi = pi/2; our design uses L = 64 uH and phi_nom = 28.2 deg at 800/400 V,
6.6 kW, with P_max = 12.5 kW. The inductor current is trapezoidal at d = n V2 / V1 = 1 and triangular
away from it, which raises rms current, peak current and backflow power at the corners of the
650-850 / 300-450 V window (d = 0.71-1.38). Extended (EPS), dual (DPS) and triple (TPS) phase shift add
the inner shifts D1, D2 to reduce this; the firmware default is EPS voltage matching. The same equation
with negative phi gives reverse power; the closed-loop switched simulation shows start-up, load steps,
a 10 % HV dip, reversal and a short circuit.

**Level 3 - Research:** The DAB's open problems are all visible in this chapter: ZVS is lost at light
load (below 24-35 % at d = 1 with SPS, worse at the corners), the optimal modulation is a
constrained optimisation that depends on parameters (L, Coss) that drift or are unknown, and the
light-load regime needs a different strategy (TPS search, frequency modulation, burst) than the
full-power envelope. The 2026 modules treat these as adaptive ZVS maps (`Advanced_Research_2026/Adaptive_MPC/`),
online estimation of L (`Advanced_Research_2026/Digital_Twin/`) and a supervisor that chooses (D1, D2)
on the estimated parameters.

## Structure and principle

### The DAB circuit: two bridges, series inductor, transformer
**What is it?** Bridge 1 (HV, Q1-Q4) across the 800 V link produces v1(t) in {+V1, 0, -V1}; bridge 2
(LV, Q5-Q8) across the 400 V link produces v2(t) in {+V2, 0, -V2}; the transformer (n = N1/N2 = 2)
couples them and the series inductance L (external inductor plus leakage, 64 uH referred to the HV
side) links the two voltages: L di/dt = v1(t) - n v2(t).

**Why do we need it?** Two active bridges give bidirectional flow and three-level voltages on both
sides; the inductor is the energy-transfer element whose current is set by the phase shift; the
transformer gives isolation and the 2:1 ratio.

**How does it work?**
**Level 1 - Beginner:** Two paddle wheels in one channel: each pushes the water with the same rhythm;
if the second paddles a little later than the first, water (energy) is pushed from the first to the
second. The coil is the water's inertia: it takes a moment to get going and a moment to stop.
**Level 2 - Engineering:** Referring everything to the HV side (V2' = n V2, L on the HV side), the
equivalent circuit is two square-wave sources with an inductor between them (section 1 of
`03_Mathematical_Models/dab_mathematical_model.md`). The magnetising inductance (~10.9 mH) is neglected
for power transfer; the loop resistance R_s ~ 0.3 Ohm is neglected in the analytical model and included
in the switched plant (`dabtools/dab/sim_switched.py`). Physical connections: HV bridge outputs SW_A ->
external inductor L1 (through the CT loop) and SW_B -> transformer primary; LV bridge outputs SW_C,
SW_D -> transformer secondary (`16_BOM/bom.md`, J3, J4, J7, J8, J9, CT1).
**Level 3 - Research:** Every current in the lossless model scales with 1/L, which makes L the one
parameter identifiable from port measurements; Coss enters only through the switching edges and is
not identifiable from averages (`Advanced_Research_2026/Digital_Twin/README.md`, section 1). The
transformer's interwinding capacitance (631 pF) and the inductor's gap field are the parasitics that the
lumped model hides.

**Example from our converter:** `[Implemented]` L = 64 uH = 59.9 uH (E55/28/21 gapped inductor, 17 turns)
+ 4.1 uH (E65/32/27 transformer leakage, 28:14 interleaved) (`04_Design_Calculations/design_report.md`,
sections 1, 5, 6). Figure `04_Design_Calculations/img/sps_waveforms.png` shows the analytical waveforms
at nominal; `05_Simulation/img/sim_switching_waveforms.png` the closed-loop switched waveforms at 50 %
load; `05_Simulation/img/spice_sps_waveforms.png` the ngspice check.

**Engineering calculations:** The design equation for L from the power equation: L = V1 V2' phi_nom
(pi - phi_nom) / (2 pi^2 fs P) = 800 x 800 x 0.4916 x 2.650 / (2 x 9.870 x 1e5 x 6600) = 64.0 uH (the
design script rounds L and recomputes phi_nom = 28.17 deg, `04_Design_Calculations/design_values.json` -> `phi_nom`).

**Design decision made in this project:** `[Implemented]` phi_nom = 28 deg at the nominal point
(spec `phi_nom_deg`: 28), leaving a factor 1.9 between 6.6 kW and P_max = 12.5 kW so that the phase
shift stays below 60 deg at every corner (57.1 deg at 650/300 V is the largest, `04_Design_Calculations/design_report.md`,
section 2) with control margin to the pi/2 maximum.

**Alternatives considered:** Larger phi_nom (smaller L, higher P_max but lower ZVS energy and faster
di/dt); integrated leakage (chapter 01); three-phase DAB (`02_Topology_Comparison/topology_comparison.md`).

**How to verify it:** `python3 SiC_6k6_Industrial_DAB/04_Design_Calculations/dab_design.py` reproduces
L and the corner table; `05_Simulation/run_switched_sim.py` and `05_Simulation/gen_spice.py` confirm the
waveforms. `[Simulated]`

**Common mistakes:** Forgetting to refer V2 and L to the same side; treating the magnetising
inductance as part of L; thinking the transformer "stores" the energy (the inductor does; the
transformer only couples).

**Interview explanation (30 s):** Two SiC full bridges make 100 kHz square waves on an 800 V and a
400 V link; a 2:1 transformer couples them and a 64 uH inductor between them turns the phase shift into
a current. The equation is one line, L di/dt = v1 - n v2, and everything else in the design follows
from it.

**Research-level explanation:** The lumped model is exact for the lossless, parasitic-free circuit and
is used as the physics prior of the twin; what remains unmodelled - Coss(v), winding capacitance, loop
inductance, core non-linearity - is precisely what the 2026 modules attempt to extract, estimate or
bound.

### Phase-shift power transfer: the SPS power equation
**What is it?** With both bridges producing full square waves (D1 = D2 = 1) and bridge 2 lagging
bridge 1 by the angle phi, the average power is
P = V1 V2' phi (pi - |phi|) / (2 pi^2 fs L), |phi| <= pi/2, with P_max = V1 V2' / (8 fs L) at phi = pi/2
(equations (4) and (5) of `03_Mathematical_Models/dab_mathematical_model.md`).

**Why do we need it?** It is the control law (power from phi), the design equation (L from the nominal
phi) and the feasibility check (P_max at every corner).

**How does it work?**
**Level 1 - Beginner:** The longer the delay between the two bridges, the longer the coil is pushed
hard and the more current it carries - up to a point: beyond a quarter period the push starts to
cancel itself, so there is a maximum at 90 deg.
**Level 2 - Engineering:** Figure `img/ch04_power_vs_phi.png` (script `img/fig_ch04_dab_operation.py`)
plots P(phi) for five voltage pairs with L = 64 uH: at 800/400 V the curve reaches 6.6 kW at 28.2 deg
and peaks at 12.5 kW; at 650/300 V (lowest V1 V2' product) 6.6 kW needs 57.1 deg and P_max is only
8.0 kW-class (7.2 kW with the 67.3 uH of the topology study). The firmware inverts the equation:
phi = (pi - sqrt(pi^2 - 4 c)) / 2 with c = 2 pi^2 fs L |P| / (V1 V2'), the smaller root
(`dab_model.sps_phi_for_power`, `dabtools/dab/control.py` `phi_from_power`).
**Level 3 - Research:** The equation assumes constant L and lossless bridges. Because P is
proportional to 1/L, a 20 % error in L is a 20 % error in the delivered power for a given phi; the PI
loop hides this in closed loop, but the ZVS boundaries and current limits computed from the nominal L
are wrong by the same 20 % - the motivating observation of the twin's supervisory study (the nominal
model under-predicts rms current by 10.5 % on average when L is 20 % low,
`Advanced_Research_2026/Digital_Twin/README.md`, section 3).

**Example from our converter:** `[Simulated]` Phase shift at 6.6 kW for the nine corners
(`04_Design_Calculations/design_report.md`, section 2): 57.1, 36.7, 31.5 deg at V1 = 650 V (V2 = 300, 400, 450 V); 41.0, 28.2,
24.4 deg at 800 V; 37.7, 26.2, 22.8 deg at 850 V. All below 60 deg, so full power is reachable everywhere
with control margin (`04_Design_Calculations/design_values.json` -> `corners[].Pmax_frac` = 1.0).

**Engineering calculations:** P_max at 800/400 V = 800 x 800 / (8 x 1e5 x 64e-6) = 12.5 kW
(`04_Design_Calculations/design_values.json` -> `Pmax_nom`). The numerical engine gives 12.51 kW at phi = pi/2 (grid effect).
The closed-form cross-check at 800/400 V, 6.6 kW: numerical P = 6595 W vs 6600 W closed form
(`03_Mathematical_Models/dab_mathematical_model.md`, section 2).

**Design decision made in this project:** `[Implemented]` SPS is the control baseline; the controller
output is a power command converted by the modulator inverse, so the loop gain does not depend on V1
or on the operating phase shift (`11_Control_Algorithms/control_design.md`, section 1); phi is limited to
60 deg (`11_Control_Algorithms/control_params.json` -> `phi_max_deg`).

**Alternatives considered:** Direct phi control with a PI (gain varies +/-15 % over the voltage range);
current-mode control from the CT.

**How to verify it:** `DABPoint.P` vs `sps_power()` in `dabtools/dab/dab_model.py`; the ngspice model's
measured power (`05_Simulation/gen_spice.py`). `[Simulated]`

**Common mistakes:** Using the larger root of the quadratic (phi > pi/2, same power, far higher
current); forgetting the sign convention (bridge 2 lags for 1 -> 2); applying the SPS formula when
D1 or D2 < 1.

**Interview explanation (30 s):** Power in a DAB is V1 V2' phi (pi - phi) over 2 pi^2 f L: linear in the
phase shift at first, peaking at 90 deg. We size L = 64 uH so that 6.6 kW needs 28 deg at the nominal
voltages and at most 57 deg at the worst corner, leaving a factor 1.9 to the 12.5 kW maximum.

**Research-level explanation:** The SPS equation is the special case D1 = D2 = 1 of a family whose
general member has no convenient closed form for every region of (D1, D2, phi); the project's engine
computes <v1 i> numerically for any pattern and uses the closed form only as a cross-check and as the
firmware inverse.

### Voltage matching d = n V2 / V1 and the shape of the current
**What is it?** d is the ratio of the referred LV voltage to the HV voltage. At d = 1 the inductor sees
V1 + V2' during the shift interval and zero outside it: trapezoidal current. At d != 1 the second slope
is (V1 - V2') / L, non-zero, and the current is triangular with higher peak and rms.

**Why do we need it?** The voltage window 650-850 / 300-450 V spans d = 0.71 to 1.38, so the converter
must work well away from d = 1; rms current, peak current, backflow power and the ZVS range all depend
on d.

**How does it work?**
**Level 1 - Beginner:** If both bridges push with the same strength (d = 1), the coil's current rises,
then stays flat, then falls - a smooth, efficient shape. If one bridge is stronger, the current keeps
rising until the weaker bridge flips - a sharp triangle with a higher peak that heats everything more.
**Level 2 - Engineering:** Figure `img/ch04_waveforms_three_ratios.png` shows 800/400 V (d = 1.00,
phi 28.2 deg, 9.8 A peak, 9.2 A rms), 850/300 V (d = 0.71, 37.7 deg, 19.6 A peak, 12.2 A rms) and
650/450 V (d = 1.38, 31.5 deg, 18.7 A peak, 11.3 A rms), all at 6.6 kW with L = 64 uH. Backflow power
(`02_Topology_Comparison/topology_comparison.json`, L = 67.3 uH): 327 W at d = 1.00, 1464 W at 0.71,
28 W at 1.38 - asymmetric because backflow is defined at port 1. The edge currents I0 (HV) and I1 (LV)
move in opposite directions with d: at 850/300 V I0 = 19.6 A but I1 = 4.2 A; at 650/450 V I0 = 2.5 A but
I1 = 18.7 A (closed form (2)-(3), figure `img/ch04_edge_currents_vs_d.png`).
**Level 3 - Research:** The asymmetry means that at each corner one bridge is far inside ZVS and the
other at the limit; EPS voltage matching (set the inner duty of the higher-voltage bridge to d so that
the applied volt-seconds match) removes most of the circulating current; the question of the optimal
(D1, D2, phi) for minimum rms subject to ZVS at every edge is the classical TPS problem (Krismer and
Kolar 2012, reference [8]).

**Example from our converter:** `[Simulated]` ZVS "both bridges down to (% load)" with SPS
(`02_Topology_Comparison/topology_comparison.md`, section 2): 24 % at 800/400 V, 26 % at 650/300 V, 64 % at 650/400 V, 92 % at
650/450 V, 66 % at 800/300 V, 64 % at 800/450 V, 80 % at 850/300 V, 38 % at 850/400 V, 50 % at 850/450 V.
The corners are the problem; the nominal point is fine.

**Engineering calculations:** Ideal (energy-free) ZVS conditions, equations (6)-(7): HV bridge needs
phi > pi (d - 1) / (2 d), LV bridge phi > pi (1 - d) / 2. At d = 1.38 the HV bridge needs phi > 25.0 deg
(we use 31.5 deg at full power, margin 0.7 A); at d = 0.71 the LV bridge needs phi > 26.5 deg (we use
37.7 deg, margin 3.0 A). At half load the phase shifts drop to roughly 17 deg and both corners lose ZVS
on one bridge.

**Design decision made in this project:** `[Implemented]` n = 2 puts d = 1 at the nominal 800/400 V
point; the full-power envelope requirement EL-04 is stated for 0.86 <= d <= 1.16, with the derating
map (`04_Design_Calculations/img/derating_map.png`) covering the rest; EPS voltage matching
(D of the higher-voltage bridge = d) as the firmware default (`dabtools/dab/control.py`, `11_Control_Algorithms/control_params.json`
`tps_table_note`).

**Alternatives considered:** Non-integer n to centre the window (d range 0.71-1.38 is centred at
1.0 geometrically, so n = 2 is already the centre); variable-frequency operation to keep ZVS at light
load.

**How to verify it:** `04_Design_Calculations/dab_design.py` derating and ZVS maps
(`04_Design_Calculations/design_values.json` -> `derating.zvs_sps`); `11_Control_Algorithms/control_design.py` modulation
table (`11_Control_Algorithms/img/modulation_rms.png`). `[Simulated]`

**Common mistakes:** Reading backflow power as a loss (it is circulating power; the loss is the extra
I^2 R it causes); assuming ZVS at full load implies ZVS at light load; ignoring that the two bridges
lose ZVS at opposite corners.

**Interview explanation (30 s):** d = n V2 / V1 is 1 at our nominal point, where the current is a flat
trapezoid; at the corners it is 0.71 or 1.38 and the current becomes a triangle with twice the peak
and 1.5 kW of circulating power. One bridge then sits at the ZVS limit even at full load, which is why
the firmware uses EPS voltage matching rather than plain SPS.

**Research-level explanation:** The d-dependence couples the modulation problem to parameter
knowledge: the edge currents at the corners are small differences of large terms (equations (2)-(3)),
so a 20 % error in L or an unmodelled Coss moves a bridge from ZVS to hard switching without any
visible change at the ports - the observability argument in one sentence.

## Modulation and operating modes

### SPS, EPS, DPS and TPS modulation
**What is it?** Single phase shift (SPS): D1 = D2 = 1, one variable phi. Extended phase shift (EPS):
one bridge three-level (D < 1), the other square. Dual phase shift (DPS): both bridges with the same
inner shift D1 = D2. Triple phase shift (TPS): independent D1, D2 and phi (section 5 of
`03_Mathematical_Models/dab_mathematical_model.md`).

**Why do we need it?** The inner shifts insert zero-voltage intervals that reshape the inductor
current: they can match the volt-seconds of the two bridges at d != 1, reduce rms and backflow and
keep the edge currents above the ZVS threshold at light load.

**How does it work?**
**Level 1 - Beginner:** Instead of only choosing when the second bridge flips, you can also make each
bridge pause briefly at zero in the middle of its stroke; a well-placed pause lets the stronger bridge
push less so that the two match, and the current stays smooth.
**Level 2 - Engineering:** The numerical engine (`dabtools/dab/dab_model.py`, `three_level()`,
`waveforms()`) builds any pattern and computes P, rms, peak, backflow and the edge currents with sign;
`tps_search()` runs a 13 x 13 grid over (D1, D2) with bisection on phi for the target power, keeps only
points with ZVS margin >= 0 on every edge of both bridges, and returns the minimum-rms point. Results at
the corners (`04_Design_Calculations/design_report.md`, section 3): at 850/300 V TPS with D1 = 0.78 cuts backflow from 1417 W to
225 W at equal rms (12.1 A) and extends ZVS to 100 % of the load range; at 800/300 V D1 = 0.93 cuts
backflow 1231 -> 754 W; at 800/400 V nothing changes (D1 = D2 = 1 is already optimal). Modulation
comparison at 850/300 V, 25 % load (`11_Control_Algorithms/control_design.md`, section 3): SPS 6.1 A rms,
1378 W backflow, ZVS margin -7.9 A; EPS 4.8 A, 376 W, -1.0 A; DPS 5.3 A, 150 W, -5.9 A; TPS 4.4 A, 196 W,
+1.0 A.
**Level 3 - Research:** TPS gives the lowest rms, but the gain over EPS is small in this ratio range;
EPS needs no table and is the firmware default. The optimal modulation depends on L and Coss: the
twin's supervisor re-optimises (D1, D2) on a 16-candidate grid around EPS matching using the estimated
L, with a 1 A ZVS margin and the 32 A peak limit, and falls back to the fixed EPS schedule when the
estimate is untrusted; it reduced hard-switched edges from 61 to 56 over 27 points and rms by 2.3 % on
average, but did not remove light-load hard switching (`Advanced_Research_2026/Digital_Twin/README.md`,
section 3). AI-based TPS models (L02) and hybrid-shift MPC (L01) are the 2026 literature's answers;
both are prototype-scale.

**Example from our converter:** `[Simulated]` EPS voltage matching in the switched simulation: the
dead-bus start case (LV link at 0 V, 2 mF, 10 % load) uses D1 = n V2 / V1 so that the HV bridge's
volt-seconds match the rising LV voltage (`05_Simulation/run_switched_sim.py`, case 5); the latest run
ends with an I_PK fault at 61.8 A peak and V2 = 93 V (`05_Simulation/switched_results.json` ->
`dead_bus_start`) - a documented negative result: the current-limited ramp from a dead bus is not yet
solved by EPS matching alone and needs the CC start-up logic to be revisited.

**Engineering calculations:** EPS matching rule: the bridge with the higher referred voltage gets
D = d (or 1/d) so that V1 D1 ~ n V2 D2; at 850/300 V, d = 0.71, the HV bridge runs with D1 = 0.71 - the
TPS search found 0.78 optimal, close to it. The D floor is 0.12 and the V2 floor 40 V in the firmware
(`11_Control_Algorithms/control_params.json` -> `D_min`, `V2_floor`).

**Design decision made in this project:** `[Implemented]` SPS baseline, EPS voltage matching as the
firmware default (no table), TPS as an optional look-up table over (d, P) generated in
`12_Optimization/` (`11_Control_Algorithms/control_params.json` -> `tps_table_note`). `[Proposed]` adaptive (D1, D2) from the
twin's supervisor.

**Alternatives considered:** DPS (Bai and Mi 2008, reference [10]): worse ZVS margin than EPS in the
project's table; frequency modulation; burst mode at light load.

**How to verify it:** `dab_model.tps_search()`; `11_Control_Algorithms/control_design.py`; modulation
changes are applied at the period boundary in the firmware's modulator and exercised by the SIL
harness (`10_Firmware/`). `[Simulated]`, `[Verified]` for the SIL checks.

**Common mistakes:** Changing D in the middle of a period (volt-second asymmetry -> DC current);
using the SPS power formula with D < 1; optimising rms without the ZVS constraint (the minimum-rms
point without ZVS is often hard switched).

**Interview explanation (30 s):** SPS uses one knob, the phase between the bridges; EPS, DPS and TPS
add zero intervals inside each bridge's square wave. At the voltage corners EPS matching cuts the
circulating power by a factor of three to six and keeps ZVS at light load; TPS does slightly better at
the cost of a table. Our firmware defaults to EPS because it needs no table.

**Research-level explanation:** Minimum-conduction-loss modulation has a closed form (Krismer and
Kolar 2012); the project uses a bounded numerical search instead and validates against the
qualitative behaviour; the research question is not the optimum for known parameters but the optimum
under parameter uncertainty and drift, with ZVS as a hard constraint - a robust or adaptive
optimisation problem.

### Forward and reverse power flow, start-up and transients
**What is it?** Forward: HV -> LV, the LV port regulated (CV with current limit, CC/CV for a
battery); reverse: LV -> HV with the HV voltage or power regulated as commanded over CAN (APP-03).
Transients: soft start from a precharged link, load steps, HV-bus dips, reversal, short circuit and
dead-bus start.

**Why do we need it?** The requirements EL-08 to EL-12 (regulation +/-1 %, ripple <= 1 %, 50 % step
with <= 3 % deviation and < 5 ms recovery, reversal in < 20 ms with < 5 % overshoot, cycle-by-cycle
current limit) must be shown before any hardware exists.

**How does it work?**
**Level 1 - Beginner:** The controller watches the output voltage once every switching cycle and
nudges the delay between the bridges up or down to hold it at 400 V; to send energy back it simply
makes the delay negative. Starting is done gently (soft start) and every dangerous event (too much
current, too high or too low a voltage) switches everything off.
**Level 2 - Engineering:** The controller runs once per period (one-period delay, chapter 05): PI on
the voltage error produces a power command (limited to +/-1.1 P_rated, slew 2 kW/ms), the modulator
inverse returns phi (plus dead-time compensation), EPS matching sets D1/D2, limits and the state machine
(INIT, PRECHARGE_WAIT, SOFTSTART, RUN, FAULT) wrap it (`dabtools/dab/control.py`). Results of
`05_Simulation/run_switched_sim.py` (`05_Simulation/switched_results.json`): start-up from 380 V to
400.0 V with 0.38 % overshoot and 40 ms rise (50 ms soft start); 50 -> 100 % load step with 0.37 % dip;
HV dip 800 -> 720 V for 20 ms: V2 stays within 399.86-400.11 V; reversal +6.6 -> -6.6 kW: V1 within
797.2-802.6 V, V2 within 398.2-401.8 V, no fault; LV short through 0.5 Ohm: phi saturates at 60 deg, peak
31.2 A (below the 32 A hardware trip), V2_UV fault, V2 collapses to 0.5 V.
**Level 3 - Research:** The one-period delay and the 612 Hz crossover (`11_Control_Algorithms/control_params.json`) make
the PI slow compared with what an MPC could do (0.1 V dip vs 1.5 V on a 50 % step in
`11_Control_Algorithms/control_design.md`, section 4); the MPC relies on a load estimate and plant
parameters, which links control performance to the twin. Which port is regulated in each direction
and how several converters share a bus is a system-level question outside the model.

**Example from our converter:** `[Simulated]` Figures: `05_Simulation/img/sim_startup_loadstep.png`,
`05_Simulation/img/sim_v1_dip.png`, `05_Simulation/img/sim_reversal.png`,
`05_Simulation/img/sim_deadbus_start.png`. The load-step dip of 0.37 % (0.49 % in the earlier run
logged in `05_Simulation/switched_run.log`) is far inside the 3 % of EL-10.

**Engineering calculations:** Reversal ramp: 13.2 kW / (2 kW/ms) = 6.6 ms = 660 periods; link energy
exchanged during the reversal is small compared with the 25.6 J / 9.6 J stored, which is why the
excursions are < 0.7 %. Short-circuit peak 31.2 A at phi = 60 deg and V2 ~ 0: the inductor alone limits
the current, di/dt = 800 / 64e-6 = 12.5 A/us for the whole half period gives 62 A without the phase
limit - the 60 deg phase cap and the 32 A trip are what keep it at 31 A.

**Design decision made in this project:** `[Implemented]` Power-command control with modulator
inverse and feedforward; EPS matching; phase cap 60 deg; hardware comparator trip at 32 A HV / 64 A LV,
OV 900 / 480 V, UV 600 / 250 V, NTC 95 C (`11_Control_Algorithms/control_params.json` -> `limits`,
`04_Design_Calculations/design_report.md`, section 8); direction commanded by the supervisory system only.

**Alternatives considered:** Explicit MPC with disturbance observer (documented research option);
current-mode inner loop; autonomous droop reversal (rejected, APP-03).

**How to verify it:** `05_Simulation/run_switched_sim.py` (all cases); `10_Firmware/` SIL harness
(35 checks) exercises the same control core in C; the staged lab plan
(`20_Experimental_Test_Plan/test_plan.md`) repeats each case at reduced voltage first. `[Simulated]`,
`[Verified]` SIL, `[Not yet tested]` hardware.

**Common mistakes:** Testing transients only at the nominal ratio; forgetting the external bus
capacitance of APP-04 (the simulation adds 500 uF / 1 mF); claiming the dead-bus start works when the
result file says I_PK fault.

**Interview explanation (30 s):** The controller runs once per 10 us period: a PI turns the voltage
error into a power command, the inverse of the power equation turns that into a phase shift, and the
sign of the shift sets the direction. In simulation a 50 % load step dips the output 0.4 %, a 10 % HV
dip is invisible, a full reversal takes 6.6 ms with under 0.7 % excursion, and a short trips at 31 A.

**Research-level explanation:** The transients are where parameter error matters least (the loop
absorbs it) and where constraint handling matters most (current limit, ZVS boundary during the
reversal); constrained MPC and safe-RL policies with a deterministic fallback are the 2026 research
directions (`Advanced_Research_2026/Adaptive_MPC/`, `Advanced_Research_2026/Safe_RL_Research/`).

### Light-load loss of ZVS and its mitigation
**What is it?** Because the edge currents scale with power, below a certain load the inductor current
at the switching instant falls under the ZVS threshold (2.0 A HV, 3.07 A LV) and one or both bridges
switch hard; the loss then rises sharply and the efficiency curve collapses (89 % at 10 % load in
`04_Design_Calculations/design_values.json` -> `eff_curves`).

**Why do we need it?** Industrial converters spend much of their life at partial load; EL-04a asks for
ZVS above 25 % load within the full-power envelope, and the thermal design must survive hard
switching below it.

**How does it work?**
**Level 1 - Beginner:** Soft switching needs enough current to "pull the door shut"; at light load
there is not enough, and the door slams (hard switching) - noisy, lossy, but survivable if the heatsink
has margin.
**Level 2 - Engineering:** ZVS boundaries with SPS over the (V1, V2) grid
(`04_Design_Calculations/design_values.json` -> `derating.zvs_sps`): 30 % of load at 800/400 V, 20 % at 650/325 V, up to
100 % at 650/450 V and 85 % at 850/300 V. With EPS matching and the TPS search the corners improve
(`04_Design_Calculations/design_report.md`, section 3: ZVS down to 35 % at 800/400 and 650/300 V, 100 % remains at 650/450 V
and 850/300 V even with TPS at full power - the table's "ZVS down to" column is the load fraction below
which ZVS is lost). The hard-switching penalty in the loss model is (Eon + Eoff + Coss,er V^2) fs per
edge, i.e. tens of watts, which the 0.22 K/W heatsink absorbs at light load (losses are then small
anyway) but not at full load.
**Level 3 - Research:** The twin's supervisor could not remove light-load hard switching: 16 of 27
operating points still had at least one hard-switched edge with the adaptive (D1, D2), against 19 with
the fixed schedule - "a property of the DAB at 10-30 % load with SPS/EPS"
(`Advanced_Research_2026/Digital_Twin/README.md`, section 3). The candidates are a TPS search over the
whole (D1, D2, phi) space, frequency reduction at light load (more volt-seconds per edge) and burst
mode; their ZVS maps are in `Advanced_Research_2026/Adaptive_MPC/`. The ZVS boundary itself is
uncertain by the Coss and L tolerances (`Advanced_Research_2026/Uncertainty_Quantification/`).

**Example from our converter:** `[Simulated]` Efficiency curve at 800/400 V (`eff_curves["800/400"]`):
89.2 % (10 %), 94.8 % (20 %), 98.2 % (30 %), 98.4 % (40 %), 98.6-98.7 % (50-100 %). The step between 20 and
30 % is the ZVS boundary; below it the fixed losses (12 W auxiliary + 26.4 W copper estimate) and the
hard-switching term dominate.

**Engineering calculations:** At 800/400 V the edge current is I0 = V1 phi / (omega L) for d = 1; it
equals 2.0 A at phi = 2.0 x 40.2 / 800 = 0.10 rad = 5.8 deg, i.e. at P = 800 x 800 x 0.10 x 3.04 / (2 x
9.87 x 1e5 x 64e-6) = 1.5 kW = 23 % of rated - consistent with the 24-30 % boundary of the maps (the maps
include C_par and the grid).

**Design decision made in this project:** `[Implemented]` Accept hard switching below ~25-35 % load
at d = 1 and below higher fractions at the corners, with the thermal margin to absorb it; EPS matching
as the default mitigation; `[Proposed]` light-load strategy (TPS search, frequency modulation, burst).

**Alternatives considered:** Larger L (raises ZVS energy, lowers P_max); auxiliary resonant
circuits (component count); CLLC resonant topology (ZVS over the whole range at a fixed ratio only).

**How to verify it:** ZVS maps from `04_Design_Calculations/dab_design.py`; per-edge margins from `DABPoint.zvs_margin()`;
hard-switching detection on hardware by drain-voltage probing or the proposed transition-time sensor.
`[Simulated]`, `[Proposed]`

**Common mistakes:** Quoting the full-load ZVS margin as if it applied to the whole range; assuming
EPS alone solves light load (it helps at the corners, not at d = 1); forgetting that losing ZVS also
means a hard-switched dv/dt that the gate resistor now does control (31 V/ns at turn-on with 3.3 Ohm,
`Advanced_Research_2026/Active_Gate_Drive/README.md`).

**Interview explanation (30 s):** Below roughly a quarter of full load the inductor current at the
switching instant drops under the 2-3 A the output capacitances need, and the bridges switch hard;
efficiency falls from 98 % to 89 % at 10 % load. EPS matching fixes the voltage corners but not light
load at d = 1; that needs a frequency or burst strategy, which is research, not baseline.

**Research-level explanation:** Light-load ZVS is a constrained-optimisation problem whose constraint
(the ZVS boundary) depends on unobservable parameters; the honest research path combines a conservative
map, an estimator for what can be estimated (L) and a sensor proposal for what cannot (Coss), rather
than claiming a modulation that "guarantees" ZVS.

## Worked example(s) with real numbers

**Example 1 - from specification to L and phi.** `[Simulated]` Spec: 6.6 kW, 800/400 V, n = 2, 100 kHz,
phi_nom = 28 deg (`04_Design_Calculations/design_values.json` -> `spec`). L = 800 x 800 x 0.4887 x (3.1416 - 0.4887) / (2 x
9.8696 x 1e5 x 6600) = 63.7 uH -> rounded to 64 uH, phi_nom recomputed to 28.17 deg. P_max = 640 000 /
(8 x 1e5 x 64e-6) = 12.5 kW. Edge currents I0 = I1 = (V1 pi + V2' (2 phi - pi)) / (2 omega L) = 800 x 2
x 0.4916 / (2 x 628 318 x 64e-6) = 9.78 A (closed form) vs 9.75 A (numerical). ZVS margins 9.75 - 2.0 =
7.7 A (HV), 9.75 - 3.07 ... referred to the LV side the margin is 8.2 A (`04_Design_Calculations/design_values.json` ->
`nominal.zvs1`, `nominal.zvs2`).

**Example 2 - the worst corner.** `[Simulated]` 850/300 V: d = 0.706, V2' = 600 V. phi for 6.6 kW:
c = 2 pi^2 x 1e5 x 64e-6 x 6600 / (850 x 600) = 1.635; phi = (pi - sqrt(pi^2 - 6.54)) / 2 = 0.658 rad =
37.7 deg. I0 = (850 pi + 600 (2 x 0.658 - pi)) / (2 x 628 318 x 64e-6) = (2670 - 1095) / 80.4 = 19.6 A;
I1 = (850 (1.316 - 3.142) + 600 pi) / 80.4 = (-1552 + 1885) / 80.4 = 4.1 A. The HV bridge has 17.3 A of
margin, the LV bridge 3.0 A at full load and loses ZVS below 80 % load with SPS; TPS with D1 = 0.78
holds ZVS to 100 % of load... that is, over the whole range, with backflow cut from 1417 W to 225 W
(`04_Design_Calculations/design_report.md`, sections 2-3).

**Example 3 - reading the switched simulation at 50 % load.** `[Simulated]` Closed loop at 800/400 V,
3.3 kW: I_pk = 4.96 A, I_rms = 4.42 A, V2 ripple 6.1 mV (`05_Simulation/switched_results.json` ->
`switching_50pct`). Analytical at the same power: phi = 12.8 deg, I_pk = 4.44 A, I_rms = 4.33 A
(`dabtools/dab/dab_model.py`). The plant's higher peak comes from the 0.3 Ohm loop resistance (the controller must
raise phi to deliver the same power) and the dead-time compensation; the 50 % point is comfortably
inside ZVS (4.4 A > 2.0 A).

## How this chapter connects to the files

| File | What it contains | Status |
|---|---|---|
| `SiC_6k6_Industrial_DAB/03_Mathematical_Models/dab_mathematical_model.md` | circuit, SPS equations (1)-(5), ZVS (6)-(9), modulations, averaged model | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/dabtools/dab/dab_model.py` | three_level(), waveforms(), DABPoint, sps_* closed forms, zvs_current_min, dead_time_required, tps_search | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/dabtools/dab/control.py` | PI, modulator inverse, EPS matching, state machine, limits | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/dabtools/dab/sim_switched.py` | DABPlant with R_s, pattern generation | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/04_Design_Calculations/design_report.md` | L, phi corners, TPS table, ZVS margins, protection thresholds | `[Simulated]` |
| `SiC_6k6_Industrial_DAB/04_Design_Calculations/design_values.json` | all numbers incl. derating.zvs_sps, tps, eff_curves | `[Simulated]` |
| `SiC_6k6_Industrial_DAB/02_Topology_Comparison/topology_comparison.json` | SPS stress map at L = 67.3 uH: backflow, ZVS min load | `[Simulated]` |
| `SiC_6k6_Industrial_DAB/11_Control_Algorithms/control_design.md` | modulation comparison table, MPC alternative, reverse flow | `[Simulated]` |
| `SiC_6k6_Industrial_DAB/11_Control_Algorithms/control_params.json` | phi_max 60 deg, D_min, limits, slew | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/05_Simulation/run_switched_sim.py` | the six closed-loop cases | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/05_Simulation/switched_results.json` | start-up, load step, dip, reversal, short, dead-bus start results | `[Simulated]` |
| `SiC_6k6_Industrial_DAB/05_Simulation/img/sim_switching_waveforms.png` | closed-loop waveforms, 50 % load | `[Simulated]` |
| `SiC_6k6_Industrial_DAB/04_Design_Calculations/img/sps_waveforms.png` | analytical waveforms at nominal | `[Simulated]` |
| `Advanced_Research_2026/Digital_Twin/README.md` | supervisor results, light-load statement, plant defect fix | `[Simulated]` |
| `21_Human_Friendly_Learning_Notes/img/fig_ch04_dab_operation.py` | P(phi), edge currents vs power, waveforms at three ratios | `[Implemented]` |

## Viva / interview questions

### Basic (10)
1. What are the three main parts of a DAB?
   Two full bridges (HV and LV), a series inductor and a high-frequency transformer; in our design
   64 uH and 28:14 turns.
2. What does the controller change to control the power?
   The phase shift phi between the two bridges' square waves; 28.2 deg gives 6.6 kW at 800/400 V.
3. How does the DAB send power backwards?
   With a negative phase shift (bridge 2 leading): the power equation is odd in phi.
4. What is the maximum power and where?
   P_max = V1 V2' / (8 fs L) at phi = 90 deg; 12.5 kW at 800/400 V with L = 64 uH.
5. What is d and what is special about d = 1?
   d = n V2 / V1; at d = 1 the inductor current is a trapezoid with the lowest rms and peak for a given
   power and both bridges have equal ZVS margin.
6. Name the four modulation schemes.
   SPS (phi only), EPS (one bridge three-level), DPS (both bridges, same inner shift), TPS (all three
   independent).
7. Why does the DAB lose ZVS at light load?
   The edge currents scale with power; below about a quarter load they fall under the 2-3 A needed to
   discharge the device capacitances.
8. What is backflow power?
   Energy that flows back into the HV link during part of each period; 302 W at nominal, 1.4 kW at the
   850/300 V corner; it costs conduction loss without delivering energy.
9. What does the switched simulation show for a 50 % load step?
   A 0.37 % dip on the 400 V port against the 3 % allowed, with recovery essentially immediate.
10. Is any of this measured?
    No. Every number is calculated (`04_Design_Calculations/dab_design.py`) or simulated (`05_Simulation/run_switched_sim.py`, ngspice).

### Intermediate (10)
1. Derive L from the nominal phase shift.
   L = V1 V2' phi (pi - phi) / (2 pi^2 fs P) = 800 x 800 x 0.4887 x 2.653 / (2 x 9.87 x 1e5 x 6600) =
   63.7 uH, rounded to 64 uH.
2. Why choose 28 deg and not 45 deg at nominal?
   28 deg leaves P_max / P = 1.9 and keeps every corner below 60 deg (57.1 deg at 650/300 V); 45 deg would
   halve L, double di/dt and push the corners toward the 90 deg maximum with no control margin.
3. Write the edge currents I0 and I1 and explain their asymmetry with d.
   I0 = [V1 pi + V2' (2 phi - pi)] / (2 omega L), I1 = [V1 (2 phi - pi) + V2' pi] / (2 omega L); for d < 1
   I0 grows and I1 shrinks, for d > 1 the opposite, so the bridge on the lower-voltage side loses ZVS
   first at the corners.
4. Give the ideal ZVS conditions.
   HV: phi > pi (d - 1) / (2 d); LV: phi > pi (1 - d) / 2; both are automatically satisfied at d = 1 for
   any phi > 0; with finite Coss the energy criterion adds I_min = 2.0 / 3.07 A.
5. What does EPS voltage matching do and why is it the firmware default?
   Sets the inner duty of the higher-voltage bridge to d so the applied volt-seconds match; it removes
   most circulating power at d != 1 and keeps ZVS at light load without a look-up table.
6. Quote the TPS gain at the 850/300 V corner.
   Backflow 1417 -> 225 W, rms 12.2 -> 12.1 A, D1 = 0.78, ZVS over the whole load range
   (`04_Design_Calculations/design_report.md`, section 3).
7. How does the firmware obtain phi from the power command?
   phi = (pi - sqrt(pi^2 - 4 c)) / 2 with c = 2 pi^2 fs L |P| / (V1 V2'), signed by P, plus the dead-time
   compensation, capped at 60 deg.
8. What limits the short-circuit current in the simulation?
   The 60 deg phase cap and the inductor's di/dt (12.5 A/us at 800 V across 64 uH): the peak reaches
   31.2 A, below the 32 A comparator trip; the V2_UV fault then shuts down.
9. What does the dead-bus start case show?
   With EPS matching from V2 = 0 the latest run trips I_PK at 61.8 A with V2 at 93 V: a documented
   negative result that the current-limited ramp needs rework.
10. Why is the closed-loop peak current at 50 % load (4.96 A) above the analytical 4.44 A?
    The plant includes the 0.3 Ohm loop resistance and dead-time compensation, so the controller raises
    phi to deliver the same power; the difference is the expected model-plant gap.

### Advanced / research (10)
1. Why can the SPS formula not be used for D1, D2 < 1, and what does the project do instead?
   The piecewise-linear current has more segments and region-dependent closed forms (Zhao 2012 for
   DPS); the engine integrates (v1 - v2') / (omega L) numerically on a 4000-point grid and uses the
   closed form only for the SPS check (< 0.1 %).
2. What is the role of the sign convention in `switching_currents()`?
   Each edge is evaluated with the sign that makes "positive = favourable for ZVS" for the device that
   turns on, with port 2 inverted; this lets the same test work for any modulation.
3. Explain why the twin's supervisor could not remove light-load hard switching.
   At 10-30 % load with SPS/EPS the edge currents are below I_min for any (D1, D2) in the 16-candidate
   grid; the model's ZVS feasibility also differs from the plant's at the inner edges, so two points got
   worse - a larger margin or the lossy model is recommended (`Advanced_Research_2026/Digital_Twin/README.md`, section 3).
4. How does a 20 % error in L change the picture?
   Every current scales with 1/L, so phi for a given power, the ZVS boundaries and the rms prediction
   all move by ~20 %; the nominal model under-predicted rms by 10.5 % on average in the supervisory
   study. In closed loop the voltage is still regulated, but the constraints are evaluated wrongly.
5. Compare EPS, DPS and TPS at 850/300 V, 25 % load from the project's table.
   SPS 6.1 A / 1378 W / -7.9 A; EPS 4.8 A / 376 W / -1.0 A; DPS 5.3 A / 150 W / -5.9 A; TPS 4.4 A / 196 W /
   +1.0 A - only TPS achieves ZVS, EPS is close, DPS minimises backflow but not ZVS.
6. What is the backflow definition used and why is it asymmetric in d?
   Q_back = -<min(v1 i, 0)> at port 1; the circulating interval after each bridge-1 edge is long when
   V2' < V1 (d < 1) and short when V2' > V1, so 850/300 V shows 1464 W and 650/450 V only 28 W.
7. How does the modulator's time quantisation affect modulation research?
   The C2000 ePWM has 10 ns steps (0.36 deg); the plant has 200 steps per period; the twin evaluates
   its regressor on the applied pattern to remove the quantisation error, which otherwise biased the
   estimate by 4-7 % at small phase shifts.
8. Why is burst mode or frequency modulation proposed for light load rather than more TPS?
   Because the ZVS energy per edge depends on volt-seconds per edge, which TPS cannot raise at d = 1;
   lower frequency or bursts of full-current periods do; both are listed as needed, neither is in the
   baseline.
9. What would the APEC 2025 reconfigurable 6.6 kW DAB (L06) change?
   Switching between bridge configurations extends the voltage-ratio range without a wide phase or
   frequency sweep; its efficiency is not captured in the database, so it is a benchmark to read, not
   a number to quote.
10. What would be the first hardware experiment for this chapter?
    Open-loop SPS at reduced voltage (e.g. 100/50 V) and fixed phi, measuring i_L with the CT and the
    port powers, to validate P(phi) and the edge currents against `dabtools/dab/dab_model.py` before any ZVS claim.

## Pitches

**30 s:** The dual active bridge is two SiC full bridges, a 2:1 transformer and a 64 uH inductor; the
phase shift between the bridges sets the power, P = V1 V2' phi (pi - phi) / (2 pi^2 f L), 6.6 kW at 28 deg
and 12.5 kW maximum. Its weakness is light load and the voltage corners, where the current turns
triangular and soft switching is lost; extended phase shift fixes the corners and research is working on
light load.

**2 min:** Both bridges make 100 kHz square waves; bridge 2 lags by phi, the inductor sees V1 + n V2
during the lag and V1 - n V2 afterwards, and the resulting trapezoid of current delivers
V1 V2' phi (pi - phi) / (2 pi^2 f L). Designing for 28 deg at 800/400 V gives L = 64 uH and a 1.9x margin to
the 12.5 kW maximum; at the worst corner (650/300 V) the shift is 57 deg, still under the 60 deg cap.
Away from d = n V2 / V1 = 1 the current becomes a triangle: 19.6 A peak instead of 9.8 A, 1.4 kW of
circulating power, and one bridge at the ZVS limit even at full load - at 850/300 V the LV bridge has
3 A of margin and loses ZVS below 80 % load. EPS voltage matching (inner duty of the stronger bridge
set to d) is the firmware default and cuts circulating power by a factor of three to six; TPS does
slightly better with a table. Negative phi reverses the flow: the switched simulation reverses 6.6 kW in
6.6 ms with under 0.7 % bus excursion, holds a 50 % load step to 0.4 %, ignores a 10 % HV dip and trips
a short at 31 A. What remains open is light load at d = 1, where ZVS is lost below about a quarter load
and the 2026 supervisor could not recover it; frequency modulation or burst mode is the next step.

**10 min outline:**
* Circuit: two bridges, L = 59.9 + 4.1 uH, n = 2; equivalent circuit and the one-line equation.
* SPS power equation, P_max, firmware inverse, the 60 deg cap; corner phase shifts 22.8-57.1 deg;
  figure `img/ch04_power_vs_phi.png`.
* d and current shape: trapezoid vs triangle; figure `img/ch04_waveforms_three_ratios.png`; backflow
  327 / 1464 / 28 W; edge-current asymmetry, figure `img/ch04_edge_currents_vs_d.png`.
* Modulations: SPS/EPS/DPS/TPS, `tps_search()`, the 850/300 V 25 % table, EPS as default, TPS table.
* Operating modes: control structure, six simulation cases with numbers, dead-bus negative result.
* Light-load ZVS loss: maps, efficiency curve 89 -> 98 %, supervisor result 19 -> 16 of 27, candidates.
* Research links: twin (1/L), Adaptive_MPC maps, L01/L02/L06.
* Status: `[Simulated]` throughout; first hardware test is open-loop P(phi) at reduced voltage.

## Further reading

* `SiC_6k6_Industrial_DAB/01_Literature_Review/literature_review.md` [2] Kheraluwala et al. 1992 (SPS
  equation and ZVS boundaries), [4] Zhao et al. 2014 (DAB overview), [5] Hou and Li 2020 (modulation
  and control comparison), [8] Krismer and Kolar 2012 (minimum-conduction-loss modulation), [10] Bai
  and Mi 2008 (DPS), [12] Oggier et al. 2009, [13] Jain and Ayyanar 2011 (PWM control of the DAB).
* `Advanced_Research_2026/Literature_Database/literature_2022_2026.csv` L01 (hybrid-shift MPC with
  online identification, confirmed abstract), L02 (AI model of TPS, confirmed venue), L06 (6.6 kW
  reconfigurable DAB), L15-L17, L26, L27 (MPC with EPS/TPS).
* `SiC_6k6_Industrial_DAB/11_Control_Algorithms/control_design.md` - the modulation table and the MPC
  alternative.
