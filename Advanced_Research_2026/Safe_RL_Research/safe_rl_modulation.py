#!/usr/bin/env python3
"""
SIMULATION ONLY - constrained policy search for the DAB steady-state modulation.

Question: can a learned policy choose (phi, D1, D2) for a demanded power at given (V1, V2) with
lower rms inductor current than the project's deterministic PI + EPS voltage matching, without
leaving the hard envelope (peak current, ZVS where feasible, V2 limits)?  Reference optimum: the
analytical TPS search (dabtools.dab.dab_model.tps_search).

Architecture (all deterministic except the seeded exploration noise):
  policy  ->  SAFETY FILTER (analytical model + limits from control_params.json)  ->  PLANT (DABPlant)
                 |  rejects / projects infeasible commands; after N_REJ consecutive rejections
                 v  the deterministic fallback (PI + EPS, DABController) takes over for the episode
Methods:
  M1  CEM (cross-entropy method, derivative-free) over the 115 weights of a residual 3-16-3 tanh policy
      (action = EPS reference + bounded correction), Lagrangian penalty on pre-filter violations.
  M2  constrained REINFORCE with a tabular softmax policy over a discretised (D1, D2) set (25 actions,
      18 context bins), phi solved analytically for the demanded power.
Numpy / scipy only.  Run time: a few minutes on one core (population, generations and periods were shrunk for
the 15-minute budget, see README).
"""
import os, sys, json, math, time, hashlib, platform, importlib, datetime
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DAB = os.path.join(REPO, "SiC_6k6_Industrial_DAB")
sys.path.insert(0, DAB)
from dabtools.dab.dab_model import DABPoint, zvs_current_min, tps_search      # noqa: E402
from dabtools.dab.sim_switched import DABPlant                                # noqa: E402
from dabtools.dab.control import DABController                               # noqa: E402
from dabtools.dab.devices import DEVICES                                     # noqa: E402
import matplotlib                                                            # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                              # noqa: E402

OUT = os.path.join(HERE, "results"); os.makedirs(OUT, exist_ok=True)
T0 = time.time(); SEED = 7
DESIGN = os.path.join(DAB, "04_Design_Calculations", "design_values.json")
CTRL = os.path.join(DAB, "11_Control_Algorithms", "control_params.json")
V = json.load(open(DESIGN)); CP = json.load(open(CTRL))
L, n, fs, P_RATED = V["L"], V["spec"]["n"], V["spec"]["fs"], V["spec"]["P"]
C1, C2 = V["dclink"]["C1"] + 500e-6, V["dclink"]["C2"] + 1000e-6       # bus capacitances as in 05_Simulation
C_par = V["C_par"]; Coss1, Coss2 = DEVICES[V["dev1"]]["Coss_er"], DEVICES[V["dev2"]]["Coss_er"]
I_FILTER = V["I_limit_pk"]            # 24 A: the filter's own peak limit (design value)
I_HARD = CP["limits"]["i_pk_hv"]      # 32 A: hard envelope (hardware trip) - must never be reached
V2_LIM = (CP["limits"]["v2_uv"], CP["limits"]["v2_ov"])
PHI_MAX = math.radians(CP["phi_max_deg"]); D_MIN = 0.4; ZVS_GUARD = 0.5     # A, model-plant mismatch guard
N_REJ = 3
N_SUB_TRAIN, N_SUB_EVAL = 100, 200
PERIODS_TRAIN, PERIODS_EVAL = 30, 60
CONTEXTS = [(V1, V2, f * P_RATED) for V1 in (650.0, 800.0, 850.0) for V2 in (300.0, 400.0, 450.0) for f in (0.5, 1.0)]


def imin1(V1): return zvs_current_min(Coss1, V1, L, C_par)
def imin2(V2): return zvs_current_min(Coss2, n * V2, L, C_par * n ** 2)


# ------------------------------------------------------------------ analytical helpers
def model(V1, V2, phi, D1, D2, N=2000):
    p = DABPoint(V1, V2, n, L, fs, phi, D1, D2, N=N)
    return dict(P=p.P, Irms=p.I_rms1, Ipk=p.I_peak1, m1=p.zvs_margin(1, imin1(V1)), m2=p.zvs_margin(2, imin2(V2)), i0=float(p.i[0]))


