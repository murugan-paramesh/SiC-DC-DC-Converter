#!/usr/bin/env python3
"""
L4 supervisory layer: self-optimising operating-point selection inside the validated envelope.

For a demanded power and the measured port voltages the supervisor chooses the inner phase shifts
(D1, D2) - the PI loop sets the outer phase shift - to minimise the inductor rms current subject to
ZVS margins at both bridges and the peak-current limit, evaluated on the L1 model with the ESTIMATED
L (and Coss_er).  A deterministic fallback (fixed EPS voltage-matching schedule with nominal
parameters) is used whenever the estimate is not trusted.  All commands pass the same limiter and
protections as the fixed schedule (dabtools.dab.control).

Study: true L = 0.8 L_nom (tolerance), 27 operating points (V1 x V2 x P) on the switched plant.
Compares (a) fixed EPS schedule designed with nominal L and (b) the adaptive supervisor.  Metrics are
measured on the plant (true parameters): rms current, hard-switched edges per period, peak current.
SIMULATION ONLY - maturity L2.
"""
import json, math, os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from twin import ROOT, make_plant, DEVICES, RLS, discrete_model, Sensors   # noqa: E402
from dabtools.dab.dab_model import DABPoint, zvs_current_min              # noqa: E402
from dabtools.dab.control import DABController                            # noqa: E402
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt  # noqa: E402

V = json.load(open(os.path.join(ROOT, "04_Design_Calculations", "design_values.json")))
CP = json.load(open(os.path.join(ROOT, "11_Control_Algorithms", "control_params.json")))
L0, n, fs, P_nom = V["L"], V["spec"]["n"], V["spec"]["fs"], V["spec"]["P"]
C1, C2 = V["dclink"]["C1"] + 500e-6, V["dclink"]["C2"] + 1000e-6
Coss1, Coss2 = DEVICES[V["dev1"]]["Coss_er"], DEVICES[V["dev2"]]["Coss_er"]
ENVELOPE = dict(V1=(650.0, 850.0), V2=(300.0, 450.0), P_max=P_nom, phi_max=math.radians(60), D_min=0.12, I_pk_max=32.0)
RES = os.path.join(HERE, "results"); os.makedirs(RES, exist_ok=True)


def i_min(Coss, Vdc, L):
    return zvs_current_min(Coss, Vdc, L)


def phi_for_power(P, V1, V2, D1, D2, L):
    """Bisection on the L1 model (numeric) for the outer phase shift giving P (W, >0 forward)."""
    lo, hi = 0.0, ENVELOPE["phi_max"]
    for _ in range(18):
        mid = 0.5 * (lo + hi)
        if DABPoint(V1, V2, n, L, fs, mid, D1, D2, N=1200).P < P: lo = mid
        else: hi = mid
    return 0.5 * (lo + hi)


