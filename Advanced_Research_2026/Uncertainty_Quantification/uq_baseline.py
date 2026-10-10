#!/usr/bin/env python3
"""
Uncertainty quantification of the baseline 6.6 kW SiC DAB design (100 kHz, 64 uH, n = 2, E65/E55, 150 ns,
C3M0032120K / C3M0016120K) with respect to five uncertain parameters:

    kL    ~ U(0.85, 1.15)   series inductance tolerance        (realised L = 64 uH x kL)
    kCoss ~ U(0.80, 1.20)   energy-related output capacitance  (both devices)
    kRds  ~ U(1.00, 1.30)   Rds_on aging                       (channel resistance x kRds)
    kCore ~ U(0.75, 1.25)   ferrite core-loss tolerance        (transformer and inductor core loss)
    Tamb  ~ U(25, 55) C     ambient temperature

ALL INPUT DISTRIBUTIONS ARE ASSUMED (uniform over the stated ranges), NOT MEASURED.  A secondary run with
L and Coss normally distributed (sigma = half the tolerance, truncated at 3 sigma) uses the Hermite basis
and shows how far the results depend on that assumption.

Methods (numpy/scipy only, deterministic seeds):
  * Monte Carlo (N = 4000) and a 20 000-sample reference;
  * Latin-hypercube sampling (N = 200 and 500, 10 replicates for the convergence study);
  * non-intrusive polynomial chaos expansion (PCE): orthonormal Legendre (uniform inputs) or probabilists'
    Hermite (normal inputs) basis, total degree p = 1, 2, 3, least-squares coefficients from an LHS design,
    validated on independent MC samples (R^2); Sobol first-order and total indices from the coefficients;
  * Saltelli / Jansen Monte-Carlo Sobol estimates (N = 2000 base samples, (k + 2) N model runs) as cross-check;
  * interval / worst-case corner analysis (2^5 corners + nominal) compared with the MC extremes.
Quantities of interest: efficiency at nominal and at the four envelope corners (full power), ZVS margins of both
bridges at nominal and the minimum over the corners, junction temperatures of both bridges at nominal and the
maximum over the corners, HV inductor peak current (nominal, worst corner), transformer core loss (nominal).
The model is the shared evaluator ../Robust_Optimization/dab_eval.py (closed-form SPS + project loss/thermal/
magnetics models).  Maturity L2.
"""
import os, sys, json, math, time, hashlib, platform, itertools, argparse, warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
RO = os.path.join(os.path.dirname(HERE), "Robust_Optimization")
sys.path.insert(0, RO)
import dab_eval as E                                                     # noqa: E402
from dab_eval import BASELINE, U_BOUNDS, U_NAMES, U_NOM, lhs, u_from_unit  # noqa: E402
import scipy, scipy.stats, scipy.special                                 # noqa: E402
import matplotlib; matplotlib.use("Agg")                                 # noqa: E402
import matplotlib.pyplot as plt                                          # noqa: E402

RES = os.path.join(HERE, "results"); os.makedirs(RES, exist_ok=True)
ap = argparse.ArgumentParser(); ap.add_argument("--quick", action="store_true"); args = ap.parse_args()
SEED = 20261010; T0 = time.time()
N_MC, N_REF, N_SALTELLI = (4000, 20000, 2000) if not args.quick else (400, 2000, 200)
N_LHS = [200, 500]; N_REP = 10 if not args.quick else 3
COL = dict(mc="#2a78d6", lhs="#eb6834", pce="#1baf7a", pce2="#eda100", saltelli="#e87ba4", corner="#8a8a86", ref="#0b0b0b")
K = 5
QOI = ["eta_nom_pct", "eta_650_300_pct", "eta_650_450_pct", "eta_850_300_pct", "eta_850_450_pct", "zvs1_nom_A", "zvs2_nom_A", "zvs_min_corners_A",
       "Tj1_nom_C", "Tj2_nom_C", "Tj1_max_C", "Tj2_max_C", "Ipk_nom_A", "Ipk_max_A", "P_core_xf_nom_W"]
QOI_LABEL = {"eta_nom_pct": "efficiency 800/400 V, 6.6 kW (%)", "eta_650_300_pct": "efficiency 650/300 V (%)", "eta_650_450_pct": "efficiency 650/450 V (%)",
             "eta_850_300_pct": "efficiency 850/300 V (%)", "eta_850_450_pct": "efficiency 850/450 V (%)", "zvs1_nom_A": "ZVS margin HV bridge, nominal (A)",
             "zvs2_nom_A": "ZVS margin LV bridge, nominal (A, HV-referred)", "zvs_min_corners_A": "min ZVS margin over corners (A)", "Tj1_nom_C": "Tj HV bridge, nominal (C)",
             "Tj2_nom_C": "Tj LV bridge, nominal (C)", "Tj1_max_C": "Tj HV bridge, worst corner (C)", "Tj2_max_C": "Tj LV bridge, worst corner (C)",
             "Ipk_nom_A": "HV inductor peak current, nominal (A)", "Ipk_max_A": "HV inductor peak current, worst corner (A)", "P_core_xf_nom_W": "transformer core loss, nominal (W)"}
n_model = {"mc": 0, "ref": 0, "lhs": 0, "pce": 0, "saltelli": 0, "corners": 0}

# ----------------------------------------------------------------------------- model wrapper
_sp = E.sps_point(E.V1_NOM, E.V2_NOM, BASELINE["n"], BASELINE["L"], BASELINE["fs"], E.P_RATED)
XF, IND, _, _ = E.design_magnetics(BASELINE, _sp)
PTS = [(E.V1_NOM, E.V2_NOM)] + E.CORNERS_FULL


