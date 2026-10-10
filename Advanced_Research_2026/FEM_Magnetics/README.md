# FEM_Magnetics - 2-D finite-difference magnetostatics of the DAB transformer window

Maturity: **L1-L2** (analytical / simulation with an in-house solver; no commercial FEM package, no hardware).
Scripts: `fd_magnetostatic.py` (solver + loss post-processing), `run_fem_magnetics.py` (study, regenerates
`results/` and `provenance.json`, ~2 min on one core, deterministic). Inputs: `04_Design_Calculations/design_values.json`,
`dabtools/dab/magnetics.py` (cores, Steinmetz/iGSE, litz Dowell), `06_Magnetics/magnetics_design.md`.

## 1. Purpose

The transformer in `06_Magnetics` (2 x E65/32/27, 3C95, 28:14, litz 294/588 x 0.1 mm, P/2-S-P/2) was designed with
closed-form estimates (Hurley-Woelfle leakage, strand-level Dowell). No FEM package is installed and none can be
installed in this environment, so a 2-D finite-difference magnetostatic solver was written in numpy/scipy
(sparse direct solve) to check (a) the leakage inductance, (b) the window field and the proximity-effect AC
resistance at 100 and 300 kHz, (c) a planar PCB-winding alternative, and (d) a small loss-volume-leakage Pareto
study of wound and planar variants.

## 2. Method and equations

**Field problem.** Translational 2-D approximation of the core window cross-section (x radial from the centre leg,
y axial along the window height, conductors along z with mean turn length `lw`). Vector potential `A_z`:

    -d/dx(nu dA/dx) - d/dy(nu dA/dy) = J_z,    nu = 1/(mu0 mu_r),   B_x = dA/dy,  B_y = -dA/dx,  H = B/(mu0 mu_r)

discretised on a uniform grid (node-based A, cell-based `mu_r` and `J`, five-point stencil, face reluctivity = mean of
the two neighbouring cells), Dirichlet A = 0 on the outer boundary, solved with `scipy.sparse.linalg.spsolve`.
The ferrite is modelled as a 3 mm thick region of `mu_r = 3000` (3C95 `mu_i` from `magnetics.py`) around the
window, so the high-mu wall condition (flux normal to the core, tangential H ~ 0) appears naturally. Windings are
uniform-current-density rectangles: for the litz design each layer of bundles is one rectangle (radial thickness =
bundle diameter, axial extent = turns x bundle diameter); for the planar design every PCB turn is a 70 um rectangle.
The current is enforced exactly on the rasterised area (`I / A_cells`).

**Leakage inductance** from the stored energy with primary and secondary ampere-turns balanced
(`N1 I1 = -N2 I2`, `I1 = 1 A` reference, referred to the HV side):

    W' = 1/2 sum B.H h^2  (= 1/2 sum A J h^2, checked),    L_lk = 2 W' lw / I1^2

**AC resistance (post-processing of the DC field, the Dowell/Ferreira assumption).**
Foil / PCB layers: 1-D eddy-current slab solution with the FD tangential face fields `Ha`, `Hb` of every layer,

    H(y) = [Ha sinh(k(t-y)) + Hb sinh(k y)] / sinh(k t),  k = (1+j)/delta,  J = -dH/dy,
    P_ac = int |J|^2/(2 sigma) dy,   P_dc = (Hb-Ha)^2 t /(2 sigma),   Fr = sum P_ac / sum P_dc

(this reproduces Dowell exactly when the layers span the window - see validation 2).
Litz layers: strand-level skin and proximity factors of Ferreira (1994) for a round strand of diameter `d = 0.1 mm`
(Kelvin functions, checked against the low-frequency limit `G -> pi sigma w^2 mu0^2 a^4 / 8`), applied cell by cell to
the FD field inside each bundle rectangle (strands uniformly distributed over the bundle):

    P_prox' = sum_cells (N_layer n_s / A_layer) h^2 G(xi) |H_pk|^2,    Fr = (Fs P_dc + P_prox) / P_dc

A 1-D "Sullivan" estimate (same strand factors, linear field ramp across each layer with the FD-free field
`N I / b_winding`) is reported next to the FD number, together with the design's own strand-level Dowell value.

