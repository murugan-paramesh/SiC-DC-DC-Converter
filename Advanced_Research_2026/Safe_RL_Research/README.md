# Safe_RL_Research - constrained policy search for the DAB modulation (SIMULATION ONLY)

**Maturity: L2, exploratory. Simulation on the project's switched plant only. Nothing in this folder
is proposed for deployment; no learned policy ever commands hardware. Every command passes a
deterministic safety filter and a deterministic fallback controller.**

## 1. Question

Can a learned policy choose the modulation (phi, D1, D2) for a demanded power at given port voltages
with lower inductor rms current than the project's deterministic PI + EPS voltage matching, without
leaving the hard envelope? The reference optimum is the analytical TPS search of
`dabtools/dab/dab_model.py: tps_search`.

## 2. Architecture

```
policy (M1 or M2) --> SAFETY FILTER --> plant (DABPlant, N_sub = 200)
                        |  analytical model + limits from control_params.json / design_values.json
                        |  rejects or projects any command that predicts I_pk > 24 A, phi > 60 deg,
                        |  D < 0.4, or loss of ZVS (guard 0.5 A) at a point where ZVS is feasible
                        v
                 after 3 consecutive rejections: deterministic fallback (EPS reference) for the episode
```

| Method | What it is | Size |
|---|---|---|
| PI_EPS | the project's controller (EPS voltage matching, phi from the modulator inverse) | reference |
| TPS_analytical | `tps_search` optimum per operating point | reference optimum |
| M1_CEM | cross-entropy method (derivative-free) over the 115 weights of a residual 3-16-3 tanh policy: action = EPS reference + bounded correction; Lagrangian penalty with dual ascent on pre-filter violations | population 16, elite 4, 20 generations |
| M2_REINFORCE | constrained REINFORCE, tabular softmax over 25 discrete (D1, D2) pairs per context, phi solved analytically for the demanded power | 60 iterations, 18 contexts |

Contexts: V1 in {650, 800, 850} V x V2 in {300, 400, 450} V x P in {3.3, 6.6} kW = 18 operating points.
Training episodes 30 periods at N_sub = 100; evaluation 60 periods at N_sub = 200. These sizes were
shrunk to fit a 15-minute single-core budget; a larger search could change the M1/M2 numbers.

## 3. Results (`results/results_table.md`, `results/rl_results.json`)

| Method | mean I_rms (A) | relative to PI+EPS | max I_peak (A) | ZVS edges | fallbacks |
|---|---|---|---|---|---|
| PI_EPS | 8.118 | 1.000 | 18.43 | 76/104 | 0 |
| TPS_analytical | 8.088 | 0.996 | 18.25 | 72/100 | 0 |
| M1_CEM | 8.182 | 1.008 | 18.52 | 92/128 | 6 |
| M2_REINFORCE | 8.121 | 1.000 | 18.46 | 72/108 | 0 |

**Answer to the question: no benefit.** Neither learned policy beats the deterministic PI + EPS
schedule on rms current; the analytical TPS optimum itself is only 0.4 % better than PI + EPS over
these 18 points. On this plant and envelope the modulation problem is small enough to be solved
analytically, and the learned policies add risk and compute without a measurable gain.

### Constraint checks after the filter, by category

The evaluation counts four kinds of event per episode. They are not all safety violations.

| Event | PI_EPS | TPS | M1_CEM | M2 | Meaning |
|---|---|---|---|---|---|
| peak current > 32 A (hardware trip level) | 0 | 0 | 0 | 0 | **safety limit: never reached** |
| V2 outside 250-480 V | 0 | 0 | 0 | 0 | **safety limit: never reached** |
| hard switching at a point where ZVS is feasible | 0 | 0 | **2** | 0 | **filter failure** (see below) |
| delivered power error > 3 % | 6 | 6 | 6 | 7 | tracking accuracy of the open-loop phi in 60 periods; the baselines show it too |

The two M1 events (800/400 V/3.3 kW and 800/450 V/6.6 kW) are a real shortcoming of the filter: it
judges ZVS on the analytical model with a 0.5 A guard, and the switched plant loses ZVS at an inner
edge that the model predicted to be just above the guard. A larger guard or a filter built on the
lossy period model (as in `../Digital_Twin/twin.py: discrete_model_lossy`) is needed. The safety
limits proper (peak current, link voltage) held in every episode.

Diagnostic without the filter (`diagnostic_unfiltered` in the JSON): the raw M1 proposals would have
produced 18 envelope events (maximum peak 22.4 A), M2 7 events (18.5 A). The filter rejected 18 and
corrected 738 of 750 M1 commands; M2 never needed a correction because its discrete action set was
already inside the envelope.

### Transient check

50 -> 100 % load step with the PI loop and the M1 duty choice: V2 dip 1.50 V vs 1.46 V for PI + EPS,
maximum peak 12.1 A vs 12.0 A; the filter rejected 3 of 223 commands and the fallback was active for
377 periods. No benefit in the transient either.

Figures: `results/fig_rl_vs_analytical.png` (rms current per operating point and training curves),
`results/fig_transient.png`.

## 4. Safety case

* The policy output is advisory; the filter and the fallback are deterministic code paths whose
  behaviour does not depend on learned weights.
* The hardware protections (comparator trips, interlock) of `../../SiC_6k6_Industrial_DAB/` sit below
  the filter and are not reachable from it.
* A deployment would at least need: a filter on the lossy model with a validated margin, HIL testing
  (`../HIL_Validation`, proposed), and a formal argument that the fallback is reached within a bounded
  number of periods. None of this exists; this module stays exploratory.

## 5. Not verified

* Simulation only; the plant has ideal switches and no dead time.
* Small search budgets (population 16, 20 generations; 60 REINFORCE iterations).
* The ZVS judgement of the filter is model-based and was shown to be insufficient at two points.
* The power-error criterion uses an open-loop phi; in closed loop the PI removes it.
* No comparison with deep RL methods (no torch available); the conclusion "no benefit" applies to the
  methods and budgets tested here.

## 6. Reproduce

```
python3 safe_rl_modulation.py     # a few minutes on one core; seed 7; writes results/ and provenance.json
```