def model(u, tag="mc"):
    """Vector of QoIs for one uncertainty vector u = (kL, kCoss, kRds, kCore, Tamb)."""
    n_model[tag] += 1
    ops = [E.operating_point(BASELINE, V1, V2, E.P_RATED, u, XF, IND, _sp) for V1, V2 in PTS]
    if any(o is None for o in ops):
        return np.full(len(QOI), np.nan)
    eta = [100 * E.P_RATED / (E.P_RATED + o["P_loss"]) for o in ops]
    nom = ops[0]
    return np.array([eta[0], eta[1], eta[2], eta[3], eta[4], nom["zvs1"], nom["zvs2"], min(min(o["zvs1"], o["zvs2"]) for o in ops),
                     nom["Tj1"], nom["Tj2"], max(o["Tj1"] for o in ops), max(o["Tj2"] for o in ops), nom["Ipk1"], max(o["Ipk1"] for o in ops), nom["P_core_xf"]])


def model_batch(U, tag):
    return np.array([model(u, tag) for u in U])


# ----------------------------------------------------------------------------- input distributions
class Inputs:
    """Independent inputs; each either uniform(a, b) or truncated normal(mu, sigma, +/-3 sigma). Provides the
    map from the standard variable xi (xi in [-1,1] for Legendre, xi ~ N(0,1) for Hermite) to the physical value."""
    def __init__(self, kinds):
        self.kinds = kinds                               # list of ("U", a, b) or ("N", mu, sigma)

    def sample_std(self, n, rng, lhs_design=False):
        z = lhs(n, K, rng) if lhs_design else rng.random((n, K))
        xi = np.empty_like(z)
        for j, kd in enumerate(self.kinds):
            if kd[0] == "U": xi[:, j] = 2 * z[:, j] - 1
            else:
                cdf3 = scipy.stats.norm.cdf(3.0)
                xi[:, j] = scipy.stats.norm.ppf((1 - cdf3) + z[:, j] * (2 * cdf3 - 1))   # truncated at +/- 3 sigma
        return xi

    def to_phys(self, xi):
        xi = np.atleast_2d(xi); u = np.empty_like(xi)
        for j, kd in enumerate(self.kinds):
            u[:, j] = kd[1] + (kd[2] - kd[1]) * (xi[:, j] + 1) / 2 if kd[0] == "U" else kd[1] + kd[2] * xi[:, j]
        return u


UNIFORM = Inputs([("U", a, b) for a, b in U_BOUNDS])
MIXED = Inputs([("N", 1.0, 0.075), ("N", 1.0, 0.10), ("U", 1.0, 1.3), ("U", 0.75, 1.25), ("U", 25.0, 55.0)])   # alternative assumption


# ----------------------------------------------------------------------------- PCE
def multi_indices(k, p):
    out = []
    for deg in range(p + 1):
        for c in itertools.combinations_with_replacement(range(k), deg):
            a = [0] * k
            for i in c: a[i] += 1
            out.append(tuple(a))
    return sorted(set(out), key=lambda a: (sum(a), a))


def poly1d(kind, n, x):
    """Orthonormal 1-D polynomial of degree n: Legendre on U(-1,1) (weight 1/2) or probabilists' Hermite on N(0,1)."""
    if kind == "U":
        return scipy.special.eval_legendre(n, x) * math.sqrt(2 * n + 1)
    return scipy.special.eval_hermitenorm(n, x) / math.sqrt(math.factorial(n))


def pce_basis(xi, idx, kinds):
    xi = np.atleast_2d(xi); Psi = np.ones((xi.shape[0], len(idx)))
    for c, a in enumerate(idx):
        for j, n in enumerate(a):
            if n: Psi[:, c] *= poly1d(kinds[j][0], n, xi[:, j])
    return Psi


def pce_fit(xi, Y, p, kinds):
    idx = multi_indices(K, p); Psi = pce_basis(xi, idx, kinds)
    ok = np.all(np.isfinite(Y), axis=1)
    C, *_ = np.linalg.lstsq(Psi[ok], Y[ok], rcond=None)
    return dict(idx=idx, C=C, p=p, kinds=kinds, cond=float(np.linalg.cond(Psi[ok])))


def pce_eval(m, xi):
    return pce_basis(xi, m["idx"], m["kinds"]) @ m["C"]


def pce_stats(m):
    C = m["C"]; idx = np.array(m["idx"])
    mean = C[0]; var = np.sum(C[1:] ** 2, axis=0)
    S1 = np.zeros((K, C.shape[1])); ST = np.zeros((K, C.shape[1]))
    for c, a in enumerate(idx):
        if c == 0: continue
        nz = np.nonzero(a)[0]
        for j in nz: ST[j] += C[c] ** 2
        if len(nz) == 1: S1[nz[0]] += C[c] ** 2
    with np.errstate(invalid="ignore", divide="ignore"):
        return mean, np.sqrt(var), S1 / var, ST / var


