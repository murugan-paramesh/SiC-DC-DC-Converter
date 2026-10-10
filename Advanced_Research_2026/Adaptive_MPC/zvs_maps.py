#!/usr/bin/env python3
"""
Wide-range ZVS maps of the 6.6 kW DAB over V1 x V2 x P (forward and reverse) for SPS and EPS voltage matching,
using dabtools DABPoint.zvs_margin with I_min from zvs_current_min (Coss_er, C_par as in 04_Design_Calculations).
Temperature: the device table has no temperature dependence of Coss_er (datasheet Coss(T) variation for SiC is a
few %), so the Tj = 25 C and Tj = 150 C maps are identical in this model; the tolerance sweep L +/-15 % and
Coss_er +/-20 % is what actually moves the ZVS boundary.  Hard-switching (infeasible) regions are marked
explicitly.  Also: adaptive dead-time table t_d(I_edge) from dead_time_required with Qoss(V) = Qoss_800V * V / 800.
Outputs results/zvs_*.{csv,json,png}.  Run time ~1-2 min.
"""
import os, sys, json, math, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from dab_mpc_lib import *      # noqa
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import pandas as pd

T0 = time.time()
OUT = os.path.join(HERE, "results"); os.makedirs(OUT, exist_ok=True)
V1_AX = np.arange(650, 851, 25.0); V2_AX = np.arange(300, 451, 25.0)
P_FRAC = np.concatenate([-np.arange(1.0, 0.09, -0.1), np.arange(0.1, 1.01, 0.1)])      # -100 .. -10, +10 .. +100 %
TJ = (25.0, 150.0)
CASES = dict(nominal=dict(L=1.0, C1=1.0, C2=1.0), L_minus15=dict(L=0.85, C1=1.0, C2=1.0), L_plus15=dict(L=1.15, C1=1.0, C2=1.0),
             Coss_plus20=dict(L=1.0, C1=1.2, C2=1.2), Coss_minus20=dict(L=1.0, C1=0.8, C2=0.8), worst=dict(L=1.15, C1=1.2, C2=1.2))


def point(V1, V2, P, mod, L, c1, c2):
    D1, D2 = eps_matching(V1, V2) if mod == "EPS" else (1.0, 1.0)
    phi, feas = phi_for_power_pwl(V1, V2, N_RATIO, L, FS, P, D1, D2)
    phi = float(phi[0])
    if not feas[0] or abs(phi) > PHI_MAX:
        return dict(phi=phi, zvs1=float("nan"), zvs2=float("nan"), Irms=float("nan"), Ipk=float("nan"), feasible=False)
    pt = M.DABPoint(V1, V2, N_RATIO, L, FS, phi, D1, D2, N=2000)
    Imin1, Imin2 = zvs_i_min(V1, V2, L, N_RATIO, DEV1["Coss_er"] * c1, DEV2["Coss_er"] * c2)
    return dict(phi=phi, zvs1=pt.zvs_margin(1, Imin1), zvs2=pt.zvs_margin(2, Imin2), Irms=pt.I_rms1, Ipk=pt.I_peak1, feasible=True,
                Imin1=Imin1, Imin2=Imin2, D1=D1, D2=D2)


rows = []
for case, f in CASES.items():
    L = f["L"] * L_NOM
    for mod in ("SPS", "EPS"):
        for V1 in V1_AX:
            for V2 in V2_AX:
                for pf in P_FRAC:
                    r = point(V1, V2, pf * P_RATED, mod, L, f["C1"], f["C2"])
                    rows.append(dict(case=case, modulation=mod, V1=V1, V2=V2, P_frac=pf, **r))
    print(f"case {case} done ({time.time()-T0:.0f} s)", flush=True)
df = pd.DataFrame(rows)
df["zvs_min"] = df[["zvs1", "zvs2"]].min(axis=1)
df["hard_switching"] = (df.zvs_min < 0) | (~df.feasible)
df.to_csv(os.path.join(OUT, "zvs_maps.csv"), index=False)

