# Research, Design, Optimization and Implementation of a 6.6 kW High-Efficiency Bidirectional Silicon Carbide Dual Active Bridge DC-DC Converter for Industrial High-Voltage Power Conversion Using Advanced Soft-Switching and Adaptive Digital Control

_Technical report generated from the project result files on 2026-10-10. All quantitative results are analytical or simulated unless a laboratory record is cited; no hardware has been built or measured._

## 1. Abstract

This report documents the complete, reproducible engineering chain of a 6.6 kW bidirectional dual active bridge (DAB) converter between an 650-850 V industrial DC bus and a 300-450 V DC port, built with 1200 V SiC MOSFETs on both bridges at 100 kHz. Starting from an existing 3 kW phase-shifted full-bridge (PSFB) reference design, the topology is selected by a quantitative comparison (PSFB, DAB, CLLLC, interleaved and three-phase DAB), the power stage is designed analytically (series inductance 64 uH, n = 2, E65 transformer, gapped E55 inductor), the losses and junction temperatures are modelled over the full voltage/power envelope (calculated full-load efficiency 98.62 %, peak 98.66 %), and the design is validated by a closed-loop switched-model simulation and an ngspice switching-level model (power 6.57 kW vs 6.6 kW analytical, ZVS at all eight edges). A digital controller (PI with modulator-inverse feedforward, EPS voltage matching, TPS option, explicit MPC alternative) is designed, implemented in portable C for a TI C2000 target and tested software-in-the-loop (all checks pass). A hierarchical KiCad schematic (259 components) and a 6-layer PCB with three isolation regions are generated from a single design database, DRC-checked against IEC 60664-1-derived clearance rules; thermal, EMI/EMC, insulation coordination, FMEA, optimisation, manufacturing outputs and a staged laboratory plan complete the package. The contribution is methodological (an open, tool-verified design chain); no experimental results are claimed.

## 2. Introduction

Isolated bidirectional DC-DC conversion is the enabling block of industrial DC microgrids, HVDC distribution inside plants and battery-energy-storage interfaces [1]-[5], [19]. Silicon carbide MOSFETs allow 100 kHz operation at 850 V with low switching loss [20], but the designer must handle the voltage-ratio-dependent loss of zero-voltage switching, high dv/dt, insulation coordination at 850 V and a digital controller with hardware-independent protection. This package addresses these points for a concrete 6.6 kW, 800 V / 400 V design.

## 3. Industrial application background

The converter is specified (00_Requirements) for a cabinet-mounted module between a 650-850 V DC bus and a 300-450 V DC port (battery string or LVDC feeder), pollution degree 2, overvoltage category II, <= 2000 m, -10 to +45 C full power, forced-air cooling, CAN supervision, with external precharge contactors. The regulated port and the external source/load characteristics are defined explicitly (APP-03/04) so that the control design is not based on silent assumptions.

## 4. Research motivation

Published DAB work is extensive [1]-[14]; what is rarely available is a complete, reproducible chain from analytical model to routed PCB and firmware in which every number can be regenerated. The motivation here is engineering rigour and traceability (requirements -> calculation -> simulation -> implementation -> verification), on a design point (6.6 kW, 850 V) relevant to industrial HVDC.

## 5. Literature review

See `01_Literature_Review/literature_review.md` (38 entries: DAB fundamentals and modulation [1]-[14], alternative topologies [15]-[19], SiC devices and drivers [20]-[24], magnetics [25]-[29], control [30]-[31], standards [32]-[38]). The references were recalled from memory and must be cross-checked against the publishers before citation in a submitted thesis; no DOI has been invented.

## 6. Research gap

The gap addressed is not a new topology or modulation but the absence of openly reproducible, tool-verified engineering packages at this power/voltage class in which the analytical, simulation, firmware and PCB artefacts are generated from one source and checked automatically. The limitations of this software-only study (no measurements, device data flagged for verification) are stated in chapter 23.

## 7. Research objectives

1. Select and justify the topology for the industrial specification. 2. Derive and implement the DAB models (SPS/EPS/DPS/TPS, ZVS, losses). 3. Design the power stage with a feasibility/derating map. 4. Validate by switched and SPICE simulation. 5. Design and implement the digital control with SIL verification. 6. Generate a DRC-clean, isolation-coordinated PCB. 7. Quantify thermal, EMI and safety aspects. 8. Explore the design space (Pareto). 9. Provide manufacturing and test documentation with an honest verification matrix.

## 8. Topology comparison

`02_Topology_Comparison/` evaluates the candidates at the nine (V1, V2) corners. The PSFB fails the bidirectionality requirement; the CLLLC cannot cover the gain window 0.71-1.38 with frequency control; the single-phase DAB reaches full power at all corners with |phi| <= 60 deg except 650/300 V, keeps the HV-side rms current between 8.4 and 14.3 A, and scores highest in the weighted matrix (industrial suitability, cost, fault robustness). The interleaved two-phase DAB is the documented fallback.

## 9. Selected converter architecture

