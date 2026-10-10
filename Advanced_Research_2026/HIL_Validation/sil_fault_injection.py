#!/usr/bin/env python3
"""
Automated fault-injection test suite - SOFTWARE in the loop (SIL, L3). HIL is PROPOSED only (see README).

Plant: dabtools.dab.sim_switched.DABPlant (switched model, 200 sub-steps per period); controller: dabtools.dab.control.DABController
(Python reference of the C control core). Between them this harness emulates the real sensing chain and the hardware protection
path of 07_KiCad_Schematics/sensing_protection.kicad_sch:
    true quantity -> isolated amplifier chain (gain/offset fault, output saturation) -> [HW comparators: OV 920 V / 490 V, OC 32 A]
                  -> ADC (12 bit, noise) -> controller measurement dict
The HW comparators sit on the same single-ended signals as the ADC (V1_SE / V2_SE / I_L), so a sensor-chain fault affects
both paths (common cause), while ADC noise/quantisation affects only the firmware path. A latched hardware trip forces the
gates off and (as the C code does on hw_trip) puts the controller into FAULT; the Python reference lacks the hw_trip input,
so the harness applies it. Trip granularity is one switching period (the plant has no intra-period event detection).
Each test has an explicit pass criterion; a test that FAILS documents a design weakness, it is not hidden.
Deterministic: numpy seed 20261012.  Outputs: results/sil_results.csv, sil_results.json, sil_results.md, fig_sil_traces.png, provenance.json
"""
import os, sys, json, time, hashlib, platform, math, csv
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE)); DAB = os.path.join(REPO, "SiC_6k6_Industrial_DAB")
sys.path.insert(0, DAB)
from dabtools.dab.sim_switched import DABPlant  # noqa: E402
from dabtools.dab.control import DABController  # noqa: E402
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt  # noqa: E402
RES = os.path.join(HERE, "results"); os.makedirs(RES, exist_ok=True); T0 = time.time(); SEED = 20261012
V = json.load(open(os.path.join(DAB, "04_Design_Calculations", "design_values.json"))); CP = json.load(open(os.path.join(DAB, "11_Control_Algorithms", "control_params.json")))
L, n, fs, P = V["L"], V["spec"]["n"], V["spec"]["fs"], V["spec"]["P"]
C1, C2 = V["dclink"]["C1"] + 500e-6, V["dclink"]["C2"] + 1000e-6
R_full = 400 ** 2 / P
HW = dict(v1_ov=920.0, v2_ov=490.0, i_oc=32.0)                          # hardware comparator thresholds (15.1 section 6)
FS = dict(v1=1000.0, v2=500.0, i_pk=40.0)                               # ADC / amplifier full scale per hal_adc_read and the AMC1301 ranges
LSB = {k: v / 4096 for k, v in FS.items()}


class Chain:
    """Sensing-chain model with injectable faults. gain/offset act on the amplifier output (shared by HW and FW); fail/clip likewise."""
    def __init__(self, rng):
        self.rng = rng; self.gain = dict(v1=1.0, v2=1.0, i_pk=1.0); self.offset = dict(v1=0.0, v2=0.0, i_pk=0.0)
        self.fail = dict(v1=None, v2=None, i_pk=None); self.noise_lsb = 0.0; self.quantise = False; self.clip = dict(v1=FS["v1"], v2=FS["v2"], i_pk=FS["i_pk"])
        self.T = 40.0; self.comm_ok = True; self.precharge_ok = True
    def analog(self, true):
        a = {}
        for k in ("v1", "v2", "i_pk"):
            x = true[k] * self.gain[k] + self.offset[k]
            if self.fail[k] is not None: x = self.fail[k]
            a[k] = float(np.clip(x, 0.0, self.clip[k]))
        return a
    def adc(self, a):
        m = {}
        for k in ("v1", "v2", "i_pk"):
            x = a[k] + self.rng.normal(0.0, self.noise_lsb * LSB[k]) if self.noise_lsb > 0 else a[k]
            if self.quantise: x = round(x / LSB[k]) * LSB[k]
            m[k] = float(np.clip(x, 0.0, FS[k]))
        m["T"] = self.T; m["comm_ok"] = self.comm_ok; m["precharge_ok"] = self.precharge_ok
        return m


