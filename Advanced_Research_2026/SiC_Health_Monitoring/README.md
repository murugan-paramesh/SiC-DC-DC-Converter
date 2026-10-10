# SiC health monitoring: Rds_on / Vgs_th drift as degradation indicators (feasibility and sensor-requirement study)

**Maturity: L2 on SYNTHETIC data only.** No measured aging data exists in this project, no device has been
cycled, and **no remaining-useful-life (RUL) accuracy is claimed**. Every data file in `results/` is labelled
`SYNTHETIC` and carries the generating equations and seed in its header. The deliverable is a feasibility
study: *could* the project's sensing chain detect a 1 % Rds_on drift, and what would a V_ds,on sensor need?
The present DAB design has **no V_ds,on sensor**; section 6 proposes one.

Scripts (run from any cwd, deterministic seeds 20261010 / 20261011, total < 20 s):

```
python3 Advanced_Research_2026/SiC_Health_Monitoring/01_generate_synthetic_data.py
python3 Advanced_Research_2026/SiC_Health_Monitoring/02_estimators_and_detection.py
```

## 1. Degradation indicators and why they are confounded

| Mechanism | Indicator | Model used here (assumption, literature-typical order of magnitude) |
|---|---|---|
| Bond-wire lift-off / die-attach fatigue (thermo-mechanical, power cycling) | Rds_on rises, Rth_JC rises | Coffin-Manson-Arrhenius damage `N_f = A dTj^-4.4 exp(0.08 eV / kB Tm)`, `D = sum 1/N_f`, `dR/R0 = 0.05 D^1.5` (+5 % = end of life, AQG 324-type criterion) |
| Gate-oxide charge trapping (positive gate bias, HTGB-type) | Vgs_th drifts up, channel resistance up | `dVth = 0.08 V log10(1 + t/100 h)` (~0.19 V after 3 years); channel share f_ch = 0.4 of Rds_on scales with `(Vgs_on - Vth0)/(Vgs_on - Vth0 - dVth)` |

Both mechanisms raise the on-state resistance; from Rds_on alone they cannot be separated (the synthetic
"degrading" scenario contains both: +7.1 % total after 3 years of which ~0.6 % is the Vth share, see
`results/fig_synthetic_truth.png`). A Vth measurement needs a dedicated circuit (gate current source at turn-on
with V_gs sampling, or an off-line pulse test at power-up) - **proposed only, not designed**.

Device: C3M0032120K (HV bridge), `rds_on(dev, Tj)` of `dabtools.dab.devices` (datasheet-typical, `verified=False`):
R25 = 32 mOhm, R150 = 52 mOhm, i.e. **0.5 %/K** of R25. A 1 K temperature error therefore equals a 0.5 % apparent
drift - one tenth of the end-of-life criterion. This single number drives the whole sensor requirement.

## 2. Synthetic generator (01_generate_synthetic_data.py)

Mission: 3 years hourly; load fraction U(0.2, 1) x daily pattern, V1 ~ U(650, 850) V, V2 ~ U(300, 450) V,
Tamb = 35 + 10 sin(daily) + 5 sin(annual) C. Tj from the 13_Thermal_Analysis network (forced air 0.22 K/W,
TIM 0.35 K/W, RthJC 0.45 K/W) with Rds_on(Tj) feedback; range 20-53 C (this converter runs cold: Tj - Tcase
is at most ~4 K at the worst corner). Damage from hour-to-hour Tj swings plus one on/off cycle per day;
A is calibrated so that D = 1 at 2.5 years (`A = 1.6e5`) - this is a *scenario choice*, not a lifetime estimate.

