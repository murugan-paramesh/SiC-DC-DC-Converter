#!/usr/bin/env python3
"""
Coupled electro-thermal-aging reduced-order model of the 6.6 kW SiC DAB along a 24 h bidirectional mission profile.
Maturity L2 (simulation only).  Coupling loop (see fig_coupling_diagram.png / README Mermaid):

   mission (P, V1, V2, Tamb)  ->  electrical model (SPS phase shift, DABPoint: I_rms, edge currents, ZVS test)
        ->  loss model (dabtools.dab.losses.bridge_losses with Rds_on(Tj))  ->  Foster thermal network per bridge
        ->  Tj(t)  --(Rds_on(Tj))-->  back to the loss model (electro-thermal feedback, one step delay at 60 s resolution)
        ->  rainflow counting of Tj(t)  ->  Coffin-Manson-Arrhenius / Bayerer-type lifetime proxy  ->  (parametric) Rds_on degradation
        --(R_mult)-->  back to the loss model (aging feedback, evaluated as a +5 % Rds_on sensitivity, not integrated over years)

Thermal network per bridge (ESTIMATES, labelled):  Tj_i = Tc_i + P_dev,i RthJC (junction, tau_jc ~ 0.3 s -> quasi-static at 60 s),
   Tc_i = Ts + P_dev,i Rth_tim (0.35 K/W silicone pad),  C_s dTs/dt = P_bridge - (Ts - T_ref)/R_s  (one lumped heatsink per bridge)
   cooling options (13_Thermal_Analysis): natural R_s = 1.0 K/W, forced air 3 m/s 0.22 K/W (baseline), cold plate 0.05 K/W (coolant 35 C)
   heatsink capacitance: 150 x 60 x 40 mm extrusion ~0.55 kg Al -> C_s = 500 J/K (natural/forced); cold plate ~0.6 kg -> 540 J/K (estimates)
Mission (ASSUMED, 24 h, 1-minute resolution): battery charging/discharging schedule with 1-minute full-power pulses every
   30 min between 09:00 and 17:00 (frequency-regulation-type events); V2 from the battery SoC (300-450 V), V1 = 800 +/- 20 V.
Lifetime proxy (literature-typical coefficients for Si IGBT modules, functional form only - NOT device data):
   LESIT:   N_f = A dTj^-alpha exp(Ea/(kB Tm)),  alpha = 5.0, Ea = 0.617 eV  (A cancels in ratios)
   Bayerer: N_f = K dTj^-4.416 exp(1285 / (Tj,min + 273)) t_on^-0.463  (I, V, D terms dropped; K cancels)
   daily damage D = sum n_i / N_f,i over the rainflow cycles; lifetime proxy ratio = D_baseline / D_option (no years claimed)
Variants: (a) natural, (b) forced air (baseline), (c) liquid, (d) forced air + power slew limit 50 W/s (cycling-aware
   reference shaping), (e) forced air + fan control holding the heatsink at >= 55 C (R_s between 0.22 and 1.0 K/W).
Outputs (results/): mission_profile.csv, thermal_traces_<variant>.csv, rainflow_<variant>.csv, lifetime_proxy.json, lifetime_table.md,
   fig_mission.png, fig_tj_traces.png, fig_rainflow.png, fig_lifetime_ratio.png, fig_coupling_diagram.png, provenance.json
Deterministic (no random numbers); runtime ~1 min.
"""
import os, sys, json, time, hashlib, platform, math, csv
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE)); DAB = os.path.join(REPO, "SiC_6k6_Industrial_DAB")
sys.path.insert(0, DAB)
from dabtools.dab.devices import DEVICES, rds_on  # noqa: E402
from dabtools.dab.losses import bridge_losses  # noqa: E402
from dabtools.dab.dab_model import DABPoint, sps_phi_for_power, zvs_current_min  # noqa: E402
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch  # noqa: E402
RES = os.path.join(HERE, "results"); os.makedirs(RES, exist_ok=True); T0 = time.time()
V = json.load(open(os.path.join(DAB, "04_Design_Calculations", "design_values.json")))
L, n, fs, P_RATED, T_DEAD, C_PAR = V["L"], V["spec"]["n"], V["spec"]["fs"], V["spec"]["P"], V["t_dead"], V["C_par"]
DEV1, DEV2 = V["dev1"], V["dev2"]; d1, d2 = DEVICES[DEV1], DEVICES[DEV2]
RTH_TIM = V["heatsink"]["Rth_tim"]; KB = 8.617e-5; DT = 60.0
COOLING = {"natural": dict(R_s=1.0, C_s=500.0, T_ref="ambient"), "forced_air": dict(R_s=0.22, C_s=500.0, T_ref="ambient"), "liquid": dict(R_s=0.05, C_s=540.0, T_ref=35.0)}
E_BATT_WH = 40000.0