**Core loss, volume, cost** (planar variants): Steinmetz x iGSE multiplier from `magnetics.py` with
`Bpk = V1/(4 fs N1 Ae)`; volume = core bounding box x 1.15 (wound, bobbin flanges) or x 1.3 (planar, PCB overhang);
cost = order-of-magnitude 2026 small-quantity figures in `COST` (not quotations).

## 3. Validation of the solver

| case | closed form | FD result | error |
|---|---|---|---|
| two full-height foils (2 mm each, 1 mm gap) in the E65 window, `L' = mu0/hw (d + (h1+h2)/3)` = 66.34 nH/m | 66.34 nH/m | 71.95 / 66.53 / 66.30 / 66.31 nH/m at h = 0.4 / 0.2 / 0.1 / 0.05 mm | +8.5 % / +0.28 % / -0.06 % / -0.04 % |
| Dowell, 3 + 3 full-height foils 0.25 mm, 100 kHz | Fr = 2.1114 | 2.1111 (FD field + slab) | -0.02 % |
| Dowell, same, 300 kHz | Fr = 8.3403 | 8.3379 | -0.03 % |
| energy consistency `1/2 sum B.H` vs `1/2 sum A J` | - | agree to < 1e-5 relative | - |

Figure `results/fig_validation_convergence.png`; data `validation_leakage_convergence.csv`, `validation_dowell.csv`.
Mesh convergence of the design case (layer edges are rasterised, so the sequence is not monotonic):
7.72 / 7.49 / 7.61 uH at h = 0.2 / 0.1 / 0.05 mm, i.e. +/-2 % discretisation uncertainty.

## 4. Results - wound E65/32/27 transformer (`results/fem_results.json`, `run_log.txt`)

**Geometry check (finding).** With the design's bundle diameters (packing 0.5: d1 = 2.43 mm, d2 = 3.43 mm) the four
bundle layers plus 2 x 0.15 mm polyimide and a 0.8 mm bobbin wall need 12.8 mm radially, but the E65 window is
11.7 mm wide. The model compresses the bundles by 0.905 (equivalent packing 0.61) to fit; the real build must achieve
that packing or the arrangement does not fit. Axially the layers occupy 30.7 mm of 44.2 mm (6.7 mm margins, consistent
with the 6 mm margin tape of `06_Magnetics`).

**(a) Leakage inductance, HV side**

| arrangement | design (closed form, `design_values.json`) | FD 2-D | discrepancy |
|---|---|---|---|
| P/2-S-P/2 (selected) | 4.10 uH | **7.61 uH** (h = 0.05 mm) | **+86 %** |
| P-S (non-interleaved) | 16.39 uH | 20.37 uH | +24 % |
| P-S-P-S | - | 7.35 uH | - |

Breakdown of the +86 % for P/2-S-P/2 (all numbers in `fem_results.json/wound/leakage_breakdown_P/2-S-P/2`):

| step | L_lk |
|---|---|
| design formula (`mu0 N1^2 lw/hw (h_ins + (h1+h2)/3) / 4`, h_ins = 1 mm, full window height) | 4.10 uH |
| 1-D with the actual layer thicknesses and insulation (0.15 mm), full window height | 3.20 uH |
| FD with the layers stretched to the full window height (must equal the previous row) | 3.20 uH |
| 1-D with the real winding height 30.7 mm instead of 44.2 mm | 4.61 uH |
| FD with the real layer heights (field fringing into the 6.7 mm end margins) | 7.61 uH |

So the design formula is low mainly because it uses the full window height for a winding that fills 70 % of it, and
because the fringing field in the margins (visible in `fig_field_wound_interleaved.png`) stores as much energy again.
The consequence for the converter is small: 7.6 uH is 12 % of the 64 uH series inductance (the external inductor is
gapped and sets the value; the design already states the leakage tolerance argument), but a measured leakage
"< 6 uH" in the test procedure of `06_Magnetics` section 6 should be relaxed to ~8 +/- 2 uH. The non-interleaved
P-S option reaches 20-25 uH (spacer sensitivity: +0.25/0.5/1.0 mm -> 21.1/22.7/24.9 uH, each at a higher bundle
compression), not the 16 uH / 40 uH quoted in the design note.

**(b) Field and proximity effect** (nominal 9.23 / 18.46 A rms, 100 C copper)

