#!/usr/bin/env python3
"""
Digital-twin estimation study on SIMULATED data (switched plant + the project's PI controller).

E1  L identification (RLS, EKF, grid-Bayes) with the true L 20 % below nominal and a drift at 60 ms
E2  light-load conditioning: estimator variance and gating at 10 % load
E3  Coss_er identification with the PROPOSED transition-time sensor (true Coss 20 % above datasheet)
E4  thermal twin: Tj observer from the case NTC and the loss estimate during a load step
Outputs results/*.json, results/*.png, provenance.json.  Nothing here is measured hardware data.
"""
import hashlib, json, math, os, platform, subprocess, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from twin import (ROOT, SENSOR, Sensors, RLS, EKF_L, BayesGridL, CossEstimator, ThermalTwin, regressor_I2,
                  discrete_model, discrete_model_lossy, make_plant, period_measurements, DEVICES)   # noqa: E402
from dabtools.dab.control import DABController          # noqa: E402
from dabtools.dab.losses import bridge_losses           # noqa: E402
from dabtools.dab.dab_model import zvs_current_min      # noqa: E402
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt   # noqa: E402

V = json.load(open(os.path.join(ROOT, "04_Design_Calculations", "design_values.json")))
CP = json.load(open(os.path.join(ROOT, "11_Control_Algorithms", "control_params.json")))
L0, n, fs, P_nom = V["L"], V["spec"]["n"], V["spec"]["fs"], V["spec"]["P"]
C1, C2 = V["dclink"]["C1"] + 500e-6, V["dclink"]["C2"] + 1000e-6
Ts = 1 / fs
RES = os.path.join(HERE, "results"); os.makedirs(RES, exist_ok=True)
rng = np.random.default_rng(20261010)
out = {}
T0 = time.time()


def closed_loop(L_true_fn, load_fn, periods, V1=800.0, v2_init=380.0, R_s=0.3, est_hooks=(), N_sub=200):
    """Run the switched plant with the project's PI+EPS controller; call hooks(k, meas, cmd) each period."""
    plant = make_plant(L_true_fn(0.0), n, fs, C1, C2, V1, load_fn, R_s=R_s, N_sub=N_sub); plant.v2 = v2_init
    ctl = DABController(L0, n, fs, CP["kp"], CP["ki"], P_max=1.1 * P_nom); ctl.phi_dead_comp = 0.0
    ctl.state = "RUN"; ctl.ss_scale = 1.0
    sens = Sensors(rng)
    log = []
    for k in range(periods):
        plant.L = L_true_fn(plant.t)
        m = dict(v1=sens.meas("v1", plant.v1), v2=sens.meas("v2", plant.v2), i_pk=plant.ipk, T=40, precharge_ok=True)
        phi, D1, D2 = ctl.step(m)
        rec = plant.run_period(phi, D1, D2, record=True)
        i2, i1, i_edge = period_measurements(plant, rec)
        meas = dict(t=plant.t, v1=m["v1"], v2=m["v2"], i2=sens.meas("i2", i2), i1=sens.meas("i1", i1), i_edge_true=i_edge,
                    v2_true=plant.v2, i2_true=i2, L_true=plant.L)
        s1, s2 = plant.period_voltages(phi, D1, D2)
        cmd = dict(phi=phi, D1=D1, D2=D2, s1=s1, s2=s2)
        for h in est_hooks: h(k, meas, cmd)
        log.append((plant.t, plant.v2, phi, D1, D2, i2, plant.L))
    return np.array(log)


# ------------------------------------------------------------------ E1: L identification
R_full = 400 ** 2 / P_nom
def L_true(t): return 0.8 * L0 if t < 0.06 else 0.8 * L0 * (1 + 0.15 * min(1.0, (t - 0.06) / 0.03))   # -20 %, then drift to -8 %
rls = RLS(theta0=1 / L0, P0=(0.3 / L0) ** 2, lam=0.995, g_min=2.5e-4)
ekf = EKF_L(x0=[380.0, 0.0, 1 / L0], P0=[25.0, 100.0, (0.3 / L0) ** 2], Q=[1e-3, 1.0, (3e-3 / L0) ** 2], R=[(0.5 * SENSOR["v2_fs"] / 2048) ** 2, (0.08) ** 2], C2=C2, Ts=Ts)
bay = BayesGridL(np.linspace(0.6 * L0, 1.3 * L0, 701), sigma_y=0.08)
tr = dict(t=[], rls=[], rls_sig=[], ekf=[], bay=[], bay_lo=[], bay_hi=[], L_true=[], g=[])
def hook_E1(k, m, c):
    g, _ = discrete_model(c["s1"], c["s2"], m["v1"], m["v2"], n, fs)      # regressor on the applied PWM pattern
    th = rls.update(g, m["i2"]); x = ekf.step(g, [m["v2"], m["i2"]]); bay.update(g, m["i2"])
    if k % 10 == 0:
        bm, bs, lo, hi = bay.summary()
        tr["t"].append(m["t"]); tr["rls"].append(1 / th); tr["rls_sig"].append(rls.sigma / th ** 2); tr["ekf"].append(1 / x[2])
        tr["bay"].append(bm); tr["bay_lo"].append(lo); tr["bay_hi"].append(hi); tr["L_true"].append(m["L_true"]); tr["g"].append(g)
