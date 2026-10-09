#!/usr/bin/env python3
"""
Digital control design and modulation comparison for the DAB.

1. Small-signal plant (averaged model, 03 section 7): G(s) = K_phi R / (1 + s R C2), digital delay 1.5 Ts.
2. PI design: crossover and phase margin with the delay; discrete gains for the 100 kHz ISR.
3. Gain scheduling: K_phi varies with V1 and phi -> normalised controller output (power) + feedforward
   makes the loop gain independent of V1 (the feedforward inverts the modulator).
4. Modulation comparison at the voltage-ratio corners: SPS vs EPS (voltage matching) vs DPS vs TPS
   (numerical minimum-rms search): rms current, backflow power, ZVS margin vs load.
5. MPC research alternative: one-step-ahead explicit MPC on the averaged model with a quadratic cost
   compared with the PI on the same averaged plant (load step), including its computational cost.
Outputs: control_design.md, img/*.png, control_params.json (consumed by the firmware).
"""
import os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
from tools.dab import dab_model as M
from tools.dab.devices import DEVICES
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
V = json.load(open(os.path.join(ROOT, "04_Design_Calculations", "design_values.json")))
L, n, fs, P = V["L"], V["spec"]["n"], V["spec"]["fs"], V["spec"]["P"]
Ts = 1 / fs
C2 = V["dclink"]["C2"] + 1000e-6            # with the external 1 mF (APP-04)
R = 400 ** 2 / P
d1, d2 = DEVICES[V["dev1"]], DEVICES[V["dev2"]]
IMG = os.path.join(HERE, "img")

# ---------------------------------------------------------------- 1-2. loop design (power-normalised controller)
# controller output = power command P_cmd (W); feedforward phi = f^-1(P_cmd) linearises the modulator so the
# plant seen by the PI is  v2 / P_cmd = (1/v2) * R/(1 + s R C2)  ->  at the operating point: G = R/(V2 (1 + sRC2))
V2 = 400.0
Td = 1.5 * Ts
def loop(kp, ki, f):
    s = 2j * math.pi * f
    Gp = (R / V2) / (1 + s * R * C2) * np.exp(-s * Td)
    Gc = kp + ki / s
    return Gc * Gp
def margins(kp, ki):
    f = np.logspace(1, 5, 2000); Lg = np.array([loop(kp, ki, x) for x in f])
    mag = np.abs(Lg); idx = np.argmin(np.abs(mag - 1)); fc = f[idx]; pm = 180 + np.degrees(np.angle(Lg[idx]))
    ph = np.degrees(np.angle(Lg)); i180 = np.argmax(ph < -180) if (ph < -180).any() else None
    gm = -20 * np.log10(mag[i180]) if i180 else float("inf")
    return fc, pm, gm, f, Lg
# target crossover 600 Hz (~ fs/170), PI zero at the plant pole for a first-order loop
fz = 1 / (2 * math.pi * R * C2)
fc_target = 600.0
# |Gc Gp| = 1 at fc with Gc ~ kp (zero well below): kp = V2 / R * |1 + j fc/fz|
kp = V2 / R * abs(1 + 1j * fc_target / fz)
fz_pi = fc_target / 5.0                      # PI zero at fc/5: fast integral recovery, ~11 deg PM cost
ki = 2 * math.pi * fz_pi * kp
fc, pm, gm, f, Lg = margins(kp, ki)
fig, ax = plt.subplots(2, 1, figsize=(6, 5), sharex=True)
ax[0].semilogx(f, 20 * np.log10(np.abs(Lg))); ax[0].axhline(0, c="k", lw=0.7); ax[0].set_ylabel("|L| (dB)"); ax[0].set_title(f"Voltage loop: fc = {fc:.0f} Hz, PM = {pm:.0f} deg, GM = {gm:.1f} dB (delay 1.5 Ts)")
ax[1].semilogx(f, np.degrees(np.angle(Lg))); ax[1].axhline(-180, c="r", ls="--", lw=0.7); ax[1].set_ylabel("phase (deg)"); ax[1].set_xlabel("Hz")
[a.grid(alpha=0.3) for a in ax]; fig.tight_layout(); fig.savefig(os.path.join(IMG, "loop_bode.png"), dpi=130); plt.close(fig)
# sensitivity of the margins to V1 (K_phi) when the feedforward is NOT used (shows why normalisation matters)
sens = []
for V1 in (650, 800, 850):
    phi = M.sps_phi_for_power(V1, n * V2, L, fs, P / 2)
    Kphi = n * V1 * (math.pi - 2 * phi) / (2 * math.pi ** 2 * fs * L)       # A/rad
    sens.append((V1, Kphi))