# ---------------------------------------------------------------- summary of infeasible regions
summ = {}
for (case, mod), g in df.groupby(["case", "modulation"]):
    fwd = g[g.P_frac > 0]; rev = g[g.P_frac < 0]
    def desc(h):
        hs = h[h.hard_switching]
        if len(hs) == 0:
            return dict(fraction=0.0, note="full ZVS")
        # minimum load for ZVS per (V1, V2): the largest |P| fraction that still hard-switches
        worst = hs.groupby(["V1", "V2"]).P_frac.apply(lambda x: float(np.max(np.abs(x))))
        return dict(fraction=float(len(hs) / len(h)), max_hard_switching_load_pct=float(100 * worst.max()),
                    worst_corner=f"{worst.idxmax()[0]:.0f}/{worst.idxmax()[1]:.0f} V",
                    corners_full_zvs=int((h.groupby(['V1', 'V2']).hard_switching.sum() == 0).sum()), corners_total=int(h.groupby(['V1', 'V2']).ngroups),
                    light_load_10pct_hard_fraction=float(h[np.isclose(np.abs(h.P_frac), 0.1)].hard_switching.mean()))
    summ[f"{case}/{mod}"] = dict(forward=desc(fwd), reverse=desc(rev),
                                  hv_bridge_hard_fraction=float((g.zvs1 < 0).mean()), lv_bridge_hard_fraction=float((g.zvs2 < 0).mean()),
                                  Irms_mean_A=float(g.Irms.mean()))
json.dump(dict(summary=summ, Tj_note="Tj = 25 C and 150 C maps coincide: Coss_er has no temperature dependence in the device table (weak in reality, "
               "a few % for SiC); Rds_on(Tj) does not enter the lossless ZVS criterion. Swept instead: L +/-15 %, Coss_er +/-20 %.",
               axes=dict(V1=V1_AX.tolist(), V2=V2_AX.tolist(), P_frac=P_FRAC.tolist()), cases=CASES),
          open(os.path.join(OUT, "zvs_summary.json"), "w"), indent=1)
for k, v in summ.items():
    print(f"{k:22s} fwd hard {100*v['forward']['fraction']:5.1f} %  rev hard {100*v['reverse']['fraction']:5.1f} %  "
          f"fwd worst corner {v['forward'].get('worst_corner','-')} up to {v['forward'].get('max_hard_switching_load_pct',0):.0f} % load")

# ---------------------------------------------------------------- figures: ZVS maps (V1 x V2) at several loads, fwd/rev, SPS/EPS
def map_fig(case, fname, title):
    g = df[df.case == case]
    loads = (0.1, 0.3, 0.5, 1.0)
    fig, axs = plt.subplots(4, len(loads), figsize=(3.2 * len(loads), 11), sharex=True, sharey=True)
    for i, (mod, sgn) in enumerate((("SPS", 1), ("SPS", -1), ("EPS", 1), ("EPS", -1))):
        for j, ld in enumerate(loads):
            h = g[(g.modulation == mod) & np.isclose(g.P_frac, sgn * ld)]
            Z = h.pivot(index="V2", columns="V1", values="zvs_min").values
            H = h.pivot(index="V2", columns="V1", values="hard_switching").values.astype(float)
            ax = axs[i, j]
            im = ax.imshow(Z, origin="lower", aspect="auto", extent=[V1_AX[0] - 12.5, V1_AX[-1] + 12.5, V2_AX[0] - 12.5, V2_AX[-1] + 12.5],
                           cmap="RdYlGn", vmin=-6, vmax=6)
            # hatch hard-switching cells
            for a, V2 in enumerate(V2_AX):
                for b, V1 in enumerate(V1_AX):
                    if H[a, b] > 0.5:
                        ax.add_patch(plt.Rectangle((V1 - 12.5, V2 - 12.5), 25, 25, fill=False, hatch="xxx", edgecolor="k", lw=0))
            ax.set_title(f"{mod} {'fwd' if sgn > 0 else 'rev'} {int(ld*100)} %", fontsize=9)
            if i == 3: ax.set_xlabel("V1 (V)")
            if j == 0: ax.set_ylabel("V2 (V)")
    fig.colorbar(im, ax=axs, shrink=0.5, label="min ZVS margin of both bridges (A, HV side); hatched = hard switching")
    fig.suptitle(title); fig.savefig(os.path.join(OUT, fname), dpi=120); plt.close(fig)


map_fig("nominal", "zvs_maps_nominal.png", "ZVS maps, nominal L and Coss_er (Tj 25 C = 150 C in this model, see README)")
map_fig("worst", "zvs_maps_worst_tolerance.png", "ZVS maps, worst tolerance (L +15 %, Coss_er +20 %)")

