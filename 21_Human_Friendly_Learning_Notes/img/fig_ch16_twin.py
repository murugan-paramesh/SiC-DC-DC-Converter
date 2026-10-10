#!/usr/bin/env python3
"""Figures for chapter 16 (digital twin and estimation). Deterministic (data read from result files).
Outputs:
  ch16_twin_layers.png   - block diagram of the four twin layers and the firmware / host split
                           (content: Advanced_Research_2026/Digital_Twin/README.md and interface.md)
  ch16_crlb_sensors.png  - Cramer-Rao relative standard deviation after 1000 periods per parameter and
                           sensor set (data: Digital_Twin/results/observability.json); missing bar = not identifiable
  ch16_supervisor.png    - rms-current change of the adaptive supervisor vs the fixed EPS schedule at the
                           27 operating points (data: Digital_Twin/results/supervisory_study.json)
All underlying data are SIMULATED.
"""
import os, json
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
DT = os.path.abspath(os.path.join(HERE, "..", "..", "Advanced_Research_2026", "Digital_Twin", "results"))
INK, INK2, GRID, BOX = "#0b0b0b", "#52514e", "#d9d8d3", "#f1f0ec"
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                     "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False})

# ---------------------------------------------------------------- 1. layer diagram
fig, ax = plt.subplots(figsize=(8.6, 4.6)); ax.set_xlim(0, 10); ax.set_ylim(0, 6); ax.axis("off")
def box(x, y, w, h, title, body, edge):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05", fc=BOX, ec=edge, lw=1.6))
    ax.text(x + 0.12, y + h - 0.22, title, fontsize=8.5, weight="bold", color=INK, va="top")
    ax.text(x + 0.12, y + h - 0.55, body, fontsize=7.5, color=INK2, va="top")
box(0.2, 3.3, 3.0, 2.4, "Converter (here: switched plant)", "sim_switched.DABPlant\ntrue L, Coss, R_s hidden\n\nC2000 firmware, 100 kHz ISR:\nv1, v2, i2_avg, i1_avg, i_pk,\nPWM registers phi, D1, D2,\nNTC; t_tr only if the\nPROPOSED sensor exists", INK2)
box(0.2, 0.3, 3.0, 2.5, "Safety layer (unchanged)", "limiter + check_protection\ncomparator trips, interlock\n\nadvisory ignored unless\ntwin status = TRUSTED\n(sigma_L/L <= 5 %, frame\n< 20 ms old, CRC ok)", C2)
box(4.0, 4.55, 5.8, 1.25, "L1 electrical (1 kHz)", "I2_avg = g(applied PWM pattern, V1, V2) x (1/L);  RLS with forgetting 0.995 and\nexcitation gate |g| >= 2.5e-4 A H;  EKF on [v2, i_load, 1/L];  grid Bayes (reference)", C1)
box(4.0, 3.15, 5.8, 1.2, "L2 thermal (1 kHz)", "2-node Foster network per bridge, Kalman observer of Tj from the case NTC\nand the loss estimate (capacitances ESTIMATED)", C1)
box(4.0, 1.75, 5.8, 1.2, "L3 health (slow)", "Rds_on / Coss drift as slowly varying parameters; Coss needs the\nproposed transition-time sensor (observability.py)", C1)
box(4.0, 0.3, 5.8, 1.25, "L4 supervisory", "choose (D1, D2) from 16 candidates: min model rms current s.t. 1 A ZVS margin,\n32 A peak; fallback to fixed EPS schedule when the estimate is not trusted", C1)
ax.annotate("", xy=(4.0, 5.1), xytext=(3.2, 5.1), arrowprops=dict(arrowstyle="->", color=INK, lw=1.3))
ax.text(3.25, 5.25, "telemetry\nCRC-16, 1 kHz", fontsize=7, color=INK2)
ax.annotate("", xy=(3.2, 1.0), xytext=(4.0, 0.9), arrowprops=dict(arrowstyle="->", color=INK, lw=1.3))
ax.text(3.27, 1.15, "advisory\nD1, D2, L_est", fontsize=7, color=INK2)
ax.annotate("", xy=(1.7, 3.3), xytext=(1.7, 2.85), arrowprops=dict(arrowstyle="->", color=INK, lw=1.3))
ax.text(5.0, 5.95, "host twin (Python) - every number in this module is SIMULATED", fontsize=8, color=INK2)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch16_twin_layers.png"), dpi=130); plt.close(fig)

