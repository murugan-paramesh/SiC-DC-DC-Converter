#!/usr/bin/env python3
"""
Fair comparison of surrogate models for the DAB steady-state map.

Inputs  x = (V1, V2, phi, D1, D2)            [V, V, rad, -, -]
Outputs y = (P, I_rms1, I_peak1, m_zvs1, m_zvs2)   [W, A, A, A, A]   (HV-referred)
Ground truth: dabtools.dab.dab_model.DABPoint (numerical waveform model, N = 4000 samples/period)
with the project design values (L = 64 uH, n = 2, fs = 100 kHz, C3M0032120K / C3M0016120K
energy-related Coss, C_par) for the ZVS current thresholds I_min(V) of both bridges.

Models compared (all numpy / scipy, no ML frameworks):
  A1  analytical SPS closed form (Kheraluwala 1992) - evaluated with D1 = D2 = 1 regardless of the
      commanded inner duties (this is the firmware feed-forward model);
  A2  analytical piecewise-linear TPS solution (exact integration of di/dt = (v1 - v2')/L over the
      <= 8 edge-delimited segments of one period, the generalisation of the SPS formulas to EPS/DPS/TPS);
  P3  cubic polynomial least squares (56 monomials in the normalised inputs);
  LUT 5-D multilinear interpolation on the training grid (scipy RegularGridInterpolator);
  MLP 5-32-32-5 tanh network, Adam, own numpy back-propagation;
  PINN same network + physics losses: (i) SPS-limit anchor on collocation points with D1 = D2 = 1
      (targets from the closed form, also outside the training envelope), (ii) homogeneity
      P(kV1, kV2) = k^2 P, I(kV1, kV2) = k I, (iii) consistency inequalities implied by P = mean(v1 i):
      |P| <= V1 sqrt(D1) I_rms (Cauchy-Schwarz) and I_peak >= I_rms;
  HYB hybrid 'analytical SPS + MLP residual';
  GP  Gaussian-process regression, ARD RBF kernel + noise, hyper-parameters by maximum marginal
      likelihood (L-BFGS, scipy) on a subset, prediction on <= GP_MAX_TRAIN points.
Training sets: nested regular grids (needed for the LUT; the same points are given to every model).
Test set: random points inside the design envelope; extrapolation set: V1 = 600 V and V2 = 470 V.
Everything is deterministic (fixed seeds).  Run time: 5-10 minutes on one core (epochs and GP subset sizes were
chosen for that budget).
"""
import os, sys, json, math, time, hashlib, platform, importlib, datetime
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")          # one core, deterministic timing
import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DAB = os.path.join(REPO, "SiC_6k6_Industrial_DAB")
sys.path.insert(0, DAB)
from dabtools.dab.dab_model import DABPoint, sps_power, zvs_current_min      # noqa: E402
from dabtools.dab.devices import DEVICES                                    # noqa: E402
import matplotlib                                                           # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                             # noqa: E402

OUT = os.path.join(HERE, "results")
os.makedirs(OUT, exist_ok=True)
T0 = time.time()
SEED = 2026
DESIGN = os.path.join(DAB, "04_Design_Calculations", "design_values.json")
V = json.load(open(DESIGN))
L, n, fs = V["L"], V["spec"]["n"], V["spec"]["fs"]
C_par = V["C_par"]
Coss1 = DEVICES[V["dev1"]]["Coss_er"]
Coss2 = DEVICES[V["dev2"]]["Coss_er"]
W = 2 * math.pi * fs
NAMES = ["P", "I_rms1", "I_peak1", "m_zvs1", "m_zvs2"]
UNITS = ["W", "A", "A", "A", "A"]
LO = np.array([650.0, 300.0, math.radians(2.0), 0.55, 0.55])
HI = np.array([850.0, 450.0, math.radians(60.0), 1.0, 1.0])
GP_MAX_TRAIN = 1500
GP_MAX_HYP = 200
SPS_POOL = 3000


def imin1(V1):
    return zvs_current_min(Coss1, V1, L, C_par)


def imin2(V2):
    # LV bridge: energy criterion with the LV-referred inductance, result referred to the HV side
    # (reproduces Imin2 = 3.066 A of design_values.json at 400 V)
    return zvs_current_min(Coss2, n * V2, L, C_par * n ** 2)


# --------------------------------------------------------------------------- ground truth
def truth(x, N=4000):
    V1, V2, phi, D1, D2 = x
    p = DABPoint(V1, V2, n, L, fs, phi, D1, D2, N=N)
    return [p.P, p.I_rms1, p.I_peak1, p.zvs_margin(1, imin1(V1)), p.zvs_margin(2, imin2(V2))]


