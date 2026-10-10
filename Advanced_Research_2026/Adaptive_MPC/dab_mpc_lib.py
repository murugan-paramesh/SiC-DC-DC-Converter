"""
Shared library for Advanced_Research_2026/Adaptive_MPC and Embedded_AI.

Contents
  * repo paths, design values, provenance helper
  * pwl_period(): exact period quantities of the lossless piecewise-linear DAB model (vectorised over
    candidates) - used by the FCS-MPC, the RLS regressor, the TPS/EPS map generator and the ZVS maps.
    Validated against dabtools.dab.dab_model.DABPoint (see results/pwl_validation.csv).
  * MeasuredDABPlant: dabtools DABPlant with period-average LV-link current and rms accumulators
    (identical dynamics, extra bookkeeping only) and a 12-bit ADC measurement model.
  * controllers: PIBaseline (wraps dabtools DABController), CCSMPC (linearised averaged model, box QP
    by accelerated projected gradient), FCSMPC (candidate enumeration with one-step period-average
    prediction), ExplicitMPC (3-D LUT of the CCS law), AdaptiveMPC (CCS + scalar RLS for 1/L),
    RobustMPC (CCS with constraint/gain tightening for L in [0.8, 1.2] L_nom).
  * scenario runner + metrics.
All numbers are simulation results of the project model; nothing here is hardware-validated.
"""
import os, sys, json, math, time, hashlib, platform
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESEARCH = os.path.dirname(HERE)
REPO = os.path.dirname(RESEARCH)
PROJ = os.path.join(REPO, "SiC_6k6_Industrial_DAB")
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)
from dabtools.dab.sim_switched import DABPlant                      # noqa: E402
from dabtools.dab.control import DABController                      # noqa: E402
from dabtools.dab import dab_model as M                             # noqa: E402
from dabtools.dab.devices import DEVICES                            # noqa: E402

DESIGN_FILE = os.path.join(PROJ, "04_Design_Calculations", "design_values.json")
CONTROL_FILE = os.path.join(PROJ, "11_Control_Algorithms", "control_params.json")
DESIGN = json.load(open(DESIGN_FILE))
CTRL = json.load(open(CONTROL_FILE))

L_NOM = DESIGN["L"]                      # 64 uH
N_RATIO = DESIGN["spec"]["n"]            # 2
FS = DESIGN["spec"]["fs"]                # 100 kHz
TS = 1.0 / FS
P_RATED = DESIGN["spec"]["P"]            # 6600 W
C2 = CTRL["C2"]                          # 1.12 mF (link + external, control design value)
C1 = DESIGN["dclink"]["C1"] + 500e-6     # as in 05_Simulation/run_switched_sim.py
C_PAR = DESIGN["C_par"]
T_DEAD = DESIGN["t_dead"]
PHI_MAX = math.radians(CTRL["phi_max_deg"])
D_MIN = CTRL["D_min"]
I_LIM_PK = DESIGN["I_limit_pk"]          # 24 A (HV-referred) controller peak-current limit
I_TRIP_HW = DESIGN["I_trip_hw"]          # 32 A hardware trip
PHI_DEAD_COMP = CTRL["phi_dead_comp_rad"]
V2_REF = 400.0
PWM_STEP = 2 * math.pi / 1000            # EPWM phase resolution (10 ns at 100 kHz)
DEV1, DEV2 = DEVICES[DESIGN["dev1"]], DEVICES[DESIGN["dev2"]]
TWO_PI = 2 * math.pi


# ----------------------------------------------------------------------------------------------
# provenance
# ----------------------------------------------------------------------------------------------
def _git_commit():
    try:
        head = open(os.path.join(REPO, ".git", "HEAD")).read().strip()
        if head.startswith("ref:"):
            ref = head.split(" ", 1)[1]
            p = os.path.join(REPO, ".git", ref)
            if os.path.exists(p):
                return open(p).read().strip()
            for line in open(os.path.join(REPO, ".git", "packed-refs")):
                if line.strip().endswith(ref):
                    return line.split()[0]
        return head
    except Exception:
        return "unknown"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def write_provenance(module_dir, script_name, t_start, inputs, extra=None):
    """Merge this script's record into <module_dir>/provenance.json (keyed by script name)."""
    import numpy, scipy, matplotlib
    path = os.path.join(module_dir, "provenance.json")
    prov = json.load(open(path)) if os.path.exists(path) else {}
    rec = dict(python=platform.python_version(), numpy=numpy.__version__, scipy=scipy.__version__,
               matplotlib=matplotlib.__version__, platform=platform.platform(), git_commit=_git_commit(),
               wall_time_s=round(time.time() - t_start, 1),
               input_files={os.path.relpath(p, REPO): sha256(p) for p in inputs},
               seeds=dict(numpy_default=20260101))
    if extra:
        rec.update(extra)
    prov[script_name] = rec
    json.dump(prov, open(path, "w"), indent=1)
    return prov


# ----------------------------------------------------------------------------------------------
# exact piecewise-linear period model (lossless), vectorised over candidates
# ----------------------------------------------------------------------------------------------
def _three_level(theta, amp, duty, shift):
    th = (theta - shift) % TWO_PI
    half = duty * math.pi / 2
    pos = (th > math.pi / 2 - half) & (th <= math.pi / 2 + half)
    neg = (th > 3 * math.pi / 2 - half) & (th <= 3 * math.pi / 2 + half)
    return amp * (pos.astype(float) - neg.astype(float))


