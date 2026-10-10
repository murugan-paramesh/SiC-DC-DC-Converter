#!/usr/bin/env python3
"""
Gate-drive option analysis for the 6.6 kW DAB (C3M0032120K HV bridge, C3M0016120K LV bridge, UCC21520 drivers).
Datasheet-model based, analytic; NO measurement. Maturity L1.

Current design (07_KiCad_Schematics/gate_drive.kicad_sch, 16_BOM): UCC21520DW, Rg_on = 3.3 Ohm, Rg_off = 1.5 Ohm
(separate turn-on / turn-off paths through a diode), isolated bias +15 V / -3 V (R12P21503D), 10 k gate-source bleed,
dead time 150 ns (firmware) and ~22 ns driver interlock (DT pin 2.2 k).  NOTE: dabtools/dab/devices.py assumes
Vgs_off = -4 V; the schematic bias module gives -3 V -> both are analysed, the discrepancy is reported.

Analytic gate-charge / Miller-plateau model (piecewise linear, Baliga/Infineon-app-note style):
  R_on  = Rg_on + Rg_int + R_OH,   R_off = Rg_off + Rg_int + R_OL,  tau = R * Ciss
  V_pl  = Vth + I_d / g_fs                                     (plateau voltage)
  turn-on  (hard): t_d_on = tau ln((Von - Voff)/(Von - Vth)), t_ir = tau ln((Von - Vth)/(Von - V_pl)), di/dt = I/t_ir
                   I_g,pl = (Von - V_pl)/R_on,  t_vf = Qgd / I_g,pl,  dv/dt = V / t_vf
                   E_on = 1/2 V I (t_ir + t_vf) + E_oss(V)                   (E_oss = 1/2 Coss_er V^2, dumped)
  (current edges floored at T_EDGE_MIN = 5 ns: the exponential model gives sub-ns edges at light current, which is unphysical)
  turn-off (hard): I_g,pl = (V_pl - Voff)/R_off, t_vr,gate = Qgd / I_g,pl -> dv/dt_gate = V / t_vr,gate
                   capacitive limit: dv/dt_cap = I / C_leg, C_leg = 2 Coss_tr  (channel off, load current charges the node)
                   dv/dt_off = min(dv/dt_gate, dv/dt_cap);  t_if = tau_off ln((V_pl - Voff)/(Vth - Voff)), di/dt = I/t_if
                   E_off = 1/2 V I (t_vr + t_if) if gate-limited, else I^2 t_if^2 / (24 C_leg) (capacitive turn-off)
  ZVS operation (DAB normal case): turn-on at ~0 V -> E_on ~ 0; turn-off is capacitive: dv/dt = I / C_leg
                   (independent of Rg), E_off,ZVS = I^2 t_if^2 / (24 C_leg)   [valid while t_if < C_leg V / I]
  overshoot: V_os = L_loop di/dt (hard turn-off); ringing on capacitive commutation ~ I sqrt(L_loop / C_leg) (undamped bound)
  crosstalk (false turn-on of the OFF device of a leg during the node dv/dt):
                   V_gs,ind = Voff + R_off * Qgd/V * dv/dt * (1 - exp(-t_tr / tau_off)),  t_tr = V / (dv/dt)
                   margin = Vth_min(150 C) - V_gs,ind ;  Miller clamp: R_off -> R_clamp + Rg_int (clamp bypasses Rg_off and R_OL only)
  EMI proxy: common-mode current I_cm = C_par,node * dv/dt (C_par 100 pF per node from 14_EMI_EMC)
Multi-level / active gate driver concept: fast stage R1 until the plateau (delay, current rise), slow stage R2 during the plateau (dv/dt).
All device parameters are datasheet-typical values recalled from memory (devices.py: verified=False) -> VERIFY.
"""
import os, sys, json, time, hashlib, platform
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE)); DAB = os.path.join(REPO, "SiC_6k6_Industrial_DAB")
sys.path.insert(0, DAB)
from dabtools.dab.devices import DEVICES  # noqa: E402
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt  # noqa: E402
RES = os.path.join(HERE, "results"); os.makedirs(RES, exist_ok=True); T0 = time.time()
V = json.load(open(os.path.join(DAB, "04_Design_Calculations", "design_values.json")))