def truth_batch(X):
    return np.array([truth(x) for x in X])


# --------------------------------------------------------------------------- analytical models
def _v3(th, amp, D, shift):
    x = (th - shift) % (2 * math.pi); h = D * math.pi / 2
    if math.pi / 2 - h < x <= math.pi / 2 + h:
        return amp
    if 3 * math.pi / 2 - h < x <= 3 * math.pi / 2 + h:
        return -amp
    return 0.0


def analytic_tps(V1, V2, phi, D1, D2):
    """Exact piecewise-linear steady-state solution for arbitrary (phi, D1, D2)."""
    V2p = n * V2
    def edges(D, shift):
        return [(math.pi / 2 - D * math.pi / 2 + shift) % (2 * math.pi), (math.pi / 2 + D * math.pi / 2 + shift) % (2 * math.pi),
                (3 * math.pi / 2 - D * math.pi / 2 + shift) % (2 * math.pi), (3 * math.pi / 2 + D * math.pi / 2 + shift) % (2 * math.pi)]
    e1, e2 = edges(D1, 0.0), edges(D2, phi)
    br = sorted(set([0.0] + e1 + e2))
    br.append(2 * math.pi)
    segs = []
    for a, b in zip(br[:-1], br[1:]):
        if b - a < 1e-12:
            continue
        m = 0.5 * (a + b)
        va, vb = _v3(m, V1, D1, 0.0), _v3(m, V2p, D2, phi)
        segs.append((a, b, va, vb, (va - vb) / (W * L)))
    # current at breakpoints with i(0) = i0 unknown
    inc = [0.0]
    for a, b, va, vb, s in segs:
        inc.append(inc[-1] + s * (b - a))
    inc = np.array(inc[:-1])                 # value at segment starts relative to i0
    # zero mean: sum over segments of dth*(i_a + i_b)/2 = 0
    num = 0.0
    for k, (a, b, va, vb, s) in enumerate(segs):
        ia, ib = inc[k], inc[k] + s * (b - a)
        num += (b - a) * (ia + ib) / 2
    i0 = -num / (2 * math.pi)
    P = Irms2 = 0.0; Ipk = 0.0
    ipts = {}
    for k, (a, b, va, vb, s) in enumerate(segs):
        ia, ib = i0 + inc[k], i0 + inc[k] + s * (b - a)
        P += va * (b - a) * (ia + ib) / 2
        Irms2 += (b - a) * (ia * ia + ia * ib + ib * ib) / 3
        Ipk = max(Ipk, abs(ia), abs(ib))
        ipts[round(a, 12)] = ia
    ipts[round(2 * math.pi, 12)] = i0
    P /= 2 * math.pi; Irms = math.sqrt(Irms2 / (2 * math.pi))

    def i_at(th):
        th %= 2 * math.pi
        for k, (a, b, va, vb, s) in enumerate(segs):
            if a - 1e-12 <= th <= b + 1e-12:
                return i0 + inc[k] + s * (th - a)
        return i0

    margins = []
    for port, edges, amp, D, shift in ((1, e1, V1, D1, 0.0), (2, e2, V2p, D2, phi)):
        vals = []
        for th in edges:
            dv = _v3(th + 1e-9, amp, D, shift) - _v3(th - 1e-9, amp, D, shift)
            if abs(dv) < 1e-9:
                continue
            sgn = -1.0 if dv > 0 else 1.0
            if port == 2:
                sgn = -sgn
            vals.append(sgn * i_at(th))
        margins.append(min(vals) if vals else float("nan"))
    return [P, Irms, Ipk, margins[0] - imin1(V1), margins[1] - imin2(V2)]


def analytic_sps(V1, V2, phi, D1, D2):
    """SPS closed form (D1 = D2 = 1 assumed): the firmware feed-forward model."""
    return analytic_tps(V1, V2, phi, 1.0, 1.0)


def predict_analytic(fn, X):
    return np.array([fn(*x) for x in X])


# --------------------------------------------------------------------------- helpers
def norm_x(X):
    return 2 * (X - LO) / (HI - LO) - 1


def rmse(a, b):
    return np.sqrt(np.mean((a - b) ** 2, axis=0))


# --------------------------------------------------------------------------- polynomial
def poly_features(Xn, deg=3):
    cols = [np.ones(len(Xn))]
    d = Xn.shape[1]
    import itertools
    for k in range(1, deg + 1):
        for comb in itertools.combinations_with_replacement(range(d), k):
            cols.append(np.prod(Xn[:, comb], axis=1))
    return np.stack(cols, axis=1)


