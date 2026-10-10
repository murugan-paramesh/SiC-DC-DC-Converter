#!/usr/bin/env python3
"""
Controller benchmark on the switched DAB plant (dabtools DABPlant, one update per period, command applied to
the next period).  Controllers: PI baseline (dabtools DABController), CCS-MPC, FCS-MPC, Explicit MPC (LUT from
build_explicit_mpc.py), Adaptive MPC (RLS on 1/L), Robust MPC (tightened for L in [0.8, 1.2] L_nom).
Scenarios: load step 10->100 %, 100->10 %, V1 step 800->700 V, power reversal +6.6->-6.6 kW, soft start from a
precharged link.  All with EPS voltage matching and the DC-bias-free transition modulator.
Also: modulator comparison (SPS / EPS / EPS + DC-free) for PI and CCS-MPC at 850/300 V, rate-weight sweep of the
CCS-MPC, operation counts and the C2000 WCET table.
Outputs results/benchmark_*.{csv,json,png}, results/c2000_feasibility.json.   Run time ~5-8 min on one core.
"""
import os, sys, json, math, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from dab_mpc_lib import *      # noqa
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import pandas as pd

T0 = time.time()
OUT = os.path.join(HERE, "results"); os.makedirs(OUT, exist_ok=True)
LUT = os.path.join(OUT, "empc_lut.npz")
if not os.path.exists(LUT):
    import subprocess; subprocess.run([sys.executable, os.path.join(HERE, "build_explicit_mpc.py")], check=True)
SCENARIOS = ["load_step_up", "load_step_down", "v1_step", "reversal", "soft_start"]
COLORS = {"PI": "#444444", "CCS-MPC": "#1f77b4", "FCS-MPC": "#ff7f0e", "Explicit-MPC": "#2ca02c", "Adaptive-MPC": "#9467bd", "Robust-MPC": "#d62728"}


def make_controllers():
    return [PIBaseline(), CCSMPC(), FCSMPC(), ExplicitMPC(LUT), AdaptiveMPC(), RobustMPC()]


rows = []; traces = {}
for scn in SCENARIOS:
    sc = make_scenario(scn)
    traces[scn] = {}
    for ctl in make_controllers():
        t = time.time()
        res = run_scenario(ctl, sc)
        mt = metrics(res, sc)
        mt.update(scenario=scn, controller=ctl.name, ops_total=ctl.ops().total, wall_s=time.time() - t)
        rows.append(mt); traces[scn][ctl.name] = res
        print(f"{scn:16s} {ctl.name:13s} settle {mt['settling_ms']:6.2f} ms  peak dev {mt['peak_dev_pct']:.3f} %  ITAE {mt['ITAE']:9.1f}  "
              f"Ipk {mt['i_peak_A']:5.2f} A  Irms {mt['i_rms_A']:5.2f} A  viol {mt['violations']}  ({mt['wall_s']:.0f} s)", flush=True)
df = pd.DataFrame(rows)
df.to_csv(os.path.join(OUT, "benchmark_metrics.csv"), index=False)

# ---------------------------------------------------------------- step-response figures
for scn in SCENARIOS:
    sc = make_scenario(scn)
    fig, ax = plt.subplots(3, 1, figsize=(9, 8.5), sharex=True)
    for name, res in traces[scn].items():
        tt = (res["t"] - sc["t_event"]) * 1e3
        if sc["mode"] == "CV":
            ax[0].plot(tt, res["v2"], color=COLORS[name], label=name, lw=1.0)
        else:
            ax[0].plot(tt, res["P"] / 1e3, color=COLORS[name], label=name, lw=1.0)
        ax[1].plot(tt, np.degrees(res["phi"]), color=COLORS[name], lw=1.0)
        ax[2].plot(tt, res["ipk"], color=COLORS[name], lw=1.0)
    res0 = next(iter(traces[scn].values())); tt = (res0["t"] - sc["t_event"]) * 1e3
    if sc["mode"] == "CV":
        ax[0].plot(tt, res0["ref"], "k--", lw=0.8, label="reference"); ax[0].set_ylabel("v2 (V)")
        if scn != "soft_start":
            ax[0].set_ylim(sc["v2_ref"] - 4, sc["v2_ref"] + 4)
    else:
        ax[0].plot(tt, res0["ref"] / 1e3, "k--", lw=0.8, label="reference"); ax[0].set_ylabel("P LV port (kW)")
    ax[2].axhline(I_LIM_PK, color="r", ls=":", lw=0.8); ax[2].text(0.98, 0.93, "24 A limit", transform=ax[2].transAxes, ha="right", fontsize=7, color="r")
    ax[1].set_ylabel("phi (deg)"); ax[2].set_ylabel("|i_L| peak per period (A)"); ax[2].set_xlabel("t - t_event (ms)")
    ax[0].legend(fontsize=7, ncol=4); ax[0].set_title(sc["title"] + " - switched plant, EPS matching + DC-free transitions")
    [a.grid(alpha=0.3) for a in ax]
    if scn in ("load_step_up", "load_step_down", "v1_step"):
        ax[0].set_xlim(-1, 6)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, f"benchmark_step_{scn}.png"), dpi=130); plt.close(fig)

