# 05 Mathematical model

> Reading time: ~60 min. Prerequisites: chapters 01, 04; calculus (integration of piecewise-linear
> functions), basic Laplace transforms for the control section. Files covered:
> `SiC_6k6_Industrial_DAB/03_Mathematical_Models/dab_mathematical_model.md`,
> `SiC_6k6_Industrial_DAB/dabtools/dab/dab_model.py`, `SiC_6k6_Industrial_DAB/dabtools/dab/losses.py`,
> `SiC_6k6_Industrial_DAB/11_Control_Algorithms/control_design.md`,
> `Advanced_Research_2026/Digital_Twin/README.md`, `Advanced_Research_2026/Digital_Twin/twin.py`,
> `Advanced_Research_2026/Digital_Twin/results/observability.json`.

## Overview

**Level 1 - Beginner:** The whole converter is described by one equation - the inductor law with two
square-wave voltages on either side. Because square waves are constant between edges, the current is a
chain of straight lines; the model is the geometry of that zig-zag: where it crosses zero, how high it
peaks, what its average and "heating value" are. Every design number in this project is read off that
zig-zag. The chapter shows the derivations, then checks them against a computer that simply adds up
the current step by step, and finally shows how the same zig-zag lets a computer estimate the inductor
value from measurements while the converter runs.

**Level 2 - Engineering:** Starting from L di/dt = v1 - v2' the chapter derives the piecewise-linear
SPS current, the edge currents I0 and I1 (equations (2)-(3)), the power (4)-(5), the ZVS energy criterion
I >= sqrt(2 Coss V^2 / L) (8) and the charge-based dead time t_d >= 2 Qoss / I (9), the rms current and
the backflow power, the loss-model structure, and the averaged (period) model I2 = n V1 phi (pi - phi) /
(2 pi^2 fs L) with its small-signal gain K_phi and the one-period delay T_d = 1.5 Ts that the PI design
in `11_Control_Algorithms/` uses. Each derivation is cross-checked against the numerical engine of
`dabtools/dab/dab_model.py` (P 6595 W vs 6600 W; I0 9.65 A vs 9.57-9.63 A at nominal).

**Level 3 - Research:** The lossless model has a structural property - every current is proportional
to 1/L for a fixed switching pattern - that turns parameter estimation into linear regression. The 2026
digital twin (`Advanced_Research_2026/Digital_Twin/`) builds its regressor on this, estimates 1/L with
RLS and EKF to 0.25 % on simulated data, and proves with a Fisher-information analysis which parameters
the board's sensors can identify at all: L yes (0.03 % after 1000 periods), the loss resistance weakly,
Coss not at all without a new sensor.

## Derivations

