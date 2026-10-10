# Reliability engineering: FTA, FMEDA-lite and formal check of the controller state machine

**Maturity: L1 (FTA, FMEDA-lite: analytic with assumed class failure rates) / L3 (state machine: exhaustive model check,
C-code conformance and SIL harness executed).** No SIL level, no PFD/PFH, no certification is claimed anywhere in this
module; every failure rate is an order-of-magnitude class value entered as an assumption.

```
python3 Advanced_Research_2026/Reliability_Engineering/fta.py                   # < 2 s
python3 Advanced_Research_2026/Reliability_Engineering/fmeda_lite.py            # < 1 s
python3 Advanced_Research_2026/Reliability_Engineering/state_machine_check.py   # < 30 s (compiles the C code with gcc into a temp dir)
```

Inputs: `15_Safety_Reliability/01_insulation_coordination.md`, `02_FMEA.csv`, `16_BOM/bom.csv`, `10_Firmware/src/dab_control.c`,
`10_Firmware/sil/sil_main.c`, `dabtools/dab/control.py`. The firmware tree is read only; all builds go to a temporary directory.

## 1. Fault tree analysis (`fta.py`, `results/fta_cutsets.md`, `fta_cutsets.json`, `fta_trees.md` (Mermaid), `fig_fta_cutsets.png`)

Basic events: 32, rates in FIT (1e-9/h) of the IEC TR 62380 / SN 29500 class (assumptions, listed with their mode in
`fta_cutsets.json`); detected failures are repaired in 48 h, latent ones revealed by an annual proof test (unavailability
lambda T/2), human/systematic events are per-demand probabilities, `NO_DESAT` is a house event (TRUE for the rev A
UCC21520 drivers). Minimal cut sets by boolean expansion with absorption; rare-event frequency approximation.

| top event | minimal cut sets | lowest order | frequency (/year) | dominant cut sets (share) |
|---|---|---|---|---|
| TE1 hazardous voltage at an accessible part | 6 | **1** | 1.4e-4 | ISO_BIAS 50 % (8 basic-class bias modules, open item 15.1-4), ISO_DRV 25 %, ISO_AMC 22 %; DEV_PAD AND PE_BOND and the residual-energy set are negligible |
| TE2 overcurrent / shoot-through not interrupted within the device withstand time | 21 | 2 | 1.9e-4 | DRV_HIGH AND NO_DESAT 36 %, MCU AND NO_DESAT 23 %, XTALK AND NO_DESAT 23 %, UVLO AND NO_DESAT 18 %; the inductor-OC branch (CT AND comparator AND firmware) is 4 orders lower |
| TE2b = TE2 AND fuse fails to clear | 21 | 3 | 1.7e-9 | FUSE AND NO_DESAT AND SW_PWM 51 % |
| TE3 thermal runaway | 15 | 3 | 1.7e-9 | FAN AND NTC AND HOST 74 % (NTC open reads cold, no plausibility check) |

Reading. (1) The reinforced isolation barriers are single-point events by nature (that is what "reinforced" means); the
analysis simply makes visible that the eight **basic-class** bias modules are the largest contributor and confirms open
item 15.1-4 (reinforced-rated modules). (2) For TE2 every leading cut set contains `NO_DESAT`: with the UCC21520 a
shoot-through is interrupted only by the fuse (milliseconds), because the CT sees the inductor current, not the leg
current. Replacing the drivers by the UCC21710 class (DESAT, 99 % coverage assumed) divides the TE2 frequency by ~100
(`fta_cutsets.md`, variant). (3) TE3 is dominated by the NTC-open mode (reads cold); an NTC plausibility check (temperature
vs loss model and vs the second NTC) reduces TE3 by 4.4x. A CT plausibility check does not change TE2 (the CT branch is
already small) but is the main gain for the OC protection's diagnostic coverage (below).

Fault trees: `results/fta_trees.md` (Mermaid). Figures: `results/fig_fta_cutsets.png`.

## 2. FMEDA-lite for the protection functions (`fmeda_lite.py`, `results/fmeda_lite.csv`, `fmeda_lite.md`, `fmeda_summary.json`)

Each protection chain (divider -> AMC1301 -> TLV9062 -> LM393 / ADC -> 74HC32 / PROT_DIS -> driver DIS + TZ) is split into
failure modes classified safe (S), dangerous detected (DD) or dangerous undetected (DU); class rates in FIT, mode splits by
engineering judgement. DC = DD/(DD+DU), SFF = (S+DD)/total. **No SIL assignment** (needs certified data, systematic
capability and an independent assessor).

