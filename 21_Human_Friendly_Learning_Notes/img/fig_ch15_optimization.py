#!/usr/bin/env python3
"""Figures for chapter 15 (optimisation and uncertainty). Deterministic (fixed seed, data read from files).
Outputs:
  ch15_pareto_dominance.png - the three (loss, volume) Pareto points of 12_Optimization and the baseline,
                              with the region each point dominates (data: optimization_results.json)
  ch15_mc_vs_lhs.png        - 16 plain Monte-Carlo points vs 16 Latin-hypercube points in two inputs
                              (didactic; same LHS construction as Robust_Optimization/dab_eval.py lhs())
  ch15_sobol_total.png      - total Sobol indices (PCE) for four quantities of interest
                              (data: Uncertainty_Quantification/results/uq_summary.json)
"""
import os, json
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
INK, INK2, GRID = "#0b0b0b", "#52514e", "#d9d8d3"
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                     "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False})

# ---------------------------------------------------------------- 1. Pareto dominance
R = json.load(open(os.path.join(REPO, "SiC_6k6_Industrial_DAB", "12_Optimization", "optimization_results.json")))
front = sorted(R["pareto"], key=lambda r: r["vol"])
base = R["baseline"]
fig, ax = plt.subplots(figsize=(6.4, 4.2))
xmax, ymax = 300, 96
for r in front:
    ax.add_patch(plt.Rectangle((r["vol"], r["P_loss"]), xmax - r["vol"], ymax - r["P_loss"], color=C1, alpha=0.07, lw=0))
ax.plot([r["vol"] for r in front], [r["P_loss"] for r in front], "-o", color=C1, lw=2, ms=8, label="grid Pareto front (loss, volume)")
for r in front:
    ax.annotate(f"{r['fs']/1e3:.0f} kHz, {r['tcore'].split('/')[0]}\n{r['P_loss']:.0f} W, {r['vol']:.0f} cm3", (r["vol"], r["P_loss"]),
                textcoords="offset points", xytext=(8, -18), fontsize=8, color=INK)
ax.plot([base["vol"]], [base["P_loss"]], "s", color=C2, ms=9, label="baseline (100 kHz, E65 + E55)")
ax.annotate(f"baseline\n{base['P_loss']:.0f} W, {base['vol']:.0f} cm3\nZVS to {100*base['zvs_light']:.0f} % load",
            (base["vol"], base["P_loss"]), textcoords="offset points", xytext=(-80, 6), fontsize=8, color=INK)
ax.text(232, 94.5, "shaded: region dominated by a front point", fontsize=7.5, color=INK2)
ax.set_xlim(140, xmax); ax.set_ylim(78, ymax)
ax.set_xlabel("magnetics volume (cm3)"); ax.set_ylabel("total loss at 800/400 V, 6.6 kW (W)")
ax.grid(color=GRID, lw=0.6); ax.legend(loc="lower left", fontsize=8, frameon=False)
ax.set_title("12_Optimization: 8640 candidates, 1404 feasible, 3 non-dominated in (loss, volume)", fontsize=9, color=INK)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch15_pareto_dominance.png"), dpi=130); plt.close(fig)

# ---------------------------------------------------------------- 2. MC vs LHS
rng = np.random.default_rng(20261010)
N = 16
mc = rng.random((N, 2))
lhs = (np.arange(N)[:, None] + rng.random((N, 2))) / N
for j in range(2): lhs[:, j] = lhs[rng.permutation(N), j]
fig, axs = plt.subplots(1, 2, figsize=(7.6, 3.7), sharey=True)
for a, pts, title, col in ((axs[0], mc, "plain Monte Carlo, 16 points", C1), (axs[1], lhs, "Latin hypercube, 16 points", C2)):
    for k in range(1, N):
        a.axvline(k / N, color=GRID, lw=0.5); a.axhline(k / N, color=GRID, lw=0.5)
    a.plot(pts[:, 0], pts[:, 1], "o", color=col, ms=7, mec="white", mew=1.5)
    a.set_xlim(0, 1); a.set_ylim(0, 1); a.set_title(title, fontsize=9, color=INK)
    a.set_xlabel("input 1, e.g. kL mapped to [0, 1]")
    for s in ("top", "right"): a.spines[s].set_visible(True)
axs[0].set_ylabel("input 2, e.g. kCore mapped to [0, 1]")
fig.text(0.5, 0.005, "LHS: exactly one point in every column and every row of the 16 x 16 grid; MC leaves gaps and clusters",
         ha="center", fontsize=7.5, color=INK2)
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(os.path.join(HERE, "ch15_mc_vs_lhs.png"), dpi=130); plt.close(fig)

# ---------------------------------------------------------------- 3. Sobol total indices
U = json.load(open(os.path.join(REPO, "Advanced_Research_2026", "Uncertainty_Quantification", "results", "uq_summary.json")))
qois = [("eta_nom_pct", "efficiency 800/400 V"), ("eta_650_300_pct", "efficiency 650/300 V"),
        ("zvs1_nom_A", "ZVS margin HV, nominal"), ("Tj1_nom_C", "Tj HV bridge, nominal")]
inputs = ["kL", "kCoss", "kRds", "kCore", "Tamb"]
fig, axs = plt.subplots(1, 4, figsize=(10, 3.0), sharey=True)
for a, (q, lab) in zip(axs, qois):
    st = U["sobol_pce"][q]["ST"]; vals = [max(st[i], 0.0) for i in inputs]
    a.barh(range(len(inputs)), vals, color=C1, height=0.6)
    for k, v in enumerate(vals):
        a.text(min(v, 1.0) + 0.03, k, f"{v:.2f}", va="center", fontsize=8, color=INK)
    a.set_xlim(0, 1.25); a.set_xticks([0, 0.5, 1.0]); a.set_title(lab, fontsize=9, color=INK); a.set_xlabel("total Sobol index ST")
    a.grid(axis="x", color=GRID, lw=0.6)
axs[0].set_yticks(range(len(inputs))); axs[0].set_yticklabels(inputs); axs[0].invert_yaxis()
fig.suptitle("Which assumed uncertainty drives which result (PCE order 3, uq_summary.json; assumed input ranges)", fontsize=9, color=INK)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch15_sobol_total.png"), dpi=130); plt.close(fig)
print("written: ch15_pareto_dominance.png, ch15_mc_vs_lhs.png, ch15_sobol_total.png")