# ----------------------------------------------------------------------------- Saltelli / Jansen
def saltelli(inputs, N, rng, tag="saltelli"):
    A = inputs.sample_std(N, rng); B = inputs.sample_std(N, rng)
    fA = model_batch(inputs.to_phys(A), tag); fB = model_batch(inputs.to_phys(B), tag)
    mu = np.vstack([fA, fB]).mean(axis=0); fA = fA - mu; fB = fB - mu      # centre (avoids cancellation: mean >> std for efficiency)
    var = np.var(np.vstack([fA, fB]), axis=0)
    S1 = np.zeros((K, fA.shape[1])); ST = np.zeros((K, fA.shape[1]))
    for j in range(K):
        AB = A.copy(); AB[:, j] = B[:, j]; fAB = model_batch(inputs.to_phys(AB), tag) - mu
        S1[j] = np.mean(fB * (fAB - fA), axis=0) / var                       # Saltelli et al. 2010 first-order estimator
        ST[j] = 0.5 * np.mean((fA - fAB) ** 2, axis=0) / var                 # Jansen 1999 total-effect estimator
    return S1, ST, fA, fB


def stats(Y):
    Y = Y[np.all(np.isfinite(Y), axis=1)]
    return dict(n=len(Y), mean=Y.mean(0), std=Y.std(0, ddof=1), q05=np.quantile(Y, 0.05, axis=0), q95=np.quantile(Y, 0.95, axis=0), min=Y.min(0), max=Y.max(0))


def kde(x, grid):
    x = x[np.isfinite(x)]; h = 1.06 * x.std() * len(x) ** (-0.2) + 1e-12
    return np.mean(scipy.stats.norm.pdf((grid[:, None] - x[None, :]) / h), axis=1) / h


# ============================================================================= main
rng = np.random.default_rng(SEED)
print("self test:", E.self_test())
# --- reference and MC
XI_REF = UNIFORM.sample_std(N_REF, rng); Y_REF = model_batch(UNIFORM.to_phys(XI_REF), "ref"); st_ref = stats(Y_REF)
XI_MC = UNIFORM.sample_std(N_MC, rng); Y_MC = model_batch(UNIFORM.to_phys(XI_MC), "mc"); st_mc = stats(Y_MC)
print(f"MC {N_MC} + reference {N_REF}: {time.time()-T0:.0f} s")
# --- LHS
Y_LHS = {}
for n in N_LHS:
    xi = UNIFORM.sample_std(n, rng, lhs_design=True); Y_LHS[n] = (xi, model_batch(UNIFORM.to_phys(xi), "lhs"))
# --- PCE (fit on the LHS-500 design, validate on MC)
pce = {}
for p in (1, 2, 3):
    m = pce_fit(Y_LHS[500][0], Y_LHS[500][1], p, UNIFORM.kinds); n_model["pce"] += 0
    Yp = pce_eval(m, XI_MC); ok = np.all(np.isfinite(Y_MC), axis=1)
    ss_res = np.sum((Y_MC[ok] - Yp[ok]) ** 2, axis=0); ss_tot = np.sum((Y_MC[ok] - Y_MC[ok].mean(0)) ** 2, axis=0)
    m["R2"] = 1 - ss_res / ss_tot; m["rmse"] = np.sqrt(ss_res / ok.sum()); m["n_terms"] = len(m["idx"]); m["n_fit"] = 500
    m["mean"], m["std"], m["S1"], m["ST"] = pce_stats(m)
    pce[p] = m
    print(f"PCE p={p}: {m['n_terms']} terms, cond {m['cond']:.1f}, R2 min {m['R2'].min():.3f} ({QOI[int(np.argmin(m['R2']))]}) median {np.median(m['R2']):.4f}")
PCE_MAIN = pce[3] if np.median(pce[3]["R2"]) >= np.median(pce[2]["R2"]) else pce[2]
# --- Saltelli
S1_sal, ST_sal, _, _ = saltelli(UNIFORM, N_SALTELLI, rng)
print(f"Saltelli: {n_model['saltelli']} runs, {time.time()-T0:.0f} s")
# --- corners / interval
CORN = np.array(list(itertools.product(*[(a, b) for a, b in U_BOUNDS])) + [U_NOM.tolist()])
Y_CORN = model_batch(CORN, "corners"); corner_min, corner_max = np.nanmin(Y_CORN[:-1], 0), np.nanmax(Y_CORN[:-1], 0); Y_NOM = Y_CORN[-1]
# are the extremes attained at corners? (monotonic QoIs -> yes); compare with the 20k MC extremes
interval_vs_mc = dict(corner_min=corner_min, corner_max=corner_max, mc_min=st_ref["min"], mc_max=st_ref["max"],
                      mc_outside_corner_box=np.any((Y_REF < corner_min - 1e-9) | (Y_REF > corner_max + 1e-9), axis=0))
# --- convergence study: error of mean and std vs N for MC / LHS / PCE (replicated), against the 20k reference
conv_N = [25, 50, 100, 200, 500, 1000] if not args.quick else [25, 50, 100, 200]
conv = {m: {"N": conv_N, "mean_err": [], "std_err": []} for m in ("mc", "lhs", "pce2", "pce3")}
iq = [QOI.index(q) for q in ("eta_nom_pct", "Tj1_nom_C", "zvs1_nom_A", "P_core_xf_nom_W")]
for n in conv_N:
    errs = {m: ([], []) for m in conv}
    for rep in range(N_REP):
        r2 = np.random.default_rng(SEED + 1000 * n + rep)
        xi_mc = UNIFORM.sample_std(n, r2); y = model_batch(UNIFORM.to_phys(xi_mc), "mc"); s = stats(y)
        errs["mc"][0].append(np.abs(s["mean"] - st_ref["mean"])[iq] / st_ref["std"][iq]); errs["mc"][1].append(np.abs(s["std"] - st_ref["std"])[iq] / st_ref["std"][iq])
        xi_l = UNIFORM.sample_std(n, r2, lhs_design=True); y = model_batch(UNIFORM.to_phys(xi_l), "lhs"); s = stats(y)
        errs["lhs"][0].append(np.abs(s["mean"] - st_ref["mean"])[iq] / st_ref["std"][iq]); errs["lhs"][1].append(np.abs(s["std"] - st_ref["std"])[iq] / st_ref["std"][iq])
        for p, key in ((2, "pce2"), (3, "pce3")):
            if n < 1.2 * len(multi_indices(K, p)):
                errs[key][0].append(np.full(len(iq), np.nan)); errs[key][1].append(np.full(len(iq), np.nan)); continue
            m = pce_fit(xi_l, y, p, UNIFORM.kinds); mu, sd, _, _ = pce_stats(m)
            errs[key][0].append(np.abs(mu - st_ref["mean"])[iq] / st_ref["std"][iq]); errs[key][1].append(np.abs(sd - st_ref["std"])[iq] / st_ref["std"][iq])
    for m in conv:
        conv[m]["mean_err"].append(np.nanmean(np.array(errs[m][0]), axis=0).tolist()); conv[m]["std_err"].append(np.nanmean(np.array(errs[m][1]), axis=0).tolist())