log1 = closed_loop(L_true, lambda v2, t: v2 / R_full if t < 0.04 else v2 / (2 * R_full), 10000, est_hooks=[hook_E1])
t = np.array(tr["t"]) * 1e3; Lt = np.array(tr["L_true"]) * 1e6
fig, ax = plt.subplots(2, 1, figsize=(7.5, 6), sharex=True)
ax[0].plot(t, Lt, "k", lw=2, label="true L (hidden)"); ax[0].plot(t, np.array(tr["rls"]) * 1e6, label="RLS (lambda 0.995)")
ax[0].plot(t, np.array(tr["ekf"]) * 1e6, label="EKF [v2, i_load, 1/L]"); ax[0].plot(t, np.array(tr["bay"]) * 1e6, "--", label="grid Bayes mean")
ax[0].fill_between(t, np.array(tr["bay_lo"]) * 1e6, np.array(tr["bay_hi"]) * 1e6, alpha=0.2, label="Bayes 95 % credible")
ax[0].axhline(L0 * 1e6, color="grey", ls=":", label="nominal 64 uH"); ax[0].set_ylabel("L (uH)"); ax[0].legend(fontsize=8, ncol=2); ax[0].grid(alpha=0.3)
ax[0].set_title("E1: series-inductance identification on simulated data (100 % -> 50 % load at 40 ms, drift from 60 ms)")
ax[1].plot(log1[:, 0] * 1e3, log1[:, 1]); ax[1].set_ylabel("v2 (V)"); ax[1].set_xlabel("t (ms)"); ax[1].grid(alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(RES, "E1_L_identification.png"), dpi=130); plt.close(fig)
def conv_time(est, true, tt, tol=0.02, t_start=0.0):
    ok = np.abs(np.array(est) / np.array(true) - 1) < tol
    for i in range(len(ok)):
        if tt[i] >= t_start and ok[i:].all(): return float(tt[i] - t_start)
    return None
seg = (t < 60)
out["E1"] = dict(
    description="true L = 0.8 L_nom (tolerance case) then +15 % drift between 60 and 90 ms; estimators start at L_nom",
    rls=dict(conv_2pct_ms=conv_time(tr["rls"], tr["L_true"], t), final_err_pct=float(100 * (tr["rls"][-1] / tr["L_true"][-1] - 1)),
             err_pct_at_50ms=float(100 * (np.interp(50, t, tr["rls"]) / (0.8 * L0) - 1)), one_sigma_pct_final=float(100 * tr["rls_sig"][-1] / tr["rls"][-1])),
    ekf=dict(conv_2pct_ms=conv_time(tr["ekf"], tr["L_true"], t), final_err_pct=float(100 * (tr["ekf"][-1] / tr["L_true"][-1] - 1)),
             err_pct_at_50ms=float(100 * (np.interp(50, t, tr["ekf"]) / (0.8 * L0) - 1))),
    bayes=dict(final_err_pct=float(100 * (tr["bay"][-1] / tr["L_true"][-1] - 1)), credible95_width_pct_final=float(100 * (tr["bay_hi"][-1] - tr["bay_lo"][-1]) / tr["L_true"][-1]),
               note="sequential grid posterior assumes a constant parameter -> it does not track the drift (reference only)"),
    bias_sources="AC loop resistance R_s = 0.3 Ohm (lossless regressor), ADC quantisation, gain errors of the v1/v2/i2 chains (fixed per unit, drawn from SENSOR); the modulator time quantisation (N_sub = 200 steps per period in the plant, 2000 in the C2000 ePWM) is removed by evaluating the regressor on the applied switching pattern")
print("E1", json.dumps(out["E1"]["rls"]), json.dumps(out["E1"]["ekf"]), round(time.time() - T0), "s")

