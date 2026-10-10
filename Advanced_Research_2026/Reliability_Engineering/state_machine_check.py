#!/usr/bin/env python3
"""
Formal check of the DAB controller state machine (10_Firmware/src/dab_control.c) by exhaustive enumeration.

1. The state machine is extracted into an explicit Python transition model (states INIT, PRECHARGE_WAIT, SOFTSTART,
   RUN, FAULT; 13 abstract boolean inputs; the two timers are abstracted as 'done' inputs).
2. Model checking: BFS over the reachable states x all 2^13 input combinations (minus physically inconsistent ones);
   properties checked on EVERY transition:
     P1  every fault input leads to FAULT within one step (literal reading)
     P1' every fault input leads to FAULT within one step under the documented conditions (UV only in RUN,
         comm loss not in INIT, precharge timeout only in PRECHARGE_WAIT)
     P2  FAULT is only left by an explicit clear command
     P3  gates_enabled is false in every state other than RUN / SOFTSTART (and false whenever a fault was detected)
     P4  no deadlock: every reachable state has a successor, RUN is reachable from every state, INIT reachable from FAULT
     P5  gates_enabled implies enable is true
3. Conformance: the SAME enumeration is run through the unmodified C code (sm_conformance.c, compiled with gcc into
   the scratch directory) and through the Python reference controller (dabtools/dab/control.py); every mismatch is reported.
4. The existing SIL harness (10_Firmware/sil/sil_main.c) is compiled and run from a scratch directory (it writes
   sil/sil_results.csv relative to its cwd); its PASS/FAIL lines are recorded. The firmware tree is not modified.
Outputs: results/state_machine_results.json, state_machine_report.md, sil_harness_output.txt, provenance_sm.json
"""
import os, sys, json, time, hashlib, platform, subprocess, tempfile, itertools
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE)); DAB = os.path.join(REPO, "SiC_6k6_Industrial_DAB")
FW = os.path.join(DAB, "10_Firmware"); RES = os.path.join(HERE, "results"); os.makedirs(RES, exist_ok=True); T0 = time.time()
sys.path.insert(0, DAB)
from dabtools.dab.control import DABController  # noqa: E402

STATES = ["INIT", "PRECHARGE_WAIT", "SOFTSTART", "RUN", "FAULT"]
BITS = ["enable", "precharge_ok", "v1_low", "v2_low", "v1_ov", "v2_ov", "ipk_over", "ot", "driver_fault", "hw_trip", "comm_lost", "ss_done", "pc_timeout"]
FAULT_BITS = ["v1_low", "v2_low", "v1_ov", "v2_ov", "ipk_over", "ot", "driver_fault", "hw_trip", "comm_lost", "pc_timeout"]
UNCONDITIONAL = ["hw_trip", "driver_fault", "v1_ov", "v2_ov", "ipk_over", "ot"]


def inputs():
    for mask in range(1 << len(BITS)):
        d = {b: bool((mask >> i) & 1) for i, b in enumerate(BITS)}
        if (d["v1_low"] and d["v1_ov"]) or (d["v2_low"] and d["v2_ov"]):
            continue
        yield mask, d


def check_protection(state, d):
    """Mirror of check_protection() in dab_control.c, same priority order."""
    if d["hw_trip"]: return "HW_TRIP"
    if d["driver_fault"]: return "DRIVER"
    if d["v1_ov"]: return "V1_OV"
    if d["v2_ov"]: return "V2_OV"
    if state == "RUN" and d["v1_low"]: return "V1_UV"
    if state == "RUN" and d["v2_low"]: return "V2_UV"
    if d["ipk_over"]: return "I_PK"
    if d["ot"]: return "OT"
    if state != "INIT" and d["comm_lost"]: return "COMM"
    return None