Single-phase DAB: HV bridge 4 x C3M0032120K, LV bridge 4 x C3M0016120K, n = 2 (E65/32/27 3C95, 28:14), series inductance 64 uH (4.1 uH leakage + 60 uH external E55), HV link 4 x 20 uF/1100 V film, LV link 4 x 30 uF/700 V, four UCC21520 reinforced isolated drivers with eight isolated +15/-3 V bias modules, AMC1301 isolated sensing, CT inductor-current sense, LM393 hardware protection, TI F280049C control via LaunchPad, 24 V auxiliary input, CAN/UART.

## 10. Mathematical modeling

Chapter source: `03_Mathematical_Models/dab_mathematical_model.md`, implementation `dabtools/dab/dab_model.py`. The SPS closed forms (power, switching currents, ZVS boundaries) are reproduced numerically to < 0.1 % by the generic three-level waveform engine that also serves EPS/DPS/TPS. The averaged model (current source K_phi into C2 || R with 1.5 Ts delay) is the control plant.

## 11. SiC semiconductor analysis

Device parameters (`dabtools/dab/devices.py`, flagged verified=False) feed conduction (Rds(Tj)), ZVS turn-off (k_zvs = 0.35 of datasheet Eoff, an explicit assumption), hard-switching (Eon + Eoff + Coss energy where the ZVS criterion fails), dead-time diode and gate losses. At 800/400 V, 6.6 kW: HV bridge 9.8 W, LV bridge 15.7 W, Tj 49 / 51 C at 45 C ambient. Worst-case stresses: 850 V / 1200 V (71 %), peak current 19.6 A HV side at the corners, design envelope limit 24 A, hardware trip 32 A.

## 12. Soft-switching analysis

The energy criterion with Coss(er) gives minimum switching currents I_min = 2.00 A (HV) and 3.07 A (LV); ZVS maps over (V1, V2, P) are in `04_Design_Calculations/img/derating_map.png`: with SPS full ZVS holds down to ~20-100 % load depending on the ratio; EPS/TPS extend it (chapter 14). The ngspice model confirms ZVS at all eight edges at the nominal point (v_DS at turn-on < 0.5 % of the link voltage) and shows the dead-time effect on the effective phase (5.4 deg per edge, compensated in firmware).

## 13. High-frequency magnetics design

`06_Magnetics/magnetics_design.md`: core comparison (E55/ETD59/E65/PQ65/E70 x 3C95/N97), selected E65 pair, 28:14 litz (294/588 x 0.1 mm), Bpk 0.132 T, core loss 11.4 W, copper 7.4 W (Dowell/litz), leakage 4.1 uH interleaved vs 16.4 uH non-interleaved (integrated-leakage option rejected for tolerance reasons), reinforced tape insulation, test procedure. Inductor: E55 gapped 2.10 mm, 17 turns, 7.0 W.

## 14. Digital control development

`11_Control_Algorithms/`: power-normalised PI (kp = 1689 W/V, ki = 1.27e+06 W/(V s)) with modulator inverse in current form, crossover 612 Hz, phase margin 76 deg including the 1.5 Ts delay; EPS voltage matching (D = d) as default modulation, TPS by numerical search as option, explicit one-step MPC as research alternative (dip 0.13 V vs 2.7 V for PI on the averaged model). Firmware (`10_Firmware/`): portable C core + C2000 HAL; the SIL harness exposed two real defects during development (soft-start reference from 0 V, period-end instead of peak current) which were fixed in both implementations.

## 15. Simulation methodology

Three model levels: analytical waveform engine; closed-loop switched model in Python (ideal switches, R_s = 0.3 Ohm loop resistance, link capacitors with bus/battery models, controller in the loop at 100 kHz); ngspice netlist with behavioural switches, body diodes and Coss. Results: start-up overshoot 0.38 %, 50 % load-step dip 0.37 %, 10 % HV dip -> V2 within 399.9-400.1 V, reversal without fault, dead-bus start at 20.2 A peak; SPICE 6568 W, I_rms 9.17 A vs 9.23 A analytical.

## 16. PCB engineering

`07_KiCad_Schematics/` holds the KiCad 7 project (schematic 5 sheets + 6-layer PCB generated by `dabtools/kicad_dab/`): regions HV | 16 mm barrier | control | 16 mm barrier | LV, planes HV_N/HV_P, GND, LV_N/LV_P, switch-node strips on B.Cu, gate clusters at the Kelvin-source pins, straddling isolators in barrier cut-outs with slots under the bias modules, DRC rules by net class (1.5 mm HV-HV, 0.5 mm gate, 8/10/12 mm isolation). 
DRC state of the generated board: 0 errors, 0 unconnected items, kinds {'silk_overlap': 11, 'silk_over_copper': 27, 'silk_edge_clearance': 16, 'track_dangling': 9}.

## 17. Thermal engineering

`13_Thermal_Analysis/`: worst-corner bridge losses scaled from the loss model, cooling options from natural convection to cold plate; selected forced air 3 m/s with two 0.22 K/W extrusions (Tj < 70 C at 45 C ambient; margin for 2x model error), derating curve above 55 C, capacitor hot-spot and thermal-cycling notes.