# ---------------------------------------------------------------- 4. modulation comparison at corners vs load
Imin1 = M.zvs_current_min(d1["Coss_er"], 800, L); 
def point(V1, V2_, Pt, mod):
    V2p = n * V2_; d = V2p / V1
    Imin1 = M.zvs_current_min(d1["Coss_er"], V1, L); Imin2 = M.zvs_current_min(d2["Coss_er"], V2_, L / n ** 2) / n
    if mod == "SPS":
        phi = M.sps_phi_for_power(V1, V2p, L, fs, Pt); pt = M.DABPoint(V1, V2_, n, L, fs, phi, N=1500)
    elif mod == "EPS":
        D1, D2 = (max(0.12, min(1, d)), 1.0) if d < 1 else (1.0, max(0.12, min(1, 1 / d)))
        pt = _solve(V1, V2_, Pt, D1, D2)
    elif mod == "DPS":
        best = None
        for D in np.linspace(0.5, 1.0, 11):
            q = _solve(V1, V2_, Pt, D, D)
            if q and (best is None or q.I_rms1 < best.I_rms1): best = q
        pt = best
    else:
        pt, _ = M.tps_search(V1, V2_, n, L, fs, Pt, d1["Coss_er"], d2["Coss_er"], grid=9, N=1200)
    if pt is None: return None
    return dict(Irms=pt.I_rms1, back=pt.Q_backflow, zvs=min(pt.zvs_margin(1, Imin1), pt.zvs_margin(2, Imin2)), D1=pt.D1, D2=pt.D2, phi=pt.phi)
def _solve(V1, V2_, Pt, D1, D2):
    lo, hi = 0.0, math.pi / 2
    for _ in range(28):
        mid = (lo + hi) / 2; q = M.DABPoint(V1, V2_, n, L, fs, mid, D1, D2, N=1500)
        if q.P < Pt: lo = mid
        else: hi = mid
    q = M.DABPoint(V1, V2_, n, L, fs, (lo + hi) / 2, D1, D2, N=1500)
    return q if abs(q.P - Pt) < 0.03 * Pt else None
mods = ("SPS", "EPS", "DPS", "TPS")
loads = (0.25, 0.5, 0.75, 1.0)
cmp_tbl = {}
for (V1, V2_) in ((850, 300), (650, 450), (800, 400)):
    for mod in mods:
        for fr in loads:
            try:
                cmp_tbl[(V1, V2_, mod, fr)] = point(V1, V2_, P * fr, mod)
            except ValueError:
                cmp_tbl[(V1, V2_, mod, fr)] = None
fig, ax = plt.subplots(1, 3, figsize=(12, 3.6))
for k, (V1, V2_) in enumerate(((850, 300), (650, 450), (800, 400))):
    for mod in mods:
        ys = [cmp_tbl[(V1, V2_, mod, fr)]["Irms"] if cmp_tbl[(V1, V2_, mod, fr)] else np.nan for fr in loads]
        ax[k].plot([100 * x for x in loads], ys, marker="o", label=mod)
    ax[k].set_title(f"{V1} V / {V2_} V"); ax[k].set_xlabel("load (%)"); ax[k].set_ylabel("I_rms HV side (A)"); ax[k].grid(alpha=0.3); ax[k].legend(fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(IMG, "modulation_rms.png"), dpi=130); plt.close(fig)