class Poly3:
    name = "P3 polynomial (deg 3)"

    def fit(self, X, Y, **kw):
        A = poly_features(norm_x(X)); self.mu, self.sd = Y.mean(0), Y.std(0) + 1e-12
        lam = 1e-8 * np.eye(A.shape[1])
        self.c = np.linalg.solve(A.T @ A + lam, A.T @ ((Y - self.mu) / self.sd))
        return self

    def predict(self, X):
        return poly_features(norm_x(X)) @ self.c * self.sd + self.mu

    ops = 56 * 5 * 2 + 56 * 3


# --------------------------------------------------------------------------- LUT
class LUT:
    name = "LUT multilinear"

    def fit(self, X, Y, axes=None, **kw):
        shape = tuple(len(a) for a in axes)
        self.f = [RegularGridInterpolator(axes, Y[:, j].reshape(shape), method="linear",
                                          bounds_error=False, fill_value=None) for j in range(Y.shape[1])]
        return self

    def predict(self, X):
        return np.stack([f(X) for f in self.f], axis=1)

    ops = 5 * 2 + 32 * 5 * 2 + 32 * 4            # index search, 32 corner weights x 5 outputs


# --------------------------------------------------------------------------- MLP
class MLP:
    name = "MLP 5-32-32-5"

    def __init__(self, nh=32, seed=SEED, epochs=1200, lr=3e-3, batch=256, physics=False, residual=None):
        self.nh, self.seed, self.epochs, self.lr, self.batch = nh, seed, epochs, lr, batch
        self.physics, self.residual = physics, residual
        if physics:
            self.name = "PINN (MLP + physics loss)"
        if residual is not None:
            self.name = "HYB analytical SPS + MLP residual"

    def _init(self, nin, nout):
        rng = np.random.default_rng(self.seed)
        s = lambda a, b: rng.normal(0, 1 / math.sqrt(a), (a, b))
        self.p = [s(nin, self.nh), np.zeros(self.nh), s(self.nh, self.nh), np.zeros(self.nh), s(self.nh, nout), np.zeros(nout)]
        self.m = [np.zeros_like(a) for a in self.p]; self.v = [np.zeros_like(a) for a in self.p]; self.t = 0
        return rng

    def _fwd(self, Xn):
        W1, b1, W2, b2, W3, b3 = self.p
        h1 = np.tanh(Xn @ W1 + b1); h2 = np.tanh(h1 @ W2 + b2)
        return h2 @ W3 + b3, (Xn, h1, h2)

    def _bwd(self, cache, dy):
        Xn, h1, h2 = cache
        W1, b1, W2, b2, W3, b3 = self.p
        gW3 = h2.T @ dy; gb3 = dy.sum(0)
        dh2 = (dy @ W3.T) * (1 - h2 ** 2)
        gW2 = h1.T @ dh2; gb2 = dh2.sum(0)
        dh1 = (dh2 @ W2.T) * (1 - h1 ** 2)
        gW1 = Xn.T @ dh1; gb1 = dh1.sum(0)
        return [gW1, gb1, gW2, gb2, gW3, gb3]

    def _adam(self, g):
        self.t += 1; b1, b2, eps = 0.9, 0.999, 1e-8
        for i in range(len(self.p)):
            self.m[i] = b1 * self.m[i] + (1 - b1) * g[i]
            self.v[i] = b2 * self.v[i] + (1 - b2) * g[i] ** 2
            mh = self.m[i] / (1 - b1 ** self.t); vh = self.v[i] / (1 - b2 ** self.t)
            self.p[i] -= self.lr * mh / (np.sqrt(vh) + eps)

    def _target(self, X, Y):
        if self.residual is not None:
            return Y - predict_analytic(self.residual, X)
        return Y

    def fit(self, X, Y, **kw):
        Yt = self._target(X, Y)
        self.mu, self.sd = Yt.mean(0), Yt.std(0) + 1e-9
        Xn, Yn = norm_x(X), (Yt - self.mu) / self.sd
        rng = self._init(Xn.shape[1], Yn.shape[1])
        N = len(Xn); nb = max(1, N // self.batch)
        self.hist = []
        for ep in range(self.epochs):
            lr0 = self.lr * (0.5 * (1 + math.cos(math.pi * ep / self.epochs)) * 0.9 + 0.1)
            self.lr_eff = lr0
            perm = rng.permutation(N)
            tot = 0.0
            for b in range(nb):
                idx = perm[b::nb]
                y, cache = self._fwd(Xn[idx])
                r = y - Yn[idx]
                loss = np.mean(r ** 2); tot += loss
                g = self._bwd(cache, 2 * r / r.size)
                if self.physics:
                    gp = self._physics_grad(rng)
                    g = [a + b_ for a, b_ in zip(g, gp)]
                lr_save = self.lr; self.lr = lr0; self._adam(g); self.lr = lr_save
            self.hist.append(tot / nb)
        return self

    # ---- physics losses (PINN) ----
    def _physics_grad(self, rng, Bc=128, w_sps=1.0, w_hom=0.3, w_ineq=0.3):
        g = [np.zeros_like(a) for a in self.p]
        # (i) SPS-limit anchor: D1 = D2 = 1 collocation points over a widened voltage range
        #     (fixed pool of SPS_POOL points generated once from the closed form; a random subset per step)
        if not hasattr(self, "_pool"):
            prng = np.random.default_rng(self.seed + 1)
            Xc = np.column_stack([prng.uniform(560, 940, SPS_POOL), prng.uniform(270, 480, SPS_POOL),
                                  prng.uniform(LO[2], HI[2], SPS_POOL), np.ones(SPS_POOL), np.ones(SPS_POOL)])
            Yc = predict_analytic(analytic_sps, Xc)
            if self.residual is not None:
                Yc = Yc - predict_analytic(self.residual, Xc)
            self._pool = (Xc, Yc)
        sel = rng.integers(0, SPS_POOL, Bc)
        Xc, Yc = self._pool[0][sel], self._pool[1][sel]
        Ycn = (Yc - self.mu) / self.sd
        y, cache = self._fwd(norm_x(Xc)); r = y - Ycn
        for i, gi in enumerate(self._bwd(cache, w_sps * 2 * r / r.size)):
            g[i] += gi
        # (ii) homogeneity in the voltages: y(kV1, kV2) = S_k y(V1, V2), S = (k^2, k, k, k, k)
        if self.residual is None:        # (the residual target is not homogeneous once the SPS part is removed; skipped)
            Xa = LO + rng.uniform(0, 1, (Bc, 5)) * (HI - LO)
            k = rng.uniform(0.85, 1.15, Bc)
            Xb = Xa.copy(); Xb[:, 0] *= k; Xb[:, 1] *= k
            S = np.column_stack([k ** 2, k, k, k, k])
            ya, ca = self._fwd(norm_x(Xa)); yb, cb = self._fwd(norm_x(Xb))
            fa = ya * self.sd + self.mu; fb = yb * self.sd + self.mu
            r = (fb - S * fa) / self.sd
            dfb = w_hom * 2 * r / r.size; dfa = -S * dfb
            for i, gi in enumerate(self._bwd(cb, dfb)):
                g[i] += gi
            for i, gi in enumerate(self._bwd(ca, dfa)):
                g[i] += gi
        # (iii) inequality consistency: |P| <= V1 sqrt(D1) I_rms ; I_peak >= I_rms (hinge^2)
        Xa = LO + rng.uniform(0, 1, (Bc, 5)) * (HI - LO)
        ya, ca = self._fwd(norm_x(Xa))
        base = predict_analytic(self.residual, Xa) if self.residual is not None else 0.0
        f = ya * self.sd + self.mu + base
        P, Ir, Ip = f[:, 0], f[:, 1], f[:, 2]
        g1 = np.maximum(0, np.abs(P) - Xa[:, 0] * np.sqrt(Xa[:, 3]) * Ir) / 1000.0
        g2 = np.maximum(0, Ir - Ip) / 10.0
        df = np.zeros_like(f)
        df[:, 0] = 2 * g1 * np.sign(P) / 1000.0
        df[:, 1] = -2 * g1 * Xa[:, 0] * np.sqrt(Xa[:, 3]) / 1000.0 + 2 * g2 / 10.0
        df[:, 2] = -2 * g2 / 10.0
        df = w_ineq * df * self.sd / Bc
        for i, gi in enumerate(self._bwd(ca, df)):
            g[i] += gi
        return g

    def predict(self, X):
        y, _ = self._fwd(norm_x(X))
        out = y * self.sd + self.mu
        if self.residual is not None:
            out = out + predict_analytic(self.residual, X)
        return out

    ops = 2 * (5 * 32 + 32 * 32 + 32 * 5) + 64 * 8     # MACs x2 + tanh (counted as 8 flops)


# --------------------------------------------------------------------------- GP
class GP:
    name = "GP (ARD RBF, ML-II)"

    def fit(self, X, Y, **kw):
        rng = np.random.default_rng(SEED)
        self.xm, self.xs = X.mean(0), X.std(0) + 1e-12
        self.mu, self.sd = Y.mean(0), Y.std(0) + 1e-12
        Xn, Yn = (X - self.xm) / self.xs, (Y - self.mu) / self.sd
        N = len(Xn)
        sel = rng.permutation(N)[:min(N, GP_MAX_TRAIN)]
        hyp_sel = sel[:min(len(sel), GP_MAX_HYP)]
        self.Xtr = Xn[sel]
        self.models = []
        for j in range(Y.shape[1]):
            th = self._optimise(Xn[hyp_sel], Yn[hyp_sel, j])
            K = self._k(self.Xtr, self.Xtr, th) + np.exp(2 * th[-1]) * np.eye(len(sel)) + 1e-8 * np.eye(len(sel))
            Lc = np.linalg.cholesky(K)
            alpha = np.linalg.solve(Lc.T, np.linalg.solve(Lc, Yn[sel, j]))
            self.models.append((th, alpha))
        self.n_train_used = len(sel)
        return self

    @staticmethod
    def _k(A, B, th):
        ls = np.exp(th[:5]); sf2 = np.exp(2 * th[5])
        d = (A[:, None, :] - B[None, :, :]) / ls
        return sf2 * np.exp(-0.5 * np.sum(d ** 2, axis=2))

    def _nlml(self, th, X, y):
        """Negative log marginal likelihood and its analytic gradient w.r.t. th = (log ls[5], log sf, log sn)."""
        N = len(X)
        ls = np.exp(th[:5]); sf2 = np.exp(2 * th[5]); sn2 = np.exp(2 * th[6])
        d = (X[:, None, :] - X[None, :, :]) / ls                 # N x N x 5
        Kf = sf2 * np.exp(-0.5 * np.sum(d ** 2, axis=2))
        K = Kf + (sn2 + 1e-8) * np.eye(N)
        try:
            Lc = np.linalg.cholesky(K)
        except np.linalg.LinAlgError:
            return 1e10, np.zeros_like(th)
        a = np.linalg.solve(Lc.T, np.linalg.solve(Lc, y))
        nlml = 0.5 * y @ a + np.sum(np.log(np.diag(Lc))) + 0.5 * N * math.log(2 * math.pi)
        Kinv = np.linalg.solve(Lc.T, np.linalg.solve(Lc, np.eye(N)))
        Wm = np.outer(a, a) - Kinv                                  # d nlml / d theta_j = -0.5 tr(W dK/dtheta_j)
        g = np.zeros_like(th)
        for j in range(5):
            g[j] = -0.5 * np.sum(Wm * (Kf * d[:, :, j] ** 2))
        g[5] = -0.5 * np.sum(Wm * (2 * Kf))
        g[6] = -0.5 * np.trace(Wm) * 2 * sn2
        return nlml, g

    def _optimise(self, X, y):
        th0 = np.array([0.0] * 5 + [0.0, math.log(0.05)])
        best = None
        for start in (th0,):                      # one start, 40 L-BFGS iterations: budget-limited (see README)
            r = minimize(self._nlml, start, args=(X, y), jac=True, method="L-BFGS-B",
                         bounds=[(-3, 4)] * 5 + [(-3, 3), (-6, 1)], options=dict(maxiter=40))
            if best is None or r.fun < best.fun:
                best = r
        return best.x

    def predict(self, X):
        Xn = (X - self.xm) / self.xs
        out = []
        for th, alpha in self.models:
            out.append(self._k(Xn, self.Xtr, th) @ alpha)
        return np.stack(out, axis=1) * self.sd + self.mu

    @property
    def ops(self):
        return self.n_train_used * (5 * 3 + 8 + 2) * 5


# --------------------------------------------------------------------------- data
def grid(nv1, nv2, nphi, nd1, nd2):
    axes = [np.linspace(LO[0], HI[0], nv1), np.linspace(LO[1], HI[1], nv2), np.linspace(LO[2], HI[2], nphi),
            np.linspace(LO[3], HI[3], nd1), np.linspace(LO[4], HI[4], nd2)]
    M = np.meshgrid(*axes, indexing="ij")
    X = np.column_stack([m.ravel() for m in M])
    return axes, X


def main():
    print("ground truth ...")
    rng = np.random.default_rng(SEED)
    grids = [(2, 2, 3, 2, 2), (3, 3, 4, 3, 3), (4, 4, 6, 3, 3), (5, 5, 8, 4, 4), (6, 6, 12, 4, 4)]
    train = []
    cache = {}
    for g in grids:
        axes, X = grid(*g)
        Y = np.array([cache.setdefault(tuple(np.round(x, 10)), truth(x)) for x in X])
        train.append((g, axes, X, Y))
        print(f"  grid {g}: {len(X)} points")
    Xte = LO + rng.uniform(0, 1, (2000, 5)) * (HI - LO)
    Yte = truth_batch(Xte)
    # extrapolation: V1 = 600 V (below the envelope) and V2 = 470 V (above the envelope)
    Xex = LO + rng.uniform(0, 1, (400, 5)) * (HI - LO)
    Xex[:200, 0] = 600.0; Xex[200:, 1] = 470.0
    Yex = truth_batch(Xex)
    t_truth = time.time() - T0
    print(f"  truth done in {t_truth:.1f} s")
    gfull = train[-1]
    np.savetxt(os.path.join(OUT, "ground_truth_grid_6x6x12x4x4.csv"), np.column_stack([gfull[2], gfull[3]]), delimiter=",",
               header="V1_V,V2_V,phi_rad,D1,D2,P_W,I_rms1_A,I_peak1_A,m_zvs1_A,m_zvs2_A (DABPoint N=4000, L=64uH n=2 fs=100kHz)", comments="# ")
    np.savetxt(os.path.join(OUT, "test_set_random.csv"), np.column_stack([Xte, Yte]), delimiter=",",
               header="V1_V,V2_V,phi_rad,D1,D2,P_W,I_rms1_A,I_peak1_A,m_zvs1_A,m_zvs2_A (2000 random points, seed 2026)", comments="# ")
    np.savetxt(os.path.join(OUT, "extrapolation_set.csv"), np.column_stack([Xex, Yex]), delimiter=",",
               header="V1_V,V2_V,phi_rad,D1,D2,P_W,I_rms1_A,I_peak1_A,m_zvs1_A,m_zvs2_A (V1=600 V rows 1-200, V2=470 V rows 201-400)", comments="# ")
    yrange = Yte.max(0) - Yte.min(0)

    def metrics(Yp, Yt_, Ype, Yte_):
        e = Yp - Yt_
        return dict(rmse=rmse(Yp, Yt_).tolist(), rmse_pct_range=(100 * rmse(Yp, Yt_) / yrange).tolist(),
                    max_abs=np.max(np.abs(e), axis=0).tolist(),
                    rmse_extrap=rmse(Ype, Yte_).tolist(), rmse_extrap_pct_range=(100 * rmse(Ype, Yte_) / yrange).tolist(),
                    max_abs_extrap=np.max(np.abs(Ype - Yte_), axis=0).tolist())

    results = dict(outputs=NAMES, units=UNITS, test_range=yrange.tolist(), n_test=len(Xte), n_extrap=len(Xex),
                   grids=[dict(shape=g, n=len(X)) for g, _, X, _ in train], models={})
    # analytical (no training)
    for key, fn, ops in (("A1_sps_closed_form", analytic_sps, 160), ("A2_analytic_tps_piecewise", analytic_tps, 420)):
        t = time.time(); Yp = predict_analytic(fn, Xte); dt = (time.time() - t) / len(Xte)
        Ype = predict_analytic(fn, Xex)
        results["models"][key] = dict(name=key, train_n=0, metrics=metrics(Yp, Yte, Ype, Yex), ops_per_eval=ops,
                                      python_eval_us=dt * 1e6, train_s=0.0, curve=[])
        print(f"{key}: rmse % range {np.round(100 * rmse(Yp, Yte) / yrange, 3)}")
        if key == "A2_analytic_tps_piecewise":
            np.savetxt(os.path.join(OUT, "parity_A2_test.csv"), np.column_stack([Yte, Yp]), delimiter=",",
                       header="truth(5 cols),A2(5 cols)", comments="# ")
    # trainable models: data-efficiency curve over nested grids, final metrics on the full grid
    factories = {
        "P3_polynomial": lambda: Poly3(),
        "LUT_multilinear": lambda: LUT(),
        "MLP_plain": lambda: MLP(),
        "PINN_physics_loss": lambda: MLP(physics=True),
        "HYB_sps_plus_residual": lambda: MLP(residual=analytic_sps),
        "GP_rbf": lambda: GP(),
    }
    curves = {}
    for key, mk in factories.items():
        curve = []
        for g, axes, X, Y in train:
            m = mk(); t = time.time(); m.fit(X, Y, axes=axes); ttrain = time.time() - t
            t = time.time(); Yp = m.predict(Xte); dt = (time.time() - t) / len(Xte)
            Ype = m.predict(Xex)
            mt = metrics(Yp, Yte, Ype, Yex)
            curve.append(dict(n=len(X), shape=g, rmse_pct_range=mt["rmse_pct_range"], rmse=mt["rmse"], train_s=ttrain,
                              max_rmse_pct=float(max(mt["rmse_pct_range"]))))
            print(f"{key} n={len(X)}: rmse % range {np.round(mt['rmse_pct_range'], 3)}  ({ttrain:.1f} s)")
        ops = m.ops if not callable(getattr(type(m), "ops", None)) else m.ops
        results["models"][key] = dict(name=m.name, train_n=len(X), metrics=mt, ops_per_eval=int(ops),
                                      python_eval_us=dt * 1e6, train_s=ttrain, curve=curve)
        curves[key] = curve
        np.savetxt(os.path.join(OUT, f"parity_{key}_test.csv"), np.column_stack([Yte, Yp]), delimiter=",",
                   header="truth(5 cols),prediction(5 cols)", comments="# ")
        if key == "GP_rbf":
            results["models"][key]["gp_hyperparameters_log"] = [m_[0].tolist() for m_ in m.models]
            results["models"][key]["gp_train_points_used"] = m.n_train_used
    # data needed for 1 % (of test range) RMSE on every output
    for key, curve in curves.items():
        need = next((c["n"] for c in curve if c["max_rmse_pct"] < 1.0), None)
        results["models"][key]["n_for_1pct_all_outputs"] = need
        needP = next((c["n"] for c in curve if c["rmse_pct_range"][0] < 1.0), None)
        results["models"][key]["n_for_1pct_P_only"] = needP
    # ranking by worst-output test RMSE (% of range), full training grid
    rank = sorted(results["models"].items(), key=lambda kv: max(kv[1]["metrics"]["rmse_pct_range"]))
    results["ranking_worst_output_rmse_pct"] = [(k, float(max(v["metrics"]["rmse_pct_range"]))) for k, v in rank]
    rankP = sorted(results["models"].items(), key=lambda kv: kv[1]["metrics"]["rmse_pct_range"][0])
    results["ranking_P_rmse_pct"] = [(k, float(v["metrics"]["rmse_pct_range"][0])) for k, v in rankP]
    results["wall_time_s"] = time.time() - T0
    json.dump(results, open(os.path.join(OUT, "metrics.json"), "w"), indent=1)

    # ---- tables
    lines = ["| model | train pts | " + " | ".join(f"RMSE {nm} ({u})" for nm, u in zip(NAMES, UNITS)) +
             " | worst RMSE (% range) | max abs err P (W) | extrap. worst RMSE (% range) | ops/eval | n for 1 % (all) | train (s) |",
             "|---|---|" + "---|" * 5 + "---|---|---|---|---|---|"]
    for k, v in rank:
        mt = v["metrics"]
        lines.append(f"| {k} | {v['train_n']} | " + " | ".join(f"{r:.3g}" for r in mt["rmse"]) +
                     f" | {max(mt['rmse_pct_range']):.3f} | {mt['max_abs'][0]:.3g} | {max(mt['rmse_extrap_pct_range']):.3f} | {v['ops_per_eval']} | "
                     f"{v.get('n_for_1pct_all_outputs', '-')} | {v['train_s']:.1f} |")
    lines += ["", "Per-output RMSE as % of the test-set range (full training grid, 6912 points):", "",
              "| model | " + " | ".join(NAMES) + " | extrap " + " | extrap ".join(NAMES) + " |", "|---|" + "---|" * 10]
    for k, v in rank:
        mt = v["metrics"]
        lines.append(f"| {k} | " + " | ".join(f"{r:.3f}" for r in mt["rmse_pct_range"]) + " | " +
                     " | ".join(f"{r:.3f}" for r in mt["rmse_extrap_pct_range"]) + " |")
    lines += ["", "Data efficiency (worst-output RMSE in % of range vs number of training points):", "",
              "| model | " + " | ".join(str(len(X)) for _, _, X, _ in train) + " |", "|---|" + "---|" * len(train)]
    for k, curve in curves.items():
        lines.append(f"| {k} | " + " | ".join(f"{c['max_rmse_pct']:.2f}" for c in curve) + " |")
    open(os.path.join(OUT, "metrics_table.md"), "w").write("\n".join(lines) + "\n")

    # ---- figures
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    for k, curve in curves.items():
        ax[0].loglog([c["n"] for c in curve], [max(c["max_rmse_pct"], 1e-4) for c in curve], "o-", label=k)
        ax[1].loglog([c["n"] for c in curve], [max(c["rmse_pct_range"][0], 1e-4) for c in curve], "o-", label=k)
    for a, ttl in zip(ax, ("worst output", "power P")):
        a.axhline(1.0, color="k", ls="--", lw=0.8); a.set_xlabel("training points (regular grid)"); a.set_ylabel("test RMSE (% of range)")
        a.set_title(f"Data efficiency - {ttl}"); a.grid(alpha=0.3, which="both")
    a2 = results["models"]["A2_analytic_tps_piecewise"]["metrics"]["rmse_pct_range"]
    ax[0].axhline(max(a2), color="gray", ls=":", label="A2 analytical (no data)"); ax[1].axhline(a2[0], color="gray", ls=":")
    ax[0].legend(fontsize=7); fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_data_efficiency.png"), dpi=130); plt.close(fig)

    fig, ax = plt.subplots(2, 3, figsize=(12, 7)); ax = ax.ravel()
    keys = ["A2_analytic_tps_piecewise", "LUT_multilinear", "MLP_plain", "PINN_physics_loss", "GP_rbf", "P3_polynomial"]
    for a, k in zip(ax, keys):
        Yp = np.loadtxt(os.path.join(OUT, f"parity_{k if k != 'A2_analytic_tps_piecewise' else 'A2'}_test.csv"), delimiter=",")[:, 5:]
        a.scatter(Yte[:, 1], Yp[:, 1], s=3, alpha=0.4, label="I_rms1"); a.scatter(Yte[:, 3], Yp[:, 3], s=3, alpha=0.4, label="m_zvs1")
        lim = [min(Yte[:, 3].min(), 0), Yte[:, 1].max()]; a.plot(lim, lim, "k-", lw=0.7)
        a.set_title(k, fontsize=9); a.set_xlabel("truth (A)"); a.set_ylabel("prediction (A)"); a.grid(alpha=0.3)
    ax[0].legend(fontsize=7); fig.suptitle("Parity on the random test set (full training grid)"); fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_parity.png"), dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4))
    ks = [k for k, _ in rank]; xpos = np.arange(len(ks)); wdt = 0.38
    ax.bar(xpos - wdt / 2, [max(results["models"][k]["metrics"]["rmse_pct_range"]) for k in ks], wdt, label="test (inside envelope)")
    ax.bar(xpos + wdt / 2, [max(results["models"][k]["metrics"]["rmse_extrap_pct_range"]) for k in ks], wdt, label="extrapolation V1=600 V / V2=470 V")
    ax.set_yscale("log"); ax.set_xticks(xpos); ax.set_xticklabels(ks, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("worst-output RMSE (% of range)"); ax.axhline(1, color="k", ls="--", lw=0.8); ax.legend(); ax.grid(alpha=0.3, axis="y")
    ax.set_title("Interpolation vs extrapolation error (full training grid)"); fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_extrapolation.png"), dpi=130); plt.close(fig)

    # ---- provenance
    def sha(p):
        return hashlib.sha256(open(p, "rb").read()).hexdigest()

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
    inputs = [DESIGN, os.path.join(DAB, "dabtools", "dab", "dab_model.py"), os.path.join(DAB, "dabtools", "dab", "devices.py"), __file__]
    prov = dict(script=os.path.relpath(__file__, REPO), generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                python=platform.python_version(), platform=platform.platform(),
                packages={m: importlib.import_module(m).__version__ for m in ("numpy", "scipy", "matplotlib")},
                git_commit=git_commit(), input_sha256={os.path.relpath(p, REPO): sha(p) for p in inputs},
                seeds=dict(global_seed=SEED), wall_time_s=time.time() - T0,
                ground_truth="DABPoint N=4000; I_min from zvs_current_min with design C_oss,er and C_par",
                outputs=sorted(os.listdir(OUT)))
    json.dump(prov, open(os.path.join(HERE, "provenance.json"), "w"), indent=1)
    print(f"done in {time.time() - T0:.0f} s")
    print(json.dumps(results["ranking_worst_output_rmse_pct"], indent=0))


if __name__ == "__main__":
    main()
