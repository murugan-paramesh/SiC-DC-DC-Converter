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

## Last toolchain run (2026-10-10T07:53:09 UTC, commit ca67152a87)

| Module | Script | Status | Wall (s) |
|---|---|---|---|
| SiC_Health_Monitoring | 01_generate_synthetic_data.py | PASS | 2.3 |
| SiC_Health_Monitoring | 02_estimators_and_detection.py | PASS | 5.5 |
| Active_Gate_Drive | gate_drive_analysis.py | PASS | 2.6 |
| Reliability_Engineering | fta.py | PASS | 1.4 |
| Reliability_Engineering | fmeda_lite.py | PASS | 0.3 |
| Reliability_Engineering | state_machine_check.py | PASS | 1.5 |
| HIL_Validation | sil_fault_injection.py | PASS | 52.5 |
| Cybersecurity | cmac_replay_demo.py | PASS | 0.1 |
| Multiphysics_Models | electro_thermal_aging.py | PASS | 2.5 |
