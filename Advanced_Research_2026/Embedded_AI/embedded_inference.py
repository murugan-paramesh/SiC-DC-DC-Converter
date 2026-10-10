#!/usr/bin/env python3
"""
Embedded inference feasibility on a C2000 (F28379D class) for the DAB controller:
  (a) Q15 quantisation of the explicit-MPC look-up table (Adaptive_MPC/results/empc_lut.npz) and of a small MLP
      surrogate (3-16-16-3 ReLU, numpy back-propagation) of the TPS/EPS optimal-modulation map generated with the
      project model (exact piecewise-linear period model + ZVS criterion, validated against dabtools tps_search);
      quantisation error vs float, memory, operation counts, WCET (cycles, us, fraction of the 10 us ISR);
  (b) LUT vs MLP vs analytic inverse decision;
  (d) bit-exact test vectors for the C-like fixed-point reference (fixed_point_ref.py).
Outputs results/*.{json,csv,png,npz}.  Run time ~4-6 min (map generation dominates).
"""
import os, sys, json, math, time
import numpy as np
EMB_DIR = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, EMB_DIR)
MPC_DIR = os.path.join(os.path.dirname(EMB_DIR), "Adaptive_MPC"); sys.path.insert(0, MPC_DIR)
from dab_mpc_lib import *          # noqa  (project model wrappers, plant, ExplicitMPC, op counting, provenance; redefines HERE)
HERE = EMB_DIR
import fixed_point_ref as FP
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import pandas as pd

T0 = time.time()
OUT = os.path.join(HERE, "results"); os.makedirs(OUT, exist_ok=True)
LUT_FILE = os.path.join(MPC_DIR, "results", "empc_lut.npz")
if not os.path.exists(LUT_FILE):
    import subprocess; subprocess.run([sys.executable, os.path.join(MPC_DIR, "build_explicit_mpc.py")], check=True)
rng = np.random.default_rng(20260101)
PHI_SCALE = math.pi / 2
report = {}

# =============================================================================================== (a1) explicit-MPC LUT in Q15
z = np.load(LUT_FILE)
e_ax, v1_ax, p_ax, tab = z["e_axis"], z["v1_axis"], z["p_axis"], z["phi"]
SCALES = dict(e_V=16.0, v1_offset_V=750.0, v1_V=128.0, p_W=8192.0)            # input normalisation (full scale of the Q15 input)
axes_q = [(FP.to_q15(e_ax[0], SCALES["e_V"]), FP.to_q15(e_ax[1] - e_ax[0], SCALES["e_V"]), len(e_ax)),
          (FP.to_q15(v1_ax[0] - SCALES["v1_offset_V"], SCALES["v1_V"]), FP.to_q15(v1_ax[1] - v1_ax[0], SCALES["v1_V"]), len(v1_ax)),
          (FP.to_q15(p_ax[0], SCALES["p_W"]), FP.to_q15(p_ax[1] - p_ax[0], SCALES["p_W"]), len(p_ax))]
for (x0, st, n), ax, sc_ in zip(axes_q, (e_ax, v1_ax - SCALES["v1_offset_V"], p_ax), (SCALES["e_V"], SCALES["v1_V"], SCALES["p_W"])):
    assert abs(FP.from_q15(st, sc_) - (ax[1] - ax[0])) < 1e-9, "axis step must be exactly representable in Q15"
tab_q = np.clip(np.round(tab / PHI_SCALE * FP.Q15_ONE), -32768, 32767).astype(np.int16)
lut_q = FP.LutQ15(tab_q.ravel(), axes_q, tab.shape)
lut_meta = dict(scales=SCALES, phi_scale_rad=PHI_SCALE, shape=list(tab.shape), source=os.path.relpath(LUT_FILE, REPO))
lut_q.save(os.path.join(OUT, "empc_lut_q15.npz"), lut_meta)


def lut_q15_eval_float(e, v1, P):
    """Float in -> Q15 path -> float out (rad), as the firmware would do with ADC-derived Q15 inputs."""
    q = lut_q.eval(FP.to_q15(e, SCALES["e_V"]), FP.to_q15(v1 - SCALES["v1_offset_V"], SCALES["v1_V"]), FP.to_q15(P, SCALES["p_W"]))
    return FP.from_q15(q, PHI_SCALE)