def controller():
    c = DABController(L, n, fs, CP["kp"], CP["ki"], P_max=1.1 * P)
    c.phi_dead_comp = 0.5 * 2 * math.pi * fs * V["t_dead"]
    return c


def run(periods, load_fn, chain, v1_fn=lambda t: 800.0, v2_init=380.0, inject=lambda t, ch, pl: None, enable_fn=lambda t: True):
    plant = DABPlant(L, n, fs, C1, C2, 800.0, 0.3, load_fn, N_sub=200); plant.v2 = v2_init
    ctl = controller(); hw_trip = None
    log = dict(t=[], v1=[], v2=[], v2_meas=[], ipk=[], phi=[], state=[], gates=[])
    for k in range(periods):
        t = plant.t; plant.V1_src = v1_fn(t); inject(t, chain, plant)
        true = dict(v1=plant.v1, v2=plant.v2, i_pk=plant.ipk)
        a = chain.analog(true)
        if hw_trip is None and (a["v1"] > HW["v1_ov"] or a["v2"] > HW["v2_ov"] or a["i_pk"] > HW["i_oc"]):
            hw_trip = ("V1_OV_HW" if a["v1"] > HW["v1_ov"] else "V2_OV_HW" if a["v2"] > HW["v2_ov"] else "OC_HW", t)
        m = chain.adc(a)
        if hw_trip is not None and ctl.state != "FAULT":
            ctl.state, ctl.fault = "FAULT", "HW_TRIP"            # emulates the C core's hw_trip input
        phi, D1, D2 = ctl.step(m, enable=enable_fn(t))
        gates = ctl.state in ("SOFTSTART", "RUN") and hw_trip is None
        if not gates: phi, D1, D2 = 0.0, 1.0, 1.0
        if gates:
            plant.run_period(phi, D1, D2)
        else:                                                   # gates off: the LV link just discharges into the load, HV link follows the source
            dt = 1 / fs
            plant.v2 += -load_fn(plant.v2, plant.t) / C2 * dt; plant.v1 += (plant.V1_src - plant.v1) / 0.3 / C1 * dt
            plant.v1 = min(plant.v1, plant.V1_src) if plant.V1_src >= plant.v1 else max(plant.v1, plant.V1_src)
            plant.iL = 0.0; plant.ipk = 0.0; plant.t += dt
        for key, val in (("t", plant.t), ("v1", plant.v1), ("v2", plant.v2), ("v2_meas", m["v2"]), ("ipk", plant.ipk), ("phi", math.degrees(phi)), ("state", ctl.state), ("gates", gates)):
            log[key].append(val)
    for key in ("t", "v1", "v2", "v2_meas", "ipk", "phi"): log[key] = np.array(log[key])
    return log, ctl, hw_trip


def first_time(log, pred):
    idx = [i for i, s in enumerate(log["state"]) if pred(i)]
    return float(log["t"][idx[0]]) if idx else None


TESTS = []
def test(tid, name, category, criterion):
    def deco(fn):
        TESTS.append((tid, name, category, criterion, fn)); return fn
    return deco


def std_load(v2, t): return v2 / R_full


@test("T01", "baseline start-up and regulation", "reference", "RUN without fault; |v2 - 400| < 4 V for t > 70 ms")
def t01(rng):
    ch = Chain(rng); log, ctl, hw = run(9000, std_load, ch)
    seg = log["v2"][log["t"] > 0.07]
    return dict(passed=ctl.state == "RUN" and ctl.fault is None and np.all(np.abs(seg - 400) < 4), fault=ctl.fault, hw=hw, v2_end=float(log["v2"][-1]), v2_dev_max=float(np.abs(seg - 400).max())), log


