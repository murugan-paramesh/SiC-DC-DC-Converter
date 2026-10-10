# Advanced Research 2026 - gap analysis and execution plan

Date: 2026-10-10. Baseline preserved as git tag `engineering-baseline-2026-10-10` on branch
`claude/gifted-archimedes-m9e484` (this session may only develop and push on that branch, so the
research work lives in `Advanced_Research_2026/` on the same branch instead of a second branch; a
separate branch can be cut from the tag at any time without losing anything).

## 1. Repository audit (what exists, how it was verified)

| Area | State | Evidence | Maturity (sec. 28 scale) |
|---|---|---|---|
| PSFB 3 kW reference design | complete: schematic, 4-layer PCB, DRC 0 errors / 0 unconnected, gerbers, docs, switched simulation | `hardware/kicad/drc_summary.json`, `hardware/outputs/` | L3 (software-verified design); no hardware |
| DAB requirements, envelope, RTM | complete | `00_Requirements/` | L1 |
| DAB literature review | 38 recalled references, policy note "to cross-check" | `01_Literature_Review/` | L0 (not verified against sources) |
| Topology comparison | script, quantitative | `02_Topology_Comparison/` | L2 |
| Mathematical model (SPS/EPS/DPS/TPS, ZVS, losses, averaged model) | derivations + `dabtools/dab/dab_model.py`, closed form vs numeric < 0.1 % | `03_Mathematical_Models/` | L1-L2 |
| Design calculations | L = 64 uH, phi_nom 28 deg, eta_calc 98.6 % at nominal, derating/ZVS maps | `04_Design_Calculations/design_values.json` | L2 (calculation only, 2 oz copper loss estimate dominates uncertainty) |
| Simulations | Python switched plant + controller in the loop (regulation, load step, reversal, dead-bus start); ngspice behavioural switching model (P, I_rms, ZVS at all 8 edges) | `05_Simulation/` | L2 |
| Magnetics | E65 transformer 28:14, E55 inductor; Steinmetz/iGSE, Dowell/litz, leakage and capacitance estimates | `06_Magnetics/` | L1-L2 (no FEM) |
| KiCad schematic | 5 sheets, 261 components, netlist = design database | `07_KiCad_Schematics/` | L3 |
| 6-layer PCB | generated placement/planes/pours; auto-routed with the in-house negotiated router; DRC 0 errors / 0 unconnected since routing run 27 (2026-10-10), 63 silkscreen/stub warnings | `07_KiCad_Schematics/drc_summary.json`, `08_KiCad_PCB/README.md` | L3 |
| Firmware | portable C control core (PI + modulator inverse, EPS matching, soft start, state machine, protections, CRC telemetry), SIL harness 30 checks pass; C2000 HAL written, not compiled | `10_Firmware/` | L3 (core), L0-L1 (HAL) |
| Control design | PI loop design, SPS/EPS/DPS/TPS comparison, explicit MPC as alternative | `11_Control_Algorithms/` | L2 |
| Optimisation | exhaustive grid over (fs, L, n, Bpk), Pareto front | `12_Optimization/` | L2 |
| Thermal | losses -> Tj, cooling options | `13_Thermal_Analysis/` | L2 |
| EMI/EMC | DM/CM estimate, filter, standards | `14_EMI_EMC/` | L1-L2 |
| Safety | insulation coordination (IEC 62477-1/60664-1 basis), FMEA | `15_Safety_Reliability/` | L1 |
| BOM, manufacturing, verification, report, test plan | generated; verification report lists what ran | `16`-`20` | L2/L3 |

Nothing has been built, energised or measured (L5/L6: none).

## 2. Gap matrix against the 2026 specification