| quantity | design (`magnetics.py`) | FD + Ferreira (this work) | 1-D Sullivan estimate |
|---|---|---|---|
| peak H in the window at nominal peak current | 4.1 kA/m (1-D) | 7.5 kA/m | - |
| Fr1 (primary) 100 kHz, P/2-S-P/2 | 1.038 | **1.41** | 1.28 |
| Fr2 (secondary) 100 kHz, P/2-S-P/2 | 1.077 | **1.57** | 1.28 |
| Fr1 / Fr2 300 kHz, P/2-S-P/2 | - | 4.70 / 6.09 | 3.53 / 3.53 |
| Fr1 / Fr2 100 kHz, P-S | 1.153 / 1.307 | 2.06 / 2.54 | 2.09 |
| copper loss at the fundamental, P/2-S-P/2 | 7.41 W | **10.4 W** | - |
| copper loss, P-S | 8.6 W | 16.1 W | - |

The design's strand-level Dowell approximation (`litz_rac_ratio`, effective layer count `m sqrt(n)/2`) under-estimates
the proximity loss of the thick 294/588-strand bundles by a factor ~10 in `Fr - 1`; the 1-D Sullivan estimate and the
FD agree within the margin-fringing difference (1.28 vs 1.41). The 300 kHz factors are large (4.7 / 6.1) but the
third harmonic of the trapezoidal DAB current carries ~1/9 of the fundamental amplitude, so its contribution to copper
loss is ~(1/81) x 4.7 / 1.41 ~ 4 % of the fundamental loss - the fundamental-only numbers above are therefore within
~5 % of a harmonic-weighted result at the nominal point. Transformer total at nominal: 11.4 W core + 10.4 W copper =
21.9 W (design: 18.8 W). Fully interleaved P-S-P-S gives no further improvement (Fr1 1.41, Llk 7.35 uH).

Figures: `fig_field_wound_interleaved.png`, `fig_field_wound_noninterleaved.png` (|H| map, flux lines = A_z contours).

## 5. Results - planar PCB-winding alternative

Core: planar E64/10/50 (ELP64) pair, Ae 519 mm2, window 21.8 x 10.2 mm (catalogue values recalled, to be verified),
mu_r 3000, 3C95 Steinmetz data. Windings: stacked 6-layer boards with 70 um (2 oz) copper, 0.42 mm dielectric
between P and S layers (solid insulation for the 800 V class), 0.21 mm between same-winding layers, 0.49 mm between
boards, 1.0 mm margin to the core, 0.5 mm track gap; boards are paralleled (current / k per board). Layer order per
board "PSPSPP" = interleaved (4 P layers, 2 S layers).

| variant | cores | N1:N2 | boards | J1 / J2 (A/mm2) | Llk (uH) | Fr1 / Fr2 100 kHz | Fr1 / Fr2 300 kHz | Pcu (W) | Pcore (W) | Ptot (W) | volume (cm3) | cost (EUR, rough) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 | 1 | 30:15 | 3 | 22 / 43 | 0.69 | 1.00 / 1.00 | 1.01 / 1.00 | 77.2 | 5.4 | 82.6 | 86 | 180 |
| P2 | 2 (stacked) | 16:8 | 3 | 10 / 19 | 0.30 | 1.00 / 1.00 | 1.01 / 1.00 | 28.1 | 9.2 | 37.3 | 172 | 264 |
| P3 | 2 | 16:8 | 2 | 14 / 29 | 0.46 | 1.00 / 1.00 | 1.01 / 1.00 | 42.2 | 9.2 | 51.4 | 172 | 190 |
| P4 (PPPPSS, not interleaved) | 2 | 16:8 | 3 | 10 / 19 | 1.20 | 1.01 / 1.00 | 1.09 / 1.02 | 28.2 | 9.2 | 37.5 | 172 | 264 |
| P5 (0.21 mm P-S, basic insulation only) | 2 | 16:8 | 4 | 7 / 14 | 0.14 | 1.00 / 1.00 | 1.01 / 1.00 | 21.1 | 9.2 | 30.3 | 172 | 338 |
| P6 (0.42 mm P-S, 4 boards) | 2 | 16:8 | 4 | - | stack 10.7 mm > 10.2 mm window: infeasible | | | | | | | |

