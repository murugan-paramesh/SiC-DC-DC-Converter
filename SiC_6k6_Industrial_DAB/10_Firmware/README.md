# 10 - Firmware

| Component | Files | Status |
|---|---|---|
| Portable control core (PI, modulator inverse, EPS matching, state machine, protections, fault log) | `src/dab_control.[ch]`, `src/dab_params.h` (generated) | **compiles (gcc), software-in-the-loop tested** (`make test`) |
| Communication protocol (telemetry frame with CRC-16, command parser) | `src/dab_comm.[ch]` | compiles, unit-tested in SIL |
| C plant for SIL (same equations as 05_Simulation) | `hal/sil/plant.[ch]` | compiles |
| SIL scenarios: start-up, load steps, reversal, 5 protection injections, precharge timeout, dead-bus start, comm | `sil/sil_main.c` | run with `make test`; results in `sil/sil_results.csv` |
| C2000 HAL (EPWM phase-shift, dead band, trip zones, ADC SOC, GPIO) | `hal/c2000/hal_f28004x.[ch]`, `hal/c2000/main.c` | **written, NOT compiled** (no TI toolchain here), **NOT hardware tested** |

Build and test on the host:
```
python3 tools/gen_params.py     # regenerates src/dab_params.h from 04/11 results
make test
```
Target build: import `src/`, `hal/c2000/` into a Code Composer Studio project for TMS320F280049C
with C2000Ware driverlib; define `__TMS320C28XX__` (set by the TI compiler). The leg-shift PWM
scheme and the ADC scaling (`hal_adc_read`) correspond to the sensing chain in
`07_KiCad_Schematics` (AMC1311 0-2 V = 0-1000 V on V1, 0-500 V on V2; CT peak detector 40 A FS).

CAN mapping (500 kbit/s, 11-bit IDs, to be confirmed with the supervisory system): 0x100 status
(state, fault, mode), 0x101 measurements (v1, v2, i_pk, temp as uint16 scaled), 0x200 command
(enable, mode, reference), heartbeat 0x7FF at 10 Hz; comm loss = no heartbeat for 500 ms.

Timing budget (F280049C, 100 MHz): the control step is ~120 floating-point operations (one
sqrt), < 2 us; ADC conversion of 4 channels ~1 us; the ISR fits in < 5 % of the 10 us period.
Quantisation: phase shift resolution 1/1000 of the period (10 ns at 100 MHz TBCLK) = 0.36 deg,
equivalent to 0.5 % of rated power at the nominal point.

Known limitations: no closed-loop current control of the HV port in reverse mode (CP mode only,
per APP-03); the TPS look-up table is not yet generated (EPS matching is used); CAN/SCI drivers
are placeholders.