# ---- assumptions (datasheet-typical, to verify) -------------------------------------------------------
EXTRA = {"C3M0032120K": dict(Ciss=1.7e-9, g_fs=14.0, Rg_int=2.5, Vth_min_150C=1.8),
         "C3M0016120K": dict(Ciss=3.4e-9, g_fs=30.0, Rg_int=1.5, Vth_min_150C=1.8)}
T_EDGE_MIN = 5e-9                                             # s, floor on the current rise/fall time (internal gate network / package), ASSUMPTION
DRIVER = dict(name="UCC21520DW", R_OH=5.0, R_OL=0.55, I_src_max=4.0, I_sink_max=6.0, Von=15.0, note="ROH/ROL typ. values recalled, verify")
DESIGN = dict(Rg_on=3.3, Rg_off=1.5, Voff_schematic=-3.0, Voff_devices_py=-4.0)
L_LOOP = {"C3M0032120K": 15e-9, "C3M0016120K": 12e-9}        # H, power-loop inductance estimate (6-layer planes, TO-247-4) - ASSUMPTION
C_PAR_NODE = 100e-12                                          # F, switching node to heatsink/PE (14_EMI_EMC)
POINTS = {"C3M0032120K": dict(V=800.0, I_nom=V["nominal"]["Ipk1"], I_max=max(c["Ipk1"] for c in V["corners"]), I_hard=3.0),
          "C3M0016120K": dict(V=400.0, I_nom=V["nominal"]["Ipk2"], I_max=2 * max(c["Ipk1"] for c in V["corners"]), I_hard=6.0)}


def transient(dev, Rg_on, Rg_off, Voff, V, I, mode):
    d = DEVICES[dev]; e = EXTRA[dev]; Von = DRIVER["Von"]
    Ron = Rg_on + e["Rg_int"] + DRIVER["R_OH"]; Roff = Rg_off + e["Rg_int"] + DRIVER["R_OL"]
    Vth = d["Vgs_th"]; Vpl = Vth + I / e["g_fs"]; Ciss = e["Ciss"]
    Qgd = d["Qgd"] * np.sqrt(V / 800.0)                           # datasheet Qgd at 800 V scaled with Cgd ~ V^-1/2 (junction-capacitance approximation, ASSUMPTION)
    C_leg = 2 * d["Coss_tr"]
    # turn-on (only meaningful when hard switched)
    tau_on = Ron * Ciss
    t_d_on = tau_on * np.log((Von - Voff) / (Von - Vth)); t_ir = max(tau_on * np.log((Von - Vth) / (Von - Vpl)), T_EDGE_MIN)
    Ig_on = min((Von - Vpl) / Ron, DRIVER["I_src_max"]); t_vf = Qgd / Ig_on; dvdt_on = V / t_vf
    E_on = 0.5 * V * I * (t_ir + t_vf) + 0.5 * d["Coss_er"] * V ** 2
    # turn-off
    tau_off = Roff * Ciss
    Ig_off = min((Vpl - Voff) / Roff, DRIVER["I_sink_max"]); t_vr_gate = Qgd / Ig_off
    dvdt_gate = V / t_vr_gate; dvdt_cap = I / C_leg
    t_if = max(tau_off * np.log((Vpl - Voff) / (Vth - Voff)), T_EDGE_MIN); didt_off = I / t_if
    if mode == "hard":
        if dvdt_gate < dvdt_cap:
            dvdt_off = dvdt_gate; E_off = 0.5 * V * I * (t_vr_gate + t_if); regime = "gate-limited"
        else:
            dvdt_off = dvdt_cap; E_off = I ** 2 * t_if ** 2 / (24 * C_leg); regime = "capacitive"
        V_os = L_LOOP[dev] * didt_off
    else:                                                         # ZVS: capacitive commutation, E_on ~ 0
        dvdt_off = dvdt_cap; E_off = I ** 2 * t_if ** 2 / (24 * C_leg); regime = "capacitive (ZVS)"
        E_on = 0.0; dvdt_on = dvdt_cap
        V_os = I * np.sqrt(L_LOOP[dev] / C_leg)                      # undamped ringing bound at the end of the commutation
    # crosstalk on the off device seeing dv/dt (the larger of the two edges)
    dvdt_x = max(dvdt_on, dvdt_off); t_tr = V / dvdt_x
    V_ind = Voff + Roff * Qgd / V * dvdt_x * (1 - np.exp(-t_tr / tau_off))
    margin = e["Vth_min_150C"] - V_ind
    dvdt_selflimit = (e["Vth_min_150C"] - Voff) / (Roff * Qgd / V)   # dv/dt at which the induced gate voltage reaches Vth,min (Miller re-turn-on starts)
    R_clamp = 1.0 + e["Rg_int"]
    V_ind_clamp = Voff + R_clamp * Qgd / V * dvdt_x * (1 - np.exp(-t_tr / (R_clamp * Ciss)))
    return dict(Ron=Ron, Roff=Roff, Vpl=Vpl, t_d_on_ns=t_d_on * 1e9, t_ir_ns=t_ir * 1e9, t_vf_ns=t_vf * 1e9, dvdt_on_Vns=dvdt_on / 1e9,
                dvdt_off_Vns=dvdt_off / 1e9, dvdt_gate_Vns=dvdt_gate / 1e9, dvdt_cap_Vns=dvdt_cap / 1e9, t_if_ns=t_if * 1e9, t_vr_gate_ns=t_vr_gate * 1e9,
                didt_off_Ans=didt_off / 1e9, E_on_uJ=E_on * 1e6, E_off_uJ=E_off * 1e6, regime=regime, V_os=V_os,
                V_gs_induced=V_ind, crosstalk_margin=margin, V_gs_induced_clamp=V_ind_clamp, crosstalk_margin_clamp=e["Vth_min_150C"] - V_ind_clamp,
                I_cm_A=C_PAR_NODE * dvdt_x, t_tr_ns=t_tr * 1e9, dvdt_selflimit_Vns=dvdt_selflimit / 1e9, Qgd_used_nC=Qgd * 1e9)