With 70 um copper the AC resistance factor is ~1.00 at 100 kHz and < 1.1 at 300 kHz (t/delta = 0.3-0.5), and the
interleaved planar leakage is 0.1-0.7 uH (< 1 % of the 64 uH series inductance). The problem is DC copper: 28 turns
at 9.2 A and 14 turns at 18.5 A need ~2.3 / 4.6 mm2 of copper per turn, which 2 oz PCB layers cannot provide inside a
10 mm planar window without a large number of paralleled boards. The copper loss is 2-4 x the wound design even with
two stacked cores (which doubles the core volume). This confirms the conclusion of `06_Magnetics` section 1
("planar attractive only for low turn counts") with numbers. Figure: `fig_field_planar.png` (P2).

## 6. Pareto study (`results/pareto_variants.csv`, `fig_pareto.png`)

| variant | Ptot (W) | volume (cm3) | Llk (uH) | cost (EUR) | Pareto-optimal (min loss, volume, Llk) |
|---|---|---|---|---|---|
| W1 E65 P/2-S-P/2 (design) | 21.9 | 130 | 7.6 | 61 | no (W3 dominates by 0.03 W / 0.26 uH - within model error) |
| W2 E65 P-S | 27.5 | 130 | 20.4 | 61 | no |
| W3 E65 P-S-P-S | 21.8 | 130 | 7.4 | 61 | yes |
| P1 planar 1 core | 82.6 | 86 | 0.69 | 180 | yes (smallest volume, 4 x the loss) |
| P2 planar 2 cores, 3 boards | 37.3 | 172 | 0.30 | 264 | no |
| P3 planar 2 cores, 2 boards | 51.4 | 172 | 0.46 | 190 | no |
| P4 planar 2 cores, PPPPSS | 37.5 | 172 | 1.20 | 264 | no |
| P5 planar 2 cores, 4 boards, basic insulation | 30.3 | 172 | 0.14 | 338 | yes (lowest leakage) |

Conclusion: the wound E65 litz design stays the right choice for 28:14 at 6.6 kW / 100 kHz; W1 and W3 are
equivalent within the model accuracy, so the simpler P/2-S-P/2 (two insulation layers instead of three) is kept.
The planar route only becomes competitive at low turn counts (n ~ 1, < 400 V) or with thick-copper / hybrid
(foil + PCB) windings, which are outside the 2 oz 6-layer constraint studied here.

## 7. Figures

* `results/fig_validation_convergence.png` - solver error vs cell size against the foil closed form
* `results/fig_field_wound_interleaved.png`, `fig_field_wound_noninterleaved.png` - |H| map and flux lines, E65 window
* `results/fig_field_planar.png` - |H| map and flux lines, planar P2
* `results/fig_pareto.png` - loss vs volume and loss vs leakage of all feasible variants

## 8. Limitations and what was NOT verified

* **2-D approximation**: translational symmetry with the mean turn length; no 3-D end-winding effects, no fringing
  around the bobbin flanges or at the core corners, no field in the core depth direction. Expect +/-10-20 % on the
  leakage against a 3-D solution or a measurement.
* **No FEM package**: in-house finite-difference solver; validated only against two closed forms (foil leakage,
  Dowell) and an energy-consistency check. No comparison with a commercial solver was possible.
* **Magnetostatic field**: eddy-current redistribution of the current is not in the field solve; AC resistance comes from
  the DC field (Dowell/Ferreira assumption, accurate while layer thickness < ~2 skin depths; the 70 um planar layers
  and the 0.1 mm strands satisfy this, the litz bundles are handled at strand level).
* **Litz model**: strands assumed uniformly distributed and perfectly transposed (no bundle-level circulating currents,
  no strand-level skin effect beyond `Fs`); bundles modelled as compressed rectangles (packing 0.61 instead of 0.5).
* **Fundamental only**: Fr at 100 and 300 kHz are given; the copper loss uses the fundamental (harmonic-weighted
  difference estimated ~5 % at nominal).
* **Planar core data** (ELP64/10/50 Ae, Ve, window) recalled from catalogue memory, not verified; planar insulation
  coordination (0.42 mm solid insulation as reinforced, creepage at the board edge, partial discharge) not assessed.
* **Costs** are order-of-magnitude assumptions, not quotations; **volumes** use bounding boxes with fixed overhang factors.
* **Temperature**: copper at 100 C, ferrite data at 100 C; no thermal coupling.
* **Nothing measured**: no transformer was built; the leakage and Fr numbers above are predictions (maturity L2 for the
  solver results, L1 for the cost/volume estimates).