| function | lambda_S | lambda_DD | lambda_DU (FIT) | DC | SFF | main DU modes |
|---|---|---|---|---|---|---|
| OV HV | 6.5 | 19.9 | 36.8 | 35 % | 42 % | isolated 5 V loss (mid-scale reading), comparator no-trip, AMC gain drift, PROT_DIS stuck inactive |
| OV LV | 6.5 | 19.4 | 36.5 | 35 % | 41 % | as above; **AMC1301 gain drift is a common cause for regulation, firmware OV and hardware OV** (see HIL_Validation T03) |
| OC (inductor) | 3.6 | 10.0 | 16.6 | 38 % | 45 % | CT open / rectifier (reads zero) - single point for HW and FW |
| OT | 0.8 | 10.0 | 11.4 | 47 % | 49 % | NTC open reads cold |
| interlock | 38.5 | 0.0 | 17.5 | 0 % | 69 % | optocoupler / contact stuck "precharge ok" |
| DESAT / short circuit | 8.0 | 0.0 | 3.0 | 0 % | 73 % | rev A has no detection at all |

Proposed diagnostics, each converting named DU modes into DD: CT plausibility (|i_pk| vs the SPS power model at the
commanded phi), comparator pulse test at start-up (test level into the LM393 inputs, expect PROT_DIS), NTC plausibility,
V1/V2 cross-check against the power balance, parameter-block CRC, DESAT driver upgrade.

## 3. Formal check of the controller state machine (`state_machine_check.py`, `sm_conformance.c`, `results/state_machine_report.md`, `state_machine_results.json`, `sil_harness_output.txt`)

The state machine of `dab_ctrl_step()` was extracted into an explicit transition model (5 states, 13 abstract boolean
inputs: enable, precharge_ok, v1_low, v2_low, v1_ov, v2_ov, ipk_over, ot, driver_fault, hw_trip, comm_lost, ss_done,
pc_timeout; the two timers are abstracted as "done" inputs; an optional `clear` command before the step). BFS over the
reachable states with all 4608 physically consistent input combinations x clear/no-clear = **46 080 transitions**.

| property | result | detail |
|---|---|---|
| P1 (literal) every fault input leads to FAULT within one step | **FAIL** (456 transitions) | `v1_low`/`v2_low` are ignored outside RUN, `comm_lost` is ignored in INIT, `pc_timeout` acts only in PRECHARGE_WAIT - all by documented design (dead-bus start needs v2 < UV; the heartbeat is not required before enable) |
| P1' same, under the documented conditions | PASS | unconditional faults (hw_trip, driver, OV, I_PK, OT) -> FAULT from every state in one step |
| P2 FAULT is only left by an explicit clear | PASS | and re-faults in the next step if the condition persists (SIL scenario 3 confirms) |
| P3 gates_enabled false outside RUN / SOFTSTART and whenever a fault is detected | PASS | |
| P4 no deadlock; RUN reachable from every state; FAULT -> INIT in one step via clear | PASS | |
| P5 gates_enabled implies enable | PASS | |

**C-code conformance:** the unmodified `dab_control.c` was compiled with gcc together with `sm_conformance.c`, which drives
the same 46 080 (state, input, clear) cases; **0 mismatches** against the Python model (next state and gate enable).

**Python reference controller (`dabtools/dab/control.py`) vs the C code:** 71 mismatch classes over 23 040 cases, all
explained by three documented-nowhere differences: (a) the Python class has no `driver_fault` / `hw_trip` inputs, so it
never faults on them; (b) it has no 5 s precharge timeout; (c) in PRECHARGE_WAIT it ignores `enable = false` (the C code
returns to INIT). The control law is the same; the protection layer is not. This is a **documentation discrepancy**
(control.py says "same algorithm as the C control core"), not a firmware defect - reported, not fixed (firmware and dabtools
are outside this module's scope).

**SIL harness:** `10_Firmware/sil/sil_main.c` compiled (gcc -O2 -Wall -Wextra, no warnings) and run from a scratch
directory: **30 PASS, 0 FAIL, exit code 0** (the firmware README says "35 checks"; the harness as present contains 30
CHECK lines). Output in `results/sil_harness_output.txt`.

One observation from the model for the firmware owner: a `clear` command issued over CAN while the fault condition is still
present produces a one-period INIT -> FAULT bounce (gates stay off, so harmless), and `$C,CLR` is unauthenticated (see
`Cybersecurity/`).

## 4. Not verified

* All failure rates and mode splits are assumptions; no manufacturer FIT data, no field data, no common-cause beta factors.
* The FTA is static (no sequence dependence, no repair-time distribution); the demand-type events (ACCESS, SW_PWM, TZ_CFG) are placeholders.
* The state-machine model abstracts timers and treats the asynchronous `clear` as happening before a step; interrupt-level
  interleavings (clear arriving mid-step) were not modelled.
* Only the host build (gcc) was executed; the C2000 HAL remains uncompiled (no TI toolchain).
