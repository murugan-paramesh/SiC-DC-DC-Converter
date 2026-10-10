# Adaptive / predictive control of the 6.6 kW DAB - benchmark on the switched plant

Module of `Advanced_Research_2026` (gap-analysis items 7 and 9, contribution A). Six controllers for the LV-link
voltage (CV) and the transferred power (CP) are implemented and benchmarked on the **same switched plant** as
05_Simulation (`dabtools.dab.sim_switched.DABPlant`: L = 64 uH, n = 2, fs = 100 kHz, C2 = 1.12 mF from
`control_params.json`, C1 = 580 uF, HV source 0.3 Ohm, R_s = 0.3 Ohm, no dead time), one controller update per
switching period with the command applied to the next period, 12-bit ADC quantisation + 0.5 LSB noise on v1, v2 and
the period-average LV current, EPS voltage matching in the inner modulator for all. The plant is integrated with
N_sub = 1000 sub-steps (0.36 deg = the EPWM phase resolution; 05_Simulation uses 200).

**Maturity: L2 (simulation on the project model). WCET numbers are L1 (instruction-count estimates, no C2000
toolchain). Nothing here is hardware-validated.**

## 1. Files

| file | content | run time (one core) |
|---|---|---|
| `dab_mpc_lib.py` | exact piecewise-linear period model `pwl_period` (validated vs `DABPoint`), plant wrapper with period accumulators and the DC-bias-free transition modulator, ADC model, the six controllers, scenarios, metrics, operation counting, provenance helper | library |
| `build_explicit_mpc.py` | pre-computes the CCS-MPC law on a 33 x 9 x 23 grid -> `results/empc_lut.npz` | 7 s |
| `run_benchmarks.py` | 6 controllers x 5 scenarios, step-response figures, metric bar charts, modulator comparison (SPS / EPS / EPS + DC-free), CCS rate-weight sweep, operation counts and C2000 feasibility (`results/benchmark_*`, `results/c2000_feasibility.json`) | 4.5 min |
| `run_adaptive_robust.py` | RLS convergence (L +20 %, -20 %, drifting) and constraint study of CCS / adaptive / robust MPC / PI on plants with L = 0.8, 1.0, 1.2 L_nom at the 650/450 V corner (`results/adaptive_*`) | 2 min |
| `zvs_maps.py` | ZVS maps V1 x V2 x P, forward/reverse, SPS/EPS, tolerance sweep, adaptive dead-time table (`results/zvs_*`) | 6 min |
| `provenance.json` | versions, git commit, input hashes, wall time per script |

Scenario windows were shortened to keep the total under the 15 min limit: 8 ms pre-roll + 12 ms after the event;
the soft start uses a 20 ms ramp instead of the firmware's 50 ms (1 V/ms instead of 0.4 V/ms - harder, not easier).

## 2. Controllers

All MPC variants use the averaged LV-link model `v2[k+1] = v2[k] + a (i2[k] - d[k])`, a = Ts / C2 = 8.9 mV/A, with
`d` (load current + model mismatch) from a two-state Luenberger disturbance observer (double pole at z = 0.9, i.e.
~1.7 kHz) - this gives offset-free tracking without an explicit integrator. The period-average LV current is
`i2 = n V1 phi (pi - |phi|) / (2 pi^2 fs L)` (SPS), affine in phi around the last command:
`i2 ~= i2(phi0) + g (phi - phi0)`, `g = n V1 (pi - 2|phi0|) / (2 pi^2 fs L)`.

