#!/usr/bin/env python3
"""Figures for chapter 04 from dabtools/dab/dab_model.py and design_values.json.
Outputs: ch04_power_vs_phi.png, ch04_edge_currents_vs_d.png, ch04_waveforms_three_ratios.png. Deterministic."""
import os, sys, json, math
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "SiC_6k6_Industrial_DAB"))
sys.path.insert(0, ROOT)
from dabtools.dab.dab_model import sps_power, sps_switching_currents, waveforms, sps_phi_for_power   # noqa: E402
V = json.load(open(os.path.join(ROOT, "04_Design_Calculations", "design_values.json")))
L, fs, n = V["L"], V["spec"]["fs"], V["spec"]["n"]
phi = np.linspace(-math.pi / 2, math.pi / 2, 361)
fig, ax = plt.subplots(figsize=(6.5, 3.8))
for V1, V2, c in ((800, 400, "C0"), (650, 300, "C1"), (850, 450, "C2"), (650, 450, "C3"), (850, 300, "C4")):
    ax.plot(np.degrees(phi), [sps_power(V1, n * V2, L, fs, p) / 1e3 for p in phi], color=c, label="%d / %d V (d = %.2f)" % (V1, V2, n * V2 / V1))
ax.axhline(6.6, color="k", ls="--", lw=0.8); ax.axhline(-6.6, color="k", ls="--", lw=0.8)
ax.text(-85, 7.0, "+6.6 kW", fontsize=8); ax.text(50, -7.6, "-6.6 kW (reverse)", fontsize=8)
ax.set_xlabel("outer phase shift phi (deg)"); ax.set_ylabel("P (kW), positive = HV -> LV")
ax.set_title("P = V1 V2' phi (pi - |phi|) / (2 pi^2 fs L), L = %.0f uH, fs = %.0f kHz" % (L * 1e6, fs / 1e3), fontsize=9)
ax.grid(alpha=0.3); ax.legend(fontsize=7)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch04_power_vs_phi.png"), dpi=130); plt.close(fig)

# edge currents I0 (HV bridge) and I1 (LV bridge) vs power for three voltage ratios
fig, ax = plt.subplots(figsize=(6.5, 3.8))
P = np.linspace(200, 6600, 65)
for V1, V2, c in ((800, 400, "C0"), (850, 300, "C4"), (650, 450, "C3")):
    I0, I1 = [], []
    for p in P:
        ph = sps_phi_for_power(V1, n * V2, L, fs, p); a, b = sps_switching_currents(V1, n * V2, L, fs, ph); I0.append(a); I1.append(b)
    ax.plot(P / 1e3, I0, color=c, label="I0 (HV edge) %d/%d V" % (V1, V2)); ax.plot(P / 1e3, I1, color=c, ls="--", label="I1 (LV edge) %d/%d V" % (V1, V2))
ax.axhline(V["nominal"]["Imin1"], color="k", ls=":", lw=0.8); ax.text(0.1, V["nominal"]["Imin1"] + 0.3, "I_min HV = %.1f A" % V["nominal"]["Imin1"], fontsize=8)
ax.axhline(0, color="k", lw=0.5)
ax.set_xlabel("power (kW)"); ax.set_ylabel("edge current referred to HV side (A)")
ax.set_title("SPS edge currents: negative = hard switching; d far from 1 loses ZVS on one bridge at light load", fontsize=9)
ax.grid(alpha=0.3); ax.legend(fontsize=7, ncol=2)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch04_edge_currents_vs_d.png"), dpi=130); plt.close(fig)

# bridge voltages and inductor current for d = 1, d < 1, d > 1 at 6.6 kW
fig, ax = plt.subplots(3, 1, figsize=(7, 7), sharex=True)
for a, (V1, V2) in zip(ax, ((800, 400), (850, 300), (650, 450))):
    ph = sps_phi_for_power(V1, n * V2, L, fs, 6600)
    th, v1, v2, i = waveforms(V1, n * V2, L, fs, ph)
    t = th / (2 * math.pi * fs) * 1e6
    a.step(t, v1 / 100, where="post", label="v1 / 100 V"); a.step(t, v2 / 100, where="post", label="n v2 / 100 V"); a.plot(t, i, color="C3", label="i_L (A)")
    a.set_title("%d / %d V, d = %.2f, phi = %.1f deg, I_pk = %.1f A, I_rms = %.1f A" % (V1, V2, n * V2 / V1, math.degrees(ph), np.abs(i).max(), math.sqrt(np.mean(i ** 2))), fontsize=9)
    a.grid(alpha=0.3); a.legend(fontsize=7, loc="upper right")
ax[-1].set_xlabel("t (us)")
fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch04_waveforms_three_ratios.png"), dpi=130); plt.close(fig)
print("ch04 figures written")
