#!/usr/bin/env python3
"""
Observability / identifiability of the twin parameters from the available sensors.

Parameters p = [L, Coss_er1, Coss_er2, R_s] (series inductance, effective output capacitances of the
HV and LV devices, AC loop resistance).  Candidate measurements per switching period:
  I2_avg (LV shunt), I1_avg (HV CT), I_pk (peak detector on the CT), v2 ripple (not used),
  t_tr1 (HV drain transition time, PROPOSED sensor), t_tr2 (LV, PROPOSED).
Sensitivities by central finite differences on the switched plant in steady state (stiff ports);
Fisher information F = sum_k J_k^T R^-1 J_k over operating points; Cramer-Rao bound per parameter for
each sensor set.  Result: which parameters are identifiable with the sensors on the board and which
need the proposed transition-time sensor.
"""
import json, math, os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from twin import ROOT, SENSOR, make_plant, period_measurements, DEVICES  # noqa: E402
V = json.load(open(os.path.join(ROOT, "04_Design_Calculations", "design_values.json")))
L0, n, fs = V["L"], V["spec"]["n"], V["spec"]["fs"]
C1, C2 = 200e-6, 2000e-6
dev1, dev2 = V["dev1"], V["dev2"]
P0 = dict(L=L0, C1=DEVICES[dev1]["Coss_er"], C2=DEVICES[dev2]["Coss_er"], Rs=0.3)
NAMES = ["L", "Coss_er1", "Coss_er2", "R_s"]


def steady(p, V1, V2, phi, D1, D2, periods=40):
    """Steady-state period measurements of the switched plant with parameters p (stiff ports)."""
    plant = make_plant(p["L"], n, fs, C1, C2, V1, lambda v2, t: (v2 - V2) / 0.05, R_s=p["Rs"], N_sub=200)
    plant.v2 = V2
    for k in range(periods - 1): plant.run_period(phi, D1, D2)
    rec = plant.run_period(phi, D1, D2, record=True)
    i2, i1, i_edge = period_measurements(plant, rec)
    r = np.asarray(rec); i_pk = float(np.max(np.abs(r[:, 3])))
    # transition times (charge based): t = 2 Coss V / |I_edge| at each bridge; LV edge current ~ i_edge * n (approx. same instants)
    t1 = 2 * p["C1"] * V1 / max(i_edge, 0.2); t2 = 2 * p["C2"] * V2 / max(i_edge * n, 0.2)
    return np.array([i2, i1, i_pk, t1, t2])


def jacobian(V1, V2, phi, D1, D2, rel=0.02):
    base = steady(P0, V1, V2, phi, D1, D2); J = np.zeros((5, 4))
    for j, key in enumerate(["L", "C1", "C2", "Rs"]):
        pp = dict(P0); pm = dict(P0); h = rel * P0[key]; pp[key] += h; pm[key] -= h
        J[:, j] = (steady(pp, V1, V2, phi, D1, D2) - steady(pm, V1, V2, phi, D1, D2)) / (2 * h) * P0[key]   # d y / d ln p
    return base, J


def main():
    t0 = time.time()
    sig = np.array([SENSOR["i2_fs"] / 2 ** 12 * 0.5 + 0.005 * 16, SENSOR["i1_fs"] / 2 ** 12 * 0.5 + 0.01 * 8, 0.3, SENSOR["t_tr_noise"], SENSOR["t_tr_noise"]])
    # operating points: (V1, V2, phi, D1, D2) - EPS matching, 10..100 % power, both directions
    pts = []
    for V1 in (650.0, 800.0, 850.0):
        for V2 in (300.0, 400.0, 450.0):
            d = n * V2 / V1; D1, D2 = (min(1, d), 1.0) if d < 1 else (1.0, min(1, 1 / d))
            for phi in (0.08, 0.25, 0.5, -0.25):
                pts.append((V1, V2, phi, D1, D2))
    sets = {"board: I2_avg": [0], "board: I2_avg + I1_avg": [0, 1], "board: I2, I1, I_pk": [0, 1, 2],
            "+ proposed t_tr(HV)": [0, 1, 2, 3], "+ proposed t_tr(HV, LV)": [0, 1, 2, 3, 4]}
    Fs = {k: np.zeros((4, 4)) for k in sets}
    Jlist = []
    for (V1, V2, phi, D1, D2) in pts:
        y, J = jacobian(V1, V2, phi, D1, D2); Jlist.append(dict(V1=V1, V2=V2, phi=phi, J=J.tolist(), y=y.tolist()))
        for k, idx in sets.items():
            Jk = J[idx, :]; R = np.diag(sig[idx] ** 2)
            Fs[k] += Jk.T @ np.linalg.inv(R) @ Jk
    out = {}
    N = len(pts)
    for k, F in Fs.items():
        ev = np.linalg.eigvalsh(F); rank = int((ev > 1e-6 * ev.max()).sum())
        row = dict(rank=rank, eigenvalues=ev.tolist(), cond=float(ev.max() / max(ev[ev > 0].min(), 1e-300)) if rank == 4 else None)
        # Cramer-Rao bound (relative std, since J is w.r.t. ln p) for the identifiable sub-block
        try:
            crlb = np.sqrt(np.diag(np.linalg.pinv(F)))
            row["crlb_rel_std_per_point"] = {NAMES[i]: float(crlb[i]) for i in range(4)}
            row["crlb_rel_std_after_1000_periods"] = {NAMES[i]: float(crlb[i] / math.sqrt(1000 / N)) for i in range(4)}
        except np.linalg.LinAlgError:
            pass
        # identifiable directions: parameters whose column norm in F is > 1e-6 of the max
        diag = np.diag(F); row["information_per_parameter"] = {NAMES[i]: float(diag[i]) for i in range(4)}
        out[k] = row
    res = dict(sensor_noise_1sigma=dict(I2_avg=float(sig[0]), I1_avg=float(sig[1]), I_pk=float(sig[2]), t_tr=float(sig[3])),
               operating_points=N, sets=out, jacobians=Jlist, wall_s=time.time() - t0)
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    json.dump(res, open(os.path.join(HERE, "results", "observability.json"), "w"), indent=1)
    print(json.dumps({k: dict(rank=v["rank"], crlb_1000=v.get("crlb_rel_std_after_1000_periods")) for k, v in out.items()}, indent=1))
    print("wall", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
