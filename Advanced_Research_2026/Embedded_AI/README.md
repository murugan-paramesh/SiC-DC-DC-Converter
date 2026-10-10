# Embedded AI - fixed-point inference feasibility on the C2000

Module of `Advanced_Research_2026` (gap-analysis item 17). Question: which part of the research controllers of
`../Adaptive_MPC` (explicit-MPC law, TPS/EPS optimal-modulation map) can run inside the 10 us / 100 kHz control ISR
of an F28379D-class MCU, in what number format, at what memory and cycle cost - and is a small neural network ever
the right tool for it?

**Maturity: L2 for the algorithms (quantisation, training, bit-exact reference verified in simulation), L1 for every
WCET / cycle number (instruction-count estimate; no C2000 toolchain and no hardware in this environment).**

## 1. Files

| file | purpose |
|---|---|
| `embedded_inference.py` | (a) Q15 quantisation of the explicit-MPC LUT and of an MLP surrogate of the TPS/EPS map, errors, memory, operation counts, WCET; (b) decision; (d) writes the bit-exact test vectors. ~1 min. |
| `fixed_point_ref.py` | C-like integer-only reference of the two inference paths (`LutQ15`, `MlpQ15`), test-vector generator; run standalone it re-checks `results/test_vectors_*.csv` bit-exactly (exit code 0/1). |
| `scheduling.py` | (c) ISR / 10 kHz / 1 kHz / background split and the timing diagram. |
| `results/` | `embedded_report.json` (all numbers below), `empc_lut_q15.npz`, `tps_mlp_q15.npz`, `tps_eps_map_MODEL.csv` (training data, computed from the model - not measured), `test_vectors_lut_q15.csv`, `test_vectors_mlp_q15.csv`, `scheduling.json`, figures. |
| `provenance.json` | python/numpy versions, git commit, input-file hashes, wall time per script. |

Dependencies: numpy, pandas, matplotlib and `../Adaptive_MPC/dab_mpc_lib.py` (project model wrappers, switched
plant, explicit-MPC controller). No torch/sklearn; the MLP is trained with hand-written numpy back-propagation.

## 2. Method

### 2.1 Fixed-point format and arithmetic (mirrored in C)

Q1.15: `int16` x represents x / 32768. `mul_q15(a, b) = sat16((a*b + 2^14) >> 15)`. LUT axes are uniform; the index
is `(x - x0) * inv_step >> 20` with `inv_step = round(2^20 / step)` (int32 product), the interpolation fraction
`((x - x0) - i*step) * inv_step >> 5`, inputs clamped to the axis range. The MLP uses Q15 weights with a per-layer
power-of-two shift, biases in the accumulator format, int64 accumulation of the Q30 products, rounding and saturation
to int16 after each layer, ReLU = `max(x, 0)`. Hidden activations are calibrated on the training set and scaled by
2^-k (k = 3 and 4 for the two hidden layers) so that they fit Q15; the scale is folded into the weights, the float
network function is unchanged.

### 2.2 Explicit-MPC LUT (from `../Adaptive_MPC/results/empc_lut.npz`)

Inputs (e = v2_ref - v2, V1, P_hat = d_hat * v2_ref) normalised to Q15 with full scales 16 V / 128 V (offset 750 V)
/ 8192 W; the axis steps (0.75 V, 25 V, 660 W) are exactly representable. Output phi / (pi/2) in Q15
(LSB 0.0027 deg, PWM step is 0.36 deg).

### 2.3 TPS/EPS optimal-modulation map and MLP surrogate

