# 01 - Specification and architecture

## Target application

A 3 kW isolated DC-DC stage for a telecom / data-centre rectifier, battery charger or
industrial 48 V power supply. It sits behind a PFC front end (400 V DC link) and delivers a
regulated 48 V bus with reinforced isolation.

## Electrical specification

| Parameter | Min | Nom | Max | Notes |
|---|---|---|---|---|
| Input voltage (full power) | 370 V | 400 V | 420 V | PFC output |
| Input voltage (derated) | 320 V | | | hold-up, output current limited |
| Output voltage | | 48.0 V | | +/- 1 % set-point, trimmable via R45 |
| Output current | 0 | | 62.5 A | continuous |
| Output power | | | 3.0 kW | |
| Switching frequency | | 100 kHz | | per primary switch, output ripple at 200 kHz |
| Efficiency (full load, 400 V) | 96 % | 97 % (est.) | | see docs/02 |
| Output ripple | | | 100 mV p-p | at 200 kHz |
| Load step response | | 220 mV | | 50 % step, 8 kHz crossover |
| Isolation (pri-sec) | 4 kVrms, 1 min | | | reinforced, 8 mm creepage/clearance |
| Bias input | 10.8 V | 12 V | 13.2 V | 1.5 A max, secondary referenced |
| Ambient temperature | -10 C | | 50 C | forced air, 2 m/s across heatsinks |

## Topology

ZVS phase-shifted full bridge (PSFB) with:

* **Primary** - four SiC MOSFETs (Wolfspeed C3M0060065K, 650 V / 60 mOhm, TO-247-4 Kelvin
  source) in a full bridge; an external 12 uH resonant inductor extends the ZVS range to
  about 10 % load; two SiC Schottky clamp diodes (C3D04065A) on the resonant-inductor node
  remove the secondary rectifier ringing (Redl clamp) so 200 V synchronous rectifiers can be used
  with a 140 V nominal stress; 2 x 4.7 uF film capacitors block DC and prevent flux walking.
* **Transformer** - ETD59, 3C95, 18:3:3 centre-tapped, 1 mH magnetising inductance, foil
  secondaries, reinforced insulation.
* **Secondary** - centre-tapped synchronous rectifier with two paralleled 200 V / 10.7 mOhm
  MOSFETs per leg (Infineon IPP110N20N3 G), RC snubbers, 6.8 uH output inductor (powder core),
  6 x 470 uF + 6 x 10 uF output capacitors, 0.5 mOhm output current shunt.
* **Control** - TI UCC28951 PSFB controller located on the secondary side (direct output
  sensing, direct SR drive, peak current mode with slope compensation, adaptive ZVS delays,
  DCM detection, soft start). The primary bridge is driven through two UCC21520 reinforced
  isolated dual gate drivers; the SR MOSFETs through a UCC27524.
* **Gate bias** - four RECOM R12P21503D isolated 2 W modules give each SiC MOSFET a +15 V / -3 V
  supply referenced to its Kelvin source.
* **Current sense** - a 1:100 current transformer with a one-turn insulated flying lead on the
  primary; secondary side bridge rectifier and burden feed the UCC28951 CS pin (cycle-by-cycle
  limit at 16.7 A primary / ~100 A output).

```
 400 V DC ──F1──┬── C1..C6 ──┐
                │   Q1  Q3   │     Lr    D1/D2    Cb         T1 18:3:3       Q5,Q6
            VBUS├──┤   ├──SW_A─┤ 12uH ├──┬──LR_N──┤ 4.7uF ├─PRI_1─[CT]─PRI_2─┤ P+   S1 ├───┤  ├──┐  Lo 6.8uH
                │   Q2  Q4   │          clamp                               │      CT ├──────────┤  ├──┬── 48 V / 62.5 A
            PGND├──┤   ├──SW_B──────────────────────────────────────────────┤ P-   S2 ├───┤  ├──┘      │  Co 2.8 mF
                │             ↑ UCC21520 x2  ← OUTA..D                             Q7,Q8   ↑ UCC27524 ← OUTE/F
                │             isolated bias x4 (R12P21503D)        UCC28951 (secondary side, peak CM)
```

## Protection and supervision

* Input fuse 15 A / 500 V (6.3 x 32 ceramic).
* Cycle-by-cycle primary peak current limit (CS pin, 2 V threshold).
* UCC28951 UVLO on VDD, soft start / enable pin brought out to the signal header.
* Output current monitor (shunt Kelvin pins on the signal header), heatsink NTC input.
* Y1 capacitors across the barrier for common-mode noise control.

## Mechanical

* PCB 260 x 200 mm, 4 layers, 2 oz copper on all layers, 2.0 mm FR4, Tg >= 150 C.
* Primary SiC MOSFETs and clamp diodes stand vertically along the top edge and bolt to an
  extruded heatsink bar; the SR MOSFETs stand along the top and bottom edges of the secondary
  half and share a second heatsink bar.
* Four M4 mounting holes, M4 input lugs, M5 output lugs.
* Isolation barrier at x = 130 mm; routed slots under the SIP-7 bias modules.