def solve_phi(V1, V2, D1, D2, P_dem):
    """phi for the demanded power at given inner duties (bisection on the numerical model)."""
    lo, hi = 0.0, PHI_MAX
    for _ in range(26):
        mid = 0.5 * (lo + hi)
        if model(V1, V2, mid, D1, D2, N=1000)["P"] < P_dem:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def eps_reference(V1, V2, P_dem):
    """The project's deterministic schedule: EPS voltage matching + phi for the demanded power."""
    ctl = DABController(L, n, fs, CP["kp"], CP["ki"])
    D1, D2 = ctl.eps_matching(V1, V2)
    return solve_phi(V1, V2, D1, D2, P_dem), D1, D2


# ------------------------------------------------------------------ safety filter
class SafetyFilter:
    """Deterministic projection of a proposed command onto the validated envelope.

    Checks (analytical model): |P - P_dem| <= 2 %, I_peak <= I_FILTER (24 A), ZVS margin >= ZVS_GUARD at
    every edge of both bridges when ZVS is feasible for the context, phi/D ranges.  A failing command is
    projected: phi re-solved for the power, then (if still infeasible) blended toward the EPS reference
    with the largest feasible blend factor (bisection).  Counts consecutive rejections -> fallback flag."""

    def __init__(self, zvs_feasible):
        self.zvs_feasible = zvs_feasible          # dict context -> bool (from tps_search)
        self.consecutive = 0; self.n_calls = 0; self.n_rejected = 0; self.n_corrected = 0; self.log = []

    def check(self, ctx, a):
        V1, V2, P_dem = ctx; phi, D1, D2 = a
        m = model(V1, V2, phi, D1, D2)
        ok_p = abs(m["P"] - P_dem) <= 0.02 * P_dem
        ok_i = m["Ipk"] <= I_FILTER
        ok_z = (not self.zvs_feasible[ctx]) or (min(m["m1"], m["m2"]) >= ZVS_GUARD)
        return ok_p, ok_i, ok_z, m

    def __call__(self, ctx, proposal, ref):
        V1, V2, P_dem = ctx; self.n_calls += 1
        phi = min(max(proposal[0], 0.0), PHI_MAX); D1 = min(max(proposal[1], D_MIN), 1.0); D2 = min(max(proposal[2], D_MIN), 1.0)
        clipped = (phi, D1, D2) != tuple(proposal)
        ok_p, ok_i, ok_z, m = self.check(ctx, (phi, D1, D2))
        reason = []
        if ok_p and ok_i and ok_z and not clipped:
            self.consecutive = 0
            return (phi, D1, D2), dict(rejected=False, corrected=False, reason=reason, pre=m)
        pre = m
        if not ok_p:
            reason.append("power")
        if not ok_i:
            reason.append("peak")
        if not ok_z:
            reason.append("zvs")
        if clipped:
            reason.append("range")
        # projection 1: power-matching phi at the proposed duties
        phi2 = solve_phi(V1, V2, D1, D2, P_dem)
        ok_p, ok_i, ok_z, m = self.check(ctx, (phi2, D1, D2))
        if ok_p and ok_i and ok_z:
            self.n_corrected += 1
            self.consecutive = 0 if reason == ["power"] else self.consecutive     # a pure power correction is not a rejection
            if reason != ["power"]:
                self.n_rejected += 1; self.consecutive += 1
            return (phi2, D1, D2), dict(rejected=reason != ["power"], corrected=True, reason=reason, pre=pre)
        # projection 2: blend the duties toward the EPS reference, largest feasible alpha
        self.n_rejected += 1; self.consecutive += 1
        lo, hi = 0.0, 1.0; best = ref
        for _ in range(7):
            al = 0.5 * (lo + hi)
            d1 = ref[1] + al * (D1 - ref[1]); d2 = ref[2] + al * (D2 - ref[2])
            ph = solve_phi(V1, V2, d1, d2, P_dem)
            ok_p, ok_i, ok_z, m = self.check(ctx, (ph, d1, d2))
            if ok_p and ok_i and ok_z:
                lo = al; best = (ph, d1, d2)
            else:
                hi = al
        return best, dict(rejected=True, corrected=True, reason=reason + ["projected"], pre=pre)


class PassThrough(SafetyFilter):
    """Range clipping only - used to evaluate the deterministic references (PI+EPS, TPS) as they are."""

    def __call__(self, ctx, proposal, ref):
        phi = min(max(proposal[0], 0.0), PHI_MAX); d1 = min(max(proposal[1], D_MIN), 1.0); d2 = min(max(proposal[2], D_MIN), 1.0)
        self.n_calls += 1
        return (phi, d1, d2), dict(rejected=False, corrected=False, reason=[], pre=None)


