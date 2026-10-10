#!/usr/bin/env python3
"""
SYNTHETIC degradation data generator for SiC MOSFET health monitoring (Rds_on / Vgs_th drift).

EVERYTHING PRODUCED HERE IS SYNTHETIC. No measured aging data exists in this project. The purpose
is a feasibility and sensor-requirement study for the estimators in 02_estimators_and_detection.py.

Model (all coefficients are literature-typical ORDERS OF MAGNITUDE, labelled as assumptions):
  Operating point per hour h (mission, random with daily pattern, seed below):
      p_h ~ U(0.2, 1.0) * daily profile, V1 ~ U(650, 850), V2 ~ U(300, 450), Tamb = 35 + 10 sin(2 pi h/24)
  Device current sample (HV device, mid-conduction):  I_s = 0.85 * Ipk1_nom * p_h * (800 / V1)
  Junction temperature (steady state per hour, forced-air heatsink of 13_Thermal_Analysis):
      Tj = Tamb + P_bridge * Rth_sink + P_dev * (RthJC + Rth_tim),  P_dev = I_dev^2 Rds(Tj) + P_sw
      (two fixed-point iterations; P_sw = 0.9 W per device at nominal, scaled with p_h)
  Damage accumulation (Coffin-Manson-Arrhenius, hour-to-hour Tj swing as one cycle, plus one daily on/off cycle):
      N_f(dTj, Tm) = A * dTj^(-alpha) * exp(Ea / (kB * Tm_K)),  alpha = 4.4 (Bayerer-type), Ea = 0.08 eV
      D_h = sum 1 / N_f ;  A is calibrated so that D = 1 ("end of life") is reached after ~2.5 years
      for the degrading scenario.  Healthy scenario: A -> infinity (no damage).
  Rds_on degradation (bond-wire lift-off / die-attach fatigue):
      R_true(T, D) = rds_on(dev, T) * (1 + k_EOL * D^gamma),  k_EOL = 0.05 (AQG 324-type +5 % criterion), gamma = 1.5
  Gate-oxide threshold drift (positive-bias charge trapping, logarithmic in time):
      dVth(h) = a_vth * log10(1 + h / tau_vth),  a_vth = 0.08 V, tau_vth = 100 h  (~0.2 V after 3 years)
      channel-resistance share f_ch = 0.4 of Rds_on scales with (Vgs_on - Vth0) / (Vgs_on - Vth0 - dVth)
  Measurement chain (the project's sensing chain; V_ds_on sensing is a PROPOSAL, see README):
      V_ds: divider 1:4 -> AMC1301 (gain 8.2) -> TLV9062 -> 12-bit ADC 3.3 V FS: LSB 0.806 mV / 2.05 = 0.39 mV at the device
            gain error 0.3 % fixed + 50 ppm/K * (T_board - 25), offset 0.2 mV + 3 uV/K, noise 1.0 mV rms (output 3 mV / 2.05 / sqrt(averaging 2))
      I_d : CT 1:100, 6.2 Ohm burden, 40 A FS, 12-bit: LSB 9.8 mA; ratio error 1 % fixed + 100 ppm/K, noise 30 mA rms
      T   : three sensor placements  (a) heatsink NTC (current design): bias = P_dev (RthJC + Rth_tim) [load dependent], noise 1 K
                                      (b) case sensor:                     bias = P_dev RthJC,               noise 0.5 K
                                      (c) junction estimate (model):       bias ~ N(0, 1 K) slowly varying,  noise 0.5 K
Outputs (results/):  SYNTHETIC_mission_<scenario>.csv, SYNTHETIC_truth_<scenario>.csv, SYNTHETIC_meas_<scenario>_<Tsensor>.csv,
                     SYNTHETIC_generator_params.json, fig_synthetic_truth.png
"""
import os, sys, json, time, hashlib, platform
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DAB = os.path.join(REPO, "SiC_6k6_Industrial_DAB")
sys.path.insert(0, DAB)
from dabtools.dab.devices import DEVICES, rds_on  # noqa: E402
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt  # noqa: E402

