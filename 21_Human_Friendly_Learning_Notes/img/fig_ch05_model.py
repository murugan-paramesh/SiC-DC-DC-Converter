#!/usr/bin/env python3
"""Figures for chapter 05 (mathematical model): closed form vs numerical cross-check, averaged-model gain,
and the 1/L regressor of the 2026 digital twin. Uses dabtools/dab/dab_model.py only. Deterministic.
Outputs: ch05_closed_vs_numeric.png, ch05_averaged_gain.png, ch05_regressor_1_over_L.png."""
import os, sys, json, math
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "SiC_6k6_Industrial_DAB"))
sys.path.insert(0, ROOT)
from dabtools.dab.dab_model import DABPoint, sps_power, sps_switching_currents   # noqa: E402
V = json.load(open(os.path.join(ROOT, "04_Design_Calculations", "design_values.json")))
L, fs, n = V["L"], V["spec"]["fs"], V["spec"]["n"]
V1, V2 = 800.0, 400.0
phis = np.linspace(0.02, math.pi / 2, 40)
Pc = [sps_power(V1, n * V2, L, fs, p) for p in phis]
Pn, I0n, I0c = [], [], []
for p in phis:
    pt = DABPoint(V1, V2, n, L, fs, p)
    Pn.append(pt.P); I0n.append(min(i for _, i in pt.switching_currents()[1])); I0c.append(sps_switching_currents(V1, n * V2, L, fs, p)[0])
fig, ax = plt.subplots(1, 2, figsize=(9, 3.6))
ax[0].plot(np.degrees(phis), np.array(Pc) / 1e3, label="closed form eq. (4)"); ax[0].plot(np.degrees(phis), np.array(Pn) / 1e3, "o", ms=3, label="numerical <v1 i>, N = 4000")
ax[0].set_xlabel("phi (deg)"); ax[0].set_ylabel("P (kW)"); ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3); ax[0].set_title("power: 800/400 V", fontsize=9)
ax[1].plot(np.degrees(phis), I0c, label="I0 closed form eq. (2)"); ax[1].plot(np.degrees(phis), I0n, "o", ms=3, label="min edge current, numerical")
ax[1].set_xlabel("phi (deg)"); ax[1].set_ylabel("I0 (A)"); ax[1].legend(fontsize=8); ax[1].grid(alpha=0.3); ax[1].set_title("HV-bridge edge current", fontsize=9)
err = max(abs(a - b) / b for a, b, p in zip(Pn, Pc, phis) if p >= math.radians(5)) * 100
err_small = max(abs(a - b) / b for a, b, p in zip(Pn, Pc, phis) if p < math.radians(5)) * 100
fig.suptitle("Closed form vs numerical engine of dab_model.py: max power error %.2f %% for phi >= 5 deg (%.1f %% below 5 deg: grid quantisation)" % (err, err_small), fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch05_closed_vs_numeric.png"), dpi=130); plt.close(fig)

# averaged model: I2(phi) and K_phi = dI2/dphi
phi_a = np.linspace(0, math.pi / 2, 200)
I2 = n * V1 * phi_a * (math.pi - phi_a) / (2 * math.pi ** 2 * fs * L)
K = n * V1 * (math.pi - 2 * phi_a) / (2 * math.pi ** 2 * fs * L)
fig, ax = plt.subplots(figsize=(6.5, 3.6)); ax2 = ax.twinx()
ax.plot(np.degrees(phi_a), I2, color="C0", label="I2(phi), eq. (10)"); ax2.plot(np.degrees(phi_a), K, color="C3", label="K_phi = dI2/dphi, eq. (11)")
ax.axvline(math.degrees(V["phi_nom"]), color="k", ls=":", lw=0.8); ax.text(math.degrees(V["phi_nom"]) + 1, 2, "phi_nom = %.1f deg\nI2 = 16.5 A" % math.degrees(V["phi_nom"]), fontsize=8)
ax.set_xlabel("phi (deg)"); ax.set_ylabel("average LV-port current I2 (A)", color="C0"); ax2.set_ylabel("small-signal gain K_phi (A/rad)", color="C3")
ax.set_title("Averaged (period) model at 800/400 V: the DAB is a phi-controlled current source", fontsize=9); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch05_averaged_gain.png"), dpi=130); plt.close(fig)

# twin regressor: every current scales with 1/L (lossless model) -> I2 = g(phi, D1, D2, V1, V2) / L
Ls = np.linspace(0.6, 1.4, 9) * L
fig, ax = plt.subplots(figsize=(6.5, 3.6))
for ph, D1, D2, c in ((V["phi_nom"], 1.0, 1.0, "C0"), (0.25, 1.0, 1.0, "C1"), (V["phi_nom"], 0.8, 1.0, "C2")):
    I2s = [DABPoint(V1, V2, n, l, fs, ph, D1, D2, N=1500).P2 / V2 for l in Ls]
    ax.plot(1 / (Ls * 1e6) * 1e3, I2s, "o-", color=c, ms=4, label="phi = %.1f deg, D1 = %.1f, D2 = %.1f" % (math.degrees(ph), D1, D2))
ax.set_xlabel("1/L (1/mH)"); ax.set_ylabel("period-average I2 (A)")
ax.set_title("Digital-twin regressor: I2_avg = g(pattern, V1, V2) x (1/L) is linear in 1/L for every pattern", fontsize=9)
ax.grid(alpha=0.3); ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch05_regressor_1_over_L.png"), dpi=130); plt.close(fig)
print("ch05 figures written, max P error %.3f %% (phi >= 5 deg), %.2f %% (phi < 5 deg)" % (err, err_small))
