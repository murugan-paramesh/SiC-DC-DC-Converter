#!/usr/bin/env python3
"""
Deterministic, C-like fixed-point reference implementation (Python integers only, no floats in the inference
path) of the two embedded inference candidates:

  1. lut3d_q15(): trilinear interpolation in a 3-D Q15 table (the explicit-MPC law, inputs e / V1 / P_hat as Q15
     normalised to the table axes) - the CHOSEN path (see embedded_inference.py / README).
  2. mlp_q15(): 3-16-16-3 ReLU multilayer perceptron with Q15 weights (per-layer power-of-two scaling), int64
     Q30 accumulation, rounding and saturation to int16 - the alternative evaluated for the TPS/EPS map.

Arithmetic conventions (mirror these exactly in C):
  * Q15: int16 in [-32768, 32767] represents x / 32768.
  * mul_q15(a, b) = sat16((a * b + 2^14) >> 15)   (round-half-up on the Q30 product, arithmetic shift).
  * Table axes are uniform: index = (x_q - x0_q) * inv_step >> 20 with inv_step = round(2^20 / step_q) (int32 product),
    the fraction f = ((x_q - x0_q) - index * step_q) * inv_step >> 5 (Q15) clipped to [0, 32767]; inputs are clamped
    to the axis range first.  Table entries are Q15 of phi / PHI_SCALE with PHI_SCALE = pi/2 rad.
  * MLP: y = sat16( round( sum_i W[i] * x[i] + b ) ) with W in Q15 after a per-layer shift s_l (W_real = W_q * 2^s_l / 32768),
    accumulation in Q30 (int64), bias in Q30, result shifted right by (15 - s_l) with rounding.
Running this file re-generates results/test_vectors_*.csv from the stored model files and checks them bit-exactly
against the existing CSVs (exit code 1 on mismatch).
"""
import os, sys, json, csv, math
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results")
Q15_ONE = 32768
INT16_MIN, INT16_MAX = -32768, 32767


def sat16(x):
    return INT16_MAX if x > INT16_MAX else (INT16_MIN if x < INT16_MIN else int(x))


def sat32(x):
    return 2147483647 if x > 2147483647 else (-2147483648 if x < -2147483648 else int(x))


def ashr(x, n):
    """Arithmetic shift right of a Python int (floor division, like C on two's-complement targets)."""
    return x >> n


def mul_q15(a, b):
    return sat16(ashr(a * b + (1 << 14), 15))


def to_q15(x, scale):
    """Float -> Q15 of x / scale, saturated (used only for data preparation, never inside the inference path)."""
    return sat16(int(np.round(x / scale * Q15_ONE)))


def from_q15(q, scale):
    return q / Q15_ONE * scale


# -------------------------------------------------------------------------------------------------- LUT path
class LutQ15:
    """
    3-D Q15 table with uniform axes.  axis_q = (x0_q, step_q, n) per dimension, all Q15 integers in the same
    normalisation as the input (input scale per axis given in meta).  table: flat list of int16, index
    ((i * n1) + j) * n2 + k.
    """

    def __init__(self, table_int16, axes_q, shape):
        self.tab = [int(v) for v in table_int16]
        self.axes = [(int(x0), int(step), int(n), int(round((1 << 20) / step))) for (x0, step, n) in axes_q]
        self.shape = tuple(int(s) for s in shape)
        assert len(self.tab) == self.shape[0] * self.shape[1] * self.shape[2]

    def _locate(self, x_q, ax):
        x0, step, n, inv = ax
        xmax = x0 + step * (n - 1)
        if x_q < x0: x_q = x0
        if x_q > xmax: x_q = xmax
        d = x_q - x0
        i = ashr(d * inv, 20)
        if i > n - 2: i = n - 2
        if i < 0: i = 0
        f = ashr((d - i * step) * inv, 5)
        if f < 0: f = 0
        if f > INT16_MAX: f = INT16_MAX
        return i, f

    def _at(self, i, j, k):
        return self.tab[(i * self.shape[1] + j) * self.shape[2] + k]

    @staticmethod
    def lerp(a, b, f):
        # a + (b - a) * f ; (b - a) fits int32 (|.| <= 65535), product fits int64; result saturated to int16
        return sat16(a + ashr((b - a) * f + (1 << 14), 15))

    def eval(self, e_q, v1_q, p_q):
        (i, fe), (j, fv), (k, fp) = self._locate(e_q, self.axes[0]), self._locate(v1_q, self.axes[1]), self._locate(p_q, self.axes[2])
        c00 = self.lerp(self._at(i, j, k), self._at(i, j, k + 1), fp)
        c01 = self.lerp(self._at(i, j + 1, k), self._at(i, j + 1, k + 1), fp)
        c10 = self.lerp(self._at(i + 1, j, k), self._at(i + 1, j, k + 1), fp)
        c11 = self.lerp(self._at(i + 1, j + 1, k), self._at(i + 1, j + 1, k + 1), fp)
        c0 = self.lerp(c00, c01, fv); c1 = self.lerp(c10, c11, fv)
        return self.lerp(c0, c1, fe)

    # --- (de)serialisation -------------------------------------------------------------------------------
    def save(self, path, meta):
        np.savez(path, table=np.array(self.tab, dtype=np.int16), axes_q=np.array([a[:3] for a in self.axes], dtype=np.int32),
                 shape=np.array(self.shape, dtype=np.int32), meta=json.dumps(meta))

    @classmethod
    def load(cls, path):
        z = np.load(path)
        return cls(z["table"], z["axes_q"], z["shape"]), json.loads(str(z["meta"]))