| # | controller | law | tuning |
|---|---|---|---|
| 1 | **PI** (baseline) | `dabtools.dab.control.DABController`: PI on v2 -> power command -> SPS inverse (`phi_from_power`) -> EPS matching; CP mode = pure feed-forward (as in `dab_control.c`) | kp = 1689 W/V, ki = 1.27e6 W/(V s) from `control_params.json`; dead-time term of the inverse set to 0 because the plant has no dead time |
| 2 | **CCS-MPC** | `min sum_j q (v2_{j+1} - ref)^2 + r (phi_j - phi_{j-1})^2`, N = 8, box `|phi_j| <= phi_bar(V1, V2, D1, D2, I_lim = 24 A, L)` (phi_max = 60 deg and the steady-state peak-current bound of the actual modulator; SPS closed form, EPS from the piecewise-linear model). Box constraints -> accelerated projected gradient (Nesterov, K = 20 fixed iterations, O(N) per iteration through cumulative sums, warm start) converges to the exact QP optimum. CP mode: same QP on i2 with a filtered measured-current mismatch correction | q = 1, r = 16 (sweep in sec. 3.3) |
| 3 | **FCS-MPC** | 11 candidates delta_phi in {0, +/-1, 3, 10, 30, 100} PWM steps x {SPS, EPS matching} = 22 candidates; each evaluated with the exact period model (`pwl_period`: period-average i2, I_rms, I_pk, edge currents); one-step prediction with the candidate held for H = 10 periods; cost `(v2+ - ref)^2 + 5 dphi^2 + 5e-4 I_rms^2 + 0.05 max(0, -ZVS margin)`, candidates with I_pk > 24 A removed | - |
| 4 | **Explicit MPC** | law of #2 pre-computed on (e = ref - v2 in [-12, 12] V, V1 in [650, 850] V, P_hat = d_hat ref in [-7.26, 7.26] kW), 33 x 9 x 23 nodes, trilinear interpolation; the linearisation point of the stored law is the steady-state feed-forward phi_ff(P_hat, V1) so the table is 3-D (no previous-phi axis) | built for v2_ref = 400 V; interpolation error vs the exact law: max 0.85 deg, rms 0.14 deg (PWM step 0.36 deg); 30 % of the nodes are at the constraint |
| 5 | **Adaptive MPC** | #2 with theta = 1/L from scalar RLS: `y = i2_meas`, `x = L_nom n I2_pwl(L_nom; phi, D1, D2, V1, V2)` (the lossless current scales exactly with 1/L); forgetting 0.995, excitation gate |i2_model| > 1 A, outlier gate (transition periods), bounds [0.6, 2] / L_nom. L_hat feeds the gain and the current bound every period | - |
| 6 | **Robust MPC** | #2 with tube-style tightening for L in [0.8, 1.2] L_nom: current bound evaluated at L_min = 0.8 L_nom (current ~ 1/L) and the largest gain of the set (L_min) so that the move is never larger than the true plant needs | - |

**Inner modulator.** All controllers run with EPS voltage matching (D of the higher-voltage bridge = n V2 / V1,
D_min = 0.12, as in the firmware). In addition a **DC-bias-free transition** was added to the modulator: when the
command changes, the first LV-bridge edge after the period boundary is moved by
`delta = (i_ss,new(0) - i_ss,old(0)) w L / h_edge` so the inductor current lands on the new steady state after one
period (for SPS this is the classical "half the phase step in the first half period"). Without it any fast
controller excites a DC offset in i_L that decays with tau = L / R_s ~ 210 us and that the averaged model does
not see: the CCS-MPC peak current went from 14 A to 19-24 A at 800/400 V and to 30-31 A (26 periods above the
24 A limit) at 850/300 V. The transition modulator is applied to every controller alike (sec. 3.2).

## 3. Benchmark results (`results/benchmark_metrics.csv`, figures `results/benchmark_step_*.png`, `results/benchmark_metrics_bars.png`)

Settling = time after the event (after the ramp for reversal / soft start) until |v2 - ref| stays within +/-1 V
(0.25 %); 0 = never left the band. Peak deviation in % of 400 V (CV) or of 6.6 kW (CP). ITAE in V ms^2 (CV) or
W ms^2 (CP) from the event. Currents are HV-referred inductor currents over the window after the event.
Violations = periods with |i_L| > 24 A (none occurred with the DC-free modulator; hardware trip 32 A never reached).

### 3.1 Metrics

