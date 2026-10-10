#!/usr/bin/env python3
"""Figure for chapter 02: hard switching (v-i overlap) versus zero-voltage switching (capacitive commutation).
Conceptual sketch with the project's edge values: 800 V, 9.75 A (design_values.json), Coss_tr = 320 pF (devices.py).
Output: ch02_hard_vs_soft.png. Deterministic."""
import os, sys, json, math
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "SiC_6k6_Industrial_DAB"))
sys.path.insert(0, ROOT)
from dabtools.dab.devices import DEVICES                          # noqa: E402
V = json.load(open(os.path.join(ROOT, "04_Design_Calculations", "design_values.json")))
Vdc, Isw = 800.0, V["nominal"]["Ipk1"]
Coss_tr = DEVICES["C3M0032120K"]["Coss_tr"]
t = np.linspace(0, 120, 1201)  # ns
# hard turn-on: current rises first (0-20 ns), then voltage falls (20-50 ns): overlap -> loss
i_h = np.clip(t / 20, 0, 1) * Isw
v_h = Vdc * (1 - np.clip((t - 20) / 30, 0, 1))
p_h = v_h * i_h
# ZVS: inductor current discharges the two Coss first (dead time), the switch turns on at v = 0
t_tr = 2 * Coss_tr * Vdc / Isw * 1e9                              # linear estimate, ns
v_z = Vdc * (1 - np.clip(t / t_tr, 0, 1))
i_z = np.where(t < t_tr, 0.0, Isw)                               # channel current only after v reached 0
p_z = v_z * i_z
fig, ax = plt.subplots(1, 2, figsize=(9, 3.4), sharey=False)
for a, (title, v, i, p) in zip(ax, (("hard turn-on: v and i overlap", v_h, i_h, p_h),
                                     ("ZVS turn-on: Coss discharged by i_L in the dead time", v_z, i_z, p_z))):
    a.plot(t, v / Vdc, label="v_ds / 800 V"); a.plot(t, i / Isw, label="i_ch / %.1f A" % Isw)
    a.fill_between(t, 0, p / (Vdc * Isw), alpha=0.3, color="C3", label="p = v i (normalised)")
    a.set_title(title, fontsize=9); a.set_xlabel("t (ns)"); a.grid(alpha=0.3); a.legend(fontsize=7, loc="center right")
ax[1].annotate("t_tr ~ 2 Coss,tr V / I = %.0f ns" % t_tr, xy=(t_tr, 0.02), xytext=(t_tr + 10, 0.4), arrowprops=dict(arrowstyle="->"), fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch02_hard_vs_soft.png"), dpi=130); plt.close(fig)
print("ch02 figure written, t_tr = %.1f ns" % t_tr)