# ------------------------------------------------------------------ E2: light load conditioning
res2 = {}
for frac, label in ((1.0, "100 %"), (0.3, "30 %"), (0.1, "10 %")):
    rls2 = RLS(theta0=1 / L0, P0=(0.3 / L0) ** 2, lam=0.995, g_min=2.5e-4)
    rls2_nogate = RLS(theta0=1 / L0, P0=(0.3 / L0) ** 2, lam=0.995, g_min=0.0)
    hist = []; hist_ng = []
    def hook(k, m, c, a=rls2, b=rls2_nogate, h=hist, hn=hist_ng):
        g, _ = discrete_model(c["s1"], c["s2"], m["v1"], m["v2"], n, fs)
        a.update(g, m["i2"]); b.update(g, m["i2"])
        if k >= 2000: h.append(1 / a.theta); hn.append(1 / b.theta)
    closed_loop(lambda t: 0.9 * L0, lambda v2, t: v2 / (R_full / frac), 4000, est_hooks=[hook])
    h = np.array(hist) / (0.9 * L0) - 1; hn = np.array(hist_ng) / (0.9 * L0) - 1
    res2[label] = dict(gated=dict(mean_err_pct=float(100 * h.mean()), std_pct=float(100 * h.std()), updates=rls2.n_upd),
                       ungated=dict(mean_err_pct=float(100 * hn.mean()), std_pct=float(100 * hn.std()), updates=rls2_nogate.n_upd))
out["E2"] = dict(description="steady state at 100/30/10 % load, true L = 0.9 L_nom, statistics over the last 2000 periods", results=res2,
                 g_min_A_H="2.5e-4 A*H (regressor threshold -> updates gated below ~25 % load)")
print("E2", json.dumps(res2), round(time.time() - T0), "s")

# ------------------------------------------------------------------ E3: Coss_er with the proposed t_tr sensor
dev1 = V["dev1"]; C_true = 1.2 * DEVICES[dev1]["Coss_er"]
rls3 = RLS(theta0=1 / L0, P0=(0.3 / L0) ** 2, lam=0.995, g_min=2.5e-4)
cest_est = CossEstimator(C0=DEVICES[dev1]["Coss_er"], P0=(0.5 * DEVICES[dev1]["Coss_er"]) ** 2, lam=0.995)
cest_nom = CossEstimator(C0=DEVICES[dev1]["Coss_er"], P0=(0.5 * DEVICES[dev1]["Coss_er"]) ** 2, lam=0.995)
tr3 = dict(t=[], C_est=[], C_nomL=[])
def hook_E3(k, m, c):
    g, ie1 = discrete_model(c["s1"], c["s2"], m["v1"], m["v2"], n, fs); th = rls3.update(g, m["i2"])
    t_tr_meas = 2 * C_true * m["v1"] / max(m["i_edge_true"], 0.2) + rng.normal(0, SENSOR["t_tr_noise"])     # SYNTHETIC sensor
    if k % 5 == 0:
        I_edge_est = discrete_model_lossy(c["s1"], c["s2"], m["v1"], m["v2"], n, fs, 1 / th, 0.3)        # lossy model (design R_s) with estimated L
        I_edge_nom = discrete_model_lossy(c["s1"], c["s2"], m["v1"], m["v2"], n, fs, L0, 0.3)            # same with nominal L
        cest_est.update(t_tr_meas, m["v1"], I_edge_est); cest_nom.update(t_tr_meas, m["v1"], I_edge_nom)
        tr3["t"].append(m["t"]); tr3["C_est"].append(cest_est.theta); tr3["C_nomL"].append(cest_nom.theta)
closed_loop(lambda t: 0.85 * L0, lambda v2, t: v2 / (R_full / 0.5), 3000, est_hooks=[hook_E3])
t3 = np.array(tr3["t"]) * 1e3
fig, ax = plt.subplots(figsize=(7.5, 4))
ax.plot(t3, np.array(tr3["C_est"]) * 1e12, label="Coss_er estimate (with estimated L)"); ax.plot(t3, np.array(tr3["C_nomL"]) * 1e12, label="Coss_er estimate (nominal L, 15 % off)")
ax.axhline(C_true * 1e12, color="k", lw=2, label="true (hidden) = 1.2 x datasheet"); ax.axhline(DEVICES[dev1]["Coss_er"] * 1e12, color="grey", ls=":", label="datasheet")
ax.set_xlabel("t (ms)"); ax.set_ylabel("Coss_er (pF)"); ax.grid(alpha=0.3); ax.legend(fontsize=8); ax.set_title("E3: Coss_er identification from a PROPOSED transition-time sensor (synthetic, 5 ns rms)")
fig.tight_layout(); fig.savefig(os.path.join(RES, "E3_Coss_identification.png"), dpi=130); plt.close(fig)
out["E3"] = dict(description="true Coss_er = 1.2 x datasheet, true L = 0.85 L_nom, 50 % load; transition-time sensor synthetic with 5 ns rms noise",
                 final_err_pct_with_estimated_L=float(100 * (tr3["C_est"][-1] / C_true - 1)), final_err_pct_with_nominal_L=float(100 * (tr3["C_nomL"][-1] / C_true - 1)),
                 note="the Coss estimate inherits the L error one-to-one through I_edge; without the sensor Coss is unobservable (observability.json)")