def pwl_period(V1, V2p, L, fs, phi, D1=1.0, D2=1.0):
    """
    Period quantities of the lossless DAB (same conventions as dabtools.dab.dab_model.waveforms) from the
    exact piecewise-linear inductor current, for arrays of candidates (phi, D1, D2 broadcast to shape (M,)).
    Returns dict: P (W, port 1 -> 2), I2 (period-average LV-bridge current referred to port 1, i.e. mean(s2*i);
    multiply by n for the real LV current), Irms, Ipk (port-1 referred), zvs1, zvs2 (minimum edge current
    with the ZVS sign convention of DABPoint.switching_currents, before subtracting I_min).
    The whole current waveform scales with 1/L (used by the RLS regressor).
    """
    phi, D1, D2 = np.broadcast_arrays(np.atleast_1d(np.asarray(phi, float)), np.asarray(D1, float), np.asarray(D2, float))
    Mn = phi.shape[0]
    w = TWO_PI * fs
    h1 = D1 * math.pi / 2
    h2 = D2 * math.pi / 2
    b = np.stack([math.pi / 2 - h1, math.pi / 2 + h1, 3 * math.pi / 2 - h1, 3 * math.pi / 2 + h1,
                  math.pi / 2 - h2 + phi, math.pi / 2 + h2 + phi, 3 * math.pi / 2 - h2 + phi, 3 * math.pi / 2 + h2 + phi], axis=1) % TWO_PI
    b = np.concatenate([np.zeros((Mn, 1)), b], axis=1)
    b.sort(axis=1)
    b = np.concatenate([b, np.full((Mn, 1), TWO_PI)], axis=1)                      # (M, 10) breakpoints
    dth = np.diff(b, axis=1)                                                        # (M, 9)
    mid = 0.5 * (b[:, :-1] + b[:, 1:])
    v1 = _three_level(mid, V1, D1[:, None], 0.0)
    v2 = _three_level(mid, V2p, D2[:, None], phi[:, None])
    slope = (v1 - v2) / (w * L)
    ib = np.concatenate([np.zeros((Mn, 1)), np.cumsum(slope * dth, axis=1)], axis=1)   # (M, 10)
    ia, ic = ib[:, :-1], ib[:, 1:]
    mean = np.sum(0.5 * (ia + ic) * dth, axis=1) / TWO_PI
    ib = ib - mean[:, None]
    ia, ic = ib[:, :-1], ib[:, 1:]
    seg_mean = 0.5 * (ia + ic)
    P = np.sum(v1 * seg_mean * dth, axis=1) / TWO_PI
    s2 = np.sign(v2)
    I2 = np.sum(s2 * seg_mean * dth, axis=1) / TWO_PI
    Irms = np.sqrt(np.sum(dth * (ia * ia + ia * ic + ic * ic) / 3.0, axis=1) / TWO_PI)
    Ipk = np.max(np.abs(ib), axis=1)
    # edges: breakpoint k (k = 0..9) separates segment k-1 (wrapping) and segment k
    def edge_min(v, port):
        vb = np.concatenate([v[:, -1:], v], axis=1)            # value before breakpoint k (k = 0..9)
        va = np.concatenate([v, v[:, :1]], axis=1)             # value after
        e = va - vb
        sgn = -np.sign(e) if port == 1 else np.sign(e)
        iz = sgn * ib
        iz = np.where(np.abs(e) > 1e-9, iz, np.inf)
        return np.min(iz, axis=1)
    return dict(P=P, I2=I2, Irms=Irms, Ipk=Ipk, zvs1=edge_min(v1, 1), zvs2=edge_min(v2, 2))


def zvs_i_min(V1, V2, L, n, Coss1=None, Coss2=None, C_par=C_PAR):
    """I_min of both bridges (port-1 referred), same formula as 04_Design_Calculations/dab_design.py."""
    Coss1 = DEV1["Coss_er"] if Coss1 is None else Coss1
    Coss2 = DEV2["Coss_er"] if Coss2 is None else Coss2
    Imin1 = M.zvs_current_min(Coss1, V1, L, C_par)
    Imin2 = M.zvs_current_min(Coss2, V2, L / n ** 2, C_par * n ** 2) / n
    return Imin1, Imin2


def phi_for_power_pwl(V1, V2, n, L, fs, P, D1=1.0, D2=1.0, iters=40):
    """Bisection on the exact piecewise-linear model for |phi| <= pi/2 (vectorised over P)."""
    P = np.atleast_1d(np.asarray(P, float))
    lo = np.zeros_like(P); hi = np.full_like(P, math.pi / 2)
    sgn = np.sign(P); sgn[sgn == 0] = 1.0
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        Pm = pwl_period(V1, n * V2, L, fs, sgn * mid, D1, D2)["P"]
        under = np.abs(Pm) < np.abs(P)
        lo = np.where(under, mid, lo); hi = np.where(under, hi, mid)
    phi = sgn * 0.5 * (lo + hi)
    Pm = pwl_period(V1, n * V2, L, fs, phi, D1, D2)["P"]
    feasible = np.abs(np.abs(Pm) - np.abs(P)) < 0.01 * np.maximum(np.abs(P), 1.0)
    return phi, feasible


def eps_matching(v1, v2, n=N_RATIO, D_min=D_MIN):
    d = n * v2 / max(v1, 1.0)
    if d < 1.0:
        return max(D_min, min(1.0, d)), 1.0
    return 1.0, max(D_min, min(1.0, 1.0 / d))


def i2_sps(phi, v1, n=N_RATIO, fs=FS, L=L_NOM):
    """Period-average LV-link current of the SPS averaged model (A, actual LV side)."""
    return n * v1 * phi * (math.pi - abs(phi)) / (2 * math.pi ** 2 * fs * L)


def di2_dphi_sps(phi, v1, n=N_RATIO, fs=FS, L=L_NOM):
    return n * v1 * (math.pi - 2 * abs(phi)) / (2 * math.pi ** 2 * fs * L)


def phi_from_i2_sps(I2, v1, n=N_RATIO, fs=FS, L=L_NOM, phi_max=PHI_MAX):
    """Inverse of i2_sps (the firmware's dab_phi_from_power in current form, without dead-time term)."""
    if v1 < 50:
        return 0.0
    Imax = n * v1 / (8 * fs * L)
    I2 = max(-0.98 * Imax, min(0.98 * Imax, I2))
    c = 2 * math.pi ** 2 * fs * L * abs(I2) / (n * v1)
    phi = (math.pi - math.sqrt(max(0.0, math.pi ** 2 - 4 * c))) / 2
    return math.copysign(min(phi, phi_max), I2)


def phi_bound_peak(v1, v2, L, n=N_RATIO, fs=FS, I_lim=I_LIM_PK, phi_max=PHI_MAX):
    """
    Largest |phi| whose SPS peak current (max of the two edge currents, affine in phi) stays below I_lim:
    I0 = (V1 pi + V2p (2 phi - pi)) / (2 w L), I1 = (V1 (2 phi - pi) + V2p pi) / (2 w L).
    Conservative under EPS (the D < 1 bridge reduces the peak).
    """
    w = TWO_PI * fs
    V2p = n * v2
    b = []
    for A, B in ((v1, V2p), (V2p, v1)):
        if B > 1e-6:
            b.append((2 * w * L * I_lim - A * math.pi + B * math.pi) / (2 * B))
    return max(0.0, min([phi_max] + b))


