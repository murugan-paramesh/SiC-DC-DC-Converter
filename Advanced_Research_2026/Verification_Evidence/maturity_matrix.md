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
| Engineering baseline | DAB firmware control core + SIL harness | **L3** | 10_Firmware/sil/sil_results.csv (35 checks) | C2000 HAL never compiled with the TI toolchain (L0-L1) |
| Engineering baseline | DAB KiCad schematic (5 sheets) and netlist consistency | **L3** | 18_Verification/verification_report.md | pinouts flagged for datasheet verification |
| Engineering baseline | DAB 6-layer PCB (generated placement/routing, DRC) | **L2** | 07_KiCad_Schematics/drc_summary.json (latest run) | becomes L3 only at 0 DRC errors / 0 unconnected; silk warnings remain |
| Engineering baseline | Thermal, EMI/EMC, safety (insulation coordination), FMEA, BOM, manufacturing outputs | **L1-L2** | 13_, 14_, 15_, 16_, 17_ folders | no measurement, no pre-compliance test, no certification |
| Research 2026 | Literature database 2022-2026 | **L0 (record)** | Advanced_Research_2026/Literature_Database/ | 57 entries: 43 confirmed from search snippets, 12 partially, 2 not found; no full texts accessible (publisher hosts blocked); the specification-named 'DAB digital twin TIM 2025' is IECON 2024 (Bayindir et al.), the Kiel APEC 2025 98 % figure is only a snippet |
| Research 2026 | Digital twin: observability, RLS/EKF/Bayes estimation, Coss estimator, thermal observer, supervisory | **L2 (L3 code)** | Advanced_Research_2026/Digital_Twin/results/ | transition-time sensor is a proposal; no hardware |
| Research 2026 | FEM_Magnetics: 2-D finite-difference magnetostatics (leakage, proximity, planar vs wound, Pareto) | **L1-L2** | Advanced_Research_2026/FEM_Magnetics/results/ (validation vs closed form -0.04 %, Dowell -0.03 %) | 2-D approximation, no 3-D/commercial FEM, no measurement; finds proximity factors 1.41/1.57 vs the design's 1.04/1.08 and a litz packing problem (12.8 mm needed vs 11.7 mm window) |
| Research 2026 | Parasitic_Extraction: commutation-loop and gate-loop partial inductance from the board geometry, overshoot margin | **L1** | Advanced_Research_2026/Parasitic_Extraction/results/parasitics.json (27.9 nH loop, 109/56 nH gate loops) | closed-form partial inductances, package inductance from literature-typical values, no field solver or measurement |

## Last toolchain run (2026-10-10T03:11:15 UTC, commit 85c5adc518)

| Module | Script | Status | Wall (s) |
|---|---|---|---|
| FEM_Magnetics | run_fem_magnetics.py | PASS | 232.0 |
| Parasitic_Extraction | extract_parasitics.py | PASS | 7.1 |