Mv = 5000
e_r = rng.uniform(-12, 12, Mv); v_r = rng.uniform(650, 850, Mv); p_r = rng.uniform(-7260, 7260, Mv)
f_lut = np.array([ExplicitMPC.trilinear(tab, (e_ax, v1_ax, p_ax), (a, b, c)) for a, b, c in zip(e_r, v_r, p_r)])
q_lut = np.array([lut_q15_eval_float(a, b, c) for a, b, c in zip(e_r, v_r, p_r)])
err_q = np.degrees(q_lut - f_lut)
meta_f = json.load(open(os.path.join(MPC_DIR, "results", "empc_lut_meta.json")))
report["explicit_lut"] = dict(entries=int(tab.size), bytes_q15=int(tab.size * 2), bytes_float32=int(tab.size * 4), shape=list(tab.shape),
                              input_quantisation=dict(e_LSB_V=SCALES["e_V"] / 32768, v1_LSB_V=SCALES["v1_V"] / 32768, p_LSB_W=SCALES["p_W"] / 32768),
                              output_LSB_deg=math.degrees(PHI_SCALE / 32768),
                              q15_vs_float_error_deg=dict(max=float(np.max(np.abs(err_q))), rms=float(np.sqrt(np.mean(err_q ** 2)))),
                              float_lut_vs_exact_law_error_deg=meta_f["interp_error_deg"], pwm_step_deg=math.degrees(PWM_STEP))
print("explicit LUT Q15 vs float: max %.4f deg, rms %.4f deg (PWM step 0.36 deg)" % (report["explicit_lut"]["q15_vs_float_error_deg"]["max"], report["explicit_lut"]["q15_vs_float_error_deg"]["rms"]), flush=True)

# closed-loop check of the Q15 path on the switched plant (load step 10 -> 100 %)
sc = make_scenario("load_step_up")
cl = {}
for name, ctl in (("float LUT", ExplicitMPC(LUT_FILE)), ("Q15 LUT", ExplicitMPC(LUT_FILE, quantised=lut_q15_eval_float))):
    res = run_scenario(ctl, sc); mt = metrics(res, sc); cl[name] = mt
    print(f"closed loop {name:10s}: peak dev {mt['peak_dev_pct']:.3f} %  settle {mt['settling_ms']:.2f} ms  ITAE {mt['ITAE']:.2f}  Ipk {mt['i_peak_A']:.2f} A", flush=True)
report["explicit_lut"]["closed_loop_load_step"] = cl

# =============================================================================================== (a2) TPS/EPS optimal-modulation map
V1_AX = np.arange(650, 851, 25.0); V2_AX = np.arange(300, 451, 25.0)
P_FRAC = np.concatenate([-np.arange(1.0, 0.09, -0.1), np.arange(0.1, 1.01, 0.1)])
ND = 25
Dg = np.linspace(0.4, 1.0, ND)
D1g, D2g = np.meshgrid(Dg, Dg, indexing="ij"); D1g, D2g = D1g.ravel(), D2g.ravel()


def tps_opt(V1, V2, P, iters=30):
    """Minimum-rms (D1, D2, phi) for power P subject to ZVS at every edge (exact piecewise-linear model, 25x25 D grid)."""
    V2p = N_RATIO * V2
    sgn = 1.0 if P > 0 else -1.0
    lo = np.zeros(ND * ND); hi = np.full(ND * ND, math.pi / 2)
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        Pm = pwl_period(V1, V2p, L_NOM, FS, sgn * mid, D1g, D2g)["P"]
        under = np.abs(Pm) < abs(P)
        lo = np.where(under, mid, lo); hi = np.where(under, hi, mid)
    phi = sgn * 0.5 * (lo + hi)
    r = pwl_period(V1, V2p, L_NOM, FS, phi, D1g, D2g)
    Imin1, Imin2 = zvs_i_min(V1, V2, L_NOM, N_RATIO)
    feas = (np.abs(np.abs(r["P"]) - abs(P)) < 0.01 * abs(P)) & (np.abs(phi) <= PHI_MAX)
    zvs = (r["zvs1"] >= Imin1) & (r["zvs2"] >= Imin2)
    cand = feas & zvs
    zvs_ok = bool(cand.any())
    if not zvs_ok:
        cand = feas
    if not cand.any():
        return None
    k = int(np.argmin(np.where(cand, r["Irms"], np.inf)))
    ksps = int(np.argmin(np.abs(D1g - 1) + np.abs(D2g - 1)))
    return dict(phi=float(phi[k]), D1=float(D1g[k]), D2=float(D2g[k]), Irms=float(r["Irms"][k]), Ipk=float(r["Ipk"][k]), zvs_ok=zvs_ok,
                Irms_sps=float(r["Irms"][ksps]), zvs_sps=bool(zvs[ksps] and feas[ksps]))


