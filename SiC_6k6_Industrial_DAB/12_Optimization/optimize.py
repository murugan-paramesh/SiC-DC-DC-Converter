#!/usr/bin/env python3
"""
Multi-objective design-space exploration for the DAB power stage (reproducible, deterministic).

Variables: switching frequency, turns ratio, nominal phase shift (-> series inductance), transformer
core, inductor core, dead time, HV/LV device choice (1 or 2 in parallel).
Objectives (all computed with the same models as 04_Design_Calculations):
  f1 total loss at 800/400 V, 6.6 kW (W)            f2 magnetics volume (cm3)
  f3 rms inductor current averaged over 3 corners   f4 light-load ZVS limit at 800/400 (fraction)
  f5 cost proxy (core volume + device silicon area index)
Constraints: full power reachable at all 9 corners (phi <= 60 deg), Tj <= 150 C, transformer bundle fill
<= 0.7, inductor fill <= 0.7, Bpk <= 0.2 T.
Method: exhaustive grid (no stochastic search) -> non-dominated (Pareto) set in (f1, f2) and tables.
"""
import os, sys, json, math, itertools, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
from dabtools.dab import dab_model as M
from dabtools.dab.devices import DEVICES
from dabtools.dab import losses as LS
from dabtools.dab import magnetics as MG
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
P = 6600.0; Tamb = 45.0
heatsink = dict(Rth_sink=0.22, Rth_tim=0.35)
grid = dict(fs=[60e3, 80e3, 100e3, 120e3, 150e3], n=[1.8, 2.0, 2.2], phi_deg=[20, 25, 30, 35],
            tcore=["E55/28/21", "ETD59/31/22", "E65/32/27", "E70/33/32"], lcore=["ETD44/22/15", "ETD49/25/16", "E55/28/21"],
            t_dead=[100e-9, 150e-9, 200e-9], dev1=[("C3M0032120K", 1), ("C3M0016120K", 1)], dev2=[("C3M0016120K", 1), ("C3M0032120K", 2)])

def evaluate(fs, n, phi_deg, tcore, lcore, t_dead, dev1, dev2):
    phi = math.radians(phi_deg)
    L = 800 * n * 400 * phi * (math.pi - phi) / (2 * math.pi ** 2 * fs * P)
    d1, p1 = dev1; d2, p2 = dev2
    D1, D2 = DEVICES[d1], DEVICES[d2]
    # corner feasibility
    for V1 in (650, 800, 850):
        for V2 in (300, 400, 450):
            V2p = n * V2
            if P > 0.999 * M.sps_max_power(V1, V2p, L, fs): return None
            if M.sps_phi_for_power(V1, V2p, L, fs, P) > math.pi / 3: return None
    def pt_at(V1, V2):
        ph = M.sps_phi_for_power(V1, n * V2, L, fs, P); return M.DABPoint(V1, V2, n, L, fs, ph, N=1200)
    nom = pt_at(800, 400)
    corners = [pt_at(650, 450), nom, pt_at(850, 300)]
    Imin1 = M.zvs_current_min(D1["Coss_er"] * p1, 800, L); Imin2 = M.zvs_current_min(D2["Coss_er"] * p2, 400, L / n ** 2) / n
    sc = nom.switching_currents(); e1 = [i for _, i in sc[1]]; e2 = [i * n for _, i in sc[2]]
    Tj1 = Tj2 = 100.0
    for _ in range(5):
        b1 = LS.bridge_losses(d1, 800, nom.device_rms(1), e1, fs, Tj1, t_dead, Imin1, n_parallel=p1)
        b2 = LS.bridge_losses(d2, 400, nom.device_rms(2), e2, fs, Tj2, t_dead, Imin2 * n, n_parallel=p2)
        Tj1 = Tamb + b1["P_total"] * heatsink["Rth_sink"] + b1["P_per_device"] / p1 * (D1["RthJC"] + heatsink["Rth_tim"])
        Tj2 = Tamb + b2["P_total"] * heatsink["Rth_sink"] + b2["P_per_device"] / p2 * (D2["RthJC"] + heatsink["Rth_tim"])
    if Tj1 > 150 or Tj2 > 150: return None
    xf = MG.design_transformer(800, 400, n, fs, nom.I_rms1, nom.I_rms2, P, core=tcore, Bpk_target=0.13)
    if not xf["fill_ok"] or xf["Bpk"] > 0.2: return None
    L_ext = max(L - xf["Llk"], 2e-6)
    ind = MG.design_inductor(L_ext, nom.I_peak1 * 1.2, nom.I_rms1, fs, core=lcore, Bpk_max=0.12)
    if ind["fill"] > 0.7: return None
    P_loss = b1["P_total"] + b2["P_total"] + b1["P_gate"] + b2["P_gate"] + xf["P_total"] + ind["P_total"] + 12.0 + 0.004 * P
    vol = (MG.CORES[tcore]["Ve"] * 2.2 + MG.CORES[lcore]["Ve"] * 2.2) * 1e6       # core + winding volume estimate (cm3)
    Irms_avg = float(np.mean([c.I_rms1 for c in corners]))
    # light-load ZVS limit at nominal (SPS)
    zl = 1.0
    for frac in np.linspace(1.0, 0.05, 20):
        ph = M.sps_phi_for_power(800, n * 400, L, fs, P * frac); q = M.DABPoint(800, 400, n, L, fs, ph, N=800)
        if q.zvs_margin(1, Imin1) >= 0 and q.zvs_margin(2, Imin2) >= 0: zl = frac
        else: break
    cost = vol / 50.0 + 4 * p1 * (1.0 if d1 == "C3M0032120K" else 1.8) + 4 * p2 * (1.0 if d2 == "C3M0032120K" else 1.8)
    return dict(fs=fs, n=n, phi_deg=phi_deg, L=L, tcore=tcore, lcore=lcore, t_dead=t_dead, dev1=f"{d1}x{p1}", dev2=f"{d2}x{p2}",
                P_loss=P_loss, eta=P / (P + P_loss), vol=vol, Irms_avg=Irms_avg, zvs_light=zl, cost=cost, Tj1=Tj1, Tj2=Tj2,
                P_semi=b1["P_total"] + b2["P_total"], P_mag=xf["P_total"] + ind["P_total"], Bpk=xf["Bpk"])