# minimum ZVS load (forward) over the V1 x V2 plane for SPS vs EPS, nominal and worst
fig, axs = plt.subplots(2, 2, figsize=(9, 7), sharex=True, sharey=True)
for i, case in enumerate(("nominal", "worst")):
    for j, mod in enumerate(("SPS", "EPS")):
        g = df[(df.case == case) & (df.modulation == mod) & (df.P_frac > 0)]
        def min_zvs_load(h):
            hs = h[h.hard_switching]
            return 0.0 if len(hs) == 0 else float(np.max(hs.P_frac) + 0.1)
        Z = g.groupby(["V2", "V1"]).apply(min_zvs_load).unstack().values * 100
        ax = axs[i, j]
        im = ax.imshow(Z, origin="lower", aspect="auto", extent=[V1_AX[0] - 12.5, V1_AX[-1] + 12.5, V2_AX[0] - 12.5, V2_AX[-1] + 12.5], cmap="magma_r", vmin=0, vmax=110)
        for (a, V2) in enumerate(V2_AX):
            for (b, V1) in enumerate(V1_AX):
                ax.text(V1, V2, f"{Z[a, b]:.0f}", ha="center", va="center", fontsize=7, color="w" if Z[a, b] > 50 else "k")
        ax.set_title(f"{case}, {mod}: minimum load for full ZVS (%)", fontsize=9)
        if i == 1: ax.set_xlabel("V1 (V)")
        if j == 0: ax.set_ylabel("V2 (V)")
fig.colorbar(im, ax=axs, shrink=0.6, label="minimum forward load for ZVS of both bridges (%); 110 = never")
fig.suptitle("Light-load ZVS boundary (forward power)"); fig.savefig(os.path.join(OUT, "zvs_min_load.png"), dpi=130); plt.close(fig)

# ---------------------------------------------------------------- adaptive dead-time table
I_edge = np.concatenate([np.arange(0.5, 5, 0.5), np.arange(5, 31, 1.0)])
dt_rows = []
for dev, name, Vs in ((DEV1, "HV C3M0032120K", (650, 800, 850)), (DEV2, "LV C3M0016120K", (300, 400, 450))):
    for V in Vs:
        Qoss = dev["Qoss_800V"] * V / 800.0
        for I in I_edge:
            td = M.dead_time_required(Qoss, I, t_min=50e-9)
            dt_rows.append(dict(device=name, V=V, I_edge_A=I, Qoss_nC=Qoss * 1e9, t_d_ns=td * 1e9, clipped_500ns=td > 500e-9,
                                t_d_table_ns=min(500.0, td * 1e9)))
dft = pd.DataFrame(dt_rows); dft.to_csv(os.path.join(OUT, "zvs_dead_time_table.csv"), index=False)
fig, ax = plt.subplots(figsize=(7, 4))
for (dev, V), g in dft.groupby(["device", "V"]):
    ax.plot(g.I_edge_A, g.t_d_ns, label=f"{dev} {V} V")
ax.axhline(150, color="k", ls="--", lw=0.8, label="fixed design dead time 150 ns"); ax.axhline(500, color="r", ls=":", lw=0.8, label="table clip 500 ns")
ax.set_xlabel("edge current |I_edge| (A, own side)"); ax.set_ylabel("required dead time (ns)"); ax.set_yscale("log"); ax.set_ylim(30, 3000)
ax.legend(fontsize=7); ax.grid(alpha=0.3, which="both"); ax.set_title("Adaptive dead time t_d = max(50 ns, 2 Qoss(V) / I_edge)")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "zvs_dead_time_table.png"), dpi=130); plt.close(fig)
I150 = {name: float(2 * DEV["Qoss_800V"] * V / 800 / 150e-9) for DEV, name, V in ((DEV1, "HV_800V", 800), (DEV2, "LV_400V", 400))}
json.dump(dict(I_edge_for_150ns_A=I150, note="below these edge currents the fixed 150 ns dead time is too short for a complete transition "
               "(partial ZVS); the table extends it up to 500 ns, beyond which the point is treated as hard switching"),
          open(os.path.join(OUT, "zvs_dead_time_summary.json"), "w"), indent=1)
print("edge current for 150 ns:", I150)
write_provenance(HERE, "zvs_maps.py", T0, [DESIGN_FILE, os.path.join(PROJ, "dabtools", "dab", "dab_model.py"), os.path.join(PROJ, "dabtools", "dab", "devices.py"),
                                           os.path.join(HERE, "dab_mpc_lib.py")],
                 extra=dict(outputs=sorted(f for f in os.listdir(OUT) if f.startswith("zvs_"))))
print(f"done in {time.time()-T0:.0f} s")
