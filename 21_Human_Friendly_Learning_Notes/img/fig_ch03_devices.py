#!/usr/bin/env python3
"""Figures for chapter 03 from dabtools/dab/devices.py (datasheet-typical values, verified=False).
Outputs: ch03_rds_vs_tj.png, ch03_zvs_current_min.png. Deterministic."""
import os, sys, json, math
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "SiC_6k6_Industrial_DAB"))
sys.path.insert(0, ROOT)
from dabtools.dab.devices import DEVICES, rds_on                  # noqa: E402
from dabtools.dab.dab_model import zvs_current_min                # noqa: E402
V = json.load(open(os.path.join(ROOT, "04_Design_Calculations", "design_values.json")))
L, n = V["L"], V["spec"]["n"]
Tj = np.linspace(25, 175, 151)
fig, ax = plt.subplots(figsize=(6.5, 3.6))
for dev, c in (("C3M0032120K", "C0"), ("C3M0016120K", "C1"), ("C3M0060065K", "C2")):
    ax.plot(Tj, [rds_on(dev, T) * 1e3 for T in Tj], color=c, label="%s (%.0f -> %.0f mOhm)" % (dev, DEVICES[dev]["Rds_25"] * 1e3, DEVICES[dev]["Rds_150"] * 1e3))
for dev, T in (("C3M0032120K", V["nominal"]["Tj1"]), ("C3M0016120K", V["nominal"]["Tj2"])):
    ax.plot([T], [rds_on(dev, T) * 1e3], "ko", ms=5)
ax.annotate("design points: Tj = %.0f / %.0f C at 800/400 V, 6.6 kW" % (V["nominal"]["Tj1"], V["nominal"]["Tj2"]), xy=(50, 20), xytext=(70, 70), arrowprops=dict(arrowstyle="->"), fontsize=8)
ax.set_xlabel("junction temperature Tj (C)"); ax.set_ylabel("Rds(on) (mOhm)")
ax.set_title("Rds(on) vs Tj: linear interpolation of two datasheet-typical points (devices.py, verified=False)", fontsize=9)
ax.grid(alpha=0.3); ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch03_rds_vs_tj.png"), dpi=130); plt.close(fig)

# minimum ZVS current vs DC voltage (energy criterion) for both bridges, with the series inductance referred to each side
fig, ax = plt.subplots(figsize=(6.5, 3.6))
Vhv = np.linspace(650, 850, 41); Vlv = np.linspace(300, 450, 31)
ax.plot(Vhv, [zvs_current_min(DEVICES["C3M0032120K"]["Coss_er"], v, L, V["C_par"]) for v in Vhv], label="HV bridge C3M0032120K, L = %.0f uH, C_par = %.0f pF" % (L * 1e6, V["C_par"] * 1e12))
ax.plot(Vlv, [zvs_current_min(DEVICES["C3M0016120K"]["Coss_er"], v, L / n ** 2) for v in Vlv], label="LV bridge C3M0016120K, L/n^2 = %.0f uH (LV-side A)" % (L / n ** 2 * 1e6))
ax.set_xlabel("DC-link voltage of the bridge (V)"); ax.set_ylabel("I_min for complete ZVS (A)")
ax.set_title("ZVS current threshold I_min = sqrt(2 (Coss,er V^2 + 0.5 C_par V^2) / L)", fontsize=9)
ax.grid(alpha=0.3); ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch03_zvs_current_min.png"), dpi=130); plt.close(fig)
print("ch03 figures written")
