#!/usr/bin/env python3
"""
Complete power-stage design calculation for the 6.6 kW SiC DAB.
Writes design_values.json (consumed by simulation, magnetics, thermal, firmware and KiCad
generators), design_report.md and img/*.png.
"""
import os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from tools.dab import dab_model as M
from tools.dab.devices import DEVICES, rds_on
from tools.dab import losses as LS
from tools.dab import magnetics as MG
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
IMG = os.path.join(HERE, "img"); os.makedirs(IMG, exist_ok=True)

# ------------------------------------------------------------------ specification
spec = dict(P=6600.0, V1_nom=800.0, V1_min=650.0, V1_max=850.0, V2_nom=400.0, V2_min=300.0, V2_max=450.0,
            fs=100e3, n=2.0, phi_nom_deg=28.0, Tamb=45.0, Tj_max=150.0, eta_peak_obj=0.975, eta_full_obj=0.965)
fs, n = spec["fs"], spec["n"]
dev1, dev2 = "C3M0032120K", "C3M0016120K"
d1, d2 = DEVICES[dev1], DEVICES[dev2]
t_dead = 150e-9
C_par = 60e-12                       # transformer winding capacitance seen by each bridge (estimate)
V1n, V2n, P = spec["V1_nom"], spec["V2_nom"], spec["P"]

# ------------------------------------------------------------------ 1. series inductance
phi_nom = math.radians(spec["phi_nom_deg"])
L = V1n * n * V2n * phi_nom * (math.pi - phi_nom) / (2 * math.pi ** 2 * fs * P)
L = round(L * 1e6) * 1e-6
Pmax_nom = M.sps_max_power(V1n, n * V2n, L, fs)

# ------------------------------------------------------------------ 2. thermal model (per device)
heatsink = dict(Rth_sink=0.22, Rth_tim=0.35)     # K/W: one extruded heatsink per bridge (4 devices), 3 m/s; silicone pad per device
def Tj_of(P_dev, dev, P_bridge):
    d = DEVICES[dev]
    Ts = spec["Tamb"] + P_bridge * heatsink["Rth_sink"]
    return Ts + P_dev * (d["RthJC"] + heatsink["Rth_tim"])

# ------------------------------------------------------------------ 3. operating-point evaluator
def evaluate(V1, V2, Pt, modulation="SPS", N=3000):
    """Return dict with waveform metrics and losses at (V1, V2, Pt); None if not reachable."""
    V2p = n * V2
    if abs(Pt) > M.sps_max_power(V1, V2p, L, fs) * 0.999:
        return None
    try:
        phi = M.sps_phi_for_power(V1, V2p, L, fs, Pt)
    except ValueError:
        return None
    pt = M.DABPoint(V1, V2, n, L, fs, phi, N=N)
    if modulation == "TPS" and abs(V2p / V1 - 1) > 0.03:
        best, _ = M.tps_search(V1, V2, n, L, fs, Pt, d1["Coss_er"], d2["Coss_er"], grid=9, N=1200)
        if best is not None:
            pt = best
    Imin1 = M.zvs_current_min(d1["Coss_er"], V1, L, C_par)
    Imin2 = M.zvs_current_min(d2["Coss_er"], V2, L / n ** 2, C_par * n ** 2) / n
    sc = pt.switching_currents()
    e1 = [i for _, i in sc[1]]; e2 = [i * n for _, i in sc[2]]      # LV-side edges in LV amperes
    Tj1 = Tj2 = 100.0
    for _ in range(6):                                              # electro-thermal iteration
        b1 = LS.bridge_losses(dev1, V1, pt.device_rms(1), e1, fs, Tj1, t_dead, Imin1)
        b2 = LS.bridge_losses(dev2, V2, pt.device_rms(2), e2, fs, Tj2, t_dead, Imin2 * n)
        Tj1 = Tj_of(b1["P_per_device"], dev1, b1["P_total"]); Tj2 = Tj_of(b2["P_per_device"], dev2, b2["P_total"])
    return dict(phi=pt.phi, D1=pt.D1, D2=pt.D2, P=pt.P, Irms1=pt.I_rms1, Ipk1=pt.I_peak1, Irms2=pt.I_rms2, Ipk2=pt.I_peak2,
                backflow=pt.Q_backflow, zvs1=pt.zvs_margin(1, Imin1), zvs2=pt.zvs_margin(2, Imin2),
                Imin1=Imin1, Imin2=Imin2 * n, b1=b1, b2=b2, Tj1=Tj1, Tj2=Tj2, pt=pt)