| Spec section | Existing | Gap | Planned module (directory) | Target maturity |
|---|---|---|---|---|
| 4 Literature 2022-2026 | 38 recalled refs | no verified 2025-2026 sources, no structured database | `Literature_Database/` (CSV + notes; DOIs checked online where reachable) | verified refs |
| 5 Physics-informed AI | none | surrogate models and their fair comparison | `Physics_Informed_Models/` (analytical vs NN vs physics-constrained NN vs GP, numpy/scipy only) | L2 |
| 6 Digital twin | plant model + controller exist, no estimation layer | L1-L4 twin, online estimation (RLS/EKF), observability | `Digital_Twin/` | L2-L3 |
| 7 Advanced MPC | explicit MPC proposal only | CCS/FCS/adaptive MPC implemented and benchmarked, WCET budget | `Adaptive_MPC/` | L2 (+L3 for the C port) |
| 8 Safe RL | none | simulation-only constrained policy search with envelope + fallback | `Safe_RL_Research/` | L2 (exploratory) |
| 9 Wide-range ZVS | ZVS maps at nominal temperature, SPS/EPS | maps over V1, V2, P, Tj, direction, modulation, tolerance; adaptive dead time | `Adaptive_MPC/zvs_maps.py` + `Digital_Twin/` | L2 |
| 10 Active gate drive | fixed Rg design | Rg / multilevel / Miller-clamp trade-off analysis with datasheet models | `Active_Gate_Drive/` | L1-L2 |
| 11 SiC health monitoring | none | Rds_on/Vth drift estimators on synthetic data with provenance | `SiC_Health_Monitoring/` | L2 (synthetic) |
| 12 FEM magnetics | analytical only, no FEM solver installed | 2-D finite-difference magnetostatic solver of the winding window (leakage, field, proximity) + comparison to Dowell; planar vs wound study | `FEM_Magnetics/` | L2 |
| 13 Multiphysics | separate loss/thermal scripts | coupled electro-thermal-aging loop, mission profile, coupling diagram | `Multiphysics_Models/` | L2 |
| 14 Parasitic extraction | none | partial-inductance extraction from the generated board geometry (power loop, gate loop) | `Parasitic_Extraction/` | L1-L2 |
| 15 Robust optimisation | exhaustive grid | NSGA-II with uncertainty (LHS), mission profile | `Robust_Optimization/` | L2 |
| 16 UQ | none | Monte Carlo / LHS / worst case on efficiency, ZVS margin, Tj | `Uncertainty_Quantification/` | L2 |
| 17 Embedded AI | C2000 cycle budget qualitative | fixed-point LUT/MLP sizing, WCET by instruction count, scheduling | `Embedded_AI/` | L1-L3 |
| 18 HIL | SIL harness | HIL architecture, fault-injection test set run in SIL, acceptance tests | `HIL_Validation/` | L3 (SIL), HIL proposed |
| 19 Formal safety | FMEA | FTA, FMEDA-lite, exhaustive state-machine model check | `Reliability_Engineering/` | L1-L3 |
| 20 Cybersecurity | none | IEC 62443 applicability, secure update/auth design | `Cybersecurity/` | L0-L1 |
| 21 Thermal | steady state | electro-thermal transient (Foster), cycling, cooling comparison | `Multiphysics_Models/` | L2 |
| 22 Self-optimising | none | supervisory operating-point selector over validated maps | `Digital_Twin/supervisory.py` | L2 |
| 23 Toolchain | per-folder scripts | `run_all.py` with provenance (versions, hashes) | `Verification_Evidence/` | L3 |
| 24 Benchmarks | none | table + plots vs published 6.6 kW work and our baselines | `Research_Benchmarks/` | L2 |
| 25-26 Contributions / publications | none | this document + `Research_Publications/` | - |
| 28 Maturity levels | partially (verification report) | per-deliverable matrix | `Verification_Evidence/maturity_matrix.md` | - |
| Learning notes (mandatory) | engineering docs only | `21_Human_Friendly_Learning_Notes/` with 21 sections + textbook | - |

## 3. Highest-value contribution (selected)