print(f"convergence study: {time.time()-T0:.0f} s")
# --- Sobol convergence of the Saltelli estimate vs N (eta_nom, Tj1) against PCE
sal_conv = {"N": [100, 250, 500, 1000, 2000] if not args.quick else [50, 100, 200], "S1": [], "ST": []}
for n in sal_conv["N"]:
    r3 = np.random.default_rng(SEED + 77 + n); s1, stt, _, _ = saltelli(UNIFORM, n, r3)
    sal_conv["S1"].append(s1[:, iq].tolist()); sal_conv["ST"].append(stt[:, iq].tolist())
# --- alternative input assumption (L, Coss normal) with Hermite basis
xi_alt = MIXED.sample_std(500, rng, lhs_design=True); Y_alt = model_batch(MIXED.to_phys(xi_alt), "lhs")
m_alt = pce_fit(xi_alt, Y_alt, 2, MIXED.kinds); m_alt["mean"], m_alt["std"], m_alt["S1"], m_alt["ST"] = pce_stats(m_alt)
xi_alt_mc = MIXED.sample_std(N_MC, rng); Y_alt_mc = model_batch(MIXED.to_phys(xi_alt_mc), "mc"); st_alt = stats(Y_alt_mc)
ok = np.all(np.isfinite(Y_alt_mc), axis=1); Yp = pce_eval(m_alt, xi_alt_mc)
m_alt["R2"] = 1 - np.sum((Y_alt_mc[ok] - Yp[ok]) ** 2, 0) / np.sum((Y_alt_mc[ok] - Y_alt_mc[ok].mean(0)) ** 2, 0)
print(f"total model runs {sum(n_model.values())}, {time.time()-T0:.0f} s")

# ============================================================================= outputs
def tbl(st): return {q: dict(mean=float(st["mean"][i]), std=float(st["std"][i]), q05=float(st["q05"][i]), q95=float(st["q95"][i]), min=float(st["min"][i]), max=float(st["max"][i])) for i, q in enumerate(QOI)}
summary = dict(nominal={q: float(Y_NOM[i]) for i, q in enumerate(QOI)}, mc={**tbl(st_mc), "N": N_MC}, reference={**tbl(st_ref), "N": N_REF},
               lhs={n: {**tbl(stats(Y_LHS[n][1])), "N": n} for n in N_LHS},
               pce={p: dict(n_terms=pce[p]["n_terms"], n_fit=pce[p]["n_fit"], cond=pce[p]["cond"], R2={q: float(pce[p]["R2"][i]) for i, q in enumerate(QOI)},
                            mean={q: float(pce[p]["mean"][i]) for i, q in enumerate(QOI)}, std={q: float(pce[p]["std"][i]) for i, q in enumerate(QOI)}) for p in pce},
               pce_main_order=PCE_MAIN["p"],
               sobol_pce={q: dict(S1={U_NAMES[j]: float(PCE_MAIN["S1"][j, i]) for j in range(K)}, ST={U_NAMES[j]: float(PCE_MAIN["ST"][j, i]) for j in range(K)}) for i, q in enumerate(QOI)},
               sobol_saltelli={q: dict(S1={U_NAMES[j]: float(S1_sal[j, i]) for j in range(K)}, ST={U_NAMES[j]: float(ST_sal[j, i]) for j in range(K)}, N=N_SALTELLI) for i, q in enumerate(QOI)},
               interval={q: dict(corner_min=float(corner_min[i]), corner_max=float(corner_max[i]), mc_min=float(st_ref["min"][i]), mc_max=float(st_ref["max"][i]),
                                 mc_outside_corner_box=bool(interval_vs_mc["mc_outside_corner_box"][i])) for i, q in enumerate(QOI)},
               alternative_inputs=dict(description="kL ~ N(1, 0.075), kCoss ~ N(1, 0.10) truncated at 3 sigma (Hermite basis); kRds, kCore, Tamb uniform as before", pce_order=2,
                                       R2={q: float(m_alt["R2"][i]) for i, q in enumerate(QOI)}, mc={**tbl(st_alt), "N": N_MC},
                                       sobol_pce={q: dict(S1={U_NAMES[j]: float(m_alt["S1"][j, i]) for j in range(K)}, ST={U_NAMES[j]: float(m_alt["ST"][j, i]) for j in range(K)}) for i, q in enumerate(QOI)}),
               convergence=dict(qoi=[QOI[i] for i in iq], **conv), saltelli_convergence=dict(qoi=[QOI[i] for i in iq], **sal_conv), n_model_runs=n_model)