# ------------------------------------------------------------------ 4. magnetics at nominal
nom = evaluate(V1n, V2n, P)
xf = MG.design_transformer(V1n, V2n, n, fs, nom["Irms1"], nom["Irms2"], P, core="E65/32/27", Bpk_target=0.13)
xf_int = MG.design_transformer(V1n, V2n, n, fs, nom["Irms1"], nom["Irms2"], P, core="E65/32/27", Bpk_target=0.13, interleaved=False)
L_ext = L - xf["Llk"]
ind = MG.design_inductor(L_ext, nom["Ipk1"] * 1.2, nom["Irms1"], fs, core="E55/28/21", Bpk_max=0.12)

# ------------------------------------------------------------------ 5. DC-link capacitors
def dc_link(pt, V, C, ESR, side):
    """Capacitor rms current and voltage ripple from the pulsating bridge current."""
    v = pt.v1 if side == 1 else pt.v2
    i = pt.i if side == 1 else pt.i * n
    i_br = i * np.sign(v)                       # current drawn from the DC link
    ic = i_br - i_br.mean()
    irms = float(np.sqrt(np.mean(ic ** 2)))
    q = np.cumsum(ic) * (1 / fs / len(ic)); dv = float((q.max() - q.min()) / C)
    return dict(I_rms=irms, dV=dv, dV_pct=100 * dv / V, P_esr=irms ** 2 * ESR)
C1, ESR1 = 4 * 20e-6, 0.004          # 4 x 20 uF / 1100 V film (TDK B32778 class) -> verify ESR
C2, ESR2 = 4 * 30e-6, 0.004          # 4 x 30 uF / 700 V film
dc1 = dc_link(nom["pt"], V1n, C1, ESR1, 1); dc2 = dc_link(nom["pt"], V2n, C2, ESR2, 2)
# worst case over corners
dc1_w = max((dc_link(evaluate(a, b, P)["pt"], a, C1, ESR1, 1)["dV_pct"] for a in (650, 800, 850) for b in (300, 400, 450) if evaluate(a, b, P)), default=0)
dc2_w = max((dc_link(evaluate(a, b, P)["pt"], b, C2, ESR2, 2)["dV_pct"] for a in (650, 800, 850) for b in (300, 400, 450) if evaluate(a, b, P)), default=0)
# bleeders: < 60 V in 5 min
R_bleed1 = 300 / math.log(850 / 60) / C1; R_bleed2 = 300 / math.log(450 / 60) / C2
P_bleed1 = 850 ** 2 / R_bleed1; P_bleed2 = 450 ** 2 / R_bleed2

# ------------------------------------------------------------------ 6. full loss budget at nominal
def budget(ev, V1, V2, Pt):
    P_xf = xf["P_core"] * (V1 / V1n) ** MG.MATERIALS["3C95"]["beta"] + xf["P_cu"] * (ev["Irms1"] / nom["Irms1"]) ** 2
    P_ind = ind["P_core"] * (ev["Ipk1"] / nom["Ipk1"]) ** 2.5 + ind["P_cu"] * (ev["Irms1"] / nom["Irms1"]) ** 2
    P_cap = dc_link(ev["pt"], V1, C1, ESR1, 1)["P_esr"] + dc_link(ev["pt"], V2, C2, ESR2, 2)["P_esr"]
    P_aux = 12.0                     # gate-drive bias, control, fans (fixed)
    items = {"HV bridge conduction": ev["b1"]["P_cond"], "HV bridge switching (ZVS turn-off)": ev["b1"]["P_off"],
             "HV bridge hard switching": ev["b1"]["P_hard"], "HV bridge dead-time diode": ev["b1"]["P_diode"],
             "LV bridge conduction": ev["b2"]["P_cond"], "LV bridge switching (ZVS turn-off)": ev["b2"]["P_off"],
             "LV bridge hard switching": ev["b2"]["P_hard"], "LV bridge dead-time diode": ev["b2"]["P_diode"],
             "Gate drive (both bridges)": ev["b1"]["P_gate"] + ev["b2"]["P_gate"], "Transformer": P_xf,
             "Series inductor": P_ind, "DC-link capacitors": P_cap, "Auxiliary / bias / fans": P_aux,
             "PCB copper and bus bars (est.)": 0.004 * abs(Pt)}
    tot = sum(items.values())
    return items, tot, abs(Pt) / (abs(Pt) + tot)