Measurement chain (the project's sensing components, V_ds,on path proposed as in section 6):

| Quantity | Chain | Resolution / errors modelled |
|---|---|---|
| V_ds,on | 1:4 divider -> AMC1301 (gain 8.2) -> TLV9062 -> 12-bit ADC (3.3 V) | LSB 0.39 mV at the device; gain error 0.3 % + 50 ppm/K; offset 0.2 mV + 3 uV/K; noise 1 mV rms |
| I_d (sample) | CT 1:100, 6.2 Ohm burden, 40 A FS, 12 bit | LSB 9.8 mA; ratio error 1 % + 100 ppm/K; noise 30 mA rms |
| T | (a) heatsink NTC (current design), (b) case sensor, (c) junction estimate from a thermal model | (a) bias P_dev (RthJC + Rth_tim), 1 K noise; (b) bias P_dev RthJC, 0.5 K; (c) slow random bias 1 K rms, 0.5 K noise |

Files: `SYNTHETIC_mission_*.csv`, `SYNTHETIC_truth_*.csv`, `SYNTHETIC_meas_<scenario>_<Tsensor>.csv`,
`SYNTHETIC_generator_params.json` (all coefficients), `provenance_generator.json`.

## 3. Estimators (02_estimators_and_detection.py)

1. **Temperature-compensated Rds_on**: `R25_hat = (V_ds / I_d) rds(25) / rds(T_meas)`; samples below 40 % of the
   nominal sample current are discarded (excitation gating - at light load the 1 mV / 30 mA noise is > 1 %).
2. **RLS** (2 parameters, forgetting 0.9995): `V_ds = I_d theta0 + I_d (T - 25) theta1`; theta1 estimates the
   temperature coefficient from the data (self-calibration against datasheet tolerance).
3. **Kalman filter** on R25_hat: state [level, rate], random-walk rate, gives a smoothed level with a 2-sigma band.
4. **CUSUM** on weekly means of R25_hat in relative units: `g = max(0, g + (block/mu0 - 1) - k)`, k = 0.5 %
   (half of the 1 % drift to detect), threshold h in fraction x weeks; baseline mu0 = first 13 weeks.

A first version standardised the CUSUM with the baseline standard deviation of 13 weekly means; it produced
60-90 % false alarms on healthy data because 13 blocks estimate sigma and mu0 too poorly (negative result, documented
here; the relative-units design above fixes it).

## 4. Results (24 Monte-Carlo noise realisations per setting; `results/detection_tables.md`, `detection_results.json`)

Single realisation (`fig_estimators_demo.png`): with the heatsink NTC the Kalman level ends at 6.66 % against a
true 7.08 % (bias from the 0.9 K mean temperature error); with a case sensor 6.46 % vs 7.08 % (the Kalman level
lags the accelerating truth); the RLS temperature coefficient oscillates with the annual ambient cycle around
the datasheet value (19-22 mOhm per 125 K vs 20) because the seasonal Tj swing is small compared with the noise.

Detection delay vs false alarm rate (CUSUM, k = 0.5 %):

| T sensor | h | false alarm frac (healthy, 3 y) | detect frac | alarm relative to the 1 % crossing, mean / p90 (days) | true dR at alarm, mean / p90 (%) |
|---|---|---|---|---|---|
| heatsink NTC (current design) | 0.5 % | 0.00 | 1.00 | -3 / +8 | 0.99 / 1.04 |
| heatsink NTC | 2.0 % | 0.00 | 1.00 | +36 / +45 | 1.17 / 1.21 |
| case sensor | 0.5 % | 0.00 | 1.00 | +1 / +10 | 1.00 / 1.05 |
| case sensor | 2.0 % | 0.00 | 1.00 | +41 / +52 | 1.19 / 1.24 |
| junction model (1 K slow bias) | 0.5 % | 0.62 | 1.00 | -41 / +1 | 0.82 / 1.00 |
| junction model | 1.5 % | 0.08 | 1.00 | +11 / +59 | 1.05 / 1.27 |
| junction model | 2.0 % | 0.00 | 1.00 | +26 / +90 | 1.12 / 1.41 |

Sensitivity to the temperature measurement (case sensor, h = 2 %):

| Temperature error | false alarms | alarm rel. to 1 % (days) |
|---|---|---|
| random sigma_T 0.5 ... 10 K | 0.00 | +37 ... +23 (averaging over ~100 gated samples per week removes random error) |
| load-dependent bias x0 ... x2 of P_dev (RthJC + Rth_tim), stationary mission | 0.00 | +38 ... +35 |
| same with a +30 % load shift after 1.5 years | 0.00 | +37 (bias change ~0.4 K = 0.2 % in this cold-running design) |
| slow sensor drift 1 K over 3 years | 0.00 | +25 |
| **slow sensor drift 2 K over 3 years** | **1.00** | +14 |
| slow sensor drift 3 / 5 K over 3 years | 1.00 / 1.00 | +6 / -10 |

Reading: in the synthetic world the 1 % drift is detected 1-7 weeks after it occurs with zero false alarms in
3 years, *provided the temperature reference does not drift by more than ~1 K over the service life*. Random
temperature noise up to 10 K and the load-dependent heatsink-to-junction offset are harmless because the
estimator averages weekly and because this converter's Tj - Tcase is only 1-4 K. The dominant risk is a slow
systematic error (NTC ageing, thermal-interface degradation which changes the NTC-to-junction offset, a sensor
replacement) - exactly the kind of error that a synthetic study cannot bound; it must be measured.

Sensor requirement (`fig_sensor_requirement.png`, analytic 3-sigma of a weekly mean, random errors only):

| V_ds noise (mV rms) | sigma_T = 0.5 K | 2 K | 10 K |
|---|---|---|---|
| 0.1 | 0.15 % | 0.26 % | 1.09 % |
| 1.0 (modelled chain) | 0.20 % | 0.29 % | 1.09 % |
| 3.0 | 0.43 % | 0.48 % | 1.16 % |
| 10 | 1.36 % | 1.38 % | 1.73 % |

The modelled chain (1 mV, 0.39 mV LSB, 30 mA current noise) resolves 0.2-0.3 % on weekly means; a 10 mV-class
sensor (e.g. an un-divided 2 V-span channel) would not resolve the 1 % level. Systematic temperature error adds
0.47 %/K directly (the datasheet tempco of R25 referred to R(40 C)).

## 5. Negative results and limits

* Rds_on alone cannot separate bond-wire fatigue from Vth drift; the Vth share (~0.6 % of 7 %) is below the detection level anyway.
* The Kalman rate state is not useful for RUL: the synthetic aging law is a power law in D with an assumed exponent, so extrapolation only reproduces the assumption.
* The aging coefficients (alpha, Ea, A, k_EOL, gamma, a_vth) are literature-typical orders of magnitude; the detection *delay in days* scales with the assumed drift rate and must not be quoted as a property of the device.
* Only one HV device was modelled; the LV device (C3M0016120K, 16 -> 27 mOhm) has the same 0.5 %/K sensitivity and half the V_ds (worse resolution).

## 6. Proposed V_ds,on sensing circuit (PROPOSAL - not in the schematic, not simulated at circuit level)

Per monitored device (one per bridge minimum: Q1 and Q5): a 1200 V fast diode from the drain to a sense node that
a 1 mA current source pulls up when the device is on (desaturation-detector topology); the sense node is clamped to
~5 V when the device is off; 1:4 divider -> AMC1301 (the project's isolated amplifier, +/-250 mV input, reinforced)
-> TLV9062 -> ADC. ADC start-of-conversion placed by the EPWM at the mid-conduction point (blanking >= 300 ns
after the edge). Requirements derived above: resolution <= 0.4 mV at the device (12 bit over a 1 V span), gain drift
< 50 ppm/K, offset drift < 10 uV/K, current at the sample instant within 0.5 % (the CT path needs a sampled
instantaneous value, not the peak detector of the current design), and a temperature reference within 1 K of
Tj *over the service life* (case-mounted sensor plus thermal-model correction, periodic self-check against the
heatsink NTC). Cost: one isolated channel (AMC1301 + isolated 5 V) per device, ~2 x 1 W bias modules, 2 ADC channels.

## 7. Not verified

* No measured aging data, no power-cycling test, no RUL accuracy; no hardware exists.
* The AMC1301 / CT / ADC error figures are datasheet-typical values recalled from memory, to verify.
* The temperature coefficient of `rds_on()` is a linear interpolation of two datasheet points.
* The V_ds,on sensing circuit has not been simulated (dynamic settling, diode reverse recovery, clamp leakage).
