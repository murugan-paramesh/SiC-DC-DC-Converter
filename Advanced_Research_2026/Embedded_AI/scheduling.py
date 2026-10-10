#!/usr/bin/env python3
"""
Scheduling proposal for the DAB control firmware on an F28379D-class C2000: which computation runs in the 100 kHz
EPWM ISR, which in the 10 kHz / 1 kHz periodic tasks and which in the background loop, with the WCET estimates of
embedded_inference.py / Adaptive_MPC (L1, instruction-count based).  Draws the timing diagram
results/scheduling_timing.png and writes results/scheduling.json.  Run time < 5 s.
"""
import os, sys, json, time
import numpy as np
EMB_DIR = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, EMB_DIR)
MPC_DIR = os.path.join(os.path.dirname(EMB_DIR), "Adaptive_MPC"); sys.path.insert(0, MPC_DIR)
from dab_mpc_lib import write_provenance, DESIGN_FILE, CONTROL_FILE   # noqa
HERE = EMB_DIR
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

T0 = time.time()
OUT = os.path.join(HERE, "results"); os.makedirs(OUT, exist_ok=True)
rep_path = os.path.join(OUT, "embedded_report.json")
wc = json.load(open(rep_path))["wcet"]["paths"] if os.path.exists(rep_path) else {}
us = lambda k, default: wc[k]["us"] if k in wc else default

# ISR (every 10 us) ------------------------------------------------------------------------------------------------
isr = [("context save + ADC results (v1, v2, i2 avg, i_pk)", 0.5),
       ("protection / state machine", 0.25),
       ("disturbance observer (v2, d_hat) + i2 mismatch", 0.2),
       ("explicit-MPC LUT (Q15 trilinear)", us("explicit LUT Q15 trilinear (3 in, 1 out)", 0.9)),
       ("analytic inverse + EPS matching (CP / fallback PI path)", us("analytic SPS inverse + EPS matching (float)", 0.6)),
       ("DC-free transition (edge move) + EPWM shadow writes", 0.5),
       ("fallback-selection checks + context restore", 0.3)]
isr_total = sum(d for _, d in isr)
# 10 kHz task (every 10th period, lower priority, pre-empted by the ISR) ---------------------------------------------
t10k = [("RLS update of 1/L (pwl regressor, 1 scalar RLS step)", 2.5),
        ("i_L peak / ZVS-margin estimate from the pwl model (one evaluation)", 1.5)]
# 1 kHz task ---------------------------------------------------------------------------------------------------------
t1k = [("L_hat validation, LUT input rescaling (P_hat * L_hat/L_nom), fallback decision", 2.0),
       ("adaptive dead-time table look-up (t_d from predicted edge currents)", 1.0),
       ("thermal derating / temperature sampling", 0.5),
       ("telemetry frame assembly", 2.0)]
bg = ["CAN / SCI communication, command parser", "logging, fault log", "no on-line learning: all training and table generation off-line"]

sched = dict(isr_100kHz=dict(items=[dict(task=t, us=d) for t, d in isr], total_us=round(isr_total, 2), budget_us=10.0,
                             fraction=round(isr_total / 10.0, 3), note="float32 path for the inverse/EPS/observer, Q15 for the LUT"),
             task_10kHz=dict(items=[dict(task=t, us=d) for t, d in t10k], total_us=sum(d for _, d in t10k), period_us=100.0),
             task_1kHz=dict(items=[dict(task=t, us=d) for t, d in t1k], total_us=sum(d for _, d in t1k), period_us=1000.0),
             background=bg,
             cpu_load_estimate=round(isr_total / 10.0 + sum(d for _, d in t10k) / 100.0 + sum(d for _, d in t1k) / 1000.0, 3),
             not_in_isr=["on-line QP (CCS-MPC, >= 10.5 us even at N = 5, K = 10)", "FCS-MPC candidate enumeration (~100 us)",
                         "MLP inference (~12-13 us for 3-16-16-3)"],
             maturity="L1 - instruction-count estimates, no C2000 toolchain or hardware; ISR entry/exit and ADC latency taken from the "
                      "F2837x TRM typical figures (not measured)")
json.dump(sched, open(os.path.join(OUT, "scheduling.json"), "w"), indent=1)

# timing diagram over 100 us (10 ISR periods) ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(12, 4.2))
colors = plt.cm.tab10(np.linspace(0, 1, 10))
y_isr, y_10k, y_1k, y_bg = 3, 2, 1, 0
for k in range(10):
    t0 = k * 10.0
    for i, (name, d) in enumerate(isr):
        ax.broken_barh([(t0, d)], (y_isr - 0.35, 0.7), color=colors[i], label=name if k == 0 else None)
        t0 += d
# the 10 kHz task starts after ISR 0 and is pre-empted by the following ISRs
remaining = sum(d for _, d in t10k); t = isr_total; segs = []
while remaining > 1e-9:
    free = 10.0 - (t % 10.0)
    seg = min(free, remaining); segs.append((t, seg)); remaining -= seg; t += seg
    if remaining > 1e-9:
        t = (t // 10.0 + 1) * 10.0 + isr_total
ax.broken_barh(segs, (y_10k - 0.35, 0.7), color="#8c564b", label="10 kHz task (RLS, ZVS estimate)")
# 1 kHz task: one slot every 1 ms -> shown once (hatched) in this 100 us window as 'one of ten 100-us windows'
ax.broken_barh([(20.0 + isr_total, 5.5)], (y_1k - 0.35, 0.7), color="#17becf", hatch="//", label="1 kHz task (one slice per ms; shown once)")
ax.broken_barh([(x, 10.0 - isr_total) for x in np.arange(isr_total, 100, 10.0)], (y_bg - 0.35, 0.7), color="#dddddd", label="background (comms, logging)")
for k in range(11):
    ax.axvline(k * 10.0, color="k", lw=0.5, ls=":")
ax.set_yticks([y_bg, y_1k, y_10k, y_isr]); ax.set_yticklabels(["background", "1 kHz task", "10 kHz task", "100 kHz ISR"])
ax.set_xlabel("time (us) - 10 switching periods"); ax.set_xlim(0, 100)
ax.set_title(f"Proposed schedule: ISR {isr_total:.1f} us of 10 us ({100*isr_total/10:.0f} %), CPU load estimate {100*sched['cpu_load_estimate']:.0f} % (L1 estimates)")
ax.legend(fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=3)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "scheduling_timing.png"), dpi=130, bbox_inches="tight"); plt.close(fig)
write_provenance(HERE, "scheduling.py", T0, [DESIGN_FILE, CONTROL_FILE] + ([rep_path] if os.path.exists(rep_path) else []),
                 extra=dict(outputs=["results/scheduling.json", "results/scheduling_timing.png"]))
print(json.dumps({k: v for k, v in sched.items() if k in ("cpu_load_estimate",)}), "ISR total us", isr_total)
print(f"done in {time.time()-T0:.1f} s")