# ----------------------------------------------------------------------------------------------
# plant with measurement bookkeeping
# ----------------------------------------------------------------------------------------------
def i_ss_at_zero(V1, V2p, L, fs, phi, D1, D2):
    """Steady-state lossless inductor current at theta = 0 (port-1 referred) from the piecewise-linear model."""
    phi, D1, D2 = np.broadcast_arrays(np.atleast_1d(np.asarray(phi, float)), np.asarray(D1, float), np.asarray(D2, float))
    Mn = phi.shape[0]; w = TWO_PI * fs
    h1 = D1 * math.pi / 2; h2 = D2 * math.pi / 2
    b = np.stack([math.pi / 2 - h1, math.pi / 2 + h1, 3 * math.pi / 2 - h1, 3 * math.pi / 2 + h1,
                  math.pi / 2 - h2 + phi, math.pi / 2 + h2 + phi, 3 * math.pi / 2 - h2 + phi, 3 * math.pi / 2 + h2 + phi], axis=1) % TWO_PI
    b = np.concatenate([np.zeros((Mn, 1)), b], axis=1); b.sort(axis=1)
    b = np.concatenate([b, np.full((Mn, 1), TWO_PI)], axis=1)
    dth = np.diff(b, axis=1); mid = 0.5 * (b[:, :-1] + b[:, 1:])
    slope = (_three_level(mid, V1, D1[:, None], 0.0) - _three_level(mid, V2p, D2[:, None], phi[:, None])) / (w * L)
    ib = np.concatenate([np.zeros((Mn, 1)), np.cumsum(slope * dth, axis=1)], axis=1)
    mean = np.sum(0.5 * (ib[:, :-1] + ib[:, 1:]) * dth, axis=1) / TWO_PI
    return float((ib[:, 0] - mean)[0])


class MeasuredDABPlant(DABPlant):
    """
    DABPlant with identical dynamics plus period accumulators: i2_avg (A, LV side), iL_rms, ipk, and an optional
    DC-bias-free transition modulator (dc_free=True): when the command (phi, D1, D2) changes, the first edge of
    the LV-bridge waveform after the period boundary is moved by delta = (i_ss,new(0) - i_ss,old(0)) w L / h_edge
    (h_edge = voltage step of that edge) so that the inductor current lands on the new steady state after one
    period instead of carrying a DC offset that decays with tau = L / R_s (~210 us).  For SPS this reduces to
    the classical 'half the phase step in the first half period'.  The correction is feedforward (lossless model).
    """

    def __init__(self, *a, dc_free=False, **k):
        super().__init__(*a, **k)
        self.i2_avg = 0.0; self.i1_avg = 0.0; self.iL_rms = 0.0
        self.dc_free = dc_free
        self.prev_cmd = None
        self.dc_moves = 0

    def _transition_s2(self, phi, D1, D2):
        """LV-bridge waveform (units of n v2) for the transition period, with the first edge moved (see class doc)."""
        th = (np.arange(self.N_sub) + 0.5) / self.N_sub * TWO_PI
        V2p = self.n * self.v2
        if V2p < 1.0 or self.prev_cmd is None or self.prev_cmd == (phi, D1, D2):
            return None
        p0, a0, b0 = self.prev_cmd
        i_old = i_ss_at_zero(self.v1, V2p, self.L, self.fs, p0, a0, b0)
        i_new = i_ss_at_zero(self.v1, V2p, self.L, self.fs, phi, D1, D2)
        delta_i = i_new - i_old
        if D2 >= 1.0:
            edges = [((phi) % TWO_PI, 2.0), ((phi + math.pi) % TWO_PI, -2.0)]
        else:
            h2 = D2 * math.pi / 2
            edges = [((phi + math.pi / 2 - h2) % TWO_PI, 1.0), ((phi + math.pi / 2 + h2) % TWO_PI, -1.0),
                     ((phi + 3 * math.pi / 2 - h2) % TWO_PI, -1.0), ((phi + 3 * math.pi / 2 + h2) % TWO_PI, 1.0)]
        edges.sort()
        v0 = float(_three_level(np.array([TWO_PI - 1e-9]), 1.0, D2, phi)[0])        # value just before theta = 0
        th_e, h_e = edges[0]
        delta = delta_i * TWO_PI * self.fs * self.L / (h_e * V2p)
        nxt = edges[1][0] if len(edges) > 1 else TWO_PI
        th_new = min(max(th_e + delta, 0.0), nxt - 1e-6)
        edges[0] = (th_new, h_e)
        s2 = np.full(self.N_sub, v0)
        for te, he in edges:
            s2 += he * (th > te)
        self.dc_moves += 1
        return s2

    def run_period(self, phi, D1=1.0, D2=1.0, record=False):
        s1, s2 = self.period_voltages(phi, D1, D2)
        if self.dc_free:
            s2t = self._transition_s2(phi, D1, D2)
            if s2t is not None:
                s2 = s2t
        self.prev_cmd = (phi, D1, D2)
        rec = [] if record else None
        self.ipk = 0.0
        acc2 = 0.0; acc1 = 0.0; acc_sq = 0.0
        L, n, dt, C1, C2, R_s = self.L, self.n, self.dt, self.C1, self.C2, self.R_s
        iL, v1, v2, t = self.iL, self.v1, self.v2, self.t
        load = self.load
        for k in range(self.N_sub):
            va = s1[k] * v1
            vb = s2[k] * n * v2
            iL += (va - vb - R_s * iL) / L * dt
            a = abs(iL)
            if a > self.ipk:
                self.ipk = a
            i_br1 = iL * s1[k]
            i_src = (self.V1_src - v1) / self.R1_src
            v1 += (i_src - i_br1) / C1 * dt
            i_br2 = iL * s2[k] * n
            v2 += (i_br2 - load(v2, t)) / C2 * dt
            t += dt
            acc2 += i_br2; acc1 += i_br1; acc_sq += iL * iL
            if record:
                rec.append((t, va, vb, iL, v1, v2, i_br1, i_br2))
        self.iL, self.v1, self.v2, self.t = iL, v1, v2, t
        self.i2_avg = acc2 / self.N_sub; self.i1_avg = acc1 / self.N_sub
        self.iL_rms = math.sqrt(acc_sq / self.N_sub)
        return rec


class ADC:
    """12-bit measurement model: V1 0-1000 V, V2 0-500 V (07_KiCad: AMC1311 chains), i2 +/-50 A, 0.5 LSB rms noise."""

    def __init__(self, seed=20260101, noise_lsb=0.5):
        self.rng = np.random.default_rng(seed)
        self.q = dict(v1=1000 / 4096, v2=500 / 4096, i2=100 / 4096)
        self.noise = noise_lsb

    def measure(self, plant):
        out = {}
        for key, val in (("v1", plant.v1), ("v2", plant.v2), ("i2", plant.i2_avg)):
            q = self.q[key]
            out[key] = q * round((val + self.noise * q * self.rng.standard_normal()) / q)
        out["i_pk"] = plant.ipk
        out["T"] = 40.0; out["precharge_ok"] = True
        return out


