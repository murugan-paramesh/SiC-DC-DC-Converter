#!/usr/bin/env python3
"""
Deterministic figures for chapters 17 and 18 of the learning notes (matplotlib only, no random
numbers).  Every plotted number is READ from a results file of Advanced_Research_2026 at run time,
so the figures cannot drift from the module outputs.  Run from any directory:
    python3 <path>/make_figs_ch17_18.py
Writes next to this script:
    ch17_wcet_budget.png        estimated ISR time per controller / inference path vs the 10 us budget
    ch17_surrogate_accuracy.png worst-output RMSE of the surrogate models (analytical model wins)
    ch18_te2_variants.png       fault-tree top event TE2 frequency: rev A vs DESAT driver vs CT check
    ch18_crosstalk_margin.png   quasi-static crosstalk margin at the worst ZVS corner per gate-drive option
Sources:
    Advanced_Research_2026/Adaptive_MPC/results/c2000_feasibility.json
    Advanced_Research_2026/Embedded_AI/results/embedded_report.json (wcet section) - values also in the README table
    Advanced_Research_2026/Physics_Informed_Models/results/metrics.json
    Advanced_Research_2026/Reliability_Engineering/results/fta_cutsets.json
    Advanced_Research_2026/Active_Gate_Drive/results/gate_drive_results.json
"""
import os
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
AR = os.path.join(REPO, "Advanced_Research_2026")
BLUE, ORANGE, GREEN, GREY, RED = "#2a78d6", "#eb6834", "#1baf7a", "#8a8f98", "#c0392b"
plt.rcParams.update({"font.size": 9, "font.family": "DejaVu Sans"})


def load(*parts):
    with open(os.path.join(AR, *parts), encoding="utf-8") as f:
        return json.load(f)


def clean(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color="#e3e5e8", lw=0.6)
    ax.set_axisbelow(True)


def fig_wcet():
    c2k = load("Adaptive_MPC", "results", "c2000_feasibility.json")["controllers"]
    rows = [(name, v["wcet_us"]) for name, v in c2k.items()]
    # Embedded_AI inference paths (README table 3.1 / embedded_report.json "wcet")
    try:
        w = load("Embedded_AI", "results", "embedded_report.json")["wcet"]
        extra = []
        for key, label in (("lut_q15", "Q15 explicit-MPC LUT (Embedded_AI)"),
                           ("mlp_q15", "MLP 3-16-16-3 Q15 (Embedded_AI)")):
            if key in w and isinstance(w[key], dict) and "us" in w[key]:
                extra.append((label, w[key]["us"]))
        rows += extra
    except (KeyError, OSError):
        pass
    rows.sort(key=lambda r: r[1])
    names = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    colors = [GREEN if v <= 10.0 else ORANGE for v in vals]
    fig, ax = plt.subplots(figsize=(7.2, 0.42 * len(rows) + 1.2))
    ax.barh(range(len(rows)), vals, color=colors, height=0.6)
    ax.axvline(10.0, color=RED, lw=1.2, ls="--")
    ax.text(10.4, len(rows) - 0.6, "10 us ISR budget (100 kHz)", color=RED, fontsize=8, va="top")
    for i, v in enumerate(vals):
        ax.text(v * 1.08, i, f"{v:.1f} us  {'fits' if v <= 10 else 'does not fit'}", va="center", fontsize=7.5)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xscale("log")
    ax.set_xlim(0.3, 400)
    ax.set_xlabel("estimated WCET per update on a 200 MHz C28x (us, log scale) - L1 instruction-count estimate")
    ax.set_title("Which controller fits the 10 us control ISR? (estimate, no toolchain, no hardware)", fontsize=9.5)
    clean(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "ch17_wcet_budget.png"), dpi=150)
    plt.close(fig)


