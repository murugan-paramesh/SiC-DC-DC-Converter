# 03 - Component selection

All part numbers are proposals; every pinout marked **verify** must be checked against the
datasheet revision in hand before the first build. The symbol/footprint generator
(`tools/kicad`) makes such changes a one-line edit.

## Power semiconductors

| Function | Part | Key data | Why |
|---|---|---|---|
| Primary bridge Q1-Q4 | Wolfspeed C3M0060065K, TO-247-4 | 650 V, 60 mOhm (25 C), Qg ~36 nC, Coss(er) ~100 pF, Kelvin source | Low Coss gives ZVS down to ~10 % load with only 12 uH; Kelvin source removes common-source inductance so 5 Ohm gate resistors are enough; 650 V class is right for a 420 V bus with ZVS (no overshoot). Alternatives: C3M0045065K (lower Rds), Infineon IMZA65R048M1H. |
| Primary clamp D1, D2 | Wolfspeed C3D04065A, TO-220-2 | 650 V SiC Schottky, 4 A | Zero reverse recovery - the clamp conducts short pulses every cycle. Pinout 1 = A, 2 = K (tab): **verify**. |
| Synchronous rectifiers Q5-Q8 | Infineon IPP110N20N3 G, TO-220 | 200 V, 10.7 mOhm, Qg ~100 nC | 140 V clamped stress at 420 V in leaves 30 % margin; two in parallel per leg for 20 A rms each. Alternative with lower Rds: IPB107N20N3 G (D2PAK) on a copper-pour heatsink. |

## Magnetics (custom, see docs/06)

| Item | Core | Turns / wire |
|---|---|---|
| T1 main transformer | ETD59/31/22, 3C95, ungapped | 18 T litz 600 x 0.1 mm; 2 x (3 T, 2 parallel foils 0.15 x 38 mm) |
| L1 resonant inductor | ETD39/20/13, 3C95, 1.3 mm gap | 10 T litz 600 x 0.1 mm |
| L2 output inductor | 2 x Magnetics 77439-A7 (Kool Mu 60u) stacked | 5 T, 2 x 6 mm flat copper |
| CT1 current transformer | Ferrite toroid 1:100 (e.g. Magnetics ZW42908TC, 100 T AWG32) | 1-turn insulated primary lead through the core |

## Control and drive ICs

| Ref | Part | Notes |
|---|---|---|
| U1 | TI UCC28951PW (TSSOP-24) | PSFB controller with SR outputs, adaptive delays, DCM and burst, 5 V VREF. Pin map as in the symbol: VREF 1, EA+ 2, EA- 3, COMP 4, SS/EN 5, DELAB 6, DELCD 7, DELEF 8, TMIN 9, RT 10, RSUM 11, DCM 12, ADELEF 13, ADEL 14, CS 15, SYNC 16, OUTF 17, OUTE 18, OUTD 19, OUTC 20, OUTB 21, OUTA 22, VDD 23, GND 24. |
| U2, U3 | TI UCC21520DW (SOIC-16 wide) | 5.7 kVrms reinforced isolated dual driver, 4 A / 6 A, 19 ns prop delay, programmable interlock dead time (R20/R21 = 2.2 k -> ~22 ns safety). Logic side powered from +12 V. |
| U4 | TI UCC27524D | Dual 5 A low-side driver for the four SR MOSFETs (two per channel). |
| PS1-PS4 | RECOM R12P21503D (SIP-7) | 12 V in, +15 V / -3 V out, 2 W, 5.2 kVDC isolation, matches the C3M recommended gate drive. Pinout 1 +Vin, 2 -Vin, 5 -Vout, 6 Com, 7 +Vout: **verify**. Murata MGJ2D121505SC is a drop-in with -5 V. |

## Passives

| Function | Choice |
|---|---|
| DC-link film C1-C4 | TDK B32778G4106K, 10 uF / 450 V, 37.5 mm pitch, 4.8 A rms total ripple |
| Bridge HF decoupling C5, C6 | 470 nF / 630 V X7T 2220 MLCC, one per leg |
| DC blocking C7, C8 | TDK B32674D3475K 4.7 uF / 250 V film (4 V ripple, 10 A rms) |
| Output electrolytic C11-C16 | Nichicon UHW1J471MHD 470 uF / 63 V, 20 mOhm, 16 x 25 mm |
| Output MLCC C17-C22 | 10 uF / 100 V X7S 1210 |
| Y capacitors CY1, CY2 | 2.2 nF Y1 (Vishay VY1222M63Y5UQ63V0) |
| SR snubbers R1/C9, R2/C10 | 10 Ohm 2 W 2512 + 470 pF / 250 V C0G |
| Gate resistors (SiC) | 5.1 Ohm on, 2.2 Ohm off through SS14 Schottky, 10 k gate-source bleed |
| SR gate resistors | 4.7 Ohm per MOSFET, 10 k bleed |
| Output shunt R3 | Vishay WSBS8518L5000JK 0.5 mOhm, 2 W at full load |
| Fuse F1 | 15 A / 500 V ceramic 6.3 x 32 (Littelfuse 0215015.MXP) in PCB clips |

## Controller programming components (see docs/02 for the derivations)

| Pin | Parts | Value |
|---|---|---|
| EA+ | R41/R42 10 k / 10 k from VREF | 2.5 V reference |
| EA- | R43+R44 20 k, R45 1.1 k | 48 V set point |
| COMP | R46 150 k, C56 8.2 nF, C57 56 pF | type-II, fc 7 kHz, PM 92 deg |
| SS/EN | C58 100 nF | ~20 ms soft start |
| DELAB / DELCD | R47/R48 13 k | ~60-100 ns leg delays (tune on the bench) |
| DELEF | R49 20 k | SR delay |
| TMIN | R50 20 k | minimum on-time |
| RT | R51 60.4 k to VREF | 100 kHz (**verify** against the datasheet equation) |
| RSUM | R52 100 k | slope compensation |
| DCM | R53/R54 100 k / 10 k | DCM threshold (SR off at light load) |
| ADEL / ADELEF | R55/R56, R57/R58 100 k / 10 k | adaptive delay slope |
| CS | R59 12 Ohm burden, R60 100 Ohm / C59 100 pF filter | 1.48 V at full load, 2 V limit |
