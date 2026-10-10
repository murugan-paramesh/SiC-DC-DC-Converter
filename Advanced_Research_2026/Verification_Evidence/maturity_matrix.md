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
| Research 2026 | Literature database 2022-2026 | **L0** | Advanced_Research_2026/Literature_Database/ | see verification_status per entry; several specification-named papers not confirmed |
| Research 2026 | Digital twin: observability, RLS/EKF/Bayes estimation, Coss estimator, thermal observer, supervisory | **L2 (L3 code)** | Advanced_Research_2026/Digital_Twin/results/ | transition-time sensor is a proposal; no hardware |