| scenario | controller | settling (ms) | peak dev. (%) | ITAE | I_pk (A) | I_rms (A) | ops / update |
|---|---|---|---|---|---|---|---|
| load step 10 -> 100 % | PI | 2.12 | 0.672 | 7.3 | 13.1 | 9.48 | 103 |
| | CCS-MPC | 0 | 0.166 | 1.6 | 13.9 | 9.44 | 2467 |
| | FCS-MPC | 0 | 0.212 | 2.6 | 14.5 | 9.37 | 8040 |
| | Explicit MPC | 0.23 | 0.262 | 1.3 | 15.0 | 9.70 | 136 |
| | Adaptive MPC | 0 | 0.165 | 1.5 | 14.9 | 9.44 | 2812 |
| | Robust MPC | 0 | 0.165 | 1.5 | 15.0 | 9.44 | 2467 |
| load step 100 -> 10 % | PI | 1.95 | 0.673 | 6.6 | 11.4 | 1.83 | |
| | CCS-MPC | 0 | 0.156 | 1.6 | 10.7 | 2.58 | |
| | FCS-MPC | 0 | 0.211 | 7.9 | 10.2 | 2.11 | |
| | Explicit MPC | 0 | 0.245 | 1.2 | 12.3 | 3.29 | |
| | Adaptive MPC | 0 | 0.159 | 1.5 | 10.2 | 2.67 | |
| | Robust MPC | 0 | 0.160 | 1.6 | 10.6 | 2.39 | |
| V1 step 800 -> 700 V, full load | PI | 0 | 0.025 | 0.65 | 15.1 | 10.53 | |
| | CCS-MPC | 0 | 0.017 | 1.6 | 15.7 | 10.54 | |
| | FCS-MPC | 0 | 0.029 | 3.2 | 17.2 | 10.59 | |
| | Explicit MPC | 0 | 0.016 | 0.97 | 15.3 | 10.54 | |
| | Adaptive MPC | 0 | 0.018 | 1.6 | 15.7 | 10.54 | |
| | Robust MPC | 0 | 0.018 | 1.5 | 15.8 | 10.54 | |
| reversal +6.6 -> -6.6 kW (CP, 2 kW/ms) | PI | 0 | 0.963 | 810 | 10.2 | 8.02 | |
| | CCS-MPC | 0 | 1.020 | 1401 | 10.6 | 8.02 | |
| | FCS-MPC | 0 | 1.355 | 1325 | 10.9 | 8.03 | |
| | Explicit MPC | 0 | 1.027 | 1376 | 10.6 | 8.02 | |
| | Adaptive MPC | 0 | 1.013 | 1452 | 10.6 | 8.02 | |
| | Robust MPC | 0 | 1.025 | 1412 | 10.7 | 8.02 | |
| soft start 380 -> 400 V (20 ms), 50 % | PI | 0 | 0.425 | 22.5 | 7.4 | 4.73 | |
| | CCS-MPC | 0 | 0.099 | 14.7 | 8.4 | 4.83 | |
| | FCS-MPC | 0 | 0.132 | 28.3 | 8.8 | 4.82 | |
| | Explicit MPC | 0 | 0.163 | 38.9 | 10.1 | 5.02 | |
| | Adaptive MPC | 0 | 0.099 | 14.9 | 8.4 | 4.84 | |
| | Robust MPC | 0 | 0.100 | 14.1 | 8.2 | 4.83 | |

Measured Python time per update (secondary indicator, numpy overhead dominates): PI 10-23 us, explicit MPC
7-70 us, FCS 0.4-0.9 ms, CCS / adaptive / robust 0.5-1.5 ms.

### 3.2 Plain reading of the numbers

* **Load steps (CV):** every MPC variant cuts the voltage deviation by a factor 3-4 (0.67 % -> 0.16-0.26 %) and
  the ITAE by 3-5, and is back inside +/-1 V in < 0.25 ms instead of 2 ms, at the same rms current and within
  +2 A of the PI's peak current. The explicit LUT keeps most of that (0.26 %) at the PI's compute cost. The 05
  requirement EL-10 (3 % dip) is met by the PI already; the MPC gain is in margin, not in compliance.
