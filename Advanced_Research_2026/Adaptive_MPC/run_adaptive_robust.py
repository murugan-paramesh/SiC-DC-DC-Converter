#!/usr/bin/env python3
"""
Adaptive and robust MPC study on the switched plant.
  1. RLS convergence of the inductance estimate when the plant L is 20 % above / below nominal (load step 10->100 %
     at 650/450 V) and when it drifts 1.0 -> 0.85 L_nom during operation (unrealistically fast drift, 10 ms, to
     show tracking - a real thermal drift takes minutes).
  2. Constraint satisfaction: CCS-MPC with the nominal model, Adaptive MPC and Robust MPC on plants with
     L = 0.8, 1.0, 1.2 L_nom at the 650/450 V corner (highest peak currents of the envelope), load step 10 -> 100 %.
Outputs results/adaptive_*.{csv,json,png}.  Run time ~2-3 min.
"""
import os, sys, json, math, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from dab_mpc_lib import *      # noqa
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import pandas as pd

T0 = time.time()
OUT = os.path.join(HERE, "results"); os.makedirs(OUT, exist_ok=True)
V1C, V2C = 650.0, 450.0
sc = make_scenario("load_step_up", v1=V1C, v2_ref=V2C)

# ---------------------------------------------------------------- 1. RLS convergence
conv = {}
fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
for frac, col in ((1.2, "#1f77b4"), (0.8, "#d62728")):
    ctl = AdaptiveMPC()
    res = run_scenario(ctl, sc, L_plant=frac * L_NOM)
    Lh = np.array(ctl.L_hist) * 1e6
    t = res["t"] * 1e3
    ax[0].plot(t, Lh, color=col, label=f"L_hat, plant L = {frac:.1f} L_nom")
    ax[0].axhline(frac * L_NOM * 1e6, color=col, ls=":", lw=0.8)
    err = np.abs(Lh / (frac * L_NOM * 1e6) - 1)
    k2 = np.argmax(err < 0.02) if (err < 0.02).any() else None
    conv[f"L={frac:.1f}"] = dict(L_true_uH=frac * L_NOM * 1e6, L_hat_final_uH=float(Lh[-1]), final_error_pct=float(100 * err[-1]),
                                 t_to_2pct_ms=float(t[k2]) if k2 is not None else None,
                                 metrics=metrics(res, sc))
    print(f"RLS plant L = {frac:.1f} L_nom: L_hat final {Lh[-1]:.2f} uH (err {100*err[-1]:.2f} %), 2 % reached at {conv[f'L={frac:.1f}']['t_to_2pct_ms']} ms", flush=True)
ax[0].axvline(sc["t_event"] * 1e3, color="k", lw=0.6, ls="--"); ax[0].set_xlabel("t (ms)"); ax[0].set_ylabel("L estimate (uH)")
ax[0].set_title("RLS on 1/L, 20 % initial error (load step at 8 ms)"); ax[0].legend(fontsize=7); ax[0].grid(alpha=0.3)
# drift: 1.0 -> 0.85 L_nom between 8 and 18 ms, constant 60 % load
sc_d = make_scenario("load_step_up", v1=V1C, v2_ref=V2C, post=0.016)
R60 = V2C ** 2 / (0.6 * P_RATED)
sc_d["load"] = lambda v2, t: v2 / R60
L_drift = lambda t: L_NOM * (1.0 - 0.15 * min(1.0, max(0.0, (t - 0.008) / 0.010)))
ctl = AdaptiveMPC()
res = run_scenario(ctl, sc_d, L_drift=L_drift)
Lh = np.array(ctl.L_hist) * 1e6; t = res["t"] * 1e3
Lt = np.array([L_drift(x) for x in res["t"]]) * 1e6
ax[1].plot(t, Lt, "k--", label="true L (SYNTHETIC drift 1.0 -> 0.85 L_nom in 10 ms)"); ax[1].plot(t, Lh, color="#9467bd", label="L_hat")
ax[1].set_xlabel("t (ms)"); ax[1].set_ylabel("L (uH)"); ax[1].legend(fontsize=7); ax[1].grid(alpha=0.3); ax[1].set_title("Tracking of a drifting inductance (60 % load)")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "adaptive_rls_convergence.png"), dpi=130); plt.close(fig)
lag_err = np.abs(Lh - Lt) / Lt
conv["drift"] = dict(max_tracking_error_pct=float(100 * lag_err[t > 9].max()), final_error_pct=float(100 * lag_err[-1]),
                     metrics=metrics(res, sc_d), note="forgetting factor 0.995 -> ~200 periods memory")
print(f"drift tracking: max error {conv['drift']['max_tracking_error_pct']:.2f} %, final {conv['drift']['final_error_pct']:.2f} %", flush=True)

# ---------------------------------------------------------------- 2. constraint satisfaction vs plant L
rows = []
fig, axs = plt.subplots(1, 3, figsize=(14, 3.8), sharey=True)
for j, frac in enumerate((0.8, 1.0, 1.2)):
    for ctl, col in ((CCSMPC(), "#1f77b4"), (AdaptiveMPC(), "#9467bd"), (RobustMPC(), "#d62728"), (PIBaseline(), "#444444")):
        res = run_scenario(ctl, sc, L_plant=frac * L_NOM)
        mt = metrics(res, sc); mt.update(controller=ctl.name, L_plant_frac=frac)
        rows.append(mt)
        tt = (res["t"] - sc["t_event"]) * 1e3
        axs[j].plot(tt, res["ipk"], color=col, lw=1, label=ctl.name)
        print(f"L = {frac:.1f} L_nom  {ctl.name:13s} peak dev {mt['peak_dev_pct']:.3f} %  Ipk {mt['i_peak_A']:5.2f} A  violations(24 A) {mt['violations']}  hw(32 A) {mt['violations_hw']}", flush=True)
    axs[j].axhline(I_LIM_PK, color="r", ls=":", lw=0.8); axs[j].set_title(f"plant L = {frac:.1f} L_nom"); axs[j].set_xlabel("t - t_event (ms)")
    axs[j].grid(alpha=0.3); axs[j].set_xlim(-0.5, 4)
axs[0].set_ylabel("|i_L| peak per period (A)"); axs[0].legend(fontsize=7)
fig.suptitle(f"Peak current at the 650/450 V corner, load step 10 -> 100 % (24 A controller limit)"); fig.tight_layout()
fig.savefig(os.path.join(OUT, "adaptive_robust_constraints.png"), dpi=130); plt.close(fig)
dfr = pd.DataFrame(rows); dfr.to_csv(os.path.join(OUT, "adaptive_robust_metrics.csv"), index=False)
json.dump(dict(convergence=conv, constraint_study=rows, corner=dict(V1=V1C, V2=V2C)), open(os.path.join(OUT, "adaptive_summary.json"), "w"), indent=1, default=float)
write_provenance(HERE, "run_adaptive_robust.py", T0, [DESIGN_FILE, CONTROL_FILE, os.path.join(HERE, "dab_mpc_lib.py")],
                 extra=dict(outputs=sorted(f for f in os.listdir(OUT) if f.startswith("adaptive_"))))
print(f"done in {time.time()-T0:.0f} s")
