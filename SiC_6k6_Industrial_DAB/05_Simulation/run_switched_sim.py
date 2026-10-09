#!/usr/bin/env python3
"""
Closed-loop switched simulation of the 6.6 kW DAB (Python plant + Python controller).
Cases: start-up / soft start, 50 % load step, HV-bus 10 % dip, power reversal (CP mode),
light load (steady state), current limit (output short through 0.5 Ohm).
Outputs 05_Simulation/img/*.png and 05_Simulation/switched_results.json
"""
import os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
from dabtools.dab.sim_switched import DABPlant
from dabtools.dab.control import DABController
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
V = json.load(open(os.path.join(ROOT, "04_Design_Calculations", "design_values.json")))
L, n, fs = V["L"], V["spec"]["n"], V["spec"]["fs"]
C1, C2 = V["dclink"]["C1"] + 500e-6, V["dclink"]["C2"] + 1000e-6     # bus capacitances per APP-04
P = V["spec"]["P"]
res = {}

CP = json.load(open(os.path.join(ROOT, "11_Control_Algorithms", "control_params.json")))
def controller(kp=None, ki=None):
    # PI gains from 11_Control_Algorithms/control_design.py (600 Hz crossover, 1.5 Ts delay)
    kp = kp or CP["kp"]
    ki = ki or CP["ki"]
    c = DABController(L, n, fs, kp, ki, P_max=1.1 * P)
    c.phi_dead_comp = 0.5 * 2 * math.pi * fs * V["t_dead"]
    return c

def run(case, periods, load_fn, v1_fn=lambda t: 800.0, mode="CV", P_ref=0.0, v2_init=0.0, record_last=2, enable_at=0):
    plant = DABPlant(L, n, fs, C1, C2, 800.0, 0.3, load_fn, N_sub=200)
    plant.v2 = v2_init
    ctl = controller(); ctl.mode = mode; ctl.P_ref = P_ref
    if mode == "CP":
        ctl.state = "RUN"; ctl.ss_scale = 1.0
    t_log, v2_log, v1_log, p_log, phi_log, state_log = [], [], [], [], [], []
    ipk_log = []
    rec_last = []
    for k in range(periods):
        plant.V1_src = v1_fn(plant.t)
        m = dict(v1=plant.v1, v2=plant.v2, i_pk=plant.ipk, T=40, precharge_ok=True)
        phi, D1, D2 = ctl.step(m, enable=(k >= enable_at))
        rec = plant.run_period(phi, D1, D2, record=(k >= periods - record_last))
        if rec: rec_last += rec
        t_log.append(plant.t); v2_log.append(plant.v2); v1_log.append(plant.v1); phi_log.append(math.degrees(phi)); state_log.append(ctl.state)
        p_log.append(ctl.log[-1][1] if ctl.log else 0.0); ipk_log.append(plant.ipk)
    return dict(t=np.array(t_log), v2=np.array(v2_log), v1=np.array(v1_log), phi=np.array(phi_log), P=np.array(p_log),
                ipk=np.array(ipk_log), state=state_log, rec=np.array(rec_last), ctl=ctl)

# 1. start-up from a precharged LV link (380 V, APP-05) into 50 % load, 50 -> 100 % step at 80 ms, back at 120 ms
R_full = 400 ** 2 / P
def load_step(v2, t):
    R = R_full if 0.08 <= t < 0.12 else 2 * R_full
    return v2 / R
r = run("startup_step", 16000, load_step, v2_init=380.0)
res["startup"] = dict(v2_final=float(r["v2"][-1]), overshoot_pct=float(100 * (r["v2"].max() - 400) / 400),
                      t_rise_ms=float(r["t"][np.argmax(r["v2"] > 396)] * 1e3) if (r["v2"] > 396).any() else None)
