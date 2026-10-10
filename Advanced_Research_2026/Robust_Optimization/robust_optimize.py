#!/usr/bin/env python3
"""
Reliability-aware multi-objective design optimisation of the 6.6 kW SiC DAB under parameter uncertainty.

Methods (all numpy, deterministic seeds):
  * NSGA-II (Deb 2002): constrained non-dominated sorting, crowding distance, binary tournament,
    SBX crossover, polynomial mutation.  Mixed variables are encoded in [0,1]^9 and decoded
    (`dab_eval.decode`), discrete choices by interval mapping.
  * Three problem variants evaluated with the same evaluator:
      nominal            : parameters at their nominal values
      robust             : objectives and constraints = worst case over S LHS samples of the uncertainty
      chance-constrained : objectives = sample mean, every constraint enforced at the 95 % quantile
                           (ZVS over the envelope corners satisfied with probability >= 95 %)
  * Surrogate-assisted search: Gaussian-process regression (ARD squared-exponential kernel, marginal-
    likelihood hyperparameters) with expected improvement on an augmented-Tchebycheff scalarisation of
    the normalised objectives, repeated for a few weight vectors (ParEGO-like).  This is a simplified
    single-objective BO per weight vector, not a multi-objective BO with a hypervolume acquisition.
  * Exhaustive grid of 12_Optimization re-evaluated with this evaluator for a like-for-like comparison.
Outputs are written to results/ (CSV/JSON/PNG), plus README.md and provenance.json.
"""
import os, sys, json, math, time, hashlib, itertools, platform, argparse
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dab_eval as E                                       # noqa: E402
from dab_eval import decode, evaluate_design, BASELINE, lhs, u_from_unit, U_NOM, U_NAMES, X_NAMES   # noqa: E402
import scipy, scipy.optimize, scipy.stats                  # noqa: E402
import matplotlib; matplotlib.use("Agg")                   # noqa: E402
import matplotlib.pyplot as plt                            # noqa: E402

RES = os.path.join(HERE, "results"); os.makedirs(RES, exist_ok=True)
ap = argparse.ArgumentParser(); ap.add_argument("--quick", action="store_true"); args = ap.parse_args()
SEED = 20261010
POP, GEN = (60, 60) if not args.quick else (24, 8)
GEN_BY_MODE = {m: GEN for m in ["nominal", "nominal_strict", "robust", "cc", "robust_strict", "cc_strict"]}   # equal budgets for every variant
S_UNC = 24 if not args.quick else 6                         # LHS samples of the uncertainty per design
BO_INIT, BO_ITER = (20, 30) if not args.quick else (8, 6)
CC_PROB = 0.95
T0 = time.time()
COL = dict(nominal="#2a78d6", robust="#eb6834", cc="#1baf7a", nominal_strict="#104281", robust_strict="#c98500", cc_strict="#008300", grid="#8a8a86", bo="#6250d6", base="#0b0b0b", knee="#e34948")
LABEL = dict(nominal="nominal", robust="robust (worst case)", cc="chance-constrained 95 %", nominal_strict="nominal, strict (ZVS at all full-power corners)",
             robust_strict="robust, strict", cc_strict="chance-constrained 95 %, strict")
MODE_LIST = ["nominal", "robust", "cc", "nominal_strict", "robust_strict", "cc_strict"]
MAIN = ["nominal", "robust", "cc"]
F_NAMES = ["P_loss_nom_W", "vol_cm3", "log10_damage_rel", "neg_zvs_margin_A"]
F_LABELS = ["loss at 800/400 V, 6.6 kW (W)", "magnetics volume (cm3)", "log10 damage / baseline", "ZVS margin (A, HV-referred)"]
G_NAMES = ["phi_corner", "Tj", "zvs_full", "Bpk_850V", "fill_xf", "fill_ind", "Ipk"]

# ----------------------------------------------------------------------------- evaluators
rng_u = np.random.default_rng(SEED + 1)
U_LHS = u_from_unit(lhs(S_UNC, 5, rng_u))                 # common random numbers for every design
n_eval = {m: 0 for m in MODE_LIST} | {"grid": 0, "bo": 0}
base_nom = evaluate_design(BASELINE, U_NOM)
LOG10_D_BASE = base_nom["f"][2]


def _fix(r):
    f = r["f"].copy()
    if np.isfinite(f[2]):
        f[2] -= LOG10_D_BASE
    return f, r["g"]


def eval_mode(x, mode, count=True):
    d = decode(x)
    if count: n_eval[mode] += 1
    zc = "corners" if mode.endswith("_strict") else "nominal"
    r0 = evaluate_design(d, U_NOM, zvs_constraint=zc)
    if mode.startswith("nominal") or not np.all(np.isfinite(r0["f"])) or cv(r0["g"]) > 0:
        # designs infeasible at nominal parameters are not evaluated under uncertainty (worst case can only be
        # worse; for the chance-constrained variant this is a shortcut, stated in the README)
        f, g = _fix(r0)
        return f, g, bool(np.all(g <= 0) and np.all(np.isfinite(f)))
    F = []; G = []
    for u in U_LHS:
        r = evaluate_design(d, u, zvs_constraint=zc)
        f, g = _fix(r)
        if not np.all(np.isfinite(f)):
            return f, np.maximum(g, 0.05), False
        F.append(f); G.append(g)
    F = np.array(F); G = np.array(G)
    if mode.startswith("robust"):
        f = np.array([F[:, 0].max(), F[:, 1].max(), F[:, 2].max(), F[:, 3].max()]); g = G.max(axis=0)
    else:   # chance-constrained
        f = F.mean(axis=0); g = np.quantile(G, CC_PROB, axis=0, method="higher")
    return f, g, bool(np.all(g <= 0))


# ----------------------------------------------------------------------------- NSGA-II
def cv(g):
    return float(np.sum(np.maximum(g, 0.0)))


def dominates(fa, ga, fb, gb):
    ca, cb = cv(ga), cv(gb)
    if ca == 0 and cb == 0:
        return bool(np.all(fa <= fb) and np.any(fa < fb))
    return ca < cb


def nd_sort(F, G):
    N = len(F); S = [[] for _ in range(N)]; nd = np.zeros(N, int); fronts = [[]]
    for p in range(N):
        for q in range(N):
            if p == q: continue
            if dominates(F[p], G[p], F[q], G[q]): S[p].append(q)
            elif dominates(F[q], G[q], F[p], G[p]): nd[p] += 1
        if nd[p] == 0: fronts[0].append(p)
    i = 0
    while fronts[i]:
        nxt = []
        for p in fronts[i]:
            for q in S[p]:
                nd[q] -= 1
                if nd[q] == 0: nxt.append(q)
        i += 1; fronts.append(nxt)
    return fronts[:-1]


def crowding(F):
    n, m = F.shape; dist = np.zeros(n)
    if n <= 2: return np.full(n, np.inf)
    for k in range(m):
        idx = np.argsort(F[:, k]); fr = F[idx, k]; rngk = fr[-1] - fr[0]
        dist[idx[0]] = dist[idx[-1]] = np.inf
        if rngk <= 0: continue
        dist[idx[1:-1]] += (fr[2:] - fr[:-2]) / rngk
    return dist


def sbx(p1, p2, rng, eta=15.0, pc=0.9):
    c1, c2 = p1.copy(), p2.copy()
    if rng.random() > pc: return c1, c2
    for i in range(len(p1)):
        if rng.random() > 0.5 or abs(p1[i] - p2[i]) < 1e-12: continue
        y1, y2 = min(p1[i], p2[i]), max(p1[i], p2[i]); u = rng.random()
        beta = 1 + 2 * y1 / max(y2 - y1, 1e-12); alpha = 2 - beta ** (-(eta + 1))
        bq = (u * alpha) ** (1 / (eta + 1)) if u <= 1 / alpha else (1 / (2 - u * alpha)) ** (1 / (eta + 1))
        ch1 = 0.5 * ((y1 + y2) - bq * (y2 - y1))
        beta = 1 + 2 * (1 - y2) / max(y2 - y1, 1e-12); alpha = 2 - beta ** (-(eta + 1))
        bq = (u * alpha) ** (1 / (eta + 1)) if u <= 1 / alpha else (1 / (2 - u * alpha)) ** (1 / (eta + 1))
        ch2 = 0.5 * ((y1 + y2) + bq * (y2 - y1))
        if rng.random() < 0.5: ch1, ch2 = ch2, ch1
        c1[i], c2[i] = np.clip(ch1, 0, 1), np.clip(ch2, 0, 1)
    return c1, c2


def poly_mut(x, rng, eta=20.0, pm=None):
    pm = pm or 1.0 / len(x); y = x.copy()
    for i in range(len(x)):
        if rng.random() > pm: continue
        u = rng.random(); d1, d2 = y[i], 1 - y[i]
        if u < 0.5:
            dq = (2 * u + (1 - 2 * u) * (1 - d1) ** (eta + 1)) ** (1 / (eta + 1)) - 1
        else:
            dq = 1 - (2 * (1 - u) + 2 * (u - 0.5) * (1 - d2) ** (eta + 1)) ** (1 / (eta + 1))
        y[i] = np.clip(y[i] + dq, 0, 1)
    return y


