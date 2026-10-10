"""
Hierarchical digital twin of the 6.6 kW SiC dual active bridge (research module, simulation only).

Layers
  L1 electrical  : period-averaged DAB model  I2 = g(phi, D1, D2, V1, V2) * theta,  theta = 1/L
                   (exact for the lossless switched model: every current scales with 1/L)
  L2 thermal     : 2-node Foster network per bridge (junction, case/heatsink), Kalman observer of Tj
                   from the case NTC and the loss estimate
  L3 health      : slowly varying Rds_on multiplier tracked from the conduction-loss residual (weakly
                   observable - see observability.py); detailed study in ../SiC_Health_Monitoring
  L4 supervisory : operating-point selection on the estimated parameters inside the validated
                   envelope with a deterministic fallback (supervisory.py)

Estimators: recursive least squares with forgetting (RLS), extended Kalman filter (EKF) with joint
state [v2, i_load, theta], grid Bayesian posterior over L (reference), and a Coss_er estimator that
needs a drain-voltage transition-time sensor (not present in the current hardware -> proposal).

All data in this module come from the project's switched simulation (dabtools.dab.sim_switched),
never from hardware. Sensor noise is modelled from the sensing chain of the schematic (12-bit ADC,
AMC1301 gain error, shunt / CT tolerance) - values stated in SENSOR.
"""
import math, os, sys
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "SiC_6k6_Industrial_DAB"))
sys.path.insert(0, ROOT)
from dabtools.dab.dab_model import DABPoint, zvs_current_min        # noqa: E402
from dabtools.dab.sim_switched import DABPlant                      # noqa: E402
from dabtools.dab.devices import DEVICES                            # noqa: E402

# ---------------------------------------------------------------------------------------------
# sensing chain (from 07_KiCad_Schematics: AMC1301 isolated amplifiers, 1 mOhm shunt, CT, 12-bit ADC)
# ---------------------------------------------------------------------------------------------
SENSOR = dict(
    adc_bits=12,
    v1_fs=1000.0,   v1_gain_err=0.003,   # AMC1301 +/-0.3 % gain error (datasheet typ. class), resistor divider 0.1 %
    v2_fs=500.0,    v2_gain_err=0.003,
    i2_fs=40.0,     i2_gain_err=0.005,   # 1 mOhm shunt + AMC1301, 0.5 % incl. shunt tolerance
    i1_fs=20.0,     i1_gain_err=0.01,    # CT + burden, 1 %
    i_edge_fs=20.0, i_edge_noise=0.3,    # hypothetical edge-current / transition-time sensor (proposal)
    t_tr_noise=5e-9,                     # 5 ns rms on a transition-time measurement (proposal)
    T_noise=1.0,                         # NTC after linearisation, K rms
)


class Sensors:
    """Quantisation + gain error + white noise; one object per simulated converter (fixed gain errors)."""

    def __init__(self, rng, S=SENSOR):
        self.S = S; self.rng = rng
        self.g = {k: 1.0 + rng.normal(0, S[k + "_gain_err"]) for k in ("v1", "v2", "i2", "i1")}
        self.q = {k: S[k + "_fs"] / 2 ** (S["adc_bits"] - 1) for k in ("v1", "v2", "i2", "i1")}

    def meas(self, key, value):
        q = self.q[key]
        v = self.g[key] * value + self.rng.normal(0, 0.5 * q)      # 0.5 LSB rms noise (realistic for a clean layout)
        return q * round(v / q)


# ---------------------------------------------------------------------------------------------
# L1 electrical model: regressor g such that I2_avg = g * (1/L)
# ---------------------------------------------------------------------------------------------
_gcache = {}


def regressor_I2(phi, D1, D2, V1, V2, n, fs, N=1500):
    """Period-average LV-port current for L = 1 H (then I2 = g / L). Cached on a coarse key."""
    key = (round(phi, 4), round(D1, 3), round(D2, 3), round(V1, 0), round(V2, 0))
    if key not in _gcache:
        pt = DABPoint(V1, V2, n, 1.0, fs, phi, D1, D2, N=N)
        _gcache[key] = pt.P2 / max(V2, 1.0) if V2 > 1 else 0.0       # I2 = P2 / V2 (lossless)
    return _gcache[key]