# ---------------------------------------------------------------- 5. MPC alternative on the averaged model
# discrete averaged plant: v2[k+1] = v2[k] + Ts/C2 * (I2(P_cmd[k-1]) - v2[k]/R)  (one-period delay), I2 = P/v2
def sim_avg(ctrl, steps=4000, step_at=2000):
    v2 = 400.0; u_prev = P / 2; log = []
    Rl = R * 2
    for k in range(steps):
        if k == step_at: Rl = R
        I2 = u_prev / max(v2, 40)
        v2 = v2 + Ts / C2 * (I2 - v2 / Rl)
        u = ctrl(v2, k)
        u_prev = u; log.append(v2)
    return np.array(log)
class PIc:
    def __init__(s): s.i = 0.0
    def __call__(s, v2, k):
        e = 400 - v2; u = kp * e + s.i
        if -1.1 * P < u < 1.1 * P: s.i += ki * Ts * e
        return max(-1.1 * P, min(1.1 * P, u))
class MPC:
    """Explicit one-step MPC: choose P_cmd minimising (v2[k+2]-ref)^2 + lam*(dP)^2 with the delay model; load estimated by a disturbance observer."""
    def __init__(s): s.u = P / 2; s.Ihat = 0.0; s.v_prev = 400.0
    def __call__(s, v2, k):
        # observer: load current estimate from the measured v2 slope and the last command
        s.Ihat = 0.9 * s.Ihat + 0.1 * (s.u / max(v2, 40) - (v2 - s.v_prev) * C2 / Ts); s.v_prev = v2
        # prediction with the one-period delay: v2[k+1] uses u[k-1] (= s.u); v2[k+2] uses u[k]
        v_k1 = v2 + Ts / C2 * (s.u / max(v2, 40) - s.Ihat)
        lam = 1e-9
        # minimise J = (v_k1 + Ts/C2*(u/v_k1 - Ihat) - 400)^2 + lam (u - s.u)^2  -> quadratic in u, closed form
        a = Ts / C2 / max(v_k1, 40); b = v_k1 - Ts / C2 * s.Ihat - 400
        u = (-(a * b) + lam * s.u) / (a * a + lam)
        s.u = max(-1.1 * P, min(1.1 * P, u))
        return s.u
pi_log = sim_avg(PIc()); mpc_log = sim_avg(MPC())
t = np.arange(len(pi_log)) * Ts * 1e3
fig, a = plt.subplots(figsize=(6, 3.6))
a.plot(t, pi_log, label="PI (fc 600 Hz)"); a.plot(t, mpc_log, label="explicit 1-step MPC + observer"); a.axvline(2000 * Ts * 1e3, c="gray", ls="--", lw=0.7)
a.set_xlabel("t (ms)"); a.set_ylabel("V2 (V)"); a.set_title("Averaged model, 50 -> 100 % load step at 20 ms"); a.legend(); a.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(IMG, "mpc_vs_pi.png"), dpi=130); plt.close(fig)
def settle(x, band=1.0):
    out = np.nonzero(np.abs(x[2000:] - 400) > band)[0]
    return float((out[-1] + 1) * Ts * 1e3) if len(out) else 0.0
mpc_res = dict(pi_dip=float(400 - pi_log[2000:].min()), mpc_dip=float(400 - mpc_log[2000:].min()), pi_settle_ms=settle(pi_log), mpc_settle_ms=settle(mpc_log))

# ---------------------------------------------------------------- outputs
params = dict(kp=kp, ki=ki, fc=fc, pm=pm, gm=gm, Td=Td, C2=C2, phi_max_deg=60, D_min=0.12, V2_floor=40.0,
              phi_dead_comp_rad=0.5 * 2 * math.pi * fs * V["t_dead"], soft_start_s=0.05, slew_W_per_s=2e6,
              limits=dict(v1_ov=900, v1_uv=600, v2_ov=480, v2_uv=250, i_pk_hv=float(V["I_limit_pk"]), T_max=95),
              tps_table_note="EPS voltage matching (D = d) in firmware; TPS table generation in 12_Optimization")