def fig_surrogates():
    m = load("Physics_Informed_Models", "results", "metrics.json")["ranking_worst_output_rmse_pct"]
    labels = {"A2_analytic_tps_piecewise": "A2 analytical TPS (no data)", "MLP_plain": "plain MLP",
              "HYB_sps_plus_residual": "SPS + NN residual", "PINN_physics_loss": "physics-informed MLP",
              "LUT_multilinear": "5-D LUT", "GP_rbf": "Gaussian process", "P3_polynomial": "cubic polynomial",
              "A1_sps_closed_form": "A1 SPS closed form"}
    names = [labels.get(k, k) for k, _ in m][::-1]
    vals = [v for _, v in m][::-1]
    colors = [BLUE if n.startswith("A2") else (GREY if n.startswith("A1") else ORANGE) for n in names]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.barh(range(len(vals)), vals, color=colors, height=0.6)
    ax.axvline(1.0, color=GREY, lw=1.0, ls=":")
    ax.text(1.05, -0.6, "1 % of range", color=GREY, fontsize=7.5)
    for i, v in enumerate(vals):
        ax.text(v * 1.1, i, f"{v:.2f} %", va="center", fontsize=7.5)
    ax.set_yticks(range(len(vals)))
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xscale("log")
    ax.set_xlim(0.05, 120)
    ax.set_xlabel("worst-output RMSE on 2000 random test points (% of output range, log scale), 6912 training points")
    ax.set_title("Surrogates of the DAB steady-state map: the analytical model wins (simulation only)", fontsize=9.5)
    clean(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "ch17_surrogate_accuracy.png"), dpi=150)
    plt.close(fig)


def fig_te2():
    d = load("Reliability_Engineering", "results", "fta_cutsets.json")
    rows = [("rev A (UCC21520, no DESAT)", d["TE2_uncontrolled_energy_overcurrent"]["frequency_per_year"]),
            ("rev A + CT plausibility check", d["TE2_with_CT_plausibility"]["frequency_per_year"]),
            ("DESAT driver (UCC21710 class, 99 % coverage assumed)", d["TE2_with_DESAT_driver"]["frequency_per_year"])]
    fig, ax = plt.subplots(figsize=(7.2, 2.4))
    vals = [r[1] for r in rows]
    ax.barh(range(3), vals, color=[ORANGE, ORANGE, GREEN], height=0.55)
    for i, v in enumerate(vals):
        ax.text(v * 1.15, i, f"{v:.2e} /year", va="center", fontsize=8)
    ax.set_yticks(range(3))
    ax.set_yticklabels([r[0] for r in rows], fontsize=8)
    ax.set_xscale("log")
    ax.set_xlim(1e-7, 1e-2)
    ax.set_xlabel("TE2 frequency (/year, log scale) - ASSUMED class failure rates, relative comparison only")
    ax.set_title("Fault tree TE2 (shoot-through not interrupted in time): the missing DESAT dominates", fontsize=9.5)
    clean(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "ch18_te2_variants.png"), dpi=150)
    plt.close(fig)


def fig_crosstalk():
    g = load("Active_Gate_Drive", "results", "gate_drive_results.json")["options"]
    devs = [("C3M0032120K", "HV device, 800 V"), ("C3M0016120K", "LV device, 400 V")]
    opts = [k for k in g["C3M0032120K"].keys() if not k.startswith("E ")]
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.2), sharey=True)
    for ax, (dev, title) in zip(axes, devs):
        vals = [g[dev][o].get("crosstalk_margin_worst_V", float("nan")) for o in opts]
        cols = [GREEN if v > 0 else RED for v in vals]
        ax.barh(range(len(opts)), vals, color=cols, height=0.55)
        ax.axvline(0, color="black", lw=0.8)
        for i, v in enumerate(vals):
            ax.text(v + (0.15 if v >= 0 else -0.15), i, f"{v:+.1f} V", va="center",
                    ha="left" if v >= 0 else "right", fontsize=7.5)
        ax.set_title(title, fontsize=9)
        ax.set_xlim(-7.5, 4.5)
        ax.set_xlabel("margin to Vth,min(150 C) at worst ZVS corner (V)")
        clean(ax)
    axes[0].set_yticks(range(len(opts)))
    axes[0].set_yticklabels(opts, fontsize=7.5)
    fig.suptitle("Crosstalk (false turn-on) margin per gate-drive option - L1 analytic model, below 0 = re-conduction",
                 fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "ch18_crosstalk_margin.png"), dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    fig_wcet()
    fig_surrogates()
    fig_te2()
    fig_crosstalk()
    print("wrote ch17_wcet_budget.png, ch17_surrogate_accuracy.png, ch18_te2_variants.png, ch18_crosstalk_margin.png")