def discrete_model_lossy(s1, s2, V1, V2, n, fs, L, R_s):
    """
    Edge current of the lossy model (series R_s, assumed design value) at the sensed edge, periodic
    steady state computed exactly: i_{k+1} = a i_k + b_k, a = 1 - R_s dt / L  ->  i_0 = c / (1 - a^N)
    with c the one-period response from zero.
    """
    N = len(s1); dt = 1.0 / fs / N; a = 1.0 - R_s * dt / L
    b = (s1 * V1 - s2 * n * V2) * dt / L
    c = 0.0
    for k in range(N): c = a * c + b[k]
    i = c / (1.0 - a ** N); iL = np.zeros(N)
    for k in range(N):
        i = a * i + b[k]; iL[k] = i
    return float(abs(iL[first_rising_edge(np.sign(s1))]))


def discrete_model(s1, s2, V1, V2, n, fs, L=1.0):
    """
    Period-average LV current and minimum |i| at the HV-bridge edges computed on the modulator's own
    switching pattern (s1, s2 = +/-1/0 arrays over one period, as the PWM registers define them).
    Using the applied pattern instead of the ideal phase removes the time-quantisation error of the
    modulator from the regressor (the controller knows its own registers).  Lossless: i scales 1/L.
    """
    N = len(s1); dt = 1.0 / fs / N
    di = (s1 * V1 - s2 * n * V2) / L * dt
    i = np.cumsum(di); i -= i.mean()
    i2_avg = float(np.mean(i * s2 * n))
    i_edge = float(abs(i[first_rising_edge(np.sign(s1))]))      # same edge definition as period_measurements
    return i2_avg, i_edge


def edge_current_bridge1(phi, D1, D2, V1, V2, n, L, fs):
    """Minimum switching-edge current of bridge 1 (HV), referred to port 1 (model, A)."""
    pt = DABPoint(V1, V2, n, L, fs, phi, D1, D2, N=1500)
    sc = pt.switching_currents()[1]
    return min(i for _, i in sc) if sc else float("nan")


# ---------------------------------------------------------------------------------------------
# estimators
# ---------------------------------------------------------------------------------------------
class RLS:
    """Scalar recursive least squares with forgetting factor and excitation gating."""

    def __init__(self, theta0, P0, lam=0.995, g_min=2.5e-4):
        # g_min: regressor threshold in A*H; the full-load regressor of this design is ~1.1e-3 A*H
        # (I2 = 16.5 A at L = 64 uH), so 2.5e-4 gates updates below ~25 % load
        self.theta, self.P, self.lam, self.g_min = theta0, P0, lam, g_min
        self.n_upd = 0

    def update(self, g, y):
        if abs(g) < self.g_min:                 # light load: regressor too small -> hold (conditioning)
            return self.theta
        k = self.P * g / (self.lam + g * self.P * g)
        self.theta += k * (y - g * self.theta)
        self.P = (self.P - k * g * self.P) / self.lam
        self.n_upd += 1
        return self.theta

    @property
    def sigma(self):
        return math.sqrt(max(self.P, 0.0))


class EKF_L:
    """
    Joint EKF: x = [v2, i_load, theta=1/L]; inputs (phi, D1, D2, v1); measurements z = [v2_meas, I2_meas].
    v2_{k+1} = v2_k + Ts/C2 * (g_k theta_k - i_load_k);  i_load, theta random walks.
    """

    def __init__(self, x0, P0, Q, R, C2, Ts):
        self.x = np.array(x0, float); self.P = np.diag(P0).astype(float)
        self.Q = np.diag(Q); self.R = np.diag(R); self.C2, self.Ts = C2, Ts

    def step(self, g, z):
        v2, il, th = self.x
        F = np.array([[1.0, -self.Ts / self.C2, self.Ts / self.C2 * g], [0, 1, 0], [0, 0, 1]])
        x_pred = np.array([v2 + self.Ts / self.C2 * (g * th - il), il, th])
        P_pred = F @ self.P @ F.T + self.Q
        H = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, g]])
        zh = np.array([x_pred[0], g * x_pred[2]])
        S = H @ P_pred @ H.T + self.R
        K = P_pred @ H.T @ np.linalg.inv(S)
        self.x = x_pred + K @ (np.asarray(z) - zh)
        self.P = (np.eye(3) - K @ H) @ P_pred
        return self.x.copy()


class BayesGridL:
    """Sequential Bayesian posterior over L on a grid (reference solution for the RLS/EKF)."""

    def __init__(self, L_grid, sigma_y):
        self.L = np.asarray(L_grid); self.logp = np.zeros_like(self.L); self.s = sigma_y

    def update(self, g, y):
        self.logp += -0.5 * ((y - g / self.L) / self.s) ** 2
        self.logp -= self.logp.max()

    def summary(self):
        p = np.exp(self.logp); p /= p.sum()
        m = float((p * self.L).sum()); sd = float(np.sqrt((p * (self.L - m) ** 2).sum()))
        c = np.cumsum(p)
        return m, sd, float(self.L[np.searchsorted(c, 0.025)]), float(self.L[np.searchsorted(c, 0.975)])