# ----------------------------------------------------------------------------------------------
# operation counting (for the C2000 WCET estimate)
# ----------------------------------------------------------------------------------------------
class OpCount(dict):
    KEYS = ("mul", "add", "div", "sqrt", "cmp", "load")

    def __init__(self, **k):
        super().__init__({x: 0 for x in self.KEYS}); self.update(k)

    def __add__(self, o):
        r = OpCount(); [r.__setitem__(k, self[k] + o.get(k, 0)) for k in self.KEYS]; return r

    def scaled(self, f):
        r = OpCount(); [r.__setitem__(k, int(round(self[k] * f))) for k in self.KEYS]; return r

    @property
    def total(self):
        return sum(self[k] for k in self.KEYS)


# per-op cycle assumptions, TMS320F28379D (C28x + FPU32 + TMU, 200 MHz), compiled C without hand assembly
CYCLES_PER_OP = dict(mul=2, add=2, div=8, sqrt=8, cmp=4, load=2)
ISR_OVERHEAD_CYCLES = 60 + 40 + 20     # context save/restore, 4 ADC results read + scaling, 3 EPWM register writes
MCU_HZ = 200e6
ISR_BUDGET_S = 10e-6

OPS_INVERSE_SPS = OpCount(mul=9, add=5, div=2, sqrt=1, cmp=5, load=4)     # dab_phi_from_power
OPS_EPS = OpCount(mul=1, add=0, div=2, cmp=4, load=2)                       # dab_eps_matching
OPS_PI = OpCount(mul=3, add=3, cmp=2, load=3)
OPS_PROTECTION = OpCount(cmp=9, load=9)
OPS_OBSERVER = OpCount(mul=6, add=6, cmp=0, load=4)                         # 2-state disturbance observer incl. i2_sps
OPS_PWL = OpCount(mul=120, add=110, div=2, sqrt=1, cmp=60, load=30)         # one pwl_period() evaluation (one candidate)
OPS_DCFREE = OpCount(mul=14, add=12, div=1, cmp=6, load=6)                 # DC-free transition: i_ss(0) old/new (closed form) + edge move


def wcet_us(ops: OpCount):
    cyc = ISR_OVERHEAD_CYCLES + sum(ops[k] * CYCLES_PER_OP[k] for k in OpCount.KEYS)
    return cyc, cyc / MCU_HZ * 1e6, cyc / MCU_HZ / ISR_BUDGET_S


# ----------------------------------------------------------------------------------------------
# controllers.  Common interface: reset(v2_ref), set_mode(mode, P_ref), step(m, ref, t) -> (phi, D1, D2)
#   m = dict(v1, v2, i2, i_pk)  (ADC measurements at the period boundary); the returned command is applied
#   to the next period -> same one-period measurement/actuation structure as 05_Simulation and the firmware.
# ----------------------------------------------------------------------------------------------
class PIBaseline:
    """Project baseline: dabtools DABController (PI on v2 -> power command -> SPS inverse -> EPS matching)."""
    name = "PI"

    def __init__(self, use_eps=True, soft_start_s=0.05, L=L_NOM):
        self.ctl = DABController(L, N_RATIO, FS, CTRL["kp"], CTRL["ki"], P_max=1.1 * P_RATED, phi_max=PHI_MAX,
                                 v2_ref=V2_REF, soft_start_s=soft_start_s)
        self.ctl.phi_dead_comp = 0.0          # the DABPlant model has no dead time -> no dead-time term in the inverse
        self.ctl.use_eps = use_eps
        self.use_eps = use_eps
        self.ctl.state = "RUN"; self.ctl.ss_scale = 1.0
        self.mode = "CV"

    def set_mode(self, mode, P_ref=0.0, soft_start=False, soft_start_s=0.05):
        self.ctl.mode = mode; self.ctl.P_ref = P_ref; self.ctl.soft_start_s = soft_start_s
        if soft_start:
            self.ctl.state = "INIT"; self.ctl.pi.reset()
        else:
            self.ctl.state = "RUN"; self.ctl.ss_scale = 1.0

    def step(self, m, ref, t):
        mm = dict(v1=m["v1"], v2=m["v2"], i_pk=m["i_pk"], T=40, precharge_ok=True)
        if self.ctl.mode == "CP":
            self.ctl.P_ref = ref
        return self.ctl.step(mm)

    def ops(self):
        return OPS_PROTECTION + OPS_PI + OPS_INVERSE_SPS + (OPS_EPS if self.use_eps else OpCount())


class DisturbanceObserver:
    """
    Augmented averaged model x = [v2, d], v2+ = v2 + a (i2(u) - d), d+ = d, a = Ts / C2, y = v2.
    Deadbeat-type Luenberger gains for a double pole at z = p: l1 = 2 (1 - p), l2 = -(1 - p)^2 / a.
    d = effective disturbance = load current + model mismatch (EPS, losses) -> offset-free tracking.
    """

    def __init__(self, a, pole=0.90):
        self.a = a; self.l1 = 2 * (1 - pole); self.l2 = -(1 - pole) ** 2 / a
        self.v2_hat = 0.0; self.d_hat = 0.0

    def reset(self, v2, d=0.0):
        self.v2_hat, self.d_hat = v2, d

    def update(self, v2_meas, i2_applied):
        v2_pred = self.v2_hat + self.a * (i2_applied - self.d_hat)
        inn = v2_meas - v2_pred
        self.v2_hat = v2_pred + self.l1 * inn
        self.d_hat = self.d_hat + self.l2 * inn
        return self.d_hat


