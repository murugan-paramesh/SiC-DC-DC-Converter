# Paper 3 (secondary contribution, magnetics) - draft outline with results

**Working title:** Window-level magnetostatic verification of a litz-wound 6.6 kW / 100 kHz DAB
transformer: leakage, proximity loss and a planar alternative - what closed-form design formulas miss

**Target venue:** IEEE ECCE / APEC (conference), IEEE Transactions on Magnetics or TPEL letter.

**Validation level: L1-L2 (in-house 2-D finite-difference solver validated against closed forms,
no commercial FEM, no measurement). The title and abstract must say "numerical", not "measured".**

## Abstract (draft)

The transformer of a 6.6 kW, 100 kHz, 800 V / 400 V SiC dual active bridge (2 x E65/32/27, 3C95,
28:14, litz 294/588 x 0.1 mm, P/2-S-P/2) was designed with the usual closed-form leakage and
strand-level Dowell estimates. A 2-D finite-difference magnetostatic solver of the winding window
(validated to -0.04 % against the foil-winding leakage formula and to -0.03 % against Dowell for a
3+3 foil stack) shows three things the closed forms miss: (1) the leakage inductance is 7.6 uH, not
4.1 uH, because the formula assumes full window height and 1 mm insulation while the real layers fill
30.7 of 44.2 mm and the end margins add fringing (+86 %; still only 12 % of the 64 uH series
inductance, so the external inductor absorbs it); (2) the proximity factors at 100 kHz are
1.41 / 1.57 instead of 1.04 / 1.08, i.e. 10.4 W copper loss instead of 7.4 W, and 4.7 / 6.1 at
300 kHz; (3) the design's litz bundles need 12.8 mm radially in an 11.7 mm window (packing factor
0.61 required), so the winding as specified does not fit without a smaller bundle or a third layer.
A planar PCB-winding alternative on an ELP64 pair with 2 oz 6-layer stacked boards reaches Fr ~ 1.00
and 0.1-0.7 uH leakage but 21-77 W copper loss at this current, confirming the wound choice; a
loss-volume-leakage Pareto table of wound and planar variants is given.

## Sections

1. Introduction: closed-form vs FEM design flows for MF transformers; the 2022-2026 planar /
   leakage-integration literature (`../Literature_Database`: L23, L24 and the confirmed planar entries).
2. Solver: A_z formulation, five-point stencil, high-mu core wall, sparse direct solve, convergence
   study (`results/validation_leakage_convergence.csv`, `fig_validation_convergence.png`).
3. Validation against closed forms (`results/validation_dowell.csv`).
4. Wound design: leakage breakdown (formula -> 1-D real layers -> winding height -> 2-D fringing),
   field maps interleaved vs non-interleaved (`fig_field_wound_*.png`), proximity and copper loss,
   the packing-factor finding and the corrected design options.
5. Planar alternative (`fig_field_planar.png`, `results/pareto_variants.csv`).
6. Pareto discussion (`fig_pareto.png`), cost labelled as order-of-magnitude.
7. Impact on the converter: leakage absorbed by L_ext; copper-loss delta (+3 W) vs the 92 W loss
   budget; recommendation to re-specify the litz bundle (fill the "Not verified" list honestly).
8. Limitations: 2-D, no end-turn effects, no core-loss change, no thermal coupling, no measurement;
   proposed measurement plan (impedance analyser short-circuit test, calorimetric copper loss).

## Reproducibility

`python3 Verification_Evidence/run_all.py FEM_Magnetics` (232 s on one core; seeds and versions in
`FEM_Magnetics/provenance.json`).