def model_step(state, d, clear):
    """Explicit transition model of dab_ctrl_step() (+ an optional dab_ctrl_clear_fault() call before the step)."""
    if clear and state == "FAULT":
        state = "INIT"
    f = check_protection(state, d)
    if f and state != "FAULT":
        return "FAULT", False, f
    if state == "FAULT":
        return "FAULT", False, None
    if state == "INIT":
        return ("PRECHARGE_WAIT" if d["enable"] else "INIT"), False, None
    if state == "PRECHARGE_WAIT":
        if not d["enable"]: return "INIT", False, None
        if d["precharge_ok"] and not d["v1_low"]: return "SOFTSTART", False, None
        if d["pc_timeout"]: return "FAULT", False, "PRECHARGE"
        return "PRECHARGE_WAIT", False, None
    if not d["enable"]:
        return "INIT", False, None
    if state == "SOFTSTART":
        return ("RUN" if d["ss_done"] else "SOFTSTART"), True, None
    return "RUN", True, None


def expected_fault_literal(state, d):
    return any(d[b] for b in FAULT_BITS)


def expected_fault_conditional(state, d):
    if any(d[b] for b in UNCONDITIONAL): return True
    if d["comm_lost"] and state != "INIT": return True
    if (d["v1_low"] or d["v2_low"]) and state == "RUN": return True
    if d["pc_timeout"] and state == "PRECHARGE_WAIT" and not (d["precharge_ok"] and not d["v1_low"]) and d["enable"]: return True
    return False


def model_check():
    props = {k: dict(status="PASS", violations=[]) for k in ("P1_literal", "P1_conditional", "P2_fault_latched", "P3_gates_off_outside_run_softstart", "P4_no_deadlock", "P5_gates_imply_enable")}
    reach = {"INIT"}; q = deque(["INIT"]); succ = {s: set() for s in STATES}; n_trans = 0
    while q:
        s = q.popleft()
        for mask, d in inputs():
            for clear in (False, True):
                s2, gates, f = model_step(s, d, clear); n_trans += 1
                succ[s].add(s2)
                if s2 not in reach: reach.add(s2); q.append(s2)
                active = {b for b in BITS if d[b]}
                if s != "FAULT" and expected_fault_literal(s, d) and s2 != "FAULT":
                    props["P1_literal"]["violations"].append(dict(state=s, inputs=sorted(active), next=s2))
                if s != "FAULT" and expected_fault_conditional(s, d) and s2 != "FAULT":
                    props["P1_conditional"]["violations"].append(dict(state=s, inputs=sorted(active), next=s2))
                if s == "FAULT" and not clear and s2 != "FAULT":
                    props["P2_fault_latched"]["violations"].append(dict(state=s, inputs=sorted(active), next=s2))
                if gates and s2 not in ("RUN", "SOFTSTART"):
                    props["P3_gates_off_outside_run_softstart"]["violations"].append(dict(state=s, inputs=sorted(active), next=s2))
                if gates and f is not None:
                    props["P3_gates_off_outside_run_softstart"]["violations"].append(dict(state=s, inputs=sorted(active), next=s2, fault=f))
                if gates and not d["enable"]:
                    props["P5_gates_imply_enable"]["violations"].append(dict(state=s, inputs=sorted(active), next=s2))
    # P4: reachability
    def reachable_from(a):
        seen = {a}; qq = deque([a])
        while qq:
            x = qq.popleft()
            for y in succ[x]:
                if y not in seen: seen.add(y); qq.append(y)
        return seen
    for s in STATES:
        if not succ[s]: props["P4_no_deadlock"]["violations"].append(dict(state=s, issue="no successor"))
        if "RUN" not in reachable_from(s): props["P4_no_deadlock"]["violations"].append(dict(state=s, issue="RUN not reachable"))
    if "INIT" not in succ["FAULT"]: props["P4_no_deadlock"]["violations"].append(dict(state="FAULT", issue="INIT not reachable in one step"))
    for k, p in props.items():
        # compress the violation lists: summarise by (state, fault bits present)
        if p["violations"]:
            p["status"] = "FAIL"
            summ = {}
            for v in p["violations"]:
                key = (v["state"], tuple(sorted(set(v["inputs"]) & set(FAULT_BITS))) if "inputs" in v else (v["state"], v.get("issue")))
                summ[key] = summ.get(key, 0) + 1
            p["summary"] = [dict(state=k[0], fault_bits=list(k[1]) if isinstance(k[1], tuple) else k[1], count=c) for k, c in sorted(summ.items(), key=lambda kv: -kv[1])[:25]]
            p["n_violations"] = len(p["violations"]); del p["violations"]
        else:
            p["n_violations"] = 0; del p["violations"]
    return props, sorted(reach), n_trans, {s: sorted(v) for s, v in succ.items()}


