# Paper 2 (control) - draft outline with results

**Working title:** What model predictive control actually buys a 6.6 kW SiC dual active bridge:
a same-plant benchmark of six controllers, a C2000 execution-time budget and the wide-range ZVS envelope

**Target venue:** IEEE Open Journal of Power Electronics, IEEE JESTPE, or IECON / ECCE (conference).

**Validation level: L2 (switched simulation) for every controller result, L1 for every execution-time
number (operation counts with stated cycles-per-operation; no C2000 toolchain or hardware).**

## Abstract (draft)

MPC for dual active bridges is usually reported against a hand-tuned PI on a different plant, without an
execution-time budget. We benchmark six controllers - the deterministic PI with modulator inverse and EPS
voltage matching, continuous-control-set MPC (box QP by projected gradient), finite-control-set MPC on an exact
piecewise-linear period model, explicit MPC as a 33 x 9 x 23 look-up table, adaptive MPC with recursive least
squares on 1/L, and a tube-robust variant - on the same 6.6 kW, 100 kHz switched plant with a 12-bit
measurement chain and a one-period delay. Every MPC variant reduces the load-step voltage deviation by a
factor 3-4 (0.67 % to 0.16-0.26 %) and settles in under 0.25 ms instead of 2.1 ms at unchanged rms current,
but none is better than the PI during a slew-limited power reversal, the explicit LUT is worse than the PI in
soft start, and finite-control-set MPC never wins. Operation-count budgets on a 200 MHz C28x with FPU and TMU
show that only the explicit LUT (2.3 us, 23 % of the 10 us interrupt) fits the switching-period interrupt;
the online QP needs 11-29 us. A modulation-independent finding matters more: over the 650-850 V / 300-450 V
envelope 46 % of the V1 x V2 x P cells hard-switch at nominal parameters with SPS or EPS, every voltage pair
hard-switches at 10 % load, and a -15 % inductance raises this to 54 %; control of the outer phase shift cannot
fix light-load soft switching.

## Sections and evidence (all in `../Adaptive_MPC/`)

1. Introduction: MPC for DAB in the confirmed literature (L15-L17, L26, L27 of `../Literature_Database`);
   the gap: same-plant comparison plus execution budget.
2. Plant and measurement model (`../../SiC_6k6_Industrial_DAB/dabtools/dab/sim_switched.py`, N_sub = 1000,
   12-bit ADC, one-period delay) and the DC-bias-free transition modulator without which fast controllers reach
   30 A at 850/300 V.
3. Controllers (`dab_mpc_lib.py`, `build_explicit_mpc.py`).
4. Benchmarks (`results/benchmark_metrics.csv`, figures `benchmark_step_*.png`): load steps, V1 step, power
   reversal, soft start; metrics ITAE, deviation, settling, rms and peak current, constraint events.
5. Parameter error (`results/adaptive_*`): RLS brings L_hat within 1 % from a 20 % initial error and tracks a
   drift within 4.9 %; the robust tube is infeasible at 650/450 V with L = 1.2 L_nom.
6. C2000 budget (`results/c2000_feasibility.json`) and the deterministic fallback logic.
7. ZVS envelope and adaptive dead time (`zvs_maps.py`, `results/zvs_maps_*.png`, `zvs_dead_time_table.csv`):
   the 46 % hard-switching fraction, worst pair 650/450 V, 150 ns dead time sufficient above 2.7 A.
8. Embedded implementation (`../Embedded_AI`): Q15 LUT 13.3 KB, 0.9 us, 0.067 deg maximum quantisation error;
   the 3-16-16-3 MLP alternative is 13 us and 1.5 deg rms - rejected.
9. Discussion: the MPC gain is margin, not compliance (the PI already meets the 3 % load-step requirement);
   where the research effort should go instead (light-load TPS / burst, Paper 1 adaptive schedule).

## Limitations

Simulation only; scenario windows shortened (12 ms, 20 ms soft start); DPS/TPS not benchmarked as closed-loop
inner modulators; Coss(T) absent from the device table; execution times are estimates.

## Reproducibility

`python3 ../Verification_Evidence/run_all.py Adaptive_MPC Embedded_AI` (about 7 minutes on one core).