RES = os.path.join(HERE, "results"); os.makedirs(RES, exist_ok=True)
SEED = 20261010
T0 = time.time()
V = json.load(open(os.path.join(DAB, "04_Design_Calculations", "design_values.json")))
DEV = V["dev1"]; d = DEVICES[DEV]
HOURS = 3 * 365 * 24                       # 3 years hourly
KB = 8.617e-5                              # eV/K

P = dict(seed=SEED, device=DEV, hours=HOURS, Ipk1_nom=V["nominal"]["Ipk1"], Irms1_nom=V["nominal"]["Irms1"],
         Rth_sink=V["heatsink"]["Rth_sink"], Rth_tim=V["heatsink"]["Rth_tim"], RthJC=d["RthJC"], P_sw_nom=0.9,
         alpha=4.4, Ea_eV=0.08, k_EOL=0.05, gamma=1.5, EOL_years_target=2.5,
         a_vth=0.08, tau_vth_h=100.0, f_ch=0.4, Vgs_on=d["Vgs_on"], Vth0=d["Vgs_th"],
         vds_lsb=0.806e-3 / 2.05, vds_gain_err=0.003, vds_gain_tc=50e-6, vds_offset=0.2e-3, vds_offset_tc=3e-6, vds_noise=1.0e-3,
         id_lsb=40.0 / 4096, id_gain_err=0.01, id_gain_tc=100e-6, id_noise=0.03,
         T_sensors={"heatsink_ntc": dict(bias="P_dev*(RthJC+Rth_tim)", noise=1.0),
                    "case_sensor": dict(bias="P_dev*RthJC", noise=0.5),
                    "junction_model": dict(bias="slow N(0,1K)", noise=0.5)},
         note="SYNTHETIC - literature-typical orders of magnitude, not measured; see README")


def mission(rng, hours):
    h = np.arange(hours)
    daily = 0.6 + 0.4 * np.sin(2 * np.pi * (h % 24) / 24 - np.pi / 2) ** 2       # night low / day high
    p = np.clip(rng.uniform(0.2, 1.0, hours) * daily / daily.max() + 0.1, 0.1, 1.0)
    V1 = rng.uniform(650, 850, hours); V2 = rng.uniform(300, 450, hours)
    Tamb = 35 + 10 * np.sin(2 * np.pi * h / 24) + 5 * np.sin(2 * np.pi * h / (24 * 365))
    return p, V1, V2, Tamb


def thermal(p, V1, Tamb, R_mult):
    """Steady-state Tj per hour with Rds(Tj) feedback (2 fixed-point iterations)."""
    I_dev = P["Irms1_nom"] / np.sqrt(2) * p * 800.0 / V1
    P_sw = P["P_sw_nom"] * p
    Tj = Tamb + 15.0
    for _ in range(2):
        R = rds_on(DEV, Tj) * R_mult
        P_dev = I_dev ** 2 * R + P_sw
        Tj = Tamb + 4 * P_dev * P["Rth_sink"] + P_dev * (P["RthJC"] + P["Rth_tim"])
    return Tj, P_dev, I_dev


def calibrate_A(dT, Tm):
    """A such that the cumulative damage of the given cycle list equals 1 at EOL_years_target."""
    n_eol = int(P["EOL_years_target"] * 365 * 24)
    s = np.sum(dT[:n_eol] ** P["alpha"] * np.exp(-P["Ea_eV"] / (KB * (Tm[:n_eol] + 273.15))))
    return s


