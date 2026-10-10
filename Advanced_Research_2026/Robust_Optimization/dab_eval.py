#!/usr/bin/env python3
"""
Shared design evaluator for Robust_Optimization/ and Uncertainty_Quantification/.

It re-implements the chain of SiC_6k6_Industrial_DAB/12_Optimization/optimize.py::evaluate()
(SPS operating point -> bridge losses with electro-thermal iteration -> transformer and inductor
design -> total loss / volume / ZVS) on top of the project models (dabtools.dab.*), with three
changes needed for optimisation under uncertainty:

1. The SPS waveform quantities are evaluated in closed form (Kheraluwala 1992; the same formulas
   `dab_model.sps_switching_currents` cross-checks) instead of on a 1200-point grid.  For the
   piecewise-linear SPS inductor current the rms value is exact:
       i(0) = -I0, i(phi) = I1, i(pi) = +I0  (slopes (V1+V2')/(wL) and (V1-V2')/(wL))
       I_rms^2 = [ phi (I0^2 - I0 I1 + I1^2) + (pi - phi) (I1^2 + I1 I0 + I0^2) ] / (3 pi)
   `self_test()` verifies this against `DABPoint` (N = 4000) to < 0.5 %.
2. Every operating point takes an uncertainty vector u = (kL, kCoss, kRds, kCore, Tamb):
   realised series inductance L*kL, energy-related output capacitance Coss_er*kCoss, channel
   resistance Rds_on*kRds (aging), ferrite loss *kCore, ambient Tamb.  The magnetics are DESIGNED
   with nominal values (that is what a designer does) and OPERATED with the realised ones.
3. A 24 h bidirectional mission profile (ASSUMED, see MISSION) gives the daily loss energy and the
   junction-temperature sequence of both bridges; a rainflow count and a Coffin-Manson/Arrhenius
   (LESIT-type) law give a lifetime-consumption proxy.  The law's coefficients are literature-typical
   values for Si IGBT modules (Held et al. 1997); they are NOT measured for discrete SiC TO-247
   devices, so only the ratio between designs is meaningful.  The proxy is reported relative to the
   baseline design (log10 of the damage ratio).

Nothing here is measured; maturity L2 (analytical/simulation models only).
"""
import os, sys, math
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DAB_ROOT = os.path.join(REPO, "SiC_6k6_Industrial_DAB")
if DAB_ROOT not in sys.path:
    sys.path.insert(0, DAB_ROOT)
from dabtools.dab import dab_model as M                      # noqa: E402
from dabtools.dab import losses as LS                        # noqa: E402
from dabtools.dab import magnetics as MG                     # noqa: E402
from dabtools.dab.devices import DEVICES, rds_on             # noqa: E402

# ----------------------------------------------------------------------------- fixed project data
P_RATED = 6600.0
V1_NOM, V2_NOM = 800.0, 400.0
CORNERS_FULL = [(650.0, 300.0), (650.0, 450.0), (850.0, 300.0), (850.0, 450.0)]   # envelope corners
ALL9 = [(a, b) for a in (650.0, 800.0, 850.0) for b in (300.0, 400.0, 450.0)]
HEATSINK = dict(Rth_sink=0.22, Rth_tim=0.35)        # K/W, forced air 3 m/s, silicone pad (13_Thermal_Analysis)
C_PAR = 60e-12                                      # winding capacitance seen by each bridge (04 design_values)
TJ_LIMIT = 125.0                                    # design limit used in 13_Thermal_Analysis (device rating 175 C)
IPK_LIMIT = 24.0                                    # A HV side, design_values I_limit_pk
PHI_MAX = math.pi / 3                               # full power must be reachable with phi <= 60 deg
P_AUX = 12.0                                        # W bias / control / fans
K_PCB = 0.004                                       # PCB copper + bus-bar loss estimate (fraction of P)
BPK_MAX, FILL_MAX = 0.20, 0.70

