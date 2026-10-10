#!/usr/bin/env python3
"""Figures for chapter 01 (electrical fundamentals), drawn from the project's own DAB model.
Outputs: ch01_inductor_voltseconds.png, ch01_rms_avg_peak.png. Deterministic (no random numbers)."""
import os, sys, json, math
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "SiC_6k6_Industrial_DAB"))
sys.path.insert(0, ROOT)
from dabtools.dab.dab_model import waveforms                      # noqa: E402
V = json.load(open(os.path.join(ROOT, "04_Design_Calculations", "design_values.json")))
L, fs, phi = V["L"], V["spec"]["fs"], V["phi_nom"]
V1, V2p = 800.0, 2.0 * 400.0
theta, v1, v2, i = waveforms(V1, V2p, L, fs, phi, N=4000)
t_us = theta / (2 * math.pi * fs) * 1e6
vL = v1 - v2
fig, ax = plt.subplots(2, 1, figsize=(7, 5.2), sharex=True)
ax[0].step(t_us, vL, where="post", color="C0")
ax[0].set_ylabel("v_L = v1 - v2' (V)")
ax[0].set_title("Series inductor L = %.0f uH at 800/400 V, phi = %.1f deg: volt-seconds balance" % (L * 1e6, math.degrees(phi)))
ax[0].fill_between(t_us, 0, vL, where=vL > 0, color="C0", alpha=0.25, step="post", label="+ volt-seconds")
ax[0].fill_between(t_us, 0, vL, where=vL < 0, color="C3", alpha=0.25, step="post", label="- volt-seconds (equal area)")
ax[0].legend(loc="upper right", fontsize=8); ax[0].grid(alpha=0.3)
ax[1].plot(t_us, i, color="C1")
ax[1].set_ylabel("i_L (A, HV side)"); ax[1].set_xlabel("t (us)")
ax[1].annotate("slope (V1+V2')/L = %.0f A/us" % ((V1 + V2p) / L / 1e6), xy=(0.4, 0), xytext=(1.6, -7),
               arrowprops=dict(arrowstyle="->"), fontsize=8)
ax[1].annotate("slope (V1-V2')/L = 0 (d = 1)", xy=(3.0, i.max()), xytext=(3.6, 5), arrowprops=dict(arrowstyle="->"), fontsize=8)
ax[1].axhline(0, color="k", lw=0.5); ax[1].grid(alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch01_inductor_voltseconds.png"), dpi=130); plt.close(fig)

# rms / average / peak of the three waveform shapes a converter engineer meets
t = np.linspace(0, 1, 2001)
sine = np.sin(2 * math.pi * t)
square = np.sign(sine); square[square == 0] = 1
tri = 2 * np.abs(2 * (t - np.floor(t + 0.5))) - 1
fig, ax = plt.subplots(1, 3, figsize=(9, 2.8))
for a, (name, y) in zip(ax, (("sine", sine), ("square", square), ("triangle", tri))):
    a.plot(t, y, color="C0"); a.axhline(0, color="k", lw=0.5)
    rms = math.sqrt(np.mean(y ** 2)); avg_abs = np.mean(np.abs(y))
    a.axhline(rms, color="C3", ls="--", lw=1); a.axhline(avg_abs, color="C2", ls=":", lw=1)
    a.set_title("%s: peak 1, rms %.3f,\nmean|x| %.3f" % (name, rms, avg_abs), fontsize=9)
    a.set_ylim(-1.3, 1.3); a.grid(alpha=0.3); a.set_xticks([])
ax[0].text(0.02, 1.08, "rms (dashed), mean|x| (dotted)", fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch01_rms_avg_peak.png"), dpi=130); plt.close(fig)
print("ch01 figures written")