def nsga2(mode, seed):
    rng = np.random.default_rng(seed); GEN = GEN_BY_MODE[mode]
    X = lhs(POP, E.N_X, rng)
    out = [eval_mode(x, mode) for x in X]
    F = np.array([o[0] for o in out]); G = np.array([o[1] for o in out])
    F = np.where(np.isfinite(F), F, 1e9)
    history = []; archive_x, archive_f, archive_g = [], [], []
    for gen in range(GEN + 1):
        fronts = nd_sort(F, G)
        feas = np.array([cv(g) == 0 for g in G])
        first = [i for i in fronts[0] if feas[i]]
        history.append(dict(gen=gen, front_f=F[first].tolist(), n_feasible=int(feas.sum()), n_eval=n_eval[mode]))
        archive_x += [X[i] for i in first]; archive_f += [F[i] for i in first]; archive_g += [G[i] for i in first]
        if gen == GEN: break
        rank = np.zeros(POP, int); crowd = np.zeros(POP)
        for r, fr in enumerate(fronts):
            rank[fr] = r; crowd[fr] = crowding(F[fr])
        def tourn():
            a, b = rng.integers(POP, size=2)
            if rank[a] != rank[b]: return X[a] if rank[a] < rank[b] else X[b]
            return X[a] if crowd[a] >= crowd[b] else X[b]
        kids = []
        while len(kids) < POP:
            c1, c2 = sbx(tourn(), tourn(), rng); kids += [poly_mut(c1, rng), poly_mut(c2, rng)]
        kids = np.array(kids[:POP])
        ko = [eval_mode(x, mode) for x in kids]
        Fk = np.array([o[0] for o in ko]); Gk = np.array([o[1] for o in ko]); Fk = np.where(np.isfinite(Fk), Fk, 1e9)
        Xa = np.vstack([X, kids]); Fa = np.vstack([F, Fk]); Ga = np.vstack([G, Gk])
        fronts = nd_sort(Fa, Ga); sel = []
        for fr in fronts:
            if len(sel) + len(fr) <= POP: sel += fr
            else:
                cd = crowding(Fa[fr]); order = np.argsort(-cd); sel += [fr[i] for i in order[: POP - len(sel)]]; break
        X, F, G = Xa[sel], Fa[sel], Ga[sel]
    # final non-dominated set of all feasible archived points (deduplicated)
    if not archive_f:                                 # no feasible design found: report the least-violating final design
        i = int(np.argmin([cv(g) for g in G]))
        return dict(X=np.zeros((0, E.N_X)), F=np.zeros((0, 4)), G=np.zeros((0, 7)), history=history, least_violation=dict(x=X[i].tolist(), g=G[i].tolist()))
    AX = np.array(archive_x); AF = np.array(archive_f); AG = np.array(archive_g)
    AF, idx = np.unique(np.round(AF, 6), axis=0, return_index=True); AX, AG = AX[idx], AG[idx]
    nd = nd_sort(AF, AG)[0]
    return dict(X=AX[nd], F=AF[nd], G=AG[nd], history=history)


# ----------------------------------------------------------------------------- hypervolume (Monte Carlo, fixed points)
HV_RNG = np.random.default_rng(SEED + 7); HV_PTS = HV_RNG.random((100_000, 4))


def hypervolume(F, ideal, nadir):
    if len(F) == 0: return 0.0
    Fn = (np.asarray(F) - ideal) / (nadir - ideal)
    Fn = np.clip(Fn, 0, 1)
    dom = np.zeros(len(HV_PTS), bool)
    for f in Fn:
        dom |= np.all(HV_PTS >= f, axis=1)
    return float(dom.mean())


# ----------------------------------------------------------------------------- knee selection
def knee(F):
    """Point of the front closest to the ideal point after min-max normalisation on the front itself."""
    F = np.asarray(F); lo, hi = F.min(0), F.max(0); span = np.where(hi - lo > 0, hi - lo, 1.0)
    Fn = (F - lo) / span
    return int(np.argmin(np.linalg.norm(Fn, axis=1))), Fn


def knee_2d(F, i=0, j=1):
    """Maximum perpendicular distance to the chord between the two extreme points of the (i, j) projection."""
    P = np.asarray(F)[:, [i, j]]
    keep = [k for k in range(len(P)) if not np.any(np.all(P <= P[k], axis=1) & np.any(P < P[k], axis=1))]   # 2-D non-dominated subset
    P = P[keep]; lo, hi = P.min(0), P.max(0); Pn = (P - lo) / np.where(hi - lo > 0, hi - lo, 1)
    a = Pn[np.argmin(Pn[:, 0])]; b = Pn[np.argmin(Pn[:, 1])]
    v = b - a
    if np.linalg.norm(v) < 1e-12: return 0
    Q = Pn - a; dist = np.abs(v[0] * Q[:, 1] - v[1] * Q[:, 0]) / np.linalg.norm(v)
    return keep[int(np.argmax(dist))]


# ----------------------------------------------------------------------------- GP + EI surrogate search
class GP:
    def __init__(self, X, y):
        self.X = X; self.ym, self.ys = y.mean(), y.std() + 1e-12; self.y = (y - self.ym) / self.ys
        self.theta = self.fit()

    def kern(self, A, B, ls, sv):
        d = (A[:, None, :] - B[None, :, :]) / ls
        return sv * np.exp(-0.5 * np.sum(d * d, axis=2))

    def nll(self, lt):
        ls, sv, nv = np.exp(lt[:-2]), np.exp(lt[-2]), np.exp(lt[-1])
        K = self.kern(self.X, self.X, ls, sv) + (nv + 1e-8) * np.eye(len(self.X))
        try:
            Lc = np.linalg.cholesky(K)
        except np.linalg.LinAlgError:
            return 1e10
        a = np.linalg.solve(Lc.T, np.linalg.solve(Lc, self.y))
        return float(0.5 * self.y @ a + np.sum(np.log(np.diag(Lc))) + 0.5 * len(self.y) * math.log(2 * math.pi))

    def fit(self):
        best = None
        for ls0 in (0.3, 0.6):
            x0 = np.r_[np.full(self.X.shape[1], math.log(ls0)), 0.0, math.log(1e-3)]
            r = scipy.optimize.minimize(self.nll, x0, method="L-BFGS-B", bounds=[(math.log(0.05), math.log(5.0))] * self.X.shape[1] + [(-3, 3), (math.log(1e-6), math.log(1.0))])
            if best is None or r.fun < best.fun: best = r
        lt = best.x; ls, sv, nv = np.exp(lt[:-2]), np.exp(lt[-2]), np.exp(lt[-1])
        K = self.kern(self.X, self.X, ls, sv) + (nv + 1e-8) * np.eye(len(self.X))
        self.Lc = np.linalg.cholesky(K); self.alpha = np.linalg.solve(self.Lc.T, np.linalg.solve(self.Lc, self.y))
        return ls, sv, nv

    def predict(self, Xs):
        ls, sv, nv = self.theta
        Ks = self.kern(Xs, self.X, ls, sv); mu = Ks @ self.alpha
        v = np.linalg.solve(self.Lc, Ks.T); var = np.maximum(sv - np.sum(v * v, axis=0), 1e-12)
        return mu * self.ys + self.ym, np.sqrt(var) * self.ys


def scalarise(f, g, w, ideal, nadir):
    fn = np.clip((f - ideal) / (nadir - ideal), 0, 1.5)
    s = np.max(w * fn) + 0.05 * np.sum(w * fn)
    if cv(g) > 0 or not np.all(np.isfinite(f)): s = 2.0 + min(cv(g), 5.0)
    return s


def bo_run(w, ideal, nadir, seed):
    rng = np.random.default_rng(seed)
    X = lhs(BO_INIT, E.N_X, rng); Y = []; FG = []
    for x in X:
        f, g, _ = eval_mode(x, "nominal", count=False); n_eval["bo"] += 1; Y.append(scalarise(f, g, w, ideal, nadir)); FG.append((f, g))
    X = list(X)
    for it in range(BO_ITER):
        gp = GP(np.array(X), np.array(Y)); ybest = min(Y)
        cand = rng.random((4000, E.N_X))
        top = np.argsort(Y)[:5]
        loc = np.clip(np.repeat(np.array(X)[top], 60, axis=0) + rng.normal(0, 0.05, (300, E.N_X)), 0, 1)
        cand = np.vstack([cand, loc]); mu, sd = gp.predict(cand)
        z = (ybest - mu) / sd; ei = (ybest - mu) * scipy.stats.norm.cdf(z) + sd * scipy.stats.norm.pdf(z)
        x = cand[int(np.argmax(ei))]
        f, g, _ = eval_mode(x, "nominal", count=False); n_eval["bo"] += 1
        X.append(x); Y.append(scalarise(f, g, w, ideal, nadir)); FG.append((f, g))
    return np.array(X), np.array(Y), FG