# ---------------------------------------------------------------- bar charts
mets = [("peak_dev_pct", "peak deviation (%)"), ("settling_ms", "settling time to +/-1 V / 2 % (ms)"), ("ITAE", "ITAE (V ms^2 | W ms^2)"),
        ("i_peak_A", "peak inductor current (A, HV side)"), ("i_rms_A", "rms inductor current (A)"), ("ops_total", "operations per update")]
fig, axs = plt.subplots(2, 3, figsize=(14, 7))
names = [c.name for c in make_controllers()]
for ax, (key, lab) in zip(axs.ravel(), mets):
    w = 0.13
    for i, name in enumerate(names):
        vals = [df[(df.scenario == s) & (df.controller == name)][key].values[0] for s in SCENARIOS]
        vals = [0 if (isinstance(v, float) and math.isnan(v)) else v for v in vals]
        ax.bar(np.arange(len(SCENARIOS)) + (i - 2.5) * w, vals, w, color=COLORS[name], label=name)
    ax.set_xticks(range(len(SCENARIOS))); ax.set_xticklabels([s.replace("_", "\n") for s in SCENARIOS], fontsize=7)
    ax.set_title(lab, fontsize=9); ax.grid(alpha=0.3, axis="y")
    if key in ("ITAE", "ops_total"):
        ax.set_yscale("log")
axs[0, 0].legend(fontsize=7)
fig.suptitle("Benchmark metrics (settling time 0 = never left the band; reversal: power tracking, ITAE in W ms^2)")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "benchmark_metrics_bars.png"), dpi=130); plt.close(fig)

# ---------------------------------------------------------------- modulator comparison (PI, CCS) at 850/300 V
mod_rows = []
sc = make_scenario("load_step_up", v1=850.0, v2_ref=300.0)
fig, ax = plt.subplots(2, 1, figsize=(8.5, 6), sharex=True)
for mod, use_eps, dc in (("SPS", False, False), ("EPS", True, False), ("EPS + DC-free", True, True)):
    for ctl in (PIBaseline(use_eps=use_eps), CCSMPC(use_eps=use_eps)):
        res = run_scenario(ctl, sc, dc_free=dc)
        mt = metrics(res, sc); mt.update(modulator=mod, controller=ctl.name, scenario="load_step_up_850_300")
        # steady-state rms at full load (last 2 ms) and ZVS margin of the final operating point
        mt["i_rms_full_load_A"] = float(np.sqrt(np.mean(res["irms"][-200:] ** 2)))
        pt = pwl_period(res["v1"][-1], N_RATIO * res["v2"][-1], L_NOM, FS, res["phi"][-1], res["D"][-1, 0], res["D"][-1, 1])
        Imin1, Imin2 = zvs_i_min(res["v1"][-1], res["v2"][-1], L_NOM, N_RATIO)
        mt["zvs_margin_HV_A"] = float(pt["zvs1"][0] - Imin1); mt["zvs_margin_LV_A"] = float(pt["zvs2"][0] - Imin2)
        mod_rows.append(mt)
        ls = "-" if ctl.name == "PI" else "--"
        tt = (res["t"] - sc["t_event"]) * 1e3
        ax[0].plot(tt, res["v2"], ls, lw=1, label=f"{ctl.name} / {mod}"); ax[1].plot(tt, res["ipk"], ls, lw=1)
        print(f"modulator {mod:14s} {ctl.name:8s} peak dev {mt['peak_dev_pct']:.3f} %  Ipk {mt['i_peak_A']:5.2f}  Irms_FL {mt['i_rms_full_load_A']:5.2f}  "
              f"ZVS HV {mt['zvs_margin_HV_A']:+.2f} LV {mt['zvs_margin_LV_A']:+.2f}", flush=True)
