# Digital-twin software interface (proposal, L1)

## Data flow

```
C2000 firmware (100 kHz ISR)                      host twin (Python, 1 kHz / 10 Hz / background)
----------------------------                      -----------------------------------------------
per period: v1, v2, i2_avg, i1_avg, i_pk,  ---->  L1: regressor on the applied pattern, RLS/EKF -> L_est, sigma
            PWM registers (phi, D1, D2 counts),   L2: Foster observer -> Tj_est (both bridges)
            NTC, state, fault code                L3: slow drift of Rds_on / Coss (if the t_tr sensor exists)
            [t_tr1, t_tr2 if the sensor exists]   L4: supervisor -> (D1, D2) advisory + ZVS-margin forecast
                                            <----  advisory frame: D1, D2, L_est, confidence, twin status
```

The firmware's existing telemetry (`10_Firmware/src/dab_comm.c`: CRC-16 framed packets) is extended
with the PWM register values and the period-average currents (already computed for protection).
Advisory commands are consumed only in state RUN, pass `DABController.check_protection` and the
phase/D limiters, and are ignored when the twin status is not `TRUSTED` (sigma_L/L > 5 %, stale
frame > 20 ms, CRC error) - the firmware then keeps the fixed EPS schedule. Hardware protections
(comparator trips, interlock) are untouched by the twin.

## Frame contents

| Field | Type | Rate | Source |
|---|---|---|---|
| v1, v2 (V) | int16 (0.1 V) | 1 kHz (averaged over 100 periods) | ADC |
| i2_avg, i1_avg (A) | int16 (0.01 A) | 1 kHz | shunt / CT, averaged |
| i_pk (A) | int16 | 1 kHz | peak detector / max over the window |
| phi, D1, D2 | uint16 counts | 1 kHz | ePWM registers |
| T_ntc1, T_ntc2 (C) | int16 (0.1 C) | 10 Hz | NTC |
| t_tr1, t_tr2 (ns) | uint16 | 1 kHz | PROPOSED sensor |
| state, fault | uint8 | 1 kHz | state machine |
| CRC-16 | uint16 | - | as in dab_comm.c |

## Rates and budgets

* L1 estimator: one scalar RLS update per frame (1 kHz) on the host; a firmware version would cost
  ~30 multiply-adds per period (see `../Embedded_AI`).
* L2 observer: 2x2 Kalman at 1 kHz.
* L4 supervisor: 16 candidate evaluations of the period model (1200 samples each) - ~20 ms in Python;
  as a LUT in firmware it is a table look-up (see `../Adaptive_MPC`, explicit MPC / LUT sizing).

## Simulated-data labelling

Every dataset produced by this module is written under `results/` with `data_origin = SIMULATED` in
`provenance.json`. No file in this directory contains measured data.