@test("T02", "V2 sensor gain +5 % (AMC1301 chain)", "sensor gain fault", "no trip (undetectable by design); true v2 = 400/1.05 within 1 %; true v2 <= 480 V")
def t02(rng):
    ch = Chain(rng); ch.gain["v2"] = 1.05; log, ctl, hw = run(9000, std_load, ch)
    v2 = float(log["v2"][-1]); return dict(passed=ctl.fault is None and abs(v2 - 400 / 1.05) < 4 and log["v2"].max() <= 480, fault=ctl.fault, hw=hw, v2_true_end=v2, v2_true_max=float(log["v2"].max())), log


@test("T03", "V2 sensor gain -20 % at 60 ms (AMC1301 chain, common cause for FW + HW OV)", "sensor gain fault", "true v2 must stay <= 480 V (LIM_V2_OV) or a trip must occur")
def t03(rng):
    ch = Chain(rng)
    def inj(t, c, p):
        if t >= 0.06: c.gain["v2"] = 0.80
    log, ctl, hw = run(12000, std_load, ch, inject=inj)
    v2max = float(log["v2"].max()); return dict(passed=(v2max <= 480) or ctl.fault is not None or hw is not None, fault=ctl.fault, hw=hw, v2_true_max=v2max, v2_meas_end=float(log["v2_meas"][-1])), log


@test("T04", "V2 sensor offset -30 V at 60 ms", "sensor offset fault", "true v2 <= 480 V or trip; report true v2")
def t04(rng):
    ch = Chain(rng)
    def inj(t, c, p):
        if t >= 0.06: c.offset["v2"] = -30.0
    log, ctl, hw = run(10000, std_load, ch, inject=inj)
    v2max = float(log["v2"].max()); return dict(passed=(v2max <= 480) or ctl.fault is not None or hw is not None, fault=ctl.fault, hw=hw, v2_true_max=v2max), log


@test("T05", "V2 sensor fail-low (reads 0 V) at 60 ms in RUN", "sensor failure", "FAULT = V2_UV within 2 periods of the fault, gates off")
def t05(rng):
    ch = Chain(rng)
    def inj(t, c, p):
        if t >= 0.06: c.fail["v2"] = 0.0
    log, ctl, hw = run(8000, std_load, ch, inject=inj)
    tf = first_time(log, lambda i: log["state"][i] == "FAULT"); return dict(passed=ctl.fault == "V2_UV" and tf is not None and tf - 0.06 <= 2.5 / fs and not log["gates"][-1], fault=ctl.fault, hw=hw, t_fault_ms=None if tf is None else 1e3 * tf, delay_periods=None if tf is None else round((tf - 0.06) * fs)), log


@test("T06", "V1 sensor fail-high (reads 1000 V = full scale) at 60 ms", "sensor failure", "FAULT = V1_OV within 2 periods; HW OV comparator also trips (same signal)")
def t06(rng):
    ch = Chain(rng)
    def inj(t, c, p):
        if t >= 0.06: c.fail["v1"] = 1000.0
    log, ctl, hw = run(8000, std_load, ch, inject=inj)
    tf = first_time(log, lambda i: log["state"][i] == "FAULT"); return dict(passed=ctl.fault in ("V1_OV", "HW_TRIP") and tf is not None and tf - 0.06 <= 2.5 / fs, fault=ctl.fault, hw=hw, delay_periods=None if tf is None else round((tf - 0.06) * fs)), log


@test("T07", "real HV bus over-voltage: V1 source ramps 800 -> 960 V from 60 ms at 40 V/ms", "bus overvoltage", "firmware FAULT V1_OV within 1 period of v1 > 900 V and before the HW comparator (920 V) is needed")
def t07(rng):
    ch = Chain(rng); log, ctl, hw = run(9000, std_load, ch, v1_fn=lambda t: 800.0 if t < 0.06 else min(960.0, 800.0 + 40e3 * (t - 0.06)))
    t900 = first_time(log, lambda i: log["v1"][i] > 900); tf = first_time(log, lambda i: log["state"][i] == "FAULT")
    return dict(passed=ctl.fault == "V1_OV" and tf is not None and t900 is not None and tf - t900 <= 1.5 / fs, fault=ctl.fault, hw=hw, v1_at_fault=None if tf is None else float(log["v1"][np.searchsorted(log["t"], tf)]), delay_periods=None if (tf is None or t900 is None) else round((tf - t900) * fs)), log