class Supervisor:
    def __init__(self, margin_A=1.0, trust_sigma=0.05):
        self.margin, self.trust = margin_A, trust_sigma
        self.n_fallback = 0; self.n_adaptive = 0

    def fixed_schedule(self, V1, V2):
        d = n * V2 / max(V1, 1.0)
        return (max(ENVELOPE["D_min"], min(1.0, d)), 1.0) if d < 1 else (1.0, max(ENVELOPE["D_min"], min(1.0, 1.0 / d)))

    def select(self, P, V1, V2, L_est, sigma_rel, Coss1_est=Coss1, Coss2_est=Coss2):
        """Return (D1, D2, info). Fallback when the estimate is not trusted or outside the validated band."""
        if not (ENVELOPE["V1"][0] <= V1 <= ENVELOPE["V1"][1] and ENVELOPE["V2"][0] <= V2 <= ENVELOPE["V2"][1]) \
                or sigma_rel > self.trust or not (0.7 * L0 <= L_est <= 1.3 * L0) or abs(P) > ENVELOPE["P_max"]:
            self.n_fallback += 1; return (*self.fixed_schedule(V1, V2), dict(mode="fallback"))
        d = n * V2 / V1; best = None
        Dm1, Dm2 = self.fixed_schedule(V1, V2)
        cands = []
        for D1 in np.unique(np.clip([Dm1, Dm1 - 0.1, Dm1 - 0.2, 1.0], ENVELOPE["D_min"], 1.0)):
            for D2 in np.unique(np.clip([Dm2, Dm2 - 0.1, Dm2 - 0.2, 1.0], ENVELOPE["D_min"], 1.0)):
                cands.append((float(D1), float(D2)))
        for D1, D2 in cands:
            phi = phi_for_power(abs(P), V1, V2, D1, D2, L_est)
            pt = DABPoint(V1, V2, n, L_est, fs, phi, D1, D2, N=1200)
            if abs(pt.P - abs(P)) > 0.03 * abs(P) + 20: continue              # power not reachable with this D pair
            m1 = pt.zvs_margin(1, i_min(Coss1_est, V1, L_est)); m2 = pt.zvs_margin(2, i_min(Coss2_est, n * V2, L_est) / 1.0)
            feas = (m1 >= self.margin) and (m2 >= self.margin) and pt.I_peak1 <= ENVELOPE["I_pk_max"]
            score = pt.I_rms1 + (0 if feas else 100 + 10 * max(0, self.margin - min(m1, m2)))
            if best is None or score < best[0]: best = (score, D1, D2, phi, m1, m2, feas, pt.I_rms1)
        if best is None:
            self.n_fallback += 1; return (*self.fixed_schedule(V1, V2), dict(mode="fallback-nocand"))
        self.n_adaptive += 1
        return best[1], best[2], dict(mode="adaptive", phi=best[3], m1=best[4], m2=best[5], feasible=best[6], Irms_pred=best[7])


def evaluate_on_plant(V1, V2, P, D1, D2, L_true, periods=120):
    """Closed-loop PI (regulates v2) with the chosen D pair on the true plant; returns measured metrics."""
    R = V2 ** 2 / P
    plant = make_plant(L_true, n, fs, C1, C2, V1, lambda v2, t: v2 / R, R_s=0.3, N_sub=200); plant.v2 = V2
    ctl = DABController(L0, n, fs, CP["kp"], CP["ki"], P_max=1.1 * P_nom, v2_ref=V2); ctl.state = "RUN"; ctl.ss_scale = 1.0; ctl.use_eps = False
    rec = None
    for k in range(periods):
        m = dict(v1=plant.v1, v2=plant.v2, i_pk=plant.ipk, T=40, precharge_ok=True)
        phi, _, _ = ctl.step(m)
        rec = plant.run_period(phi, D1, D2, record=(k == periods - 1))
    r = np.asarray(rec); iL = r[:, 3]; va = r[:, 1]; vb = r[:, 2]
    def hard_edges(v, Imin, port):
        sg = np.sign(np.round(v, 1)); sp = np.concatenate([sg[-1:], sg]); dv = np.diff(sp); k = np.nonzero(dv)[0]; cnt = 0
        for kk in k:
            edge = dv[kk]; i_after = iL[kk % len(iL)]
            sign = -1.0 if edge > 0 else 1.0
            if port == 2: sign = -sign
            if sign * i_after < Imin: cnt += 1
        return cnt, len(k)
    h1, e1 = hard_edges(va, i_min(Coss1, V1, L_true), 1); h2, e2 = hard_edges(vb, i_min(Coss2, n * V2, L_true), 2)
    return dict(Irms=float(np.sqrt(np.mean(iL ** 2))), Ipk=float(np.abs(iL).max()), hard_edges=h1 + h2, edges=e1 + e2, phi_deg=math.degrees(phi), v2=float(plant.v2))


