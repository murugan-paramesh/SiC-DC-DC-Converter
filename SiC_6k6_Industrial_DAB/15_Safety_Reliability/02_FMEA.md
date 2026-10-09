# 15.2 - Failure Mode and Effects Analysis (design FMEA, rev A)

Severity/occurrence/detection on 1-10 scales (engineering judgement, no field data). RPN > 60 items carry an action in the notes column.

| item | failure mode | effect | detection / mitigation | S | O | D | RPN | notes |
|---|---|---|---|---|---|---|---|---|
| HV SiC MOSFET | short circuit (die failure) | shoot-through, DC-link short, fuse operation, possible case rupture | DESAT soft turn-off <1 us; semiconductor fuse; TO-247 with margin 850/1200 V; derated Tj | 8 | 2 | 6 | 96 | detectable: FLT, fuse state; add explosion-safe enclosure |
| HV SiC MOSFET | open (bond wire lift) | loss of one leg -> asymmetric transformer flux, saturation | DC-blocking capacitor option; current-sense asymmetry detection in firmware (future) | 6 | 2 | 5 | 60 | firmware flux-balance check is an open item |
| Gate driver | UVLO / supply loss | device partially on -> high loss, possible shoot-through | driver FLT -> TZ; negative turn-off bias | 7 | 3 | 3 | 63 |  |
| Gate driver | isolation breakdown | HV on control circuits -> hazard to personnel | reinforced-rated isolator, PCB slot, 4 kVrms type test | 10 | 1 | 4 | 40 | safety-critical; PD test |
| Gate bias module | isolation breakdown / output fail | as above / driver UVLO | reinforced-class module required (open item), UVLO | 10 | 1 | 4 | 40 | open item 15.1-4 |
| DC-link film capacitor | loss of capacitance (self-healing ageing) | ripple increase, EMI, eventually over-voltage trip | voltage derating 77 %, temperature < 60 C, capacitance monitoring via ripple (host) | 4 | 3 | 6 | 72 |  |
| DC-link film capacitor | short | fuse operation, energy release | fuse, cap bank segmented, enclosure | 8 | 1 | 3 | 24 |  |
| Transformer | interwinding insulation failure | HV to LV port, loss of isolation | 3-layer reinforced tape, margins, hipot routine test | 9 | 1 | 5 | 45 | safety-critical |
| Transformer | saturation (DC bias, over-voltage) | over-current, device stress | current limit CMPSS, UV/OV windows, EPS matching limits volt-seconds | 6 | 3 | 3 | 54 |  |
| Series inductor | gap/winding overheating | inductance drift -> power capability loss | Bpk 0.12 T, litz away from gap, NTC on heatsink | 4 | 3 | 5 | 60 |  |
| Current transformer | open secondary / drift | loss of OC protection | burden on PCB, plausibility check vs power model in firmware | 7 | 2 | 6 | 84 | firmware plausibility check is an open item |
| Voltage sensing AMC1311 | drift / fail-low | wrong regulation, OV undetected by firmware | independent hardware OV comparator (TZ3); redundancy | 8 | 2 | 4 | 64 |  |
| DSP | latch-up / software fault | loss of control | watchdog -> gates off; hardware trips independent of software | 8 | 2 | 3 | 48 |  |
| 24 V aux | loss | all gates off (safe), link energy remains | bleeders; status to host | 3 | 3 | 2 | 18 |  |
| Fans | failure | over-temperature | NTC derating/trip; host alarm | 5 | 3 | 3 | 45 | no tachometer in rev A |
| Connectors / bus bars | loose joint | hot spot, arcing | torque spec, thermal inspection | 7 | 2 | 6 | 84 |  |
| PCB | contamination/creepage reduction | tracking across barriers | conformal coating, PD2 enclosure, slots | 9 | 1 | 6 | 54 |  |
| Precharge interface | contactor welded / failed | inrush or no isolation | precharge feedback interlock + timeout | 7 | 2 | 4 | 56 |  |
| CAN link | loss | no supervisory control | FLT_COMM -> safe state | 3 | 3 | 1 | 9 |  |

## Reliability assessment

No MTBF figure is claimed: a parts-count prediction (IEC 61709 / MIL-HDBK-217F) requires the final BOM with manufacturer FIT data; the dominant contributors are expected to be the film capacitors (voltage/temperature derated), the eight gate-bias modules and the fans. The design choices that drive reliability: 77 % / 64 % voltage derating of the links, Tj < 75 C at full load (13), no electrolytic capacitors in the power path, hardware-only protection path independent of firmware.

