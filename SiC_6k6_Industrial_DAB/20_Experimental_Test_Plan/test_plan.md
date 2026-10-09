# 20 - Experimental validation plan (laboratory)

**This plan is not an authorisation to energise.** Steps 5-10 require (a) independent review of this
package, (b) an approved laboratory procedure with an interlocked HV source, isolated instrumentation,
emergency stop that opens both port contactors and discharges the links, (c) two persons present.
None of the tests below can be executed in the present software-only environment; the "expected"
columns come from calculation/simulation and must not be reported as measurements.

## Instruments (minimum)
| Instrument | Requirement |
|---|---|
| Oscilloscope | >= 500 MHz, 4 ch, isolated or with 2 x high-voltage differential probes (1.5 kV, 100 MHz) and 1 x isolated 50 MHz probe for gate-source |
| Current probes | 2 x 50 A / 50 MHz (CT) for i_L, 1 x DC/AC 100 A clamp for port currents |
| Power analyser | 0.1 % class, 1000 V / 50 A channels (e.g. WT5000 class), 2 channels for efficiency |
| HV DC supply/sink | 0-1000 V, bidirectional or source + electronic load with regenerative sink, 7 kW |
| LV DC source/load | 0-500 V, 7 kW bidirectional (battery emulator) |
| Hipot tester | 5 kV AC/DC, 1 min, with PD option if available |
| Thermal | 8-ch thermocouple logger + IR camera |
| EMI | DC LISNs (2), EMI receiver 9 kHz-30 MHz, near-field probes |
| Impedance analyser / LCR | 100 Hz-1 MHz for magnetics |

## Staged tests
| # | Test | Conditions | Expected (calc/sim) | Pass criterion | Risk level |
|---|---|---|---|---|---|
| 1 | Bare-board inspection, netlist test, solder review | - | - | no defects | low |
| 2 | Magnetics characterisation | LCR 100 kHz | Lm ~10 mH, Llk 4 uH, L1 = 60 uH +/-5 % | within 10 % | low |
| 3 | Insulation (type test, assembled, no LaunchPad) | 2.5 kVrms HV-LV 60 s; 4 kVrms HV-CTRL; 3 kVrms LV-CTRL; PE bonding < 0.1 Ohm | leakage < 1 mA | pass | medium (HV) |
| 4 | Aux power and gate drive, no link voltage | 24 V in, LaunchPad connected | rails 12/5/3.3 V, 8 x +15/-3 V; PWM 100 kHz, dead time 150 ns, phase shift command vs measured | timing within 10 ns | low |
| 5 | Protection functions, no link voltage | inject I_L (signal generator into CT burden), V1_SE/V2_SE | PROT_DIS asserts at 2.0 V (32 A), 920 V, 490 V; TZ latches, FLT LED, telemetry | all trips within 1 us (hardware) / 10 us (firmware) | low |
| 6 | Controller HIL | LaunchPad with the SIL plant ported to a HIL box (Typhoon/OPAL class) or the C plant on a second MCU | start-up, steps, reversal as in `10_Firmware/sil` | matches SIL within 5 % | low |
| 7 | Low-voltage power test | V1 = 50-100 V, V2 open then 50 % resistive load, 1 A current limit | waveforms as 05_Simulation scaled; ZVS not expected at low V | no abnormal ringing; i_L symmetric (no DC) | medium |
| 8 | Staged power: 200/400/600/800 V, 10-100 % load | HV source, LV load; forced air on | ZVS at both bridges > 35 % load (SPS) - verify v_DS reaches 0 before gate rises on all 8 devices; link ripple < 2 % | ZVS confirmed; Tj (case) < 80 C | high |
| 9 | Efficiency map | 9 corners x 5 loads, both directions, power analyser | calc 98.6 % nominal (expect 97-98 % measured) | EL-06/07 objectives | high |
| 10 | Dynamics | 50 % load steps, 10 % V1 dips, reversal 2 kW/ms | dip < 3 %, reversal < 20 ms | EL-10/EL-11 | high |
| 11 | Thermal soak | full load 2 h at 45 C ambient equivalent | sink < 60 C, transformer < 100 C | 13_Thermal | high |
| 12 | EMI pre-compliance | DC LISNs both ports, 25/50/100 % | within CISPR 11 A with the proposed filter | margin >= 6 dB | medium |
| 13 | Long duration | 100 h at 80 %, 10 on/off cycles per hour for 24 h | no fault log entries, no drift > 1 % | - | high |

## Measurement notes
* Efficiency: two-wattmeter method with simultaneous sampling; subtract aux power separately; uncertainty budget +/-0.15 % at 97 %.
* ZVS verification: probe v_DS (HV differential probe, 100 MHz) and v_GS (isolated probe) on the same device; ZVS = v_DS < 5 % of the link voltage when v_GS crosses the threshold; record at 25/50/100 % load and all 9 voltage corners.
* Thermal: thermocouples on each TO-247 tab (under the clip), transformer outer winding, inductor core, two link capacitors; IR camera for PCB hot spots.
* Dead-time trimming: adjust DAB_T_DEAD_S from the measured transition times (expected 10-90 ns); re-run step 8.

## Reporting
Each test produces a record (instrument serials, settings, raw files, screenshots) stored under `20_Experimental_Test_Plan/records/<date>_<test>/`, and the RTM (`00_Requirements/03_RTM.csv`) status column is updated from "sim"/"calc" to "measured" only with a record reference.