map_file = os.path.join(OUT, "tps_eps_map_MODEL.csv")
t = time.time()
rows = []
for V1 in V1_AX:
    for V2 in V2_AX:
        for pf in P_FRAC:
            o = tps_opt(V1, V2, pf * P_RATED)
            if o:
                rows.append(dict(V1=V1, V2=V2, P=pf * P_RATED, **o))
dmap = pd.DataFrame(rows)
dmap.to_csv(map_file, index=False)
print(f"TPS/EPS map: {len(dmap)} points in {time.time()-t:.0f} s, ZVS feasible at {100*dmap.zvs_ok.mean():.1f} % of the points "
      f"(SPS: {100*dmap.zvs_sps.mean():.1f} %), mean Irms reduction vs SPS {100*(1-dmap.Irms.mean()/dmap.Irms_sps.mean()):.1f} %", flush=True)
# validation against dabtools tps_search at three points (slow brute force with DABPoint, grid 13)
val_tps = []
for V1, V2, P in ((800, 400, 0.75 * P_RATED), (850, 300, 0.25 * P_RATED), (650, 450, 1.0 * P_RATED)):
    best, sps = M.tps_search(V1, V2, N_RATIO, L_NOM, FS, P, DEV1["Coss_er"], DEV2["Coss_er"], grid=13, N=1000)
    o = tps_opt(V1, V2, P)
    val_tps.append(dict(V1=V1, V2=V2, P=P, tps_search_Irms=(best.I_rms1 if best else None), tps_search_D1=(best.D1 if best else None),
                        tps_search_D2=(best.D2 if best else None), ours_Irms=o["Irms"], ours_D1=o["D1"], ours_D2=o["D2"], ours_zvs_ok=o["zvs_ok"], sps_Irms=sps.I_rms1))
    print("tps_search check", val_tps[-1], flush=True)
report["tps_map"] = dict(points=len(dmap), zvs_feasible_fraction=float(dmap.zvs_ok.mean()), sps_zvs_fraction=float(dmap.zvs_sps.mean()),
                         mean_Irms_A=float(dmap.Irms.mean()), mean_Irms_sps_A=float(dmap.Irms_sps.mean()), validation_vs_tps_search=val_tps,
                         note="computed from the lossless piecewise-linear model (no measurement); D grid 0.4..1.0 step 0.025; ZVS energy criterion with C_par")
# off-grid validation set (truth from the same optimiser)
Nv = 150
vv1 = rng.uniform(650, 850, Nv); vv2 = rng.uniform(300, 450, Nv); vp = rng.uniform(0.1, 1.0, Nv) * P_RATED * rng.choice([-1, 1], Nv)
val_rows = []
for a, b, c in zip(vv1, vv2, vp):
    o = tps_opt(a, b, c)
    if o:
        val_rows.append(dict(V1=a, V2=b, P=c, **o))
dval = pd.DataFrame(val_rows)
print(f"validation set {len(dval)} off-grid points ({time.time()-t:.0f} s)", flush=True)

# =============================================================================================== MLP surrogate (numpy backprop)
def norm_in(V1, V2, P):
    return np.stack([(np.asarray(V1) - 750) / 100, (np.asarray(V2) - 375) / 75, np.asarray(P) / P_RATED], axis=-1)