def generate(scenario, rng, p_shift=None):
    """p_shift = (hour, factor): optional non-stationary mission (load mix scaled by factor after the given hour)."""
    p, V1, V2, Tamb = mission(rng, HOURS)
    if p_shift is not None:
        p = np.where(np.arange(HOURS) >= p_shift[0], np.clip(p * p_shift[1], 0.1, 1.0), p)
    # first pass without degradation to get the cycle list, then calibrate A and integrate damage
    Tj0, P_dev0, I_dev = thermal(p, V1, Tamb, 1.0)
    dT = np.abs(np.diff(Tj0, prepend=Tj0[0])) + 1e-3
    Tm = 0.5 * (Tj0 + np.roll(Tj0, 1))
    daily_on_off = (np.arange(HOURS) % 24 == 6)                        # one full on/off cycle per day (Tj -> Tamb)
    dT = np.where(daily_on_off, np.maximum(dT, Tj0 - Tamb), dT)
    A = calibrate_A(dT, Tm) if scenario == "degrading" else np.inf
    inv_Nf = dT ** P["alpha"] * np.exp(-P["Ea_eV"] / (KB * (Tm + 273.15))) / A
    D = np.cumsum(inv_Nf)
    h = np.arange(HOURS)
    dVth = P["a_vth"] * np.log10(1 + h / P["tau_vth_h"]) if scenario == "degrading" else np.zeros(HOURS)
    ch_factor = 1 + P["f_ch"] * ((P["Vgs_on"] - P["Vth0"]) / (P["Vgs_on"] - P["Vth0"] - dVth) - 1)
    R_mult = (1 + P["k_EOL"] * D ** P["gamma"]) * ch_factor
    Tj, P_dev, I_dev = thermal(p, V1, Tamb, R_mult)
    R25_true = rds_on(DEV, 25.0) * R_mult
    R_true = rds_on(DEV, Tj) * R_mult
    I_s = 0.85 * P["Ipk1_nom"] * p * 800.0 / V1
    Vds_true = I_s * R_true
    return dict(h=h, p=p, V1=V1, V2=V2, Tamb=Tamb, Tj=Tj, P_dev=P_dev, D=D, dVth=dVth, R_mult=R_mult,
                R25_true=R25_true, R_true=R_true, I_s=I_s, Vds_true=Vds_true, A=A)


def measure(tr, sensor, rng):
    n = HOURS
    T_board = tr["Tamb"] + 10.0                                            # control-board temperature (estimate)
    g_v = 1 + P["vds_gain_err"] + P["vds_gain_tc"] * (T_board - 25)
    off_v = P["vds_offset"] + P["vds_offset_tc"] * (T_board - 25)
    Vm = tr["Vds_true"] * g_v + off_v + rng.normal(0, P["vds_noise"], n)
    Vm = np.round(Vm / P["vds_lsb"]) * P["vds_lsb"]
    g_i = 1 + P["id_gain_err"] + P["id_gain_tc"] * (T_board - 25)
    Im = tr["I_s"] * g_i + rng.normal(0, P["id_noise"], n)
    Im = np.round(Im / P["id_lsb"]) * P["id_lsb"]
    if sensor == "heatsink_ntc":
        Tm = tr["Tj"] - tr["P_dev"] * (P["RthJC"] + P["Rth_tim"]) + rng.normal(0, 1.0, n)
    elif sensor == "case_sensor":
        Tm = tr["Tj"] - tr["P_dev"] * P["RthJC"] + rng.normal(0, 0.5, n)
    else:                                                                  # junction model: slow random bias
        slow = np.convolve(rng.normal(0, 1.0, n), np.ones(24 * 7) / (24 * 7), mode="same") * np.sqrt(24 * 7)
        Tm = tr["Tj"] + slow + rng.normal(0, 0.5, n)
    return Vm, Im, Tm


def save_csv(path, header_note, cols):
    names = list(cols)
    arr = np.column_stack([cols[k] for k in names])
    np.savetxt(path, arr, delimiter=",", header="SYNTHETIC DATA - " + header_note + "\n" + ",".join(names), comments="# ", fmt="%.5g")