seg = (r["t"] >= 0.08) & (r["t"] < 0.12)
dev = r["v2"][seg]; res["load_step"] = dict(dip_pct=float(100 * (400 - dev.min()) / 400), rec_ms=float((r["t"][seg][np.argmax(np.abs(dev - 400) < 4)] - 0.08) * 1e3) if (np.abs(dev - 400) < 4).any() else None)
fig, ax = plt.subplots(3, 1, figsize=(7, 7), sharex=True)
ax[0].plot(r["t"] * 1e3, r["v2"]); ax[0].set_ylabel("V2 (V)"); ax[0].set_title("Start-up (soft start 50 ms), 50->100->50 % load steps at 80/120 ms")
ax[1].plot(r["t"] * 1e3, r["P"] / 1e3); ax[1].set_ylabel("P cmd (kW)")
ax[2].plot(r["t"] * 1e3, r["phi"]); ax[2].set_ylabel("phi (deg)"); ax[2].set_xlabel("t (ms)")
[a.grid(alpha=0.3) for a in ax]; fig.tight_layout(); fig.savefig(os.path.join(HERE, "img", "sim_startup_loadstep.png"), dpi=130); plt.close(fig)
# switching waveforms of the last two periods at full load
rr = r["rec"]
fig, ax = plt.subplots(3, 1, figsize=(7, 6), sharex=True)
tt = (rr[:, 0] - rr[0, 0]) * 1e6
ax[0].plot(tt, rr[:, 1], label="v_HV bridge"); ax[0].plot(tt, rr[:, 2], label="n v_LV bridge"); ax[0].legend(); ax[0].set_ylabel("V")
ax[1].plot(tt, rr[:, 3]); ax[1].set_ylabel("i_L (A, HV side)")
ax[2].plot(tt, rr[:, 6], label="i HV link"); ax[2].plot(tt, rr[:, 7] / n, label="i LV link / n"); ax[2].legend(); ax[2].set_ylabel("A"); ax[2].set_xlabel("us")
[a.grid(alpha=0.3) for a in ax]; fig.suptitle("Switching waveforms, closed loop, 800/400 V, 50 % load"); fig.tight_layout()
fig.savefig(os.path.join(HERE, "img", "sim_switching_waveforms.png"), dpi=130); plt.close(fig)
res["switching_50pct"] = dict(iL_pk=float(np.abs(rr[:, 3]).max()), iL_rms=float(np.sqrt(np.mean(rr[:, 3] ** 2))), v2_ripple_mV=float((rr[:, 5].max() - rr[:, 5].min()) * 1e3))

# 2. HV bus dip 800 -> 720 V (10 %) for 20 ms at full load
def v1_dip(t): return 720.0 if 0.07 <= t < 0.09 else 800.0
r2 = run("v1_dip", 12000, lambda v2, t: v2 / R_full, v1_fn=v1_dip, v2_init=380.0)
seg = (r2["t"] >= 0.07) & (r2["t"] < 0.11)
res["v1_dip"] = dict(v2_min=float(r2["v2"][seg].min()), v2_max=float(r2["v2"][seg].max()))
fig, ax = plt.subplots(2, 1, figsize=(7, 5), sharex=True)
ax[0].plot(r2["t"] * 1e3, r2["v1"]); ax[0].set_ylabel("V1 (V)"); ax[0].set_title("HV bus 10 % dip for 20 ms at full load")
ax[1].plot(r2["t"] * 1e3, r2["v2"]); ax[1].set_ylabel("V2 (V)"); ax[1].set_xlabel("t (ms)")
[a.grid(alpha=0.3) for a in ax]; fig.tight_layout(); fig.savefig(os.path.join(HERE, "img", "sim_v1_dip.png"), dpi=130); plt.close(fig)