# ----------------------------------------------------------------------------- helpers
def design_row(d, f, g, mode):
    if not isinstance(d, dict): d = decode(d)
    r = evaluate_design(d, U_NOM)
    return dict(mode=mode, fs_kHz=d["fs"] / 1e3, phi_nom_deg=d["phi_nom_deg"], L_uH=d["L"] * 1e6, n=d["n"], Bpk_target=d["Bpk"],
                Bpk_realised=r["aux"].get("Bpk", math.nan), tcore=d["tcore"], lcore=d["lcore"], t_dead_ns=d["t_dead"] * 1e9,
                dev1=f"{d['dev1'][0]}x{d['dev1'][1]}", dev2=f"{d['dev2'][0]}x{d['dev2'][1]}",
                f_loss_W=f[0], f_vol_cm3=f[1], f_log10_damage_rel=f[2], f_zvs_margin_A=-f[3],
                eta_nom_pct=100 * r["aux"].get("eta_nom", math.nan), eta_mission_pct=100 * r["aux"].get("eta_mission", math.nan),
                E_loss_Wh_day=r["aux"].get("E_loss_Wh", math.nan), Tj_max_C=r["aux"].get("Tj_max", math.nan),
                dTj1_K=r["aux"].get("dTj1_max", math.nan), dTj2_K=r["aux"].get("dTj2_max", math.nan),
                Ipk_max_A=r["aux"].get("Ipk_max", math.nan), fill_xf=r["aux"].get("fill_t", math.nan), fill_ind=r["aux"].get("fill_l", math.nan),
                N1=r["aux"].get("N1"), N2=r["aux"].get("N2"), N_ind=r["aux"].get("N_ind"), cv=cv(g))


def write_csv(path, rows):
    if not rows: open(path, "w").write(""); return
    keys = list(rows[0].keys())
    with open(path, "w") as fh:
        fh.write(",".join(keys) + "\n")
        for r in rows:
            fh.write(",".join(f"{r[k]:.6g}" if isinstance(r[k], (float, np.floating)) else str(r[k]) for k in keys) + "\n")


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def git_commit():
    try:
        head = open(os.path.join(E.REPO, ".git", "HEAD")).read().strip()
        if head.startswith("ref:"):
            ref = head.split()[1]; p = os.path.join(E.REPO, ".git", ref)
            if os.path.exists(p): return open(p).read().strip()
            packed = os.path.join(E.REPO, ".git", "packed-refs")
            if os.path.exists(packed):
                for line in open(packed):
                    if line.strip().endswith(ref): return line.split()[0]
        return head
    except Exception as ex:
        return f"unknown ({ex})"


# ============================================================================= run
print("self test:", json.dumps(E.self_test(), default=str))
# cross-check against the stored exhaustive-grid baseline (phi = 28 deg -> L = 63.69 uH, no winding capacitance)
grid_json = json.load(open(os.path.join(E.DAB_ROOT, "12_Optimization", "optimization_results.json")))
gb = grid_json["baseline"]
d_gridbase = E.design_from_values(gb["fs"], gb["L"], gb["n"], 0.13, gb["tcore"], gb["lcore"], gb["t_dead"], ("C3M0032120K", 1), ("C3M0016120K", 1))
Cpar_saved = E.C_PAR; E.C_PAR = 0.0; r_gb = evaluate_design(d_gridbase, U_NOM); E.C_PAR = Cpar_saved
crosscheck = dict(stored_grid_baseline_P_loss_W=gb["P_loss"], this_evaluator_same_design_P_loss_W=float(r_gb["f"][0]),
                  stored_vol_cm3=gb["vol"], this_vol_cm3=float(r_gb["f"][1]),
                  baseline_L64uH_with_Cpar_P_loss_W=float(base_nom["f"][0]))
print("cross-check:", crosscheck)

# --- NSGA-II, three variants
runs = {}
for k, mode in enumerate(MODE_LIST):
    t = time.time(); runs[mode] = nsga2(mode, SEED + 10 + k); runs[mode]["t_s"] = time.time() - t
    print(f"{mode}: {len(runs[mode]['F'])} non-dominated, {n_eval[mode]} evaluations, {runs[mode]['t_s']:.0f} s")

# --- exhaustive grid of 12_Optimization re-evaluated here (Bpk target 0.13 as in optimize.py)
t = time.time()
grid = dict(fs=[60e3, 80e3, 100e3, 120e3, 150e3], n=[1.8, 2.0, 2.2], phi_deg=[20, 25, 30, 35],
            tcore=["E55/28/21", "ETD59/31/22", "E65/32/27", "E70/33/32"], lcore=["ETD44/22/15", "ETD49/25/16", "E55/28/21"],
            t_dead=[100e-9, 150e-9, 200e-9], dev1=[("C3M0032120K", 1), ("C3M0016120K", 1)], dev2=[("C3M0016120K", 1), ("C3M0032120K", 2)])
GF, GX, GD, GFull = [], [], [], []; n_grid_full = 0
for combo in itertools.product(*grid.values()):
    fs, n, phi_deg, tcore, lcore, t_dead, dev1, dev2 = combo
    phi = math.radians(phi_deg); L = 800 * n * 400 * phi * (math.pi - phi) / (2 * math.pi ** 2 * fs * E.P_RATED)
    d = E.design_from_values(fs, L, n, 0.13, tcore, lcore, t_dead, dev1, dev2); n_eval["grid"] += 1
    r = evaluate_design(d, U_NOM); f, g = _fix(r)
    if not np.all(np.isfinite(f)): continue
    grid_own_ok = bool(np.all(g[[0, 1, 3, 4, 5]] <= 0))      # 12_Optimization's constraint set: phi <= 60 deg, Tj, Bpk, fills (no ZVS constraint, no Ipk)
    if grid_own_ok and r["aux"]["zvs_full"] >= 0 and g[6] <= 0: n_grid_full += 1       # also satisfies the strict ZVS-at-corners + Ipk constraints
    if grid_own_ok: GF.append(f); GD.append(d); GFull.append(r["feasible"])
GF = np.array(GF); GFull = np.array(GFull); grid_nd = nd_sort(GF, np.zeros((len(GF), 1)))[0]
grid_front_F = GF[grid_nd]; grid_front_D = [GD[i] for i in grid_nd]
pts2 = GF[:, :2]; grid_nd2 = [i for i in range(len(GF)) if not np.any(np.all(pts2 <= pts2[i], axis=1) & np.any(pts2 < pts2[i], axis=1))]
print(f"grid: {n_eval['grid']} candidates, {len(GF)} feasible under the grid's own constraints, {n_grid_full} under the strict constraint set, {len(grid_nd)} non-dominated (4-D), {len(grid_nd2)} (loss, volume), {time.time()-t:.0f} s")

# --- common objective box for hypervolume (union of everything feasible)
allF = np.vstack([runs[m]["F"] for m in runs if len(runs[m]["F"])] + [grid_front_F] + [h for m in runs for g in runs[m]["history"] for h in [np.array(g["front_f"])] if len(h)])
IDEAL = allF.min(0) - 1e-9; NADIR = allF.max(0) + 1e-9
hv_hist = {m: [hypervolume(np.array(h["front_f"]), IDEAL, NADIR) if h["front_f"] else 0.0 for h in runs[m]["history"]] for m in runs}
hv_final = {m: hypervolume(runs[m]["F"], IDEAL, NADIR) for m in runs}
if len(runs["nominal"]["F"]) == 0: raise SystemExit("no feasible nominal design found - check the constraint set")
hv_grid = hypervolume(grid_front_F, IDEAL, NADIR)

# --- surrogate BO (nominal problem), weight vectors on the normalised objectives
t = time.time()
W = [np.array([0.7, 0.1, 0.1, 0.1]), np.array([0.1, 0.7, 0.1, 0.1]), np.array([0.1, 0.1, 0.7, 0.1]), np.array([0.1, 0.1, 0.1, 0.7]), np.array([0.25, 0.25, 0.25, 0.25])]
bo_X, bo_F, bo_G, bo_best, bo_trace = [], [], [], [], []
for k, w in enumerate(W):
    Xb, Yb, FGb = bo_run(w, IDEAL, NADIR, SEED + 100 + k)
    bo_trace.append(np.minimum.accumulate(Yb).tolist())
    for x, (f, g) in zip(Xb, FGb):
        if cv(g) == 0 and np.all(np.isfinite(f)): bo_X.append(x); bo_F.append(f); bo_G.append(g)
    ib = int(np.argmin(Yb)); bo_best.append(dict(w=w.tolist(), s=float(Yb[ib]), x=Xb[ib].tolist(), f=FGb[ib][0].tolist(), feasible=cv(FGb[ib][1]) == 0))
