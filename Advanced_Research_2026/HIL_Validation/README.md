# HIL validation: architecture (PROPOSED, not executed) and automated fault-injection suite (SIL, executed)

**HIL is PROPOSED only - no real-time simulator, no C2000 toolchain and no hardware exist in this environment; what was
executed is a software-in-the-loop (SIL, L3) fault-injection suite on the Python plant and the Python reference controller.**
Maturity: L3 for the SIL suite (19 tests run, pass/fail recorded), L0 for the HIL architecture.

```
python3 Advanced_Research_2026/HIL_Validation/sil_fault_injection.py     # ~1-4 min (19 tests, switched plant, 200 sub-steps/period)
```
Outputs: `results/sil_results.md` / `.csv` / `.json`, `results/fig_sil_traces.png`, `results/provenance.json` (seed 20261012).

## 1. Proposed HIL architecture

```
+------------------------------+        analog 0-3.3 V, digital        +-----------------------------------+
|  real-time simulator (FPGA)  | ----- V1_SE, V2_SE, I_L(peak), NTC --> |  LAUNCHXL-F280049C (real firmware) |
|  DAB plant: L, n, C1, C2,    | <---- 8 x PWM (EPWM1-4 A/B), DIS ----- |  10_Firmware/src + hal/c2000       |
|  source/load, dead time,     | ----- PROT_DIS (comparator emul.) ---> |  TZ1/TZ2/TZ3 inputs                |
|  sensing-chain + comparator  | <---- CAN 0x200 / 0x7FF (test host) -> |  CAN (TCAN332)                     |
|  emulation, fault injection  |                                        +-----------------------------------+
+------------------------------+
```

| item | requirement | reason |
|---|---|---|
| plant solver | FPGA, fixed step <= 50 ns (the SIL plant uses Ts/200 = 50 ns); 100 kHz switching, phase-shift resolution 10 ns | the controller's PWM resolution is 10 ns (TBCLK 100 MHz); the plant must resolve dead time (150 ns) and the EPS inner shifts |
| PWM capture | 8 digital inputs, edge time-stamping at >= 100 MHz | phase shift and D1/D2 are read from the edges, not from registers |
| analog outputs (plant -> controller) | V1_SE: 0-1000 V -> 0-3.3 V (hal_adc_read: 1000/4096 per LSB); V2_SE: 0-500 V -> 0-3.3 V; I_L peak-hold: 0-40 A -> 0-3.3 V; NTC: resistance emulation or voltage equivalent of the 10 k NTC divider; 12-bit DAC, settling < 1 us, update at the plant step | must match the real conditioning so the firmware scaling (`hal_adc_read`) is unchanged. **Discrepancy to resolve before HIL:** the firmware README says "AMC1311 0-2 V = 0-1000 V", the schematic uses AMC1301 (+/-250 mV in, x8.2) with a TLV9062 stage, and `hal_adc_read` assumes 1000 V = 4096 counts (3.3 V); one scaling must be chosen and the I/O map written from it |
| hardware comparators | emulated in the simulator on the same V1_SE / V2_SE / I_L signals (920 V / 490 V / 32 A), driving PROT_DIS as a digital output into TZ and a logic emulation of the driver DIS pins | the comparators sit downstream of the isolated amplifiers: a sensor-chain fault must affect both the firmware and the hardware path (common cause, see `Reliability_Engineering/` FMEDA) |
| fault injection | at the conditioning stage: gain / offset / stuck / clip / noise per channel; at the plant: source steps, load short, bus OV; at the bus: heartbeat suppression, frame corruption; digital: driver FLT, precharge feedback | the 19 SIL cases below are the acceptance set; each has a measurable pass criterion |
| latency budget (controller loop) | ADC conversion 4 ch ~1 us + ISR < 2 us + PWM latch at the next period (<= 10 us) + simulator I/O (DAC settle + capture) <= 1 us + plant step 50 ns => <= 1.5 switching periods command-to-effect, same as the SIL one-period delay | the control design (11_Control_Algorithms) assumed 1.5 Ts delay; the HIL must not add more than ~2 us or the phase margin (76 deg) is misreported |
| acceptance | start-up, load steps, reversal and dead-bus start reproduce the SIL results within 5 % (test plan step 6); all 19 fault cases give the same classification as the SIL table | |

Not available here: the simulator, the LaunchPad, a CAN interface, the TI toolchain. The SIL suite is the executable
specification of the HIL acceptance tests.

## 2. SIL fault-injection suite (executed)

