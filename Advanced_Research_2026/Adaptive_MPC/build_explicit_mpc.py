#!/usr/bin/env python3
"""
Explicit MPC: pre-compute the CCS-MPC law of dab_mpc_lib.CCSMPC on a 3-D grid
    e = v2_ref - v2 (V)  x  V1 (V)  x  P_hat = d_hat * v2_ref (W, estimated load power)
with the linearisation point phi0 = phi_ff(P_hat, V1) (steady-state feedforward) and v2 = v2_ref - e.
Each node is the exact box-QP optimum (vectorised accelerated projected gradient, 600 iterations,
convergence checked against 1200 iterations).  Outputs results/empc_lut.npz (+ meta json, slice figure,
interpolation-error table versus the online law at random off-grid points).
Run time: < 1 min.
"""
import os, sys, json, math, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from dab_mpc_lib import *      # noqa
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

T0 = time.time()
OUT = os.path.join(HERE, "results"); os.makedirs(OUT, exist_ok=True)
N, Q, R = 8, 1.0, 16.0                             # same as the online CCS-MPC default
E_AX = np.linspace(-12, 12, 33)                    # 0.75 V steps; |e| > 12 V is saturated for every (V1, P_hat)
V1_AX = np.linspace(650, 850, 9)                   # 25 V
P_AX = np.linspace(-1.1 * P_RATED, 1.1 * P_RATED, 23)   # 660 W
A = TS / C2


def solve_batch(c, phi0, g, pbar, K):
    """Batched accelerated projected gradient for min q||a g T p + c||^2 + r||D p - phi0 e1||^2, |p| <= pbar."""
    M = c.shape[0]
    ag = A * g[:, None]
    lam = 2 * (Q * (A * g) ** 2 * N * (N + 1) / 2 + 4 * R); step = (1.0 / lam)[:, None]
    pb = pbar[:, None]
    p = np.zeros((M, N)); y = p.copy(); p_prev = p.copy()
    for k in range(K):
        res = ag * np.cumsum(y, axis=1) + c
        grad_track = 2 * Q * ag * np.cumsum(res[:, ::-1], axis=1)[:, ::-1]
        dp = np.diff(np.concatenate((phi0[:, None], y), axis=1), axis=1)
        grad_rate = 2 * R * (dp - np.concatenate((dp[:, 1:], np.zeros((M, 1))), axis=1))
        p_new = np.clip(y - step * (grad_track + grad_rate), -pb, pb)
        y = p_new + (k / (k + 3.0)) * (p_new - p_prev); p_prev = p_new
    return p_new


def law(e, v1, P_hat, K=600):
    """Vectorised explicit evaluation of the CCS law at (e, V1, P_hat) (arrays of equal length)."""
    v2 = V2_REF - e
    d_hat = P_hat / V2_REF
    phi0 = np.array([phi_from_i2_sps(d, v) for d, v in zip(d_hat, v1)])
    g = np.array([di2_dphi_sps(p, v) for p, v in zip(phi0, v1)])
    i2_0 = np.array([i2_sps(p, v) for p, v in zip(phi0, v1)])
    pbar = np.array([phi_bound_peak(v, w, L_NOM) for v, w in zip(v1, v2)])
    c = v2[:, None] + A * np.arange(1, N + 1)[None, :] * (i2_0 - g * phi0 - d_hat)[:, None] - V2_REF
    return solve_batch(c, phi0, g, pbar, K)[:, 0]


E, V, P = np.meshgrid(E_AX, V1_AX, P_AX, indexing="ij")
e_f, v_f, p_f = E.ravel(), V.ravel(), P.ravel()
t = time.time()
phi_600 = law(e_f, v_f, p_f, 600)
phi_1200 = law(e_f, v_f, p_f, 1200)
conv = float(np.max(np.abs(phi_600 - phi_1200)))
print(f"grid {E.shape}, {E.size} nodes, solver time {time.time()-t:.1f} s, convergence 600 vs 1200 it: {math.degrees(conv):.4f} deg")
tab = phi_1200.reshape(E.shape)
np.savez(os.path.join(OUT, "empc_lut.npz"), e_axis=E_AX, v1_axis=V1_AX, p_axis=P_AX, phi=tab)