class CCSMPC:
    """
    Continuous-control-set MPC on the linearised averaged model.
      state v2 (+ disturbance d from the observer), input phi, horizon N
      i2(phi) ~= i2(phi0) + g (phi - phi0),  g = n V1 (pi - 2|phi0|) / (2 pi^2 fs L),  phi0 = last command
      v2_{j+1} = v2_0 + a sum_{i<=j} (i2_0 + g (p_i - phi0) - d_hat)          (a = Ts / C2)
      J = sum_j q (v2_{j+1} - ref)^2 + r (p_j - p_{j-1})^2,  p_{-1} = phi0
      |p_j| <= phi_bar(V1, V2, I_lim, L)  (phi_max and SPS peak-current bound, both affine -> box)
    The constraint set is a box in p, so projected gradient converges to the exact QP optimum.  Solver:
    Nesterov accelerated projected gradient, fixed K iterations, warm start with the shifted previous solution.
    Structure MᵀM p = (a g)^2 Tᵀ T p is evaluated with cumulative sums -> O(N) per iteration.
    CP mode: tracks the period-average current i2_ref = P_ref / v2 with the same QP (reference on i2).
    """
    name = "CCS-MPC"

    def __init__(self, N=8, q=1.0, r=16.0, K=20, obs_pole=0.90, use_eps=True, L=L_NOM, I_lim=I_LIM_PK,
                 L_constraint=None, L_gain=None, name=None):
        self.N, self.q, self.r, self.K = N, q, r, K
        self.use_eps = use_eps
        self.L = L                                  # model inductance (adaptive variants update it)
        self.L_constraint = L_constraint or L       # inductance used for the peak-current bound (robust: 0.8 L)
        self.L_gain = L_gain                        # inductance used for the prediction gain (robust: 0.8 L)
        self.I_lim = I_lim
        self.a = TS / C2
        self.obs = DisturbanceObserver(self.a, obs_pole)
        self.phi = 0.0; self.D1 = 1.0; self.D2 = 1.0
        self.p_warm = np.zeros(N)
        self.mode = "CV"; self.P_ref = 0.0
        self.di = 0.0                               # CP mode: filtered mismatch i2_meas - i2_model (offset-free power tracking)
        self.di_pole = obs_pole
        if name:
            self.name = name

    def set_mode(self, mode, P_ref=0.0, soft_start=False, soft_start_s=0.05):
        self.mode = mode; self.P_ref = P_ref

    def reset(self, v2):
        self.obs.reset(v2, 0.0); self.phi = 0.0; self.p_warm[:] = 0.0; self.di = 0.0

    # model hooks (AdaptiveMPC overrides the inductance used here)
    def _i2_model(self, phi, v1):
        return i2_sps(phi, v1, L=self.L)

    def _gain(self, phi, v1):
        return di2_dphi_sps(phi, v1, L=(self.L_gain or self.L))

    def solve_box_qp(self, c, phi0, g, pbar):
        """min_p q||a g T p + c||^2 + r||D p - phi0 e1||^2  s.t. |p| <= pbar  (accelerated projected gradient)."""
        N, q, r, a = self.N, self.q, self.r, self.a
        ag = a * g
        lam = 2 * (q * ag * ag * N * (N + 1) / 2 + 4 * r)          # upper bound of the largest Hessian eigenvalue
        step = 1.0 / lam
        p = np.clip(self.p_warm, -pbar, pbar)
        y = p.copy(); p_prev = p.copy()
        for k in range(self.K):
            Tp = np.cumsum(y)                                      # T y
            res = ag * Tp + c                                      # prediction error
            grad_track = 2 * q * ag * np.cumsum(res[::-1])[::-1]   # Tᵀ res
            dp = np.diff(np.concatenate(([phi0], y)))              # D y - phi0 e1
            grad_rate = 2 * r * (dp - np.concatenate((dp[1:], [0.0])))   # Dᵀ dp
            p_new = np.clip(y - step * (grad_track + grad_rate), -pbar, pbar)
            beta = k / (k + 3.0)
            y = p_new + beta * (p_new - p_prev)
            p_prev = p_new
        return p_new

    def step(self, m, ref, t):
        v1, v2 = m["v1"], m["v2"]
        # observer update with the command applied during the last period
        i2_model_prev = self._i2_model(self.phi, v1)
        d_hat = self.obs.update(v2, i2_model_prev)
        self.di = self.di_pole * self.di + (1 - self.di_pole) * (m["i2"] - i2_model_prev)
        phi0 = self.phi
        g = self._gain(phi0, v1)
        i2_0 = self._i2_model(phi0, v1)
        pbar = phi_bound_peak(v1, v2, self.L_constraint, I_lim=self.I_lim)
        N = self.N
        if self.mode == "CV":
            # c_j = v2_0 + a (j+1)(i2_0 - g phi0 - d) - ref
            c = v2 + self.a * np.arange(1, N + 1) * (i2_0 - g * phi0 - d_hat) - ref
            p = self.solve_box_qp(c, phi0, g, pbar)
        else:
            # CP: regulate i2 to i2_ref = P_ref / v2 (same QP with a = 1: predicted i2_j = i2_0 + g (p_j - phi0) - i2_ref)
            i2_ref = ref / max(v2, 40.0) - self.di               # measured-current correction (the PI baseline has none)
            c = np.full(N, i2_0 - g * phi0 - i2_ref)
            p = self._solve_static(c, phi0, g, pbar)
        self.p_warm = np.concatenate((p[1:], p[-1:]))
        self.phi = float(p[0])
        if self.use_eps:
            self.D1, self.D2 = eps_matching(v1, v2)
        else:
            self.D1, self.D2 = 1.0, 1.0
        return self.phi, self.D1, self.D2

    def _solve_static(self, c, phi0, g, pbar):
        """CP mode: min sum_j q (g p_j + c_j)^2 + r (p_j - p_{j-1})^2, |p| <= pbar."""
        N, q, r = self.N, self.q, self.r
        lam = 2 * (q * g * g + 4 * r); step = 1.0 / lam
        p = np.clip(self.p_warm, -pbar, pbar); y = p.copy(); p_prev = p.copy()
        for k in range(self.K):
            grad_track = 2 * q * g * (g * y + c)
            dp = np.diff(np.concatenate(([phi0], y)))
            grad_rate = 2 * r * (dp - np.concatenate((dp[1:], [0.0])))
            p_new = np.clip(y - step * (grad_track + grad_rate), -pbar, pbar)
            y = p_new + (k / (k + 3.0)) * (p_new - p_prev); p_prev = p_new
        return p_new

    def ops(self):
        N, K = self.N, self.K
        per_iter = OpCount(mul=3 * N + 3, add=7 * N, cmp=2 * N, load=2 * N)
        setup = OpCount(mul=12, add=10, div=3, cmp=6, load=8) + OPS_OBSERVER
        return OPS_PROTECTION + setup + per_iter.scaled(K) + (OPS_EPS if self.use_eps else OpCount())


class RobustMPC(CCSMPC):
    """
    Tube-style CCS-MPC for L in [0.8, 1.2] L_nom: the peak-current box is tightened with L_min (the current
    scales with 1/L, so L_min is the worst case) and the prediction gain is the largest gain of the set
    (L_min) so that the controller never moves phi more than the true plant needs (no overshoot on the
    vertex with the highest gain; slower on the vertex with the lowest gain).
    """
    name = "Robust-MPC"

    def __init__(self, L_lo=0.8, L_hi=1.2, **k):
        super().__init__(L_constraint=L_lo * L_NOM, L_gain=L_lo * L_NOM, name="Robust-MPC", **k)
        self.L_lo, self.L_hi = L_lo, L_hi