def main():
    t0 = time.time(); rng = np.random.default_rng(7)
    L_true = 0.8 * L0
    sup = Supervisor(margin_A=1.0, trust_sigma=0.05)
    rows = []
    for V1 in (650.0, 800.0, 850.0):
        for V2 in (300.0, 400.0, 450.0):
            for pf in (0.1, 0.3, 1.0):
                P = pf * P_nom
                Df = sup.fixed_schedule(V1, V2)                               # fixed EPS matching (nominal design)
                # estimated L: RLS result of the twin study (0.25 % error, 0.9 % 1-sigma) - emulate with that accuracy
                L_est = L_true * (1 + rng.normal(0.0025, 0.004)); sig = 0.009
                Da1, Da2, info = sup.select(P, V1, V2, L_est, sig)
                mf = evaluate_on_plant(V1, V2, P, Df[0], Df[1], L_true)
                ma = evaluate_on_plant(V1, V2, P, Da1, Da2, L_true)
                # what the nominal-parameter model predicted for the fixed schedule (to show the prediction error)
                phi_n = phi_for_power(P, V1, V2, Df[0], Df[1], L0); ptn = DABPoint(V1, V2, n, L0, fs, phi_n, Df[0], Df[1], N=1200)
                rows.append(dict(V1=V1, V2=V2, P_pct=100 * pf, fixed=dict(D1=Df[0], D2=Df[1], **mf), adaptive=dict(D1=Da1, D2=Da2, mode=info["mode"], **ma),
                                 nominal_model_pred=dict(Irms=ptn.I_rms1, m1=ptn.zvs_margin(1, i_min(Coss1, V1, L0)), m2=ptn.zvs_margin(2, i_min(Coss2, n * V2, L0)))))
                print(f"V1={V1:.0f} V2={V2:.0f} P={100*pf:3.0f}%  fixed D=({Df[0]:.2f},{Df[1]:.2f}) Irms={mf['Irms']:.2f} hard={mf['hard_edges']}/{mf['edges']} | adaptive D=({Da1:.2f},{Da2:.2f}) {info['mode']} Irms={ma['Irms']:.2f} hard={ma['hard_edges']}/{ma['edges']}")
    # summary
    irms_f = np.array([r["fixed"]["Irms"] for r in rows]); irms_a = np.array([r["adaptive"]["Irms"] for r in rows])
    hf = np.array([r["fixed"]["hard_edges"] for r in rows]); ha = np.array([r["adaptive"]["hard_edges"] for r in rows])
    pred_err = np.array([r["nominal_model_pred"]["Irms"] / r["fixed"]["Irms"] - 1 for r in rows])
    summary = dict(points=len(rows), L_true_over_nominal=0.8,
                   rms_current_change_pct=dict(mean=float(100 * np.mean(irms_a / irms_f - 1)), min=float(100 * np.min(irms_a / irms_f - 1)), max=float(100 * np.max(irms_a / irms_f - 1))),
                   hard_switched_edges=dict(fixed_total=int(hf.sum()), adaptive_total=int(ha.sum()), points_with_hard_switching_fixed=int((hf > 0).sum()), points_with_hard_switching_adaptive=int((ha > 0).sum())),
                   nominal_model_rms_prediction_error_pct=dict(mean=float(100 * pred_err.mean()), max_abs=float(100 * np.abs(pred_err).max())),
                   supervisor_decisions=dict(adaptive=sup.n_adaptive, fallback=sup.n_fallback), wall_s=time.time() - t0,
                   caveat="switched simulation with the project's plant; ZVS judged by the charge-based current criterion at the sensed edge; no hardware")
    json.dump(dict(summary=summary, rows=rows), open(os.path.join(RES, "supervisory_study.json"), "w"), indent=1)
    # figure
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    x = np.arange(len(rows)); lab = [f"{r['V1']:.0f}/{r['V2']:.0f}/{r['P_pct']:.0f}%" for r in rows]
    ax[0].bar(x - 0.2, irms_f, 0.4, label="fixed EPS schedule (nominal L)"); ax[0].bar(x + 0.2, irms_a, 0.4, label="adaptive supervisor (estimated L)")
    ax[0].set_ylabel("inductor rms current (A, HV side)"); ax[0].set_xticks(x); ax[0].set_xticklabels(lab, rotation=90, fontsize=6); ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3, axis="y")
    ax[1].bar(x - 0.2, hf, 0.4, label="fixed"); ax[1].bar(x + 0.2, ha, 0.4, label="adaptive"); ax[1].set_ylabel("hard-switched edges per period (of 8)")
    ax[1].set_xticks(x); ax[1].set_xticklabels(lab, rotation=90, fontsize=6); ax[1].legend(fontsize=8); ax[1].grid(alpha=0.3, axis="y")
    fig.suptitle("Supervisory operating-point selection on the switched plant, true L = 0.8 L_nom (simulation)"); fig.tight_layout()
    fig.savefig(os.path.join(RES, "supervisory_study.png"), dpi=130); plt.close(fig)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