# ---------------------------------------------------------------- 2. CRLB per sensor set
O = json.load(open(os.path.join(DT, "observability.json")))
sets = list(O["sets"].keys()); params = ["L", "Coss_er1", "Coss_er2", "R_s"]
cols = {"L": C1, "Coss_er1": C2, "Coss_er2": C3, "R_s": "#6250d6"}
fig, ax = plt.subplots(figsize=(8.4, 3.9))
w = 0.2
for j, p in enumerate(params):
    for i, s in enumerate(sets):
        v = O["sets"][s]["crlb_rel_std_after_1000_periods"][p]
        x = i + (j - 1.5) * w
        if v > 0:
            ax.bar(x, 100 * v, width=w * 0.92, color=cols[p], label=p if i == len(sets) - 1 else None)
        else:
            ax.text(x, 1.2e-2, "x", ha="center", va="bottom", fontsize=9, color=INK2)
ax.set_yscale("log"); ax.set_ylim(1e-2, 30)
ax.set_xticks(range(len(sets))); ax.set_xticklabels([s.replace("board: ", "board:\n").replace("+ proposed ", "+ proposed\n") for s in sets], fontsize=7.5)
ax.set_ylabel("Cramer-Rao rel. std after 1000 periods (%)"); ax.grid(axis="y", color=GRID, lw=0.6)
ax.legend(fontsize=8, frameon=False, ncol=4, loc="upper right")
ax.set_title("Fisher-information rank per sensor set (x = not identifiable): ranks " +
             ", ".join(str(O["sets"][s]["rank"]) for s in sets) + "  (observability.json, SIMULATED)", fontsize=8.5, color=INK)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch16_crlb_sensors.png"), dpi=130); plt.close(fig)

# ---------------------------------------------------------------- 3. supervisor per point
S = json.load(open(os.path.join(DT, "supervisory_study.json")))
rows = S["rows"]
fig, ax = plt.subplots(figsize=(8.6, 3.6))
for pf, col in ((10.0, C1), (30.0, C2), (100.0, C3)):
    idx = [k for k, r in enumerate(rows) if r["P_pct"] == pf]
    d = [100 * (rows[k]["adaptive"]["Irms"] / rows[k]["fixed"]["Irms"] - 1) for k in idx]
    ax.bar(idx, d, color=col, width=0.8, label=f"{pf:.0f} % load")
ax.axhline(0, color=INK2, lw=0.8)
ax.set_xticks(range(len(rows)))
ax.set_xticklabels([f"{r['V1']:.0f}/{r['V2']:.0f}" for r in rows], rotation=90, fontsize=6.5)
ax.set_ylabel("rms current change (%)\nadaptive vs fixed EPS"); ax.grid(axis="y", color=GRID, lw=0.6)
sm = S["summary"]
ax.set_title("Supervisor on the switched plant, true L = 0.8 L_nom: mean %.1f %%, hard-switched points %d -> %d of 27 (SIMULATED)"
             % (sm["rms_current_change_pct"]["mean"], sm["hard_switched_edges"]["points_with_hard_switching_fixed"],
                sm["hard_switched_edges"]["points_with_hard_switching_adaptive"]), fontsize=8.5, color=INK)
ax.legend(fontsize=8, frameon=False, ncol=3)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch16_supervisor.png"), dpi=130); plt.close(fig)
print("written: ch16_twin_layers.png, ch16_crlb_sensors.png, ch16_supervisor.png")