CORE_T = ["E55/28/21", "ETD59/31/22", "E65/32/27", "E70/33/32"]
CORE_L = ["ETD44/22/15", "ETD49/25/16", "E55/28/21"]
DEV1 = [("C3M0032120K", 1), ("C3M0016120K", 1)]
DEV2 = [("C3M0016120K", 1), ("C3M0032120K", 2)]

# uncertain parameters: name -> (lower, upper) of the assumed UNIFORM distribution
U_NAMES = ["kL", "kCoss", "kRds", "kCore", "Tamb"]
U_BOUNDS = np.array([[0.85, 1.15], [0.80, 1.20], [1.00, 1.30], [0.75, 1.25], [25.0, 55.0]])
U_NOM = np.array([1.0, 1.0, 1.0, 1.0, 45.0])
U_DESC = {"kL": "series inductance tolerance +/-15 %", "kCoss": "Coss_er tolerance +/-20 %",
          "kRds": "Rds_on aging +0..30 %", "kCore": "ferrite core-loss tolerance +/-25 %", "Tamb": "ambient 25..55 C"}

# ----------------------------------------------------------------------------- design variables
# continuous bounds (decoded from x in [0, 1]); cores / devices are discrete indices
X_NAMES = ["fs", "phi_nom_deg", "n", "Bpk", "tcore", "lcore", "t_dead", "dev1", "dev2"]
X_BOUNDS = {"fs": (60e3, 200e3), "phi_nom_deg": (12.0, 50.0), "n": (1.6, 2.4), "Bpk": (0.08, 0.20),
            "t_dead": (80e-9, 250e-9)}
N_X = 9


def decode(x):
    """x in [0,1]^9 -> design dict (phi_nom -> L through the SPS power equation at 800/400 V, 6.6 kW)."""
    x = np.clip(np.asarray(x, float), 0.0, 1.0 - 1e-12)
    d = {}
    for i, k in enumerate(["fs", "phi_nom_deg", "n", "Bpk"]):
        lo, hi = X_BOUNDS[k]; d[k] = lo + (hi - lo) * x[i]
    d["tcore"] = CORE_T[int(x[4] * len(CORE_T))]
    d["lcore"] = CORE_L[int(x[5] * len(CORE_L))]
    lo, hi = X_BOUNDS["t_dead"]; d["t_dead"] = lo + (hi - lo) * x[6]
    d["dev1"] = DEV1[int(x[7] * len(DEV1))]
    d["dev2"] = DEV2[int(x[8] * len(DEV2))]
    phi = math.radians(d["phi_nom_deg"])
    d["L"] = V1_NOM * d["n"] * V2_NOM * phi * (math.pi - phi) / (2 * math.pi ** 2 * d["fs"] * P_RATED)
    return d


def design_from_values(fs, L, n, Bpk, tcore, lcore, t_dead, dev1, dev2):
    phi = _phi_from_L(fs, L, n)
    return dict(fs=fs, phi_nom_deg=math.degrees(phi), n=n, Bpk=Bpk, tcore=tcore, lcore=lcore, t_dead=t_dead,
                dev1=dev1, dev2=dev2, L=L)


def _phi_from_L(fs, L, n):
    c = 2 * math.pi ** 2 * fs * L * P_RATED / (V1_NOM * n * V2_NOM)
    return (math.pi - math.sqrt(max(math.pi ** 2 - 4 * c, 0.0))) / 2


BASELINE = design_from_values(100e3, 64e-6, 2.0, 0.13, "E65/32/27", "E55/28/21", 150e-9, ("C3M0032120K", 1), ("C3M0016120K", 1))

# ----------------------------------------------------------------------------- mission profile (ASSUMED)
# 24 hourly segments: (P in W, V1 in V, V2 in V).  P > 0 charges the battery from the 800 V bus,
# P < 0 is vehicle-to-grid discharge.  The battery voltage follows the state of charge.  This is a
# plausible EV-charger / battery-interface day, NOT a measured or standardised profile.
MISSION = [
    (6600, 800, 330), (6600, 800, 360), (6600, 800, 390), (6600, 800, 410), (3300, 800, 430), (1000, 800, 445),
    (0, 800, 445), (-3300, 780, 440), (-5000, 780, 420), (660, 800, 410), (0, 800, 410), (3300, 820, 400),
    (3300, 820, 410), (3300, 820, 420), (3300, 820, 430), (0, 800, 435), (0, 800, 435), (-5000, 780, 430),
    (-6600, 760, 400), (-6600, 760, 370), (-3300, 780, 350), (0, 800, 340), (0, 800, 340), (0, 800, 340)]
