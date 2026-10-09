#!/usr/bin/env python3
"""
Switched-model time-domain simulation of the PSFB power stage.

Model: ideal full bridge producing v_AB (+Vin / 0 / -Vin with the designed phase shift),
resonant inductor Lr in series with an ideal transformer (magnetising inductance Lm),
centre-tapped ideal rectifier, output inductor Lo, output capacitor Co (with ESR) and a
resistive load.  The rectifier has two modes:
  * powering   - one rectifier conducts, secondary current = iLo, Lr and Lo share v_AB
  * freewheel  - both rectifiers conduct (secondary shorted) while Lr reverses the primary
                 current; this is the duty-cycle loss interval.
A slow integral regulator trims the phase shift so the output settles at 48 V.

Run:  python3 simulation/psfb_sim.py   -> docs/img/sim_waveforms.png + printed summary
"""
import json, os, math
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V = json.load(open(os.path.join(ROOT, "design", "design_values.json")))

Vin, Vo_t, Io = V["spec"]["Vin_nom"], V["spec"]["Vout"], V["spec"]["Iout"]
fsw, n, Lr, Lm = V["spec"]["fsw"], V["n"], V["Lr"], V["Lm"]
Lo, Co, ESR = V["Lo_full"], V["Co_total"], 0.0033
R = Vo_t / Io
T = 1 / fsw
dt = 1e-9
cycles = 400
phase = V["Deff_nom"] + V["dD_nom"]

ip, im, iLo, vC = 0.0, 0.0, Io, Vo_t
mode, s = "free", 1
rec = {k: [] for k in ("t", "vab", "ip", "vsec", "vsr", "iLo", "vo", "mode")}
vo_acc, n_acc = 0.0, 0
k_cycle = int(T / dt)
for k in range(cycles * k_cycle):
    t = k * dt
    tc = (k % k_cycle) / k_cycle
    if tc < 0.5:
        vab = Vin if tc < phase / 2 else 0.0
    else:
        vab = -Vin if (tc - 0.5) < phase / 2 else 0.0
    vo = vC + (iLo - vC / R) * ESR
    if mode == "free":
        vsec = 0.0
        ip += vab / Lr * dt
        iLo += (-vo) / Lo * dt
        isec = n * (ip - im)
        if abs(isec) >= iLo:
            mode, s = "pow", 1 if isec > 0 else -1
            ip = im + s * iLo / n
    else:
        a = 1 + Lr / Lm
        x = (vab - a * n * s * vo) / (Lr * s / n + a * n * s * Lo)
        vsec = Lo * x + vo
        if vsec < 0:
            mode = "free"
            vsec = 0.0
            ip += vab / Lr * dt
            iLo += (-vo) / Lo * dt
        else:
            vpri = n * s * vsec
            iLo += x * dt
            im += vpri / Lm * dt
            ip = im + s * iLo / n
    ic = iLo - vC / R
    vC += ic / Co * dt
    vo_acc += vo; n_acc += 1
    if (k + 1) % k_cycle == 0:
        phase += 0.05 * (Vo_t - vo_acc / n_acc) / Vo_t
        phase = min(max(phase, 0.05), 0.98)
        vo_acc, n_acc = 0.0, 0
    if k >= (cycles - 2) * k_cycle and k % 5 == 0:
        rec["t"].append(t); rec["vab"].append(vab); rec["ip"].append(ip); rec["vsec"].append(vsec)
        rec["vsr"].append(2 * vsec); rec["iLo"].append(iLo); rec["vo"].append(vo); rec["mode"].append(1 if mode == "pow" else 0)

t = (np.array(rec["t"]) - rec["t"][0]) * 1e6
ip_a, iLo_a, vo_a, vsr_a = map(np.array, (rec["ip"], rec["iLo"], rec["vo"], rec["vsr"]))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
fig, ax = plt.subplots(4, 1, figsize=(7, 8.5), sharex=True)
ax[0].plot(t, rec["vab"]); ax[0].set_ylabel("v_AB (V)")
ax[1].plot(t, ip_a); ax[1].set_ylabel("i_primary (A)")
ax[2].plot(t, vsr_a); ax[2].set_ylabel("SR off-state (V)")
ax[3].plot(t, iLo_a); ax[3].set_ylabel("i_Lo (A)"); ax[3].set_xlabel("time (us)")
b = ax[3].twinx(); b.plot(t, vo_a, color="C1"); b.set_ylabel("v_out (V)", color="C1")
for a in ax:
    a.grid(alpha=0.3)
fig.suptitle(f"PSFB switched model: {Vin:.0f} V in, {Io:.1f} A out, total duty = {phase:.3f}")
fig.tight_layout()
out = os.path.join(ROOT, "docs", "img", "sim_waveforms.png")
fig.savefig(out, dpi=140)
print(f"steady state: Vout = {vo_a.mean():.2f} V, output ripple = {(vo_a.max()-vo_a.min())*1e3:.0f} mV p-p, "
      f"i_Lo ripple = {iLo_a.max()-iLo_a.min():.1f} A p-p, primary peak = {abs(ip_a).max():.1f} A, "
      f"primary rms = {math.sqrt(np.mean(ip_a**2)):.1f} A, SR stress = {vsr_a.max():.0f} V, total duty = {phase:.3f} "
      f"(design: {V['D_nom']:.3f})")
print("saved", out)