def c_conformance(tmp):
    exe = os.path.join(tmp, "sm_conformance")
    cmd = ["gcc", "-O1", "-std=c11", "-I" + os.path.join(FW, "src"), os.path.join(HERE, "sm_conformance.c"), os.path.join(FW, "src", "dab_control.c"), "-lm", "-o", exe]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return dict(status="BUILD_FAILED", stderr=r.stderr[-2000:])
    out = subprocess.run([exe], capture_output=True, text=True).stdout.strip().splitlines()
    mism = []; n = 0
    for line in out:
        s, mask, clear, s2, g = line.split(","); s = STATES[int(s)]; mask = int(mask); clear = clear == "1"
        d = {b: bool((mask >> i) & 1) for i, b in enumerate(BITS)}
        ms2, mg, _ = model_step(s, d, clear); n += 1
        if ms2 != STATES[int(s2)] or mg != (g == "1"):
            mism.append(dict(state=s, inputs=[b for b in BITS if d[b]], clear=clear, c_next=STATES[int(s2)], c_gates=g == "1", model_next=ms2, model_gates=mg))
    return dict(status="PASS" if not mism else "MISMATCH", n_cases=n, n_mismatches=len(mism), examples=mism[:20])


def python_reference_conformance():
    """Run the Python reference controller through the same abstract inputs and list where it differs from the C model."""
    mism = {}; n = 0
    for s in STATES:
        for mask, d in inputs():
            c = DABController(64e-6, 2.0, 100e3, 1.0, 1.0); c.state = s; c.t_state = 0.0
            if s == "SOFTSTART" and d["ss_done"]: c.t_state = c.soft_start_s
            m = dict(v1=950 if d["v1_ov"] else (500 if d["v1_low"] else 800), v2=500 if d["v2_ov"] else (200 if d["v2_low"] else 400),
                     i_pk=40 if d["ipk_over"] else 10, T=110 if d["ot"] else 40, precharge_ok=d["precharge_ok"], comm_ok=not d["comm_lost"])
            try:
                c.step(m, enable=d["enable"])
                py_next, py_gates = c.state, (c.state in ("RUN", "SOFTSTART") and d["enable"])
            except Exception as e:  # noqa: BLE001
                py_next, py_gates = f"EXC:{type(e).__name__}", None
            ms2, mg, _ = model_step(s, d, False); n += 1
            if py_next != ms2:
                key = (s, ms2, py_next, tuple(b for b in ("driver_fault", "hw_trip", "pc_timeout", "enable") if d[b]))
                mism[key] = mism.get(key, 0) + 1
    rows = [dict(state=k[0], c_model_next=k[1], python_next=k[2], distinguishing_inputs=list(k[3]), count=v) for k, v in sorted(mism.items(), key=lambda kv: -kv[1])]
    return dict(n_cases=n, n_mismatch_classes=len(rows), classes=rows[:30])