* **V1 step:** no difference - all controllers feed V1 forward through the inverse; the PI has the lowest ITAE.
* **Power reversal (CP): the MPCs are NOT better than the PI's static inverse.** Peak power error 1.0-1.4 % vs
  0.96 %, ITAE 1.7x larger. The reference ramp (2 kW/ms firmware slew limit) is slow compared with every loop, so
  the only thing that matters is the steady-state model mismatch (R_s losses, EPS): the MPC's filtered
  measured-current correction lags the ramp more than it helps. A plain feed-forward with a slowly adapted loss
  factor would do the same job as the MPC in CP mode.
* **Soft start:** CCS / adaptive / robust are best (0.10 % tracking error); the explicit LUT is the worst MPC
  (ITAE 39 vs PI 22) because its stored law is linearised at the steady-state phi_ff and has no memory of the
  previous command - during a ramp it hunts. A 4-D table with a previous-phi axis would fix it at 13x the memory.
* **FCS-MPC** is never the best: the PWM-step candidate set limits its slew (36 deg per period) and the discrete
  choice adds +/-1 step chatter (visible in the rms at 10 % load, 2.1 A vs 1.8 A for the PI); its 22 exact period
  evaluations per update cost 8000 operations.
* Adaptive and robust variants behave as the CCS-MPC on the nominal plant (as they should); their value shows only
  with parameter error (sec. 4).

### 3.3 Modulator comparison (load step 10 -> 100 % at 850/300 V, d = n V2 / V1 = 0.71; `results/benchmark_modulators.*`)

| modulator | controller | peak dev. (%) | settling (ms) | I_pk (A) | periods > 24 A | I_rms full load (A) | ZVS margin HV / LV (A) |
|---|---|---|---|---|---|---|---|
| SPS | PI | 0.93 | 1.9 | 23.0 | 0 | 12.22 | +16.8 / +2.3 |
| SPS | CCS-MPC | 0.29 | 0 | 30.2 | 21 | 12.23 | +17.2 / +2.8 |
| EPS matching | PI | 1.75 | > 12 (not settled) | 22.2 | 0 | 11.97 | +2.3 / +5.1 |
| EPS matching | CCS-MPC | 0.33 | 0 | 31.5 | 26 | 12.31 | +2.5 / +5.3 |
| EPS + DC-free transition | PI | 1.75 | > 12 | 18.7 | 0 | 11.98 | +2.3 / +5.1 |
| EPS + DC-free transition | CCS-MPC | 0.33 | 0 | 22.9 | 0 | 12.31 | +3.0 / +6.0 |

EPS matching equalises the ZVS margins of the two bridges (SPS: +16.8 / +2.3 A -> EPS: +2.3 / +5.1 A) and lowers
the full-load rms by 2 %, but it costs the PI its feed-forward accuracy: the SPS inverse under-estimates phi by
~15 % at d = 0.71, the extra power must come from the integrator, and the PI output clamp at 1.1 P_rated is
reached - the PI does not get back inside +/-1 V within the 12 ms window (steady-state 2 V below reference). The
observer-based MPC absorbs the mismatch. The DC-free transition removes the 24 A violations of the fast controller
(30-31 A -> 22.9 A) and lowers the PI's peak as well (22-23 A -> 18.7 A).
**Not benchmarked:** DPS and TPS as inner modulators of the closed loop (only the steady-state TPS map is used in
`../Embedded_AI`); the analytical SPS/EPS/DPS/TPS comparison remains in 11_Control_Algorithms/control_design.md.

### 3.4 CCS-MPC tuning (`results/benchmark_ccs_r_sweep.*`, load step 10 -> 100 % at 800/400 V)

| r (rad^-2 V^2) | 2 | 8 | 16 | 32 | 128 | 512 | PI |
|---|---|---|---|---|---|---|---|
| peak deviation (%) | 0.116 | 0.146 | 0.166 | 0.186 | 0.276 | 0.466 | 0.672 |
| I_pk (A) | 19.2 | 14.8 | 13.9 | 14.7 | 15.9 | 16.6 | 13.1 |
| I_rms (A) | 10.84 | 9.64 | 9.44 | 9.37 | 9.39 | 9.47 | 9.48 |