print("E3", json.dumps({k: v for k, v in out["E3"].items() if k.startswith("final")}), round(time.time() - T0), "s")

# ------------------------------------------------------------------ E4: thermal twin
tw_true = ThermalTwin(dev1, Ts=1e-3); tw_obs = ThermalTwin(dev1, Ts=1e-3)
tw_obs.RthJC *= 1.15                                                                   # observer with a 15 % wrong RthJC (model error)
x_true = np.array([60.0, 55.0]); tw_obs.x = np.array([45.0, 45.0])
Tj_log = []; t_log = []
for k in range(20000):                                                                 # 20 s at 1 ms
    tt = k * 1e-3
    P_dev = 6.0 if tt < 5 else (14.0 if tt < 12 else 4.0)                              # W per device (conduction+switching, ~order of the loss budget)
    P_est = P_dev * (1 + 0.1 * (tt > 5))                                               # loss estimate 10 % high after the step (model error)
    x_true = tw_true.predict_true(x_true, P_dev)
    Tc_meas = x_true[1] + rng.normal(0, SENSOR["T_noise"])
    xo = tw_obs.step(P_est, Tc_meas)
    if k % 10 == 0: t_log.append(tt); Tj_log.append((x_true[0], xo[0], x_true[1], xo[1]))
Tj = np.array(Tj_log); t4 = np.array(t_log)
fig, ax = plt.subplots(figsize=(7.5, 4))
ax.plot(t4, Tj[:, 0], "k", lw=2, label="Tj true (simulated)"); ax.plot(t4, Tj[:, 1], label="Tj observer (NTC + loss estimate, 15 % RthJC error)")
ax.plot(t4, Tj[:, 2], "k--", label="Tc true"); ax.plot(t4, Tj[:, 3], "--", label="Tc observer"); ax.set_xlabel("t (s)"); ax.set_ylabel("T (C)"); ax.grid(alpha=0.3); ax.legend(fontsize=8)
ax.set_title("E4: thermal twin (2-node Foster per bridge, ESTIMATED capacitances) - Tj observer"); fig.tight_layout(); fig.savefig(os.path.join(RES, "E4_thermal_twin.png"), dpi=130); plt.close(fig)
e = Tj[:, 1] - Tj[:, 0]
out["E4"] = dict(description="loss steps 6 -> 14 -> 4 W per device; observer has +15 % RthJC and +10 % loss-estimate error; NTC noise 1 K",
                 Tj_error_K=dict(max_abs=float(np.abs(e).max()), rms=float(np.sqrt(np.mean(e ** 2))), steady_after_step=float(e[(t4 > 10) & (t4 < 12)].mean())),
                 note="Tj is not measurable; the error is dominated by the RthJC and loss-model errors, not by the NTC noise -> calibration need, see Multiphysics_Models")
print("E4", json.dumps(out["E4"]["Tj_error_K"]), round(time.time() - T0), "s")

# ------------------------------------------------------------------ provenance
def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
try: commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE, text=True).strip()
except Exception: commit = "n/a"
prov = dict(script="run_twin_study.py", python=platform.python_version(), numpy=np.__version__, matplotlib=matplotlib.__version__, git_commit=commit,
            inputs={p: sha(os.path.join(ROOT, p)) for p in ("04_Design_Calculations/design_values.json", "11_Control_Algorithms/control_params.json", "dabtools/dab/sim_switched.py", "dabtools/dab/control.py")},
            seed=20261010, wall_s=time.time() - T0, data_origin="SIMULATED (switched plant), no hardware")
json.dump(out, open(os.path.join(RES, "twin_study.json"), "w"), indent=1); json.dump(prov, open(os.path.join(HERE, "provenance.json"), "w"), indent=1)
print("done", round(time.time() - T0), "s")