def run_sil(tmp):
    exe = os.path.join(tmp, "sil_test"); os.makedirs(os.path.join(tmp, "sil"), exist_ok=True)
    src = [os.path.join(FW, "src", "dab_control.c"), os.path.join(FW, "src", "dab_comm.c"), os.path.join(FW, "hal", "sil", "plant.c"), os.path.join(FW, "sil", "sil_main.c")]
    r = subprocess.run(["gcc", "-O2", "-Wall", "-Wextra", "-std=c11", "-I" + os.path.join(FW, "src"), "-I" + os.path.join(FW, "hal", "sil"), "-o", exe] + src + ["-lm"], capture_output=True, text=True)
    if r.returncode != 0:
        return dict(status="BUILD_FAILED", stderr=r.stderr[-2000:])
    p = subprocess.run([exe], cwd=tmp, capture_output=True, text=True, timeout=600)
    open(os.path.join(RES, "sil_harness_output.txt"), "w").write(p.stdout + p.stderr)
    lines = p.stdout.splitlines()
    return dict(status="RUN", exit_code=p.returncode, n_pass=sum(l.startswith("PASS") for l in lines), n_fail=sum(l.startswith("FAIL") for l in lines),
                result_line=[l for l in lines if l.startswith("RESULT")], build_warnings=r.stderr.strip()[-1000:])


def main():
    props, reach, n_trans, succ = model_check()
    with tempfile.TemporaryDirectory(prefix="sm_check_") as tmp:
        conf = c_conformance(tmp); sil = run_sil(tmp)
    pyc = python_reference_conformance()
    res = dict(states=STATES, inputs=BITS, reachable_states=reach, n_transitions_checked=n_trans, successors=succ, properties=props,
               c_conformance=conf, python_reference_vs_c_model=pyc, sil_harness=sil)
    json.dump(res, open(os.path.join(RES, "state_machine_results.json"), "w"), indent=1)
    md = ["# State-machine model check (generated by state_machine_check.py)\n", f"Reachable states from INIT: {reach}; transitions checked: {n_trans} (5 states x {n_trans//10} consistent input combinations x clear/no-clear)\n",
          "| property | status | violations | summary |", "|---|---|---|---|"]
    for k, p in props.items():
        summ = "; ".join(f"{v['state']}: {v['fault_bits']} ({v['count']})" for v in p.get("summary", [])[:6])
        md.append(f"| {k} | {p['status']} | {p['n_violations']} | {summ} |")
    md += ["", f"C-code conformance (sm_conformance.c against the unmodified dab_control.c): **{conf['status']}**, {conf.get('n_cases', 0)} cases, {conf.get('n_mismatches', 'n/a')} mismatches"]
    if conf.get("examples"): md += ["", "Examples: " + json.dumps(conf["examples"][:5])]
    md += ["", f"Python reference controller (dabtools/dab/control.py) vs the C model: {pyc['n_mismatch_classes']} mismatch classes over {pyc['n_cases']} cases:", "",
           "| state | C model next | Python next | distinguishing inputs | count |", "|---|---|---|---|---|"]
    for r in pyc["classes"][:15]:
        md.append(f"| {r['state']} | {r['c_model_next']} | {r['python_next']} | {r['distinguishing_inputs']} | {r['count']} |")
    md += ["", f"SIL harness (10_Firmware/sil/sil_main.c, compiled with gcc in a scratch directory): {sil}"]
    open(os.path.join(RES, "state_machine_report.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))
    def hs(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
    head = open(os.path.join(REPO, ".git", "HEAD")).read().strip(); commit = head
    if head.startswith("ref:"):
        rp = os.path.join(REPO, ".git", head[5:]); commit = open(rp).read().strip() if os.path.exists(rp) else head
    gcc = subprocess.run(["gcc", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    json.dump(dict(script="state_machine_check.py", python=platform.python_version(), gcc=gcc, git_commit=commit, wall_time_s=round(time.time() - T0, 2), deterministic="exhaustive enumeration, no random numbers",
                   inputs={os.path.relpath(f, REPO): hs(f) for f in [os.path.join(FW, "src", "dab_control.c"), os.path.join(FW, "src", "dab_control.h"), os.path.join(FW, "src", "dab_params.h"),
                                                                     os.path.join(FW, "sil", "sil_main.c"), os.path.join(DAB, "dabtools", "dab", "control.py"), os.path.join(HERE, "sm_conformance.c")]}),
              open(os.path.join(RES, "provenance_sm.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
