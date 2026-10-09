# 03 - Mathematical model of the single-phase dual active bridge

Implementation: `tools/dab/dab_model.py` (waveforms, power, switching currents, ZVS),
`tools/dab/losses.py`, `tools/dab/magnetics.py`. Symbols: V1 HV-port voltage, V2 LV-port
voltage, n = N1/N2, V2' = nV2, d = V2'/V1, L series inductance referred to the HV side,
fs switching frequency, omega = 2 pi fs, phi outer phase shift (rad, bridge 2 lags bridge 1 for
power 1 -> 2), D1, D2 inner duty ratios (fraction of the half period during which a bridge
voltage is non-zero).

## 1. Circuit and bridge voltages

The two full bridges produce three-level voltages v1(t) in {+V1, 0, -V1} and v2'(t) in
{+V2', 0, -V2'}; the series inductance L (transformer leakage + external) links them:

    L di/dt = v1(t) - v2'(t)                                   (1)

With a magnetising inductance Lm >> L the magnetising current is neglected in the power
transfer (it is included in the magnetics loss model). Steady state requires <i> = 0.

## 2. Single phase shift (SPS, D1 = D2 = 1)

Piecewise-linear current over a half period (0 <= theta <= pi, theta = omega t):

    0 <= theta < phi :      di/dtheta = (V1 + V2') / (omega L)
    phi <= theta < pi :     di/dtheta = (V1 - V2') / (omega L)

with half-wave symmetry i(theta + pi) = -i(theta). Solving with i(0) = -I0:

    I0 = [ V1 pi + V2' (2 phi - pi) ] / (2 omega L)             (2)   current at the bridge-1 edge
    I1 = [ V1 (2 phi - pi) + V2' pi ] / (2 omega L)             (3)   current at the bridge-2 edge

Average power (from <v1 i>):

    P = V1 V2' phi (pi - |phi|) / (2 pi^2 fs L),   |phi| <= pi/2                  (4)
    P_max = V1 V2' / (8 fs L)  at phi = pi/2                                         (5)

Equation (4) is the design equation for L: L = V1 V2' phi_nom (pi - phi_nom) / (2 pi^2 fs P).
The script `04_Design_Calculations/dab_design.py` picks phi_nom (default 30 deg at 800/400 V,
6.6 kW) and then checks (5) and the phase-shift margin at every (V1, V2) corner.

RMS and peak current (closed form, SPS) are obtained by integrating the trapezoid; the
implementation integrates (1) numerically on a 4000-point grid so that the same code serves
SPS, EPS, DPS and TPS. The numerical result was cross-checked against (2)-(4) at
800/400 V, 6.6 kW: P = 6595 W vs 6600 W, I0 = I1 = 9.65 A vs 9.57-9.63 A (grid resolution).

## 3. Reactive (circulating) power

Instantaneous port-1 power p1 = v1 i is negative during the interval after each bridge-1
edge while the current has not yet reversed (duration phi - theta_zc). The model reports the
average negative part Q_back = -<min(p1, 0)> (W) and the time fraction. For d = 1 the
circulating interval is small; for d far from 1 it grows and is the main driver of extra
conduction loss - the motivation for DPS/TPS (section 5).

## 4. Zero-voltage switching

A leg switches with ZVS when, at the dead-time start, the inductor current flows out of the
leg in the direction that discharges the output capacitance of the device about to turn on.
Ideal (energy-free) conditions from (2)-(3):

    bridge 1 (HV):  I0 > 0  <=>  phi > pi (d - 1) / (2 d)       (6)
    bridge 2 (LV):  I1 > 0  <=>  phi > pi (1 - d) / 2           (7)

With finite output capacitance the energy criterion is applied (conservative; Everts et al.
2014 give the exact charge-based condition):

    1/2 L I_sw^2 >= Coss,er,leg V_dc^2 + 1/2 C_par V_dc^2,   I_min = sqrt(2 E / L)       (8)

where Coss,er is the energy-related output capacitance of one device (two per leg, one
charging, one discharging: E = Coss,er V^2) and C_par the transformer winding capacitance
referred to the bridge. The required dead time is charge based:

    t_dead >= 2 Qoss(V_dc) / I_sw                                                       (9)

`DABPoint.switching_currents()` evaluates the current at every edge of both bridge voltages
with the correct sign, so the same test works for any modulation; `zvs_margin()` returns
min(I_edge) - I_min.

## 5. Extended modulations

* EPS: one bridge three-level (D < 1), the other square.
* DPS: both bridges with the same inner shift D1 = D2 = D (Bai & Mi 2008, Zhao et al. 2012).
* TPS: independent D1, D2 and phi (Krismer & Kolar 2012 give the closed-form minimum
  conduction-loss solution). `dab_model.tps_search()` performs a bounded grid/bisection
  search minimising the rms inductor current at a target power subject to (8) on all edges.
  It is used to quantify how much rms current and backflow power can be removed at the
  voltage-ratio corners (04_Design_Calculations, 11_Control_Algorithms). In firmware the
  result is stored as a look-up table over (d, P).

The power in the general case is obtained numerically as <v1 i>; for DPS the closed form
(Zhao 2012) is P = V1 V2' / (2 pi^2 fs L) * [phi (pi - phi) - pi^2 D^2/2 ...] - the numerical
engine was used instead of transcribing the piecewise closed form, and it reproduces the SPS
special case to < 0.1 %.

## 6. Loss model (per operating point)

Semiconductors (`losses.py`): conduction I_dev,rms^2 Rds(Tj) with Rds interpolated between
25 C and 150 C; turn-off E_off(V, I) fs k_zvs with k_zvs = 0.35 (assumption: under ZVS most of
the datasheet E_off is the Coss charging energy that is recycled, cf. Krismer 2010); hard
switching (E_on + E_off + Coss,er V^2) fs when (8) fails; body-diode conduction during the
dead time; gate charge loss Qg (Vgs,on - Vgs,off) fs. Device rms current = I_rms / sqrt(2)
(each device conducts half the period).

Transformer and inductor (`magnetics.py`): Steinmetz Pv = k f^alpha B^beta with an iGSE
multiplier for triangular flux; copper loss with Dowell's AC resistance applied at the strand
level for litz wire; leakage inductance and interwinding capacitance estimates (Hurley &
Woelfle 2013).

Capacitors: I_rms^2 ESR with the pulsating bridge current computed from the waveform.

## 7. Averaged model for control design

For control bandwidths far below fs the DAB is a current source controlled by phi (SPS):

    I2(phi) = P / V2 = n V1 phi (pi - phi) / (2 pi^2 fs L)                              (10)
    dI2/dphi = n V1 (pi - 2 phi) / (2 pi^2 fs L)  =: K_phi(phi)                         (11)

With the LV-port capacitor C2 and a load/source modelled as R (or a battery with R_int):

    G_vphi(s) = V2(s)/phi(s) = K_phi * R / (1 + s R C2)                                 (12)

Digital implementation adds the sampling/PWM delay e^{-s T_d}, T_d ~ 1.5 Ts (sample, compute,
update at the next period). The PI design and the feedforward phi_ff = f^{-1}(P_ref, V1, V2)
are developed in `11_Control_Algorithms/` using (10)-(12); the small-signal model is validated
against the switched simulation by a load step in `05_Simulation/`.

## 8. DC-link ripple

The bridge input current i1(t) = i(t) sgn(v1(t)) is pulsating at 2 fs; the capacitor carries
i_C = i1 - <i1>. The rms capacitor current and the voltage ripple Delta V = max(integral of
i_C)/C are computed numerically from the waveform (`04_Design_Calculations`).