MISSION_DT_H = 1.0

# LESIT Coffin-Manson/Arrhenius coefficients (Held et al. 1997, Si IGBT modules): Nf = A dT^a exp(Q/(R Tm))
LESIT = dict(A=3.025e5, alpha=-5.039, Q_over_R=9.891e4 / 8.314)
DTJ_MIN = 1.0      # K, cycles below this are ignored


# ----------------------------------------------------------------------------- closed-form SPS point
def sps_point(V1, V2, n, L, fs, P):
    """Closed-form SPS quantities for |P| (reverse power is symmetric for SPS); None if unreachable."""
    V2p = n * V2
    Pa = abs(P)
    Pmax = V1 * V2p / (8 * fs * L)
    if Pa > 0.999 * Pmax:
        return None
    c = 2 * math.pi ** 2 * fs * L * Pa / (V1 * V2p)
    phi = (math.pi - math.sqrt(math.pi ** 2 - 4 * c)) / 2
    w = 2 * math.pi * fs
    I0 = (V1 * math.pi + V2p * (2 * phi - math.pi)) / (2 * w * L)    # current at bridge-1 edges (>0: ZVS favourable)
    I1 = (V1 * (2 * phi - math.pi) + V2p * math.pi) / (2 * w * L)    # current at bridge-2 edges (referred to port 1)
    Irms = math.sqrt((phi * (I0 * I0 - I0 * I1 + I1 * I1) + (math.pi - phi) * (I0 * I0 + I0 * I1 + I1 * I1)) / (3 * math.pi))
    return dict(phi=phi, I0=I0, I1=I1, Irms1=Irms, Ipk1=max(abs(I0), abs(I1)), Pmax=Pmax)


def bridge_losses_u(dev, Vdc, I_rms_dev, I_sw_edges, fs, Tj, t_dead, I_min_zvs, n_parallel=1, kRds=1.0, kCoss=1.0, k_zvs=0.35):
    """dabtools.dab.losses.bridge_losses with Rds_on and Coss scaled by (kRds, kCoss); identical at k = 1."""
    d = DEVICES[dev]
    R = rds_on(dev, Tj) * kRds / n_parallel
    P_cond = 4 * I_rms_dev ** 2 * R
    P_off = P_hard = P_diode = 0.0
    for i_sw in I_sw_edges:
        i_abs = abs(i_sw)
        if i_sw >= I_min_zvs:
            P_off += LS.eoff_scaled(dev, Vdc, i_abs) * fs * k_zvs
            P_diode += d["Vsd"] * i_abs * t_dead * fs * 0.5
        else:
            P_hard += (LS.eon_scaled(dev, Vdc, max(i_abs, 1.0)) + LS.eoff_scaled(dev, Vdc, max(i_abs, 1.0))) * fs
            P_hard += d["Coss_er"] * kCoss * Vdc ** 2 * fs
    P_gate = 4 * n_parallel * d["Qg"] * (d["Vgs_on"] - d["Vgs_off"]) * fs
    total = P_cond + P_off + P_hard + P_diode
    return dict(P_cond=P_cond, P_off=P_off, P_hard=P_hard, P_diode=P_diode, P_gate=P_gate, P_total=total, P_per_device=total / 4)


def _bridge_thermal(dev, p, Vdc, I_rms_dev, edges, fs, t_dead, Imin, Tamb, kRds, kCoss, iters=3):
    # contraction factor of the Tj <-> Rds_on loop is ~0.04 per iteration (0.5 %/K x 0.6 K/W x 12 W), 3 iterations -> < 1e-4 relative
    D = DEVICES[dev]; Tj = Tamb + 20.0; b = None
    for _ in range(iters):
        b = bridge_losses_u(dev, Vdc, I_rms_dev, edges, fs, Tj, t_dead, Imin, n_parallel=p, kRds=kRds, kCoss=kCoss)
        Tj = Tamb + b["P_total"] * HEATSINK["Rth_sink"] + b["P_per_device"] / p * (D["RthJC"] + HEATSINK["Rth_tim"])
    return b, Tj