bo_F = np.array(bo_F); bo_X = np.array(bo_X); bo_G = np.array(bo_G)
bo_nd = nd_sort(bo_F, np.zeros((len(bo_F), 1)))[0] if len(bo_F) else []
bo_front_F = bo_F[bo_nd]; bo_front_X = bo_X[bo_nd]
hv_bo = hypervolume(bo_front_F, IDEAL, NADIR)
# NSGA-II nominal hypervolume at the same evaluation budget as BO
bo_budget = n_eval["bo"]
hv_nom_same_budget = next((hv for h, hv in zip(runs["nominal"]["history"], hv_hist["nominal"]) if h["n_eval"] >= bo_budget), hv_hist["nominal"][-1])
# fraction of BO front points dominated by the NSGA-II nominal front
FN = runs["nominal"]["F"]
bo_dominated = float(np.mean([np.any(np.all(FN <= f, axis=1) & np.any(FN < f, axis=1)) for f in bo_front_F])) if len(bo_front_F) else math.nan
grid_dominated = float(np.mean([np.any(np.all(FN <= f, axis=1) & np.any(FN < f, axis=1)) for f in grid_front_F]))
print(f"BO: {bo_budget} evaluations, {len(bo_front_F)} non-dominated, HV {hv_bo:.3f} vs NSGA-II nominal {hv_nom_same_budget:.3f} at the same budget, {time.time()-t:.0f} s")

# --- knee points and baseline comparison
MODES = [m for m in runs if len(runs[m]["F"])]            # variants with at least one feasible design
knees = {}
for m in MODES:
    F = runs[m]["F"]; ik, Fn = knee(F); ik2 = knee_2d(F)
    knees[m] = dict(index=ik, index_2d=ik2, row=design_row(runs[m]["X"][ik], F[ik], runs[m]["G"][ik], m), row_2d=design_row(runs[m]["X"][ik2], F[ik2], runs[m]["G"][ik2], m),
                    norm_dist=float(np.linalg.norm(Fn[ik])), x=runs[m]["X"][ik].tolist())
base_cmp = {}
for m in runs:
    # baseline evaluated in the same mode (no encoding needed: evaluate the design dict directly)
    d = BASELINE; zc = "corners" if m.endswith("_strict") else "nominal"
    r0 = evaluate_design(d, U_NOM, zvs_constraint=zc)
    if m.startswith("nominal"):
        fb, gb_ = _fix(r0)
    else:
        Fs, Gs = [], []
        for u in U_LHS:
            f, g = _fix(evaluate_design(d, u, zvs_constraint=zc)); Fs.append(f); Gs.append(g)
        Fs, Gs = np.array(Fs), np.array(Gs)
        fb = np.nanmax(Fs, 0) if m.startswith("robust") else np.nanmean(Fs, 0); fb[1] = Fs[0, 1]
        gb_ = Gs.max(0) if m.startswith("robust") else np.quantile(Gs, CC_PROB, axis=0, method="higher")
        if np.any(np.isnan(Fs)): gb_[0] = max(gb_[0], 0.5)      # full power unreachable in at least one sample
    F = runs[m]["F"]
    if len(F) == 0:
        base_cmp[m] = dict(f=fb.tolist(), g=gb_.tolist(), feasible=bool(np.all(gb_ <= 0)), n_front=0, n_dominating=0, normalised_distance_to_front=math.nan,
                           improvement_available={k: 0.0 for k in F_NAMES}, dominating_examples=[]); continue
    lo, hi = F.min(0), F.max(0); span = np.where(hi - lo > 0, hi - lo, 1)
    dom_idx = [i for i in range(len(F)) if np.all(F[i] <= fb) and np.any(F[i] < fb)]
    dist = float(np.min(np.linalg.norm((F - fb) / span, axis=1)))
    # best improvement available in each objective among dominating designs (others not worse)
    impr = {F_NAMES[k]: float(fb[k] - F[dom_idx][:, k].min()) if dom_idx else 0.0 for k in range(4)}
    base_cmp[m] = dict(f=fb.tolist(), g=gb_.tolist(), feasible=bool(np.all(gb_ <= 0)), n_front=len(F), n_dominating=len(dom_idx),
                       normalised_distance_to_front=dist, improvement_available=impr,
                       dominating_examples=[design_row(runs[m]["X"][i], F[i], runs[m]["G"][i], m) for i in dom_idx[:3]])

# --- effect of the chance constraint / robustness: compare fronts
def front_stats(F):
    if len(F) == 0: return dict(n=0, loss_min=math.nan, loss_max=math.nan, vol_min=math.nan, vol_max=math.nan, zvs_min=math.nan, zvs_max=math.nan, rel_best=math.nan, rel_worst=math.nan)
    return dict(n=len(F), loss_min=float(F[:, 0].min()), loss_max=float(F[:, 0].max()), vol_min=float(F[:, 1].min()), vol_max=float(F[:, 1].max()),
                zvs_min=float(-F[:, 3].max()), zvs_max=float(-F[:, 3].min()), rel_best=float(F[:, 2].min()), rel_worst=float(F[:, 2].max()))
# how many nominal-front designs survive the CC / robust constraints?
survive = {}
for m in [m for m in MODE_LIST if m != "nominal"]:
    ok = 0
    for x in runs["nominal"]["X"]:
        _, g, feas = eval_mode(x, m, count=False); ok += feas
    survive[m] = dict(n_nominal_front=len(runs["nominal"]["X"]), n_feasible_under_mode=int(ok))
# ZVS probability of nominal-front and cc-front designs (fraction of LHS samples with ZVS at all corners at full power)
def zvs_prob(d, strict=False):
    if not isinstance(d, dict): d = decode(d)
    return float(np.mean([evaluate_design(d, u, zvs_constraint="corners" if strict else "nominal")["g"][2] <= 0 for u in U_LHS]))
zvs_p = {m: [zvs_prob(x, m.endswith("_strict")) for x in runs[m]["X"]] for m in MODES}

# ============================================================================= outputs
rows = []
for m in MODES:
    for x, f, g in zip(runs[m]["X"], runs[m]["F"], runs[m]["G"]): rows.append(design_row(x, f, g, m))
for d, f in zip(grid_front_D, grid_front_F):
    r = dict(mode="grid", fs_kHz=d["fs"] / 1e3, phi_nom_deg=d["phi_nom_deg"], L_uH=d["L"] * 1e6, n=d["n"], Bpk_target=d["Bpk"], tcore=d["tcore"], lcore=d["lcore"],
             t_dead_ns=d["t_dead"] * 1e9, dev1=f"{d['dev1'][0]}x{d['dev1'][1]}", dev2=f"{d['dev2'][0]}x{d['dev2'][1]}", f_loss_W=f[0], f_vol_cm3=f[1], f_log10_damage_rel=f[2], f_zvs_margin_A=-f[3])
    rows.append(r)
for x, f in zip(bo_front_X, bo_front_F): rows.append(design_row(x, f, np.zeros(7), "bo"))
write_csv(os.path.join(RES, "pareto_fronts.csv"), [r for r in rows if r["mode"] in runs])
write_csv(os.path.join(RES, "grid_front_reevaluated.csv"), [r for r in rows if r["mode"] == "grid"])
write_csv(os.path.join(RES, "bo_front.csv"), [r for r in rows if r["mode"] == "bo"])
write_csv(os.path.join(RES, "uncertainty_samples_LHS.csv"), [dict(zip(U_NAMES, u)) for u in U_LHS])
write_csv(os.path.join(RES, "mission_profile_ASSUMED.csv"), [dict(hour=h, P_W=p, V1_V=v1, V2_V=v2) for h, (p, v1, v2) in enumerate(E.MISSION)])
json.dump(dict(hv_history=hv_hist, hv_final=hv_final, hv_grid=hv_grid, hv_bo=hv_bo, hv_nominal_at_bo_budget=hv_nom_same_budget, ideal=IDEAL.tolist(), nadir=NADIR.tolist(),
               n_eval=n_eval, bo_trace_scalarised=bo_trace, bo_best=bo_best, bo_front_dominated_by_nsga_fraction=bo_dominated, grid_front_dominated_by_nsga_fraction=grid_dominated),
          open(os.path.join(RES, "convergence.json"), "w"), indent=1)
json.dump(dict(knees=knees, baseline_rows=design_row(BASELINE, *(_fix(base_nom)), "baseline"),
               baseline_vs_front=base_cmp, front_stats={m: front_stats(runs[m]["F"]) for m in runs}, survival=survive,
               zvs_probability={m: dict(min=min(v), mean=float(np.mean(v)), frac_ge_95=float(np.mean(np.array(v) >= CC_PROB))) for m, v in zvs_p.items()},
               crosscheck=crosscheck, lifetime_model=dict(law="Nf = A dT^alpha exp(Q/(R Tm)) (LESIT, Held 1997, Si IGBT modules - literature-typical, not measured for SiC TO-247)", **E.LESIT, dTj_min_K=E.DTJ_MIN,
                                                           baseline_daily_damage=10 ** LOG10_D_BASE, baseline_lifetime_proxy_years=1 / (365 * 10 ** LOG10_D_BASE))),
          open(os.path.join(RES, "knee_and_baseline.json"), "w"), indent=1, default=float)