# ------------------------------------------------------------------ plant episodes
def battery_load(V2set, R_int=0.05):
    return lambda v2, t: (v2 - V2set) / R_int


def run_episode(ctx, act_fn, periods, N_sub, filt, ref, fallback=True, query_every_period=True):
    """act_fn(v1, v2, P_dem) -> proposal.  The policy is queried every period (evaluation) or once at the start
    (training, query_every_period=False: the policy is deterministic and the context fixed, so repeated queries would
    be identical - this saves one analytical-model evaluation per period); the filter projects the proposal;
    after N_REJ consecutive rejections the deterministic fallback (EPS reference) is used for the rest."""
    V1, V2, P_dem = ctx
    plant = DABPlant(L, n, fs, C1, C2, V1, 0.3, battery_load(V2), N_sub=N_sub); plant.v2 = V2
    filt.consecutive = 0
    a0, info0 = filt(ctx, act_fn(V1, V2, P_dem), ref)
    plant.iL = model(V1, V2, *a0)["i0"]            # start near the analytical steady state (no DC offset transient)
    in_fallback = False; rec = None; rejected = int(info0["rejected"])
    for k in range(periods):
        if in_fallback:
            a = ref
        elif not query_every_period:
            a = a0
        else:
            a, info = filt((plant.v1, plant.v2, P_dem), act_fn(plant.v1, plant.v2, P_dem), ref)
            rejected += int(info["rejected"])
            if fallback and filt.consecutive >= N_REJ:
                in_fallback = True; a = ref
        rec = plant.run_period(*a, record=(k == periods - 1))
    r = np.array(rec)
    va, vb, iL, v1, v2 = r[:, 1], r[:, 2], r[:, 3], r[:, 4], r[:, 5]
    out = dict(P=float(np.mean(va * iL)), Irms=float(np.sqrt(np.mean(iL ** 2))), Ipk=float(np.max(np.abs(iL))),
               v2_min=float(v2.min()), v2_max=float(v2.max()), action=[float(x) for x in a], fallback=in_fallback, rejected=rejected)
    # ZVS edges on the plant waveform (same sign convention as DABPoint.switching_currents)
    edges = []
    for port, v, Vdc in ((1, va, V1), (2, vb, V2)):
        dv = np.diff(np.concatenate([v, v[:1]])); idx = np.nonzero(np.abs(dv) > 1.0)[0]
        im = imin1(V1) if port == 1 else imin2(V2)
        for kk in idx:
            s = -1.0 if dv[kk] > 0 else 1.0
            if port == 2:
                s = -s
            edges.append(s * iL[(kk + 1) % len(iL)] - im)
    out["zvs_edges"] = int(sum(1 for e in edges if e > 0)); out["edges"] = len(edges); out["zvs_margin_min"] = float(min(edges))
    return out


# ------------------------------------------------------------------ policies
class ResidualPolicy:
    """3-16-3 tanh MLP; action = EPS reference + (20 deg, 0.5, 0.5) * tanh(output)."""
    nin, nh, nout = 3, 16, 3
    size = nin * nh + nh + nh * nout + nout

    def __init__(self, theta, refs):
        self.W1 = theta[:48].reshape(3, 16); self.b1 = theta[48:64]; self.W2 = theta[64:112].reshape(16, 3); self.b2 = theta[112:115]
        self.refs = refs

    def __call__(self, V1, V2, P_dem):
        x = np.array([(V1 - 750) / 100, (V2 - 375) / 75, P_dem / P_RATED - 0.75])
        y = np.tanh(np.tanh(x @ self.W1 + self.b1) @ self.W2 + self.b2)
        ref = self.refs(V1, V2, P_dem)
        return (ref[0] + math.radians(20) * y[0], ref[1] + 0.5 * y[1], ref[2] + 0.5 * y[2])