def norm_out(phi, D1, D2):
    return np.stack([np.asarray(phi) / PHI_SCALE, (np.asarray(D1) - 0.7) / 0.3, (np.asarray(D2) - 0.7) / 0.3], axis=-1)


def denorm_out(y):
    return y[..., 0] * PHI_SCALE, y[..., 1] * 0.3 + 0.7, y[..., 2] * 0.3 + 0.7


X = norm_in(dmap.V1.values, dmap.V2.values, dmap.P.values); Y = norm_out(dmap.phi.values, dmap.D1.values, dmap.D2.values)
idx = rng.permutation(len(X)); ntr = int(0.8 * len(X)); tr, te = idx[:ntr], idx[ntr:]
Xv = norm_in(dval.V1.values, dval.V2.values, dval.P.values); Yv = norm_out(dval.phi.values, dval.D1.values, dval.D2.values)


class MLP:
    def __init__(self, sizes, seed=20260101):
        r = np.random.default_rng(seed)
        self.W = [r.standard_normal((o, i)) * math.sqrt(2.0 / i) for i, o in zip(sizes[:-1], sizes[1:])]
        self.b = [np.zeros(o) for o in sizes[1:]]

    def forward(self, X):
        acts = [X]; h = X
        for l, (W, b) in enumerate(zip(self.W, self.b)):
            h = h @ W.T + b
            if l < len(self.W) - 1:
                h = np.maximum(h, 0)
            acts.append(h)
        return acts

    def train(self, X, Y, Xte, Yte, epochs=15000, lr=3e-3, l2=1e-5):
        mW = [np.zeros_like(w) for w in self.W]; vW = [np.zeros_like(w) for w in self.W]
        mb = [np.zeros_like(b) for b in self.b]; vb = [np.zeros_like(b) for b in self.b]
        b1, b2, eps = 0.9, 0.999, 1e-8
        hist = []
        for ep in range(1, epochs + 1):
            acts = self.forward(X)
            out = acts[-1]
            g = 2 * (out - Y) / len(X)
            gW = [None] * len(self.W); gb = [None] * len(self.b)
            for l in reversed(range(len(self.W))):
                gW[l] = g.T @ acts[l] + l2 * self.W[l]; gb[l] = g.sum(axis=0)
                if l > 0:
                    g = (g @ self.W[l]) * (acts[l] > 0)
            lr_t = lr * (0.5 * (1 + math.cos(math.pi * ep / epochs)))        # cosine decay
            for l in range(len(self.W)):
                for P_, G, mm, vv in ((self.W[l], gW[l], mW[l], vW[l]), (self.b[l], gb[l], mb[l], vb[l])):
                    mm *= b1; mm += (1 - b1) * G; vv *= b2; vv += (1 - b2) * G * G
                    P_ -= lr_t * (mm / (1 - b1 ** ep)) / (np.sqrt(vv / (1 - b2 ** ep)) + eps)
            if ep % 100 == 0 or ep == 1:
                hist.append((ep, float(np.mean((out - Y) ** 2)), float(np.mean((self.forward(Xte)[-1] - Yte) ** 2))))
        return hist


t = time.time()
mlp = MLP([3, 16, 16, 3])
hist = mlp.train(X[tr], Y[tr], X[te], Y[te], epochs=15000)
print(f"MLP trained in {time.time()-t:.0f} s: train mse {hist[-1][1]:.2e}, test mse {hist[-1][2]:.2e}", flush=True)


def errors(pred_y, true_y):
    phi_p, d1_p, d2_p = denorm_out(pred_y); phi_t, d1_t, d2_t = denorm_out(true_y)
    e_phi = np.degrees(phi_p - phi_t); e_d = np.concatenate([d1_p - d1_t, d2_p - d2_t])
    return dict(phi_rms_deg=float(np.sqrt(np.mean(e_phi ** 2))), phi_max_deg=float(np.max(np.abs(e_phi))),
                D_rms=float(np.sqrt(np.mean(e_d ** 2))), D_max=float(np.max(np.abs(e_d))))


