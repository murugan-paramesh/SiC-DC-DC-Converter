#!/usr/bin/env python3
"""
Reproducible toolchain runner for Advanced_Research_2026.

Runs every script listed in manifest.json (module -> scripts), records exit codes, wall times,
stdout tails, SHA-256 of the files each module writes under results/, the package versions and the
git commit, and writes run_log.json + run_report.md.  A module whose script fails is reported as
FAIL - nothing is marked passed unless its script returned 0 in this run.
Usage: python3 run_all.py [module ...]     (default: all modules of the manifest)
"""
import hashlib, json, os, platform, subprocess, sys, time, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); REPO = os.path.dirname(ROOT)
man = json.load(open(os.path.join(HERE, "manifest.json")))
sel = sys.argv[1:] or list(man)
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()[:16]
def versions():
    v = {"python": platform.python_version()}
    for m in ("numpy", "scipy", "matplotlib", "pandas"):
        try: v[m] = __import__(m).__version__
        except Exception: v[m] = "n/a"
    try: v["git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    except Exception: v["git_commit"] = "n/a"
    return v
log = dict(started=datetime.datetime.now(datetime.timezone.utc).isoformat(), versions=versions(), modules={})
for mod in sel:
    d = os.path.join(ROOT, mod); entry = dict(scripts=[], results={})
    for s in man.get(mod, []):
        t0 = time.time(); p = os.path.join(d, s)
        if not os.path.exists(p):
            entry["scripts"].append(dict(script=s, status="MISSING")); continue
        try:
            r = subprocess.run([sys.executable, p], cwd=d, capture_output=True, text=True, timeout=1800)
            status = "PASS" if r.returncode == 0 else "FAIL"; tail = (r.stdout + r.stderr)[-600:]
        except subprocess.TimeoutExpired:
            status, tail = "TIMEOUT", ""
        entry["scripts"].append(dict(script=s, status=status, wall_s=round(time.time() - t0, 1), tail=tail))
        print(f"[{status}] {mod}/{s} ({time.time() - t0:.0f} s)")
    rd = os.path.join(d, "results")
    if os.path.isdir(rd):
        for f in sorted(os.listdir(rd)):
            fp = os.path.join(rd, f)
            if os.path.isfile(fp): entry["results"][f] = dict(sha256_16=sha(fp), bytes=os.path.getsize(fp))
    log["modules"][mod] = entry
log["finished"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
json.dump(log, open(os.path.join(HERE, "run_log.json"), "w"), indent=1)
lines = [f"# Advanced_Research_2026 toolchain run\n", f"Started {log['started']}, finished {log['finished']}.  Versions: {log['versions']}\n",
         "| Module | Script | Status | Wall (s) |", "|---|---|---|---|"]
for mod, e in log["modules"].items():
    for s in e["scripts"]: lines.append(f"| {mod} | {s['script']} | {s['status']} | {s.get('wall_s', '')} |")
lines.append("\nResult files hashed in run_log.json: " + str(sum(len(e["results"]) for e in log["modules"].values())))
open(os.path.join(HERE, "run_report.md"), "w").write("\n".join(lines) + "\n")
fails = [s for e in log["modules"].values() for s in e["scripts"] if s["status"] != "PASS"]
print("done;", len(fails), "non-passing scripts")
sys.exit(1 if fails else 0)