def main():
    out = dict(assumptions=dict(EXTRA=EXTRA, DRIVER=DRIVER, DESIGN=DESIGN, L_LOOP=L_LOOP, C_PAR_NODE=C_PAR_NODE, POINTS=POINTS), options={}, sweeps={})
    fs = V["spec"]["fs"]
    Rg = np.linspace(0.0, 20.0, 41)
    fig1, ax1 = plt.subplots(1, 2, figsize=(11, 4)); fig2, ax2 = plt.subplots(1, 2, figsize=(11, 4)); fig3, ax3 = plt.subplots(1, 2, figsize=(11, 4.2)); fig4, ax4 = plt.subplots(1, 2, figsize=(11, 4))
    for j, dev in enumerate(("C3M0032120K", "C3M0016120K")):
        pt = POINTS[dev]; Vdc = pt["V"]
        sw = {}
        for Voff in (DESIGN["Voff_schematic"], DESIGN["Voff_devices_py"]):
            rows = [transient(dev, r, r, Voff, Vdc, pt["I_hard"], "hard") for r in Rg]            # hard switching at the light-load edge current
            rows_z = [transient(dev, DESIGN["Rg_on"], r, Voff, Vdc, pt["I_nom"], "zvs") for r in Rg]  # ZVS at nominal, Rg_off swept
            rows_x = [transient(dev, DESIGN["Rg_on"], r, Voff, Vdc, pt["I_max"], "zvs") for r in Rg]  # ZVS at the worst-corner current
            sw[f"Voff_{Voff:+.0f}V"] = dict(Rg=Rg.tolist(),
                                            hard=dict(dvdt_on=[q["dvdt_on_Vns"] for q in rows], dvdt_off=[q["dvdt_off_Vns"] for q in rows], E_on=[q["E_on_uJ"] for q in rows], E_off=[q["E_off_uJ"] for q in rows], V_os=[q["V_os"] for q in rows], margin=[q["crosstalk_margin"] for q in rows]),
                                            zvs_nom=dict(dvdt=[q["dvdt_off_Vns"] for q in rows_z], E_off=[q["E_off_uJ"] for q in rows_z], margin=[q["crosstalk_margin"] for q in rows_z], margin_clamp=[q["crosstalk_margin_clamp"] for q in rows_z]),
                                            zvs_max=dict(dvdt=[q["dvdt_off_Vns"] for q in rows_x], margin=[q["crosstalk_margin"] for q in rows_x], margin_clamp=[q["crosstalk_margin_clamp"] for q in rows_x], V_os=[q["V_os"] for q in rows_x]))
            ls = "-" if Voff == DESIGN["Voff_schematic"] else "--"
            ax3[j].plot(Rg, [q["crosstalk_margin"] for q in rows_z], "b" + ls, label=f"ZVS nominal I, Voff {Voff:+.0f} V")
            ax3[j].plot(Rg, [q["crosstalk_margin"] for q in rows_x], "r" + ls, label=f"ZVS worst-corner I, Voff {Voff:+.0f} V")
            ax3[j].plot(Rg, [q["crosstalk_margin_clamp"] for q in rows_x], "g" + ls, label=f"worst corner + Miller clamp, Voff {Voff:+.0f} V")
        out["sweeps"][dev] = sw
        rows = [transient(dev, r, r, DESIGN["Voff_schematic"], Vdc, pt["I_hard"], "hard") for r in Rg]
        rows_z = [transient(dev, DESIGN["Rg_on"], r, DESIGN["Voff_schematic"], Vdc, pt["I_nom"], "zvs") for r in Rg]
        ax1[j].plot(Rg, [q["dvdt_on_Vns"] for q in rows], label=f"hard turn-on, I = {pt['I_hard']} A (gate-limited)")
        ax1[j].plot(Rg, [q["dvdt_off_Vns"] for q in rows], label=f"hard turn-off, I = {pt['I_hard']} A")
        ax1[j].axhline(rows_z[0]["dvdt_cap_Vns"], c="k", ls="--", lw=0.8, label=f"ZVS, nominal I = {pt['I_nom']:.1f} A: I/C_leg (Rg independent)")
        ax1[j].axhline(transient(dev, 3.3, 1.5, -3, Vdc, pt["I_max"], "zvs")["dvdt_cap_Vns"], c="k", ls=":", lw=0.8, label=f"ZVS, worst-corner I = {pt['I_max']:.1f} A")
        ax1[j].axvline(DESIGN["Rg_on"], c="gray", lw=0.6); ax1[j].axvline(DESIGN["Rg_off"], c="gray", lw=0.6)
        ax1[j].set_xlabel("external Rg (Ohm)"); ax1[j].set_ylabel("dv/dt (V/ns)"); ax1[j].set_title(f"{dev}, {Vdc:.0f} V"); ax1[j].legend(fontsize=7); ax1[j].grid(alpha=0.3); ax1[j].set_ylim(0, 60)
        ax2[j].semilogy(Rg, [q["E_on_uJ"] + q["E_off_uJ"] for q in rows], label=f"hard switching E_on + E_off at I = {pt['I_hard']} A")
        ax2[j].semilogy(Rg, [q["E_off_uJ"] for q in rows_z], label=f"ZVS turn-off E_off at I = {pt['I_nom']:.1f} A (capacitive, model)")
        key = [k for k in DEVICES[dev] if k.startswith("Eoff_")][0]
        ax2[j].axhline(DEVICES[dev][key] * 1e6 * 0.35 * pt["I_nom"] / float(key.split("_")[2][:-1]) * Vdc / float(key.split("_")[1][:-1]), c="k", ls="--", lw=0.8, label="design assumption 0.35 x datasheet Eoff (losses.py)")
        ax2[j].set_xlabel("external Rg (Ohm)"); ax2[j].set_ylabel("energy per edge (uJ)"); ax2[j].set_title(f"{dev}"); ax2[j].legend(fontsize=7); ax2[j].grid(alpha=0.3, which="both")
        ax3[j].axhline(0, c="k", lw=0.8); ax3[j].axvline(DESIGN["Rg_off"], c="gray", lw=0.6)
        ax3[j].set_xlabel("external Rg_off (Ohm)"); ax3[j].set_ylabel("crosstalk margin Vth,min(150 C) - V_gs,induced (V)"); ax3[j].set_title(f"{dev}: false turn-on margin"); ax3[j].legend(fontsize=6.5); ax3[j].grid(alpha=0.3)
        # trade-off map: hard-switching loss vs dv/dt, colour = overshoot
        sc = ax4[j].scatter([q["dvdt_off_Vns"] for q in rows], [q["E_on_uJ"] + q["E_off_uJ"] for q in rows], c=[q["V_os"] for q in rows], cmap="viridis", s=18)
        for r, q in zip(Rg[::8], rows[::8]): ax4[j].annotate(f"{r:.0f} Ohm", (q["dvdt_off_Vns"], q["E_on_uJ"] + q["E_off_uJ"]), fontsize=6)
        ax4[j].set_xlabel("hard turn-off dv/dt (V/ns)"); ax4[j].set_ylabel("E_on + E_off hard (uJ)"); ax4[j].set_title(f"{dev}: trade-off map (colour = L_loop di/dt overshoot, V)"); ax4[j].grid(alpha=0.3)
        fig4.colorbar(sc, ax=ax4[j])
        # option table at the operating points
        opts = {}
        for name, (ron, roff, voff, clamp) in {"A fixed Rg 3.3/3.3": (3.3, 3.3, -3.0, False), "B two-level 3.3/1.5 (current design, -3 V)": (3.3, 1.5, -3.0, False),
                                               "B' two-level 3.3/1.5, -4 V bias": (3.3, 1.5, -4.0, False), "C two-level + Miller clamp (-3 V)": (3.3, 1.5, -3.0, True),
                                               "D slow Rg 10/10 (EMI-oriented)": (10.0, 10.0, -3.0, False)}.items():
            h = transient(dev, ron, roff, voff, Vdc, pt["I_hard"], "hard"); z = transient(dev, ron, roff, voff, Vdc, pt["I_nom"], "zvs"); x = transient(dev, ron, roff, voff, Vdc, pt["I_max"], "zvs")
            mkey = "crosstalk_margin_clamp" if clamp else "crosstalk_margin"
            opts[name] = dict(hard_dvdt_on_Vns=round(h["dvdt_on_Vns"], 1), hard_dvdt_off_Vns=round(h["dvdt_off_Vns"], 1), hard_E_total_uJ=round(h["E_on_uJ"] + h["E_off_uJ"], 1), hard_V_os=round(h["V_os"], 1),
                              hard_P_at_fs_W_per_edge=round((h["E_on_uJ"] + h["E_off_uJ"]) * 1e-6 * fs, 2),
                              zvs_dvdt_nom_Vns=round(z["dvdt_off_Vns"], 1), zvs_dvdt_max_Vns=round(x["dvdt_off_Vns"], 1), zvs_E_off_nom_uJ=round(z["E_off_uJ"], 3), zvs_t_if_ns=round(z["t_if_ns"], 2),
                              crosstalk_margin_nom_V=round(z[mkey], 2), crosstalk_margin_worst_V=round(x[mkey], 2), I_cm_worst_A=round(x["I_cm_A"], 2), zvs_ringing_bound_V=round(x["V_os"], 0),
                              hard_turn_on_crosstalk_margin_V=round(h[mkey], 2), dvdt_selflimit_Vns=round(z["dvdt_selflimit_Vns"], 1), Qgd_used_nC=round(z["Qgd_used_nC"], 1))
        # E multi-level driver concept: fast stage 1 Ohm until plateau, slow stage 10 Ohm during the plateau (hard switching only)
        f = transient(dev, 1.0, 1.0, -3.0, Vdc, pt["I_hard"], "hard"); s = transient(dev, 10.0, 10.0, -3.0, Vdc, pt["I_hard"], "hard")
        # turn-on: current rise with the fast stage, voltage fall with the slow stage; turn-off: voltage rise slow stage, current fall fast stage
        E_ml = 0.5 * Vdc * pt["I_hard"] * (f["t_ir_ns"] + s["t_vf_ns"]) * 1e-9 * 1e6 + 0.5 * DEVICES[dev]["Coss_er"] * Vdc ** 2 * 1e6 + s["E_off_uJ"]
        opts["E multi-level (1 Ohm pre-plateau / 10 Ohm plateau) concept"] = dict(hard_dvdt_on_Vns=round(s["dvdt_on_Vns"], 1), hard_dvdt_off_Vns=round(s["dvdt_off_Vns"], 1), hard_E_total_uJ=round(E_ml, 1),
                                                                                hard_V_os=round(f["V_os"], 1), hard_P_at_fs_W_per_edge=round(E_ml * 1e-6 * fs, 2),
                                                                                zvs_dvdt_nom_Vns=opts["B two-level 3.3/1.5 (current design, -3 V)"]["zvs_dvdt_nom_Vns"], zvs_E_off_nom_uJ="no gain (capacitive)",
                                                                                note="hard switching: delay/di-dt of 1 Ohm with the dv/dt of 10 Ohm; under ZVS no benefit")
        out["options"][dev] = opts
    for f, nm in ((fig1, "fig_dvdt_vs_rg.png"), (fig2, "fig_loss_vs_rg.png"), (fig3, "fig_crosstalk_margin.png"), (fig4, "fig_tradeoff_map.png")):
        f.tight_layout(); f.savefig(os.path.join(RES, nm), dpi=130); plt.close(f)
    # ZVS share of the operating envelope (from design_values zvs_sps minimum-load map): fraction of (V1,V2,P) grid in ZVS
    zmap = np.array(V["derating"]["zvs_sps"]); loads = np.linspace(0.1, 1.0, 10)
    share = float(np.mean([(loads >= z).mean() for z in zmap.ravel()]))
    out["zvs_share_of_envelope_grid"] = share
    out["summary"] = {}
    for dev in out["options"]:
        b = out["options"][dev]["B two-level 3.3/1.5 (current design, -3 V)"]; b4 = out["options"][dev]["B' two-level 3.3/1.5, -4 V bias"]
        out["summary"][dev] = dict(zvs_dvdt_nom_Vns=b["zvs_dvdt_nom_Vns"], zvs_dvdt_worst_Vns=b["zvs_dvdt_max_Vns"], crosstalk_margin_worst_minus3V=b["crosstalk_margin_worst_V"],
                                   crosstalk_margin_worst_minus4V=b4["crosstalk_margin_worst_V"], hard_P_per_edge_W=b["hard_P_at_fs_W_per_edge"], zvs_E_off_model_uJ=b["zvs_E_off_nom_uJ"])
    json.dump(out, open(os.path.join(RES, "gate_drive_results.json"), "w"), indent=1)
    # markdown table
    rows = []
    for dev, opts in out["options"].items():
        rows += [f"\n**{dev}** ({POINTS[dev]['V']:.0f} V; hard-switched at {POINTS[dev]['I_hard']} A, ZVS at {POINTS[dev]['I_nom']:.1f} A nominal / {POINTS[dev]['I_max']:.1f} A worst corner)\n",
                 "| option | hard dv/dt on/off (V/ns) | hard E_on+E_off (uJ) | hard P per edge at 100 kHz (W) | hard V_os (V) | ZVS dv/dt nom/worst (V/ns) | ZVS E_off model (uJ) | crosstalk margin ZVS nom/worst (V) | crosstalk margin at hard turn-on (V) | self-limiting dv/dt (V/ns) | I_cm worst (A) |",
                 "|---|---|---|---|---|---|---|---|---|---|---|"]
        for k, q in opts.items():
            rows.append(f"| {k} | {q['hard_dvdt_on_Vns']}/{q['hard_dvdt_off_Vns']} | {q['hard_E_total_uJ']} | {q['hard_P_at_fs_W_per_edge']} | {q['hard_V_os']} | {q.get('zvs_dvdt_nom_Vns','-')}/{q.get('zvs_dvdt_max_Vns','-')} | {q.get('zvs_E_off_nom_uJ','-')} | {q.get('crosstalk_margin_nom_V','-')}/{q.get('crosstalk_margin_worst_V','-')} | {q.get('hard_turn_on_crosstalk_margin_V','-')} | {q.get('dvdt_selflimit_Vns','-')} | {q.get('I_cm_worst_A','-')} |")
    open(os.path.join(RES, "option_table.md"), "w").write("\n".join(rows) + "\n")
    print("\n".join(rows)); print(json.dumps(out["summary"], indent=1)); print("ZVS share of envelope grid: %.2f" % share)
    import numpy, matplotlib as mpl
    def hs(pth): return hashlib.sha256(open(pth, "rb").read()).hexdigest()[:16]
    head = open(os.path.join(REPO, ".git", "HEAD")).read().strip(); commit = head
    if head.startswith("ref:"):
        rp = os.path.join(REPO, ".git", head[5:]); commit = open(rp).read().strip() if os.path.exists(rp) else head
    json.dump(dict(script=os.path.basename(__file__), python=platform.python_version(), numpy=numpy.__version__, matplotlib=mpl.__version__, git_commit=commit,
                   wall_time_s=round(time.time() - T0, 2), deterministic="no random numbers",
                   inputs={os.path.relpath(f, REPO): hs(f) for f in [os.path.join(DAB, "04_Design_Calculations", "design_values.json"), os.path.join(DAB, "dabtools", "dab", "devices.py"),
                                                                     os.path.join(DAB, "16_BOM", "bom.csv"), os.path.join(DAB, "07_KiCad_Schematics", "gate_drive.kicad_sch")]},
                   outputs=sorted(os.listdir(RES))), open(os.path.join(RES, "provenance.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