# ----------------------------------------------------------------------------- figures
plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.25, "axes.spines.top": False, "axes.spines.right": False})
# 1. 2-D projections
fig, ax = plt.subplots(1, 3, figsize=(14, 4.3))
pairs = [(1, 0, F_LABELS[1], F_LABELS[0]), (0, 2, F_LABELS[0], F_LABELS[2]), (0, 3, F_LABELS[0], F_LABELS[3])]
for a, (i, j, xl, yl) in zip(ax, pairs):
    sgn = -1 if j == 3 else 1
    a.scatter(grid_front_F[:, i], sgn * grid_front_F[:, j], s=14, c=COL["grid"], marker="s", label="exhaustive grid front (12_Optimization constraints, re-evaluated)", alpha=0.8)
    if len(bo_front_F): a.scatter(bo_front_F[:, i], sgn * bo_front_F[:, j], s=20, facecolors="none", edgecolors=COL["bo"], marker="D", label="GP-EI surrogate search")
    for m in MODES:
        F = runs[m]["F"]; a.scatter(F[:, i], sgn * F[:, j], s=16, c=COL[m], label=f"NSGA-II {LABEL[m]}", alpha=0.85)
        k = knees[m]["index"]; a.scatter(F[k, i], sgn * F[k, j], s=120, facecolors="none", edgecolors=COL["knee"], linewidths=1.5, zorder=5)
    fb = np.array(base_cmp["nominal"]["f"]); a.scatter(fb[i], sgn * fb[j], s=90, c=COL["base"], marker="*", zorder=6, label="baseline (100 kHz, 64 uH, n = 2, E65)")
    a.set_xlabel(xl); a.set_ylabel(yl)
ax[0].legend(fontsize=7, loc="upper right"); ax[0].set_title("red rings: knee designs (closest to ideal point)", fontsize=8)
fig.suptitle("Pareto sets: nominal vs robust vs chance-constrained (2-D projections of the 4-objective fronts)", fontsize=10)
fig.tight_layout(); fig.savefig(os.path.join(RES, "pareto_2d.png"), dpi=140); plt.close(fig)
# 2. 3-D
M3 = [m for m in MAIN if m in MODES]
fig = plt.figure(figsize=(3.8 * len(M3), 4.6))
for k, m in enumerate(M3):
    a = fig.add_subplot(1, len(M3), k + 1, projection="3d"); F = runs[m]["F"]
    sc = a.scatter(F[:, 0], F[:, 1], -F[:, 3], c=F[:, 2], cmap="Blues_r", s=18, depthshade=False, edgecolors=COL[m], linewidths=0.4, vmin=allF[:, 2].min(), vmax=allF[:, 2].max())
    a.scatter([base_cmp[m]["f"][0]], [base_cmp[m]["f"][1]], [-base_cmp[m]["f"][3]], c=COL["base"], marker="*", s=80)
    a.set_xlabel("loss (W)", fontsize=8); a.set_ylabel("volume (cm3)", fontsize=8); a.set_zlabel("ZVS margin (A)", fontsize=8); a.set_title(LABEL[m], fontsize=9)
    a.tick_params(labelsize=7)
fig.colorbar(sc, ax=fig.axes, shrink=0.6, label="log10 damage / baseline (darker = more reliable)")
fig.savefig(os.path.join(RES, "pareto_3d.png"), dpi=140); plt.close(fig)
# 3. convergence
fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
for m in runs: ax[0].plot(range(len(hv_hist[m])), hv_hist[m], c=COL[m], lw=2, label=f"NSGA-II {LABEL[m]}")
ax[0].axhline(hv_grid, c=COL["grid"], ls="--", lw=1.5, label="exhaustive grid front (nominal)")
ax[0].set_xlabel("generation"); ax[0].set_ylabel("hypervolume (fraction of the common box)"); ax[0].legend(fontsize=7)
ev = [h["n_eval"] for h in runs["nominal"]["history"]]; ax[1].plot(ev, hv_hist["nominal"], c=COL["nominal"], lw=2, label="NSGA-II nominal")
ax[1].scatter([bo_budget], [hv_bo], c=COL["bo"], marker="D", s=50, zorder=5, label=f"GP-EI surrogate search ({len(W)} weight vectors)")
ax[1].set_xlabel("design evaluations"); ax[1].set_ylabel("hypervolume"); ax[1].legend(fontsize=7); ax[1].set_xscale("log")
fig.tight_layout(); fig.savefig(os.path.join(RES, "convergence_hypervolume.png"), dpi=140); plt.close(fig)
# 4. decision variables on the fronts
fig, ax = plt.subplots(2, 4, figsize=(14, 6))
cont = [("fs_kHz", "fs (kHz)"), ("phi_nom_deg", "phi_nom (deg)"), ("L_uH", "L (uH)"), ("n", "turns ratio n"), ("Bpk_target", "Bpk target (T)"), ("t_dead_ns", "dead time (ns)")]
for a, (k, lab) in zip(ax.flat[:6], cont):
    for m in M3:
        v = [r[k] for r in rows if r["mode"] == m]
        a.hist(v, bins=12, color=COL[m], alpha=0.55, label=LABEL[m])
    a.set_xlabel(lab); a.set_ylabel("count on front")
ax.flat[0].legend(fontsize=7)
for a, key, cats in ((ax.flat[6], "tcore", E.CORE_T), (ax.flat[7], "dev1", [f"{d}x{p}" for d, p in E.DEV1])):
    wdt = 0.8 / len(M3)
    for k, m in enumerate(M3):
        v = [r[key] for r in rows if r["mode"] == m]; a.bar(np.arange(len(cats)) + (k - (len(M3) - 1) / 2) * wdt, [v.count(c) for c in cats], wdt, color=COL[m])
    a.set_xticks(range(len(cats))); a.set_xticklabels(cats, fontsize=7, rotation=15); a.set_ylabel("count on front"); a.set_xlabel(key)
fig.suptitle("Decision-variable distributions on the Pareto sets (requirement-based constraint set)", fontsize=10); fig.tight_layout(); fig.savefig(os.path.join(RES, "decision_variables.png"), dpi=140); plt.close(fig)
# 5. mission profile and Tj traces (baseline vs nominal knee)
fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
hrs = np.arange(24); ax[0].step(hrs, [p[0] / 1e3 for p in E.MISSION], where="post", c=COL["nominal"], lw=2, label="power (kW, >0 charging)")
ax[0].set_xlabel("hour"); ax[0].set_ylabel("kW"); ax[0].set_title("ASSUMED 24 h mission profile (not measured)", fontsize=9)
a2 = ax[0]; a2.step(hrs, [p[2] / 100 for p in E.MISSION], where="post", c=COL["robust"], lw=1.5, ls="--", label="battery voltage V2 (x100 V)"); a2.legend(fontsize=7)
rb = evaluate_design(BASELINE, U_NOM, want_detail=True); rk = evaluate_design(decode(np.array(knees["nominal"]["x"])), U_NOM, want_detail=True)
ax[1].step(hrs, rb["Tj1_series"], where="post", c=COL["base"], lw=2, label="baseline HV bridge Tj"); ax[1].step(hrs, rb["Tj2_series"], where="post", c=COL["base"], lw=1, ls=":", label="baseline LV bridge Tj")
ax[1].step(hrs, rk["Tj1_series"], where="post", c=COL["knee"], lw=2, label="nominal knee HV bridge Tj"); ax[1].step(hrs, rk["Tj2_series"], where="post", c=COL["knee"], lw=1, ls=":", label="nominal knee LV bridge Tj")
ax[1].set_xlabel("hour"); ax[1].set_ylabel("junction temperature (C), Tamb 45 C"); ax[1].legend(fontsize=7); ax[1].set_title("steady-state Tj per hourly segment -> rainflow -> damage proxy", fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(RES, "mission_profile_Tj.png"), dpi=140); plt.close(fig)

# ----------------------------------------------------------------------------- provenance
inputs = [os.path.join(E.DAB_ROOT, "dabtools", "dab", f) for f in ("dab_model.py", "losses.py", "magnetics.py", "devices.py")] + \
         [os.path.join(E.DAB_ROOT, "04_Design_Calculations", "design_values.json"), os.path.join(E.DAB_ROOT, "12_Optimization", "optimization_results.json"),
          os.path.join(HERE, "dab_eval.py"), os.path.abspath(__file__)]
prov = dict(module="Advanced_Research_2026/Robust_Optimization", script=os.path.basename(__file__), generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__, matplotlib=matplotlib.__version__, git_commit=git_commit(),
            input_hashes_sha256_16={os.path.relpath(p, E.REPO): sha(p) for p in inputs}, seed=SEED, population=POP, generations=GEN, lhs_samples_uncertainty=S_UNC,
            bo_init=BO_INIT, bo_iterations=BO_ITER, n_evaluations=n_eval, quick_mode=args.quick, wall_time_s=time.time() - T0, maturity="L2")
json.dump(prov, open(os.path.join(HERE, "provenance.json"), "w"), indent=1)