class AdaptiveMPC(CCSMPC):
    """
    CCS-MPC with the inductance estimated online by scalar recursive least squares on theta = 1/L:
       y_k = i2_meas (period average, A LV side), x_k = n * L_nom * I2_pwl(L_nom; phi_{k-1}, D1, D2, V1, V2)
       (the lossless current scales exactly with 1/L, so x_k theta = i2 for the true L)
       K = P x / (lambda + x^2 P); theta += K (y - x theta); P = (P - K x P) / lambda
    Excitation gating (|x| > x_min), forgetting lambda, bounds theta in [1/(1.6 L_nom), 1/(0.5 L_nom)].
    The estimate feeds the model gain and the current constraint every period.
    """
    name = "Adaptive-MPC"

    def __init__(self, lam=0.995, x_min=1.0, P0=1e-2, **k):
        super().__init__(name="Adaptive-MPC", **k)
        self.lam, self.x_min = lam, x_min
        self.theta = 1.0 / L_NOM; self.P = P0 * self.theta ** 2
        self.P0 = P0
        self.prev_cmd = (0.0, 1.0, 1.0)
        self.L_hist = []

    def reset(self, v2):
        super().reset(v2); self.theta = 1.0 / L_NOM; self.P = self.P0 * self.theta ** 2
        self.prev_cmd = (0.0, 1.0, 1.0); self.L_hist = []

    def step(self, m, ref, t):
        phi_p, D1_p, D2_p = self.prev_cmd
        x = N_RATIO * L_NOM * float(pwl_period(m["v1"], N_RATIO * m["v2"], L_NOM, FS, phi_p, D1_p, D2_p)["I2"][0])
        if abs(x) > self.x_min:
            y = m["i2"]
            Kg = self.P * x / (self.lam + x * x * self.P)
            self.theta += Kg * (y - x * self.theta)
            self.P = (self.P - Kg * x * self.P) / self.lam
            self.theta = min(1 / (0.5 * L_NOM), max(1 / (1.6 * L_NOM), self.theta))
        self.L = 1.0 / self.theta
        self.L_constraint = self.L
        self.L_hist.append(self.L)
        out = super().step(m, ref, t)
        self.prev_cmd = out
        return out

    def ops(self):
        return super().ops() + OPS_PWL + OpCount(mul=8, add=5, div=2, cmp=3, load=4)


class FCSMPC:
    """
    Finite-control-set MPC: enumerate candidates (delta_phi in PWM steps) x (modulator: SPS, EPS matching),
    predict one period ahead with the exact piecewise-linear period model (period-average i2, Irms, Ipk, ZVS),
    v2+ = v2 + H a (n I2_pwl - d_hat) (candidate held for H = 10 periods, which gives the one-step cost a usable
    sensitivity: a = Ts/C2 = 8.9 mV/A), cost = q (v2+ - ref)^2 + r dphi^2 + w_rms Irms^2 + w_zvs max(0, -zvs)
    with candidates violating Ipk > I_lim removed.  The observer uses the same model (EPS-aware).
    """
    name = "FCS-MPC"
    STEPS = (0, 1, -1, 3, -3, 10, -10, 30, -30, 100, -100)

    def __init__(self, q=1.0, r=5.0, w_rms=5e-4, w_zvs=0.05, H=10, obs_pole=0.90, modulators=("SPS", "EPS"), L=L_NOM, I_lim=I_LIM_PK):
        self.q, self.r, self.w_rms, self.w_zvs, self.H = q, r, w_rms, w_zvs, H
        self.a = TS / C2; self.L = L; self.I_lim = I_lim
        self.obs = DisturbanceObserver(self.a, obs_pole)
        self.modulators = modulators
        self.phi, self.D1, self.D2 = 0.0, 1.0, 1.0
        self.mode = "CV"; self.P_ref = 0.0
        self.last_choice = None
        self.di = 0.0; self.di_pole = obs_pole

    def set_mode(self, mode, P_ref=0.0, soft_start=False, soft_start_s=0.05):
        self.mode = mode; self.P_ref = P_ref

    def reset(self, v2):
        self.obs.reset(v2); self.phi = 0.0; self.D1 = self.D2 = 1.0; self.di = 0.0

    def step(self, m, ref, t):
        v1, v2 = m["v1"], m["v2"]
        V2p = N_RATIO * v2
        i2_applied = N_RATIO * float(pwl_period(v1, V2p, self.L, FS, self.phi, self.D1, self.D2)["I2"][0])
        d_hat = self.obs.update(v2, i2_applied)
        self.di = self.di_pole * self.di + (1 - self.di_pole) * (m["i2"] - i2_applied)
        cand_phi, cand_D1, cand_D2, cand_dphi, cand_mod = [], [], [], [], []
        De1, De2 = eps_matching(v1, v2)
        for s in self.STEPS:
            ph = max(-PHI_MAX, min(PHI_MAX, self.phi + s * PWM_STEP))
            for mod in self.modulators:
                D1, D2 = (1.0, 1.0) if mod == "SPS" else (De1, De2)
                cand_phi.append(ph); cand_D1.append(D1); cand_D2.append(D2); cand_dphi.append(ph - self.phi); cand_mod.append(mod)
        cand_phi = np.array(cand_phi); cand_dphi = np.array(cand_dphi)
        r = pwl_period(v1, V2p, self.L, FS, cand_phi, np.array(cand_D1), np.array(cand_D2))
        i2 = N_RATIO * r["I2"]
        Imin1, Imin2 = zvs_i_min(v1, v2, self.L, N_RATIO)
        zvs = np.minimum(r["zvs1"] - Imin1, r["zvs2"] - Imin2)
        if self.mode == "CV":
            v2n = v2 + self.H * self.a * (i2 - d_hat)          # candidate held for H periods (sensitivity x H)
            track = (v2n - ref) ** 2
        else:
            i2_ref = ref / max(v2, 40.0) - self.di
            track = (i2 - i2_ref) ** 2
        J = self.q * track + self.r * cand_dphi ** 2 + self.w_rms * r["Irms"] ** 2 + self.w_zvs * np.maximum(0.0, -zvs)
        J = np.where(r["Ipk"] > self.I_lim, np.inf, J)
        k = int(np.argmin(J))
        if not np.isfinite(J[k]):
            k = int(np.argmin(r["Ipk"]))
        self.phi, self.D1, self.D2 = float(cand_phi[k]), float(cand_D1[k]), float(cand_D2[k])
        self.last_choice = cand_mod[k]
        return self.phi, self.D1, self.D2

    def ops(self):
        n_c = len(self.STEPS) * len(self.modulators)
        per_cand = OPS_PWL + OpCount(mul=8, add=8, cmp=4, load=3)
        return OPS_PROTECTION + OPS_OBSERVER + OPS_PWL + per_cand.scaled(n_c) + OpCount(mul=4, add=2, div=2, sqrt=2, cmp=n_c)