mlp_float_test = errors(mlp.forward(X[te])[-1], Y[te]); mlp_float_val = errors(mlp.forward(Xv)[-1], Yv)
# TPS LUT alternative: trilinear interpolation of the 9x7x20 map (3 outputs) evaluated on the off-grid set
tps_tab = {k: dmap.pivot_table(index="V1", columns=["V2", "P"], values=k).values.reshape(len(V1_AX), len(V2_AX), len(P_FRAC)) for k in ("phi", "D1", "D2")}
P_AXm = P_FRAC * P_RATED
lut_pred = np.stack([np.array([ExplicitMPC.trilinear(tps_tab[k], (V1_AX, V2_AX, P_AXm), (a, b, c)) for a, b, c in zip(dval.V1, dval.V2, dval.P)]) for k in ("phi", "D1", "D2")], axis=-1)
tps_lut_val = errors(norm_out(lut_pred[:, 0], lut_pred[:, 1], lut_pred[:, 2]), Yv)
# Q15 MLP
# activation-range calibration on the training set: hidden activations are scaled by 2^-k so that they fit Q15
act_max = [float(np.max(np.abs(a))) for a in mlp.forward(X[tr])[1:-1]]
layers, act_shifts = FP.quantise_mlp(mlp.W, mlp.b, act_max)
mlp_q = FP.MlpQ15(layers)
mlp_meta = dict(input_norm="[(V1-750)/100, (V2-375)/75, P/6600] in Q15", output_norm="[phi/(pi/2), (D1-0.7)/0.3, (D2-0.7)/0.3] in Q15",
                sizes=[3, 16, 16, 3], activation="ReLU (hidden), linear (output)", shifts=[s for (_, _, s) in layers],
                activation_shifts=act_shifts, activation_max_train=act_max)
mlp_q.save(os.path.join(OUT, "tps_mlp_q15.npz"), mlp_meta)


def mlp_q15_forward(Xn):
    out = []
    for x in Xn:
        xq = [FP.to_q15(v, 1.0) for v in x]
        out.append([q / FP.Q15_ONE for q in mlp_q.eval(xq)])
    return np.array(out)


q_val = mlp_q15_forward(Xv); f_val = mlp.forward(Xv)[-1]
mlp_q15_vs_float = errors(q_val, f_val); mlp_q15_val = errors(q_val, Yv)
n_params = sum(w.size + b.size for w, b in zip(mlp.W, mlp.b))
report["mlp"] = dict(architecture="3-16-16-3 ReLU", parameters=int(n_params), bytes_q15=int(n_params * 2), bytes_q15_with_int32_bias=int(n_params * 2 + 2 * sum(b.size for b in mlp.b)),
                     training=dict(samples_train=int(ntr), samples_test=int(len(te)), epochs=15000, optimiser="Adam, cosine lr 3e-3, L2 1e-5, full batch", seed=20260101,
                                   train_mse_norm=hist[-1][1], test_mse_norm=hist[-1][2]),
                     error_float_test_grid=mlp_float_test, error_float_offgrid=mlp_float_val, error_q15_vs_float_offgrid=mlp_q15_vs_float, error_q15_offgrid=mlp_q15_val,
                     tps_lut_alternative=dict(entries=int(3 * dmap.shape[0]), bytes_q15=int(6 * dmap.shape[0]), error_offgrid=tps_lut_val),
                     quantisation_shifts=mlp_meta["shifts"], activation_shifts=act_shifts)
print("MLP float off-grid:", mlp_float_val); print("MLP Q15 off-grid:", mlp_q15_val); print("TPS LUT off-grid:", tps_lut_val, flush=True)

# =============================================================================================== operation counts / WCET
def wc(ops, overhead=0):
    cyc = overhead + sum(ops[k] * CYCLES_PER_OP[k] for k in OpCount.KEYS)
    return dict(ops=dict(ops), ops_total=ops.total, cycles=int(cyc), us=round(cyc / MCU_HZ * 1e6, 3), isr_fraction=round(cyc / MCU_HZ / ISR_BUDGET_S, 4))


