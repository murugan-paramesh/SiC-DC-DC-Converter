# Conventions for every module under Advanced_Research_2026/

1. Each module directory contains: `README.md` (purpose, method, results, maturity level, what was
   NOT verified), one or more Python scripts (numpy / scipy / matplotlib / pandas only; no torch,
   sklearn, cvxpy, LaTeX), a `results/` folder with JSON/CSV outputs and PNG figures that the scripts
   regenerate, and a `provenance.json` written by the script (python version, package versions, git
   commit, input file hashes, wall time).
2. Honesty rules: no fabricated measurements; synthetic data is labelled `SYNTHETIC` in file names
   and headers with the generating equations and seeds; no hardware-validation, certification or
   RUL-accuracy claims; infeasible regions, failed convergence and negative results are reported.
3. Maturity scale (sec. 28 of the research specification):
   L0 concept, L1 analytical, L2 simulation-validated, L3 software-verified (tests pass),
   L4 HIL-verified, L5 hardware-validated, L6 publication-ready with evidence. Nothing in this
   repository is above L3 (no hardware, no HIL, no FEM solver, no C2000 toolchain).
4. Project model API (import with `sys.path.insert(0, "<repo>/SiC_6k6_Industrial_DAB")`):
   * `dabtools.dab.dab_model`: `DABPoint(V1, V2, n, L, fs, phi, D1, D2)` -> `.P`, `.I_rms1`,
     `.I_peak1`, `.switching_currents()`, `.zvs_margin(port, I_min)`, `.backflow`;
     `sps_power`, `sps_phi_for_power`, `zvs_current_min(Coss_er, Vdc, L)`, `dead_time_required`,
     `tps_search`.
   * `dabtools.dab.sim_switched.DABPlant(L, n, fs, C1, C2, V1_src, R1_src, load, dead_time, N_sub, R_s)`
     with `.run_period(phi, D1, D2, record)` (one switching period, fixed-step), `.state()`.
   * `dabtools.dab.control.DABController(L, n, fs, kp, ki, ...)`, `.step(m)` -> (phi, D1, D2).
   * `dabtools.dab.devices.DEVICES`, `rds_on(dev, Tj)`; `dabtools.dab.losses.bridge_losses(...)`;
     `dabtools.dab.magnetics` (Steinmetz/iGSE, Dowell, litz, design_transformer, design_inductor).
   * Design values: `04_Design_Calculations/design_values.json` (L = 64 uH, n = 2, fs = 100 kHz,
     C3M0032120K HV bridge, C3M0016120K LV bridge, t_dead = 150 ns, E65/32/27 3C95 28:14, E55 inductor).
   * Control: `11_Control_Algorithms/control_params.json` (kp, ki, limits).
5. No model/vendor identifiers of the AI tooling in code or comments. Scripts must run from any cwd
   (`python3 <path>/script.py`) in under ~15 minutes on one core and be deterministic (fixed seeds).