class ExplicitMPC:
    """
    Explicit MPC: the CCS-MPC law pre-computed on a 3-D grid (e = ref - v2, V1, P_hat = d_hat * ref) with
    trilinear interpolation at run time.  The linearisation point of the stored law is the steady-state
    feedforward phi_ff(P_hat, V1, ref) (the rate penalty then regularises towards phi_ff); V2 is taken as the
    reference (table built for v2_ref = 400 V).  Same observer as the CCS-MPC (needs i2_sps of the command).
    """
    name = "Explicit-MPC"

    def __init__(self, lut_file, use_eps=True, obs_pole=0.90, quantised=None):
        z = np.load(lut_file)
        self.e_ax, self.v1_ax, self.p_ax = z["e_axis"], z["v1_axis"], z["p_axis"]
        self.tab = z["phi"]                                 # (ne, nv1, np) rad
        self.quantised = quantised                          # optional callable(e, v1, P) -> phi (fixed-point path)
        self.use_eps = use_eps
        self.a = TS / C2
        self.obs = DisturbanceObserver(self.a, obs_pole)
        self.phi, self.D1, self.D2 = 0.0, 1.0, 1.0
        self.mode = "CV"; self.P_ref = 0.0
        self.L = L_NOM
        self.di = 0.0; self.di_pole = obs_pole

    def set_mode(self, mode, P_ref=0.0, soft_start=False, soft_start_s=0.05):
        self.mode = mode; self.P_ref = P_ref

    def reset(self, v2):
        self.obs.reset(v2); self.phi = 0.0; self.di = 0.0

    @staticmethod
    def trilinear(tab, axes, x):
        idx = []; fr = []
        for ax, xv in zip(axes, x):
            xv = min(max(xv, ax[0]), ax[-1])
            i = int(np.searchsorted(ax, xv, side="right") - 1)
            i = min(max(i, 0), len(ax) - 2)
            idx.append(i); fr.append((xv - ax[i]) / (ax[i + 1] - ax[i]))
        (i, j, k), (fe, fv, fp) = idx, fr
        c00 = tab[i, j, k] * (1 - fp) + tab[i, j, k + 1] * fp
        c01 = tab[i, j + 1, k] * (1 - fp) + tab[i, j + 1, k + 1] * fp
        c10 = tab[i + 1, j, k] * (1 - fp) + tab[i + 1, j, k + 1] * fp
        c11 = tab[i + 1, j + 1, k] * (1 - fp) + tab[i + 1, j + 1, k + 1] * fp
        c0 = c00 * (1 - fv) + c01 * fv; c1 = c10 * (1 - fv) + c11 * fv
        return c0 * (1 - fe) + c1 * fe

    def step(self, m, ref, t):
        v1, v2 = m["v1"], m["v2"]
        i2_model_prev = i2_sps(self.phi, v1)
        d_hat = self.obs.update(v2, i2_model_prev)
        self.di = self.di_pole * self.di + (1 - self.di_pole) * (m["i2"] - i2_model_prev)
        if self.mode == "CV":
            e = ref - v2; P_hat = d_hat * ref
            if self.quantised is not None:
                self.phi = float(self.quantised(e, v1, P_hat))
            else:
                self.phi = float(self.trilinear(self.tab, (self.e_ax, self.v1_ax, self.p_ax), (e, v1, P_hat)))
        else:
            self.phi = phi_from_i2_sps(ref / max(v2, 40.0) - self.di, v1)
        self.phi = max(-PHI_MAX, min(PHI_MAX, self.phi))
        self.D1, self.D2 = eps_matching(v1, v2) if self.use_eps else (1.0, 1.0)
        return self.phi, self.D1, self.D2

    def ops(self):
        lut = OpCount(mul=3 + 14, add=3 + 14, div=0, cmp=9, load=8 + 3)   # index (mult. by 1/step), 7 lerps, clamps, 8 table reads
        return OPS_PROTECTION + OPS_OBSERVER + lut + (OPS_EPS if self.use_eps else OpCount())


# ----------------------------------------------------------------------------------------------
# scenarios and metrics
# ----------------------------------------------------------------------------------------------
R_FULL = V2_REF ** 2 / P_RATED


def make_scenario(name, soft_start_s=0.02, v1=800.0, v2_ref=V2_REF, pre=0.008, post=0.012):
    """
    Returns dict(periods, t_event, load, v1_src, mode, ref(t), v2_init, ...) for the named scenario.
    Windows: pre-roll 8 ms (controllers settle from their initial state), 12 ms after the event.  The soft start
    uses a 20 ms ramp (the firmware default is 50 ms; shortened to keep the run time < 15 min - the ramp rate is
    then 1 V/ms instead of 0.4 V/ms, which is harder, not easier, for the controllers).
    """
    R_full = v2_ref ** 2 / P_RATED
    base = dict(v1=v1, v2_ref=v2_ref, t_event=pre, v2_init=v2_ref, mode="CV", ref=lambda t: v2_ref,
                v1_src=lambda t: v1, periods=int((pre + post) * FS))
    if name == "load_step_up":          # 10 -> 100 %
        return dict(base, load=lambda v2, t: v2 / (R_full if t >= pre else 10 * R_full),
                    title=f"Load step 10 -> 100 % ({v1:.0f}/{v2_ref:.0f} V)")
    if name == "load_step_down":        # 100 -> 10 %
        return dict(base, load=lambda v2, t: v2 / (10 * R_full if t >= pre else R_full),
                    title=f"Load step 100 -> 10 % ({v1:.0f}/{v2_ref:.0f} V)")
    if name == "v1_step":               # 800 -> 700 V at full load
        return dict(base, load=lambda v2, t: v2 / R_full, v1_src=lambda t: v1 - 100.0 if t >= pre else v1,
                    title=f"HV bus step {v1:.0f} -> {v1-100:.0f} V at full load")
    if name == "reversal":              # +6.6 -> -6.6 kW, 2 kW/ms slew (firmware limit), battery on the LV port
        t_ramp = 2 * P_RATED / 2e6
        def ref(t):
            if t < pre: return P_RATED
            return max(-P_RATED, P_RATED - 2e6 * (t - pre))
        return dict(base, periods=int((pre + t_ramp + post) * FS), mode="CP", ref=ref, t_ramp=t_ramp,
                    load=lambda v2, t: (v2 - v2_ref) / 0.1,
                    title="Power reversal +6.6 -> -6.6 kW (CP, 2 kW/ms, battery 400 V / 0.1 Ohm)")
    if name == "soft_start":            # precharged link (v2_ref - 20 V) -> v2_ref ramp, 50 % load
        v0 = v2_ref - 20.0
        def ref(t):
            sc = min(1.0, max(0.0, t / soft_start_s))
            return v0 + (v2_ref - v0) * sc
        return dict(base, periods=int((soft_start_s + post) * FS), t_event=0.0, v2_init=v0, ref=ref, soft_start=True,
                    soft_start_s=soft_start_s, load=lambda v2, t: v2 / (2 * R_full),
                    title=f"Soft start {v0:.0f} -> {v2_ref:.0f} V ({soft_start_s*1e3:.0f} ms ramp, 50 % load)")
    raise KeyError(name)