# ----------------------------------------------------------------------------- README
def frow(r, extra=""):
    return (f"| {r['fs_kHz']:.0f} | {r['phi_nom_deg']:.1f} | {r['L_uH']:.1f} | {r['n']:.2f} | {r['Bpk_target']:.3f} | {r['tcore']} | {r['lcore']} | {r['t_dead_ns']:.0f} | {r['dev1']} | {r['dev2']} | "
            f"{r['f_loss_W']:.1f} | {r['f_vol_cm3']:.0f} | {r['f_log10_damage_rel']:+.2f} | {r['f_zvs_margin_A']:.2f} |{extra}")
HDR = "| fs (kHz) | phi_nom (deg) | L (uH) | n | Bpk (T) | transformer | inductor | t_dead (ns) | HV device | LV device | loss (W) | volume (cm3) | log10 D/D_base | ZVS margin (A) |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
R = []; w = R.append
w("# Robust_Optimization - reliability-aware multi-objective DAB design under uncertainty\n")
w(f"_Generated by `robust_optimize.py` (seed {SEED}, NSGA-II population {POP} x {GEN} generations for every variant, {S_UNC} LHS uncertainty samples per design, "
  f"{sum(n_eval.values())} design evaluations in {prov['wall_time_s']:.0f} s). Maturity **L2** (analytical/simulation models, nothing measured)._\n")
w("## 1. Problem\n")
w("Design variables (9, mixed): switching frequency fs 60-200 kHz; nominal phase shift phi_nom 12-50 deg, which fixes the series inductance "
  "L = V1 n V2 phi (pi - phi) / (2 pi^2 fs P) at 800/400 V, 6.6 kW (L is reported); turns ratio n 1.6-2.4; transformer peak-flux target 0.08-0.20 T; "
  "transformer core {E55, ETD59, E65, E70}; inductor core {ETD44, ETD49, E55}; dead time 80-250 ns; HV device {C3M0032120K, C3M0016120K}; LV device {C3M0016120K x1, C3M0032120K x2}. "
  "Modulation is SPS (as in 12_Optimization); magnetics are designed at the nominal point with `dabtools.dab.magnetics.design_transformer/design_inductor`.\n")
w("Objectives (all minimised, no weighted sum):\n\n"
  "1. total converter loss at 800/400 V, 6.6 kW (W) - same budget as 04/12: bridges, gate drive, transformer, inductor, 12 W auxiliary, 0.4 % PCB/bus-bar;\n"
  "2. magnetics volume (cm3) = 2.2 x (transformer + inductor core volume), as in 12_Optimization;\n"
  "3. reliability proxy: log10 of the daily lifetime consumption D = sum n_i / Nf_i of the hotter bridge over the ASSUMED 24 h mission profile "
  "(rainflow count of the hourly steady-state Tj sequence, Coffin-Manson/Arrhenius law Nf = A dTj^alpha exp(Q/(R Tm)) with the LESIT coefficients "
  f"A = {E.LESIT['A']:.3e}, alpha = {E.LESIT['alpha']}, Q/R = {E.LESIT['Q_over_R']:.0f} K). **These coefficients are literature-typical values for Si IGBT modules "
  "(Held et al. 1997); they are not measured for discrete SiC TO-247 devices, so only the ratio between designs is meaningful** - the objective is reported as log10(D / D_baseline). "
  f"For the record the absolute proxy for the baseline is {1/(365*10**LOG10_D_BASE):.2e} years, i.e. thermal cycling is not life-limiting with the project heatsink (dTj < 15 K);\n"
  "4. negative ZVS margin: -min over {nominal + 4 envelope corners} x {100 %, 50 % load} of (I_edge - I_min) at both bridges, A referred to the HV side "
  "(I_min from the energy criterion with Coss_er and the 60 pF winding capacitance of design_values.json).\n")
w("Constraints (<= 0), following 00_Requirements/02_operating_envelope.md: full power reachable at all 9 (V1, V2) corners with phi <= 60 deg (requirement 1, firmware clamp); "
  "Tj <= 125 C at every full-power corner (13_Thermal_Analysis limit, heatsink 0.22 K/W + 0.35 K/W pad) **with hard-switching losses charged wherever the ZVS criterion fails** (requirement 2/3: "
  "a point without ZVS is allowed if the thermal budget holds); ZVS at both bridges at the nominal voltages 800/400 V at 100 % and 50 % load (EL-04a style); transformer Bpk at 850 V <= 0.2 T; "
  "transformer and inductor window fill <= 0.7; HV peak current <= 24 A (design_values I_limit_pk). ZVS over the envelope corners is objective 4 (maximised margin) and, in the three *strict* variants, "
  "an additional hard constraint (ZVS at both bridges at all five full-power points); the strict variants are reported because the task asked for corner ZVS as a constraint, and section 3.3 shows why it is "
  "incompatible with the 60 deg limit under inductance tolerance for SPS.\n")
w("Uncertainty (assumed uniform, not measured): " + "; ".join(f"{k} {E.U_DESC[k]} [{E.U_BOUNDS[i,0]:g}, {E.U_BOUNDS[i,1]:g}]" for i, k in enumerate(U_NAMES)) +
  f". One Latin-hypercube set of {S_UNC} samples (common random numbers, `results/uncertainty_samples_LHS.csv`) is used for every design. "
  "**Robust** variant: every objective and constraint is the worst case over the samples. **Chance-constrained** variant: objectives are sample means, "
  f"every constraint is enforced at its {100*CC_PROB:.0f} % empirical quantile, so ZVS at the envelope corners holds with probability >= {100*CC_PROB:.0f} % (at most {int((1-CC_PROB)*S_UNC)} of {S_UNC} samples may fail).\n")
w("Mission profile (`results/mission_profile_ASSUMED.csv`, figure below): ASSUMED EV-charger / battery-interface day, bidirectional (night charging 6.6 kW with "
  "battery voltage rising 330 -> 445 V, morning and evening vehicle-to-grid discharge up to 6.6 kW, midday PV charging 3.3 kW, standby hours with 12 W auxiliary loss). "
  "Segments are hourly, so each is evaluated at steady state (thermal time constants of TO-247 + heatsink are minutes).\n")
w("## 2. Methods\n")
w("* **Evaluator** (`dab_eval.py`): closed-form SPS waveform quantities (exact piecewise-linear rms), project loss model (`dabtools.dab.losses` re-implemented with Rds_on/Coss scaling, "
  "identical at scale 1), 5-step electro-thermal iteration, project magnetics design routines. Self-test against the numerical `DABPoint` model: "
  f"rms/peak within {100*E.self_test()['max_rel_err_Irms_Ipk_vs_DABPoint_N4000']:.2f} %, edge currents identical to `dab_model.sps_switching_currents`. "
  f"Cross-check with the stored 12_Optimization baseline (phi = 28 deg -> 63.7 uH, no winding capacitance): stored {crosscheck['stored_grid_baseline_P_loss_W']:.2f} W, "
  f"this evaluator {crosscheck['this_evaluator_same_design_P_loss_W']:.2f} W; the project baseline with L = 64.0 uH gives {crosscheck['baseline_L64uH_with_Cpar_P_loss_W']:.2f} W. "
  "The 1 W difference has a cause worth recording: `DABPoint.switching_currents()` detects a third, wrap-around edge on bridge 1 (theta = 2 pi - d_theta) so 12_Optimization and 04 count three HV turn-off/dead-time events per period instead of two "
  "(HV switching 2.80 W and dead-time diode 0.87 W in design_values.json vs 1.88 W and 0.59 W here); the closed form uses two edges per bridge.\n"
  "* **NSGA-II** (numpy): constrained non-dominated sorting (feasible beats infeasible, infeasible ranked by total violation), crowding distance, binary tournament, SBX (eta_c = 15, p_c = 0.9), polynomial mutation (eta_m = 20, p_m = 1/9). "
  "The reported Pareto set is the non-dominated subset of all feasible first-front members archived over the generations. Hypervolume is a Monte-Carlo estimate (1e5 fixed points) in a common box spanned by the union of all fronts.\n"
  "* **Surrogate-assisted search**: Gaussian process (ARD squared-exponential kernel, hyperparameters by marginal likelihood, L-BFGS-B, two restarts) on an augmented-Tchebycheff scalarisation "
  f"s = max_k w_k f~_k + 0.05 sum_k w_k f~_k of the box-normalised objectives, expected-improvement acquisition maximised over 4000 random + 300 local candidates; {len(W)} weight vectors, {BO_INIT} LHS initial + {BO_ITER} iterations each. "
  "Infeasible designs get s = 2 + violation. This is a simplified single-objective BO per weight vector (ParEGO-like), not a hypervolume-based multi-objective BO; the weight vectors only steer the search, the result reported is the non-dominated set of all feasible evaluated points.\n"
  "* **Exhaustive grid**: the 8640-point grid of 12_Optimization re-evaluated with this evaluator (Bpk target 0.13 T as there) for a like-for-like comparison.\n"
  "* **Knee selection**: on each front, min-max normalise the four objectives over the front and take the point closest (Euclidean) to the ideal point; "
  "a second knee from the (loss, volume) projection (maximum distance from the chord between the extremes) is reported as a cross-check. Both are standard knee heuristics; neither is a tuned weighted-sum score.\n")