def design_magnetics(d, nom):
    """Transformer and inductor designed at nominal (800/400 V, 6.6 kW) with the NOMINAL inductance."""
    xf = MG.design_transformer(V1_NOM, V2_NOM, d["n"], d["fs"], nom["Irms1"], nom["Irms1"] * d["n"], P_RATED,
                               core=d["tcore"], Bpk_target=d["Bpk"])
    L_ext = max(d["L"] - xf["Llk"], 2e-6)
    ind = MG.design_inductor(L_ext, nom["Ipk1"] * 1.2, nom["Irms1"], d["fs"], core=d["lcore"], Bpk_max=0.12)
    vol = (MG.CORES[d["tcore"]]["Ve"] * 2.2 + MG.CORES[d["lcore"]]["Ve"] * 2.2) * 1e6
    return xf, ind, L_ext, vol


def operating_point(d, V1, V2, P, u, xf, ind, nom):
    """
    Losses, Tj, ZVS margins at (V1, V2, P) with realised parameters u.  P = 0 -> standby (bridges off,
    Tj = Tamb, only auxiliary loss).  Returns None if |P| is unreachable with the realised inductance.
    """
    kL, kCoss, kRds, kCore, Tamb = u
    if P == 0:
        return dict(P_loss=P_AUX, Tj1=Tamb, Tj2=Tamb, zvs1=math.nan, zvs2=math.nan, Irms1=0.0, Ipk1=0.0, phi=0.0,
                    P_semi=0.0, P_core_xf=0.0, P_mag=0.0, hard1=False, hard2=False)
    L = d["L"] * kL; n = d["n"]; fs = d["fs"]
    sp = sps_point(V1, V2, n, L, fs, P)
    if sp is None:
        return None
    (dev1, p1), (dev2, p2) = d["dev1"], d["dev2"]
    D1, D2 = DEVICES[dev1], DEVICES[dev2]
    Imin1 = M.zvs_current_min(D1["Coss_er"] * p1 * kCoss, V1, L, C_PAR)
    Imin2 = M.zvs_current_min(D2["Coss_er"] * p2 * kCoss, V2, L / n ** 2, C_PAR * n ** 2) / n   # referred to port 1
    e1 = [sp["I0"], sp["I0"]]; e2 = [sp["I1"] * n, sp["I1"] * n]
    Irms_dev1 = sp["Irms1"] / math.sqrt(2); Irms_dev2 = sp["Irms1"] * n / math.sqrt(2)
    b1, Tj1 = _bridge_thermal(dev1, p1, V1, Irms_dev1, e1, fs, d["t_dead"], Imin1, Tamb, kRds, kCoss)
    b2, Tj2 = _bridge_thermal(dev2, p2, V2, Irms_dev2, e2, fs, d["t_dead"], Imin2 * n, Tamb, kRds, kCoss)
    beta = MG.MATERIALS["3C95"]["beta"]
    P_core_xf = xf["P_core"] * kCore * (V1 / V1_NOM) ** beta
    P_xf = P_core_xf + xf["P_cu"] * (sp["Irms1"] / nom["Irms1"]) ** 2
    P_ind = ind["P_core"] * kCore * (sp["Ipk1"] / nom["Ipk1"]) ** 2.5 + ind["P_cu"] * (sp["Irms1"] / nom["Irms1"]) ** 2
    P_semi = b1["P_total"] + b2["P_total"]
    P_loss = P_semi + b1["P_gate"] + b2["P_gate"] + P_xf + P_ind + P_AUX + K_PCB * abs(P)
    return dict(P_loss=P_loss, Tj1=Tj1, Tj2=Tj2, zvs1=sp["I0"] - Imin1, zvs2=sp["I1"] - Imin2, Irms1=sp["Irms1"],
                Ipk1=sp["Ipk1"], phi=sp["phi"], P_semi=P_semi, P_core_xf=P_core_xf, P_mag=P_xf + P_ind,
                hard1=b1["P_hard"] > 0, hard2=b2["P_hard"] > 0, b1=b1, b2=b2)