### Piecewise-linear inductor current and the edge currents I0, I1
**What is it?** For SPS (D1 = D2 = 1), over a half period 0 <= theta < pi (theta = omega t) the
inductor current obeys di/dtheta = (V1 + V2') / (omega L) for 0 <= theta < phi and di/dtheta =
(V1 - V2') / (omega L) for phi <= theta < pi, with half-wave symmetry i(theta + pi) = -i(theta). The
current at the bridge-1 edge is -I0 (theta = 0) and at the bridge-2 edge +I1 (theta = phi).

**Why do we need it?** I0 and I1 are the currents at the switching instants: they decide ZVS, the dead
time and the turn-off loss. The peak current is max(I0, I1); the rms follows from the trapezoid.

**How does it work?**
**Level 1 - Beginner:** Draw the two square waves, subtract them, and you get a voltage that is +big
for a short while, then +small (or zero), then -big, then -small. The current is the running total of
that: a steep ramp, a gentle ramp, a steep ramp down, a gentle ramp down - a zig-zag that repeats.
**Level 2 - Engineering:** Integrate the two slopes: i(phi) = -I0 + (V1 + V2') phi / (omega L);
i(pi) = i(phi) + (V1 - V2') (pi - phi) / (omega L). Half-wave symmetry gives i(pi) = +I0. Solving the two
equations: I0 = [V1 pi + V2' (2 phi - pi)] / (2 omega L) (2) and I1 = i(phi) = [V1 (2 phi - pi) + V2' pi] /
(2 omega L) (3) (`03_Mathematical_Models/dab_mathematical_model.md`, section 2). At d = 1 both reduce to
V1 phi / (omega L) = 800 x 0.4916 / (628 318 x 64e-6) = 9.78 A. The engine `sps_switching_currents()`
in `dabtools/dab/dab_model.py` implements exactly (2)-(3); `DABPoint.switching_currents()` reads the
same currents off the numerical waveform at every edge with the sign convention "positive = favourable
for ZVS".
**Level 3 - Research:** For D1, D2 < 1 the half period has up to five segments and the closed forms
depend on the ordering of the edges (region-dependent expressions, Zhao et al. 2012 for DPS); the
project avoids transcribing them by integrating numerically on a 4000-point grid, which serves SPS,
EPS, DPS and TPS with one code path. The price is a quantisation of edge positions to 2 pi / 4000 =
0.09 deg, visible at very small phase shifts.

**Example from our converter:** `[Simulated]` Nominal 800/400 V, 6.6 kW: closed form I0 = I1 = 9.78 A;
numerical edge currents 9.69-9.75 A (`04_Design_Calculations/design_values.json` -> `nominal.Ipk1` = 9.75 A); the model
document quotes 9.65 A vs 9.57-9.63 A for an earlier evaluation - all within the grid resolution.
Worst corner 850/300 V: I0 = 19.6 A, I1 = 4.1 A (worked example 2 of chapter 04).

**Engineering calculations:** Zero crossing of the current (needed for the backflow interval):
theta_zc = I0 omega L / (V1 + V2') = 9.78 x 40.2 / 1600 = 0.246 rad = 14.1 deg at nominal, half the
phase shift, as symmetry requires at d = 1.

**Design decision made in this project:** `[Implemented]` The closed forms are used in the firmware
(modulator inverse) and as the regression check; the design and optimisation scripts use the numerical
engine so that modulations can be changed without new algebra.

**Alternatives considered:** Full closed-form TPS expressions (Krismer and Kolar 2012); state-space
averaging (loses the intra-period information that ZVS needs); generalised averaging with harmonics
(first-harmonic approximation is poor at d != 1).

**How to verify it:** The cross-check in section 2 of `03_Mathematical_Models/dab_mathematical_model.md`;
figure `img/ch05_closed_vs_numeric.png` (script `img/fig_ch05_model.py`) compares (2) and (4) with the
engine over phi: 0.8 % maximum power error for phi >= 5 deg, 5.7 % below 5 deg where the grid
quantisation of the edge position dominates. `[Simulated]`

**Common mistakes:** Forgetting half-wave symmetry (the DC component must be zero in steady state);
sign errors in which edge sees which current; evaluating the current "at the edge" on the wrong side of
the discontinuity in a numerical waveform.

**Interview explanation (30 s):** The current is straight lines between the bridge edges; integrating
the two slopes over a half period and requiring the waveform to repeat with opposite sign gives the
two edge currents in closed form. At our nominal point both are 9.8 A; at the 850/300 V corner one is
19.6 A and the other only 4.1 A.

**Research-level explanation:** The edge currents at the corners are small differences of large terms
(V1 pi and V2' pi), which is why the ZVS boundary is so sensitive to L and to any unmodelled
volt-second asymmetry; the twin's plant defect (a one-cell asymmetry giving 13 A of DC current) was
found through exactly this sensitivity.

### Power: the closed form and the numerical cross-check
**What is it?** The period-average power P = <v1 i> = V1 V2' phi (pi - |phi|) / (2 pi^2 fs L) for
|phi| <= pi/2 (4), with P_max = V1 V2' / (8 fs L) at phi = pi/2 (5).

**Why do we need it?** It is the design equation for L, the control inverse and the feasibility
check; its agreement with the numerical engine validates the engine for the modulations that have no
closed form.

**How does it work?**
**Level 1 - Beginner:** Multiply the HV square wave by the zig-zag current and average: during the
positive half of v1 the current is mostly positive, so the product is mostly positive - energy goes
out of bridge 1 - except for a short interval right after the edge, where the current has not yet
reversed and energy flows back.
**Level 2 - Engineering:** Over the half period 0..pi with v1 = +V1: P = (V1 / pi) integral of i
dtheta. The integral of the trapezoid from -I0 to +I1 (slope (V1 + V2') / omega L over phi) and from
I1 to I0 (slope (V1 - V2') / omega L over pi - phi), substituting (2)-(3), collapses to
V2' phi (pi - phi) / (2 pi omega L) ... times V1 and with omega = 2 pi fs gives (4). The engine computes
`np.mean(self.v1 * self.i)` and also `P2 = np.mean(v2 * i)`; in the lossless model P = P2.
**Level 3 - Research:** The formula is proportional to 1/L and to the product V1 V2'; the firmware
inverts it per period, so an error in L shows up as a steady-state gain error that the PI removes but
that corrupts every open-loop quantity (ZVS maps, current limits). The twin's E1 study demonstrates
that the inversion can be corrected online.

**Example from our converter:** `[Simulated]` Cross-check at 800/400 V, 6.6 kW: P = 6595 W numerical
vs 6600 W closed form, I0 = I1 = 9.65 A vs 9.57-9.63 A (`03_Mathematical_Models/dab_mathematical_model.md`,
section 2, "grid resolution"). Re-running `DABPoint(800, 400, 2, 64e-6, 1e5, 0.4916).P` with the current
code gives 6585 W (0.2 %). P_max numerical 12.51 kW vs 12.50 kW closed form.

**Engineering calculations:** dP/dphi = V1 V2' (pi - 2 phi) / (2 pi^2 fs L): 13.4 kW/rad at nominal
(phi = 0.4916), zero at pi/2; the control gain therefore falls with load, from 16.4 kW/rad at phi = 0 to
zero at the maximum, and would be negative beyond - the reason for the 60 deg cap.

**Design decision made in this project:** `[Implemented]` The numerical engine is the reference for
every modulation; the closed form is retained for the firmware inverse (`phi_from_power` in
`dabtools/dab/control.py`) and as a regression test of the engine (< 0.1 % at the SPS special case,
`SiC_6k6_Industrial_DAB/README.md`, directory map row 03).

**Alternatives considered:** Fundamental-harmonic model P = (8 / pi^2) V1 V2' sin(phi) / (omega L)
(simpler, 5-10 % error at large phi, used for the CLLLC comparison).

**How to verify it:** `python3 21_Human_Friendly_Learning_Notes/img/fig_ch05_model.py` prints the
maximum error; `03_Mathematical_Models/dab_mathematical_model.md` section 2 states the design-point
numbers. `[Simulated]`

**Common mistakes:** Using |phi| > pi/2 (same power, much higher current, negative gain); confusing
P (port-1 average) with P2 (port-2 average), equal only without losses; comparing the closed form with
the plant that includes R_s.

**Interview explanation (30 s):** Averaging v1 times the zig-zag current over a period gives
V1 V2' phi (pi - phi) over 2 pi^2 f L. Our numerical engine, which just sums the current step by step,
reproduces this to 0.1-0.2 % at the design point and within 0.8 % over the whole phase range; the small
deviation is the 0.09 deg grid.

**Research-level explanation:** The agreement of the closed form with the engine is a code
verification, not a model validation; validation against the switched plant with losses (0.3 Ohm) and
against hardware is a separate step with its own error budget (the 50 % load case shows a 12 % peak
current gap to the lossy plant, chapter 04).

### ZVS criterion and charge-based dead time
**What is it?** A leg switches softly when the inductor energy at the edge is at least the energy
needed to charge one device's output capacitance and discharge the other's: 0.5 L I_sw^2 >= Coss,er V^2
(+ 0.5 C_par V^2), hence I_min = sqrt(2 E / L) (8). The dead time must let the current move the charge
of both devices: t_dead >= 2 Qoss(V) / I_sw (9).

**Why do we need it?** (8) gives the ZVS maps and the hard-switching penalty of the loss model;
(9) gives the dead time and its light-load limit.

**How does it work?**
**Level 1 - Beginner:** The inductor is a flywheel, the two device capacitors are two buckets to be
filled and emptied; the flywheel must have enough energy to do it (criterion 8) and enough time to do
it at its current rate (criterion 9).
**Level 2 - Engineering:** `zvs_current_min(Coss_er, Vdc, L, C_par)` returns sqrt(2 (Coss,er V^2 +
0.5 C_par V^2) / L): 2.0 A for the HV bridge (170 pF, 800 V, 64 uH, 60 pF) and 3.07 A for the LV bridge
(350 pF, 400 V, L/n^2 = 16 uH on the LV side, referred back through n) (`04_Design_Calculations/design_values.json` ->
`nominal.Imin1`, `nominal.Imin2`). `dead_time_required(Qoss, I_sw)` returns max(50 ns, 2 Qoss / I_sw):
41 ns -> 50 ns at 9.75 A, 200 ns at 2.0 A. The two criteria are evaluated per edge by
`DABPoint.zvs_margin(port, I_min)` = min over edges of (i_edge - I_min).
**Level 3 - Research:** (8) is conservative against the exact charge-based condition (Everts et al.
2014, [14]), because the current changes during the transition; (8) and (9) disagree at light load,
where the energy is just sufficient but the time is not (chapter 03, worked example 2). Coss,er depends
on the voltage swing non-linearly; the uncertainty module propagates a Coss tolerance into the ZVS
boundary, and the twin's observability study shows Coss cannot be identified from the board's
sensors - the transition time t_tr = 2 Coss,er V / |I_edge| would be the direct measurement (E3).

**Example from our converter:** `[Simulated]` ZVS margins at the nine full-power corners
(`04_Design_Calculations/design_report.md`, section 2): HV from 0.7 A (650/450 V) to 17.3 A (850/300 V),
LV from 3.0 A (850/300 V) to 16.9 A (650/450 V); all positive at full power, so the hard-switching line
of the loss budget is 0.0 W at every corner at 6.6 kW.

**Engineering calculations:** Energy balance at the HV ZVS limit: 0.5 x 64e-6 x 2.0^2 = 128 uJ =
170e-12 x 800^2 + 0.5 x 60e-12 x 800^2 = 109 + 19 uJ. LV bridge in LV-side quantities: L/n^2 = 16 uH,
I_min,LV = sqrt(2 x 350e-12 x 400^2 / 16e-6) = 2.65 A on the LV side = 1.32 A referred to the HV side
without C_par; the design script's 3.07 A includes the parasitic-capacitance term for that bridge.

**Design decision made in this project:** `[Implemented]` Energy criterion for all maps and the loss
model (conservative); fixed 150 ns dead time; `[Proposed]` charge-based adaptive dead time and the
transition-time sensor.

**Alternatives considered:** Exact charge-based ZVS condition with Coss(v) curves (needs the
datasheet curve, which is not archived); ideal ZVS conditions (6)-(7) (energy-free, too optimistic by
2-3 A).

**How to verify it:** `zvs_current_min()` and `dead_time_required()` are two-line functions; the
ngspice model with Coss confirms the ZVS edges (`05_Simulation/gen_spice.py`); hardware: drain-voltage
waveform at turn-on. `[Simulated]`, `[Not yet tested]`

**Common mistakes:** Using Coss at V instead of Coss,er; forgetting the factor two in 2 Qoss (two
devices per leg); applying I_min referred to the wrong side.

**Interview explanation (30 s):** ZVS needs 0.5 L I^2 of inductor energy to exceed Coss,er V^2 of
capacitor energy - 2 A on our HV bridge - and a dead time of at least 2 Qoss / I - 41 ns at full load
but 200 ns at the limit, longer than our 150 ns. The energy test sets the maps; the charge test says
where the maps are optimistic.

**Research-level explanation:** The ZVS boundary is a constraint whose location depends on Coss(v),
L and C_par; only L is identifiable from the ports, so a research-grade adaptive ZVS law needs either a
conservative margin (the supervisor uses 1 A) or a transition-time sensor - the central conclusion of
the observability study.

### RMS current, backflow power and the loss model
**What is it?** The rms current of the trapezoid, I_rms = sqrt(mean(i^2)); the backflow (circulating)
power Q_back = -<min(v1 i, 0)> and its time fraction; and the loss model that turns these into watts:
conduction I_dev,rms^2 Rds(Tj), ZVS turn-off Eoff(V, I) fs k_zvs, hard switching (Eon + Eoff + Coss,er V^2)
fs, dead-time diode Vsd I t_dead fs x 0.5, gate Qg (Vgs,on - Vgs,off) fs; magnetics by Steinmetz / iGSE and
Dowell; capacitors I_rms^2 ESR (`03_Mathematical_Models/dab_mathematical_model.md`, sections 3 and 6).

**Why do we need it?** The efficiency, the thermal design and the modulation optimisation all run on
these quantities.

**How does it work?**
**Level 1 - Beginner:** The heating value of the zig-zag (rms) and the fraction of each cycle in which
energy flows the wrong way (backflow) are the two numbers that say how "wasteful" an operating point
is; the loss model multiplies them by the component properties.
**Level 2 - Engineering:** For the SPS trapezoid the rms can be written in closed form by integrating
the two linear segments; the engine takes sqrt(mean(i^2)) on the grid (`DABPoint.I_rms1`), 9.23 A at
nominal, and I_rms2 = n I_rms1 = 18.46 A. Device rms = I_rms / sqrt(2) because each device conducts half
the period. Backflow at nominal: 301.6 W (`04_Design_Calculations/design_values.json` -> `nominal.backflow`), and the period
fraction with negative port-1 power is 7.8 % (`DABPoint.backflow`). Loss lines at nominal: HV bridge
6.1 + 2.8 + 0 + 0.9 W, LV bridge 12.5 + 2.0 + 0 + 1.2 W, gate 2.0 W, transformer 18.8 W, inductor 7.0 W,
capacitors 0.4 W, auxiliary 12 W, PCB copper 26.4 W (estimate): 92.2 W, 98.62 %
(`04_Design_Calculations/design_report.md`, section 4). Rds is interpolated between 25 and 150 C and
iterated with the thermal model.
**Level 3 - Research:** The loss model's structure follows Krismer and Kolar 2010 ([6]); its weakest
assumptions are k_zvs = 0.35 (share of the double-pulse Eoff that is really dissipated under ZVS), the
iGSE multiplier for triangular flux and the PCB copper estimate. These are the quantities the
uncertainty-quantification module varies; the health-monitoring module asks whether the conduction-loss
residual can reveal Rds(on) drift.

**Example from our converter:** `[Simulated]` Backflow and rms over the voltage window with L =
67.3 uH (`02_Topology_Comparison/topology_comparison.json`): I_rms HV 8.4-14.3 A, backflow 28-1464 W;
with TPS at the corners (`04_Design_Calculations/design_report.md`, section 3) the backflow at 850/300 V falls from 1417 W to
225 W at nearly unchanged rms (12.2 -> 12.1 A), showing that backflow and rms are related but not
identical objectives.

**Engineering calculations:** Why rms and backflow differ: rms counts I^2 over the whole period;
backflow counts energy in the interval after each bridge-1 edge before the current reverses (theta_zc =
14.1 deg at nominal, i.e. 2 x 14.1 / 360 = 7.8 % of the period). Reducing the circulating interval
lowers backflow directly; it lowers rms only if the peak also drops.

**Design decision made in this project:** `[Implemented]` Numerical rms and backflow for every
modulation; `tps_search()` minimises rms subject to ZVS (not backflow), because conduction loss is
I^2 R; loss model with explicit assumptions flagged in the docstrings.

**Alternatives considered:** Closed-form rms for SPS only (implemented implicitly as a check);
minimising backflow (DPS literature, Bai and Mi 2008) - gives worse ZVS margin in the project's table.

**How to verify it:** `04_Design_Calculations/dab_design.py` produces the budget; the UQ module
(`Advanced_Research_2026/Uncertainty_Quantification/README.md`) its spread; calorimetry on hardware.
`[Simulated]`, `[Not yet tested]`

**Common mistakes:** Treating backflow power as a loss in watts (it is circulating power; the loss is
the extra I^2 R); forgetting that device rms is bridge rms / sqrt(2); using Rds at 25 C.

**Interview explanation (30 s):** The rms of the current zig-zag heats the copper and the silicon; the
backflow is the share of each period in which energy flows backwards - 7.8 % and 300 W at our nominal
point, 1.4 kW at the worst corner. The loss model multiplies rms^2 by resistances, edge currents by
switching energies and adds magnetics: 92 W, 98.6 % calculated.

**Research-level explanation:** rms and backflow are two of several possible objectives (others:
peak current, ZVS margin, total loss with temperature feedback); the minimum-rms-with-ZVS problem has a
closed form for SPS/TPS but the project solves it numerically so that the same code can be run on an
estimated L inside the twin.

## The model used for control

### Averaged (period) model, small-signal model and the one-period delay
**What is it?** For control bandwidths far below fs the DAB is a current source into the LV link
controlled by phi: I2(phi) = P / V2 = n V1 phi (pi - phi) / (2 pi^2 fs L) (10); its small-signal gain is
K_phi = dI2/dphi = n V1 (pi - 2 phi) / (2 pi^2 fs L) (11); with the link capacitance C2 and a load R the
plant is G(s) = V2(s) / phi(s) = K_phi R / (1 + s R C2) (12), multiplied by the digital delay e^{-s T_d}
with T_d ~ 1.5 Ts (sample, compute, update at the next period) (`03_Mathematical_Models/dab_mathematical_model.md`,
section 7).

**Why do we need it?** The PI controller, the feedforward and the stability margins are designed on
this model; the switched simulation then validates it.

**How does it work?**
**Level 1 - Beginner:** Seen slowly (hundreds of times slower than the switching), the converter is
just a tap that pours current into the output capacitor; the phase shift opens the tap. The controller
measures the level once per cycle and adjusts the tap for the next cycle - one cycle late.
**Level 2 - Engineering:** At nominal, I2 = 16.5 A at phi = 0.4916 rad; evaluating (11) gives K_phi =
2 x 800 x (3.1416 - 0.9832) / (2 x 9.8696 x 1e5 x 64e-6) = 27.3 A/rad; over the voltage range
`11_Control_Algorithms/control_design.md` reports 26.6-36.6 A/rad, a +/-15 % variation that the design
removes by letting the PI output a power command and inverting (10) in the modulator (`phi_from_power`),
so the loop sees a constant gain. Plant pole: 1 / (2 pi R C2) with R = 400^2 / 6600 = 24.2 Ohm and C2 =
1.12 mF (120 uF on board + 1 mF external) = 5.9 Hz ("6 Hz"). PI: kp = 1689 W/V, ki = 1.27e6 W/(V s), zero at
120 Hz, crossover 612 Hz, phase margin 76 deg, gain margin infinite, T_d = 15 us; the delay costs 360 x
612 x 15e-6 = 3.3 deg of phase at crossover (`11_Control_Algorithms/control_params.json`,
`11_Control_Algorithms/img/loop_bode.png`). Figure `img/ch05_averaged_gain.png` plots (10) and (11).
**Level 3 - Research:** The averaged model loses everything inside the period (ZVS, peak current),
so constraints must be handled outside the loop (limiter, maps); an MPC on the same averaged model with
a disturbance observer gives 0.1 V instead of 1.5 V of dip on a 50 % step (`11_Control_Algorithms/control_design.md`,
section 4) but depends on C2, the delay and a load estimate. The twin's EKF uses the same discrete model
v2(k+1) = v2(k) + Ts / C2 (g theta - i_load) with theta = 1/L as a state (`Advanced_Research_2026/Digital_Twin/twin.py`,
`EKF_L`).

**Example from our converter:** `[Simulated]` Validation of (12) by the switched simulation: 50 % load
step -> 0.37 % dip (EL-10 allows 3 %), start-up overshoot 0.38 %, 10 % HV dip -> 0.03 % V2 deviation
(`05_Simulation/switched_results.json`). The controller runs once per period and sets the phase for
the next one (`dabtools/dab/sim_switched.py` docstring: "one-period delay").

**Engineering calculations:** Crossover check: open-loop gain at fc for a power-command loop is
kp x (1 / (s C2)) in the region above the plant pole: 1689 / (2 pi x 612 x 1.12e-3) = 0.39... the design
script includes the integral term and the exact plant; the point is that fc = fs / 167 keeps the
delay's phase lag at 3 deg and the quantisation negligible (10 ns ePWM steps, 12-bit ADC = 0.25 V on
850 V).

**Design decision made in this project:** `[Implemented]` Power-command PI with modulator inverse
and feedforward phi_ff = f^-1(P_ref, V1, V2); clamping anti-windup; output limits +/-1.1 P_rated, slew
2 kW/ms; crossover ~600 Hz (`11_Control_Algorithms/control_params.json`). MPC documented as a research option, not baseline.

**Alternatives considered:** Direct phi PI (gain varies with V1 and phi); higher crossover (delay
phase and ripple sensitivity); explicit MPC (implemented in `11_Control_Algorithms/control_design.py`,
30 multiply-adds, but parameter dependent).

**How to verify it:** `11_Control_Algorithms/control_design.py` (Bode, margins);
`05_Simulation/run_switched_sim.py` (closed-loop steps); `10_Firmware/` SIL harness (35 checks) runs the
C implementation of the same loop. `[Simulated]`, `[Verified]` SIL.

**Common mistakes:** Designing the loop on K_phi at one operating point without the inverse (gain
error +/-15 %); forgetting the external bus capacitance in C2; ignoring the 1.5 Ts delay (harmless at
600 Hz, fatal at 10 kHz).

**Interview explanation (30 s):** Averaged over a period the DAB is a current source of
n V1 phi (pi - phi) / (2 pi^2 f L) into the output capacitor; the PI sees a single pole at 6 Hz, a 15 us
delay and, thanks to the modulator inverse, a constant gain. We close the loop at 612 Hz with 76 deg of
phase margin and the switched simulation confirms 0.4 % dips on 50 % steps.

**Research-level explanation:** The averaged model is exact for the mean of the lossless switched
model and is the physics prior of the twin; its parameters (L through g, C2) are the first targets of
online identification, and its omission of intra-period constraints is why the research control
modules pair an MPC with ZVS maps rather than relying on the loop alone.

### The 2026 digital-twin regressor and the observability result
**What is it?** For a fixed switching pattern (s1, s2 arrays of +/-1/0 over one period, as the PWM
registers define them) the lossless model gives every current as a known function of the pattern and
the voltages divided by L: I2_avg = g(phi, D1, D2, V1, V2) x (1/L). Measuring I2_avg and computing g
from the applied pattern makes 1/L a scalar linear regression (`Advanced_Research_2026/Digital_Twin/twin.py`,
`regressor_I2`, `discrete_model`). The observability study (`Advanced_Research_2026/Digital_Twin/observability.py`)
computes the Fisher information of p = [L, Coss,er1, Coss,er2, R_s] for each sensor set.

**Why do we need it?** The inductance has a +/-5 % tolerance (gap) and drifts with temperature and
bias; an online estimate corrects the modulator inverse, the ZVS maps and the current limits. The
observability result says which of these corrections are possible with the existing board.

**How does it work?**
**Level 1 - Beginner:** If you know the pattern of pushes and the voltages, the only unknown in how
much current results is the coil; so from the measured current you can work out the coil - but only
the coil: the tiny capacitors in the switches leave no trace in the averaged current, so no amount of
averaging will reveal them.
**Level 2 - Engineering:** `discrete_model` builds di = (s1 V1 - s2 n V2) / L dt, cumulates it, removes
the mean and returns i2_avg = mean(i s2 n) and the HV edge current; with L = 1 H the result is g, and
I2 = g / L. Figure `img/ch05_regressor_1_over_L.png` shows I2 against 1/L for three patterns: straight
lines through the origin, as the model asserts. The full-load regressor is g = I2 L = 16.5 A x 64 uH =
1.06e-3 A H; the RLS gates updates when |g| < 2.5e-4 A H (about 25 % load) because at light load the
information per sample is small and the lossless-regressor bias (R_s = 0.3 Ohm is not in g) dominates
(`Advanced_Research_2026/Digital_Twin/twin.py`, `RLS`). Estimators: RLS with forgetting 0.995, EKF with joint state [v2, i_load, 1/L],
sequential grid Bayes as reference, and a Coss estimator for a proposed transition-time sensor
(t_tr = 2 Coss,er V / |I_edge|).
**Level 3 - Research:** Results on simulated data (`Advanced_Research_2026/Digital_Twin/README.md`,
section 2; `results/twin_study.json`): E1 - true L = 0.8 L_nom then +15 % drift: RLS and EKF converge
within the first logged sample (< 0.1 ms) and track to 0.24 % / 0.25 % final error, RLS 1-sigma 0.86 %;
the grid Bayes assumes a constant parameter and fails on the drift (-11.2 %). E2 - steady state at 100 /
30 / 10 % load with L = 0.9 L_nom: bias +0.6 / -0.9 / -0.5 % from the neglected R_s; gating holds the
estimate at 10 % load (141 of 4000 updates). E3 - Coss,er = 1.2 x datasheet with a synthetic 5 ns rms
transition-time sensor: +4.5 % error with the estimated L, -11.6 % with the nominal L (the Coss
estimate inherits the L error). Observability (`results/observability.json`, 36 operating points,
sensor noise 1-sigma: I2_avg 0.085 A, I1_avg 0.082 A, I_pk 0.3 A, t_tr 5 ns): with the LV shunt only,
rank 2, Cramer-Rao relative std after 1000 periods L 0.03 %, R_s 8 %, Coss not identifiable
(information exactly zero); adding the HV CT and the peak detector keeps rank 2 (R_s improves to
0.7 %); the proposed HV transition-time sensor raises the rank to 3 (Coss,er1 0.03 %, R_s 0.06 %); both
transition-time sensors give rank 4 with condition number 49.

**Example from our converter:** `[Simulated]` The twin found a defect in the switched plant: a one-cell
asymmetry between the positive and negative pulses created a DC volt-second and, through R_s, a 13 A DC
inductor current whenever D < 1; the fix (negative pulse = positive pulse rolled by N_sub/2) moved the
headline simulation results by < 0.3 V / < 0.1 % (`Advanced_Research_2026/Digital_Twin/README.md`, section 2). The supervisory
study on the estimated L (`results/supervisory_study.json`) reduced rms by 2.3 % on average and
hard-switched edges from 61 to 56 over 27 points; the nominal-parameter model under-predicted rms by
10.5 % on average (22.6 % max) when L was 20 % low.

**Engineering calculations:** Information per period from the shunt alone: with sigma = 0.085 A and
g = 1.06e-3 A H, the Cramer-Rao bound on 1/L per sample is sigma / g = 80 H^-1 against 1/L = 15 625 H^-1,
i.e. 0.5 %; after N = 1000 periods it shrinks by sqrt(1000) to 0.016 %, the same order as the 0.03 % of
the study (which averages over 36 operating points with different g). The light-load regressor at
10 % load is 1.06e-4 A H, below the 2.5e-4 gate.

**Design decision made in this project:** `[Proposed]` The twin runs on a host from 1 kHz telemetry
frames (`Advanced_Research_2026/Digital_Twin/interface.md`), sends advisory (D1, D2) that pass the same
limiter as the fixed schedule and is ignored unless its status is TRUSTED (sigma_L / L <= 5 %, fresh
frame, CRC ok); hardware protections are untouched. `[Simulated]` All results are from the switched
plant with modelled sensors, labelled SIMULATED in `Advanced_Research_2026/Digital_Twin/provenance.json`.

**Alternatives considered:** Lossy regressor (removes the 0.6-0.9 % bias at the cost of knowing
R_s); differentiable-simulator estimation (L28) and uncertainty-aware estimation (L29) as gradient-based
alternatives to RLS/EKF; a firmware RLS (~30 multiply-adds per period,
`Advanced_Research_2026/Embedded_AI/`).

**How to verify it:** `python3 Advanced_Research_2026/Digital_Twin/observability.py` (~10 s),
`run_twin_study.py` (~45 s), `Advanced_Research_2026/Digital_Twin/supervisory.py` (~6 s) regenerate every number and figure
(`results/E1_L_identification.png`, `results/E3_Coss_identification.png`). `[Simulated]`; the deterministic
estimator tests give it L3 maturity for the code, L2 for the results; `[Not yet tested]` on hardware.

**Common mistakes:** Evaluating g on the ideal phase instead of the applied PWM registers (4-7 %
error at small shifts); updating the estimator at light load (bias and spread); claiming Coss
identification without the sensor; forgetting that the estimate's 1-sigma, not its mean, decides
whether the supervisor may act.

**Interview explanation (30 s):** Because the lossless DAB's currents are proportional to 1/L for a
known switching pattern, measuring the average output current gives the inductance by linear
regression: our estimator converges in one sample and tracks a 15 % drift to 0.25 %. The Fisher
information shows the board can identify L and weakly the loss resistance but not the device
capacitances - for those a transition-time sensor is proposed.

**Research-level explanation:** The observability result is the module's main scientific statement:
period-average sensing has zero sensitivity to Coss, so "adaptive ZVS control" claims that rely on
port measurements alone are not identifiable in this plant; the proposal is a drain-voltage
transition-time measurement, whose 5 ns noise figure is assumed, and whose estimate inherits the L
error one-to-one, so the two estimators must run jointly.

## Worked example(s) with real numbers

**Example 1 - deriving I0, P and rms at nominal by hand.** `[Simulated]` V1 = V2' = 800 V, omega L =
628 318 x 64e-6 = 40.21 Ohm, phi = 0.4916 rad. (2): I0 = [800 pi + 800 (0.9832 - pi)] / (2 x 40.21) =
800 x 0.9832 / 80.42 = 9.78 A; (3) gives the same. Zero crossing at theta_zc = phi / 2 = 0.2458 rad.
Power (4): 800 x 800 x 0.4916 x 2.650 / (2 x 9.8696 x 1e5 x 64e-6) = 833 900 / 126.3 = 6602 W. rms of the
trapezoid: segments of length phi (linear from -9.78 to +9.78) and pi - phi (constant 9.78); mean square
= [phi x 9.78^2 / 3 + (pi - phi) x 9.78^2] / pi = 9.78^2 x (0.1639 + 2.650) / 3.1416 = 95.6 x 0.8957 = 85.6
A^2; rms = 9.25 A - the engine says 9.23 A (`04_Design_Calculations/design_values.json` -> `nominal.Irms1`). Device rms 6.54 A;
conduction 4 x 6.54^2 x 35.9 mOhm = 6.1 W.

**Example 2 - ZVS energy and dead time at half load.** `[Simulated]` At 3.3 kW, phi = 12.8 deg =
0.2232 rad, I0 = 800 x 0.2232 / 40.21 = 4.44 A (engine 4.44 A; closed-loop plant 4.96 A). Energy 0.5 x
64e-6 x 4.44^2 = 631 uJ against 128 uJ required: margin factor 4.9 in energy, 2.4 A in current. Charge
time 2 x 200 nC / 4.44 A = 90 ns, inside the 150 ns dead time. At 23 % load (I0 = 2.0 A) the energy is just
sufficient and the charge time is 200 ns: the maps say ZVS, the dead time says partial hard switching.

**Example 3 - loop gain and the delay.** `[Simulated]` C2 = 1.12 mF, R = 24.2 Ohm at full load: pole
5.9 Hz. Power-command loop: the plant from power to V2 is 1 / (V2 C2 s) above the pole (a 16.5 A current
source per 6.6 kW); crossover 612 Hz with kp = 1689 W/V and the PI zero at 120 Hz; delay phase 3.3 deg;
phase margin 76 deg (`11_Control_Algorithms/control_params.json`). The switched simulation's 0.37 % dip for a 50 % step
(3.3 kW into 1.12 mF at 612 Hz: dI / (2 pi fc C2) = 8.25 / (3846 x 1.12e-3) = 1.9 V = 0.5 % as a
back-of-envelope estimate) agrees.

**Example 4 - one RLS update.** `[Simulated]` Pattern at nominal: g = 1.056e-3 A H (16.5 A x 64 uH).
Suppose the true L is 0.8 x 64 = 51.2 uH: the measured I2 is 16.5 / 0.8 = 20.6 A. Starting from theta =
1/64e-6 = 15 625 H^-1 with a large P0, the first RLS step moves theta to y / g = 20.6 / 1.056e-3 = 19 530
H^-1, i.e. L = 51.2 uH, in one update - which is why E1 reports convergence "within the first logged
sample"; subsequent samples only average the 0.085 A noise and the 0.6-0.9 % R_s bias.

## How this chapter connects to the files

| File | What it contains | Status |
|---|---|---|
| `SiC_6k6_Industrial_DAB/03_Mathematical_Models/dab_mathematical_model.md` | derivations (1)-(12), loss model structure, DC-link ripple | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/dabtools/dab/dab_model.py` | numerical engine and closed forms; zvs_current_min, dead_time_required, tps_search | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/dabtools/dab/losses.py` | semiconductor loss model with k_zvs = 0.35 | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/dabtools/dab/control.py` | PI, modulator inverse (phi_from_power), one-period structure | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/dabtools/dab/sim_switched.py` | switched plant (R_s = 0.3 Ohm, one-period delay, pattern fix) | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/04_Design_Calculations/design_values.json` | nominal I0/I1, rms, backflow, Imin, margins, losses | `[Simulated]` |
| `SiC_6k6_Industrial_DAB/11_Control_Algorithms/control_design.md` | averaged-model PI design, K_phi range, MPC alternative | `[Simulated]` |
| `SiC_6k6_Industrial_DAB/11_Control_Algorithms/control_params.json` | kp, ki, fc, pm, Td, C2 | `[Implemented]` |
| `SiC_6k6_Industrial_DAB/05_Simulation/switched_results.json` | closed-loop validation of the averaged model | `[Simulated]` |
| `Advanced_Research_2026/Digital_Twin/README.md` | twin layers, observability table, E1-E4, supervisor, defect report | `[Simulated]` |
| `Advanced_Research_2026/Digital_Twin/twin.py` | regressor, RLS, EKF, Bayes grid, Coss estimator, thermal twin | `[Implemented]` |
| `Advanced_Research_2026/Digital_Twin/observability.py` | Fisher information / Cramer-Rao study | `[Implemented]` |
| `Advanced_Research_2026/Digital_Twin/results/observability.json` | ranks, eigenvalues, CRLB per sensor set | `[Simulated]` |
| `Advanced_Research_2026/Digital_Twin/results/twin_study.json` | E1-E4 numbers | `[Simulated]` |
| `Advanced_Research_2026/Digital_Twin/interface.md` | telemetry frame and advisory command interface | `[Proposed]` |
| `21_Human_Friendly_Learning_Notes/img/fig_ch05_model.py` | closed-form vs numeric, K_phi, 1/L regressor figures | `[Implemented]` |

## Viva / interview questions

### Basic (10)
1. What single equation describes the DAB power stage?
   L di/dt = v1(t) - v2'(t): the series inductor driven by the difference of the two bridge voltages
   (referred to one side).
2. Why is the inductor current piecewise linear?
   Because the bridge voltages are constant between edges, so di/dt is constant on each segment.
3. What are I0 and I1?
   The current magnitudes at the HV-bridge edge and the LV-bridge edge; 9.8 A each at nominal.
4. State the SPS power equation.
   P = V1 V2' phi (pi - |phi|) / (2 pi^2 fs L); 6.6 kW at phi = 28.2 deg with L = 64 uH at 800/400 V.
5. What is the ZVS energy criterion?
   0.5 L I^2 >= Coss,er V^2 (+ 0.5 C_par V^2), so I >= sqrt(2 E / L); 2.0 A on the HV bridge.
6. What is the charge-based dead time?
   t_dead >= 2 Qoss / I_sw; 41 ns at 9.75 A, 200 ns at 2 A, versus the 150 ns used.
7. How does the numerical engine compute the power?
   It builds v1, v2' and i on a 4000-point grid, cumulates (v1 - v2') / (omega L), removes the mean and
   takes mean(v1 i).
8. What is the averaged model?
   I2 = n V1 phi (pi - phi) / (2 pi^2 fs L): a phi-controlled current source into the LV capacitor,
   valid for control bandwidths far below fs.
9. What is the one-period delay?
   The controller measures in period k and applies the phase in period k+1: T_d ~ 1.5 Ts = 15 us.
10. What does "every current scales with 1/L" mean for the twin?
    For a fixed switching pattern the lossless currents are proportional to 1/L, so 1/L can be found
    by linear regression from the measured average current.

### Intermediate (10)
1. Derive I0 from the two slopes and half-wave symmetry.
   i(phi) = -I0 + (V1 + V2') phi / (omega L); i(pi) = i(phi) + (V1 - V2')(pi - phi) / (omega L) = +I0;
   solving, I0 = [V1 pi + V2' (2 phi - pi)] / (2 omega L).
2. Show that P = <v1 i> gives equation (4) at d = 1.
   With I0 = I1 = V1 phi / (omega L), the trapezoid's mean over the half period is I0 (1 - phi / (2 pi))
   ... = V1 phi (pi - phi) / (pi omega L) ... times V1 and omega = 2 pi fs gives V1^2 phi (pi - phi) /
   (2 pi^2 fs L).
3. How good is the numerical cross-check and where is it worst?
   < 0.2 % at the design point, < 0.8 % for phi >= 5 deg, 5.7 % below 5 deg where the 0.09 deg grid
   quantises the edge position; the model document quotes 6595 vs 6600 W.
4. Compute I_min for the LV bridge in LV-side quantities.
   L/n^2 = 16 uH, Coss,er = 350 pF, V = 400 V: sqrt(2 x 350e-12 x 1.6e5 / 16e-6) = 2.65 A on the LV side;
   the design script adds the parasitic term and reports 3.07 A referred to the HV side.
5. What is the difference between rms and backflow as objectives?
   rms counts I^2 over the period (conduction loss); backflow counts the energy returned during the
   circulating interval; TPS at 850/300 V cuts backflow 1417 -> 225 W while rms barely moves.
6. Compute K_phi at nominal and explain why the loop does not see it.
   K_phi = n V1 (pi - 2 phi) / (2 pi^2 fs L) = 27.3 A/rad; the PI outputs a power command and the
   modulator inverts (10), so the loop gain is constant over V1 and phi (26.6-36.6 A/rad otherwise).
7. Where does the 6 Hz plant pole come from?
   1 / (2 pi R C2) with R = V2^2 / P = 24.2 Ohm and C2 = 1.12 mF (120 uF on board + 1 mF bus).
8. How much phase does the 15 us delay cost at crossover?
   360 x 612 Hz x 15e-6 s = 3.3 deg; the 76 deg phase margin is therefore set by the PI zero, not the
   delay.
9. Why does the RLS gate updates at light load?
   The regressor g shrinks with load (1.06e-3 A H at full load, 1.06e-4 at 10 %), so noise and the
   R_s bias dominate; below 2.5e-4 A H the estimate is held (141 of 4000 updates at 10 % load).
10. Why does the Coss estimate depend on the L estimate?
    t_tr = 2 Coss,er V / |I_edge| and I_edge comes from the model with the estimated L: E3 shows +4.5 %
    error with the estimated L and -11.6 % with the nominal L.

### Advanced / research (10)
1. Why does the energy criterion disagree with the charge criterion at light load?
   The energy test is met at 2.0 A, but moving 2 Qoss = 400 nC at 2 A takes 200 ns > 150 ns dead time;
   the exact condition (Everts 2014) tracks the current during the transition and lies between them.
2. State the observability result and its consequence.
   With the board's sensors the Fisher information of [L, Coss1, Coss2, R_s] has rank 2: L to 0.03 %,
   R_s to 0.7-8 %, Coss information exactly zero; an adaptive-ZVS law needs a transition-time sensor
   (rank 3 with one, rank 4 with two).
3. How does the averaged model relate to the EKF of the twin?
   The EKF propagates v2(k+1) = v2(k) + Ts / C2 (g theta - i_load) with theta = 1/L and i_load as random
   walks - the discrete form of (10)-(12) with the regressor replacing the closed-form current.
4. What is the bias of the lossless regressor and how could it be removed?
   R_s = 0.3 Ohm is not in g, giving +0.6 / -0.9 / -0.5 % bias at 100 / 30 / 10 % load; the lossy
   discrete model (`discrete_model_lossy`) with the geometric-series steady state would remove it at
   the cost of knowing R_s, which is itself only weakly observable.
5. Why does the sequential grid Bayes fail in E1?
   It assumes a constant parameter; its posterior collapses on the initial 0.8 L_nom and cannot follow
   the +15 % drift (-11.2 % final error, zero credible width) - a reference, not a tracker.
6. Discuss the plant defect found by the twin and what it teaches about models.
   Two independent floating-point comparisons generated pulses that could differ by one cell, injecting
   a DC volt-second per period; through R_s this became a 13 A DC current. A model with an exact
   symmetry (zero mean current) exposed a numerical artefact of the plant - models can validate
   simulators as well as the reverse.
7. How would you extend the derivations to EPS/DPS/TPS analytically, and would it be worth it?
   Region-wise piecewise integration over up to five segments per half period; closed forms exist
   (Krismer-Kolar 2012 for the optimum) but the numerical engine already reproduces the SPS case to
   < 0.1 % and runs inside the twin on an estimated L, so the analytical forms add insight, not
   capability.
8. What is the Cramer-Rao bound and what did it give here?
   The minimum variance of any unbiased estimator, the inverse of the Fisher information; after 1000
   periods L is bounded at 0.03 % with the shunt alone, R_s at 8 % (0.7 % with the peak detector), Coss
   unbounded (zero information).
9. What would a hardware validation of the twin's L estimate look like?
   Run the converter at reduced voltage with a known inductor swap (e.g. 51 vs 64 uH), log the telemetry
   frames of `interface.md`, and compare the RLS estimate with an impedance-analyser measurement at
   the operating current and temperature; the expected bias is the 0.6-0.9 % of E2 plus sensor gain
   errors.
10. Where does the differentiable-simulation approach (L28) fit relative to RLS/EKF?
    It optimises parameters by gradients through a simulator and can handle non-linear parameters
    (Coss(v)) in principle, but it inherits the same observability limits: with zero sensitivity in the
    measurements, no estimator - gradient or recursive - can identify Coss from port averages.

## Pitches

**30 s:** The DAB model is one inductor equation with square-wave inputs; integrating it gives the edge
currents, the power V1 V2' phi (pi - phi) / (2 pi^2 f L), the ZVS criterion and the rms current in closed
form, which our numerical engine reproduces to 0.2 %. Averaged over a period the converter is a
current source, so the control loop is a first-order design with a 15 us delay. The same structure makes
the inductance identifiable online - and shows that the device capacitances are not.

**2 min:** Start from L di/dt = v1 - v2'. With single phase shift the current is a trapezoid; half-wave
symmetry fixes its two edge currents I0 = [V1 pi + V2' (2 phi - pi)] / (2 omega L) and I1 = [V1 (2 phi - pi) +
V2' pi] / (2 omega L), both 9.8 A at our nominal point. Averaging v1 i gives the power equation,
6.6 kW at 28.2 deg with L = 64 uH; our numerical engine, which just sums the current on a 4000-point grid,
matches it to 0.2 % and extends to EPS, DPS and TPS without new algebra. ZVS needs 0.5 L I^2 >= Coss,er V^2,
i.e. 2.0 A on the HV bridge and 3.1 A on the LV bridge, and a dead time of 2 Qoss / I - 41 ns at full
load but 200 ns at the limit, which is where our fixed 150 ns is optimistic. The rms (9.23 A) and the
backflow (300 W, 7.8 % of the period) feed a loss model whose weakest links are the ZVS share of Eoff
and the copper estimate. For control, the period-average model is a current source
n V1 phi (pi - phi) / (2 pi^2 f L) into 1.12 mF with a 6 Hz pole and a 15 us delay; the PI closes at
612 Hz with 76 deg margin and the switched simulation shows 0.4 % dips. Finally, because every lossless
current is proportional to 1/L, the 2026 twin estimates 1/L by recursive least squares in one sample and
tracks drift to 0.25 %, while a Fisher-information analysis proves that the board's sensors carry no
information about Coss - the honest limit of adaptive ZVS control without a new sensor.

**10 min outline:**
* Equation (1), slopes, half-wave symmetry; derivation of (2)-(3); 9.78 A; corner asymmetry.
* Power (4)-(5) by averaging; cross-check 6595/6600 W, figure `img/ch05_closed_vs_numeric.png`; grid
  quantisation at small phi; dP/dphi and the 60 deg cap.
* ZVS energy (8) and charge (9): 2.0 / 3.07 A, 41-200 ns; conservative vs exact; C_par.
* rms by hand (9.25 vs 9.23 A), backflow 7.8 % / 302 W, loss model structure and its assumptions.
* Averaged model (10)-(12): K_phi 27.3 A/rad, modulator inverse, 6 Hz pole, 612 Hz / 76 deg, 15 us delay,
  figure `img/ch05_averaged_gain.png`; validation by the switched simulation; MPC alternative.
* Twin regressor: I2 = g / L, figure `img/ch05_regressor_1_over_L.png`; RLS/EKF/Bayes; E1-E3 numbers;
  gating; plant defect.
* Observability: Fisher rank 2 -> 3 -> 4; CRLB 0.03 % for L; Coss zero information; sensor proposal.
* Status: `[Implemented]` code, `[Simulated]` results, `[Proposed]` sensor; nothing measured.

## Further reading

* `SiC_6k6_Industrial_DAB/01_Literature_Review/literature_review.md` [2] Kheraluwala et al. 1992
  (SPS derivation), [6] [7] [8] [9] Krismer and Kolar (loss model, optimisation, closed-form TPS, thesis),
  [11] Zhao et al. 2012 (DPS power characterisation), [14] Everts et al. 2014 (charge-based ZVS).
* `Advanced_Research_2026/Literature_Database/literature_2022_2026.csv` L03 (digital-twin models for
  the DAB, closest match only - not confirmed as the cited TIM paper), L04 (one-cycle multiparameter
  identification, citation only), L05 (PINN parameter estimation, to verify before claiming novelty),
  L28 and L29 (differentiable and uncertainty-aware estimation, accessible preprints).
* `Advanced_Research_2026/Digital_Twin/README.md` sections 1-3 and 5 ("What was NOT verified").