macs = sum(w.size for w in mlp.W)
paths = {
    "explicit LUT Q15 trilinear (3 in, 1 out)": wc(OpCount(mul=3 * 2 + 7, add=3 * 3 + 7 * 2, cmp=3 * 4 + 7, load=8 + 6)),
    "TPS LUT Q15 trilinear (3 in, 3 out)": wc(OpCount(mul=3 * 2 + 21, add=9 + 42, cmp=12 + 21, load=24 + 6)),
    "MLP 3-16-16-3 Q15 (int32 MAC, int64 acc)": wc(OpCount(mul=macs, add=macs + 35 * 2, cmp=32 + 35, load=macs + 35 + 3)),
    "MLP 3-16-16-3 float32 (FPU32)": wc(OpCount(mul=macs, add=macs + 35, cmp=32 + 3, load=macs + 35 + 3)),
    "analytic SPS inverse + EPS matching (float)": wc(OPS_INVERSE_SPS + OPS_EPS),
    "PI + analytic inverse + EPS (firmware today)": wc(OPS_PI + OPS_INVERSE_SPS + OPS_EPS),
    "observer + explicit LUT + EPS + DC-free (proposed ISR core)": wc(OPS_OBSERVER + OpCount(mul=13, add=23, cmp=19, load=14) + OPS_EPS + OPS_DCFREE),
}
report["wcet"] = dict(cycles_per_op=CYCLES_PER_OP, mcu_hz=MCU_HZ, isr_budget_us=10.0,
                      assumptions="L1 estimate: compiled C, no CLA, 2 cycles per add/mul incl. load/store, 8 per TMU div/sqrt, 4 per compare+branch; "
                                  "fixed-point MAC counted as mul+add+load (RPT||MAC would halve it); ISR entry/exit, ADC and PWM register access not included here "
                                  "(+120 cycles, see Adaptive_MPC/results/c2000_feasibility.json)", paths=paths)
for k, v in paths.items():
    print(f"WCET {k:60s} {v['ops_total']:5d} ops {v['cycles']:6d} cycles {v['us']:6.2f} us {100*v['isr_fraction']:5.1f} %")

# =============================================================================================== (b) decision
report["decision"] = dict(
    explicit_mpc_law="LUT (Q15, 13.3 KB, trilinear): ~1 us, deterministic, quantisation error far below the PWM step; the online QP (CCS-MPC) does not fit the 10 us ISR",
    modulator_inverse="analytic SPS inverse + EPS matching in float (existing firmware, ~0.3 us): exact, no table; keeps the PI fallback path identical",
    tps_eps_map="LUT (7.4 KB Q15, 3 outputs) if TPS is ever enabled: 3x the WCET of the explicit LUT but still ~1.3 us; the MLP (0.8 KB) needs ~4x the cycles "
                "and has a larger error on the plateau-like D1/D2 map; the MLP only becomes attractive when the input dimension grows (e.g. adding L_hat and Tj -> 5-D LUT of several 100 KB)",
    mlp_verdict="not justified for the 3-input maps of this converter; kept as a documented option with a bit-exact fixed-point reference",
    offline_only="all training and table generation stay offline (PC); nothing is learned on the MCU")

# =============================================================================================== figures
fig, ax = plt.subplots(1, 3, figsize=(14, 3.8))
h = np.array(hist); ax[0].semilogy(h[:, 0], h[:, 1], label="train"); ax[0].semilogy(h[:, 0], h[:, 2], label="test"); ax[0].set_xlabel("epoch"); ax[0].set_ylabel("mse (normalised outputs)")
ax[0].set_title("MLP training (numpy Adam)"); ax[0].legend(); ax[0].grid(alpha=0.3)
ax[1].hist(err_q, bins=60, color="#2ca02c", alpha=0.8); ax[1].set_xlabel("phi error Q15 LUT - float LUT (deg)"); ax[1].set_title(f"Explicit LUT quantisation (max {np.max(np.abs(err_q)):.4f} deg)"); ax[1].grid(alpha=0.3)
phi_t = np.degrees(denorm_out(Yv)[0]); phi_f = np.degrees(denorm_out(f_val)[0]); phi_q = np.degrees(denorm_out(q_val)[0]); phi_l = np.degrees(lut_pred[:, 0])
ax[2].hist(phi_f - phi_t, bins=40, alpha=0.6, label="MLP float"); ax[2].hist(phi_q - phi_t, bins=40, alpha=0.6, label="MLP Q15"); ax[2].hist(phi_l - phi_t, bins=40, alpha=0.6, label="TPS LUT trilinear")
ax[2].set_xlabel("phi error vs optimiser, off-grid points (deg)"); ax[2].legend(fontsize=7); ax[2].set_title("TPS/EPS map surrogates"); ax[2].grid(alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "quantisation_errors.png"), dpi=130); plt.close(fig)

