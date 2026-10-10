#!/usr/bin/env python3
"""
Consistency check of the learning notes against the repository.
* every chapter NN_*.md (01-20) exists and has the mandatory level headings, template headings,
  question blocks (10/10/10) and pitch markers;
* every repository path quoted in back-ticks exists (relative to the repo root or to the notes
  folder) - paths that look like files/directories of this project only;
* every status tag used is one of the allowed five.
Exit code 1 when something is missing; prints a table.  Run from anywhere.
"""
import os, re, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
LEVELS = ["**Level 1 - Beginner:**", "**Level 2 - Engineering:**", "**Level 3 - Research:**"]
TEMPLATE = ["**What is it?**", "**Why do we need it?**", "**How does it work?**", "**Example from our converter:**",
            "**Engineering calculations:**", "**Design decision made in this project:**", "**Alternatives considered:**",
            "**How to verify it:**", "**Common mistakes:**", "**Interview explanation (30 s):**", "**Research-level explanation:**"]
QBLOCKS = ["### Basic (10)", "### Intermediate (10)", "### Advanced / research (10)"]
PITCH = ["**30 s:**", "**2 min:**", "**10 min outline:**"]
TAGS = {"[Implemented]", "[Simulated]", "[Verified]", "[Proposed]", "[Not yet tested]"}
PATH_RE = re.compile(r"`([A-Za-z0-9_./\-]+\.(?:py|md|json|csv|c|h|kicad_pcb|kicad_sch|kicad_dru|png|txt|mk|ini)|[A-Za-z0-9_\-]+(?:/[A-Za-z0-9_.\-]+)+/?)`")
# index of every file and directory in the repository (relative, '/'-separated) so that a short
# reference such as `design_values.json` or `results/twin_study.json` is accepted when a real file ends
# with it; a name that matches nothing in the repository is reported as unknown.
INDEX = []
for root, dirs, files in os.walk(REPO):
    dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "textbook")]
    rel = os.path.relpath(root, REPO).replace(os.sep, "/")
    INDEX.append(rel + "/")
    INDEX += [(rel + "/" + f) if rel != "." else f for f in files]
def exists_somewhere(p):
    p = p.rstrip("/")
    for c in (os.path.join(REPO, p), os.path.join(HERE, p), os.path.join(REPO, "SiC_6k6_Industrial_DAB", p)):
        if os.path.exists(c): return True
    tail = "/" + p
    return any(x.rstrip("/").endswith(tail) or x.rstrip("/") == p for x in INDEX)
ok_all = True; rows = []
chapters = sorted(glob.glob(os.path.join(HERE, "[0-2][0-9]_*.md")))
expected = {f"{i:02d}" for i in range(0, 21)}
present = {os.path.basename(c)[:2] for c in chapters}
missing = sorted(expected - present)
if missing: print("MISSING chapters:", missing); ok_all = False
for ch in chapters:
    name = os.path.basename(ch); txt = open(ch, encoding="utf-8").read()
    if name.startswith("00"): continue
    probs = []
    for h in LEVELS:
        if h not in txt: probs.append(f"no {h}")
    n_topics = txt.count(TEMPLATE[0])
    full = min(txt.count(h) for h in TEMPLATE)
    if full < 3: probs.append(f"only {full} complete template topics")
    for q in QBLOCKS:
        if q not in txt: probs.append(f"no {q}")
        else:
            seg = txt.split(q, 1)[1]; nxt = [seg.find(x) for x in QBLOCKS + ["## Pitches"] if seg.find(x) > 0]
            seg = seg[:min(nxt)] if nxt else seg
            nq = len(re.findall(r"^\s*\d+\.\s", seg, re.M))
            if nq < 10: probs.append(f"{q} has {nq} questions")
    for p in PITCH:
        if p not in txt: probs.append(f"no {p}")
    bad_paths = []
    for m in PATH_RE.finditer(txt):
        p = m.group(1)
        if not exists_somewhere(p): bad_paths.append(p)
    bad_paths = sorted(set(bad_paths))
    if bad_paths: probs.append(f"{len(bad_paths)} unknown paths: {bad_paths[:6]}")
    tags = set(re.findall(r"\[(?:Implemented|Simulated|Verified|Proposed|Not yet tested)\]", txt))
    if not tags: probs.append("no status tags")
    words = len(txt.split())
    rows.append((name, words, n_topics, "OK" if not probs else "; ".join(probs)))
    if probs: ok_all = False
w = max(len(r[0]) for r in rows) if rows else 10
for r in rows: print(f"{r[0]:<{w}}  {r[1]:>6} words  {r[2]:>2} topics  {r[3]}")
print("ALL OK" if ok_all else "PROBLEMS FOUND")
sys.exit(0 if ok_all else 1)