r < 8 makes the law react to the 0.12 V ADC quantisation (noise-driven phase jitter raises the rms current by
15 %); r = 16 is used everywhere.

## 4. Adaptive and robust MPC with parameter error (`results/adaptive_*`, 650/450 V corner, load step 10 -> 100 %)

RLS convergence (`results/adaptive_rls_convergence.png`): plant L = 1.2 L_nom -> L_hat 77.4 uH (true 76.8, error
0.8 %); plant L = 0.8 L_nom -> 51.7 uH (true 51.2, 1.0 %). The time constant of the estimator is ~1 ms, but at
10 % load the estimate settles on a biased value (79.5 uH = +3.5 %, 54.5 uH = +6 %) because the regressor is
lossless and the R_s = 0.3 Ohm drop is a larger fraction of the small current; after the load step to 100 % both
estimates are within 2 % in 0.2 ms and within 1 % at the end of the window. SYNTHETIC drift 1.0 -> 0.85 L_nom in
10 ms at 60 % load (a thermal drift takes minutes; the fast ramp only shows tracking): the estimate follows with
~2 ms lag (forgetting factor 0.995), maximum tracking error 4.9 %, final 1.4 %.

| plant L | controller | settling (ms) | peak dev. (%) | v2 min (V) | I_pk (A) | periods > 24 A |
|---|---|---|---|---|---|---|
| 0.8 L_nom | CCS-MPC (nominal model) | 0 | 0.14 | 449.4 | 22.6 | 0 |
| | Adaptive MPC | 0 | 0.15 | 449.3 | 22.5 | 0 |
| | Robust MPC | 0 | 0.14 | 449.4 | 23.0 | 0 |
| | PI | 1.8 | 0.55 | 447.5 | 21.2 | 0 |
| 1.0 L_nom | CCS-MPC | 0 | 0.16 | 449.3 | 22.3 | 0 |
| | Adaptive MPC | 0 | 0.16 | 449.3 | 22.2 | 0 |
| | Robust MPC | 0 | 0.16 | 449.3 | 19.4 | 0 |
| | PI | not settled | 1.22 | 444.5 | 17.7 | 0 |
| 1.2 L_nom | CCS-MPC | 0 | 0.18 | 449.2 | 20.1 | 0 |
| | Adaptive MPC | 0 | 0.17 | 449.2 | 20.1 | 0 |
| | Robust MPC | not settled | 1.76 | 442.1 | 16.6 | 0 |
| | PI | not settled | 4.88 | 428.0 | 14.5 | 0 |

Findings, stated plainly:
* With the DC-free modulator and the 24 A bound the nominal CCS-MPC never violated the current limit even with
  L 20 % low (peak 22.6 A vs the 24 A limit); the adaptive estimate therefore buys little here - its value is the
  correct steady-state gain and bound, not the transient.
* The **robust (tube) variant is over-conservative where it matters**: tightening the bound for L_min = 0.8 L_nom
  removes the phase range that the plant needs when L is actually 1.2 L_nom (46.9 deg required at 650/450 V with
  EPS, 43 deg allowed) - the controller saturates and v2 sags 1.8 %. There is no single phi box that is safe for
  L = 0.8 L_nom and feasible for L = 1.2 L_nom at this corner; adaptation, not robustification, is the right tool.
* **The PI baseline cannot deliver rated power at the 650/450 V corner** (d = 1.38, EPS D2 = 0.72) once L is
  +20 %, and is marginal at nominal L: the required phase shift (37 deg nominal, 47 deg at 1.2 L_nom) corresponds
  through the nominal-L SPS inverse to a power command above the 1.1 P_rated clamp of the PI. This is a property
  of the firmware's open-loop inverse + clamp, independent of the MPC work, and worth a firmware ticket: either
  clamp phi instead of power, or use an EPS-aware inverse.