# 3. power reversal in CP mode with a battery on the LV port (400 V, 0.1 Ohm)
def battery(v2, t): return (v2 - 400.0) / 0.1
r3 = run("reversal", 8000, battery, mode="CP", P_ref=P, v2_init=400.0)
ctl = r3["ctl"]
# ramp the reference from +P to -P between 20 and 30 ms (2 kW/ms slew limit -> 6.6 ms)
plant = DABPlant(L, n, C1=C1, C2=C2, fs=fs, V1_src=800.0, R1_src=0.3, load=battery, N_sub=200); plant.v2 = 400.0
c3 = controller(); c3.mode = "CP"; c3.state = "RUN"; c3.ss_scale = 1.0
t_l, p_l, i_l, v1_l, v2_l = [], [], [], [], []
for k in range(6000):
    t = plant.t
    c3.P_ref = P if t < 0.02 else (max(-P, P - 2e6 * (t - 0.02)) if t < 0.03 else -P)
    m = dict(v1=plant.v1, v2=plant.v2, i_pk=abs(plant.iL), T=40, precharge_ok=True)
    phi, D1, D2 = c3.step(m)
    plant.run_period(phi, D1, D2)
    t_l.append(t); p_l.append(c3.P_ref); i_l.append(plant.iL); v1_l.append(plant.v1); v2_l.append(plant.v2)
res["reversal"] = dict(v1_max=float(max(v1_l)), v1_min=float(min(v1_l)), v2_max=float(max(v2_l)), v2_min=float(min(v2_l)), fault=c3.fault)
fig, ax = plt.subplots(2, 1, figsize=(7, 5), sharex=True)
ax[0].plot(np.array(t_l) * 1e3, np.array(p_l) / 1e3); ax[0].set_ylabel("P ref (kW)"); ax[0].set_title("Power reversal +6.6 -> -6.6 kW (CP mode, battery on LV port)")
ax[1].plot(np.array(t_l) * 1e3, v1_l, label="V1"); ax[1].plot(np.array(t_l) * 1e3, v2_l, label="V2"); ax[1].legend(); ax[1].set_xlabel("t (ms)")
[a.grid(alpha=0.3) for a in ax]; fig.tight_layout(); fig.savefig(os.path.join(HERE, "img", "sim_reversal.png"), dpi=130); plt.close(fig)

# 4. current limit: LV short through 0.5 Ohm at t = 60 ms (CV mode) -> controller must saturate, hardware limit assumed at 32 A
r4 = run("short", 9000, lambda v2, t: v2 / R_full if t < 0.06 else v2 / 0.5, v2_init=380.0)
res["short"] = dict(fault=r4["ctl"].fault, phi_max=float(r4["phi"].max()), ipk_max=float(r4["ipk"].max()), v2_after=float(r4["v2"][-1]))

# 5. dead-bus start (LV link at 0 V, 2 mF, 10 % resistive load) with EPS voltage matching: shows the current-limited ramp
r5 = run("deadbus", 20000, lambda v2, t: v2 / (10 * R_full), v2_init=0.0)
res["dead_bus_start"] = dict(v2_final=float(r5["v2"][-1]), ipk_max=float(r5["ipk"].max()), fault=r5["ctl"].fault,
                             t_to_90pct_ms=float(r5["t"][np.argmax(r5["v2"] > 360)] * 1e3) if (r5["v2"] > 360).any() else None)
fig, ax = plt.subplots(2, 1, figsize=(7, 5), sharex=True)
ax[0].plot(r5["t"] * 1e3, r5["v2"]); ax[0].set_ylabel("V2 (V)"); ax[0].set_title("Dead-bus start with EPS voltage matching (D1 = n V2/V1)")
ax[1].plot(r5["t"] * 1e3, r5["ipk"]); ax[1].set_ylabel("|i_L| at period end (A)"); ax[1].set_xlabel("t (ms)")
[a.grid(alpha=0.3) for a in ax]; fig.tight_layout(); fig.savefig(os.path.join(HERE, "img", "sim_deadbus_start.png"), dpi=130); plt.close(fig)

json.dump(res, open(os.path.join(HERE, "switched_results.json"), "w"), indent=1)
print(json.dumps(res, indent=1))