# -------------------------------------------------------------------------------------------------- MLP path
class MlpQ15:
    """
    Fully connected ReLU network with Q15 weights.  layers: list of (W_q (int16 [n_out][n_in]), b_q30 (int64), shift).
    W_real = W_q * 2^shift / 32768; biases stored directly in the accumulator format (Q30 * 2^-shift... see below).
    Forward: acc = sum W_q * x_q  (Q30 scaled by 2^-shift) + b_acc ; y_q = sat16(round(acc >> (15 - shift))).
    """

    def __init__(self, layers):
        self.layers = [([[int(w) for w in row] for row in W], [int(b) for b in B], int(s)) for (W, B, s) in layers]

    def eval(self, x_q):
        x = [int(v) for v in x_q]
        n_layers = len(self.layers)
        for li, (W, B, s) in enumerate(self.layers):
            y = []
            sh = 15 - s
            for row, b in zip(W, B):
                acc = b
                for w, xv in zip(row, x):
                    acc += w * xv                        # int64 accumulate of Q30-like products
                acc = sat32(ashr(acc + (1 << (sh - 1)), sh)) if sh > 0 else sat32(acc << (-sh))
                v = sat16(acc)
                if li < n_layers - 1 and v < 0:
                    v = 0                                # ReLU
                y.append(v)
            x = y
        return x

    def save(self, path, meta):
        np.savez(path, n_layers=len(self.layers), meta=json.dumps(meta),
                 **{f"W{i}": np.array(W, dtype=np.int16) for i, (W, B, s) in enumerate(self.layers)},
                 **{f"B{i}": np.array(B, dtype=np.int64) for i, (W, B, s) in enumerate(self.layers)},
                 **{f"S{i}": np.array(s, dtype=np.int32) for i, (W, B, s) in enumerate(self.layers)})

    @classmethod
    def load(cls, path):
        z = np.load(path)
        n = int(z["n_layers"])
        return cls([(z[f"W{i}"], z[f"B{i}"], int(z[f"S{i}"])) for i in range(n)]), json.loads(str(z["meta"]))


def quantise_mlp(weights, biases, act_max=None):
    """
    Float weights -> (W_q, B_acc, shift) per layer with a power-of-two per-layer weight scale so that max|W_q| <= 32767.
    act_max: maximum |activation| of each hidden layer on the training set; the hidden activations are rescaled by
    2^-k_l (k_l = ceil(log2(1.25 act_max))) so that they fit Q15 - the scale is folded into the weights/biases of the
    layer and undone in the weights of the next layer (the network function is unchanged in float arithmetic).
    Returns (layers, activation_shifts).
    """
    weights = [np.array(W, float) for W in weights]; biases = [np.array(b, float) for b in biases]
    shifts = []
    if act_max is not None:
        for l, a in enumerate(act_max):
            k = max(0, int(math.ceil(math.log2(1.25 * a)))) if a > 0 else 0
            weights[l] = weights[l] / 2 ** k; biases[l] = biases[l] / 2 ** k; weights[l + 1] = weights[l + 1] * 2 ** k
            shifts.append(k)
    layers = []
    for W, b in zip(weights, biases):
        wmax = float(np.max(np.abs(W)))
        s = 0
        while wmax * Q15_ONE / (2 ** s) > INT16_MAX:
            s += 1
        Wq = np.clip(np.round(W * Q15_ONE / 2 ** s), INT16_MIN, INT16_MAX).astype(np.int64)
        # bias in accumulator units: acc represents value * 2^(30 - s); b_acc = b * 2^(30 - s)
        Bq = np.round(b * 2 ** (30 - s)).astype(np.int64)
        layers.append((Wq.tolist(), Bq.tolist(), s))
    return layers, shifts


