# Active gate drive: is it worth its complexity for this converter?

**Maturity: L1 (analytic, datasheet-model based). No measurement, no SPICE at the gate-loop level.** All device
parameters come from `dabtools/dab/devices.py` (datasheet-typical, `verified=False`) plus the extra values in the
script header (Ciss, g_fs, Rg_int, Vth_min at 150 C, UCC21520 R_OH / R_OL) which are recalled datasheet figures
**to verify**. Script: `python3 Advanced_Research_2026/Active_Gate_Drive/gate_drive_analysis.py` (< 5 s, no random
numbers). Outputs in `results/`: `gate_drive_results.json`, `option_table.md`, four figures, `provenance.json`.

## 1. The design as it is (schematic / BOM)

| Item | Value | Source |
|---|---|---|
| Driver | UCC21520DW (reinforced, 4 A / 6 A, **no DESAT, no Miller clamp**) | `16_BOM/bom.md` U1-U4 |
| Gate resistors | Rg_on = 3.3 Ohm (R102...), Rg_off = 1.5 Ohm (R103...) - already a **two-level** on/off network | BOM, `gate_drive.kicad_sch` |
| Bias | +15 V / **-3 V** (R12P21503D), 4.7 uF "-3 V bulk" | schematic text, BOM C105 |
| Model assumption | **Vgs_off = -4 V** in `devices.py` | discrepancy, see 4 |
| Driver interlock | DT pin 2.2 k -> ~22 ns; firmware dead time 150 ns | BOM R101 |
| Kelvin source | TO-247-4 used | MEC-03 |

## 2. Model