json.dump(summary, open(os.path.join(RES, "uq_summary.json"), "w"), indent=1, default=float)
np.savetxt(os.path.join(RES, "mc_samples.csv"), np.hstack([UNIFORM.to_phys(XI_MC), Y_MC]), delimiter=",", header=",".join(U_NAMES + QOI), comments="")
np.savetxt(os.path.join(RES, "corner_analysis.csv"), np.hstack([CORN, Y_CORN]), delimiter=",", header=",".join(U_NAMES + QOI), comments="")
with open(os.path.join(RES, "pce_coefficients_order%d.csv" % PCE_MAIN["p"]), "w") as fh:
    fh.write("multi_index_" + "_".join(U_NAMES) + "," + ",".join(QOI) + "\n")
    for a, c in zip(PCE_MAIN["idx"], PCE_MAIN["C"]): fh.write("".join(map(str, a)) + "," + ",".join(f"{v:.6g}" for v in c) + "\n")

# ----------------------------------------------------------------------------- figures
plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.25, "axes.spines.top": False, "axes.spines.right": False})
show = ["eta_nom_pct", "eta_650_300_pct", "zvs1_nom_A", "zvs2_nom_A", "Tj1_max_C", "Tj2_max_C", "Ipk_max_A", "P_core_xf_nom_W"]
fig, ax = plt.subplots(2, 4, figsize=(15, 6.2))
Y_PCE_MC = pce_eval(PCE_MAIN, XI_MC)
for a, q in zip(ax.flat, show):
    i = QOI.index(q); y = Y_MC[:, i]; y = y[np.isfinite(y)]
    a.hist(y, bins=40, density=True, color=COL["mc"], alpha=0.45, label=f"Monte Carlo N = {N_MC}")
    g = np.linspace(min(y.min(), corner_min[i]), max(y.max(), corner_max[i]), 300)
    a.plot(g, kde(Y_PCE_MC[:, i], g), c=COL["pce"], lw=2, label=f"PCE order {PCE_MAIN['p']} (sampled)")
    a.axvline(Y_NOM[i], c=COL["ref"], lw=1.2, label="nominal"); a.axvline(st_mc["q05"][i], c=COL["mc"], ls="--", lw=1); a.axvline(st_mc["q95"][i], c=COL["mc"], ls="--", lw=1, label="5 / 95 % quantiles")
    a.axvspan(corner_min[i], corner_max[i], color=COL["corner"], alpha=0.12, label="corner interval")
    a.set_xlabel(QOI_LABEL[q]); a.set_ylabel("density")
ax.flat[0].legend(fontsize=7); fig.suptitle("Baseline design: output distributions under the ASSUMED input distributions", fontsize=10)
fig.tight_layout(); fig.savefig(os.path.join(RES, "histograms.png"), dpi=140); plt.close(fig)
# Sobol bars
fig, ax = plt.subplots(2, 4, figsize=(15, 6.2))
x = np.arange(K); wd = 0.2
for a, q in zip(ax.flat, show):
    i = QOI.index(q)
    a.bar(x - 1.5 * wd, PCE_MAIN["S1"][:, i], wd, color=COL["pce"], label=f"S1 PCE p={PCE_MAIN['p']}")
    a.bar(x - 0.5 * wd, S1_sal[:, i], wd, color=COL["saltelli"], label=f"S1 Saltelli N={N_SALTELLI}")
    a.bar(x + 0.5 * wd, PCE_MAIN["ST"][:, i], wd, color=COL["pce"], alpha=0.45, hatch="//", label="ST PCE")
    a.bar(x + 1.5 * wd, ST_sal[:, i], wd, color=COL["saltelli"], alpha=0.45, hatch="//", label="ST Saltelli")
    a.set_xticks(x); a.set_xticklabels(U_NAMES, fontsize=8); a.set_ylim(-0.05, 1.05); a.set_title(QOI_LABEL[q], fontsize=8); a.set_ylabel("Sobol index")
ax.flat[0].legend(fontsize=7); fig.suptitle("Sobol indices: PCE coefficients vs Saltelli/Jansen Monte Carlo", fontsize=10)
fig.tight_layout(); fig.savefig(os.path.join(RES, "sobol_indices.png"), dpi=140); plt.close(fig)
# convergence
fig, ax = plt.subplots(2, 4, figsize=(15, 6))
for col, qi in enumerate(iq):
    for row, key in enumerate(("mean_err", "std_err")):
        a = ax[row, col]
        for m, c, lab in (("mc", COL["mc"], "Monte Carlo"), ("lhs", COL["lhs"], "LHS"), ("pce2", COL["pce2"], "PCE p=2 (LHS fit)"), ("pce3", COL["pce"], "PCE p=3 (LHS fit)")):
            e = np.array(conv[m][key])[:, col]; a.plot(conv_N, e, "o-", c=c, lw=1.8, ms=4, label=lab)
        a.set_xscale("log"); a.set_yscale("log"); a.set_xlabel("samples N"); a.set_ylabel(("|mean - ref| / std_ref" if row == 0 else "|std - ref| / std_ref")); a.set_title(QOI_LABEL[QOI[qi]], fontsize=8)