@test("T08", "LV load short (0.1 Ohm) at 60 ms", "load short", "a trip occurs within 20 periods of the short; i_pk stays below the 32 A hardware limit (phi_max / EPS limiting); gates off")
def t08(rng):
    ch = Chain(rng); log, ctl, hw = run(8000, lambda v2, t: v2 / R_full if t < 0.06 else v2 / 0.1, ch)
    tf = first_time(log, lambda i: log["state"][i] == "FAULT")
    return dict(passed=tf is not None and tf - 0.06 <= 20.5 / fs and log["ipk"].max() < 32 and not log["gates"][-1], fault=ctl.fault, hw=hw, ipk_max=float(log["ipk"].max()), trip_delay_periods=None if tf is None else round((tf - 0.06) * fs)), log


@test("T09", "communication loss (heartbeat) at 60 ms", "communication loss", "FAULT = COMM within 1 period, gates off")
def t09(rng):
    ch = Chain(rng)
    def inj(t, c, p):
        if t >= 0.06: c.comm_ok = False
    log, ctl, hw = run(7000, std_load, ch, inject=inj)
    tf = first_time(log, lambda i: log["state"][i] == "FAULT"); return dict(passed=ctl.fault == "COMM" and tf is not None and tf - 0.06 <= 1.5 / fs and not log["gates"][-1], fault=ctl.fault, hw=hw, delay_periods=None if tf is None else round((tf - 0.06) * fs)), log


@test("T10", "isolated-amplifier saturation: V2 chain clips at 500 V while an external source pulls the LV link to 520 V", "amplifier saturation", "FAULT V2_OV (clip level 500 V is above LIM_V2_OV 480 V: 4 % margin)")
def t10(rng):
    ch = Chain(rng); ch.clip["v2"] = 500.0
    log, ctl, hw = run(8000, lambda v2, t: v2 / R_full if t < 0.06 else (v2 - 520.0) / 0.1, ch)
    return dict(passed=ctl.fault in ("V2_OV", "HW_TRIP"), fault=ctl.fault, hw=hw, v2_meas_max=float(log["v2_meas"].max()), v2_true_max=float(log["v2"].max()), margin_pct=100 * (500 - 480) / 480), log


@test("T11", "current-sense saturation: CT/ADC clips at 40 A FS during a load short", "amplifier saturation", "trip still occurs (40 A FS > 32 A trip): report clipped reading")
def t11(rng):
    ch = Chain(rng); ch.clip["i_pk"] = 40.0; log, ctl, hw = run(8000, lambda v2, t: v2 / R_full if t < 0.06 else v2 / 0.1, ch)
    return dict(passed=ctl.state == "FAULT" and not log["gates"][-1], fault=ctl.fault, hw=hw, ipk_true_max=float(log["ipk"].max())), log


@test("T12", "ADC quantisation (12 bit) + noise 2 LSB rms on all channels", "ADC noise", "no fault in 100 ms; v2 std < 1 %, |mean - 400| < 1 % (t > 70 ms)")
def t12(rng):
    ch = Chain(rng); ch.quantise = True; ch.noise_lsb = 2.0; log, ctl, hw = run(10000, std_load, ch)
    seg = log["v2"][log["t"] > 0.07]; return dict(passed=ctl.fault is None and hw is None and seg.std() < 4 and abs(seg.mean() - 400) < 4, fault=ctl.fault, hw=hw, v2_std=float(seg.std()), v2_mean=float(seg.mean())), log


@test("T13", "ADC noise 1 % of full scale rms (41 LSB) on all channels", "ADC noise", "no false trip at the nominal point; v2 deviation < 2 %")
def t13(rng):
    ch = Chain(rng); ch.quantise = True; ch.noise_lsb = 41.0; log, ctl, hw = run(10000, std_load, ch)
    seg = log["v2"][log["t"] > 0.07]; return dict(passed=ctl.fault is None and hw is None and np.abs(seg - 400).max() < 8, fault=ctl.fault, hw=hw, v2_dev_max=float(np.abs(seg - 400).max()), v2_std=float(seg.std())), log