ax[0].set_ylabel("v2 (V)"); ax[0].set_ylim(296, 302); ax[0].legend(fontsize=7, ncol=3); ax[0].set_title(sc["title"] + " - modulator comparison")
ax[1].set_ylabel("|i_L| peak per period (A)"); ax[1].set_xlabel("t - t_event (ms)"); ax[1].axhline(I_LIM_PK, color="r", ls=":", lw=0.8)
[a.grid(alpha=0.3) for a in ax]; ax[0].set_xlim(-1, 6)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "benchmark_modulators.png"), dpi=130); plt.close(fig)
pd.DataFrame(mod_rows).to_csv(os.path.join(OUT, "benchmark_modulators.csv"), index=False)

# ---------------------------------------------------------------- CCS rate-weight sweep (load step up, nominal)
sweep = []
sc = make_scenario("load_step_up")
for r in (2, 8, 16, 32, 128, 512):
    res = run_scenario(CCSMPC(r=r), sc); mt = metrics(res, sc); mt["r"] = r; sweep.append(mt)
    print(f"r = {r:4d}: peak dev {mt['peak_dev_pct']:.3f} %  settle {mt['settling_ms']:.2f} ms  Ipk {mt['i_peak_A']:.2f}  Irms {mt['i_rms_A']:.2f}", flush=True)
pi_row = df[(df.scenario == "load_step_up") & (df.controller == "PI")].iloc[0]
fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
ax[0].semilogx([s["r"] for s in sweep], [s["peak_dev_pct"] for s in sweep], "o-", label="CCS-MPC"); ax[0].axhline(pi_row["peak_dev_pct"], color="k", ls="--", label="PI")
ax[0].set_xlabel("rate weight r (rad^-2 V^2)"); ax[0].set_ylabel("peak deviation (%)"); ax[0].legend(); ax[0].grid(alpha=0.3)
ax[1].semilogx([s["r"] for s in sweep], [s["i_peak_A"] for s in sweep], "o-", label="peak"); ax[1].semilogx([s["r"] for s in sweep], [s["i_rms_A"] for s in sweep], "s-", label="rms")
ax[1].axhline(pi_row["i_peak_A"], color="k", ls="--", label="PI peak"); ax[1].axhline(pi_row["i_rms_A"], color="k", ls=":", label="PI rms")
ax[1].set_xlabel("rate weight r"); ax[1].set_ylabel("inductor current (A)"); ax[1].legend(fontsize=7); ax[1].grid(alpha=0.3)
fig.suptitle("CCS-MPC tuning trade-off, load step 10 -> 100 % (r = 16 used in the benchmark)"); fig.tight_layout()
fig.savefig(os.path.join(OUT, "benchmark_ccs_r_sweep.png"), dpi=130); plt.close(fig)
pd.DataFrame(sweep).to_csv(os.path.join(OUT, "benchmark_ccs_r_sweep.csv"), index=False)

# ---------------------------------------------------------------- compute cost and C2000 feasibility
meta = json.load(open(os.path.join(OUT, "empc_lut_meta.json")))
feas = dict(mcu="TMS320F28379D class (C28x + FPU32 + TMU, 200 MHz, 1 MB flash, 204 KB RAM)", isr_budget_us=10.0,
            cycles_per_op=CYCLES_PER_OP, isr_overhead_cycles=ISR_OVERHEAD_CYCLES,
            assumptions="single-issue compiled C, every FPU add/mul 2 cycles incl. load/store, TMU div/sqrt 8, compare+branch 4; "
                        "no hand-written assembly, no CLA offload; figures are L1 estimates - no toolchain or hardware available",
            controllers={})
