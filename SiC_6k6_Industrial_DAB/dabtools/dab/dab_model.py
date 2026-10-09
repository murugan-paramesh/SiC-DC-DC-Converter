"""
Analytical / semi-numerical model of the single-phase dual active bridge (DAB).

Conventions
-----------
* Port 1 = high-voltage port (V1), port 2 = low-voltage port (V2).
* n = N1/N2 is the transformer turns ratio; V2p = n*V2 is the port-2 voltage referred to port 1.
* L is the total series (leakage + external) inductance referred to port 1.
* Bridge 1 produces v1(t), bridge 2 produces v2p(t) (referred).  Both are three-level
  square waves of amplitude V1 / V2p with inner phase shifts D1, D2 (fraction of the half
  period during which the bridge voltage is non-zero, 1 = full square wave) and the outer
  phase shift phi (rad) between the two fundamental components (phi > 0: power 1 -> 2).
* All waveform quantities are computed numerically on a uniform grid; closed-form SPS
  expressions are provided for cross-checking (Kheraluwala 1992, Krismer 2010/2012).

Reference formulas (SPS, D1 = D2 = 1):
    P      = V1 * V2p * phi * (pi - |phi|) / (2 * pi^2 * fs * L)
    I0     = (V1*pi + V2p*(2*phi - pi)) / (2*w*L)     current magnitude at bridge-1 switching
    I1     = (V1*(2*phi - pi) + V2p*pi) / (2*w*L)     current magnitude at bridge-2 switching
    ZVS(1) <=> I0 > I_min(V1),  ZVS(2) <=> I1 > I_min(V2p)
"""
import math
import numpy as np


def three_level(theta, amplitude, duty, shift):
    """
    Three-level bridge voltage as a function of angle theta (rad, 0..2pi).
    duty: fraction of each half period at +/- amplitude (1 = square wave), centred on the
    fundamental; shift: phase of the fundamental.
    """
    th = (theta - shift) % (2 * math.pi)
    half = duty * math.pi / 2
    v = np.zeros_like(th)
    pos = (th > (math.pi / 2 - half)) & (th <= (math.pi / 2 + half))
    neg = (th > (3 * math.pi / 2 - half)) & (th <= (3 * math.pi / 2 + half))
    v[pos] = amplitude
    v[neg] = -amplitude
    return v


def waveforms(V1, V2p, L, fs, phi, D1=1.0, D2=1.0, N=4000):
    """Return theta, v1, v2p, i(t) (referred to port 1) for one switching period."""
    theta = np.linspace(0, 2 * math.pi, N, endpoint=False)
    w = 2 * math.pi * fs
    v1 = three_level(theta, V1, D1, 0.0)
    v2 = three_level(theta, V2p, D2, phi)
    di = (v1 - v2) / (w * L)                      # di/dtheta
    i = np.cumsum(di) * (2 * math.pi / N)
    i -= i.mean()                                 # steady state: no DC component
    return theta, v1, v2, i


class DABPoint:
    """All steady-state quantities at one operating point (numerical)."""

    def __init__(self, V1, V2, n, L, fs, phi, D1=1.0, D2=1.0, N=4000):
        self.V1, self.V2, self.n, self.L, self.fs, self.phi, self.D1, self.D2 = V1, V2, n, L, fs, phi, D1, D2
        self.V2p = n * V2
        self.theta, self.v1, self.v2, self.i = waveforms(V1, self.V2p, L, fs, phi, D1, D2, N)
        self.N = N

    # ---- power -----------------------------------------------------------
    @property
    def P(self):
        """Average power delivered from port 1 to port 2 (W); negative = reverse flow."""
        return float(np.mean(self.v1 * self.i))

    @property
    def P2(self):
        return float(np.mean(self.v2 * self.i))

    @property
    def backflow(self):
        """Fraction of the period during which instantaneous port-1 power is negative (circulating)."""
        p = self.v1 * self.i
        return float(np.mean(p < 0))

    @property
    def Q_backflow(self):
        """Average reverse (circulating) power at port 1 (W)."""
        p = self.v1 * self.i
        return float(-np.mean(np.minimum(p, 0)))

    # ---- currents ---------------------------------------------------------
    @property
    def I_rms1(self):
        return float(np.sqrt(np.mean(self.i ** 2)))

    @property
    def I_rms2(self):
        return self.I_rms1 * self.n

    @property
    def I_peak1(self):
        return float(np.max(np.abs(self.i)))

    @property
    def I_peak2(self):
        return self.I_peak1 * self.n

    def device_rms(self, port):
        """RMS current of one MOSFET (each conducts for half the period; channel + body diode)."""
        return (self.I_rms1 if port == 1 else self.I_rms2) / math.sqrt(2)

    # ---- switching instants / ZVS ------------------------------------------
    def switching_currents(self):
        """
        Current (referred to port 1) at every bridge-voltage edge, with the sign convention
        'positive = favourable for ZVS' (current flowing out of the leg that is being switched
        in the direction that discharges the turning-on device).
        Returns dict port -> list of (theta, i_zvs).
        """
        out = {1: [], 2: []}
        for port, v in ((1, self.v1), (2, self.v2)):
            dv = np.diff(np.concatenate([v, v[:1]]))
            idx = np.nonzero(dv)[0]
            for k in idx:
                edge = dv[k]
                # current after the edge (bridge voltage rises => the inductor current should be negative
                # (flowing into the bridge through the body diodes of the turning-on devices))
                i_edge = self.i[(k + 1) % self.N]
                sign = -1.0 if edge > 0 else 1.0
                if port == 2:
                    sign = -sign          # port 2 delivers/absorbs with opposite orientation
                out[port].append((float(self.theta[k]), float(sign * i_edge)))
        return out

    def zvs_margin(self, port, I_min):
        """Minimum (i_switch - I_min) over all edges of a bridge; > 0 means ZVS for every edge."""
        sc = self.switching_currents()[port]
        if not sc:
            return float("nan")
        return min(i for _, i in sc) - I_min