# interpolation error vs the exact law at random off-grid points
rng = np.random.default_rng(20260101)
Mv = 3000
e_r = rng.uniform(-12, 12, Mv); v_r = rng.uniform(650, 850, Mv); p_r = rng.uniform(-1.1 * P_RATED, 1.1 * P_RATED, Mv)
exact = law(e_r, v_r, p_r, 1200)
interp = np.array([ExplicitMPC.trilinear(tab, (E_AX, V1_AX, P_AX), (a, b, c)) for a, b, c in zip(e_r, v_r, p_r)])
err = np.degrees(interp - exact)
# fraction of nodes where the box constraint is active (saturated law)
pb = np.array([phi_bound_peak(v, V2_REF - e, L_NOM) for v, e in zip(v_f, e_f)])
sat = float(np.mean(np.abs(phi_1200) >= pb - 1e-9))
meta = dict(N=N, q=Q, r=R, axes=dict(e_V=E_AX.tolist(), V1_V=V1_AX.tolist(), P_hat_W=P_AX.tolist()), shape=list(tab.shape),
            entries=int(tab.size), bytes_float32=int(tab.size * 4), bytes_q15=int(tab.size * 2),
            convergence_deg_600_vs_1200=math.degrees(conv),
            interp_error_deg=dict(max=float(np.max(np.abs(err))), rms=float(np.sqrt(np.mean(err ** 2))), p99=float(np.percentile(np.abs(err), 99)),
                                  pwm_step_deg=math.degrees(PWM_STEP), n_samples=Mv),
            saturated_fraction=sat, v2_ref=V2_REF, linearisation="phi0 = phi_ff(P_hat, V1); v2 = v2_ref - e",
            note="law = first element of the CCS box-QP optimum; identical cost/constraints to CCSMPC(N=8, q=1, r=16)")
json.dump(meta, open(os.path.join(OUT, "empc_lut_meta.json"), "w"), indent=1)

# figure: slices
fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))
for P_hat in (-6600, -3300, 0, 3300, 6600):
    k = int(np.argmin(np.abs(P_AX - P_hat)))
    ax[0].plot(E_AX, np.degrees(tab[:, 6, k]), label=f"P = {P_AX[k]/1e3:.1f} kW")
ax[0].set_xlabel("e = v2_ref - v2 (V)"); ax[0].set_ylabel("phi (deg)"); ax[0].set_title("V1 = 800 V"); ax[0].legend(fontsize=7)
for V1 in (650, 750, 850):
    j = int(np.argmin(np.abs(V1_AX - V1)))
    ax[1].plot(P_AX / 1e3, np.degrees(tab[16, j, :]), label=f"V1 = {V1} V")
ax[1].set_xlabel("P_hat (kW)"); ax[1].set_ylabel("phi (deg)"); ax[1].set_title("e = 0 (feedforward part)"); ax[1].legend(fontsize=7)
im = ax[2].imshow(np.degrees(tab[:, 6, :]).T, origin="lower", aspect="auto", extent=[E_AX[0], E_AX[-1], P_AX[0] / 1e3, P_AX[-1] / 1e3], cmap="viridis")
ax[2].set_xlabel("e (V)"); ax[2].set_ylabel("P_hat (kW)"); ax[2].set_title("phi (deg), V1 = 800 V"); plt.colorbar(im, ax=ax[2])
[a.grid(alpha=0.3) for a in ax[:2]]
fig.suptitle(f"Explicit MPC look-up table ({tab.shape[0]}x{tab.shape[1]}x{tab.shape[2]} = {tab.size} entries, "
             f"{tab.size*2/1024:.1f} KB Q15 / {tab.size*4/1024:.1f} KB float32)")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "empc_lut_slices.png"), dpi=130); plt.close(fig)
print(json.dumps(meta["interp_error_deg"], indent=1), "saturated fraction", sat)
write_provenance(HERE, "build_explicit_mpc.py", T0, [DESIGN_FILE, CONTROL_FILE, os.path.join(HERE, "dab_mpc_lib.py")],
                 extra=dict(outputs=["results/empc_lut.npz", "results/empc_lut_meta.json", "results/empc_lut_slices.png"]))
print(f"done in {time.time()-T0:.1f} s")