variants = make_controllers() + [CCSMPC(N=5, K=10, name="CCS-MPC N=5 K=10"), CCSMPC(N=8, K=40, name="CCS-MPC N=8 K=40")]
for ctl in variants:
    ops = ctl.ops() + OPS_DCFREE
    cyc, us, frac = wcet_us(ops)
    row = dict(ops=dict(ops), ops_total=ops.total, wcet_cycles=int(cyc), wcet_us=round(us, 2), isr_fraction=round(frac, 3),
               fits_10us=bool(us < 10.0))
    sub = df[df.controller == ctl.name]
    if len(sub):
        row["python_us_mean"] = float(sub.compute_us_mean.mean()); row["python_us_max"] = float(sub.compute_us_max.max())
    feas["controllers"][ctl.name] = row
feas["memory"] = dict(explicit_lut_entries=meta["entries"], explicit_lut_kB_q15=round(meta["bytes_q15"] / 1024, 1),
                      explicit_lut_kB_float32=round(meta["bytes_float32"] / 1024, 1), lut_axes=meta["shape"],
                      ccs_mpc_state_bytes=4 * (8 + 2 + 4), note="LUT fits in flash or RAM of the F28379D; interpolation needs 8 reads")
feas["sampling"] = {
    "v1, v2": "every period (100 kHz), 12-bit, synchronous with the EPWM period event; 0.25 / 0.12 V LSB",
    "i2 period average": "integrating sample (two ADC samples per period averaged, or hardware oversampling) at 100 kHz - needed by the observer-based MPCs and the RLS; the PI baseline does not need it",
    "i_L peak": "CT + peak detector (existing design) at 100 kHz for protection; not used by the controllers",
    "temperature": "1 kHz is sufficient (derating only)",
    "RLS": "can run decimated at 10 kHz (every 10th period) - its 1/L estimate changes slowly"}
feas["fallback_logic"] = {
    "default": "explicit MPC (LUT) when all plausibility checks pass",
    "switch_to_PI_if": ["|d_hat| > 1.3 P_rated / v2 for > 10 periods (observer diverged)",
                        "LUT inputs outside the table range for > 10 periods (e, V1 or P_hat)",
                        "RLS estimate 1/L outside [1/(1.3 L_nom), 1/(0.7 L_nom)] or P covariance not decreasing after 1000 updates",
                        "|v2 - v2_ref| > 5 % for > 2 ms (the LUT law should have settled in < 1 ms)",
                        "ISR overrun flag (EPWM period event before the previous ISR finished)"],
    "switch_back": "manual / supervisory only, after 100 ms in RUN with the PI and consistent estimates",
    "deterministic": "PI and LUT paths are both fixed-iteration; the hand-over keeps the current phi and pre-loads the PI integrator "
                     "with P = d_hat * v2 so the output is continuous"}
json.dump(feas, open(os.path.join(OUT, "c2000_feasibility.json"), "w"), indent=1)
for k, v in feas["controllers"].items():
    print(f"WCET {k:20s} {v['ops_total']:6d} ops  {v['wcet_cycles']:6d} cycles  {v['wcet_us']:6.2f} us  {100*v['isr_fraction']:6.1f} % of ISR")

summary = dict(scenarios=SCENARIOS, controllers=names, N_sub=N_SUB, dc_free=True, metrics=rows, modulators=mod_rows, r_sweep=sweep)
json.dump(summary, open(os.path.join(OUT, "benchmark_summary.json"), "w"), indent=1, default=float)
write_provenance(HERE, "run_benchmarks.py", T0, [DESIGN_FILE, CONTROL_FILE, os.path.join(HERE, "dab_mpc_lib.py"), LUT,
                                                   os.path.join(PROJ, "dabtools", "dab", "sim_switched.py"), os.path.join(PROJ, "dabtools", "dab", "control.py")],
                 extra=dict(outputs=sorted(f for f in os.listdir(OUT) if f.startswith("benchmark_") or f.startswith("c2000"))))
print(f"done in {time.time()-T0:.0f} s")
