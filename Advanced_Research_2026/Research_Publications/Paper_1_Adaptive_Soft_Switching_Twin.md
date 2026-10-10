# Paper 1 (primary contribution A) - draft manuscript outline with results

**Working title:** Physics-informed online parameter estimation for adaptive soft-switching control of a
6.6 kW SiC dual active bridge: observability limits of the standard sensing chain and a
transition-time sensor proposal

**Target venue:** IEEE Transactions on Power Electronics (regular paper) or IEEE JESTPE; alternative:
ECCE / APEC (conference version).

**Validation level of every result in this draft: simulation (L2) and software (L3). No hardware.**
The manuscript must state this in the abstract and the title must not suggest an experimental result.

## Abstract (draft, 190 words)

The zero-voltage-switching (ZVS) boundary of a dual active bridge (DAB) depends on the series
inductance L and the effective output capacitance Coss,er of the devices, both of which carry
10-20 % tolerance and drift with temperature. Fixed modulation schedules therefore either waste
circulating current or lose ZVS at light load. This paper presents a hierarchical digital twin of a
6.6 kW, 100 kHz, 1200 V SiC DAB (650-850 V to 300-450 V) whose electrical layer is a period-average
model evaluated on the applied PWM pattern, so that every current is affine in 1/L and L can be
identified by recursive least squares or an extended Kalman filter from the port measurements that
already exist for protection. A Fisher-information analysis over the operating envelope shows that
the standard sensing chain (port voltages, LV shunt, HV current transformer, peak detector) makes
L identifiable to 0.03 % (noise bound) but leaves Coss,er unobservable; a drain-voltage
transition-time measurement is proposed and shown in simulation to identify Coss,er to 4.5 % when
the inductance estimate is used jointly. A supervisory layer selects the inner phase shifts on the
estimated parameters inside a validated envelope with a deterministic fallback. On the switched
simulation with L 20 % below nominal the twin corrects a 10.5 % mean (22.6 % maximum) rms-current
misprediction of the nominal model and reduces hard-switched operating points from 19 to 16 of 27.

## 1. Introduction and related work

* DAB modulation (SPS/EPS/DPS/TPS) and ZVS boundaries: Krismer & Kolar (classical), hybrid
  PS-MPC with Bayesian optimisation (L01, IEICE 2026), AI-based TPS modelling (L02, TPEL 2026).
* Digital twins and parameter identification for converters: one-cycle multi-parameter
  identification (L04), physics-informed data-light estimation (L05), differentiable simulation and
  uncertainty-aware estimation (L28, L29). Gap: none of the confirmed sources quantifies which DAB
  parameters are observable from the sensors of a protection-grade chain, nor couples the capacitance
  branch to the inductance estimate. (Literature ids refer to `../Literature_Database/`.)
* Contribution list (A1-A4): observability analysis; applied-pattern regressor removing modulator
  quantisation; joint L / Coss,er estimation with a proposed sensor; supervisory selection with
  fallback and its honest evaluation.

## 2. Model (from `../../SiC_6k6_Industrial_DAB/03_Mathematical_Models` and `../Digital_Twin/twin.py`)

Equations: period-average LV current I2 = g(s1, s2, V1, V2) / L with g computed on the PWM registers;
lossy edge current via the exact periodic steady state i_{k+1} = a i_k + b_k; ZVS criterion
I_edge >= sqrt(2 Coss,er V^2 / L); transition time t_tr = 2 Coss,er V / |I_edge|.

## 3. Observability (`../Digital_Twin/results/observability.json`)

Table: Fisher-information rank and Cramer-Rao bounds per sensor set (reproduce the README table).
Figure: information per parameter vs sensor set.

## 4. Estimators and results (`../Digital_Twin/results/twin_study.json`)

* E1: RLS/EKF track a 20 % offset and a 15 % drift with 0.24 / 0.25 % final error (Fig. E1).
* E2: light-load conditioning and excitation gating (table).
* E3: Coss,er +4.5 % with the joint estimate vs -11.6 % without (Fig. E3).
* Sensitivity to the loss resistance and ADC quantisation (bias 0.6-0.9 %).

## 5. Supervisory layer (`../Digital_Twin/results/supervisory_study.json`)

Table of the 27 operating points; the honest negative part: light-load hard switching is not removed
by inner-phase-shift selection alone; two points where the model's feasibility differs from the plant.

## 6. Implementation budget (`../Embedded_AI`, `../Adaptive_MPC`)

C2000 cycle estimate of one RLS update per period and the LUT/explicit alternative (fill from the
modules' results when available; mark as estimates, no hardware timing).

## 7. Limitations and validation plan

No hardware; sensor noise figures assumed; dead time not in the plant; thermal twin capacitances
estimated. Validation path: HIL (`../HIL_Validation`, proposed), then a 1 kW de-rated bench test with
the transition-time sensor on one leg.

## Figures and tables list

E1_L_identification.png, E3_Coss_identification.png, supervisory_study.png, observability table,
E2 table, 27-point table (appendix).

## Reproducibility statement

All results regenerate with `python3 Verification_Evidence/run_all.py Digital_Twin`; seeds fixed;
provenance.json records package versions and the git commit.