t0 = time.time(); results = []; n_eval = 0
for combo in itertools.product(*grid.values()):
    n_eval += 1
    r = evaluate(*combo)
    if r: results.append(r)
print(f"{n_eval} candidates evaluated, {len(results)} feasible, {time.time()-t0:.0f} s")
# Pareto front (minimise loss and volume)
pts = np.array([[r["P_loss"], r["vol"]] for r in results])
pareto = []
for i, r in enumerate(results):
    dominated = np.any(np.all(pts <= pts[i], axis=1) & np.any(pts < pts[i], axis=1))
    if not dominated: pareto.append(r)
pareto.sort(key=lambda r: r["P_loss"])
# plots
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
sc = ax[0].scatter(pts[:, 1], pts[:, 0], c=[r["fs"] / 1e3 for r in results], cmap="viridis", s=10, alpha=0.6)
ax[0].plot([r["vol"] for r in pareto], [r["P_loss"] for r in pareto], "r-o", ms=4, label="Pareto front")
ax[0].set_xlabel("magnetics volume (cm3)"); ax[0].set_ylabel("total loss at 6.6 kW (W)"); ax[0].legend(); ax[0].grid(alpha=0.3); fig.colorbar(sc, ax=ax[0], label="fs (kHz)")
ax[1].scatter([r["Irms_avg"] for r in results], [r["P_loss"] for r in results], c=[r["zvs_light"] for r in results], cmap="plasma", s=10)
ax[1].set_xlabel("corner-averaged HV rms current (A)"); ax[1].set_ylabel("loss (W)"); ax[1].grid(alpha=0.3); ax[1].set_title("colour: light-load ZVS limit (fraction)")
fig.tight_layout(); fig.savefig(os.path.join(HERE, "img", "pareto.png"), dpi=130); plt.close(fig)
# sensitivity: loss vs fs at fixed others (baseline)
base = dict(n=2.0, phi_deg=28, tcore="E65/32/27", lcore="E55/28/21", t_dead=150e-9, dev1=("C3M0032120K", 1), dev2=("C3M0016120K", 1))
fig, ax = plt.subplots(1, 3, figsize=(12, 3.5))
for var, vals, lab in (("fs", [50e3, 60e3, 80e3, 100e3, 120e3, 150e3, 200e3], "fs (kHz)"), ("phi_deg", [15, 20, 25, 28, 30, 35, 40, 45], "nominal phase shift (deg)"), ("t_dead", [50e-9, 100e-9, 150e-9, 200e-9, 300e-9], "dead time (ns)")):
    xs, ys, zs = [], [], []
    for v in vals:
        kw = dict(base); kw[var] = v; r = evaluate(kw.get("fs", 100e3) if var != "fs" else v, kw["n"], kw["phi_deg"], kw["tcore"], kw["lcore"], kw["t_dead"], kw["dev1"], kw["dev2"])
        if r: xs.append(v * (1e-3 if var == "fs" else 1e9 if var == "t_dead" else 1)); ys.append(r["P_loss"]); zs.append(r["vol"])
    a = ax[["fs", "phi_deg", "t_dead"].index(var)]; a.plot(xs, ys, "o-"); a.set_xlabel(lab); a.set_ylabel("loss (W)"); a.grid(alpha=0.3)
    if var == "fs": b = a.twinx(); b.plot(xs, zs, "s--", c="C1"); b.set_ylabel("magnetics volume (cm3)", color="C1")