@test("T14", "HV bus dip to 580 V (below LIM_V1_UV = 600 V) for 20 ms in RUN", "bus undervoltage", "FAULT = V1_UV (documented behaviour: UV is a fault in RUN)")
def t14(rng):
    ch = Chain(rng); log, ctl, hw = run(9000, std_load, ch, v1_fn=lambda t: 580.0 if 0.06 <= t < 0.08 else 800.0)
    return dict(passed=ctl.fault == "V1_UV", fault=ctl.fault, hw=hw), log


@test("T15", "HV bus dip 10 % (720 V) for 20 ms in RUN", "bus dip", "no fault; v2 deviation < 3 % (EL-10 class)")
def t15(rng):
    ch = Chain(rng); log, ctl, hw = run(11000, std_load, ch, v1_fn=lambda t: 720.0 if 0.06 <= t < 0.08 else 800.0)
    seg = log["v2"][(log["t"] > 0.06) & (log["t"] < 0.1)]; return dict(passed=ctl.fault is None and np.abs(seg - 400).max() < 12, fault=ctl.fault, hw=hw, v2_dev_max=float(np.abs(seg - 400).max())), log


@test("T16", "enable removed during RUN at 60 ms", "enable interlock", "state INIT within 1 period, gates off, phi = 0")
def t16(rng):
    ch = Chain(rng); log, ctl, hw = run(7000, std_load, ch, enable_fn=lambda t: t < 0.06)
    ti = first_time(log, lambda i: log["t"][i] > 0.06 and log["state"][i] == "INIT"); return dict(passed=ti is not None and ti - 0.06 <= 1.5 / fs and not log["gates"][-1] and log["phi"][-1] == 0.0, fault=ctl.fault, hw=hw, state_end=ctl.state), log


@test("T17", "precharge feedback never true", "enable interlock", "gates never enabled for the whole run (Python reference stays in PRECHARGE_WAIT; the C core would FAULT after 5 s - discrepancy documented in Reliability_Engineering)")
def t17(rng):
    ch = Chain(rng); ch.precharge_ok = False; log, ctl, hw = run(3000, std_load, ch)
    return dict(passed=not any(log["gates"]) and ctl.state == "PRECHARGE_WAIT", fault=ctl.fault, hw=hw, state_end=ctl.state), log


@test("T18", "heatsink NTC reads 110 C at 60 ms (sensor short or real over-temperature)", "over-temperature", "FAULT = OT within 1 period")
def t18(rng):
    ch = Chain(rng)
    def inj(t, c, p):
        if t >= 0.06: c.T = 110.0
    log, ctl, hw = run(7000, std_load, ch, inject=inj)
    tf = first_time(log, lambda i: log["state"][i] == "FAULT"); return dict(passed=ctl.fault == "OT" and tf is not None and tf - 0.06 <= 1.5 / fs, fault=ctl.fault, hw=hw, delay_periods=None if tf is None else round((tf - 0.06) * fs)), log


@test("T19", "i_pk sensor stuck low (CT open, reads 0) during a load short at 60 ms", "sensor failure", "documents the single-point CT: no I_PK trip expected; pass only if some trip occurs or i_pk stays < 40 A")
def t19(rng):
    ch = Chain(rng)
    def inj(t, c, p):
        if t >= 0.055: c.fail["i_pk"] = 0.0
    log, ctl, hw = run(7000, lambda v2, t: v2 / R_full if t < 0.06 else v2 / 0.1, ch, inject=inj)
    return dict(passed=(ctl.state == "FAULT") or (log["ipk"].max() < 40), fault=ctl.fault, hw=hw, ipk_true_max=float(log["ipk"].max())), log