# ----------------------------------------------------------------------------- rainflow + lifetime proxy
def rainflow(series):
    """ASTM E1049 rainflow (3-point) on a closed sequence; returns list of (range, mean, count)."""
    x = np.asarray(series, float)
    if len(x) < 3:
        return []
    # reversals
    rev = [x[0]]
    for i in range(1, len(x) - 1):
        if (x[i] - rev[-1]) * (x[i + 1] - x[i]) < 0:
            rev.append(x[i])
    rev.append(x[-1])
    out = []; stack = []
    for p in rev:
        stack.append(p)
        while len(stack) >= 3:
            X = abs(stack[-1] - stack[-2]); Y = abs(stack[-2] - stack[-3])
            if X < Y:
                break
            if len(stack) == 3:
                out.append((Y, 0.5 * (stack[0] + stack[1]), 0.5)); stack.pop(0)
            else:
                out.append((Y, 0.5 * (stack[-2] + stack[-3]), 1.0)); del stack[-3:-1]
    for i in range(len(stack) - 1):
        out.append((abs(stack[i + 1] - stack[i]), 0.5 * (stack[i + 1] + stack[i]), 0.5))
    return out


def daily_damage(Tj_series):
    """Sum n_i / Nf_i over the rainflow cycles of one day (LESIT law, Tm in K)."""
    D = 0.0
    for dT, Tm, cnt in rainflow(list(Tj_series) + [Tj_series[0]]):
        if dT < DTJ_MIN:
            continue
        Nf = LESIT["A"] * dT ** LESIT["alpha"] * math.exp(LESIT["Q_over_R"] / (Tm + 273.15))
        D += cnt / Nf
    return D