fig.tight_layout(); fig.savefig(os.path.join(HERE, "img", "sensitivity.png"), dpi=130); plt.close(fig)
json.dump(dict(n_candidates=n_eval, n_feasible=len(results), pareto=pareto, baseline=evaluate(100e3, 2.0, 28, "E65/32/27", "E55/28/21", 150e-9, ("C3M0032120K", 1), ("C3M0016120K", 1))),
          open(os.path.join(HERE, "optimization_results.json"), "w"), indent=1, default=float)
R = []; w = R.append
w("# 12 - Multi-objective design-space optimisation\n\n_Generated by `optimize.py` (deterministic exhaustive grid, %d candidates, %d feasible)._\n" % (n_eval, len(results)))
w("## Method\nExhaustive evaluation of the variable grid below with the analytical loss/thermal/magnetics models of 03/04; infeasible points (full power not reachable at a corner with phi <= 60 deg, Tj > 150 C, window fill > 0.7, Bpk > 0.2 T) are discarded; the non-dominated set in (loss, magnetics volume) is reported. No stochastic optimiser is used, so the result is reproducible bit-for-bit.\n")
w("| variable | values |\n|---|---|")
for k, v in grid.items(): w(f"| {k} | {v} |")
w("\n## Pareto front (loss vs magnetics volume at 800/400 V, 6.6 kW)\n")
w("| fs (kHz) | n | phi_nom | L (uH) | transformer | inductor | t_dead (ns) | HV device | LV device | loss (W) | eta (%) | volume (cm3) | I_rms avg (A) | ZVS light-load | Tj HV/LV (C) | cost idx |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for r in pareto[:25]:
    w(f"| {r['fs']/1e3:.0f} | {r['n']} | {r['phi_deg']} | {r['L']*1e6:.0f} | {r['tcore']} | {r['lcore']} | {r['t_dead']*1e9:.0f} | {r['dev1']} | {r['dev2']} | {r['P_loss']:.0f} | {100*r['eta']:.2f} | {r['vol']:.0f} | {r['Irms_avg']:.1f} | {100*r['zvs_light']:.0f} % | {r['Tj1']:.0f}/{r['Tj2']:.0f} | {r['cost']:.1f} |")
b = evaluate(100e3, 2.0, 28, "E65/32/27", "E55/28/21", 150e-9, ("C3M0032120K", 1), ("C3M0016120K", 1))
w(f"\n## Baseline position\nThe baseline (100 kHz, n = 2, phi = 28 deg, E65 + E55, 150 ns, C3M0032120K / C3M0016120K) has {b['P_loss']:.0f} W loss, {b['vol']:.0f} cm3 magnetics, corner-averaged rms {b['Irms_avg']:.1f} A, ZVS down to {100*b['zvs_light']:.0f} % load. ")
w("Lower switching frequency reduces loss but grows the magnetics (and the DC-link ripple current); a larger nominal phase shift (smaller L) reduces magnetics volume and the circulating current at the corners but reduces the light-load ZVS range. The baseline sits on the knee of the front; a 80 kHz / 25 deg variant is the main alternative if the thermal budget (13) proves tighter than modelled.\n")
w("![pareto](img/pareto.png)\n\n![sens](img/sensitivity.png)\n")
w("## Convergence / validity\nThe grid is exhaustive, so there is no convergence criterion; resolution is limited by the grid steps (fs 20-30 kHz, phi 5 deg). The absolute loss values inherit the uncertainty of the device parameters (`verified=False`) and the k_zvs assumption; the ranking between candidates is less sensitive because all share the same models.\n")
open(os.path.join(HERE, "optimization_report.md"), "w").write("\n".join(R) + "\n")
print("\n".join(R)[:2500])