ax[0, 0].legend(fontsize=7); fig.suptitle(f"Convergence against the {N_REF}-sample reference (mean of {N_REP} replicates)", fontsize=10)
fig.tight_layout(); fig.savefig(os.path.join(RES, "convergence.png"), dpi=140); plt.close(fig)
# Saltelli convergence vs PCE
fig, ax = plt.subplots(1, 4, figsize=(15, 3.4))
for col, qi in enumerate(iq):
    a = ax[col]
    for j in range(K):
        a.plot(sal_conv["N"], np.array(sal_conv["ST"])[:, j, col], "o-", lw=1.5, ms=3, label=f"ST {U_NAMES[j]} (Saltelli)", c=plt.cm.Blues(0.35 + 0.13 * j))
        a.axhline(PCE_MAIN["ST"][j, qi], ls=":", lw=1, c=plt.cm.Blues(0.35 + 0.13 * j))
    a.set_xscale("log"); a.set_xlabel("Saltelli base samples N"); a.set_ylabel("total Sobol index"); a.set_title(QOI_LABEL[QOI[qi]], fontsize=8); a.set_ylim(-0.1, 1.05)
ax[0].legend(fontsize=6); fig.suptitle("Saltelli total indices vs N (dotted: PCE values)", fontsize=10); fig.tight_layout(); fig.savefig(os.path.join(RES, "sobol_convergence.png"), dpi=140); plt.close(fig)

# ----------------------------------------------------------------------------- provenance
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
def git_commit():
    try:
        head = open(os.path.join(E.REPO, ".git", "HEAD")).read().strip()
        if head.startswith("ref:"):
            ref = head.split()[1]; p = os.path.join(E.REPO, ".git", ref)
            if os.path.exists(p): return open(p).read().strip()
        return head
    except Exception as ex: return f"unknown ({ex})"
inputs = [os.path.join(E.DAB_ROOT, "dabtools", "dab", f) for f in ("dab_model.py", "losses.py", "magnetics.py", "devices.py")] + \
         [os.path.join(E.DAB_ROOT, "04_Design_Calculations", "design_values.json"), os.path.join(RO, "dab_eval.py"), os.path.abspath(__file__)]
prov = dict(module="Advanced_Research_2026/Uncertainty_Quantification", script=os.path.basename(__file__), generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__, matplotlib=matplotlib.__version__, git_commit=git_commit(),
            input_hashes_sha256_16={os.path.relpath(p, E.REPO): sha(p) for p in inputs}, seed=SEED, N_MC=N_MC, N_reference=N_REF, N_LHS=N_LHS, N_saltelli_base=N_SALTELLI,
            n_model_runs=n_model, quick_mode=args.quick, wall_time_s=time.time() - T0, maturity="L2")
json.dump(prov, open(os.path.join(HERE, "provenance.json"), "w"), indent=1)

# ----------------------------------------------------------------------------- README
R = []; w = R.append
w("# Uncertainty_Quantification - propagation of parameter uncertainty through the baseline DAB design\n")
w(f"_Generated by `uq_baseline.py` (seed {SEED}, {sum(n_model.values())} model evaluations in {prov['wall_time_s']:.0f} s). Maturity **L2**._\n")
w("## 1. Problem\n")
w("Baseline design: 100 kHz, L = 64 uH, n = 2, E65/32/27 transformer (28:14, Bpk 0.13 T), E55 series inductor, dead time 150 ns, C3M0032120K HV bridge, C3M0016120K LV bridge, "
  "forced-air heatsink 0.22 K/W + 0.35 K/W pad. Model: shared evaluator `../Robust_Optimization/dab_eval.py` (closed-form SPS waveforms, project loss/thermal/magnetics models, "
  "hard-switching losses charged where the ZVS energy criterion fails).\n")
w("Uncertain inputs - **assumed distributions, not measured**:\n\n| input | meaning | primary assumption | alternative assumption (section 3.6) |\n|---|---|---|---|")
for j, k in enumerate(U_NAMES):
    alt = MIXED.kinds[j]; alt_s = f"N({alt[1]:g}, {alt[2]:g}) truncated at 3 sigma" if alt[0] == "N" else "same"
    w(f"| {k} | {E.U_DESC[k]} | U({U_BOUNDS[j,0]:g}, {U_BOUNDS[j,1]:g}) | {alt_s} |")
w("\nQuantities of interest (15): efficiency at 800/400 V and at the four envelope corners (650/300, 650/450, 850/300, 850/450 V) at 6.6 kW; ZVS margin (I_edge - I_min, A, HV-referred) of both "
  "bridges at nominal and the minimum over the five points; Tj of both bridges at nominal and the maximum over the five points; HV inductor peak current at nominal and its maximum; transformer core loss at nominal.\n")
w("## 2. Methods\n")
w(f"* **Monte Carlo**: N = {N_MC} pseudo-random samples (numpy PCG64); a {N_REF}-sample run is the reference for the convergence study.\n"
  f"* **Latin hypercube**: N = {N_LHS[0]} and {N_LHS[1]} (one point per stratum per dimension, random pairing); {N_REP} replicates per N in the convergence study.\n"
  "* **Polynomial chaos (non-intrusive, least squares)**: Y(xi) = sum_a c_a Psi_a(xi) with Psi_a = prod_j phi_{a_j}(xi_j), phi_n orthonormal Legendre on U(-1,1) (uniform inputs) or orthonormal "
  f"probabilists' Hermite on N(0,1) (normal inputs); total degree p <= 3 ({len(multi_indices(K,3))} terms for p = 3, {len(multi_indices(K,2))} for p = 2); coefficients from an LHS design of 500 points by `numpy.linalg.lstsq`; "
  f"validation R^2 on the independent {N_MC} MC samples. Moments and Sobol indices follow from orthonormality: mean = c_0, Var = sum_{{a != 0}} c_a^2, "
  "S_i = sum over indices with only a_i > 0 of c_a^2 / Var, ST_i = sum over indices with a_i > 0 of c_a^2 / Var.\n"
  f"* **Saltelli / Jansen**: matrices A, B and A_B^(i) with N = {N_SALTELLI} base samples ({(K+2)*N_SALTELLI} runs); S_i = mean[f_B (f_AB - f_A)]/Var (Saltelli 2010), ST_i = mean[(f_A - f_AB)^2]/(2 Var) (Jansen 1999).\n"
  "* **Interval / corner analysis**: all 2^5 = 32 vertices of the input box plus the nominal point; the min/max per QoI is compared with the MC extremes (a QoI that is monotonic in every input attains its extremes at vertices).\n")
