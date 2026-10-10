#!/usr/bin/env python3
"""Figures for chapter 19 (deterministic, no random numbers).
ch19_maturity_levels.png - deliverables of Advanced_Research_2026/Verification_Evidence/maturity.json counted by
the FIRST level stated in their 'level' field (e.g. 'L3 (SIL); HIL L0' counts as L3, 'L1-L2' as L1).
ch19_test_stages.png     - the 13 staged tests of SiC_6k6_Industrial_DAB/20_Experimental_Test_Plan/test_plan.md
by risk level (transcribed from the table; nothing has been executed)."""
import os, re, json
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE))
M = json.load(open(os.path.join(REPO, "Advanced_Research_2026", "Verification_Evidence", "maturity.json")))
INK, MUTED, BLUE, GRID = "#0b0b0b", "#52514e", "#2a78d6", "#e4e3df"
levels = [f"L{i}" for i in range(7)]
count = {l: 0 for l in levels}
for d in M["deliverables"]:
    count[re.search(r"L\d", d["level"]).group(0)] += 1
fig, ax = plt.subplots(figsize=(8, 4.2), dpi=130)
y = list(range(len(levels)))[::-1]
ax.barh(y, [count[l] for l in levels], color=BLUE, height=0.55)
for yi, l in zip(y, levels):
    txt = f"{count[l]}" if count[l] else "0 - not available here (no HIL, no hardware)" if l in ("L4", "L5") else ("0 - none" if count[l] == 0 else "")
    ax.text(count[l] + 0.15, yi, txt, va="center", color=INK if count[l] else MUTED, fontsize=9)
ax.set_yticks(y); ax.set_yticklabels([f"{l}  {M['scale'][l].split(' (')[0]}" for l in levels], fontsize=8.5, color=INK)
ax.set_xlabel("number of deliverables (first level stated in maturity.json)", color=MUTED, fontsize=9)
ax.set_title(f"Maturity of the {len(M['deliverables'])} deliverables - nothing above L3", color=INK, fontsize=11, loc="left")
ax.set_xlim(0, max(count.values()) + 6); ax.grid(axis="x", color=GRID, lw=0.8); ax.set_axisbelow(True)
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch19_maturity_levels.png")); plt.close(fig)

# staged laboratory tests (transcribed from test_plan.md)
tests = [(1, "bare board, netlist", "low"), (2, "magnetics LCR", "low"), (3, "insulation hipot", "medium"),
         (4, "aux power + gate drive", "low"), (5, "protection, no link V", "low"), (6, "controller HIL", "low"),
         (7, "low-voltage power", "medium"), (8, "staged power 200-800 V", "high"), (9, "efficiency map", "high"),
         (10, "dynamics", "high"), (11, "thermal soak 2 h", "high"), (12, "EMI pre-compliance", "medium"),
         (13, "long duration 100 h", "high")]
risk = {"low": 1, "medium": 2, "high": 3}
fig, ax = plt.subplots(figsize=(9, 3.8), dpi=130)
ax.step([t[0] for t in tests], [risk[t[2]] for t in tests], where="mid", color=GRID, lw=1.2)
ax.scatter([t[0] for t in tests], [risk[t[2]] for t in tests], s=70, color=BLUE, zorder=3, edgecolor="white", linewidth=1.5)
for n, name, r in tests:
    ax.annotate(name, (n, risk[r]), xytext=(0, 9 if n % 2 else -16), textcoords="offset points", ha="center", fontsize=7.5, color=INK)
ax.set_yticks([1, 2, 3]); ax.set_yticklabels(["low", "medium", "high"], color=INK)
ax.set_xticks(range(1, 14)); ax.set_xlabel("test step in 20_Experimental_Test_Plan/test_plan.md (none executed)", color=MUTED, fontsize=9)
ax.set_ylim(0.4, 3.6); ax.set_xlim(0.3, 13.7); ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
ax.set_title("Staged laboratory plan: risk rises only after the low-risk checks pass", color=INK, fontsize=11, loc="left")
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch19_test_stages.png")); plt.close(fig)
print("written ch19_maturity_levels.png, ch19_test_stages.png", count)