fig, ax = plt.subplots(1, 3, figsize=(14, 3.8))
for (V1, V2), col in (((800, 400), "C0"), ((850, 300), "C1"), ((650, 450), "C2")):
    g = dmap[(dmap.V1 == V1) & (dmap.V2 == V2)].sort_values("P")
    pr = mlp.forward(norm_in(g.V1.values, g.V2.values, g.P.values))[-1]; ph, d1, d2 = denorm_out(pr)
    ax[0].plot(g.P / 1e3, np.degrees(g.phi), "o", color=col, ms=3, label=f"{V1}/{V2} V map"); ax[0].plot(g.P / 1e3, np.degrees(ph), "-", color=col, lw=1)
    ax[1].plot(g.P / 1e3, g.D1, "o", color=col, ms=3); ax[1].plot(g.P / 1e3, d1, "-", color=col, lw=1)
    ax[2].plot(g.P / 1e3, g.D2, "o", color=col, ms=3); ax[2].plot(g.P / 1e3, d2, "-", color=col, lw=1)
ax[0].set_ylabel("phi (deg)"); ax[1].set_ylabel("D1"); ax[2].set_ylabel("D2"); [a.set_xlabel("P (kW)") for a in ax]; [a.grid(alpha=0.3) for a in ax]
ax[0].legend(fontsize=7); fig.suptitle("TPS/EPS minimum-rms ZVS modulation map (markers: optimiser; lines: MLP float)"); fig.tight_layout()
fig.savefig(os.path.join(OUT, "tps_map_vs_mlp.png"), dpi=130); plt.close(fig)

fig, ax = plt.subplots(1, 2, figsize=(12, 4))
names = list(paths.keys()); us = [paths[k]["us"] for k in names]
ax[0].barh(range(len(names)), us, color="#1f77b4"); ax[0].set_yticks(range(len(names))); ax[0].set_yticklabels(names, fontsize=7); ax[0].axvline(10, color="r", ls="--", label="ISR budget 10 us")
ax[0].set_xlabel("WCET estimate (us)"); ax[0].legend(fontsize=7); ax[0].grid(alpha=0.3, axis="x"); ax[0].invert_yaxis()
mem = {"explicit LUT Q15": report["explicit_lut"]["bytes_q15"] / 1024, "explicit LUT float32": report["explicit_lut"]["bytes_float32"] / 1024,
       "TPS LUT Q15 (3 out)": report["mlp"]["tps_lut_alternative"]["bytes_q15"] / 1024, "MLP Q15": report["mlp"]["bytes_q15_with_int32_bias"] / 1024, "analytic inverse": 0.05}
ax[1].bar(range(len(mem)), list(mem.values()), color="#ff7f0e"); ax[1].set_xticks(range(len(mem))); ax[1].set_xticklabels(list(mem.keys()), fontsize=7, rotation=15); ax[1].set_ylabel("memory (KB)")
ax[1].set_title("Memory (F28379D: 1 MB flash, 204 KB RAM)"); ax[1].grid(alpha=0.3, axis="y")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "wcet_memory.png"), dpi=130); plt.close(fig)

# =============================================================================================== (d) bit-exact test vectors
vec = FP.generate_all(write=True)
report["test_vectors"] = {k: dict(n=len(v[1]), columns=v[0]) for k, v in vec.items()}
json.dump(report, open(os.path.join(OUT, "embedded_report.json"), "w"), indent=1, default=float)
write_provenance(HERE, "embedded_inference.py", T0, [LUT_FILE, os.path.join(MPC_DIR, "dab_mpc_lib.py"), os.path.join(HERE, "fixed_point_ref.py"), DESIGN_FILE, CONTROL_FILE],
                 extra=dict(outputs=sorted(os.listdir(OUT))))
print(f"done in {time.time()-T0:.0f} s")