Harness (`sil_fault_injection.py`): `DABPlant` (switched model) + `DABController` (Python reference of the C core) + a
sensing-chain model (gain, offset, stuck, clip, 12-bit quantisation, noise) + emulated hardware comparators (OV 920/490 V,
OC 32 A, one-period granularity) that force the gates off and put the controller into FAULT (as the C core's `hw_trip` does;
the Python reference lacks that input). Each test has an explicit pass criterion; a FAIL is reported, not hidden.

Result: **19 / 19 PASS** (`results/sil_results.md`). Selected rows:

| id | test | criterion | result | key values |
|---|---|---|---|---|
| T01 | baseline start-up and regulation | RUN, |v2-400| < 4 V | PASS | deviation 0.002 V |
| T02 | V2 sensor gain +5 % | no trip (undetectable by design), true v2 = 400/1.05 | PASS | true v2 381.0 V |
| T03 | V2 sensor gain -20 % at 60 ms (AMC1301 chain: common cause for regulation, FW OV and HW OV) | true v2 <= 480 V or trip | PASS (barely) | **true v2 473.9 V, no trip, firmware reads 379 V** - a -25 % gain fault would exceed 480 V with nothing tripping |
| T04 | V2 sensor offset -30 V | true v2 <= 480 V or trip | PASS | true v2 430 V, no trip |
| T05 | V2 sensor fail-low in RUN | V2_UV within 2 periods | PASS | 1 period |
| T06 | V1 sensor fail-high (1000 V FS) | V1_OV within 2 periods | PASS | HW comparator and firmware in the same period |
| T07 | real HV bus OV ramp 800 -> 960 V | V1_OV within 1 period of 900 V, before 920 V | PASS | tripped at 900.7 V, HW would have tripped 3.2 ms later |
| T08 | LV load short 0.1 Ohm | trip within 20 periods, i_pk < 32 A | PASS | V2_UV after 7 periods, i_pk max 22.8 A (phi_max / EPS limit the current; the OC path is not even reached) |
| T09 | heartbeat loss | COMM within 1 period | PASS | 1 period |
| T10 | AMC1301 saturation at 500 V with the link pulled to 520 V | V2_OV | PASS | reading clips at 500 V > 480 V: **4 % margin** between clip level and trip level |
| T11 | CT/ADC clip at 40 A during a short | trip still occurs | PASS | (short is caught by UV; 40 A FS > 32 A) |
| T12 | 12-bit quantisation + 2 LSB noise | no fault, v2 std < 1 % | PASS | std 0.035 V |
| T13 | ADC noise 1 % FS (41 LSB) | no false trip, deviation < 2 % | PASS | max deviation 7.8 V (1.9 %) - close to the limit |
| T14 | V1 dip to 580 V | V1_UV (documented) | PASS | |
| T15 | V1 dip 10 % | no fault, deviation < 3 % | PASS | 0.13 V |
| T16 | enable removed in RUN | INIT within 1 period, gates off | PASS | |
| T17 | precharge never ok | gates never enabled | PASS | Python stays in PRECHARGE_WAIT; the C core faults after 5 s (discrepancy, see `Reliability_Engineering/`) |
| T18 | NTC reads 110 C | OT within 1 period | PASS | |
| T19 | CT stuck low during a short | trip or i_pk < 40 A | PASS | caught by V2_UV; with a resistive short that keeps v2 > 250 V nothing would trip (single-point CT) |

Findings for the design owner: (1) T03/T04: a single gain or offset fault on the LV sensing chain moves the true link
voltage without any trip because regulation, firmware OV and hardware OV all read the same AMC1301 - a plausibility check
(V2 x n vs V1 power balance, or a second sensing path) is the remedy; (2) T10: the LV full-scale/trip margin is only 4 %;
(3) T13: with 1 % FS noise the regulation deviation approaches 2 %, so the ADC noise budget must stay well below that;
(4) T08/T19: a hard LV short is handled by the voltage window and the phase-shift limit, not by the OC path.

## 3. Not verified

* No HIL executed; the architecture table is a proposal with unresolved I/O scaling (see the discrepancy row).
* The hardware comparators and the gates-off plant behaviour are harness emulations with one-period granularity; the real comparator acts within the period (cycle-by-cycle).
* The Python reference controller is not the C code: `Reliability_Engineering/` lists the protection differences (hw_trip, driver_fault, precharge timeout, enable handling in PRECHARGE_WAIT).
* The plant has no magnetics saturation, no parasitic ringing, no driver model; sensor faults are static (no bandwidth effects).