Piecewise-linear gate-charge / Miller-plateau model (equations in the script header): plateau voltage
`V_pl = Vth + I/g_fs`; gate current at the plateau `(V_drv - V_pl)/R_total` with `R_total = Rg_ext + Rg_int + R_driver`;
`dv/dt = V / (Qgd / I_g)` (Qgd scaled with sqrt(V/800 V)); current edges from the RC law with a 5 ns floor; hard-switching
energies `1/2 V I (t_i + t_v) + 1/2 Coss,er V^2`; for the **ZVS case (the DAB's normal operation) the turn-off is capacitive:
dv/dt = I_sw / (2 Coss,tr), independent of Rg**, and the residual turn-off loss is `I^2 t_if^2 / (24 C_leg)`. Crosstalk:
`V_gs,ind = Voff + R_off (Qgd/V) dv/dt (1 - exp(-t_tr/tau_off))`, margin to `Vth,min(150 C) = 1.8 V`; Miller clamp modelled as
`R_off -> 1 Ohm + Rg_int` (the clamp cannot bypass the internal gate resistance). Overshoot `L_loop di/dt` with L_loop
15 nH (HV) / 12 nH (LV) assumed. EMI proxy: `I_cm = 100 pF x dv/dt`.

Operating points: ZVS at the nominal edge current (9.8 A HV / 19.5 A LV) and at the worst full-power corner (19.6 A /
39.2 A, 650 V / 300 V corners of `design_values.json`); hard switching at the light-load edge current where ZVS is lost
(3 A HV / 6 A LV, just above I_min = 2.0 / 3.1 A). Share of the (V1, V2, load) grid in ZVS with SPS: 52 % (loads 10-100 %
uniformly weighted; at the nominal 800/400 V point ZVS from 35 % load).

## 3. Results (`results/option_table.md`, figures `fig_dvdt_vs_rg.png`, `fig_loss_vs_rg.png`, `fig_tradeoff_map.png`, `fig_crosstalk_margin.png`)

C3M0032120K, 800 V:

| option | hard dv/dt on/off (V/ns) | hard E per on+off (uJ) at 3 A | ZVS dv/dt nom / worst (V/ns) | ZVS E_off model (uJ) | crosstalk margin ZVS nom / worst (V) | margin at hard turn-on (V) |
|---|---|---|---|---|---|---|
| A fixed 3.3 / 3.3 | 31 / 4.7 | 91 | 15 / 31 | 0.16 | +1.3 / -1.6 | -1.7 |
| **B current: 3.3 / 1.5, -3 V** | 31 / 4.7 | 91 | 15 / 31 | 0.16 | +2.3 / **-0.1** | **-0.2** |
| B' current with -4 V bias | 31 / 4.7 | 91 | 15 / 31 | 0.16 | +3.3 / +0.9 | +0.8 |
| C current + Miller clamp (-3 V) | 31 / 4.7 | 91 | 15 / 31 | 0.16 | +2.9 / +1.0 | +0.9 |
| D slow 10 / 10 | 19 / 4.7 | 110 | 15 / 31 | 0.16 | -1.7 / -5.2 | -2.9 |
| E multi-level 1 / 10 concept | 19 / 4.7 | 110 | 15 / - | no gain | - | - |

C3M0016120K, 400 V:

| option | hard dv/dt on/off (V/ns) | hard E (uJ) at 6 A | ZVS dv/dt nom / worst (V/ns) | ZVS E_off (uJ) | crosstalk margin ZVS nom / worst (V) | margin at hard turn-on (V) |
|---|---|---|---|---|---|---|
| **B current: 3.3 / 1.5, -3 V** | 11.5 / 4.6 | 76 | 15 / 30 | 0.31 | **-0.4 / -3.0** | +0.6 |
| B' current with -4 V bias | 11.5 / 4.6 | 76 | 15 / 30 | 0.31 | +0.6 / -2.0 | +1.6 |
| C current + Miller clamp (-3 V) | 11.5 / 4.6 | 76 | 15 / 30 | 0.31 | +0.9 / -1.7 | +1.7 |
| D slow 10 / 10 | 6.8 / 4.3 | 222 | 15 / 30 | 0.31 | -4.7 / -6.2 | -2.0 |

Self-limiting dv/dt (the slope at which the induced gate voltage reaches Vth,min and the channel re-conducts, which then
slows the transition and costs loss instead of causing shoot-through in a ZVS leg): HV 29 V/ns, LV **12 V/ns** at -3 V;
35 / 15 V/ns at -4 V.

## 4. What this means for THIS converter (honest reading)

1. **Under ZVS - the normal DAB case - the gate resistor does not set dv/dt.** The node slope is `I_sw / (2 Coss,tr)`:
   15 V/ns at nominal and ~30 V/ns at the full-power corners, on both bridges, whatever Rg is. The 20 V/ns used in
   14_EMI_EMC is inside this range. An active/multi-level gate driver cannot slow a capacitive commutation; only snubber
   capacitance can, at the cost of ZVS range. The ZVS turn-off loss is in the 0.1-0.3 uJ range per edge by this model,
   far below the conservative `0.35 x Eoff(datasheet)` assumption of `losses.py` (19 / 42 uJ); the truth is between
   (the model ignores tail effects) and can only be settled by measurement (test plan step 8).
2. **Where Rg matters is the hard-switched light-load region** (below ~35 % load at 800/400 V, up to 100 % load at the
   worst d corners): the turn-on edge at Rg_on = 3.3 Ohm is 31 V/ns (HV) with 91 uJ per on/off pair = 9 W per edge
   position at 100 kHz if it were continuous. Rg_on = 10 Ohm costs +20 % energy for -40 % dv/dt. A multi-level driver
   (1 Ohm before the plateau, 10 Ohm during it) gives the delay of the fast stage with the dv/dt of the slow stage but, at
   these light currents, **no loss benefit** (the current-rise term is negligible). Its benefit would be delay/jitter,
   which the DAB phase-shift modulator does not need at the 10 ns level (0.36 deg resolution already).
3. **Crosstalk (false turn-on) is the real finding.** With the -3 V bias of the schematic the quasi-static model gives a
   margin of about zero for the HV device at the worst corner and a *negative* margin for the LV device (C3M0016120K, Qgd 62 nC,
   low Rg_int) already at the nominal 15 V/ns. Three remedies, in order of cost: (a) **-4 V bias as `devices.py` assumed**
   (needs a different bias module: R12P21503D gives -3 V; a +15/-4 V or +15/-5 V part, open item alongside 15.1-4) -> +1 V
   margin; (b) **a driver with an active Miller clamp** (UCC21710 / UCC5870 class, which also brings DESAT and is already the
   documented upgrade path in the BOM) -> +0.6 to +1.3 V; (c) reducing Rg_off below 1.5 Ohm helps little because the internal
   Rg_int (2.5 / 1.5 Ohm, assumed) dominates. Note that in a ZVS leg the induced bump re-conducts the device that just turned
   off (self-limiting, extra loss) rather than causing shoot-through; in the hard-switched light-load region it is genuine
   cross-conduction. The quasi-static gate-charge method is known to be pessimistic at the start of the slope and optimistic
   near its end; **this is a measurement item** (v_GS of the off device at 25/50/100 % load, test plan step 8).
4. Overshoot: with the 5 ns current-edge floor, `L_loop di/dt` gives 9-14 V at light current (negligible); the undamped
   ringing bound at the end of a worst-corner capacitive commutation is `I sqrt(L_loop/C_leg)` ~ 95 V (HV) / 90 V (LV),
   well inside the 1200 V rating at 850 V / 450 V.

**Recommendation.** Active (multi-level / closed-loop dv/dt) gate drive is **not worth its complexity** for this
converter: in ZVS it has nothing to act on, and in the hard-switched light-load region a passive Rg change achieves the
same dv/dt at a loss penalty that is small in absolute terms (light load). The worthwhile changes are (i) resolving the
-3 V / -4 V bias discrepancy in favour of -4 V (or -5 V) and (ii) moving to a Miller-clamp + DESAT driver (UCC21710 class),
which the safety analysis (15.1 section 6, FTA in `Reliability_Engineering/`) wants anyway.

## 5. Not verified / limits

* No gate-loop SPICE, no measurement; Ciss, g_fs, Rg_int, Vth,min(150 C), driver R_OH/R_OL, L_loop are recalled or assumed.
* Qgd(V) scaling with sqrt(V) and the 5 ns edge floor are modelling choices that change the hard-switching numbers by tens of percent.
* Crosstalk uses the quasi-static gate-charge method; a transient model with Cgd(V) would move the margins by +/-1 V.
* Package/common-source inductance is excluded (Kelvin source assumed effective).