Training data: for every (V1, V2, P) on 9 x 7 x 20 nodes (650-850 V, 300-450 V, +/-10..100 % of 6.6 kW) the
(D1, D2, phi) with minimum rms inductor current subject to ZVS at every edge of both bridges (energy criterion of
`dab_model.zvs_current_min` with C_par, as in 04_Design_Calculations), on a 25 x 25 grid of D1, D2 in [0.4, 1] with
phi found by bisection on the exact piecewise-linear period model (`dab_mpc_lib.pwl_period`, validated against
`DABPoint`). Where no ZVS-feasible point exists (33 % of the nodes, light load) the minimum-rms point is stored and
flagged `zvs_ok = False`. Cross-check against `dabtools.dab.dab_model.tps_search` (coarser 13-point grid): at
650/450 V, 6.6 kW tps_search gives I_rms = 11.26 A (D2 = 0.70), ours 11.16 A (D2 = 0.775); at the two other
check points tps_search finds no ZVS-feasible point on its coarse grid while the fine grid does.
MLP: 3-16-16-3, ReLU, inputs normalised to [-1, 1], outputs (phi/(pi/2), (D1-0.7)/0.3, (D2-0.7)/0.3), Adam with
cosine learning-rate decay, 15 000 full-batch epochs, 80/20 split, seed 20260101. Validation on 150 random
off-grid points whose truth comes from the same optimiser.

### 2.4 WCET model

Same per-operation cycle assumptions as `../Adaptive_MPC` (2 cycles per add/mul incl. load/store, 8 per TMU
divide/sqrt, 4 per compare+branch, 200 MHz); fixed-point MAC counted as mul + add + load (a `RPT || MAC` loop would
halve it). ISR entry/exit, ADC and EPWM register access (+120 cycles) are accounted separately in the schedule.

## 3. Results

### 3.1 Quantisation error, memory, WCET

| path | memory | error vs float / vs truth | ops | cycles | us | % of 10 us ISR |
|---|---|---|---|---|---|---|
| explicit-MPC LUT, Q15 trilinear, 33x9x23 | 13.3 KB (26.7 KB float32) | Q15 vs float LUT: max 0.067 deg, rms 0.003 deg; float LUT vs exact QP law: max 0.85 deg, rms 0.14 deg (p99 0.55 deg) | 69 | 176 | 0.88 | 8.8 % |
| TPS LUT, Q15 trilinear, 9x7x20 x 3 outputs | 7.4 KB | vs optimiser (off-grid): phi rms 0.36 deg, max 2.2 deg; D rms 0.034, max 0.22 | 141 | 348 | 1.74 | 17 % |
| MLP 3-16-16-3, Q15 | 0.84 KB (387 params) | Q15 vs float MLP: phi rms 0.028 deg, max 0.074 deg, D max 0.021; float MLP vs optimiser (off-grid): phi rms 1.49 deg, max 6.3 deg; D rms 0.037, max 0.20 | 1231 | 2596 | 13.0 | 130 % |
| MLP 3-16-16-3, float32 FPU | 1.5 KB | as float MLP above | 1164 | 2398 | 12.0 | 120 % |
| analytic SPS inverse + EPS matching (float, firmware today) | ~0 | exact (model) | 35 | 118 | 0.59 | 5.9 % |
| PI + inverse + EPS (firmware control core) | ~0 | - | 46 | 144 | 0.72 | 7.2 % |
| proposed ISR core: observer + explicit LUT + EPS + DC-free transition | 13.3 KB | - | 133 | 342 | 1.71 | 17 % |

Closed loop on the switched plant (load step 10 -> 100 %, 800/400 V): float LUT peak deviation 0.262 %, settling
0.23 ms, ITAE 1.25; Q15 LUT 0.264 %, 0.24 ms, ITAE 1.22 - the quantisation is invisible in the loop
(`embedded_report.json: explicit_lut.closed_loop_load_step`).

Figures: `results/quantisation_errors.png` (training curve, Q15 LUT error histogram, surrogate error histograms),
`results/tps_map_vs_mlp.png` (map vs MLP at three voltage pairs), `results/wcet_memory.png`.

### 3.2 Decision: LUT vs MLP vs analytic inverse

* **Explicit-MPC law -> Q15 LUT.** 13.3 KB (flash or RAM, both available on the F28379D), < 1 us, deterministic,
  quantisation error 200x below the PWM step. The online QP it replaces (CCS-MPC) needs 10.5-28 us per period and
  does not fit the ISR (`../Adaptive_MPC/results/c2000_feasibility.json`).