## 5. ZVS maps and adaptive dead time (`zvs_maps.py`)

Grid: V1 650-850 V (25 V), V2 300-450 V (25 V), P +/-10..100 % (10 %), SPS and EPS matching, phi for the target
power from the exact period model, margins from `DABPoint.zvs_margin` with
`I_min = zvs_current_min(Coss_er, V, L, C_par)` (same call as 04_Design_Calculations; HV C3M0032120K 170 pF, LV
C3M0016120K 350 pF, C_par 60 pF). **Temperature:** the device table has no Coss(T); for SiC MOSFETs the datasheet
variation of Coss with temperature is a few %, so the Tj = 25 C and Tj = 150 C maps coincide in this model (Rds_on(T)
does not enter the lossless criterion). What actually moves the boundary is swept instead: L +/-15 %, Coss_er
+/-20 %, and the worst combination. Hard-switching cells are hatched in `results/zvs_maps_nominal.png` and
`results/zvs_maps_worst_tolerance.png`; `results/zvs_min_load.png` gives the minimum forward load for ZVS of both
bridges per voltage pair.

| case | hard-switching fraction of the V1 x V2 x P envelope, forward / reverse | worst voltage pair (needs > x % load) | voltage pairs with ZVS down to 10 % |
|---|---|---|---|
| nominal, SPS | 46.3 % / 46.0 % | 650/450 V: ZVS only >= 100 % | 0 of 63 |
| nominal, EPS | 47.0 % / 46.7 % | 650/450 V: >= 90 % | 0 of 63 |
| L -15 %, SPS / EPS | 54.0 / 54.9 % | 650/450 V: never / >= 100 % | 0 |
| L +15 %, SPS / EPS | 41.6 / 43.2 % | 650/300 V: never (reverse) | 0 |
| Coss +20 %, SPS / EPS | 47.9 / 48.9 % | 650/450 V: >= 100 / 90 % | 0 |
| Coss -20 %, SPS / EPS | 45.2 / 46.5 % | 650/450 V: >= 100 / 90 % | 0 |
| worst (L +15 %, Coss +20 %), SPS / EPS | 42.7 / 43.8 % | 650-725 V / 300 V (+ 650/325 V) never with SPS; 650-750 V / 300 V never with EPS | 0 |

Infeasible (hard-switching) regions, explicitly: every voltage pair hard-switches at 10 % load with both
modulations; at nominal parameters the light-load boundary runs from 20-30 % load along the matched diagonal
(d ~ 1, e.g. 700/350, 650/325, 850/425) to 90-100 % at 650/450 V and 80-90 % at 850/300 V; with L +15 % the
650-750 V / 300-325 V corner loses ZVS at every load (reverse direction included). EPS matching moves hard
switching from one bridge to the other (nominal: HV bridge hard in 26 % of the cells with SPS, 41 % with EPS; LV
bridge 21 % -> 35 %) but does not shrink the hard-switching area in this cell count - it reduces the margin
deficit (see 11_Control_Algorithms table) rather than eliminating it. This is consistent with the `zvs_sps`
derating table of `design_values.json` (minimum load 0.2-1.0). Closing the light-load gap needs the TPS map
(`../Embedded_AI`: ZVS-feasible at 67 % of the nodes vs 55 % for SPS) or burst/frequency control, not EPS alone.

Adaptive dead time (`results/zvs_dead_time_table.csv/.png`): `t_d = max(50 ns, 2 Qoss(V) / |I_edge|)` with
`Qoss(V) = Qoss_800V V / 800` (HV 200 nC at 800 V; LV 420 nC at 800 V, i.e. 210 nC at 400 V). The fixed 150 ns design
dead time is sufficient above 2.7 A (HV, 800 V) and 2.8 A (LV, 400 V); below that the table extends it up to 500 ns
(1 A edge current needs 400-420 ns), beyond which the edge is treated as hard switching.

## 6. C2000 feasibility (`results/c2000_feasibility.json`)