def main():
    rng = np.random.default_rng(SEED + 100)                      # measurement-noise stream
    out = {}
    for i, sc in enumerate(("healthy", "degrading")):
        tr = generate(sc, np.random.default_rng(SEED + i))        # truth streams: SEED (healthy), SEED+1 (degrading)
        out[sc] = tr
        save_csv(os.path.join(RES, f"SYNTHETIC_mission_{sc}.csv"), f"mission profile, scenario {sc}, seed {SEED}",
                 dict(hour=tr["h"], p_frac=tr["p"], V1=tr["V1"], V2=tr["V2"], Tamb=tr["Tamb"]))
        save_csv(os.path.join(RES, f"SYNTHETIC_truth_{sc}.csv"), f"ground truth, scenario {sc}, seed {SEED}",
                 dict(hour=tr["h"], Tj=tr["Tj"], P_dev=tr["P_dev"], damage=tr["D"], dVth=tr["dVth"], R_mult=tr["R_mult"],
                      R25_true=tr["R25_true"], R_true=tr["R_true"], I_s=tr["I_s"], Vds_true=tr["Vds_true"]))
        for sensor in P["T_sensors"]:
            Vm, Im, Tm = measure(tr, sensor, rng)
            save_csv(os.path.join(RES, f"SYNTHETIC_meas_{sc}_{sensor}.csv"), f"measurements, scenario {sc}, T sensor {sensor}, seed {SEED}",
                     dict(hour=tr["h"], Vds_meas=Vm, Id_meas=Im, T_meas=Tm))
    tr = out["degrading"]
    yrs = tr["h"] / 8760
    fig, ax = plt.subplots(2, 2, figsize=(11, 6.5))
    ax[0, 0].plot(yrs, tr["Tj"], lw=0.3); ax[0, 0].set_ylabel("Tj (C)"); ax[0, 0].set_title("SYNTHETIC junction temperature (hourly)")
    ax[0, 1].plot(yrs, 100 * (tr["R_mult"] - 1), label="total"); ax[0, 1].plot(yrs, 100 * P["k_EOL"] * tr["D"] ** P["gamma"], "--", label="bond-wire/die-attach (damage)")
    ax[0, 1].plot(yrs, 100 * (tr["R_mult"] / (1 + P["k_EOL"] * tr["D"] ** P["gamma"]) - 1), ":", label="Vth-drift share")
    ax[0, 1].axhline(5, c="r", lw=0.8); ax[0, 1].set_ylabel("dRds_on / R0 (%)"); ax[0, 1].legend(fontsize=8); ax[0, 1].set_title("SYNTHETIC Rds_on drift components")
    ax[1, 0].plot(yrs, tr["D"]); ax[1, 0].set_ylabel("damage D (1 = EOL)"); ax[1, 0].set_xlabel("years")
    ax[1, 1].plot(yrs, 1e3 * tr["Vds_true"], lw=0.3); ax[1, 1].set_ylabel("V_ds,on sample (mV)"); ax[1, 1].set_xlabel("years"); ax[1, 1].set_title("true V_ds,on at the sample instant")
    for a in ax.ravel(): a.grid(alpha=0.3)
    fig.suptitle("SYNTHETIC degradation data (seed %d) - not measurements" % SEED); fig.tight_layout()
    fig.savefig(os.path.join(RES, "fig_synthetic_truth.png"), dpi=130); plt.close(fig)
    P["A_calibrated"] = float(tr["A"]); P["EOL_hour_degrading"] = int(np.argmax(tr["D"] >= 1.0)) if (tr["D"] >= 1).any() else None
    P["dR_pct_at_3y_degrading"] = float(100 * (tr["R_mult"][-1] - 1)); P["dVth_V_at_3y"] = float(tr["dVth"][-1])
    P["Tj_range_C"] = [float(tr["Tj"].min()), float(tr["Tj"].max())]
    json.dump(P, open(os.path.join(RES, "SYNTHETIC_generator_params.json"), "w"), indent=1)
    # provenance
    import numpy, matplotlib as mpl
    def h(pth):
        return hashlib.sha256(open(pth, "rb").read()).hexdigest()[:16]
    head = open(os.path.join(REPO, ".git", "HEAD")).read().strip()
    commit = head
    if head.startswith("ref:"):
        rp = os.path.join(REPO, ".git", head[5:])
        commit = open(rp).read().strip() if os.path.exists(rp) else head
    prov = dict(script=os.path.basename(__file__), python=platform.python_version(), numpy=numpy.__version__, matplotlib=mpl.__version__,
                git_commit=commit, seed=SEED, wall_time_s=round(time.time() - T0, 2),
                inputs={os.path.relpath(f, REPO): h(f) for f in [os.path.join(DAB, "04_Design_Calculations", "design_values.json"),
                                                                 os.path.join(DAB, "dabtools", "dab", "devices.py")]},
                outputs=sorted(os.listdir(RES)), data_label="SYNTHETIC")
    json.dump(prov, open(os.path.join(RES, "provenance_generator.json"), "w"), indent=1)
    print(json.dumps({k: P[k] for k in ("A_calibrated", "EOL_hour_degrading", "dR_pct_at_3y_degrading", "dVth_V_at_3y", "Tj_range_C")}, indent=1))
    print("wall %.1f s" % (time.time() - T0))


if __name__ == "__main__":
    main()
