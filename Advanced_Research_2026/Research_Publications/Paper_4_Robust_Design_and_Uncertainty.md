# Paper 4 (secondary contribution B, reliability-aware design) - draft outline with results

**Working title:** Robust and chance-constrained multi-objective design of a 6.6 kW SiC dual active bridge:
why ZVS at the voltage-mismatch corners cannot be guaranteed under inductance tolerance, and what the
uncertainty actually depends on

**Target venue:** IEEE Transactions on Power Electronics (regular) or IEEE JESTPE; conference version at
COMPEL / ECCE.

**Validation level: L2 (analytical and semi-numerical project models, datasheet-typical device data flagged
`verified=False`, assumed input distributions). No measured tolerance statistics, no hardware.**

## Abstract (draft)

We extend the usual nominal Pareto design of a dual active bridge with four objectives - loss, magnetics volume,
a thermal-cycling damage proxy over an assumed bidirectional mission profile, and the worst-case ZVS margin -
and with three treatments of uncertainty (worst case over a Latin-hypercube set of +/-15 % inductance,
+/-20 % Coss, +30 % Rds_on aging, +/-25 % core loss, 25-55 C ambient; a 95 % chance constraint; and nominal).
NSGA-II (3660 evaluations per variant) dominates 71 % of an 8640-point exhaustive grid's non-dominated set,
and beats a Gaussian-process expected-improvement search at equal budget (hypervolume 0.361 vs 0.291 at 250
evaluations). The project's baseline design (100 kHz, 64 uH, n = 2) is within 3 % of the nominal front in loss
but dominated in magnetics volume (an ETD49 inductor core with two LV devices saves 44 cm3 at equal loss), and
it is infeasible under the robust and chance-constrained variants. A closed-form argument shows why: with SPS,
all corners share K = 2 pi^2 fs L P scaled by 1/(V1 V2'); zero-current ZVS at 650/450 V and 850/300 V needs
K >= 690 kV^2 while the 60 deg phase limit at 650/300 V caps K <= 855 kV^2, so ZVS at every full-power corner can
only be guaranteed for a +/-10.7 % inductance band at n = 2 (+/-12.7 % at n = 1.95), narrower still once the
Coss-based ZVS current and the 24 A peak limit are added - below the assumed +/-15 % tolerance, and no design in
3660 evaluations satisfies the strict robust variant.
Uncertainty propagation (Monte Carlo, LHS, order-3 polynomial chaos) shows nominal efficiency 98.61 +/- 0.05 %
dominated by core-loss and Rds_on uncertainty (total Sobol indices 0.52 and 0.26), while the corner efficiencies
and every ZVS margin are dominated by the inductance (indices 0.76-1.00); junction temperature is driven almost
entirely by ambient. The design consequence is a tolerance specification on the series inductance rather than
on the semiconductors.

## Sections and evidence

1. Introduction; multi-objective DAB design in the literature (`../Literature_Database`, confirmed entries only).
2. Models (`../Robust_Optimization/dab_eval.py`, project chain in `../../SiC_6k6_Industrial_DAB/04_Design_Calculations`).
3. Methods: NSGA-II, GP-EI (simplified single-objective BO), LHS worst case and chance constraint; knee selection
   by ideal-point distance - no weighted-sum score (`../Robust_Optimization/README.md` sec. 2).
4. Results: fronts and hypervolume (`results/pareto_*.png`, `convergence_hypervolume.png`), knee designs,
   baseline position (sec. 3.1-3.2), effect of the uncertainty treatment and the closed-form infeasibility
   argument (sec. 3.3), decision-variable patterns (sec. 3.4).
5. Uncertainty quantification of the baseline (`../Uncertainty_Quantification/README.md`): statistics table,
   Sobol indices PCE vs Saltelli (largest deviation 0.04), PCE accuracy by order, convergence of MC / LHS / PCE.
6. Reliability proxy and the multiphysics coupling (`../Multiphysics_Models`): ratios, not absolute lifetimes.
7. Design recommendations: inductance tolerance band; EPS/TPS for the corners; inductor core resize.

## Limitations

SPS in the optimisation loop; one-node thermal network; literature-typical lifetime coefficients; assumed
mission profile and input distributions; the Rds_on aging range is a placeholder for a measured degradation law.

## Reproducibility

`python3 ../Verification_Evidence/run_all.py Robust_Optimization Uncertainty_Quantification`.
