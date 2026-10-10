# Research_Publications - publication package (drafts, not submitted)

Four manuscript outlines, each with an abstract drafted from the results that exist in this repository and the
exact files that back every number. **None has been submitted. All results are simulation (L2) or software (L3)
level; no hardware result exists, and every abstract says so.**

| # | File | Contribution (see `../00_Gap_Analysis_and_Plan.md`) | Evidence modules | Maturity of the evidence |
|---|---|---|---|---|
| 1 | `Paper_1_Adaptive_Soft_Switching_Twin.md` | A (primary): physics-informed online estimation for adaptive soft switching; observability limits of the protection-grade sensing chain | `../Digital_Twin` | L2 / L3 |
| 2 | `Paper_2_MPC_Feasibility_and_ZVS_Envelope.md` | same-plant benchmark of six controllers, C2000 execution budget, wide-range ZVS envelope | `../Adaptive_MPC`, `../Embedded_AI` | L2 / L1 (timing) |
| 3 | `Paper_3_Magnetics_Design_Verification.md` | window-level magnetostatic verification of the transformer; planar vs wound | `../FEM_Magnetics` | L1-L2 |
| 4 | `Paper_4_Robust_Design_and_Uncertainty.md` | B (secondary): robust / chance-constrained multi-objective design and UQ | `../Robust_Optimization`, `../Uncertainty_Quantification`, `../Multiphysics_Models` | L2 |

Novelty is not claimed beyond what the verified literature database supports; each outline lists the confirmed
related work it must be positioned against. Before submission each paper needs at least the validation step
named in its "Limitations" section (HIL for 1 and 2, an impedance-analyser / calorimetric measurement for 3,
measured tolerance data for 4).