def main():
    rng = np.random.default_rng(SEED)
    res = dict(contexts=CONTEXTS, limits=dict(I_filter=I_FILTER, I_hard=I_HARD, V2=V2_LIM, phi_max_deg=CP["phi_max_deg"], zvs_guard_A=ZVS_GUARD, N_rej=N_REJ))
    # ---- references: EPS schedule and analytical TPS optimum per context
    print("references ...", flush=True)
    REF, TPS, feas = {}, {}, {}
    for ctx in CONTEXTS:
        V1, V2, P_dem = ctx
        REF[ctx] = eps_reference(V1, V2, P_dem)
        best, sps = tps_search(V1, V2, n, L, fs, P_dem, Coss1, Coss2, grid=9, N=2000)
        feas[ctx] = best is not None
        if best is not None:
            # re-solve phi for the exact power at the optimal duties (tps_search stops at 0.2 % power tolerance)
            TPS[ctx] = (solve_phi(V1, V2, best.D1, best.D2, P_dem), best.D1, best.D2)
        else:
            TPS[ctx] = REF[ctx]
    res["zvs_feasible"] = {f"{c[0]:.0f}/{c[1]:.0f}/{c[2]:.0f}": feas[c] for c in CONTEXTS}
    print("  ZVS-feasible contexts:", sum(feas.values()), "/", len(CONTEXTS))
    # validated anchor for the filter's projection and for the fallback: the EPS schedule when it passes the
    # filter's own check, otherwise the analytical TPS table point (deterministic rule, see README)
    ANCHOR = {}; anchor_src = {}
    for ctx in CONTEXTS:
        okp, oki, okz, _ = SafetyFilter(feas).check(ctx, REF[ctx])
        ANCHOR[ctx] = REF[ctx] if (okp and oki and okz) else TPS[ctx]
        anchor_src[f"{ctx[0]:.0f}/{ctx[1]:.0f}/{ctx[2]:.0f}"] = "EPS" if (okp and oki and okz) else "TPS (EPS fails the filter check)"
    res["anchor_source"] = anchor_src
    print("  anchors:", {k: v[:3] for k, v in anchor_src.items() if v != "EPS"}, flush=True)

    def ref_fn(V1, V2, P_dem):
        # nearest tabulated context (the references were computed on the context grid; during the transient
        # test the measured voltages drift by < 1 % so the nearest-context reference is adequate)
        c = min(CONTEXTS, key=lambda c: ((c[0] - V1) / 100) ** 2 + ((c[1] - V2) / 75) ** 2 + ((c[2] - P_dem) / P_RATED) ** 2)
        return REF[c]

    def ctx_key(ctx):
        return min(CONTEXTS, key=lambda c: ((c[0] - ctx[0]) / 100) ** 2 + ((c[1] - ctx[1]) / 75) ** 2 + ((c[2] - ctx[2]) / P_RATED) ** 2)

    class Feas(dict):
        def __missing__(self, k):
            return feas[ctx_key(k)]
    feas_map = Feas(feas)

    # ---- M1: CEM with Lagrangian penalty ------------------------------------------------------
    print("M1 CEM ...")
    POP, ELITE, GENS = 16, 4, 20
    mu = np.zeros(ResidualPolicy.size); sig = 0.3 * np.ones(ResidualPolicy.size); lam = 1.0
    hist = []
    # fitness evaluation uses one filter call per context (steady-state task) -> the pre-filter violation is the
    # constraint signal; the plant is run for PERIODS_TRAIN periods with the filtered command
    def fitness(theta):
        pol = ResidualPolicy(theta, ref_fn); filt = SafetyFilter(feas_map)
        J, viol, fb = 0.0, 0.0, 0
        for ctx in CONTEXTS:
            o = run_episode(ctx, pol, PERIODS_TRAIN, N_SUB_TRAIN, filt, ANCHOR[ctx], query_every_period=False)
            J += o["Irms"] / ref_eval[ctx]["Irms"]
            viol += o["rejected"]; fb += int(o["fallback"])
        return J / len(CONTEXTS), viol / len(CONTEXTS), fb
    ref_eval = {ctx: run_episode(ctx, lambda a, b, c, r=REF[ctx]: r, PERIODS_TRAIN, N_SUB_TRAIN, PassThrough(feas_map), REF[ctx]) for ctx in CONTEXTS}
    best_theta, best_J = mu.copy(), 1e9
    for g in range(GENS):
        thetas = mu + sig * rng.standard_normal((POP, ResidualPolicy.size))
        scores = []
        for th in thetas:
            J, viol, fb = fitness(th)
            scores.append((J + lam * viol + 0.5 * fb, J, viol, fb))
        scores = np.array(scores); order = np.argsort(scores[:, 0])
        elite = thetas[order[:ELITE]]
        mu = elite.mean(0); sig = 0.7 * elite.std(0) + 0.3 * sig * 0.9 + 1e-3
        lam = max(0.0, lam + 2.0 * (scores[:, 2].mean() - 0.02))     # dual ascent: drives pre-filter violations below 2 %
        if scores[order[0], 2] == 0 and scores[order[0], 1] < best_J:
            best_J = scores[order[0], 1]; best_theta = thetas[order[0]].copy()
        hist.append(dict(gen=g, best=float(scores[order[0], 0]), best_J=float(scores[order[0], 1]), mean_J=float(scores[:, 1].mean()),
                         mean_viol=float(scores[:, 2].mean()), fallbacks=int(scores[:, 3].sum()), lam=float(lam)))
        print(f"  gen {g:2d} best J={scores[order[0], 1]:.4f} viol={scores[order[0], 2]:.3f} mean viol={scores[:, 2].mean():.3f} lam={lam:.2f} fallbacks={int(scores[:, 3].sum())}  t={time.time() - T0:.0f}s", flush=True)
    if best_J > 1e8:          # no violation-free candidate found: take the CEM mean
        best_theta = mu
    res["M1_cem"] = dict(population=POP, elite=ELITE, generations=GENS, policy_params=int(ResidualPolicy.size), history=hist,
                         episodes_run=POP * GENS * len(CONTEXTS), best_J_train=float(best_J))
    np.save(os.path.join(OUT, "m1_policy_theta.npy"), best_theta)
    pol1 = ResidualPolicy(best_theta, ref_fn)

    # ---- M2: constrained REINFORCE over a discrete (D1, D2) set -------------------------------
    print("M2 REINFORCE ...", flush=True)
    DSET = [0.6, 0.7, 0.8, 0.9, 1.0]; ACTIONS = [(d1, d2) for d1 in DSET for d2 in DSET]
    ITERS, ALPHA = 60, 0.5
    logits = np.zeros((len(CONTEXTS), len(ACTIONS))); lam2 = 1.0; baseline = np.zeros(len(CONTEXTS)); hist2 = []
    phi_cache = {}

    def act_from_index(ctx, ai):
        d1, d2 = ACTIONS[ai]
        key = (ctx, ai)
        if key not in phi_cache:
            phi_cache[key] = solve_phi(ctx[0], ctx[1], d1, d2, ctx[2])
        return (phi_cache[key], d1, d2)
    for it in range(ITERS):
        viol_it = 0.0; R_it = 0.0
        for ci, ctx in enumerate(CONTEXTS):
            p = np.exp(logits[ci] - logits[ci].max()); p /= p.sum()
            ai = rng.choice(len(ACTIONS), p=p)
            a = act_from_index(ctx, ai); filt = SafetyFilter(feas_map)
            o = run_episode(ctx, lambda v1, v2, pd, a=a: a, PERIODS_TRAIN, N_SUB_TRAIN, filt, ANCHOR[ctx], query_every_period=False)
            viol = o["rejected"]
            R = -o["Irms"] / ref_eval[ctx]["Irms"] - lam2 * viol
            adv = R - baseline[ci]; baseline[ci] += 0.1 * adv
            grad = -p; grad[ai] += 1.0
            logits[ci] += ALPHA * adv * grad
            viol_it += viol; R_it += R
        lam2 = max(0.0, lam2 + 2.0 * (viol_it / len(CONTEXTS) - 0.02))
        hist2.append(dict(iter=it, mean_R=R_it / len(CONTEXTS), mean_viol=viol_it / len(CONTEXTS), lam=lam2))
    greedy2 = {ctx: act_from_index(ctx, int(np.argmax(logits[ci]))) for ci, ctx in enumerate(CONTEXTS)}
    res["M2_reinforce"] = dict(actions=ACTIONS, iterations=ITERS, lr=ALPHA, history=hist2, episodes_run=ITERS * len(CONTEXTS),
                               greedy_actions={f"{c[0]:.0f}/{c[1]:.0f}/{c[2]:.0f}": [float(x) for x in a] for c, a in greedy2.items()})
    np.save(os.path.join(OUT, "m2_logits.npy"), logits)

    def pol2(V1, V2, P_dem):
        return greedy2[ctx_key((V1, V2, P_dem))]

    # ---- evaluation on the plant (N_sub = 200, 60 periods, policy queried every period) ----------
    print("evaluation ...", flush=True)
    methods = {"PI_EPS": lambda V1, V2, Pd: ref_fn(V1, V2, Pd), "TPS_analytical": lambda V1, V2, Pd: TPS[ctx_key((V1, V2, Pd))],
               "M1_CEM": pol1, "M2_REINFORCE": pol2}
    table = []; viol_total = {k: 0 for k in methods}; filt_stats = {}
    for mk, fn in methods.items():
        filt = SafetyFilter(feas_map) if mk.startswith("M") else PassThrough(feas_map)      # references are evaluated as they are
        for ctx in CONTEXTS:
            o = run_episode(ctx, fn, PERIODS_EVAL, N_SUB_EVAL, filt, ANCHOR[ctx])
            hard = dict(peak_gt_32A=o["Ipk"] > I_HARD, v2_out_of_limits=not (V2_LIM[0] <= o["v2_min"] and o["v2_max"] <= V2_LIM[1]),
                        hard_switch_where_feasible=feas[ctx] and o["zvs_edges"] < o["edges"], power_error_gt_3pct=abs(o["P"] - ctx[2]) > 0.03 * ctx[2])
            o.update(method=mk, V1=ctx[0], V2=ctx[1], P_dem=ctx[2], zvs_feasible=feas[ctx], hard_violations=int(sum(hard.values())), hard=hard)
            viol_total[mk] += o["hard_violations"]; table.append(o)
        filt_stats[mk] = dict(calls=filt.n_calls, rejected=filt.n_rejected, corrected=filt.n_corrected)
    res["evaluation"] = table; res["hard_violations_total"] = viol_total; res["filter_stats_eval"] = filt_stats
    # unfiltered check (diagnostic only): what would the raw policy proposals do on the plant?
    raw = {}
    for mk in ("M1_CEM", "M2_REINFORCE"):
        fn = methods[mk]; bad = 0; pk = 0.0
        for ctx in CONTEXTS:
            o = run_episode(ctx, fn, PERIODS_EVAL, N_SUB_EVAL, PassThrough(feas_map), ANCHOR[ctx], fallback=False)
            bad += int(o["Ipk"] > I_HARD) + int(feas[ctx] and o["zvs_edges"] < o["edges"]) + int(abs(o["P"] - ctx[2]) > 0.03 * ctx[2]); pk = max(pk, o["Ipk"])
        raw[mk] = dict(violations_without_filter=bad, max_peak_A=pk)
    res["diagnostic_unfiltered"] = raw

    # summary per method
    summ = {}
    for mk in methods:
        rows = [r for r in table if r["method"] == mk]
        summ[mk] = dict(mean_Irms=float(np.mean([r["Irms"] for r in rows])), mean_Irms_rel_PI=float(np.mean([r["Irms"] for r in rows]) / np.mean([r["Irms"] for r in table if r["method"] == "PI_EPS"])),
                        max_Ipk=float(max(r["Ipk"] for r in rows)), zvs_edges=int(sum(r["zvs_edges"] for r in rows)), edges=int(sum(r["edges"] for r in rows)),
                        hard_violations=viol_total[mk], fallbacks=int(sum(r["fallback"] for r in rows)), mean_abs_P_err_pct=float(np.mean([100 * abs(r["P"] - r["P_dem"]) / r["P_dem"] for r in rows])))
    res["summary"] = summ

    # ---- transient test: 50 -> 100 % load step at 800/400 V, CV mode (PI), D from EPS vs from the M1 policy
    print("transient ...", flush=True)
    def transient(use_policy):
        R_full = 400 ** 2 / P_RATED
        plant = DABPlant(L, n, fs, C1, C2, 800.0, 0.3, lambda v2, t: v2 / (R_full if t >= 0.002 else 2 * R_full), N_sub=N_SUB_EVAL); plant.v2 = 400.0
        ctl = DABController(L, n, fs, CP["kp"], CP["ki"], P_max=1.1 * P_RATED); ctl.state = "RUN"; ctl.ss_scale = 1.0
        ctl.pi.integ = 0.5 * P_RATED
        filt = SafetyFilter(feas_map); t_l, v2_l, ipk_l, fbk = [], [], [], 0
        for k in range(600):
            m = dict(v1=plant.v1, v2=plant.v2, i_pk=plant.ipk, T=40, precharge_ok=True)
            phi, D1, D2 = ctl.step(m)
            if use_policy:
                P_cmd = ctl.log[-1][1]
                ref = (phi, D1, D2)
                if filt.consecutive < N_REJ:
                    a, info = filt((plant.v1, plant.v2, max(P_cmd, 0.05 * P_RATED)), pol1(plant.v1, plant.v2, max(P_cmd, 0.05 * P_RATED)), ref)
                    phi, D1, D2 = a
                else:
                    fbk += 1
            plant.run_period(phi, D1, D2)
            t_l.append(plant.t); v2_l.append(plant.v2); ipk_l.append(plant.ipk)
        t = np.array(t_l); v2 = np.array(v2_l); ipk = np.array(ipk_l)
        seg = t >= 0.002
        settle = next((tt for tt, vv in zip(t[seg], v2[seg]) if abs(vv - 400) < 2 and all(abs(v2[(t >= tt) & seg] - 400) < 2)), None)
        return dict(dip_V=float(400 - v2[seg].min()), settle_ms=None if settle is None else float((settle - 0.002) * 1e3), max_ipk=float(ipk[seg].max()),
                    fallback_periods=fbk, filter_rejected=filt.n_rejected, filter_calls=filt.n_calls), t, v2, ipk
    tr_pi, t_a, v2_a, ipk_a = transient(False); tr_rl, t_b, v2_b, ipk_b = transient(True)
    res["transient_load_step"] = dict(PI_EPS=tr_pi, PI_with_M1_duties=tr_rl, note="CV mode, 800/400 V, 50->100 % resistive step at 2 ms; phi from the PI, duties from EPS or from the M1 policy through the filter")

    # ---- figures
    fig, ax = plt.subplots(1, 3, figsize=(14, 4.2))
    x = np.arange(len(CONTEXTS)); w = 0.2
    for i, mk in enumerate(methods):
        rows = [r for r in table if r["method"] == mk]
        ax[0].bar(x + (i - 1.5) * w, [r["Irms"] for r in rows], w, label=mk)
        ax[1].bar(x + (i - 1.5) * w, [r["Ipk"] for r in rows], w, label=mk)
    ax[0].set_xticks(x); ax[0].set_xticklabels([f"{c[0]:.0f}/{c[1]:.0f}\n{c[2] / 1e3:.1f}kW" for c in CONTEXTS], fontsize=6, rotation=90)
    ax[1].set_xticks(x); ax[1].set_xticklabels([f"{c[0]:.0f}/{c[1]:.0f}\n{c[2] / 1e3:.1f}kW" for c in CONTEXTS], fontsize=6, rotation=90)
    ax[0].set_ylabel("I_rms HV-referred (A)"); ax[0].set_title("rms inductor current on the plant"); ax[0].legend(fontsize=7); ax[0].grid(alpha=0.3, axis="y")
    ax[1].axhline(I_HARD, color="r", ls="--", label="hard limit 32 A"); ax[1].axhline(I_FILTER, color="orange", ls=":", label="filter limit 24 A")
    ax[1].set_ylabel("I_peak (A)"); ax[1].set_title("peak current (plant)"); ax[1].legend(fontsize=7); ax[1].grid(alpha=0.3, axis="y")
    ax[2].plot([h["gen"] for h in hist], [h["best_J"] for h in hist], "o-", label="M1 best J (I_rms / I_rms,PI)")
    ax[2].plot([h["gen"] for h in hist], [h["mean_viol"] for h in hist], "s-", label="M1 mean pre-filter violation rate")
    ax[2].plot([h["iter"] * GENS / ITERS for h in hist2], [-h["mean_R"] for h in hist2], "-", alpha=0.7, label="M2 -mean reward (iter rescaled)")
    ax[2].set_xlabel("generation"); ax[2].set_title("learning curves"); ax[2].legend(fontsize=7); ax[2].grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_rl_vs_analytical.png"), dpi=130); plt.close(fig)
    fig, ax = plt.subplots(2, 1, figsize=(7, 5), sharex=True)
    ax[0].plot(t_a * 1e3, v2_a, label="PI + EPS"); ax[0].plot(t_b * 1e3, v2_b, label="PI + M1 duties (filtered)"); ax[0].set_ylabel("V2 (V)"); ax[0].legend(); ax[0].grid(alpha=0.3)
    ax[1].plot(t_a * 1e3, ipk_a); ax[1].plot(t_b * 1e3, ipk_b); ax[1].axhline(I_HARD, color="r", ls="--"); ax[1].set_ylabel("|i_L| peak per period (A)"); ax[1].set_xlabel("t (ms)"); ax[1].grid(alpha=0.3)
    fig.suptitle("Load step 50 -> 100 % at 800/400 V (simulation)"); fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_transient.png"), dpi=130); plt.close(fig)

    # ---- tables
    lines = ["| method | mean I_rms (A) | rel. to PI+EPS | max I_peak (A) | ZVS edges | hard violations (post-filter) | fallbacks | mean |P err| (%) |", "|---|---|---|---|---|---|---|---|"]
    for mk, s in summ.items():
        lines.append(f"| {mk} | {s['mean_Irms']:.3f} | {s['mean_Irms_rel_PI']:.4f} | {s['max_Ipk']:.2f} | {s['zvs_edges']}/{s['edges']} | {s['hard_violations']} | {s['fallbacks']} | {s['mean_abs_P_err_pct']:.2f} |")
    lines += ["", "| V1/V2/P | ZVS feasible | " + " | ".join(f"{mk} I_rms / ZVS / (phi deg, D1, D2)" for mk in methods) + " |", "|---|---|" + "---|" * len(methods)]
    for ctx in CONTEXTS:
        cells = []
        for mk in methods:
            r = next(r for r in table if r["method"] == mk and (r["V1"], r["V2"], r["P_dem"]) == ctx)
            cells.append(f"{r['Irms']:.2f} A / {r['zvs_edges']}/{r['edges']} / ({math.degrees(r['action'][0]):.1f}, {r['action'][1]:.2f}, {r['action'][2]:.2f})")
        lines.append(f"| {ctx[0]:.0f}/{ctx[1]:.0f}/{ctx[2] / 1e3:.1f} kW | {feas[ctx]} | " + " | ".join(cells) + " |")
    lines += ["", f"Transient (50->100 % step): PI+EPS dip {tr_pi['dip_V']:.2f} V, settle {tr_pi['settle_ms']} ms, max peak {tr_pi['max_ipk']:.1f} A; "
              f"PI + M1 duties: dip {tr_rl['dip_V']:.2f} V, settle {tr_rl['settle_ms']} ms, max peak {tr_rl['max_ipk']:.1f} A, filter rejected {tr_rl['filter_rejected']}/{tr_rl['filter_calls']}, fallback periods {tr_rl['fallback_periods']}."]
    open(os.path.join(OUT, "results_table.md"), "w").write("\n".join(lines) + "\n")
    res["wall_time_s"] = time.time() - T0
    json.dump(res, open(os.path.join(OUT, "rl_results.json"), "w"), indent=1, default=str)

    def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()

    def git_commit():
        try:
            head = open(os.path.join(REPO, ".git", "HEAD")).read().strip()
            if head.startswith("ref: "):
                ref = head[5:]; p = os.path.join(REPO, ".git", ref)
                if os.path.exists(p):
                    return open(p).read().strip()
                for line in open(os.path.join(REPO, ".git", "packed-refs")):
                    if line.strip().endswith(ref):
                        return line.split()[0]
            return head
        except Exception:
            return "unknown"
    inputs = [DESIGN, CTRL] + [os.path.join(DAB, "dabtools", "dab", f) for f in ("dab_model.py", "sim_switched.py", "control.py", "devices.py")] + [__file__]
    prov = dict(script=os.path.relpath(__file__, REPO), generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), python=platform.python_version(),
                platform=platform.platform(), packages={m: importlib.import_module(m).__version__ for m in ("numpy", "scipy", "matplotlib")}, git_commit=git_commit(),
                input_sha256={os.path.relpath(p, REPO): sha(p) for p in inputs}, seeds=dict(global_seed=SEED), wall_time_s=time.time() - T0,
                settings=dict(N_sub_train=N_SUB_TRAIN, N_sub_eval=N_SUB_EVAL, periods_train=PERIODS_TRAIN, periods_eval=PERIODS_EVAL, contexts=len(CONTEXTS)),
                outputs=sorted(os.listdir(OUT)))
    json.dump(prov, open(os.path.join(HERE, "provenance.json"), "w"), indent=1)
    print(json.dumps(summ, indent=1)); print("transient:", json.dumps(res["transient_load_step"], indent=1)); print(f"done in {time.time() - T0:.0f} s")


if __name__ == "__main__":
    main()
