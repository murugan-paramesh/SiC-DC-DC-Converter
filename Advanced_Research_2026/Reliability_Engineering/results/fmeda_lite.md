# FMEDA-lite summary (class failure rates in FIT, assumptions; NO SIL claim)

| protection function | lambda_S | lambda_DD | lambda_DU | DC = DD/(DD+DU) | SFF | comment |
|---|---|---|---|---|---|---|
| OV_HV | 6.5 | 19.9 | 36.8 | 35 % | 42 % | AMC1301 channel shared by HW and FW paths (common cause); comparator untested |
| OV_LV | 6.5 | 19.4 | 36.5 | 35 % | 41 % | gain drift of U6 is common cause for regulation and OV (see HIL T16) |
| OC | 3.6 | 10.0 | 16.6 | 38 % | 45 % | CT is a single point for HW and FW; plausibility check is the cheapest DC gain |
| OT | 0.8 | 10.0 | 11.4 | 47 % | 49 % | firmware-only; NTC open reads cold (DU) |
| INTERLOCK | 38.5 | 0.0 | 17.5 | 0 % | 69 % | stuck-true input is DU; v1 guard mitigates |
| DESAT_SC | 8.0 | 0.0 | 3.0 | 0 % | 73 % | rev A: no detection, DC = 0 by construction |

Rev A diagnostic gaps ranked by lambda_DU: OV_HV (36.8 FIT), OV_LV (36.54 FIT), INTERLOCK (17.5 FIT), OC (16.56 FIT), OT (11.4 FIT), DESAT_SC (3.0 FIT)

Proposed diagnostics (each converts the named DU modes to DD): (1) CT plausibility: |i_pk| vs the SPS power model at the commanded phi (OC: CT open/short, rectifier); (2) comparator pulse test at start-up: inject a test level into the LM393 inputs through a DAC/GPIO and expect PROT_DIS (OV/OC comparators, 74HC32, TZ arming); (3) NTC plausibility: heatsink temperature vs the loss model and vs the second NTC (OT: NTC open); (4) V1/V2 cross-check: V2 x n vs V1 at the EPS matching point and the HV/LV power balance (AMC gain drift); (5) flash/RAM CRC of the parameter block (threshold corruption); (6) DESAT driver upgrade (UCC21710) for the short-circuit function.