Target: TMS320F28379D class (C28x + FPU32 + TMU, 200 MHz, 1 MB flash, 204 KB RAM), ISR budget 10 us at 100 kHz.
Assumptions (stated, not measured): compiled C, 2 cycles per FPU add/mul including load/store, 8 per TMU
divide/sqrt, 4 per compare+branch, 2 per memory access; ISR overhead 120 cycles (context, 4 ADC reads + scaling,
3 EPWM writes); DC-free transition (+39 ops) included for all.

| controller | ops / update (mul, add, div, sqrt, cmp, load) | cycles | WCET (us) | fraction of 10 us | fits |
|---|---|---|---|---|---|
| PI + inverse + EPS (firmware) | 103 | 414 | 2.1 | 21 % | yes |
| Explicit MPC (LUT 33x9x23 + observer) | 136 | 466 | 2.3 | 23 % | yes |
| CCS-MPC N = 8, K = 20 | 2467 | 5804 | 29.0 | 290 % | no |
| CCS-MPC N = 5, K = 10 | 897 | 2224 | 11.1 | 111 % | no |
| CCS-MPC N = 8, K = 40 | 4767 | 11044 | 55.2 | 552 % | no |
| FCS-MPC (22 candidates x exact period model) | 8040 | 19654 | 98.3 | 983 % | no |
| Adaptive MPC (CCS + RLS with pwl regressor) | 2812 | 6650 | 33.3 | 333 % | no (RLS alone: ~350 ops ~ 4 us, fine at 10 kHz) |
| Robust MPC | 2467 | 5804 | 29.0 | 290 % | no |

Memory: explicit LUT 6831 entries = 13.3 KB in Q15 (26.7 KB float32), fits in flash or RAM; CCS state 56 bytes.
Sampling: v1, v2 every period (12-bit, synchronous with the EPWM period event); **period-average LV current**
every period for the observer-based MPCs and the RLS (integrating sample or two samples per period - the present
sensing chain has a CT peak detector, which is not sufficient for this); i_L peak for protection only;
temperature at 1 kHz; the RLS can run decimated at 10 kHz.
Deterministic fallback: explicit LUT by default; switch to PI (fixed-iteration, same inverse) when any of
|d_hat| > 1.3 P_rated / v2 for 10 periods, LUT inputs out of range for 10 periods, RLS estimate outside
[0.7, 1.3] L_nom or non-decreasing covariance, |v2 - ref| > 5 % for 2 ms, or ISR overrun flag; the hand-over keeps
phi and pre-loads the PI integrator with d_hat v2 so the output is continuous; switching back is supervisory
only. Verdict: of the six, only the explicit LUT is ISR-feasible; the online QPs need either a slower rate (every
5-10 periods) or a CLA/second core, and the FCS enumeration is out by an order of magnitude.

## 7. Maturity and what was NOT verified

* L2 for all closed-loop results (switched Python plant of the project, lossless bridges, no dead time, ideal
  transformer, constant R_s). L1 for every WCET/cycle figure. No hardware, HIL or C2000 toolchain.
* Not verified: behaviour with the 150 ns dead time and body-diode conduction; sensor bandwidth and delay of a real
  period-average current measurement; EPWM implementation of the per-half-period edge move (shadow loads at both
  ZERO and PRD events); the CP-mode reversal with a real battery model; thermal drift rates of L (the 10 ms drift is
  SYNTHETIC); C-code of any controller (none written); ZVS maps against measured Coss(V, T) curves and the
  interwinding capacitance (C_par = 60 pF design assumption); Qoss(V) linear scaling in the dead-time table.
* Negative / limiting results to keep in mind: MPC gives no advantage in CP mode; the explicit LUT is worse than
  the PI on the soft-start ramp; the robust tube variant is infeasible at the 650/450 V corner; the FCS-MPC never
  wins; the PI baseline cannot reach rated power at 650/450 V with L +20 % because of its power clamp through the
  nominal inverse; the DC-free transition modulator matters more for the peak current than the choice of
  controller.
