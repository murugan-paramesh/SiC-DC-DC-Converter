#!/usr/bin/env python3
"""
Estimators and change detection on the SYNTHETIC degradation data of 01_generate_synthetic_data.py.

Estimators
  1. Temperature-compensated Rds_on:  R_meas = V_ds / I_d ;  R25_hat = R_meas * rds(25) / rds(T_meas)   (datasheet curve)
  2. RLS (2 parameters, forgetting lambda):  V_ds = I_d * theta0 + I_d (T_meas - 25) * theta1
         -> theta0 = R25 estimate, theta1 = temperature coefficient estimated from the data itself
  3. Kalman filter on R25_hat:  x = [R25, drift rate], random-walk-rate model, gives smoothed level and rate
  4. CUSUM on the standardised compensated samples (one-sided, drift k = 0.5 sigma, threshold h in sigma units),
         baseline mu0 / sigma0 from the first 30 days (burn-in), weekly block means to reduce the sample rate
Evaluation (Monte Carlo over noise realisations, deterministic seeds)
  * detection delay = time from the instant the TRUE dR/R0 crosses 1 % to the alarm (degrading scenario)
  * false alarm rate = fraction of healthy runs that alarm within 3 years, and ARL0 estimate
  * sensitivity to the temperature sensor: heatsink NTC (current design) / case sensor / junction model,
    plus a parametric sweep of the temperature error (random sigma_T and a load-dependent bias)
  * sensor requirement: minimum detectable drift vs V_ds noise and temperature error
NO RUL accuracy is claimed: the aging law is an assumption, so only detectability is studied.
"""
import os, sys, json, time, hashlib, platform, importlib.util
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DAB = os.path.join(REPO, "SiC_6k6_Industrial_DAB")
sys.path.insert(0, DAB)
from dabtools.dab.devices import rds_on  # noqa: E402
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt  # noqa: E402
spec = importlib.util.spec_from_file_location("gen", os.path.join(HERE, "01_generate_synthetic_data.py"))
gen = importlib.util.module_from_spec(spec); spec.loader.exec_module(gen)

RES = os.path.join(HERE, "results"); SEED = 20261011; T0 = time.time()
DEV = gen.DEV; P = gen.P
BURN = 13 * 7 * 24; WEEK = 7 * 24          # 13-week baseline, weekly blocks
I_GATE = 0.4 * 0.85 * P["Ipk1_nom"]        # excitation gating: samples below 40 % of the nominal sample current are discarded
MC_RUNS = 24


# --------------------------------------------------------------------------- estimators
def compensate(Vm, Im, Tm):
    """Temperature-compensated R25 estimate per sample; samples below the current gate are NaN (not used)."""
    R = Vm / np.maximum(Im, 0.5)
    z = R * rds_on(DEV, 25.0) / rds_on(DEV, Tm)
    return np.where(Im >= I_GATE, z, np.nan)


def weekly_means(z):
    nb = len(z) // WEEK
    zz = z[:nb * WEEK].reshape(nb, WEEK)
    return np.nanmean(zz, axis=1)


def rls(Vm, Im, Tm, lam=0.9995):
    th = np.array([rds_on(DEV, 25.0), (rds_on(DEV, 150) - rds_on(DEV, 25)) / 125]); Pm = np.eye(2) * 1e-2
    out = np.empty((len(Vm), 2))
    for k in range(len(Vm)):
        if Im[k] < I_GATE:                       # excitation gating
            out[k] = th; continue
        x = np.array([Im[k], Im[k] * (Tm[k] - 25.0)])
        Px = Pm @ x; g = Px / (lam + x @ Px)
        th = th + g * (Vm[k] - x @ th)
        Pm = (Pm - np.outer(g, x @ Pm)) / lam
        out[k] = th
    return out