items_nom, Ploss_nom, eta_nom = budget(nom, V1n, V2n, P)

# ------------------------------------------------------------------ 7. maps
V1g = np.linspace(650, 850, 9); V2g = np.linspace(300, 450, 7)
derate = np.zeros((len(V1g), len(V2g))); zvs_sps = np.full_like(derate, np.nan); zvs_tps = np.full_like(derate, np.nan)
I_lim = 1.0 * nom["Ipk1"] * 1.6          # inductor/device peak-current limit used for derating
for a, V1 in enumerate(V1g):
    for b, V2 in enumerate(V2g):
        # maximum power with phi <= 60 deg, Ipk <= limit, Tj <= Tj_max
        Pm = 0
        for frac in np.linspace(1.0, 0.1, 19):
            ev = evaluate(V1, V2, P * frac, N=1500)
            if ev and abs(ev["phi"]) <= math.pi / 3 and ev["Ipk1"] <= I_lim and ev["Tj1"] <= spec["Tj_max"] and ev["Tj2"] <= spec["Tj_max"]:
                Pm = frac; break
        derate[a, b] = Pm
        # light-load ZVS limit (SPS)
        zl = np.nan
        for frac in np.linspace(1.0, 0.05, 20):
            ev = evaluate(V1, V2, P * frac, N=1500)
            if ev is None: continue
            if ev["zvs1"] >= 0 and ev["zvs2"] >= 0: zl = frac
            else: break
        zvs_sps[a, b] = zl
# TPS ZVS extension at the 3x3 corners only (expensive)
tps_tbl = {}
for V1 in (650, 800, 850):
    for V2 in (300, 400, 450):
        zl = np.nan
        for frac in (1.0, 0.75, 0.5, 0.35, 0.25, 0.15, 0.1):
            ev = evaluate(V1, V2, P * frac, modulation="TPS", N=1200)
            if ev is None: continue
            if ev["zvs1"] >= 0 and ev["zvs2"] >= 0: zl = frac
            else: break
        ev_full = evaluate(V1, V2, P, modulation="TPS", N=1200); ev_sps = evaluate(V1, V2, P, N=1200)
        tps_tbl[(V1, V2)] = dict(zvs_min_load=zl, Irms_sps=ev_sps["Irms1"] if ev_sps else np.nan, Irms_tps=ev_full["Irms1"] if ev_full else np.nan,
                                 D1=ev_full["D1"] if ev_full else np.nan, D2=ev_full["D2"] if ev_full else np.nan,
                                 back_sps=ev_sps["backflow"] if ev_sps else np.nan, back_tps=ev_full["backflow"] if ev_full else np.nan)
# efficiency vs load at three ratios
eff_curves = {}
for (V1, V2) in ((800, 400), (650, 450), (850, 300)):
    xs, ys = [], []
    for frac in np.linspace(0.1, 1.0, 10):
        ev = evaluate(V1, V2, P * frac, N=1500)
        if ev:
            _, tot, eta = budget(ev, V1, V2, P * frac); xs.append(frac * 100); ys.append(eta * 100)
    eff_curves[(V1, V2)] = (xs, ys)
eta_peak = max(max(y) for _, y in eff_curves.values()) / 100.0

