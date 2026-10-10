#!/usr/bin/env python3
"""Figure for chapter 20 (deterministic): ch20_learning_roadmap.png - the reading order of the notes
(beginner -> engineer -> researcher), chapter numbers and titles as in 00_Start_Here.md."""
import os
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
HERE = os.path.dirname(os.path.abspath(__file__))
INK, MUTED, LINE = "#0b0b0b", "#52514e", "#b9b8b2"
LANES = [("Beginner", "#2a78d6", [("01", "Electrical\nfundamentals"), ("02", "Power-electronics\nbasics"), ("03", "SiC devices"), ("04", "DAB\noperation")]),
         ("Engineer", "#1baf7a", [("05", "Mathematical\nmodel"), ("06", "Design\ncalculations"), ("07", "Magnetics"), ("08", "Simulation"), ("09", "Control and\nfirmware")]),
         ("Engineer (hardware)", "#1baf7a", [("10", "Schematics"), ("11", "PCB layout"), ("12", "Thermal"), ("13", "EMI/EMC"), ("14", "Safety, FMEA")]),
         ("Researcher", "#6250d6", [("15", "Optimisation\nand UQ"), ("16", "Digital twin"), ("17", "MPC, AI,\nsafe RL, PINN"), ("18", "Health, gate drive,\nreliability, cyber"), ("19", "Testing, HIL,\nresearch method")])]
fig, ax = plt.subplots(figsize=(11, 5.6), dpi=130); ax.set_xlim(0, 11); ax.set_ylim(-0.4, 4.6); ax.axis("off")
W, H = 1.55, 0.72
for row, (name, col, items) in enumerate(LANES):
    y = 3.9 - row * 1.1
    ax.text(0.05, y, name, fontsize=10, color=INK, va="center", weight="bold")
    for k, (num, title) in enumerate(items):
        x = 1.75 + k * 1.85
        ax.add_patch(FancyBboxPatch((x, y - H / 2), W, H, boxstyle="round,pad=0.02,rounding_size=0.08", fc="white", ec=col, lw=2))
        ax.text(x + 0.1, y + 0.2, num, fontsize=9, color=col, weight="bold", va="center")
        ax.text(x + W / 2 + 0.12, y - 0.06, title, fontsize=7.6, color=INK, ha="center", va="center")
        if k: ax.annotate("", (x, y), (x - 0.3, y), arrowprops=dict(arrowstyle="-|>", color=LINE, lw=1.2))
    if row < len(LANES) - 1:
        xe = 1.75 + (len(items) - 1) * 1.85 + W / 2
        ax.annotate("", (1.75 + W / 2, y - 1.1 + H / 2), (xe, y - H / 2), arrowprops=dict(arrowstyle="-|>", color=LINE, lw=1.0, connectionstyle="arc3,rad=0.0"))
y = 3.9 - 3 * 1.1 - 0.75
ax.add_patch(FancyBboxPatch((7.3, y - 0.3), 3.3, 0.6, boxstyle="round,pad=0.02,rounding_size=0.08", fc="#f2f1ee", ec=INK, lw=1.5))
ax.text(8.95, y, "20  Final learning guide: pitches, master viva list,\nreal / simulated / proposed table, next steps", fontsize=7.6, color=INK, ha="center", va="center")
ax.annotate("", (8.95, y + 0.3), (1.75 + 4 * 1.85 + W / 2, 3.9 - 3 * 1.1 - H / 2), arrowprops=dict(arrowstyle="-|>", color=LINE, lw=1.2))
ax.text(0.05, y, "Viva preparation: question lists of every chapter, then 20", fontsize=8, color=MUTED, va="center")
ax.set_title("Learning roadmap through the notes (chapter numbers as in 00_Start_Here.md)", fontsize=11, color=INK, loc="left")
fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch20_learning_roadmap.png")); plt.close(fig)
print("written ch20_learning_roadmap.png")