# ---------------------------------------------------------------------------
# closed form SPS helpers
# ---------------------------------------------------------------------------
def sps_power(V1, V2p, L, fs, phi):
    return V1 * V2p * phi * (math.pi - abs(phi)) / (2 * math.pi ** 2 * fs * L)


def sps_phi_for_power(V1, V2p, L, fs, P):
    """Smaller phase shift (|phi| <= pi/2) that transfers P; raises if P exceeds the maximum."""
    Pmax = V1 * V2p / (8 * fs * L)
    if abs(P) > Pmax:
        raise ValueError(f"P = {P:.0f} W exceeds Pmax = {Pmax:.0f} W")
    # phi*(pi - phi) = 2 pi^2 fs L P /(V1 V2p)  ->  phi^2 - pi phi + c = 0
    c = 2 * math.pi ** 2 * fs * L * abs(P) / (V1 * V2p)
    phi = (math.pi - math.sqrt(math.pi ** 2 - 4 * c)) / 2
    return math.copysign(phi, P)


def sps_switching_currents(V1, V2p, L, fs, phi):
    w = 2 * math.pi * fs
    I0 = (V1 * math.pi + V2p * (2 * phi - math.pi)) / (2 * w * L)
    I1 = (V1 * (2 * phi - math.pi) + V2p * math.pi) / (2 * w * L)
    return I0, I1


def zvs_current_min(Coss_er, Vdc, L, C_par=0.0):
    """
    Minimum inductor current for a complete ZVS transition of one leg:
    0.5 * L * I^2 >= Coss_er_leg * Vdc^2 (+ parasitic winding capacitance energy).
    Coss_er is the energy-related output capacitance of ONE device (F).
    """
    E = Coss_er * Vdc ** 2 + 0.5 * C_par * Vdc ** 2
    return math.sqrt(2 * E / L)


def dead_time_required(Qoss, I_sw, t_min=50e-9):
    """Charge-based dead time: two devices' Qoss must be moved by the inductor current."""
    if I_sw <= 0:
        return float("inf")
    return max(t_min, 2 * Qoss / I_sw)


def sps_max_power(V1, V2p, L, fs):
    return V1 * V2p / (8 * fs * L)


def tps_search(V1, V2, n, L, fs, P_target, Coss_er1, Coss_er2, grid=13, N=2000):
    """
    Brute-force search of (D1, D2, phi) minimising the RMS inductor current for a given power,
    subject to ZVS at every edge of both bridges (energy criterion).  Returns the best point
    and the SPS reference point.  This is an engineering optimiser, not a closed-form result
    (cf. Krismer & Kolar 2012 for the analytical minimum-conduction-loss modulation).
    """
    V2p = n * V2
    Imin1 = zvs_current_min(Coss_er1, V1, L)
    Imin2 = zvs_current_min(Coss_er2, V2, L / n ** 2) / n     # referred to port 1
    best = None
    sps_phi = sps_phi_for_power(V1, V2p, L, fs, P_target)
    sps = DABPoint(V1, V2, n, L, fs, sps_phi, N=N)
    for D1 in np.linspace(0.4, 1.0, grid):
        for D2 in np.linspace(0.4, 1.0, grid):
            # find phi for the target power by bisection on the numerical power
            lo, hi = 0.0, math.pi / 2
            ok = False
            for _ in range(30):
                mid = (lo + hi) / 2
                pt = DABPoint(V1, V2, n, L, fs, math.copysign(mid, P_target), D1, D2, N=N)
                if abs(pt.P) < abs(P_target):
                    lo = mid
                else:
                    hi = mid
                if abs(abs(pt.P) - abs(P_target)) < 0.002 * abs(P_target):
                    ok = True
                    break
            if not ok:
                continue
            m1, m2 = pt.zvs_margin(1, Imin1), pt.zvs_margin(2, Imin2)
            if m1 < 0 or m2 < 0:
                continue
            if best is None or pt.I_rms1 < best.I_rms1:
                best = pt
    return best, sps