# ------------------------------------------------------------------ 8. corner table
corners = []
for V1 in (650, 800, 850):
    for V2 in (300, 400, 450):
        ev = evaluate(V1, V2, P, N=1500)
        if ev:
            _, tot, eta = budget(ev, V1, V2, P)
            corners.append(dict(V1=V1, V2=V2, phi=math.degrees(ev["phi"]), Irms1=ev["Irms1"], Ipk1=ev["Ipk1"], Irms2=ev["Irms2"],
                                zvs1=ev["zvs1"], zvs2=ev["zvs2"], Tj1=ev["Tj1"], Tj2=ev["Tj2"], Ploss=tot, eta=eta, Pmax_frac=derate[np.argmin(abs(V1g - V1)), np.argmin(abs(V2g - V2))]))
        else:
            corners.append(dict(V1=V1, V2=V2, phi=float("nan"), Irms1=float("nan"), Ipk1=float("nan"), Irms2=float("nan"), zvs1=float("nan"),
                                zvs2=float("nan"), Tj1=float("nan"), Tj2=float("nan"), Ploss=float("nan"), eta=float("nan"),
                                Pmax_frac=derate[np.argmin(abs(V1g - V1)), np.argmin(abs(V2g - V2))]))

# ------------------------------------------------------------------ 9. plots
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
im = ax[0].imshow(100 * derate.T, origin="lower", extent=[650, 850, 300, 450], aspect="auto", cmap="RdYlGn", vmin=0, vmax=100)
ax[0].set_xlabel("V1 (V)"); ax[0].set_ylabel("V2 (V)"); ax[0].set_title("Maximum power (% of 6.6 kW): phi<=60deg, Ipk, Tj<=150C"); fig.colorbar(im, ax=ax[0])
im = ax[1].imshow(100 * zvs_sps.T, origin="lower", extent=[650, 850, 300, 450], aspect="auto", cmap="viridis_r")
ax[1].set_xlabel("V1 (V)"); ax[1].set_ylabel("V2 (V)"); ax[1].set_title("SPS: minimum load with full ZVS (% of 6.6 kW)"); fig.colorbar(im, ax=ax[1])
fig.tight_layout(); fig.savefig(os.path.join(IMG, "derating_map.png"), dpi=140); plt.close(fig)
fig, a = plt.subplots(figsize=(6, 3.8))
for (V1, V2), (xs, ys) in eff_curves.items():
    a.plot(xs, ys, marker="o", ms=3, label=f"{V1} V / {V2} V")
a.axhline(100 * spec["eta_full_obj"], ls="--", c="gray", lw=0.8); a.set_xlabel("load (%)"); a.set_ylabel("calculated efficiency (%)"); a.legend(); a.grid(alpha=0.3)
a.set_title("Analytical efficiency vs load (SPS, 45 C ambient)"); fig.tight_layout(); fig.savefig(os.path.join(IMG, "efficiency_vs_load.png"), dpi=140); plt.close(fig)
fig, a = plt.subplots(figsize=(7, 4))
ks = sorted(items_nom, key=items_nom.get)
a.barh(ks, [items_nom[k] for k in ks], color="#3b6ea5"); a.set_xlabel("W"); a.set_title(f"Loss budget at 800/400 V, 6.6 kW: {Ploss_nom:.0f} W, eta = {100*eta_nom:.2f} %")
fig.tight_layout(); fig.savefig(os.path.join(IMG, "loss_budget.png"), dpi=140); plt.close(fig)
pt = nom["pt"]
fig, ax = plt.subplots(2, 1, figsize=(6, 5), sharex=True)
th = pt.theta / (2 * math.pi) * 10
ax[0].plot(th, pt.v1, label="v1"); ax[0].plot(th, pt.v2, label="n v2"); ax[0].legend(); ax[0].set_ylabel("V")
ax[1].plot(th, pt.i); ax[1].set_ylabel("i_L (A)"); ax[1].set_xlabel("time (us)"); [x.grid(alpha=0.3) for x in ax]
fig.suptitle("SPS waveforms at 800/400 V, 6.6 kW"); fig.tight_layout(); fig.savefig(os.path.join(IMG, "sps_waveforms.png"), dpi=140); plt.close(fig)

