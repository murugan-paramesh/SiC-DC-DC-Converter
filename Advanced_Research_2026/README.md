# Advanced_Research_2026 - research program on the 6.6 kW SiC DAB platform

This directory adds a research layer on top of the engineering baseline in `../SiC_6k6_Industrial_DAB/`
without changing its specification (650-850 V <-> 300-450 V, 6.6 kW, 100 kHz, 1200 V SiC, C2000 control).
The baseline was preserved as git tag `engineering-baseline-2026-10-10` (local tag; the session may push
only its development branch).

**Honesty statement.** Nothing here has been built, energised or measured. Every result is analytical (L1),
simulation (L2) or software-verified (L3). Synthetic data are labelled SYNTHETIC; proposed hardware
(transition-time sensor, V_ds,on sense circuit, HIL bench) is labelled proposed. See
`Verification_Evidence/maturity_matrix.md` for the level of every deliverable and
`Verification_Evidence/KNOWN_ISSUES.md` for the 17 findings this work made about the baseline (4 fixed, 11 open, 2 documented).

## Start here

1. `00_Gap_Analysis_and_Plan.md` - audit of what existed, gap matrix, selected contributions (primary A:
   physics-informed adaptive soft-switching control; secondary D: twin parameter estimation; secondary B:
   reliability-aware design), mathematical basis, risks.
2. `MODULE_CONVENTIONS.md` - rules every module follows (README, scripts, results/, provenance.json).
3. `Verification_Evidence/run_all.py` - reruns every module listed in `manifest.json` and hashes the outputs.

## Modules

| Module | One-line result | Level |
|---|---|---|
| `Literature_Database/` | 57 entries 2019-2026: 43 confirmed from search snippets, 12 partially, 2 not found; two specification-named papers corrected | L0 |
| `Digital_Twin/` | L and R_s identifiable from the board's sensors, Coss not; RLS/EKF track 20 % L error to 0.25 %; Coss to 4.5 % with a proposed sensor; supervisory gives a modest rms gain | L2 / L3 |
| `Adaptive_MPC/` | MPC cuts load-step deviation 3-4x but not reversal or soft start; only the explicit LUT fits the 10 us ISR; 46 % of the envelope hard-switches at nominal | L2 / L1 |
| `Embedded_AI/` | Q15 LUT 13.3 KB / 0.9 us chosen over an MLP (13 us, 1.5 deg rms) | L2 / L1 |
| `Physics_Informed_Models/` | the exact analytical model beats every learned surrogate (0.12 % vs 0.59 %); the physics loss did not help | L2 |
| `Safe_RL_Research/` | no benefit over PI + EPS; safety limits held; model-based ZVS filter missed 2 points | L2 |
| `FEM_Magnetics/` | in-house 2-D FD solver: leakage 7.6 vs 4.1 uH designed; proximity 1.41/1.57 vs 1.04/1.08; litz does not fit the window | L1-L2 |
| `Parasitic_Extraction/` | commutation loop 27.9 nH (91 % package); gate loop 109 nH; turn-off overshoot margin >= 171 V | L1 |
| `Robust_Optimization/` | baseline near the loss front, dominated in volume, infeasible under robust/chance constraints; strict-robust ZVS impossible with SPS (closed form) | L2 |
| `Uncertainty_Quantification/` | eta_nom 98.61 +/- 0.05 %; inductance tolerance dominates ZVS and corner efficiency | L2 |
| `Multiphysics_Models/` | electro-thermal-aging loop; cooling-option lifetime ratios; light-load hard switching dominates Tj cycling | L2 |
| `SiC_Health_Monitoring/` | SYNTHETIC: 1 % Rds_on drift detected in 1-7 weeks with a life-stable 1 K temperature reference | L2 |
| `Active_Gate_Drive/` | not worth it for a ZVS converter; -3 V bias leaves no crosstalk margin -> -4 V or Miller clamp | L1 |
| `Reliability_Engineering/` | FTA cut sets, FMEDA-lite (DESAT/interlock coverage 0 %), exhaustive state-machine check, 0 mismatches vs the C core | L1 / L3 |
| `HIL_Validation/` | HIL bench PROPOSED; 19/19 software fault-injection tests pass; LV-sensor common-cause gap found | L3 (SIL) |
| `Cybersecurity/` | IEC 62443 applicability, STRIDE, secure update design, CMAC + replay-counter demo | L0-L1 |
| `Research_Benchmarks/` | 14-row comparison with stated inequalities; fair-measurement methodology | L1 |
| `Research_Publications/` | four manuscript outlines, not submitted | L0 |
| `Experimental_Datasets/` | empty by design: no measured data exist; reserved for HIL/lab data with provenance | - |
| `Verification_Evidence/` | toolchain runner, manifest, maturity matrix, known-issues register | L3 |

## Not available in this environment

No hardware or laboratory, no HIL bench, no FEM package (hence the in-house 2-D solver), no C2000 compiler
(execution times are operation-count estimates), no torch/sklearn (all learning code is numpy), and no access to
publisher full texts (literature verified from search snippets only).