json.dump(params, open(os.path.join(HERE, "control_params.json"), "w"), indent=1)
def md():
    R_ = []; w = R_.append
    w("# 11 - Digital control design\n\n_Generated by `control_design.py`_\n")
    w("## 1. Plant and controller structure\n")
    w("Averaged model (03, eq. 10-12): the DAB is a current source into the LV link. The controller output is a **power command** and the "
      "modulator inverse (`phi_from_power`, current form) linearises it, so the loop gain does not depend on V1 or on the operating phase shift "
      f"(without the feedforward K_phi varies from {sens[0][1]:.1f} to {sens[2][1]:.1f} A/rad between 650 and 850 V, a +/-15 % gain change that the PI would otherwise have to tolerate). "
      "The one-period computation delay plus the PWM update give T_d = 1.5 T_s = 15 us.\n")
    w("## 2. PI design\n")
    w(f"| item | value |\n|---|---|\n| LV capacitance (link + external) | {C2*1e3:.2f} mF |\n| plant pole at full load | {fz:.0f} Hz |
| PI zero | {fz_pi:.0f} Hz (fc/5) |\n| kp | {kp:.1f} W/V |\n| ki | {ki:.3g} W/(V s) |\n| crossover | {fc:.0f} Hz |\n| phase margin | {pm:.0f} deg |\n| gain margin | {gm:.1f} dB |\n| anti-windup | clamping (integrate only when unsaturated) |\n| output limits | +/- 1.1 P_rated, slew 2 kW/ms |\n")
    w("![bode](img/loop_bode.png)\n")
    w("The 600 Hz crossover (f_s/167) keeps the delay phase lag at 3 deg and gives a 2.8 % dip for a 50 % load step in the switched simulation (05_Simulation), against the 3 % requirement EL-10. "
      "Quantisation: the C2000 EPWM has a 10 ns resolution (1/1000 of the period, 0.36 deg); the ADC is 12 bit (0.25 V on an 850 V range), both negligible against the 1 % regulation requirement.\n")
    w("## 3. Modulation comparison (analytical, HV-side rms current)\n")
    w("| V1/V2 | load | SPS I_rms / backflow / ZVS margin | EPS | DPS | TPS |\n|---|---|---|---|---|---|")
    for (V1, V2_) in ((850, 300), (650, 450), (800, 400)):
        for fr in loads:
            cells = []
            for mod in mods:
                c = cmp_tbl[(V1, V2_, mod, fr)]
                cells.append(f"{c['Irms']:.1f} A / {c['back']:.0f} W / {c['zvs']:+.1f} A" if c else "-")
            w(f"| {V1}/{V2_} | {100*fr:.0f} % | " + " | ".join(cells) + " |")
    w("\n![mod](img/modulation_rms.png)\n")
    w("EPS voltage matching (D of the higher-voltage bridge = d) removes most of the circulating power at d far from 1 and keeps ZVS at light load; "
      "it is the firmware default because it needs no table. TPS gives the lowest rms current but the gain over EPS is small at this ratio range; "
      "it is kept as an optional look-up table (12_Optimization). All modulation changes are applied by the ISR at the period boundary with the same "
      "feedforward, so the voltage loop sees the same linearised plant.\n")
    w("## 4. Model predictive control (research alternative)\n")
    w(f"An explicit one-step MPC with a disturbance observer on the averaged model gives a {mpc_res['mpc_dip']:.1f} V dip versus {mpc_res['pi_dip']:.1f} V for the PI on a 50 % step; "
      f"settling (1 V band) {mpc_res['mpc_settle_ms']} ms vs {mpc_res['pi_settle_ms']} ms. The explicit form costs ~30 multiply-adds per ISR (equivalent to the PI), but it relies on the "
      "load estimate and the plant parameters (C2, delay); in the switched simulation the PI with feedforward already meets EL-08/EL-10, so the MPC remains a documented research option, not the baseline.\n")
    w("![mpc](img/mpc_vs_pi.png)\n")
    w("## 5. Reverse power flow\n")
    w("In CP mode the power reference is signed; the feedforward returns a negative phi and the same PI trims the regulated port. The switched simulation (05) "
      "ramps +6.6 kW to -6.6 kW in 6.6 ms (2 kW/ms slew) with < 0.7 % excursion on either link.\n")
    return "\n".join(R_) + "\n"
open(os.path.join(HERE, "control_design.md"), "w").write(md())
print(json.dumps(dict(kp=kp, ki=ki, fc=fc, pm=pm, gm=gm, mpc=mpc_res), indent=1))
