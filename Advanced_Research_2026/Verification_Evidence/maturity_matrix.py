#!/usr/bin/env python3
"""Write maturity_matrix.md from maturity.json and (if present) run_log.json script statuses."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
M = json.load(open(os.path.join(HERE, "maturity.json")))
runlog = json.load(open(os.path.join(HERE, "run_log.json"))) if os.path.exists(os.path.join(HERE, "run_log.json")) else None
lines = ["# Verification maturity matrix (Advanced_Research_2026, section 28)\n",
         "| Level | Meaning |", "|---|---|"] + [f"| {k} | {v} |" for k, v in M["scale"].items()]
lines += ["", "No deliverable in this repository is above L3: there is no hardware, no HIL bench, no FEM solver, no C2000 toolchain and no laboratory.", "",
          "| Area | Deliverable | Level | Evidence | Not verified |", "|---|---|---|---|---|"]
for d in M["deliverables"]:
    lines.append(f"| {d['area']} | {d['item']} | **{d['level']}** | {d['evidence']} | {d['not_verified']} |")
if runlog:
    lines += ["", f"## Last toolchain run ({runlog['started'][:19]} UTC, commit {runlog['versions'].get('git_commit', '')[:10]})", "", "| Module | Script | Status | Wall (s) |", "|---|---|---|---|"]
    for mod, e in runlog["modules"].items():
        for s in e["scripts"]: lines.append(f"| {mod} | {s['script']} | {s['status']} | {s.get('wall_s', '')} |")
open(os.path.join(HERE, "maturity_matrix.md"), "w").write("\n".join(lines) + "\n")
print("maturity_matrix.md written with", len(M["deliverables"]), "rows")