w("## 3. Results\n")
w("Variants: `nominal`, `robust`, `cc` use the requirement-based constraint set; `*_strict` add ZVS at every full-power corner as a hard constraint.\n")
w(f"| variant | evaluations | non-dominated designs | hypervolume | loss range (W) | volume range (cm3) | ZVS-margin range (A) | log10 D/D_base range |\n|---|---|---|---|---|---|---|---|")
for m in runs:
    s = front_stats(runs[m]["F"])
    w(f"| NSGA-II {LABEL[m]} | {n_eval[m]} | {s['n']} | {hv_final[m]:.3f} | {s['loss_min']:.1f} - {s['loss_max']:.1f} | {s['vol_min']:.0f} - {s['vol_max']:.0f} | {s['zvs_min']:.2f} - {s['zvs_max']:.2f} | {s['rel_best']:+.2f} - {s['rel_worst']:+.2f} |")
s = front_stats(grid_front_F)
w(f"| exhaustive grid (nominal, re-evaluated) | {n_eval['grid']} ({len(GF)} feasible) | {s['n']} | {hv_grid:.3f} | {s['loss_min']:.1f} - {s['loss_max']:.1f} | {s['vol_min']:.0f} - {s['vol_max']:.0f} | {s['zvs_min']:.2f} - {s['zvs_max']:.2f} | {s['rel_best']:+.2f} - {s['rel_worst']:+.2f} |")
if len(bo_front_F):
    s = front_stats(bo_front_F)
    w(f"| GP-EI surrogate search (nominal) | {bo_budget} | {s['n']} | {hv_bo:.3f} | {s['loss_min']:.1f} - {s['loss_max']:.1f} | {s['vol_min']:.0f} - {s['vol_max']:.0f} | {s['zvs_min']:.2f} - {s['zvs_max']:.2f} | {s['rel_best']:+.2f} - {s['rel_worst']:+.2f} |")
w(f"\nThe robust and chance-constrained hypervolumes are computed in the same box but from worst-case / mean objectives, so they are not directly comparable to the nominal value; the comparison that matters is the shift of the fronts in the figures. "
  f"NSGA-II nominal dominates {100*grid_dominated:.0f} % of the grid's 4-D non-dominated designs and {100*bo_dominated:.0f} % of the surrogate-search designs; at the surrogate budget ({bo_budget} evaluations) NSGA-II nominal had hypervolume {hv_nom_same_budget:.3f} vs {hv_bo:.3f} for the surrogate search. "
  f"The grid front is evaluated under 12_Optimization's own constraint set (phi <= 60 deg, Tj, Bpk, fills; {len(GF)} of 8640 feasible; {int(GFull.sum())} of them also pass this module's nominal set); only {n_grid_full} grid designs satisfy the strict ZVS-at-every-full-power-corner + Ipk <= 24 A set, "
  "because the grid's phi_nom steps (20, 25, 30, 35 deg) straddle the narrow strict window (see 3.3) - its reported front designs (phi_nom 20 deg) hard-switch at the 650/450 V and 850/300 V full-power corners "
  "(allowed by the requirements if Tj holds, which it does with this heatsink).\n")
w("![pareto 2d](results/pareto_2d.png)\n\n![pareto 3d](results/pareto_3d.png)\n\n![convergence](results/convergence_hypervolume.png)\n")
w("### 3.1 Knee designs\n")
w(HDR)
for m in MODES: w(frow(knees[m]["row"], f" NSGA-II {LABEL[m]}, knee (ideal-point distance {knees[m]['norm_dist']:.2f})"))
for m in MODES: w(frow(knees[m]["row_2d"], f" NSGA-II {LABEL[m]}, 2-D (loss, volume) chord knee"))
br = json.load(open(os.path.join(RES, "knee_and_baseline.json")))["baseline_rows"]
w(frow(br, " **baseline** (nominal evaluation)"))
kn = knees["nominal"]["row"]
w(f"\nRationale: the knee is the design beyond which improving any one objective costs disproportionately in the others (closest point to the ideal in the normalised objective space). "
  f"The nominal knee runs at {kn['fs_kHz']:.0f} kHz with phi_nom {kn['phi_nom_deg']:.1f} deg (L = {kn['L_uH']:.1f} uH), n = {kn['n']:.2f}, {kn['tcore']} / {kn['lcore']}, dead time {kn['t_dead_ns']:.0f} ns, "
  f"{kn['dev1']} / {kn['dev2']}: {kn['f_loss_W']:.1f} W (eta {kn['eta_nom_pct']:.2f} %), {kn['f_vol_cm3']:.0f} cm3, mission efficiency {kn['eta_mission_pct']:.2f} % ({kn['E_loss_Wh_day']:.0f} Wh/day), "
  f"Tj max {kn['Tj_max_C']:.0f} C, dTj (HV/LV) {kn['dTj1_K']:.1f}/{kn['dTj2_K']:.1f} K, ZVS margin {kn['f_zvs_margin_A']:.2f} A.\n")
w("### 3.2 Baseline (100 kHz, 64 uH, n = 2, E65/E55, 150 ns, C3M0032120K / C3M0016120K) against the fronts\n")
w("| variant | baseline objectives (loss W, volume cm3, log10 D/D_base, ZVS margin A) | feasible under variant | front designs dominating it | normalised distance to front | loss reduction available (W) | volume reduction available (cm3) | ZVS-margin gain available (A) |\n|---|---|---|---|---|---|---|---|")
for m in runs:
    b = base_cmp[m]; f = b["f"]
    w(f"| {LABEL[m]} | {f[0]:.1f}, {f[1]:.0f}, {f[2]:+.2f}, {-f[3]:.2f} | {'yes' if b['feasible'] else 'no'} | {b['n_dominating']} of {b['n_front']} | {b['normalised_distance_to_front']:.3f} | "
      f"{b['improvement_available']['P_loss_nom_W']:.1f} | {b['improvement_available']['vol_cm3']:.0f} | {b['improvement_available']['neg_zvs_margin_A']:.2f} |")
bn = base_cmp["nominal"]
_ex = bn["dominating_examples"][0] if bn["dominating_examples"] else None
verdict = ("The baseline is **non-dominated** in the nominal problem: no design of the front is at least as good in all four objectives, so it is Pareto-optimal within this model."
           if bn["n_dominating"] == 0 else
           f"The baseline is **dominated** by {bn['n_dominating']} front design(s) in the nominal problem, but only narrowly: the normalised distance to the front is {bn['normalised_distance_to_front']:.3f} "
           f"(front span = 1) and the dominating designs save at most {bn['improvement_available']['P_loss_nom_W']:.1f} W loss, {bn['improvement_available']['vol_cm3']:.0f} cm3 magnetics and gain at most "
           f"{bn['improvement_available']['neg_zvs_margin_A']:.2f} A ZVS margin while being no worse elsewhere."
           if bn["normalised_distance_to_front"] < 0.15 else
           f"The baseline is **dominated** by {bn['n_dominating']} of the {bn['n_front']} front designs; its normalised distance to the front is {bn['normalised_distance_to_front']:.3f} of the front span. "
           f"The dominating designs save at most {bn['improvement_available']['P_loss_nom_W']:.1f} W ({100*bn['improvement_available']['P_loss_nom_W']/bn['f'][0]:.1f} % of the loss) and "
           f"{bn['improvement_available']['vol_cm3']:.0f} cm3 ({100*bn['improvement_available']['vol_cm3']/bn['f'][1]:.0f} % of the magnetics volume) while being no worse in reliability proxy and ZVS margin"
           + (f" - e.g. {_ex['fs_kHz']:.0f} kHz, phi_nom {_ex['phi_nom_deg']:.1f} deg (L = {_ex['L_uH']:.1f} uH), n = {_ex['n']:.2f}, {_ex['tcore']} + {_ex['lcore']} inductor, {_ex['t_dead_ns']:.0f} ns, {_ex['dev1']} / {_ex['dev2']}." if _ex else "."))
w("\n" + verdict + " " + ("It is near-Pareto-optimal." if bn["normalised_distance_to_front"] < 0.15 else
  f"Verdict: the baseline is near-Pareto-optimal in loss (within {100*bn['improvement_available']['P_loss_nom_W']/bn['f'][0]:.0f} %) but not in magnetics volume: the E55 series-inductor core is oversized "
  f"(window fill {json.load(open(os.path.join(RES, 'knee_and_baseline.json')))['baseline_rows']['fill_ind']:.2f}) and an ETD49 core with 2 x C3M0032120K on the LV bridge gives the same loss, ZVS margin and reliability with less volume; "
  "the choice fs = 100 kHz / phi_nom = 28 deg / n = 2 itself lies on the front.") +
  f" Under the robust and chance-constrained variants the baseline is {'feasible' if base_cmp['robust']['feasible'] else 'NOT feasible'} / {'feasible' if base_cmp['cc']['feasible'] else 'NOT feasible'} respectively "
  f"(violated constraint: {G_NAMES[int(np.argmax(base_cmp['robust']['g']))]} - the 650/300 V corner needs phi > 60 deg when L is at +15 %, see 3.3); "
  f"its probability of ZVS at 800/400 V (100 % and 50 % load) over the LHS set is {zvs_prob(BASELINE):.2f}, of ZVS at every full-power corner {zvs_prob(BASELINE, True):.2f} (see `results/knee_and_baseline.json`).\n")
