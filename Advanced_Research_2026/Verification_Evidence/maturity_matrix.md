# Verification maturity matrix (Advanced_Research_2026, section 28)

| Level | Meaning |
|---|---|
| L0 | concept / document only |
| L1 | analytical model or calculation |
| L2 | simulation-validated (scripts run, results in the repository) |
| L3 | software-verified (automated checks pass: DRC, netlist, SIL, unit tests) |
| L4 | HIL-verified (not available here) |
| L5 | hardware-validated (not available here) |
| L6 | publication-ready with evidence (none) |

No deliverable in this repository is above L3: there is no hardware, no HIL bench, no FEM solver, no C2000 toolchain and no laboratory.

| Area | Deliverable | Level | Evidence | Not verified |
|---|---|---|---|---|
| Engineering baseline | PSFB 3 kW reference design: schematic, 4-layer PCB, gerbers | **L3** | hardware/kicad/drc_summary.json (0 errors), hardware/outputs/ | no hardware |
| Engineering baseline | DAB requirements, envelope, RTM | **L1** | SiC_6k6_Industrial_DAB/00_Requirements/ | customer review |
| Engineering baseline | DAB mathematical model and design calculations | **L2** | 03_Mathematical_Models, 04_Design_Calculations/design_values.json | 2 oz copper loss estimate dominates; device data from memory (verified=False) |
| Engineering baseline | DAB switched simulation (Python plant + controller) and ngspice model | **L2** | 05_Simulation/switched_results.json, spice/spice_results.json | ideal switches, no dead time in the Python plant; pulse-asymmetry defect fixed 2026-10-10 |
| Engineering baseline | DAB firmware control core + SIL harness | **L3** | 10_Firmware/sil/sil_results.csv (30 checks) | C2000 HAL never compiled with the TI toolchain (L0-L1) |
| Engineering baseline | DAB KiCad schematic (5 sheets) and netlist consistency | **L3** | 18_Verification/verification_report.md | pinouts flagged for datasheet verification |
| Engineering baseline | DAB 6-layer PCB (generated placement/routing, DRC) | **L2** | 07_KiCad_Schematics/drc_summary.json (latest run) | becomes L3 only at 0 DRC errors / 0 unconnected; silk warnings remain |
| Engineering baseline | Thermal, EMI/EMC, safety (insulation coordination), FMEA, BOM, manufacturing outputs | **L1-L2** | 13_, 14_, 15_, 16_, 17_ folders | no measurement, no pre-compliance test, no certification |
| Research 2026 | Literature database 2022-2026 | **L0 (record)** | Advanced_Research_2026/Literature_Database/ | 57 entries: 43 confirmed from search snippets, 12 partially, 2 not found; no full texts accessible (publisher hosts blocked); the specification-named 'DAB digital twin TIM 2025' is IECON 2024 (Bayindir et al.), the Kiel APEC 2025 98 % figure is only a snippet |
| Research 2026 | Digital twin: observability, RLS/EKF/Bayes estimation, Coss estimator, thermal observer, supervisory | **L2 (L3 code)** | Advanced_Research_2026/Digital_Twin/results/ | transition-time sensor is a proposal; no hardware |
| Research 2026 | FEM_Magnetics: 2-D finite-difference magnetostatics (leakage, proximity, planar vs wound, Pareto) | **L1-L2** | Advanced_Research_2026/FEM_Magnetics/results/ (validation vs closed form -0.04 %, Dowell -0.03 %) | 2-D approximation, no 3-D/commercial FEM, no measurement; finds proximity factors 1.41/1.57 vs the design's 1.04/1.08 and a litz packing problem (12.8 mm needed vs 11.7 mm window) |
| Research 2026 | Parasitic_Extraction: commutation-loop and gate-loop partial inductance from the board geometry, overshoot margin | **L1** | Advanced_Research_2026/Parasitic_Extraction/results/parasitics.json (27.9 nH loop, 109/56 nH gate loops) | closed-form partial inductances, package inductance from literature-typical values, no field solver or measurement |
| Research 2026 | SiC_Health_Monitoring: Rds_on / Vth drift estimators (RLS, Kalman, CUSUM) on SYNTHETIC degradation data | **L2 (synthetic)** | SiC_Health_Monitoring/results/ (1 % drift detected in 1-7 weeks, 0 false alarms in 3 y with a stable T reference) | no measured aging data, no RUL claim; needs a V_ds,on sense circuit (proposed) and a <= 1 K life-stable temperature reference |
| Research 2026 | Active_Gate_Drive: fixed / two-level / Miller-clamp / active-driver trade-off with datasheet models | **L1** | Active_Gate_Drive/results/ (dv/dt 15-31 V/ns set by I/2Coss under ZVS; active drive not worth it here) | no switching measurement; -3 V vs -4 V bias discrepancy open (KNOWN_ISSUES #6) |
| Research 2026 | Reliability_Engineering: FTA (32 basic events, minimal cut sets), FMEDA-lite, exhaustive state-machine check + C conformance harness | **L1 (FTA/FMEDA), L3 (state machine)** | Reliability_Engineering/results/ (46 080 transitions checked, 0 mismatches vs dab_control.c) | failure rates are assumed generic values; no SIL/certification claim; property P1 fails as literally stated (conditional faults by design) |
| Research 2026 | HIL_Validation: HIL architecture (PROPOSED) + 19 software fault-injection tests | **L3 (SIL); HIL L0** | HIL_Validation/results/ (19/19 pass) | no HIL hardware; LV-sensor common-cause finding open (KNOWN_ISSUES #10) |
| Research 2026 | Cybersecurity: IEC 62443 applicability, STRIDE, secure boot/update design, CMAC + replay-counter demo | **L0-L1** | Cybersecurity/README.md, cmac_replay_demo.py (FIPS-197 / RFC 4493 vectors pass) | C2000 security features marked 'verify vs TRM'; no implementation on the target |
| Research 2026 | Multiphysics_Models: coupled electro-thermal-aging reduced-order model on an assumed 24 h mission profile | **L2** | Multiphysics_Models/results/ (lifetime ratios vs forced air: natural 0.01-0.23, liquid 130-5300; slew/fan variants negative results) | Foster capacitances and lifetime-model coefficients are literature-typical; ratios only, no absolute lifetime |
| Research 2026 | Adaptive_MPC: PI / CCS-MPC / FCS-MPC / explicit LUT / adaptive RLS / robust tube controllers benchmarked on the switched plant; C2000 WCET budget; wide-range ZVS maps and dead-time table | **L2 (controllers), L1 (WCET)** | Adaptive_MPC/results/ (load step: MPC settling <= 0.25 ms vs 2.1 ms PI; reversal and soft start: PI better; only the explicit LUT fits the 10 us ISR; 46 % of the V1 x V2 x P envelope hard-switches at nominal) | no C code, no toolchain/hardware timing; DPS/TPS not benchmarked as closed-loop inner modulators; scenario windows shortened for runtime; Coss(T) absent from the device table |
| Research 2026 | Embedded_AI: Q15 explicit-MPC LUT (13.3 KB, 0.9 us) vs Q15 MLP 3-16-16-3 (0.84 KB, 13 us, 1.5 deg rms) - LUT chosen; ISR/10 kHz/1 kHz schedule; bit-exact test vectors (490) | **L2 (algorithms), L1 (cycle counts)** | Embedded_AI/results/ | no C port, no C2000 timing measurement |
| Research 2026 | Robust_Optimization: NSGA-II (4 objectives incl. damage proxy and ZVS margin), GP-EI search, worst-case and 95 % chance-constrained fronts, knee and baseline position | **L2** | Robust_Optimization/results/ (baseline within 3 % of the nominal front in loss, dominated in magnetics volume; infeasible under robust/chance variants; strict robust variant empty - closed-form argument) | SPS only in the loop; assumed distributions and mission profile; literature-typical lifetime coefficients |
| Research 2026 | Uncertainty_Quantification: MC / LHS / PCE / corner analysis of the baseline, Sobol indices cross-checked (PCE vs Saltelli) | **L2** | Uncertainty_Quantification/results/ (eta_nom 98.61 +/- 0.05 %; inductance dominates ZVS margins and corner efficiencies; ambient dominates Tj) | input distributions assumed, no measured tolerance statistics |
| Research 2026 | Physics_Informed_Models: analytical vs MLP vs hybrid vs PINN vs GP vs LUT vs polynomial surrogates of the DAB map | **L2** | Physics_Informed_Models/results/ (analytical TPS model 0.12 % vs best learned 0.59 % of range; physics loss did not help) | lossless ground truth only; learned models would matter only with measured non-ideal data |
| Research 2026 | Safe_RL_Research: CEM and REINFORCE policies behind a deterministic safety filter and fallback | **L2 (exploratory)** | Safe_RL_Research/results/ (no rms benefit over PI+EPS; peak/V2 limits never reached; 2 model-based ZVS filter misses) | small search budgets, no deep RL, simulation only; never for deployment without HIL |
| Research 2026 | Research_Benchmarks: 14-row comparison vs published 6.6 kW-class work, methodology for a fair measured comparison | **L1** | Research_Benchmarks/results/, benchmark_methodology.md | our numbers calculated, theirs measured; only confirmed literature entries quoted |
| Research 2026 | Research_Publications: four manuscript outlines with abstracts drafted from the repository results | **L0** | Research_Publications/ | not submitted; each needs its named validation step first |

## Last toolchain run (2026-10-10T10:07:24 UTC, commit 921fc9bf0c)

| Module | Script | Status | Wall (s) |
|---|---|---|---|
| Research_Benchmarks | benchmark_table.py | PASS | 2.6 |
| Uncertainty_Quantification | uq_baseline.py | PASS | 32.7 |
| Physics_Informed_Models | surrogate_comparison.py | PASS | 113.3 |
| Safe_RL_Research | safe_rl_modulation.py | PASS | 168.0 |
| Robust_Optimization | robust_optimize.py | PASS | 514.0 |