def kalman(z, dt=1.0, q_rate=1e-14, r=None):
    r = r if r is not None else np.nanvar(z[:BURN])
    x = np.array([np.nanmean(z[:BURN]), 0.0]); Pk = np.diag([r, 1e-12])
    F = np.array([[1, dt], [0, 1]]); Q = np.array([[0, 0], [0, q_rate]]); H = np.array([1.0, 0.0])
    xs = np.empty((len(z), 2)); ps = np.empty(len(z))
    for k in range(len(z)):
        x = F @ x; Pk = F @ Pk @ F.T + Q
        if np.isfinite(z[k]):                     # gated samples: prediction only
            S = H @ Pk @ H + r; K = Pk @ H / S
            x = x + K * (z[k] - H @ x); Pk = Pk - np.outer(K, H @ Pk)
        xs[k] = x; ps[k] = Pk[0, 0]
    return xs, ps


def cusum_alarm(z, h_rel, k_rel=0.005):
    """
    One-sided CUSUM on the weekly means of the compensated R25, in RELATIVE units (fraction of the baseline):
        g_i = max(0, g_{i-1} + (block_i / mu0 - 1) - k_rel),   alarm when g_i > h_rel
    k_rel = 0.5 % = half of the 1 % drift to be detected (classic CUSUM design), h_rel in [fraction x weeks].
    Baseline mu0 = mean of the first 13 weeks. Returns the alarm hour or None.
    """
    blocks = weekly_means(z); nb = len(blocks)
    nburn = BURN // WEEK
    mu0 = blocks[:nburn].mean()
    g = 0.0
    for i in range(nburn, nb):
        g = max(0.0, g + (blocks[i] / mu0 - 1.0) - k_rel)
        if g > h_rel:
            return (i + 1) * WEEK
    return None


# --------------------------------------------------------------------------- evaluation
def eval_setting(tr_h, tr_d, sensor, rng, h_list, sigma_T=None, bias_scale=None, vds_noise=None, t_drift_K=None):
    """Monte Carlo over noise realisations; returns per-h: false-alarm fraction, mean detection delay (h), detection fraction."""
    save = (P["vds_noise"],)
    if vds_noise is not None:
        P["vds_noise"] = vds_noise
    onset = int(np.argmax(tr_d["R_mult"] - 1 >= 0.01))
    fa = {h: 0 for h in h_list}; dl = {h: [] for h in h_list}; det = {h: 0 for h in h_list}; dr_at = {h: [] for h in h_list}
    for _ in range(MC_RUNS):
        for sc, tr in (("healthy", tr_h), ("degrading", tr_d)):
            Vm, Im, Tm = gen.measure(tr, sensor, rng)
            if sigma_T is not None or bias_scale is not None:            # parametric temperature error
                b = (bias_scale or 0.0) * tr["P_dev"] * (P["RthJC"] + P["Rth_tim"])
                Tm = tr["Tj"] - b + rng.normal(0, sigma_T or 0.0, len(Tm))
            if t_drift_K is not None:                                   # slow sensor drift (e.g. NTC ageing): reading falls linearly by t_drift_K over 3 years
                Tm = Tm - t_drift_K * np.arange(len(Tm)) / len(Tm)
            z = compensate(Vm, Im, Tm)
            for h in h_list:
                a = cusum_alarm(z, h)
                if sc == "healthy":
                    fa[h] += a is not None
                elif a is not None:
                    det[h] += 1; dl[h].append(a - onset); dr_at[h].append(100 * (tr["R_mult"][min(a, len(tr["R_mult"]) - 1)] - 1))
    P["vds_noise"] = save[0]
    return {h: dict(false_alarm_frac=fa[h] / MC_RUNS, detect_frac=det[h] / MC_RUNS,
                    delay_mean_h=float(np.mean(dl[h])) if dl[h] else None,          # signed: negative = alarm before the 1 % crossing
                    delay_p90_h=float(np.percentile(dl[h], 90)) if dl[h] else None,
                    dR_at_alarm_mean_pct=float(np.mean(dr_at[h])) if dr_at[h] else None,
                    dR_at_alarm_p90_pct=float(np.percentile(dr_at[h], 90)) if dr_at[h] else None) for h in h_list}