# ----------------------------------------------------------------------------- full design evaluation
def evaluate_design(d, u=U_NOM, mission=MISSION, want_detail=False, phi_max=PHI_MAX, zvs_constraint="nominal"):
    """
    Returns dict:
      f    : objectives to MINIMISE [P_loss_nom (W), vol (cm3), log10(daily damage) , -ZVS margin (A)]
      g    : constraints (<= 0 feasible) [phi/phi_max-1 (max over 9 corners, phi_max = 60 deg by default), Tj/125-1,
             -zvs_req/5A (zvs_constraint = "nominal": ZVS at 800/400 V at 100 % and 50 % load - requirement EL-04a style;
             "corners": ZVS at every full-power envelope corner - stricter than the requirements, see README),
             Bpk(850 V)/0.2-1, fill_t/0.7-1, fill_l/0.7-1, Ipk/24-1]
      aux  : secondary quantities (eta, mission energy, dTj, ...).
    Objective 3 is absolute log10(damage/day); callers normalise it to the baseline.
    """
    kL = u[0]
    L_real = d["L"] * kL
    # full power reachable at all 9 corners with phi <= 60 deg (realised inductance)
    phi_worst = 0.0
    for V1, V2 in ALL9:
        sp = sps_point(V1, V2, d["n"], L_real, d["fs"], P_RATED)
        phi_worst = max(phi_worst, (math.pi / 2) if sp is None else sp["phi"])
    g_phi = phi_worst / phi_max - 1.0
    if phi_worst >= math.pi / 2:                      # full power unreachable at a corner: no finite objectives
        return dict(f=np.array([math.nan] * 4), g=np.array([g_phi, 0, 0, 0, 0, 0, 0.0]), feasible=False, aux={})
    nom_design = sps_point(V1_NOM, V2_NOM, d["n"], d["L"], d["fs"], P_RATED)   # nominal L for the magnetics design
    xf, ind, L_ext, vol = design_magnetics(d, nom_design)
    Bpk_hi = xf["Bpk"] * 850.0 / V1_NOM
    g_bpk = Bpk_hi / BPK_MAX - 1.0
    g_fill_t = xf["fill"] / FILL_MAX - 1.0
    g_fill_l = ind["fill"] / FILL_MAX - 1.0
    # envelope at full and half power
    pts_full = {}; pts_half = {}
    for V1, V2 in [(V1_NOM, V2_NOM)] + CORNERS_FULL:
        pts_full[(V1, V2)] = operating_point(d, V1, V2, P_RATED, u, xf, ind, nom_design)
        pts_half[(V1, V2)] = operating_point(d, V1, V2, 0.5 * P_RATED, u, xf, ind, nom_design)
    if any(v is None for v in pts_full.values()):
        return dict(f=np.array([math.nan] * 4), g=np.array([max(g_phi, 0.3), 0, 0, g_bpk, g_fill_t, g_fill_l, 0.0]), feasible=False, aux={})
    nom = pts_full[(V1_NOM, V2_NOM)]
    Tj_max = max(max(p["Tj1"], p["Tj2"]) for p in pts_full.values())
    zvs_full = min(min(p["zvs1"], p["zvs2"]) for p in pts_full.values())
    zvs_half = min(min(p["zvs1"], p["zvs2"]) for p in pts_half.values() if p is not None)
    zvs_obj = min(zvs_full, zvs_half)
    zvs_nom = min(nom["zvs1"], nom["zvs2"], pts_half[(V1_NOM, V2_NOM)]["zvs1"], pts_half[(V1_NOM, V2_NOM)]["zvs2"]) if pts_half[(V1_NOM, V2_NOM)] else min(nom["zvs1"], nom["zvs2"])
    zvs_req = zvs_full if zvs_constraint == "corners" else zvs_nom
    Ipk_max = max(p["Ipk1"] for p in pts_full.values())
    g = np.array([g_phi, Tj_max / TJ_LIMIT - 1.0, -zvs_req / 5.0, g_bpk, g_fill_t, g_fill_l, Ipk_max / IPK_LIMIT - 1.0])
    # mission
    cache = {}; Tj1s = []; Tj2s = []; E_loss = 0.0; E_thru = 0.0; unreachable = 0
    for (P, V1, V2) in mission:
        key = (P, V1, V2)
        if key not in cache:
            cache[key] = operating_point(d, V1, V2, P, u, xf, ind, nom_design)
        op = cache[key]
        if op is None:
            unreachable += 1; op = dict(P_loss=math.nan, Tj1=u[4], Tj2=u[4])
        Tj1s.append(op["Tj1"]); Tj2s.append(op["Tj2"]); E_loss += op["P_loss"] * MISSION_DT_H; E_thru += abs(P) * MISSION_DT_H
    D1 = daily_damage(Tj1s); D2 = daily_damage(Tj2s)
    D = max(D1, D2, 1e-300)
    f = np.array([nom["P_loss"], vol, math.log10(D), -zvs_obj])
    aux = dict(eta_nom=P_RATED / (P_RATED + nom["P_loss"]), Tj1_nom=nom["Tj1"], Tj2_nom=nom["Tj2"], Tj_max=Tj_max,
               zvs_full=zvs_full, zvs_half=zvs_half, zvs_nom_100_50=zvs_nom, Ipk_max=Ipk_max,
               hard_switching_corners=sum(1 for p in pts_full.values() if p["hard1"] or p["hard2"]), Bpk=xf["Bpk"], Bpk_850=Bpk_hi, fill_t=xf["fill"],
               fill_l=ind["fill"], N1=xf["N1"], N2=xf["N2"], N_ind=ind["N"], L_ext=L_ext, Llk=xf["Llk"],
               E_loss_Wh=E_loss, E_thru_Wh=E_thru, eta_mission=E_thru / (E_thru + E_loss) if E_thru > 0 else math.nan,
               dTj1_max=float(np.max(Tj1s) - np.min(Tj1s)), dTj2_max=float(np.max(Tj2s) - np.min(Tj2s)),
               damage1=D1, damage2=D2, mission_unreachable=unreachable, P_semi_nom=nom["P_semi"], P_mag_nom=nom["P_mag"],
               phi_worst_deg=math.degrees(phi_worst),
               hard_switching_hours=sum(1 for (P, V1, V2) in mission if cache[(P, V1, V2)] and (cache[(P, V1, V2)]["hard1"] or cache[(P, V1, V2)]["hard2"])))
    feasible = bool(np.all(g <= 0.0)) and unreachable == 0
    if unreachable:
        g[0] = max(g[0], 0.05 * unreachable)
    out = dict(f=f, g=g, feasible=feasible, aux=aux)
    if want_detail:
        out["pts_full"] = pts_full; out["pts_half"] = pts_half; out["Tj1_series"] = Tj1s; out["Tj2_series"] = Tj2s
        out["xf"] = xf; out["ind"] = ind
    return out