# ------------------------------------------------------------------ 10. outputs
vals = dict(spec=spec, L=L, L_ext=L_ext, phi_nom=nom["phi"], Pmax_nom=Pmax_nom, dev1=dev1, dev2=dev2, t_dead=t_dead, C_par=C_par,
            nominal=dict(Irms1=nom["Irms1"], Ipk1=nom["Ipk1"], Irms2=nom["Irms2"], Ipk2=nom["Ipk2"], backflow=nom["backflow"],
                         Imin1=nom["Imin1"], Imin2=nom["Imin2"], Tj1=nom["Tj1"], Tj2=nom["Tj2"], zvs1=nom["zvs1"], zvs2=nom["zvs2"],
                         losses=items_nom, Ploss=Ploss_nom, eta=eta_nom),
            transformer=xf, transformer_integrated_leakage=xf_int, inductor=ind, heatsink=heatsink,
            dclink=dict(C1=C1, ESR1=ESR1, C2=C2, ESR2=ESR2, nom1=dc1, nom2=dc2, worst_dV_pct_1=dc1_w, worst_dV_pct_2=dc2_w,
                        R_bleed1=R_bleed1, R_bleed2=R_bleed2, P_bleed1=P_bleed1, P_bleed2=P_bleed2),
            corners=corners, derating=dict(V1=V1g.tolist(), V2=V2g.tolist(), frac=derate.tolist(), zvs_sps=zvs_sps.tolist()),
            tps=[dict(V1=k[0], V2=k[1], **v) for k, v in tps_tbl.items()], eff_curves={f"{k[0]}/{k[1]}": v for k, v in eff_curves.items()},
            eta_peak=eta_peak, I_limit_pk=I_lim)
json.dump(vals, open(os.path.join(HERE, "design_values.json"), "w"), indent=1, default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o))