def main():
    rng = np.random.default_rng(SEED)
    tr_h = gen.generate("healthy", np.random.default_rng(gen.SEED))
    tr_d = gen.generate("degrading", np.random.default_rng(gen.SEED + 1))
    results = dict(seed=SEED, mc_runs=MC_RUNS, onset_hour_1pct=int(np.argmax(tr_d["R_mult"] - 1 >= 0.01)),
                   eol_hour_5pct=int(np.argmax(tr_d["R_mult"] - 1 >= 0.05)))
    # ---- 1. single-realisation estimator demonstration (degrading, heatsink NTC vs case sensor)
    fig, ax = plt.subplots(2, 2, figsize=(12, 7)); yrs = tr_d["h"] / 8760
    demo = {}
    for j, sensor in enumerate(("heatsink_ntc", "case_sensor")):
        Vm, Im, Tm = gen.measure(tr_d, sensor, np.random.default_rng(SEED + 7 + j))
        z = compensate(Vm, Im, Tm); th = rls(Vm, Im, Tm); xs, ps = kalman(z)
        R0 = tr_d["R25_true"][0]
        zw = weekly_means(z); wk = len(zw); tw = (np.arange(wk) + 0.5) * WEEK / 8760
        ax[0, j].plot(yrs, 100 * (tr_d["R25_true"] / R0 - 1), "k", lw=1.5, label="true dR25/R0")
        ax[0, j].plot(tw, 100 * (zw / zw[:4].mean() - 1), ".", ms=3, alpha=0.5, label="compensated, weekly mean")
        ax[0, j].plot(yrs, 100 * (xs[:, 0] / xs[BURN, 0] - 1), "r", lw=1, label="Kalman level")
        ax[0, j].fill_between(yrs, 100 * ((xs[:, 0] - 2 * np.sqrt(ps)) / xs[BURN, 0] - 1), 100 * ((xs[:, 0] + 2 * np.sqrt(ps)) / xs[BURN, 0] - 1), color="r", alpha=0.15)
        ax[0, j].plot(yrs, 100 * (th[:, 0] / th[BURN, 0] - 1), "g", lw=1, label="RLS theta0")
        ax[0, j].set_title(f"degrading scenario, T sensor = {sensor}"); ax[0, j].set_ylabel("dR / R0 (%)"); ax[0, j].legend(fontsize=7); ax[0, j].set_ylim(-3, 9)
        ax[1, j].plot(yrs, 1e3 * th[:, 1] * 125, "g", lw=0.8, label="RLS: R150-R25 estimate (mOhm)")
        ax[1, j].axhline(1e3 * (rds_on(DEV, 150) - rds_on(DEV, 25)), c="k", ls="--", lw=0.8, label="datasheet value")
        ax[1, j].set_xlabel("years"); ax[1, j].legend(fontsize=7)
        err_T = tr_d["Tj"] - Tm
        demo[sensor] = dict(T_error_mean_K=float(err_T.mean()), T_error_std_K=float(err_T.std()),
                            compensated_weekly_std_pct=float(100 * np.std(zw[:26]) / zw[:26].mean()),
                            kalman_final_dR_pct=float(100 * (xs[-1, 0] / xs[BURN, 0] - 1)), true_final_dR_pct=float(100 * (tr_d["R25_true"][-1] / R0 - 1)),
                            rls_tempco_final_mOhm_per_125K=float(1e3 * th[-1, 1] * 125))
    for a in ax.ravel(): a.grid(alpha=0.3)
    fig.suptitle("SYNTHETIC data - estimator demonstration (no measured aging data)"); fig.tight_layout()
    fig.savefig(os.path.join(RES, "fig_estimators_demo.png"), dpi=130); plt.close(fig)
    results["demo"] = demo
    # ---- 2. detection delay vs false alarm, three sensor placements
    h_list = [0.005, 0.01, 0.015, 0.02, 0.03, 0.05]
    roc = {}
    for sensor in P["T_sensors"]:
        roc[sensor] = eval_setting(tr_h, tr_d, sensor, rng, h_list)
    results["roc_by_sensor"] = roc
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    for sensor, r in roc.items():
        far = [r[h]["false_alarm_frac"] for h in h_list]; dly = [(r[h]["delay_mean_h"] or np.nan) / 24 for h in h_list]
        ax[0].plot(far, dly, "o-", label=sensor)
        for h, x, y in zip(h_list, far, dly): ax[0].annotate(f"h={100*h:.1f}%", (x, y), fontsize=6)
        ax[1].plot(h_list, [r[h]["detect_frac"] for h in h_list], "o-", label=sensor)
    ax[0].set_xlabel("false alarm fraction (healthy runs, 3 years)"); ax[0].set_ylabel("mean detection delay after 1 % drift (days)"); ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3)
    ax[1].set_xlabel("CUSUM threshold h (fraction x weeks)"); ax[1].set_ylabel("detection fraction before 3 years"); ax[1].legend(fontsize=8); ax[1].grid(alpha=0.3)
    fig.suptitle("SYNTHETIC - CUSUM (k = 0.5 %%) detection vs false alarm rate, %d MC runs" % MC_RUNS); fig.tight_layout()
    fig.savefig(os.path.join(RES, "fig_detection_vs_false_alarm.png"), dpi=130); plt.close(fig)
    # ---- 3. sensitivity to temperature error (random sigma_T and load-dependent bias), fixed h = 6
    #      the load-dependent bias only matters when the mission mix changes: second healthy truth with +30 % load after 1.5 years
    tr_h_shift = gen.generate("healthy", np.random.default_rng(gen.SEED), p_shift=(int(1.5 * 8760), 1.3))
    sens = {}; H_FIX = 0.02
    for bs in (0.0, 0.5, 1.0, 2.0):
        sens[f"mission_shift_loadbias_x{bs}"] = eval_setting(tr_h_shift, tr_d, "case_sensor", rng, [H_FIX], sigma_T=0.5, bias_scale=bs)[H_FIX]
    for sT in (0.5, 1.0, 2.0, 5.0, 10.0):
        sens[f"sigmaT_{sT}K"] = eval_setting(tr_h, tr_d, "case_sensor", rng, [H_FIX], sigma_T=sT, bias_scale=0.0)[H_FIX]
    for bs in (0.0, 0.5, 1.0, 2.0):
        sens[f"loadbias_x{bs}"] = eval_setting(tr_h, tr_d, "case_sensor", rng, [H_FIX], sigma_T=0.5, bias_scale=bs)[H_FIX]
    for dk in (1.0, 2.0, 3.0, 5.0):
        sens[f"sensor_drift_{dk}K_over_3y"] = eval_setting(tr_h, tr_d, "case_sensor", rng, [H_FIX], sigma_T=0.5, bias_scale=0.0, t_drift_K=dk)[H_FIX]
    results["temperature_sensitivity_h0.02"] = sens
    # ---- 4. sensor requirement: minimum detectable drift vs V_ds noise and temperature error (analytic from the noise budget)
    #     weekly-mean standard deviation of the compensated R (random errors), smallest drift resolvable at 3 sigma of a weekly mean
    I_typ = 0.85 * P["Ipk1_nom"] * 0.6; R_typ = rds_on(DEV, 40.0)
    kT = (rds_on(DEV, 150) - rds_on(DEV, 25)) / 125 / R_typ          # relative tempco per K
    vds_noises = np.array([0.1e-3, 0.3e-3, 1e-3, 3e-3, 10e-3]); sTs = np.array([0.2, 0.5, 1, 2, 5, 10])
    grid = np.zeros((len(vds_noises), len(sTs)))
    for i, sv in enumerate(vds_noises):
        for j, sT in enumerate(sTs):
            rel_sample = np.sqrt((sv / (I_typ * R_typ)) ** 2 + (P["vds_lsb"] / np.sqrt(12) / (I_typ * R_typ)) ** 2 + (P["id_noise"] / I_typ) ** 2 + (kT * sT) ** 2)
            s_week = rel_sample / np.sqrt(WEEK)
            grid[i, j] = 100 * 3 * s_week
    results["min_detectable_drift_pct_analytic"] = dict(vds_noise_V=vds_noises.tolist(), sigma_T_K=sTs.tolist(), grid=grid.round(4).tolist(),
                                                        note="random errors only; a load-dependent systematic T error of b K adds kT*b directly (kT = %.2f %%/K)" % (100 * kT))
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    for i, sv in enumerate(vds_noises):
        ax.semilogx(sTs, grid[i], "o-", label=f"V_ds noise {1e3*sv:.1f} mV rms")
    ax.axhline(1.0, c="r", ls="--", lw=0.8, label="1 % incipient level"); ax.set_xlabel("temperature error sigma_T (K)"); ax.set_ylabel("3-sigma of a weekly mean of R25_hat (%)")
    ax.legend(fontsize=7); ax.grid(alpha=0.3); ax.set_title("Sensor requirement (analytic noise budget, random errors)"); fig.tight_layout()
    fig.savefig(os.path.join(RES, "fig_sensor_requirement.png"), dpi=130); plt.close(fig)
    results["systematic_T_error_equivalent_drift_pct_per_K"] = float(100 * kT)
    json.dump(results, open(os.path.join(RES, "detection_results.json"), "w"), indent=1)
    # table
    def nz(v): return float('nan') if v is None else v
    rows = ["| T sensor | h | false alarm frac (healthy, 3 y) | detect frac (degrading, 3 y) | alarm time rel. to 1 % crossing, mean (days) | p90 (days) | true dR at alarm, mean (%) | p90 (%) |", "|---|---|---|---|---|---|---|---|"]
    for sensor, r in roc.items():
        for h in h_list:
            q = r[h]; rows.append(f"| {sensor} | {100*h:.1f} % | {q['false_alarm_frac']:.2f} | {q['detect_frac']:.2f} | {nz(q['delay_mean_h'])/24:+.0f} | {nz(q['delay_p90_h'])/24:+.0f} | {nz(q['dR_at_alarm_mean_pct']):.2f} | {nz(q['dR_at_alarm_p90_pct']):.2f} |")
    rows += ["", "| temperature error case (case sensor, h = 2 %) | false alarm frac | detect frac | alarm time rel. to 1 % (days) | true dR at alarm (%) |", "|---|---|---|---|---|"]
    for k, q in sens.items():
        rows.append(f"| {k} | {q['false_alarm_frac']:.2f} | {q['detect_frac']:.2f} | {nz(q['delay_mean_h'])/24:+.0f} | {nz(q['dR_at_alarm_mean_pct']):.2f} |")
    open(os.path.join(RES, "detection_tables.md"), "w").write("\n".join(rows) + "\n")
    print("\n".join(rows)); print(json.dumps(demo, indent=1))
    # provenance
    import numpy, matplotlib as mpl
    def hs(pth): return hashlib.sha256(open(pth, "rb").read()).hexdigest()[:16]
    head = open(os.path.join(REPO, ".git", "HEAD")).read().strip(); commit = head
    if head.startswith("ref:"):
        rp = os.path.join(REPO, ".git", head[5:]); commit = open(rp).read().strip() if os.path.exists(rp) else head
    prov = dict(script=os.path.basename(__file__), python=platform.python_version(), numpy=numpy.__version__, matplotlib=mpl.__version__,
                git_commit=commit, seed=SEED, wall_time_s=round(time.time() - T0, 2),
                inputs={os.path.relpath(f, REPO): hs(f) for f in [os.path.join(HERE, "01_generate_synthetic_data.py"), os.path.join(DAB, "dabtools", "dab", "devices.py"),
                                                                  os.path.join(DAB, "04_Design_Calculations", "design_values.json")]},
                outputs=sorted(os.listdir(RES)), data_label="SYNTHETIC")
    json.dump(prov, open(os.path.join(RES, "provenance.json"), "w"), indent=1)
    print("wall %.1f s" % (time.time() - T0))


if __name__ == "__main__":
    main()