**Primary - Contribution A: physics-informed adaptive soft-switching control.**
Question: can online estimation of the parameters that set the ZVS boundary (series inductance L,
effective output capacitance C_oss,er(T), and the port voltages) let the modulator keep the bridges
in ZVS over the 650-850 V / 300-450 V / 10-100 % envelope with less circulating current than a fixed
SPS/EPS schedule?

Mathematical basis (all already derived in `03_Mathematical_Models/` and implemented in
`dabtools/dab/dab_model.py`):

* Switching-edge currents for EPS/DPS/TPS are affine in the phase variables for fixed (V1, V2', L, fs).
* ZVS at an edge requires |I_edge| >= I_min = sqrt(2 C_oss,er V^2 / L) with the dead time
  t_d >= Q_oss(V) / |I_edge| (charge-based criterion); C_oss,er and Q_oss are datasheet functions of V,
  weakly of T; L and the leakage have +/-10-20 % tolerance and drift with temperature.
* The averaged current-source model i_L(phi, D1, D2) gives the measured quantities (port currents,
  inductor rms/peak) as explicit functions of the parameters, so L can be identified by recursive
  least squares from (phi, V1, V2, I_avg) and C_oss,er indirectly from the dead-time / ZVS-margin
  sensor (drain-voltage slope or minimum-current observer).
* The adaptive law then re-solves the EPS matching condition D = V2'/V1 and the minimum-current TPS
  point from the *estimated* parameters every N cycles, with a validated fallback to the fixed
  schedule when the estimate leaves its confidence interval.

Expected validation: identifiability/observability analysis (which parameters are observable from
V1, V2, I1, I2, i_L samples with realistic noise), RLS/EKF convergence in the switched simulation
under parameter steps, ZVS-margin and rms-current maps before/after adaptation across the envelope,
timing budget of the estimator on the C2000 (fixed point), fault handling (estimate rejected ->
fallback). Maturity reachable here: L2 (simulation) and L3 (software), with an L4/L5 plan.

Secondary 1 - Contribution D (digital-twin parameter estimation): same estimator, extended to
Rds_on / thermal-resistance drift for health monitoring; shares the twin and sensor model.

Secondary 2 - Contribution B (reliability-aware modulation): use the electro-thermal twin to score
each candidate modulation by Tj swing and rainflow damage per mission profile, not only by rms current.

Integration risks: (1) the estimator depends on sensor bandwidth (inductor current sampling at
100 kHz needs a >= 1 MS/s channel, the current design has the CT + AMC1301 chain for the HV link and
a shunt for the LV port - the inductor-current path must be specified); (2) adaptive dead time and
phase changes interact with the protection thresholds - every adapted command passes the same limiter
as the fixed schedule; (3) numerical conditioning of RLS at light load (small signal) - forgetting
factor and excitation gating required; (4) no hardware: all claims stay at L2/L3.

## 4. Execution sequence (sec. 29 priorities)

1. Finish the DAB PCB (done: run 27, 0 DRC errors), exports, verification, report - *before anything else*.
2. Research baseline validation: re-run the full chain under `Verification_Evidence/run_all.py` with provenance.
3. Primary contributions: `Digital_Twin/` (estimation + observability), `Adaptive_MPC/` (controllers + benchmarks + WCET), `FEM_Magnetics/` + `Robust_Optimization/` (magnetics/control co-optimisation).
4. Extensions: `SiC_Health_Monitoring/`, `Active_Gate_Drive/`, `Uncertainty_Quantification/`, `Physics_Informed_Models/`, `Multiphysics_Models/`, `Parasitic_Extraction/`.
5. Experimental readiness: `HIL_Validation/`, `Reliability_Engineering/`, `Cybersecurity/`.
6. Publication evidence: `Research_Benchmarks/`, `Research_Publications/`, maturity matrix.
7. Learning notes (`21_Human_Friendly_Learning_Notes/`) written alongside each module, kept in sync with the project files.

Every module reports its maturity level and what it could not verify in this environment (no FEM
solver, no HIL hardware, no laboratory, no C2000 toolchain, no measured SiC aging data).