class CossEstimator:
    """
    Coss_er from a drain-voltage transition-time sensor: t_tr = 2 Coss_er V / |I_edge|  (charge-based,
    Q_oss ~= 2 Coss_er V).  I_edge comes from the L1 model with the ESTIMATED L. RLS on theta_c = Coss_er,
    computed in normalised units (pF, ns) so that the RLS covariance is well scaled.
    """

    def __init__(self, C0, P0, lam=0.99):
        self.rls = RLS(C0 * 1e12, P0 * 1e24, lam, g_min=1e-3)

    def update(self, t_tr_meas, V, I_edge):
        if abs(I_edge) < 0.5: return self.theta
        g = 2.0 * V / abs(I_edge) * 1e-3           # ns per pF
        self.rls.update(g, t_tr_meas * 1e9)
        return self.theta

    @property
    def theta(self):
        return self.rls.theta * 1e-12


# ---------------------------------------------------------------------------------------------
# L2 thermal twin: Foster 2-node per bridge + Kalman observer of Tj from the case NTC
# ---------------------------------------------------------------------------------------------
class ThermalTwin:
    """
    Tj -(RthJC, CthJ)- Tc -(RthCA, CthC)- Tamb.  P_loss from the loss model; the case NTC is measured.
    Parameters: RthJC from the device data (datasheet class, unverified), RthCA and capacitances are
    estimates for the TO-247 pair on the shared heat-sink bar (labelled ESTIMATE).
    """

    def __init__(self, dev, RthCA=0.35, CthJ=0.05, CthC=60.0, Ts=1e-3, Tamb=45.0):
        self.RthJC = DEVICES[dev]["RthJC"]; self.RthCA, self.CthJ, self.CthC = RthCA, CthJ, CthC
        self.Ts, self.Tamb = Ts, Tamb
        self.x = np.array([Tamb, Tamb]); self.P = np.diag([25.0, 25.0])
        self.Q = np.diag([0.5, 0.05]); self.R = np.array([[SENSOR["T_noise"] ** 2]])

    def A_B(self):
        a11 = 1 - self.Ts / (self.RthJC * self.CthJ); a12 = self.Ts / (self.RthJC * self.CthJ)
        a21 = self.Ts / (self.RthJC * self.CthC); a22 = 1 - self.Ts / (self.RthJC * self.CthC) - self.Ts / (self.RthCA * self.CthC)
        A = np.array([[a11, a12], [a21, a22]]); B = np.array([self.Ts / self.CthJ, 0.0]); c = np.array([0.0, self.Ts / (self.RthCA * self.CthC) * self.Tamb])
        return A, B, c

    def predict_true(self, x, P_loss):
        A, B, c = self.A_B(); return A @ x + B * P_loss + c

    def step(self, P_loss_est, Tc_meas):
        A, B, c = self.A_B()
        xp = A @ self.x + B * P_loss_est + c; Pp = A @ self.P @ A.T + self.Q
        H = np.array([[0.0, 1.0]]); S = H @ Pp @ H.T + self.R; K = Pp @ H.T @ np.linalg.inv(S)
        self.x = xp + (K * (Tc_meas - xp[1])).ravel(); self.P = (np.eye(2) - K @ H) @ Pp
        return self.x.copy()


# ---------------------------------------------------------------------------------------------
# simulated converter with hidden parameter changes (SIMULATED data generator)
# ---------------------------------------------------------------------------------------------
def make_plant(L, n, fs, C1, C2, V1, load, R_s=0.3, N_sub=200):
    return DABPlant(L, n, fs, C1, C2, V1, 0.3, load, N_sub=N_sub, R_s=R_s)


def period_measurements(plant, rec, s1_edges=True):
    """Period-average currents and HV-bridge edge current from one recorded period."""
    r = np.asarray(rec)
    i2_avg = float(np.mean(r[:, 7]))             # LV link current delivered by the bridge (A)
    i1_avg = float(np.mean(r[:, 6]))
    va = r[:, 1]; iL = r[:, 3]
    i_edge = float(abs(iL[first_rising_edge(np.sign(va))]))     # HV leg-A outer edge (the sensed edge)
    return i2_avg, i1_avg, i_edge


def first_rising_edge(s):
    """Index of the sample just after the first transition of s from <= 0 to > 0 (cyclic)."""
    sp = np.concatenate([s[-1:], s])
    k = np.nonzero((sp[:-1] <= 0) & (sp[1:] > 0))[0]
    return int(k[0]) if len(k) else 0