def rep():
    R = []; w = R.append
    w("# 04 - Design calculations: 6.6 kW SiC DAB\n\n_Generated by `dab_design.py`; all values analytical. Device data flagged `verified=False` in `tools/dab/devices.py`._\n")
    w("## 1. Series inductance and phase shift\n")
    w(f"phi_nom = {spec['phi_nom_deg']:.0f} deg at 800/400 V, 6.6 kW  ->  **L = {L*1e6:.0f} uH** (HV-referred), P_max(800/400) = {Pmax_nom/1e3:.1f} kW. "
      f"Transformer leakage (interleaved design) {xf['Llk']*1e6:.1f} uH, external inductor {L_ext*1e6:.1f} uH.\n")
    w("## 2. Full-power corners (SPS)\n")
    w("| V1 | V2 | phi (deg) | I_rms HV (A) | I_pk HV (A) | I_rms LV (A) | ZVS margin HV (A) | ZVS margin LV (A) | Tj HV (C) | Tj LV (C) | loss (W) | eta (%) | P_max allowed (%) |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for c in corners:
        w(f"| {c['V1']} | {c['V2']} | {c['phi']:.1f} | {c['Irms1']:.1f} | {c['Ipk1']:.1f} | {c['Irms2']:.1f} | {c['zvs1']:.1f} | {c['zvs2']:.1f} | {c['Tj1']:.0f} | {c['Tj2']:.0f} | {c['Ploss']:.0f} | {100*c['eta']:.2f} | {100*c['Pmax_frac']:.0f} |")
    w("\nNegative ZVS margins mark hard-switched edges at full power (SPS); the derating map and the TPS table show the mitigation.\n")
    w("![derating](img/derating_map.png)\n")
    w("## 3. TPS modulation at the corners (numerical minimum-rms search with ZVS constraint)\n")
    w("| V1 | V2 | I_rms SPS (A) | I_rms TPS (A) | D1 | D2 | backflow SPS (W) | backflow TPS (W) | ZVS down to (% load, TPS) |\n|---|---|---|---|---|---|---|---|---|")
    for k, v in tps_tbl.items():
        w(f"| {k[0]} | {k[1]} | {v['Irms_sps']:.1f} | {v['Irms_tps']:.1f} | {v['D1']:.2f} | {v['D2']:.2f} | {v['back_sps']:.0f} | {v['back_tps']:.0f} | {100*v['zvs_min_load'] if v['zvs_min_load']==v['zvs_min_load'] else float('nan'):.0f} |")
    w("\n## 4. Loss budget and efficiency at 800/400 V, 6.6 kW\n")
    w("| Item | W |\n|---|---|")
    for k, v in items_nom.items(): w(f"| {k} | {v:.1f} |")
    w(f"| **Total** | **{Ploss_nom:.1f}** |\n\n**Calculated efficiency {100*eta_nom:.2f} %** (objective >= {100*spec['eta_full_obj']:.1f} %), calculated peak {100*eta_peak:.2f} % (objective >= {100*spec['eta_peak_obj']:.1f} %). "
      f"Junction temperatures at 45 C ambient: HV {nom['Tj1']:.0f} C, LV {nom['Tj2']:.0f} C (heatsink {heatsink['Rth_sink']} K/W per bridge, TIM {heatsink['Rth_tim']} K/W).\n")
    w("![loss](img/loss_budget.png)\n\n![eff](img/efficiency_vs_load.png)\n\n![wave](img/sps_waveforms.png)\n")
    w("## 5. Transformer (E65/32/27 pair, 3C95)\n")
    w("| Item | interleaved (P/2-S-P/2) | non-interleaved (integrated leakage) |\n|---|---|---|")
    for k, lab in (("N1", "N1"), ("N2", "N2"), ("Bpk", "Bpk (T)"), ("P_core", "core loss (W)"), ("P_cu", "copper loss (W)"), ("Fr1", "Rac/Rdc primary"), ("Fr2", "Rac/Rdc secondary"),
                   ("strands1", "litz strands 0.1 mm primary"), ("strands2", "litz strands 0.1 mm secondary"), ("layers1", "primary layers"), ("layers2", "secondary layers"),
                   ("fill", "window fill factor"), ("Llk", "leakage (H)"), ("C_iw", "interwinding C (F)"), ("dT", "temperature rise (K, 3 m/s)")):
        a_, b_ = xf[k], xf_int[k]
        fmt = (lambda v: f"{v:.3g}") if isinstance(a_, float) else str
        w(f"| {lab} | {fmt(a_)} | {fmt(b_)} |")
    w(f"\nThe non-interleaved arrangement would give ~{xf_int['Llk']*1e6:.0f} uH of leakage, i.e. {100*xf_int['Llk']/L:.0f} % of the required {L*1e6:.0f} uH, "
      f"at the cost of {xf_int['P_cu']/xf['P_cu']:.1f}x the copper loss (proximity effect). The baseline therefore uses the interleaved transformer plus a discrete inductor; "
      "the integrated-leakage option is kept as an optimisation variable (12_Optimization) with a +/-20 % manufacturing tolerance on the leakage.\n")
    w("## 6. External series inductor (E55/28/21 pair, 3C95, gapped)\n")
    w(f"L = {L_ext*1e6:.1f} uH, N = {ind['N']}, centre-leg gap {ind['gap']*1e3:.2f} mm (before fringing correction), Bpk = {ind['Bpk']:.3f} T at 1.2 x I_pk, "
      f"stored energy {ind['E']*1e3:.1f} mJ, core loss {ind['P_core']:.1f} W, copper loss {ind['P_cu']:.1f} W ({ind['strands']} x 0.1 mm litz, {ind['layers']} layers), fill {ind['fill']:.2f}.\n")
    w("## 7. DC-link capacitors and bleeders\n")
    w(f"HV link: 4 x 20 uF / 1100 V film: I_rms = {dc1['I_rms']:.1f} A, ripple {dc1['dV_pct']:.2f} % at nominal, {dc1_w:.2f} % worst corner; ESR loss {dc1['P_esr']:.1f} W. "
      f"Bleeder {R_bleed1/1e6:.2f} MOhm ({P_bleed1:.2f} W at 850 V) discharges to < 60 V in 5 min.\n")
    w(f"LV link: 4 x 30 uF / 700 V film: I_rms = {dc2['I_rms']:.1f} A, ripple {dc2['dV_pct']:.2f} % nominal, {dc2_w:.2f} % worst; ESR loss {dc2['P_esr']:.1f} W. "
      f"Bleeder {R_bleed2/1e6:.2f} MOhm ({P_bleed2:.2f} W).\n")
    w("## 8. Protection thresholds derived here\n")
    w(f"Inductor peak current limit (hardware comparator) {I_lim:.0f} A (HV side) = {I_lim*n:.0f} A (LV side); DC-link OV trip 900 V (HV) / 480 V (LV); UV 600 V / 280 V; "
      f"Tj model limit {spec['Tj_max']:.0f} C -> heatsink NTC trip at 95 C.\n")
    return "\n".join(R) + "\n"
open(os.path.join(HERE, "design_report.md"), "w").write(rep())
print(rep()[:4000])