## 18. EMI and EMC considerations

`14_EMI_EMC/`: DM spectrum from the pulsating bridge current, CM envelope from 20 V/ns edges through ~100 pF per node, required attenuation (DM ~39 dB, CM ~57 dB at 150 kHz-2 MHz vs CISPR 11 class A), two-stage LC filter proposal, layout measures, pre-compliance plan.

## 19. Reliability and safety

`15_Safety_Reliability/`: insulation coordination (IEC 62477-1 / 60664-1 basis: basic HV-LV at 850 V, reinforced ports-to-control; design distances 9/16 mm; the 3 kVrms brief value is revised to 2.5 kVrms basic + 4 kVrms reinforced tests), protection coordination (hardware OC/OV/driver -> PROT_DIS, firmware, system), FMEA with 19 items and open actions (reinforced-rated bias modules, DESAT drivers, flux-balance detection).

## 20. Multi-objective optimization

`12_Optimization/`: exhaustive grid of 8640 candidates (1404 feasible) over fs, n, phi_nom, cores, dead time and devices; Pareto front in (loss, magnetics volume) with 3 non-dominated points; the baseline (92 W, 271 cm3) sits at the knee; sensitivity plots for fs, phase shift and dead time.

## 21. Results and discussion

| Quantity | Value | Source |
|---|---|---|
| Series inductance / nominal phase shift | 64 uH / 28.2 deg | 04 |
| HV / LV rms current at nominal | 9.2 / 18.5 A | 04, SPICE 9.2 A |
| Calculated efficiency nominal / peak | 98.62 / 98.66 % | 04 (analytical) |
| Full-power envelope | all corners except 650/300 V (phi > 60 deg), see derating map | 04 |
| ZVS light-load limit (SPS, nominal) | 25 % | 04 |
| Loop crossover / phase margin | 612 Hz / 76 deg | 11 |
| 50 % load-step dip | 0.37 % | 05 |
| SIL tests | all pass | 10/18 |

The calculated efficiency is above the objectives, but the loss model inherits unverified device parameters and the k_zvs assumption; published measurements of SiC DABs in this class are typically 97-98 %, so the margin to EL-07 (96.5 %) is plausible while the absolute value is not. The SPS ZVS limit at light load is the main efficiency risk; EPS matching mitigates it at d != 1.

## 22. Comparison with published converters

Compared with the reference designs in the literature list (Krismer/Kolar automotive DAB [6]-[8] at 2 kW / 100 kHz with Si devices; Inoue/Akagi 20 kHz IGBT DAB [3]; Jung et al. CLLC for DC distribution [18]), this design operates at a higher voltage with SiC and the same fundamental SPS/EPS/TPS trade-offs; its calculated efficiency and the ZVS behaviour versus d are consistent with those publications' trends. A quantitative benchmark requires measurements.

## 23. Research limitations

No hardware; device parameters from memory (flagged); isolation values recalled from standards (flagged); gate-bias modules only basic-class; BoosterPack pin mapping unverified; KiCad 7 CLI has no ERC (netlist/pin consistency used instead); the generated PCB routing is produced by an own router and is checked by KiCad DRC but has not been reviewed for manufacturability by a human; EMI figures are analytical envelopes.

## 24. Experimental validation methodology

`20_Experimental_Test_Plan/test_plan.md`: 13 staged tests from bare-board inspection and magnetics characterisation through insulation tests, protection injection, HIL, low-voltage power, staged HV power with ZVS verification, efficiency maps, dynamics, thermal soak, EMI pre-compliance and long-duration run, with instruments, criteria and safety controls.

## 25. Future research directions

Measured validation and model calibration (k_zvs, Coss nonlinearity); TPS table generation and online adaptation; DESAT-based drivers and reinforced bias supplies; flux-balance observer; integrated-leakage transformer with controlled tolerance; MPC on target with timing measurements; three-phase DAB for 20 kW scaling.

## 26. Conclusions

A complete, regenerable engineering package for a 6.6 kW SiC DAB has been produced: topology decision, analytical design with envelope maps, two levels of simulation in agreement with the analysis, a SIL-tested control core, a generated schematic and PCB with isolation-coordinated DRC rules, and the supporting thermal/EMI/safety/manufacturing/test documentation. The verification matrix (18) states precisely which checks ran; experimental validation remains to be done under an approved procedure.

## 27. References

See `01_Literature_Review/literature_review.md` (numbered [1]-[38]).

## 28. Appendices

* A. Design values: `04_Design_Calculations/design_values.json`, report `design_report.md`
* B. Simulation results: `05_Simulation/switched_results.json`, `spice/spice_results.json`, `img/`
* C. Control parameters: `11_Control_Algorithms/control_params.json`
* D. Optimisation results: `12_Optimization/optimization_results.json`
* E. Verification evidence: `18_Verification/verification_report.md`, `verification_status.json`, DRC reports `07_KiCad_Schematics/drc_report.txt`
* F. Requirements traceability: `00_Requirements/03_RTM.csv`
* G. BOM: `16_BOM/`