def lhs(n, dim, rng):
    """Latin-hypercube sample in [0,1]^dim (centred-perturbed, one point per stratum)."""
    u = (np.arange(n)[:, None] + rng.random((n, dim))) / n
    for j in range(dim):
        u[:, j] = u[rng.permutation(n), j]
    return u


def u_from_unit(z):
    """Map [0,1]^5 -> physical uncertainty vector(s) with the uniform bounds U_BOUNDS."""
    z = np.asarray(z, float)
    return U_BOUNDS[:, 0] + (U_BOUNDS[:, 1] - U_BOUNDS[:, 0]) * z


# ----------------------------------------------------------------------------- self test
def self_test():
    """Closed-form vs numerical DAB model, scaled vs original loss model, and baseline reproduction."""
    rep = {}
    err_wave = 0.0; err_edge_cf = 0.0; err_edge_num = 0.0
    for V1, V2 in ALL9:
        sp = sps_point(V1, V2, 2.0, 64e-6, 100e3, P_RATED)
        pt = M.DABPoint(V1, V2, 2.0, 64e-6, 100e3, sp["phi"], N=4000)
        I0n, I1n = M.sps_switching_currents(V1, 2.0 * V2, 64e-6, 100e3, sp["phi"])
        err_wave = max(err_wave, abs(sp["Irms1"] - pt.I_rms1) / pt.I_rms1, abs(sp["Ipk1"] - pt.I_peak1) / pt.I_peak1)
        err_edge_cf = max(err_edge_cf, abs(sp["I0"] - I0n), abs(sp["I1"] - I1n))
        err_edge_num = max(err_edge_num, abs(sp["I0"] - pt.zvs_margin(1, 0.0)), abs(sp["I1"] - pt.zvs_margin(2, 0.0)))
    rep["max_rel_err_Irms_Ipk_vs_DABPoint_N4000"] = err_wave
    rep["max_abs_err_A_edge_current_vs_dab_model_closed_form"] = err_edge_cf
    rep["max_abs_err_A_edge_current_vs_DABPoint_N4000_grid"] = err_edge_num   # one grid step of di/dtheta: numerical model's discretisation
    b_ref = LS.bridge_losses("C3M0032120K", 800, 7.0, [10.0, 10.0], 100e3, 60.0, 150e-9, 3.0)
    b_new = bridge_losses_u("C3M0032120K", 800, 7.0, [10.0, 10.0], 100e3, 60.0, 150e-9, 3.0)
    rep["bridge_losses_identity_at_k1"] = max(abs(b_ref[k] - b_new[k]) for k in b_ref)
    r = evaluate_design(BASELINE)
    rep["baseline_P_loss_W"] = float(r["f"][0]); rep["baseline_vol_cm3"] = float(r["f"][1])
    rep["baseline_feasible"] = r["feasible"]
    return rep


if __name__ == "__main__":
    import json, time
    t = time.time(); rep = self_test(); rep["t_s"] = time.time() - t
    print(json.dumps(rep, indent=1, default=str))
    t = time.time()
    for _ in range(50):
        evaluate_design(BASELINE)
    print("ms per evaluate_design:", (time.time() - t) / 50 * 1e3)