# ----------------------------------------------------------------------------- mission profile (ASSUMED)
def mission():
    t_min = np.arange(0, 1440); h = t_min / 60.0
    P = np.zeros(1440)
    sched = [(0, 5, 0.5), (5, 7, 0.1), (7, 9, -0.8), (9, 12, -0.4), (12, 14, 1.0), (14, 17, 0.6), (17, 21, -1.0), (21, 23, -0.3), (23, 24, 0.2)]
    for a, b, p in sched: P[(h >= a) & (h < b)] = p * P_RATED
    for k in range(9 * 60, 17 * 60, 30):                                    # 1-minute full-power pulses (regulation events), alternating sign
        P[k] = P_RATED if (k // 30) % 2 == 0 else -P_RATED
    soc = 0.6 + np.cumsum(P) * (DT / 3600) / E_BATT_WH; soc = np.clip(soc, 0.1, 0.95)
    V2 = 300 + 150 * soc; V1 = 800 + 20 * np.sin(2 * np.pi * h / 24)
    Tamb = 35 + 10 * np.sin(2 * np.pi * (h - 9) / 24)                       # cabinet ambient 25-45 C, peak at 15:00
    return t_min, P, V1, V2, Tamb


# ----------------------------------------------------------------------------- electrical + loss model
_cache = {}
def losses(P, V1, V2, Tj1, Tj2, R_mult=1.0):
    """Per-bridge total losses (W) for one operating point; Tj enters through Rds_on(Tj) * R_mult."""
    if abs(P) < 50.0:
        return 0.0, 0.0, 0.0, 0.0
    key = (round(abs(P), -1), round(V1, 0), round(V2, 0))
    if key not in _cache:
        V2p = n * V2; phi = sps_phi_for_power(V1, V2p, L, fs, abs(P))
        if phi is None or not np.isfinite(phi): phi = math.radians(60)
        phi = min(abs(phi), math.radians(60))
        pt = DABPoint(V1, V2, n, L, fs, phi, N=2000)
        sc = pt.switching_currents()
        _cache[key] = dict(I1=pt.I_rms1 / math.sqrt(2), I2=pt.I_rms2 / math.sqrt(2), e1=[i for _, i in sc[1]], e2=[i * n for _, i in sc[2]],
                           Imin1=zvs_current_min(d1["Coss_er"] + C_PAR, V1, L), Imin2=zvs_current_min(d2["Coss_er"] + C_PAR, V2p, L) * n)
    c = _cache[key]
    # Rds_on(Tj) * R_mult through a temporary override of the device table
    r1, r2 = d1["Rds_25"], d1["Rds_150"]; d1["Rds_25"], d1["Rds_150"] = r1 * R_mult, r2 * R_mult
    s1, s2 = d2["Rds_25"], d2["Rds_150"]; d2["Rds_25"], d2["Rds_150"] = s1 * R_mult, s2 * R_mult
    try:
        b1 = bridge_losses(DEV1, V1, c["I1"], c["e1"], fs, Tj1, T_DEAD, c["Imin1"])
        b2 = bridge_losses(DEV2, V2, c["I2"], c["e2"], fs, Tj2, T_DEAD, c["Imin2"])
    finally:
        d1["Rds_25"], d1["Rds_150"] = r1, r2; d2["Rds_25"], d2["Rds_150"] = s1, s2
    return b1["P_total"], b2["P_total"], b1["P_hard"], b2["P_hard"]


# ----------------------------------------------------------------------------- thermal network + simulation
def simulate(variant, P, V1, V2, Tamb, R_mult=1.0):
    cool = COOLING["forced_air" if variant in ("slew_limited", "fan_control") else variant]
    R_s0, C_s = cool["R_s"], cool["C_s"]
    Tref = Tamb if cool["T_ref"] == "ambient" else np.full_like(Tamb, cool["T_ref"])
    Ts1 = Ts2 = Tref[0] + 5.0; Tj1 = Tj2 = Ts1 + 2.0
    Pcmd = np.copy(P)
    if variant == "slew_limited":                                           # reference shaping: |dP/dt| <= 50 W/s
        for k in range(1, len(P)):
            Pcmd[k] = np.clip(P[k], Pcmd[k - 1] - 50 * DT, Pcmd[k - 1] + 50 * DT)
    out = dict(t=[], P=[], Tj1=[], Tj2=[], Ts1=[], Ts2=[], P1=[], P2=[], hard1=[], hard2=[], R_s=[])
    for k in range(len(P)):
        p1, p2, h1, h2 = losses(Pcmd[k], V1[k], V2[k], Tj1, Tj2, R_mult)
        R_s = R_s0
        if variant == "fan_control":                                        # hold the heatsink at >= 55 C by reducing airflow (R_s up to 1.0 K/W)
            R_s = float(np.clip((55.0 - Tref[k]) / max(p1 + p2, 1.0), 0.22, 1.0)) if Ts1 < 56 else 0.22
        tau1 = R_s * C_s
        Ts1 = Tref[k] + (Ts1 - Tref[k]) * math.exp(-DT / tau1) + p1 * R_s * (1 - math.exp(-DT / tau1))
        Ts2 = Tref[k] + (Ts2 - Tref[k]) * math.exp(-DT / tau1) + p2 * R_s * (1 - math.exp(-DT / tau1))
        Tj1 = Ts1 + p1 / 4 * (d1["RthJC"] + RTH_TIM); Tj2 = Ts2 + p2 / 4 * (d2["RthJC"] + RTH_TIM)
        for kk, vv in (("t", k), ("P", Pcmd[k]), ("Tj1", Tj1), ("Tj2", Tj2), ("Ts1", Ts1), ("Ts2", Ts2), ("P1", p1), ("P2", p2), ("hard1", h1), ("hard2", h2), ("R_s", R_s)):
            out[kk].append(vv)
    return {k: np.array(v) for k, v in out.items()}, Pcmd


# ----------------------------------------------------------------------------- rainflow (ASTM E1049 four-point) and lifetime proxies
def rainflow(x):
    """Return list of (range, mean, count, t_on_minutes) from a 1-D series; residue counted as half cycles."""
    x = np.asarray(x, float)
    d = np.diff(x); idx = [0] + [i + 1 for i in range(len(d) - 1) if d[i] * d[i + 1] < 0] + [len(x) - 1]
    rev = [(i, x[i]) for i in idx]
    stack, cycles = [], []
    for i, v in rev:
        stack.append((i, v))
        while len(stack) >= 4:
            (i0, a), (i1, b), (i2, c), (i3, dd) = stack[-4:]
            X = abs(c - b); Y1 = abs(b - a); Y2 = abs(dd - c)
            if X <= Y1 and X <= Y2:
                cycles.append((X, 0.5 * (b + c), 1.0, abs(i2 - i1))); del stack[-3:-1]
            else:
                break
    for j in range(len(stack) - 1):
        (i0, a), (i1, b) = stack[j], stack[j + 1]
        cycles.append((abs(b - a), 0.5 * (a + b), 0.5, abs(i1 - i0)))
    return [c for c in cycles if c[0] > 0.05]


def damage(cycles):
    """Daily damage with the two proxies (arbitrary scale A = K = 1 -> only ratios are meaningful)."""
    D_lesit = D_bay = 0.0
    for rng_, mean, cnt, ton in cycles:
        Tm = mean + 273.15; Tmin = mean - rng_ / 2 + 273.15
        D_lesit += cnt / (rng_ ** -5.0 * math.exp(0.617 / (KB * Tm)))
        D_bay += cnt / (rng_ ** -4.416 * math.exp(1285.0 / Tmin) * max(ton * 60.0, 1.0) ** -0.463)
    return D_lesit, D_bay


def coupling_diagram(path):
    fig, ax = plt.subplots(figsize=(11, 5.2)); ax.axis("off")
    boxes = {"mission": (0.05, 0.62, "Mission profile\nP(t), V1, V2(SoC), Tamb\n[assumed 24 h]"), "elec": (0.30, 0.62, "Electrical model\nSPS phi, DABPoint\nI_rms, edge currents, ZVS test"),
             "loss": (0.55, 0.62, "Loss model\nbridge_losses()\nRds_on(Tj) x R_mult"), "therm": (0.80, 0.62, "Foster network\nTj = Ts + P RthJC+tim\nC_s dTs/dt = P - (Ts-Tref)/R_s"),
             "rain": (0.55, 0.15, "Rainflow counting\nof Tj(t)"), "life": (0.30, 0.15, "Lifetime proxy\nLESIT / Bayerer\ndaily damage D"), "age": (0.05, 0.15, "Degradation\nRds_on x (1 + 0.05 D^1.5)\n[parametric here]")}
    for k, (x, y, txt) in boxes.items():
        ax.add_patch(FancyBboxPatch((x, y), 0.18, 0.22, boxstyle="round,pad=0.01", fc="#e8f0fe" if y > 0.5 else "#fde8e8", ec="k", lw=1)); ax.text(x + 0.09, y + 0.11, txt, ha="center", va="center", fontsize=8)
    def arrow(a, b, txt="", rad=0.0, color="k"):
        xa, ya, _ = boxes[a]; xb, yb, _ = boxes[b]
        p = FancyArrowPatch((xa + 0.09, ya + 0.11), (xb + 0.09, yb + 0.11), connectionstyle=f"arc3,rad={rad}", arrowstyle="-|>", mutation_scale=14, color=color, lw=1.2, shrinkA=38, shrinkB=38); ax.add_patch(p)
        if txt: ax.text(0.5 * (xa + xb) + 0.09, 0.5 * (ya + yb) + 0.11 + (0.05 if rad == 0 else -0.09 * np.sign(rad)), txt, ha="center", fontsize=7, color=color)
    arrow("mission", "elec", "P, V1, V2"); arrow("elec", "loss", "I_rms, I_edge"); arrow("loss", "therm", "P_bridge"); arrow("therm", "loss", "Tj (feedback)", rad=0.6, color="tab:red")
    arrow("therm", "rain", "Tj(t)", rad=0.2); arrow("rain", "life", "cycles (dTj, Tm, t_on)"); arrow("life", "age", "D"); arrow("age", "loss", "R_mult (aging feedback)", rad=-0.5, color="tab:red")
    ax.text(0.5, 0.97, "Electro-thermal-aging coupling (reduced order, 60 s step); red = feedback paths", ha="center", fontsize=10)
    fig.savefig(path, dpi=130, bbox_inches="tight"); plt.close(fig)


def main():
    t_min, P, V1, V2, Tamb = mission()
    with open(os.path.join(RES, "mission_profile.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["# ASSUMED 24 h mission profile, 1-minute resolution; P > 0 = HV -> LV"]); w.writerow(["minute", "P_W", "V1_V", "V2_V", "Tamb_C"])
        for row in zip(t_min, P, V1, V2, Tamb): w.writerow([f"{v:.4g}" for v in row])
    variants = ["natural", "forced_air", "liquid", "slew_limited", "fan_control"]
    sims = {}; res = {}
    for v in variants:
        s, Pcmd = simulate(v, P, V1, V2, Tamb); sims[v] = s
        cyc1 = rainflow(s["Tj1"]); cyc2 = rainflow(s["Tj2"])
        Dl1, Db1 = damage(cyc1); Dl2, Db2 = damage(cyc2)
        energy_delivered = float(np.sum(np.abs(Pcmd)) * DT / 3600 / 1000)
        res[v] = dict(Tj1_max=float(s["Tj1"].max()), Tj1_mean=float(s["Tj1"].mean()), Tj2_max=float(s["Tj2"].max()), Tj2_mean=float(s["Tj2"].mean()),
                      dTj1_max_cycle=float(max(c[0] for c in cyc1)), dTj2_max_cycle=float(max(c[0] for c in cyc2)), n_cycles1=float(sum(c[2] for c in cyc1)), n_cycles2=float(sum(c[2] for c in cyc2)),
                      energy_kWh_per_day=energy_delivered, mean_loss_W=float((s["P1"] + s["P2"]).mean()), hard_switching_minutes=int(np.sum((s["hard1"] + s["hard2"]) > 0)),
                      D_lesit_HV=Dl1, D_lesit_LV=Dl2, D_bayerer_HV=Db1, D_bayerer_LV=Db2)
        with open(os.path.join(RES, f"thermal_traces_{v}.csv"), "w", newline="") as f:
            w = csv.writer(f); w.writerow(["minute", "P_cmd_W", "Tj_HV_C", "Tj_LV_C", "Ts_HV_C", "Ts_LV_C", "P_HV_W", "P_LV_W", "R_s_KperW"])
            for row in zip(s["t"], s["P"], s["Tj1"], s["Tj2"], s["Ts1"], s["Ts2"], s["P1"], s["P2"], s["R_s"]): w.writerow([f"{x:.4g}" for x in row])
        with open(os.path.join(RES, f"rainflow_{v}.csv"), "w", newline="") as f:
            w = csv.writer(f); w.writerow(["bridge", "range_K", "mean_C", "count", "t_on_min"])
            for c in cyc1: w.writerow(["HV"] + [f"{x:.4g}" for x in c])
            for c in cyc2: w.writerow(["LV"] + [f"{x:.4g}" for x in c])
    base = res["forced_air"]
    for v in variants:
        r = res[v]
        r["lifetime_ratio_lesit_HV"] = base["D_lesit_HV"] / r["D_lesit_HV"]; r["lifetime_ratio_lesit_LV"] = base["D_lesit_LV"] / r["D_lesit_LV"]
        r["lifetime_ratio_bayerer_HV"] = base["D_bayerer_HV"] / r["D_bayerer_HV"]; r["lifetime_ratio_bayerer_LV"] = base["D_bayerer_LV"] / r["D_bayerer_LV"]
        r["energy_ratio"] = r["energy_kWh_per_day"] / base["energy_kWh_per_day"]
    # aging feedback sensitivity: +5 % Rds_on (end-of-life criterion) on the baseline
    s5, _ = simulate("forced_air", P, V1, V2, Tamb, R_mult=1.05)
    Dl1_5, Db1_5 = damage(rainflow(s5["Tj1"])); Dl2_5, Db2_5 = damage(rainflow(s5["Tj2"]))
    res["aging_feedback_forced_air_Rds_plus5pct"] = dict(Tj1_max=float(s5["Tj1"].max()), mean_loss_W=float((s5["P1"] + s5["P2"]).mean()), loss_increase_pct=float(100 * ((s5["P1"] + s5["P2"]).mean() / base["mean_loss_W"] - 1)),
                                                        damage_increase_pct_lesit_HV=float(100 * (Dl1_5 / base["D_lesit_HV"] - 1)), damage_increase_pct_bayerer_HV=float(100 * (Db1_5 / base["D_bayerer_HV"] - 1)),
                                                        damage_increase_pct_lesit_LV=float(100 * (Dl2_5 / base["D_lesit_LV"] - 1)))
    # electro-thermal feedback sensitivity: losses at Tj vs at 25 C
    s25 = simulate("forced_air", P, V1, V2, Tamb)[0]
    P_fixed = np.array([sum(losses(P[k], V1[k], V2[k], 25.0, 25.0)[:2]) for k in range(len(P))])
    res["electro_thermal_feedback"] = dict(mean_loss_with_Tj_W=float((s25["P1"] + s25["P2"]).mean()), mean_loss_at_25C_W=float(P_fixed.mean()), increase_pct=float(100 * ((s25["P1"] + s25["P2"]).mean() / P_fixed.mean() - 1)))
    res["parameters"] = dict(cooling=COOLING, Rth_tim=RTH_TIM, RthJC=dict(HV=d1["RthJC"], LV=d2["RthJC"]), dt_s=DT, lesit=dict(alpha=5.0, Ea_eV=0.617), bayerer=dict(beta1=-4.416, beta2=1285, beta3=-0.463), note="proxies only; no absolute lifetime")
    json.dump(res, open(os.path.join(RES, "lifetime_proxy.json"), "w"), indent=1)
    # table
    md = ["# Lifetime proxy comparison (daily damage, ratios relative to forced air; NOT years)\n",
          "| variant | Tj HV max / mean (C) | Tj LV max / mean (C) | largest dTj cycle HV / LV (K) | cycles/day HV | mean loss (W) | hard-switched minutes | energy ratio | lifetime ratio LESIT HV / LV | lifetime ratio Bayerer HV / LV |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for v in variants:
        r = res[v]
        md.append(f"| {v} | {r['Tj1_max']:.1f} / {r['Tj1_mean']:.1f} | {r['Tj2_max']:.1f} / {r['Tj2_mean']:.1f} | {r['dTj1_max_cycle']:.1f} / {r['dTj2_max_cycle']:.1f} | {r['n_cycles1']:.0f} | {r['mean_loss_W']:.1f} | {r['hard_switching_minutes']} | {r['energy_ratio']:.3f} | {r['lifetime_ratio_lesit_HV']:.2f} / {r['lifetime_ratio_lesit_LV']:.2f} | {r['lifetime_ratio_bayerer_HV']:.2f} / {r['lifetime_ratio_bayerer_LV']:.2f} |")
    a = res["aging_feedback_forced_air_Rds_plus5pct"]; e = res["electro_thermal_feedback"]
    md += ["", f"Electro-thermal feedback: mean losses {e['mean_loss_with_Tj_W']:.1f} W with Rds_on(Tj) vs {e['mean_loss_at_25C_W']:.1f} W at 25 C (+{e['increase_pct']:.1f} %).",
           f"Aging feedback (+5 % Rds_on, forced air): losses +{a['loss_increase_pct']:.1f} %, daily damage proxy +{a['damage_increase_pct_lesit_HV']:.1f} % (LESIT, HV) / +{a['damage_increase_pct_bayerer_HV']:.1f} % (Bayerer, HV) - self-acceleration is weak because Tj - Tcase is only a few kelvin in this design."]
    open(os.path.join(RES, "lifetime_table.md"), "w").write("\n".join(md) + "\n"); print("\n".join(md))
    # figures
    h = t_min / 60
    fig, ax = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
    ax[0].plot(h, P / 1e3); ax[0].set_ylabel("P (kW), + = HV->LV"); ax[0].set_title("ASSUMED 24 h mission profile")
    ax[1].plot(h, V1, label="V1"); ax[1].plot(h, V2, label="V2 (battery)"); ax[1].legend(); ax[1].set_ylabel("V")
    ax[2].plot(h, Tamb); ax[2].set_ylabel("Tamb (C)"); ax[2].set_xlabel("hour")
    for a_ in ax: a_.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(RES, "fig_mission.png"), dpi=130); plt.close(fig)
    fig, ax = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True)
    for v in variants:
        ax[0].plot(h, sims[v]["Tj1"], lw=0.9, label=v); ax[1].plot(h, sims[v]["Tj2"], lw=0.9, label=v)
    ax[0].set_ylabel("Tj HV bridge (C)"); ax[1].set_ylabel("Tj LV bridge (C)"); ax[1].set_xlabel("hour"); ax[0].legend(fontsize=8)
    for a_ in ax: a_.grid(alpha=0.3)
    fig.suptitle("Junction temperature along the mission profile (reduced-order model, 60 s step)"); fig.tight_layout(); fig.savefig(os.path.join(RES, "fig_tj_traces.png"), dpi=130); plt.close(fig)
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))
    for a_, v in zip(ax, ("natural", "forced_air", "liquid")):
        cyc = rainflow(sims[v]["Tj2"]); a_.hist([c[0] for c in cyc], weights=[c[2] for c in cyc], bins=np.arange(0, 32, 1)); a_.set_title(f"{v}: LV-bridge rainflow"); a_.set_xlabel("dTj (K)"); a_.set_ylabel("cycles / day"); a_.set_yscale("log"); a_.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(RES, "fig_rainflow.png"), dpi=130); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4)); x = np.arange(len(variants))
    ax.bar(x - 0.3, [res[v]["lifetime_ratio_lesit_HV"] for v in variants], 0.2, label="LESIT HV"); ax.bar(x - 0.1, [res[v]["lifetime_ratio_lesit_LV"] for v in variants], 0.2, label="LESIT LV")
    ax.bar(x + 0.1, [res[v]["lifetime_ratio_bayerer_HV"] for v in variants], 0.2, label="Bayerer HV"); ax.bar(x + 0.3, [res[v]["lifetime_ratio_bayerer_LV"] for v in variants], 0.2, label="Bayerer LV")
    ax.set_xticks(x); ax.set_xticklabels(variants); ax.set_yscale("log"); ax.axhline(1, c="k", lw=0.8); ax.set_ylabel("lifetime proxy ratio vs forced air"); ax.legend(fontsize=8); ax.grid(alpha=0.3, which="both")
    ax.set_title("Lifetime proxy ratios (functional forms with literature-typical exponents; not years)"); fig.tight_layout(); fig.savefig(os.path.join(RES, "fig_lifetime_ratio.png"), dpi=130); plt.close(fig)
    coupling_diagram(os.path.join(RES, "fig_coupling_diagram.png"))
    import numpy, matplotlib as mpl
    def hs(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
    head = open(os.path.join(REPO, ".git", "HEAD")).read().strip(); commit = head
    if head.startswith("ref:"):
        rp = os.path.join(REPO, ".git", head[5:]); commit = open(rp).read().strip() if os.path.exists(rp) else head
    json.dump(dict(script="electro_thermal_aging.py", python=platform.python_version(), numpy=numpy.__version__, matplotlib=mpl.__version__, git_commit=commit, wall_time_s=round(time.time() - T0, 1), deterministic="no random numbers",
                   inputs={os.path.relpath(f, REPO): hs(f) for f in [os.path.join(DAB, "04_Design_Calculations", "design_values.json"), os.path.join(DAB, "dabtools", "dab", "losses.py"), os.path.join(DAB, "dabtools", "dab", "devices.py"),
                                                                     os.path.join(DAB, "dabtools", "dab", "dab_model.py"), os.path.join(DAB, "13_Thermal_Analysis", "thermal_report.md")]},
                   outputs=sorted(os.listdir(RES))), open(os.path.join(RES, "provenance.json"), "w"), indent=1)
    print("wall %.1f s" % (time.time() - T0))


if __name__ == "__main__":
    main()