# -------------------------------------------------------------------------------------------------- test vectors
def write_vectors(path, header_comment, columns, rows):
    with open(path, "w", newline="") as f:
        f.write("# " + header_comment + "\n")
        w = csv.writer(f); w.writerow(columns); w.writerows(rows)


def read_vectors(path):
    rows = []
    with open(path) as f:
        for line in f:
            if line.startswith("#"):
                continue
            rows.append(line.strip().split(","))
    cols = rows[0]; data = [[int(v) for v in r] for r in rows[1:]]
    return cols, data


def make_lut_vectors(lut, n_random=200, seed=20260101):
    rng = np.random.default_rng(seed)
    pts = []
    corners = [INT16_MIN, -20000, -1, 0, 1, 20000, INT16_MAX]
    for a in corners:
        for b in (INT16_MIN, 0, INT16_MAX):
            for c in (INT16_MIN, 0, INT16_MAX):
                pts.append((a, b, c))
    for _ in range(n_random):
        pts.append(tuple(int(v) for v in rng.integers(INT16_MIN, INT16_MAX + 1, 3)))
    return [(e, v, p, lut.eval(e, v, p)) for (e, v, p) in pts]


def make_mlp_vectors(mlp, n_random=200, seed=20260102):
    rng = np.random.default_rng(seed)
    pts = [(a, b, c) for a in (INT16_MIN, 0, INT16_MAX) for b in (INT16_MIN, 0, INT16_MAX) for c in (INT16_MIN, 0, INT16_MAX)]
    for _ in range(n_random):
        pts.append(tuple(int(v) for v in rng.integers(INT16_MIN, INT16_MAX + 1, 3)))
    return [tuple(p) + tuple(mlp.eval(p)) for p in pts]


def generate_all(write=True):
    """Regenerate both vector sets from the stored models; returns dict name -> rows."""
    out = {}
    lut_path = os.path.join(OUT, "empc_lut_q15.npz"); mlp_path = os.path.join(OUT, "tps_mlp_q15.npz")
    if os.path.exists(lut_path):
        lut, meta = LutQ15.load(lut_path)
        rows = make_lut_vectors(lut)
        out["test_vectors_lut_q15.csv"] = (["e_q15", "v1_q15", "p_q15", "phi_q15"], rows,
                                           f"explicit-MPC LUT Q15 trilinear; input scales: e/{meta['scales']['e_V']} V, (V1-{meta['scales']['v1_offset_V']})/{meta['scales']['v1_V']} V, "
                                           f"P_hat/{meta['scales']['p_W']} W; output phi/(pi/2) Q15; see fixed_point_ref.py")
    if os.path.exists(mlp_path):
        mlp, meta = MlpQ15.load(mlp_path)
        rows = make_mlp_vectors(mlp)
        out["test_vectors_mlp_q15.csv"] = (["v1_q15", "v2_q15", "p_q15", "phi_q15", "d1_q15", "d2_q15"], rows,
                                           f"TPS/EPS MLP 3-16-16-3 ReLU Q15; inputs {meta['input_norm']}; outputs {meta['output_norm']}; see fixed_point_ref.py")
    if write:
        for name, (cols, rows, hdr) in out.items():
            write_vectors(os.path.join(OUT, name), hdr, cols, rows)
    return out


if __name__ == "__main__":
    ok = True
    gen = generate_all(write=False)
    for name, (cols, rows, hdr) in gen.items():
        path = os.path.join(OUT, name)
        if not os.path.exists(path):
            print(f"{name}: missing (run embedded_inference.py first)"); ok = False; continue
        cols0, data0 = read_vectors(path)
        same = (cols0 == cols) and (len(data0) == len(rows)) and all(list(r) == d for r, d in zip(rows, data0))
        print(f"{name}: {len(rows)} vectors, bit-exact match = {same}")
        ok &= same
    sys.exit(0 if ok else 1)