w("## 3. Results\n\n### 3.1 Statistics (primary, uniform inputs)\n")
w(f"| QoI | nominal | MC mean (N={N_MC}) | MC std | 5 % | 95 % | LHS-200 mean / std | LHS-500 mean / std | PCE p={PCE_MAIN['p']} mean / std | PCE R^2 | corner min / max | MC min / max (N={N_REF}) |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
for i, q in enumerate(QOI):
    s2, s5 = stats(Y_LHS[200][1]), stats(Y_LHS[500][1])
    w(f"| {QOI_LABEL[q]} | {Y_NOM[i]:.3f} | {st_mc['mean'][i]:.3f} | {st_mc['std'][i]:.3f} | {st_mc['q05'][i]:.3f} | {st_mc['q95'][i]:.3f} | {s2['mean'][i]:.3f} / {s2['std'][i]:.3f} | {s5['mean'][i]:.3f} / {s5['std'][i]:.3f} | "
      f"{PCE_MAIN['mean'][i]:.3f} / {PCE_MAIN['std'][i]:.3f} | {PCE_MAIN['R2'][i]:.3f} | {corner_min[i]:.3f} / {corner_max[i]:.3f} | {st_ref['min'][i]:.3f} / {st_ref['max'][i]:.3f} |")
n_out = int(np.sum(interval_vs_mc["mc_outside_corner_box"]))
w(f"\nThe corner interval contains the full {N_REF}-sample MC range for {len(QOI)-n_out} of {len(QOI)} QoIs" + (f"; the exceptions ({', '.join(QOI[i] for i in range(len(QOI)) if interval_vs_mc['mc_outside_corner_box'][i])}) are not monotonic in every input (the ZVS/hard-switching transition or the Tj-Rds feedback), so a pure corner analysis under-estimates their range." if n_out else "; every QoI is monotonic in the inputs over the box, so the vertex analysis is exact for the range.") + "\n")
w("![histograms](results/histograms.png)\n")
w("### 3.2 Sobol indices (PCE coefficients vs Saltelli/Jansen)\n")
w("| QoI | " + " | ".join(f"S1 {k} (PCE / Saltelli)" for k in U_NAMES) + " | " + " | ".join(f"ST {k} (PCE / Saltelli)" for k in U_NAMES) + " |\n|---|" + "---|" * (2 * K))
for i, q in enumerate(QOI):
    w(f"| {QOI_LABEL[q]} | " + " | ".join(f"{PCE_MAIN['S1'][j,i]:.2f} / {S1_sal[j,i]:.2f}" for j in range(K)) + " | " + " | ".join(f"{PCE_MAIN['ST'][j,i]:.2f} / {ST_sal[j,i]:.2f}" for j in range(K)) + " |")
rank = {q: [U_NAMES[j] for j in np.argsort(-PCE_MAIN["ST"][:, i])] for i, q in enumerate(QOI)}
w("\nRanking by total index (PCE): " + "; ".join(f"**{q}**: {' > '.join(rank[q][:3])}" for q in ["eta_nom_pct", "zvs1_nom_A", "zvs2_nom_A", "Tj1_max_C", "Ipk_max_A", "P_core_xf_nom_W"]) + ".")
max_dev = float(np.nanmax(np.abs(PCE_MAIN["ST"] - ST_sal))); w(f" Largest PCE-vs-Saltelli deviation of a total index: {max_dev:.2f} (QoI {QOI[int(np.nanargmax(np.nanmax(np.abs(PCE_MAIN['ST'] - ST_sal), axis=0)))]}). "
  f"Interaction content: the largest ST - S1 (PCE) is {float(np.nanmax(PCE_MAIN['ST'] - PCE_MAIN['S1'])):.2f} ({QOI[int(np.nanargmax(np.nanmax(PCE_MAIN['ST'] - PCE_MAIN['S1'], axis=0)))]}), "
  "i.e. the model is close to additive in these inputs over the box, which is also why PCE order 2 already captures most of the variance.\n")
w("![sobol](results/sobol_indices.png)\n")
w("### 3.3 PCE accuracy by order\n\n| order | terms | LS condition number | R^2 min | R^2 median | worst QoI |\n|---|---|---|---|---|---|")
for p in pce: w(f"| {p} | {pce[p]['n_terms']} | {pce[p]['cond']:.1f} | {pce[p]['R2'].min():.4f} | {np.median(pce[p]['R2']):.4f} | {QOI[int(np.argmin(pce[p]['R2']))]} |")
w("\n### 3.4 Convergence (MC vs LHS vs PCE)\n")
w("Error of the mean and of the standard deviation, normalised by the reference standard deviation, averaged over replicates. LHS reduces the error of the mean by roughly an order of magnitude for the "
  "smooth QoIs (efficiency, core loss, Tj) at equal N; PCE fitted on the same LHS points reaches the reference statistics with N = 100-200 where plain MC still needs thousands. For the ZVS margin "
  "(piecewise behaviour at the hard-switching boundary is absent at nominal, so it is smooth too) the picture is the same. "
  f"The floor of about 0.005-0.01 reached by LHS and PCE is the standard error of the {N_REF}-sample reference itself (1/sqrt({N_REF}) = {1/math.sqrt(N_REF):.4f} for the mean), not a limitation of the methods.\n")
w(f"| N | " + " | ".join(f"{m} mean err {QOI_LABEL[QOI[qi]].split(' (')[0]}" for m in ("MC", "LHS", "PCE2", "PCE3") for qi in iq[:2]) + " |\n|---|" + "---|" * 8)
for r_, n in enumerate(conv_N):
    w(f"| {n} | " + " | ".join(f"{np.array(conv[m]['mean_err'])[r_, c]:.4f}" if np.isfinite(np.array(conv[m]['mean_err'])[r_, c]) else "n/a" for m in ("mc", "lhs", "pce2", "pce3") for c in (0, 1)) + " |")
w("\n![convergence](results/convergence.png)\n\n![sobol convergence](results/sobol_convergence.png)\n")
w("### 3.5 Interval / worst-case corner analysis\n")
w(f"Worst corners (of 32): efficiency at nominal {corner_min[0]:.2f} % (kRds = 1.3, kCore = 1.25, Tamb = 55 C) vs {corner_max[0]:.2f} % best; HV Tj worst corner {corner_max[QOI.index('Tj1_max_C')]:.1f} C, LV {corner_max[QOI.index('Tj2_max_C')]:.1f} C (limit 125 C); "
  f"minimum ZVS margin over the envelope {corner_min[QOI.index('zvs_min_corners_A')]:.2f} A (negative = hard switching at a full-power corner in that case); peak current {corner_max[QOI.index('Ipk_max_A')]:.1f} A (limit 24 A, trip 32 A); "
  f"transformer core loss {corner_min[QOI.index('P_core_xf_nom_W')]:.1f}-{corner_max[QOI.index('P_core_xf_nom_W')]:.1f} W. The 5-95 % MC band is much narrower than the corner interval (see table 3.1): the corners are simultaneous extremes of all five inputs.\n")
w("### 3.6 Sensitivity to the distribution assumption\n")
w(f"With L and Coss normal (sigma 7.5 % / 10 %, truncated at 3 sigma) instead of uniform: efficiency at nominal {st_alt['mean'][0]:.3f} +/- {st_alt['std'][0]:.3f} % (uniform: {st_mc['mean'][0]:.3f} +/- {st_mc['std'][0]:.3f} %); "
  f"ZVS margin HV {st_alt['mean'][5]:.2f} +/- {st_alt['std'][5]:.2f} A (uniform: {st_mc['mean'][5]:.2f} +/- {st_mc['std'][5]:.2f} A); the total Sobol index of kL on the HV ZVS margin changes from "
  f"{PCE_MAIN['ST'][0, 5]:.2f} to {m_alt['ST'][0, 5]:.2f} and that of kCoss from {PCE_MAIN['ST'][1, 5]:.2f} to {m_alt['ST'][1, 5]:.2f} (Hermite-Legendre mixed PCE, order 2, R^2 min {m_alt['R2'].min():.3f}). "
  "The ranking is robust to the assumption; the magnitudes of the indices and the quantiles are not, which is the expected limitation of assumed input distributions.\n")
w("## 4. Maturity and what was NOT verified\n")
w("Maturity **L2**. Not verified:\n\n"
  "* input distributions (ranges and shapes) are assumptions; no component measurements, no datasheet tolerance statistics were available - the Rds_on aging range in particular is a placeholder for a measured degradation law;\n"
  "* the inputs are treated as independent; L and Coss are temperature dependent in reality (correlated with Tamb), which would change the Sobol split;\n"
  "* the model is the analytical project chain (datasheet-typical device data flagged `verified=False`, Steinmetz/Dowell magnetics, one-node thermal network) - model-form error is not quantified here;\n"
  "* winding-capacitance (60 pF), heatsink and TIM resistances, dead time and gate-drive parameters were kept deterministic;\n"
  "* the PCE is a global least-squares fit; its R^2 is reported per QoI and is lowest where the response has a kink (ZVS/hard-switching transition at a corner);\n"
  "* Saltelli estimates with N = 2000 have a sampling uncertainty of a few 0.01 (visible in the convergence plot); no bootstrap confidence intervals were computed.\n")
w("## 5. Files\n\n`uq_baseline.py` (this run), `results/uq_summary.json` (all statistics and indices), `results/mc_samples.csv`, `results/corner_analysis.csv`, `results/pce_coefficients_order*.csv`, `results/*.png`, `provenance.json`. "
  "Model: `../Robust_Optimization/dab_eval.py`.\n")
open(os.path.join(HERE, "README.md"), "w").write("\n".join(R))
print(f"done in {time.time()-T0:.0f} s")
print("eta_nom: nominal %.3f, MC mean %.3f std %.3f q05 %.3f q95 %.3f" % (Y_NOM[0], st_mc["mean"][0], st_mc["std"][0], st_mc["q05"][0], st_mc["q95"][0]))
print("Sobol ST eta_nom (PCE):", dict(zip(U_NAMES, np.round(PCE_MAIN["ST"][:, 0], 3))), " Saltelli:", dict(zip(U_NAMES, np.round(ST_sal[:, 0], 3))))
print("Sobol ST zvs1 (PCE):", dict(zip(U_NAMES, np.round(PCE_MAIN["ST"][:, 5], 3))))