def main():
    rows = []; logs = {}
    for tid, name, cat, crit, fn in TESTS:
        rng = np.random.default_rng(SEED + int(tid[1:])); t1 = time.time()
        r, log = fn(rng); logs[tid] = log
        r = {k: (None if v is None else (v if not isinstance(v, (np.floating, np.bool_)) else v.item())) for k, v in r.items()}
        r["hw"] = None if r["hw"] is None else f"{r['hw'][0]} at {1e3*r['hw'][1]:.2f} ms"
        rows.append(dict(id=tid, name=name, category=cat, criterion=crit, result="PASS" if r.pop("passed") else "FAIL", details=r, wall_s=round(time.time() - t1, 1)))
        print(f"{tid} {rows[-1]['result']:4s} {name} :: {r}")
    n_pass = sum(r["result"] == "PASS" for r in rows)
    json.dump(dict(seed=SEED, n_tests=len(rows), n_pass=n_pass, n_fail=len(rows) - n_pass, hw_thresholds=HW, full_scale=FS, tests=rows), open(os.path.join(RES, "sil_results.json"), "w"), indent=1)
    with open(os.path.join(RES, "sil_results.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["id", "name", "category", "criterion", "result", "details"])
        for r in rows: w.writerow([r["id"], r["name"], r["category"], r["criterion"], r["result"], json.dumps(r["details"])])
    md = [f"# SIL fault-injection results: {n_pass} / {len(rows)} PASS (seed {SEED})\n", "| id | test | category | pass criterion | result | key values |", "|---|---|---|---|---|---|"]
    for r in rows:
        kv = ", ".join(f"{k}={v:.3g}" if isinstance(v, float) else f"{k}={v}" for k, v in r["details"].items() if v is not None)
        md.append(f"| {r['id']} | {r['name']} | {r['category']} | {r['criterion']} | **{r['result']}** | {kv} |")
    open(os.path.join(RES, "sil_results.md"), "w").write("\n".join(md) + "\n")
    fig, ax = plt.subplots(3, 3, figsize=(14, 9))
    for a, tid in zip(ax.ravel(), ("T01", "T03", "T05", "T07", "T08", "T10", "T12", "T13", "T16")):
        lg = logs[tid]; a.plot(lg["t"] * 1e3, lg["v2"], label="v2 true"); a.plot(lg["t"] * 1e3, lg["v2_meas"], lw=0.6, alpha=0.7, label="v2 measured")
        a2 = a.twinx(); a2.plot(lg["t"] * 1e3, lg["ipk"], "r", lw=0.6, alpha=0.6); a2.set_ylabel("i_pk (A)", color="r")
        a.set_title(f"{tid}: {[t for t in TESTS if t[0]==tid][0][1][:48]}", fontsize=8); a.set_xlabel("ms"); a.set_ylabel("V"); a.grid(alpha=0.3); a.legend(fontsize=6)
    fig.suptitle("SIL fault injection (Python plant + Python reference controller + sensing/HW-trip emulation) - not HIL"); fig.tight_layout()
    fig.savefig(os.path.join(RES, "fig_sil_traces.png"), dpi=120); plt.close(fig)
    print(f"\n{n_pass}/{len(rows)} PASS, wall {time.time()-T0:.0f} s")
    import numpy, matplotlib as mpl
    def hs(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
    head = open(os.path.join(REPO, ".git", "HEAD")).read().strip(); commit = head
    if head.startswith("ref:"):
        rp = os.path.join(REPO, ".git", head[5:]); commit = open(rp).read().strip() if os.path.exists(rp) else head
    json.dump(dict(script="sil_fault_injection.py", python=platform.python_version(), numpy=numpy.__version__, matplotlib=mpl.__version__, git_commit=commit, seed=SEED, wall_time_s=round(time.time() - T0, 1),
                   inputs={os.path.relpath(f, REPO): hs(f) for f in [os.path.join(DAB, "dabtools", "dab", "sim_switched.py"), os.path.join(DAB, "dabtools", "dab", "control.py"),
                                                                     os.path.join(DAB, "04_Design_Calculations", "design_values.json"), os.path.join(DAB, "11_Control_Algorithms", "control_params.json")]},
                   outputs=sorted(os.listdir(RES))), open(os.path.join(RES, "provenance.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