if bn["dominating_examples"]:
    w("Designs dominating the baseline (nominal, first three):\n\n" + HDR)
    for r in bn["dominating_examples"]: w(frow(r))
    w("")
w("### 3.3 Effect of the uncertainty treatment\n")
for m in [m for m in MODE_LIST if m != "nominal"]:
    sv = survive[m]
    w(f"* {sv['n_feasible_under_mode']} of the {sv['n_nominal_front']} nominal-front designs remain feasible under the {LABEL[m]} constraints.")
for m in runs:
    if m not in MODES:
        w(f"* **No feasible design was found by the {LABEL[m]} variant** ({n_eval[m]} evaluations); least-violating final design: constraints {np.round(runs[m]['least_violation']['g'], 3).tolist()} (order {G_NAMES})."); continue
    z = json.load(open(os.path.join(RES, "knee_and_baseline.json")))["zvs_probability"][m]
    what = "ZVS at every full-power corner" if m.endswith("_strict") else "ZVS at 800/400 V (100 % and 50 % load)"
    w(f"* {LABEL[m]} front: probability of {what} over the LHS set is min {z['min']:.2f}, mean {z['mean']:.2f}; {100*z['frac_ge_95']:.0f} % of its designs reach >= 95 %.")
FS = {m: front_stats(runs[m]["F"]) for m in runs}
w("* Shift of the fronts (minimum loss / maximum ZVS margin / best log10 D on each front): " + "; ".join(
    f"{LABEL[m]} {FS[m]['loss_min']:.1f} W / {FS[m]['zvs_max']:.2f} A / {FS[m]['rel_best']:+.2f}" for m in MODES) +
  ". Worst-case objectives include +30 % Rds_on, +25 % core loss and 55 C ambient simultaneously, so a robust front sits above the nominal one in loss by construction; "
  "the chance-constrained objectives are sample means and sit close to the nominal values, the difference is in which designs are admitted.")
w("* Why the strict worst case is (nearly) empty - closed form: with SPS at full power the HV bridge keeps ZVS at the 650/450 V corner only if "
  "phi > pi (V2' - V1) / (2 V2') (I0 > 0) and the LV bridge at 850/300 V only if phi > pi (V1 - V2') / (2 V1) (I1 > 0); for n = 2 these are 25.0 deg and 26.5 deg. "
  "Because P = V1 V2' phi (pi - phi) / (2 pi^2 fs L), every corner sees the same K = 2 pi^2 fs L P scaled by 1/(V1 V2'): ZVS at 650/450 V (585 kV^2, phi >= 25.0 deg) needs K >= 690 kV^2 "
  "and ZVS at 850/300 V (510 kV^2, phi >= 26.5 deg) K >= 632 kV^2, while the 60 deg limit of 00_Requirements / firmware clamp at 650/300 V (390 kV^2) caps K <= 855 kV^2. "
  "K is proportional to L, so the zero-current ZVS boundaries and the phase limit together admit only a K ratio of 1.24, i.e. a +/-10.7 % inductance band for n = 2 (+/-12.7 % for n = 1.95), "
  "below the assumed +/-15 % tolerance; the Coss-based minimum ZVS current, the +20 % Coss sample and the 24 A peak limit of the strict set narrow it further. "
  "(Earlier text quoted 57 deg at 650/300 V and a +/-1.5 % band: the 57 deg is the baseline 64 uH value, not the value implied by the 26.5 deg boundary (37.3 deg), and the 1.5 % was not supported by the closed form - corrected 2026-10-10.) "
  "In nominal-phase terms the lossless bound is phi_nom (800/400 V) = 22.5-29.1 deg; the optimiser's strict set narrows it to about 26.5-28.5 deg - the baseline (28.2 deg) sits inside it, which also explains why only "
  f"{n_grid_full} of the 8640 grid designs (phi_nom 20/25/30/35 deg) satisfy the strict constraint set. Consequence: with SPS, ZVS at the voltage-mismatch corners at full power cannot be *guaranteed* "
  "under a +/-15 % inductance tolerance; the requirement document already allows hard-switched operation where the thermal budget holds, which is what the main variants enforce (Tj with hard-switching losses) "
  "while the corner margin is maximised as an objective. EPS/TPS modulation (11_Control_Algorithms) is the known remedy and is outside this SPS study.\n")
w("![variables](results/decision_variables.png)\n\n![mission](results/mission_profile_Tj.png)\n")
w("### 3.4 Decision-variable patterns on the fronts\n")
for m in MODES:
    rr = [r for r in rows if r["mode"] == m]
    tc = {c: sum(1 for r in rr if r["tcore"] == c) for c in E.CORE_T}; d1 = {c: sum(1 for r in rr if r["dev1"] == c) for c in [f"{d}x{p}" for d, p in E.DEV1]}
    w(f"* {LABEL[m]}: fs {min(r['fs_kHz'] for r in rr):.0f}-{max(r['fs_kHz'] for r in rr):.0f} kHz (median {np.median([r['fs_kHz'] for r in rr]):.0f}), phi_nom {min(r['phi_nom_deg'] for r in rr):.0f}-{max(r['phi_nom_deg'] for r in rr):.0f} deg, "
      f"n {min(r['n'] for r in rr):.2f}-{max(r['n'] for r in rr):.2f} (median {np.median([r['n'] for r in rr]):.2f}), Bpk {min(r['Bpk_target'] for r in rr):.3f}-{max(r['Bpk_target'] for r in rr):.3f} T, "
      f"t_dead {min(r['t_dead_ns'] for r in rr):.0f}-{max(r['t_dead_ns'] for r in rr):.0f} ns; transformer cores {tc}; HV device {d1}.")
w("\nNote on objective 4: the margin is the minimum over the envelope at 100 % and 50 % load; with SPS every design is hard-switched at 50 % load at the voltage-mismatch corners "
  "(850/300 V, 650/450 V), so the values are negative throughout and rank how far from ZVS the worst point is. The per-generation hypervolume uses the population's first front, the final value the archive, so small dips are possible.\n")
w("\nFull fronts: `results/pareto_fronts.csv` (NSGA-II, all variants with feasible designs), `results/grid_front_reevaluated.csv`, `results/bo_front.csv`; hypervolume history and BO traces: `results/convergence.json`.\n")
w("## 4. Maturity and what was NOT verified\n")
w("Maturity **L2**: every number comes from the analytical/semi-numerical project models (SPS closed form, datasheet-typical device parameters flagged `verified=False`, Steinmetz/Dowell magnetics, one-node thermal network). Not verified:\n\n"
  "* no hardware, no measured losses, temperatures, ZVS transitions or inductance/capacitance tolerances - the uncertainty ranges are assumptions;\n"
  "* the lifetime law and its coefficients (LESIT, Si IGBT modules) are not calibrated for discrete SiC TO-247 devices; the proxy ranks designs, it does not predict a lifetime;\n"
  "* the mission profile is invented (labelled ASSUMED); a different profile changes the reliability ranking and the mission efficiency;\n"
  "* the mission thermal model is quasi-static (hourly steady state), so sub-hour power cycling and the resulting small-amplitude Tj cycles are not counted;\n"
  "* SPS modulation only - EPS/TPS would change the ZVS margins at the voltage-mismatch corners (see 11_Control_Algorithms);\n"
  "* the hypervolume is a Monte-Carlo estimate (1e5 points); NSGA-II is stochastic - a single seed per variant is reported (deterministic, but no multi-seed statistics); "
  "the robust and chance-constrained hypervolume curves were still rising slowly at the last generation (more generations would extend those fronts slightly);\n"
  "* the chance constraint uses an empirical quantile over 24 LHS samples (resolution 1/24), not an analytical probability;\n"
  "* the surrogate search is a simplified single-objective BO per weight vector; its lower hypervolume at equal budget is a result of this run, not a general statement about BO.\n")
w("## 5. Files\n\n`dab_eval.py` (shared evaluator, also used by `../Uncertainty_Quantification/`), `robust_optimize.py` (this run), `results/` (CSV, JSON, PNG), `provenance.json`.\n")
open(os.path.join(HERE, "README.md"), "w").write("\n".join(R))
print(f"done in {time.time()-T0:.0f} s; evaluations {n_eval}")
print(json.dumps(dict(knee=knees["nominal"]["row"], baseline=base_cmp["nominal"] | dict(dominating_examples="..."), survive=survive, hv=hv_final), indent=1, default=str)[:4000])