N_SUB = 1000      # plant sub-steps per period = EPWM phase resolution (0.36 deg); 05_Simulation uses 200 (1.8 deg)


def run_scenario(ctl, sc, L_plant=L_NOM, L_drift=None, seed=20260101, N_sub=N_SUB, record_last=0, dc_free=True):
    """Closed-loop run; returns dict of arrays and the controller.  L_drift: callable(t) -> L (plant).
    dc_free: inner modulator with DC-bias-free transitions (applies to every controller alike)."""
    plant = MeasuredDABPlant(L_plant, N_RATIO, FS, C1, C2, sc["v1_src"](0.0), 0.3, sc["load"], N_sub=N_sub, dc_free=dc_free)
    plant.v2 = sc["v2_init"]
    adc = ADC(seed)
    if hasattr(ctl, "reset"):
        ctl.reset(sc["v2_init"])
    if hasattr(ctl, "ctl"):
        ctl.ctl.v2_ref = sc["v2_ref"]
    ctl.set_mode(sc["mode"], P_ref=sc["ref"](0.0), soft_start=sc.get("soft_start", False), soft_start_s=sc.get("soft_start_s", 0.05))
    n = sc["periods"]
    t_l = np.zeros(n); v2_l = np.zeros(n); v1_l = np.zeros(n); phi_l = np.zeros(n); ipk_l = np.zeros(n)
    irms_l = np.zeros(n); i2_l = np.zeros(n); ref_l = np.zeros(n); D_l = np.zeros((n, 2)); ct_l = np.zeros(n)
    p_l = np.zeros(n)
    rec = []
    for k in range(n):
        t = plant.t
        plant.V1_src = sc["v1_src"](t)
        if L_drift is not None:
            plant.L = L_drift(t)
        m = adc.measure(plant)
        ref = sc["ref"](t)
        t0 = time.perf_counter()
        phi, D1, D2 = ctl.step(m, ref, t)
        ct_l[k] = time.perf_counter() - t0
        r = plant.run_period(phi, D1, D2, record=(k >= n - record_last))
        if r:
            rec += r
        t_l[k] = plant.t; v2_l[k] = plant.v2; v1_l[k] = plant.v1; phi_l[k] = phi; ipk_l[k] = plant.ipk
        irms_l[k] = plant.iL_rms; i2_l[k] = plant.i2_avg; ref_l[k] = ref; D_l[k] = (D1, D2)
        p_l[k] = plant.i2_avg * plant.v2
    return dict(t=t_l, v2=v2_l, v1=v1_l, phi=phi_l, ipk=ipk_l, irms=irms_l, i2=i2_l, ref=ref_l, D=D_l, P=p_l,
                ct=ct_l, rec=np.array(rec) if rec else None, ctl=ctl)


def metrics(res, sc, band_v=1.0, band_p_frac=0.02, I_lim=I_LIM_PK):
    """Settling (+/-1 V = 0.25 % band, from the end of the event/ramp), overshoot, ITAE (V ms^2 or W ms^2: time in ms,
    dt in ms), peak/rms current, violations of the 24 A controller limit and the 32 A hardware trip, compute time."""
    t = res["t"]; te = sc["t_event"]
    if sc["mode"] == "CV":
        e = res["v2"] - res["ref"]; band = band_v
        # for soft start: evaluate after the ramp
        t_from = te + sc.get("soft_start_s", 0.0)
    else:
        e = res["P"] - res["ref"]; band = band_p_frac * P_RATED
        t_from = te + sc.get("t_ramp", 0.0)
    w = t >= te
    ew = e[w]; tw = t[w] - te
    itae = float(np.sum(tw * 1e3 * np.abs(ew)) * TS * 1e3)
    after = t >= t_from
    ea = e[after]; ta = t[after]
    out_of_band = np.abs(ea) > band
    if out_of_band.any():
        last = np.max(np.nonzero(out_of_band)[0])
        t_settle = float(ta[last] - t_from) if last < len(ea) - 1 else float("nan")   # nan = not settled in window
    else:
        t_settle = 0.0
    # overshoot: for CV steps the response first deviates one way; overshoot = max excursion on the other side (recovery)
    vref = sc.get("v2_ref", V2_REF)
    if sc["mode"] == "CV" and sc.get("t_event", 0) > 0:
        first = ew[np.argmax(np.abs(ew) > 0.5)] if (np.abs(ew) > 0.5).any() else 0.0
        sgn = -math.copysign(1.0, first) if first != 0 else 1.0
        overshoot = float(max(0.0, np.max(sgn * ew)) / vref * 100)
        peak_dev = float(np.max(np.abs(ew)) / vref * 100)
    else:
        overshoot = float(np.max(np.abs(ea)) / (vref if sc["mode"] == "CV" else P_RATED) * 100) if len(ea) else float("nan")
        peak_dev = float(np.max(np.abs(ew)) / (vref if sc["mode"] == "CV" else P_RATED) * 100)
    ipk = res["ipk"][w]
    return dict(settling_ms=t_settle * 1e3 if not math.isnan(t_settle) else float("nan"),
                overshoot_pct=overshoot, peak_dev_pct=peak_dev, ITAE=itae,
                i_peak_A=float(ipk.max()), i_rms_A=float(np.sqrt(np.mean(res["irms"][w] ** 2))),
                violations=int(np.sum(ipk > I_lim)), violations_hw=int(np.sum(ipk > I_TRIP_HW)),
                compute_us_mean=float(np.mean(res["ct"]) * 1e6), compute_us_max=float(np.max(res["ct"]) * 1e6),
                v2_min=float(res["v2"][w].min()), v2_max=float(res["v2"][w].max()))