* **Modulator inverse (SPS/EPS) -> analytic, float32.** 0.6 us, exact, no table, and it is the path the PI
  fallback uses - keeping it identical makes the hand-over between explicit MPC and PI continuous.
* **TPS/EPS map -> LUT if TPS is ever enabled (7.4 KB, 1.7 us), not the MLP.** The MLP is 9x smaller in memory
  but needs 7x the cycles of the LUT, exceeds the ISR budget on its own (12-13 us), and is 4x less accurate on
  phi (rms 1.5 deg vs 0.36 deg) because the min-rms map has plateaus and jumps between D1/D2 branches that a
  16-16 ReLU network smooths over. Memory is not the scarce resource here; cycles and determinism are.
* The MLP only becomes attractive when the input dimension grows (adding L_hat and Tj to the map would make a
  5-D LUT of several hundred KB); the fixed-point reference and test vectors are kept for that case.
* Nothing is learned on the MCU: training and table generation are offline (PC); the only on-line adaptation is
  the scalar RLS of `../Adaptive_MPC` (1/L), which is a 10-operation update, not an "AI" component.

### 3.3 Scheduling proposal (`scheduling.py`, `results/scheduling_timing.png`)

| level | content | estimate |
|---|---|---|
| 100 kHz EPWM ISR (10 us budget) | ADC results (v1, v2, i2 average, i_pk) and scaling, protections/state machine, disturbance observer, explicit-MPC LUT (CV) or analytic inverse (CP / PI fallback), EPS matching, DC-free transition edge move, EPWM shadow writes, fallback checks | 3.2 us (32 %) |
| 10 kHz task (every 10th period, pre-emptable) | RLS update of 1/L (one `pwl_period` regressor + scalar RLS), ZVS-margin / edge-current estimate | 4 us per 100 us |
| 1 kHz task | L_hat validation and fallback decision, LUT input rescaling with L_hat, adaptive dead-time table look-up, thermal derating, telemetry frame | 5.5 us per 1 ms |
| background | CAN/SCI, command parser, fault log, logging | - |

CPU load estimate 37 %. Explicitly **not** in the ISR: the online QP (CCS-MPC), FCS-MPC enumeration (~100 us) and
MLP inference.

### 3.4 Bit-exact reference (`fixed_point_ref.py`)

`results/test_vectors_lut_q15.csv` (263 vectors: 63 corner combinations incl. int16 extremes, 200 random) and
`results/test_vectors_mlp_q15.csv` (227 vectors) hold int16 inputs and the expected int16 outputs of the Python
integer implementation. A C port is checked by feeding the same inputs and comparing outputs exactly;
`python3 fixed_point_ref.py` regenerates the vectors from the stored `.npz` models and verifies the CSVs (exit 0).
The arithmetic conventions a C port must reproduce (rounding, shift directions, saturation points, int64
accumulator for the MLP) are listed in the module docstring.

## 4. Maturity and what was NOT verified

* L2: quantisation, training, closed-loop effect of the Q15 LUT, bit-exactness of the Python integer reference
  against itself (regeneration) - all simulation.
* L1: every cycle/us/ISR-fraction number. They come from operation counts and assumed cycles per operation; no C2000
  compiler, no cycle-accurate simulator, no hardware. Real figures depend on compiler optimisation, memory wait
  states (flash vs RAM), the TMU/FPU pipeline and interrupt latency; a factor 2 either way is plausible.
* Not verified: C code itself (none written here - the Python integer reference is the specification); EPWM
  support for the per-half-period edge move of the DC-free transition (needs shadow loads at both ZERO and PRD events);
  the ADC chain for the period-average LV current (the current design has a peak detector, not an averaging channel);
  behaviour of the TPS map under losses, dead time and parameter tolerance (lossless model); MLP generalisation
  outside the 650-850 V / 300-450 V / +/-6.6 kW box (it saturates, it is not valid there).
* Not benchmarked: alternative network sizes or activation tables (tanh), CLA offloading, hand-written assembly.
