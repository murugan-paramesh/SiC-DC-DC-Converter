#!/usr/bin/env python3
"""
Sketch figures for chapters 11-14 of the learning notes (matplotlib only, no board file needed).
Numbers are copied from the repository files named in each function; nothing here is measured.
    python3 make_figures_ch11_14.py      -> ch11_dab_floorplan.png, ch11_router_halos.png,
                                            ch12_thermal_chain.png, ch13_dm_cm_paths.png,
                                            ch14_insulation_distances.png
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyArrowPatch

HERE = os.path.dirname(os.path.abspath(__file__))


def floorplan():
    """Regions, barriers and straddlers from SiC_6k6_Industrial_DAB/dabtools/kicad_dab/gen_pcb_dab.py."""
    BW, BH = 340.0, 250.0
    HV_X2, C_X1, C_X2, LV_X1 = 118.0, 134.0, 205.0, 221.0
    fig, ax = plt.subplots(figsize=(10.5, 7.8))
    ax.add_patch(Rectangle((0, 0), BW, BH, fc="#f4f1e8", ec="k", lw=1.5))
    for x1, x2, col, name in ((5, HV_X2, "#f7c6c6", "HV region (850 V)"), (C_X1, C_X2, "#cfe3f7", "control region (SELV)"),
                              (LV_X1, BW - 5, "#f7e2b8", "LV region (450 V)")):
        ax.add_patch(Rectangle((x1, 5), x2 - x1, BH - 10, fc=col, ec="none"))
        ax.text((x1 + x2) / 2, BH - 26, name, ha="center", fontsize=10, weight="bold")
    for x1, x2 in ((HV_X2, C_X1), (C_X2, LV_X1)):
        ax.add_patch(Rectangle((x1, 3), x2 - x1, BH - 6, fc="white", ec="k", lw=0.8, hatch="//"))
        ax.text((x1 + x2) / 2, 180, "16 mm barrier\n(no copper, all 6 layers)", rotation=90, ha="center", va="center", fontsize=7.5)
    # heatsink bars and MOSFETs (manufacturing_notes.md: bar A x 20-110, bar B x 236-326, both along the top edge)
    for xa, xb, lab in ((20, 110, "heatsink bar A (PE)"), (236, 326, "heatsink bar B (PE)")):
        ax.add_patch(Rectangle((xa, 2), xb - xa, 8, fc="#9a9a9a", ec="k"))
        ax.text((xa + xb) / 2, 6, lab, ha="center", va="center", fontsize=7, color="white")
    for q, x in zip((1, 2, 3, 4, 5, 6, 7, 8), (30, 52, 76, 98, 246, 268, 292, 314)):
        ax.add_patch(Rectangle((x - 5, 11), 10, 7, fc="#333", ec="k")); ax.text(x, 24, f"Q{q}", ha="center", fontsize=7)
    # straddlers (STRADDLE_HV / STRADDLE_LV in gen_pcb_dab.py)
    for xc, items in ((126.0, [(20, "U1"), (34, "U2"), (48, "PS1"), (58, "PS2"), (68, "PS3"), (78, "PS4"), (100, "CT1"), (124, "U5"), (136, "PS9")]),
                      (213.0, [(20, "U3"), (34, "U4"), (48, "PS5"), (58, "PS6"), (68, "PS7"), (78, "PS8"), (100, "U6"), (114, "U7"), (128, "PS10")])):
        for y, ref in items:
            h = 11 if ref.startswith("CT") else 7
            ax.add_patch(Rectangle((xc - 9, y - h / 2), 18, h, fc="#ffffff", ec="#444", lw=0.8))
            ax.text(xc, y, ref, ha="center", va="center", fontsize=6.5)
    # DC-link film capacitors, studs, PE lugs, Y caps (placement table of gen_pcb_dab.py)
    for y in (100, 139, 178, 217):
        ax.add_patch(Rectangle((60 - 29, y - 17.5), 58, 35, fc="#d9d9d9", ec="k", lw=0.6))
    ax.text(60, 158, "C1-C4\nHV link film", ha="center", va="center", fontsize=7)
    for (x, y) in ((250, 95), (295, 95), (250, 122), (295, 122)):
        ax.add_patch(Rectangle((x - 15, y - 10), 30, 20, fc="#d9d9d9", ec="k", lw=0.6))
    ax.text(272, 108, "C9-C12\nLV link", ha="center", va="center", fontsize=7)
    for (x, y, lab) in ((14, 70, "J1"), (14, 100, "J2"), (312, 160, "J5"), (312, 200, "J6")):
        ax.add_patch(Circle((x, y), 4, fc="#b87333", ec="k")); ax.text(x + 7, y, lab, va="center", fontsize=7)
    for (x, y, lab) in ((14, 125, "J21 PE_HV"), (150.5, 242, "J20 PE"), (270, 241, "J22 PE_LV")):
        ax.add_patch(Circle((x, y), 3.5, fc="#2e8b57", ec="k")); ax.text(x + 6, y, lab, va="center", fontsize=7)
    for (x, y, lab) in ((24, 241, "CY1"), (60, 241, "CY2"), (250, 241, "CY3"), (290, 241, "CY4")):
        ax.add_patch(Rectangle((x - 5, y - 3), 10, 6, fc="#ffe680", ec="k", lw=0.6)); ax.text(x, y - 7, lab, ha="center", fontsize=6.5)
    # control-region landmarks
    for (x, y, w, h, lab) in ((146, 150, 6, 52, "J10"), (170, 150, 6, 22, "J12"), (199.9, 150, 6, 52, "J11"), (165, 71, 40, 26, "U8-U11 sensing / comparators"),
                              (166, 212, 40, 10, "U13-U15 supplies"), (170, 231, 60, 8, "connectors J13-J19")):
        ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc="white", ec="#444", lw=0.6)); ax.text(x, y + h / 2 + 4, lab, ha="center", fontsize=6.5)
    ax.set_xlim(-2, BW + 2); ax.set_ylim(BH + 2, -2); ax.set_aspect("equal")
    ax.set_xlabel("x (mm)"); ax.set_ylabel("y (mm, KiCad convention: down)")
    ax.set_title("DAB power board 340 x 250 mm: HV | barrier | control | barrier | LV (sketch from gen_pcb_dab.py placement)")
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch11_dab_floorplan.png"), dpi=130); plt.close(fig)


def router_halos():
    """PathFinder halo idea of tools/kicad/router.py: full halo r, small halo r-1, conflict when they overlap."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    for ax, d, title in ((axes[0], 6, "centre spacing 6 cells: no conflict"), (axes[1], 4, "centre spacing 4 cells: conflict (re-route)")):
        r = 3
        for xc, col, lab in ((5, "#c0392b", "net A"), (5 + d, "#2980b9", "net B")):
            ax.add_patch(Rectangle((xc - r - 0.5, 0), 2 * r + 1, 12, fc=col, alpha=0.15, ec="none"))
            ax.add_patch(Rectangle((xc - (r - 1) - 0.5, 0), 2 * (r - 1) + 1, 12, fc=col, alpha=0.25, ec="none"))
            ax.add_patch(Rectangle((xc - 0.5, 0), 1, 12, fc=col, ec="none"))
            ax.text(xc, 12.6, lab, ha="center", color=col, fontsize=9)
        ax.text(5, -1.2, "full halo r = 3 (light), small halo r-1 = 2 (dark)", ha="left", fontsize=8)
        for g in range(0, 17):
            ax.axvline(g - 0.5, color="#bbb", lw=0.4)
        ax.set_xlim(-0.5, 16.5); ax.set_ylim(-2, 14); ax.set_xticks(range(0, 17, 2)); ax.set_yticks([])
        ax.set_xlabel("grid cells (0.25 mm)"); ax.set_title(title, fontsize=10)
    fig.suptitle("Negotiated congestion: a cell inside A's full halo and B's small halo marks a conflict (router.py _halo_cells)", fontsize=9.5)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch11_router_halos.png"), dpi=130); plt.close(fig)


def thermal_chain():
    """Numbers: 13_Thermal_Analysis/thermal_report.md and thermal_analysis.py (HV bridge, worst corner, 3 m/s, 45 C)."""
    P_bridge, P_dev = 21.7, 21.7 / 4          # W (HV bridge worst corner, four devices)
    RthJC, Rtim, Rsink, Tamb = 0.45, 0.35, 0.22, 45.0
    Ts = Tamb + P_bridge * Rsink
    Tc = Ts + P_dev * Rtim
    Tj = Tc + P_dev * RthJC
    fig, ax = plt.subplots(figsize=(10, 3.4))
    nodes = [("Tj", Tj), ("Tcase", Tc), ("Tsink", Ts), ("Tamb", Tamb)]
    xs = [1, 4, 7, 10]
    for (name, T), x in zip(nodes, xs):
        ax.add_patch(Circle((x, 1), 0.45, fc="#f7c6c6" if name == "Tj" else "#dddddd", ec="k"))
        ax.text(x, 1, name, ha="center", va="center", fontsize=9)
        ax.text(x, 0.1, f"{T:.1f} C", ha="center", fontsize=9, weight="bold")
    for (x1, x2, lab, P) in ((1, 4, f"RthJC = {RthJC} K/W\n(devices.py, verified=False)", P_dev), (4, 7, f"Rth TIM = {Rtim} K/W\n(silicone pad)", P_dev),
                             (7, 10, f"Rth sink = {Rsink} K/W\n(3 m/s extrusion, catalogue class)", P_bridge)):
        ax.plot([x1 + 0.45, x2 - 0.45], [1, 1], color="k", lw=2)
        ax.add_patch(Rectangle(((x1 + x2) / 2 - 0.7, 0.8), 1.4, 0.4, fc="white", ec="k"))
        ax.text((x1 + x2) / 2, 1.75, lab, ha="center", fontsize=8)
        ax.text((x1 + x2) / 2, 0.5, f"{P:.1f} W", ha="center", fontsize=8, color="#c0392b")
    ax.set_xlim(0, 11); ax.set_ylim(-0.4, 2.6); ax.axis("off")
    ax.set_title("Steady-state thermal chain, HV bridge at the worst corner (21.7 W per bridge, 45 C ambient, forced air 3 m/s)", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch12_thermal_chain.png"), dpi=130); plt.close(fig)


def dm_cm_paths():
    """Qualitative sketch of the DM and CM noise paths described in 14_EMI_EMC/emi_report.md."""
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.add_patch(Rectangle((0.5, 0.8), 2.2, 2.4, fc="#eee", ec="k")); ax.text(1.6, 3.45, "DC LISN / source", ha="center", fontsize=9)
    ax.add_patch(Rectangle((3.6, 0.8), 1.2, 2.4, fc="#ffe680", ec="k")); ax.text(4.2, 3.45, "EMI filter\n(DM L-C, CM choke, Y)", ha="center", fontsize=8)
    ax.add_patch(Rectangle((5.8, 0.8), 1.4, 2.4, fc="#d9d9d9", ec="k")); ax.text(6.5, 3.45, "DC-link film\n4 x 20 uF", ha="center", fontsize=8)
    ax.add_patch(Rectangle((8.0, 0.8), 1.8, 2.4, fc="#f7c6c6", ec="k")); ax.text(8.9, 3.45, "HV bridge Q1-Q4\n20 V/ns edges", ha="center", fontsize=8)
    ax.add_patch(Rectangle((7.6, -0.6), 2.6, 0.5, fc="#9a9a9a", ec="k")); ax.text(8.9, -0.35, "heatsink (PE)", ha="center", color="white", fontsize=8)
    ax.plot([0.5, 10.5], [-0.9, -0.9], color="#2e8b57", lw=2); ax.text(5.5, -1.2, "PE / chassis", ha="center", color="#2e8b57", fontsize=9)
    # DM loop
    ax.add_patch(FancyArrowPatch((2.7, 2.6), (8.0, 2.6), arrowstyle="->", mutation_scale=14, color="#c0392b", lw=1.8, connectionstyle="arc3,rad=0"))
    ax.add_patch(FancyArrowPatch((8.0, 1.3), (2.7, 1.3), arrowstyle="->", mutation_scale=14, color="#c0392b", lw=1.8))
    ax.text(5.3, 2.75, "DM: pulsating bridge input current at 2 fs (4.2 A rms); residual 106 dBuV at 800 kHz without filter", color="#c0392b", fontsize=7.5, ha="center")
    # CM path
    ax.add_patch(FancyArrowPatch((8.9, 0.8), (8.9, -0.1), arrowstyle="->", mutation_scale=14, color="#2980b9", lw=1.8))
    ax.text(9.0, 0.35, "~100 pF per node (pad)\nI = C dv/dt = 2 A peak", color="#2980b9", fontsize=7.5, va="center")
    ax.add_patch(FancyArrowPatch((9.6, -0.9), (10.5, -0.9), arrowstyle="-", color="#2980b9", lw=0))
    ax.add_patch(FancyArrowPatch((4.2, -0.9), (4.2, 0.8), arrowstyle="->", mutation_scale=14, color="#2980b9", lw=1.8))
    ax.text(3.0, -0.1, "Y capacitors CY1/CY2\n4.7 nF to PE_HV\n(first CM element)", color="#2980b9", fontsize=7.5, ha="center")
    ax.text(5.2, -0.5, "CM return through PE: envelope 124 dBuV at 150 kHz, 57 dB attenuation needed", color="#2980b9", fontsize=7.5, ha="center")
    ax.set_xlim(0, 11); ax.set_ylim(-1.6, 4.2); ax.axis("off")
    ax.set_title("Differential-mode and common-mode noise paths at the HV port (numbers from emi_report.md, calculated, not measured)", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch13_dm_cm_paths.png"), dpi=130); plt.close(fig)


def insulation_distances():
    """Table 3 of 15_Safety_Reliability/01_insulation_coordination.md and the DRC rules of SiC_DAB_6k6.kicad_dru."""
    pairs = ["HV - PE", "HV - LV", "LV - PE", "HV - control", "LV - control"]
    clearance_req = [3.0, 3.0, 1.5, 5.5, 3.0]
    creepage_req = [8.5, 8.5, 4.5, 17.0, 9.0]          # PD2, material group IIIa (worst case quoted in table 3)
    design = [8.5, 9.0, 5.0, 16.0, 10.0]                # "design value used" column
    drc = [8.5, 12.0, 5.0, 12.0, 10.0]                  # .kicad_dru minimum clearance rules (pe_to_hv, iso_hv_lv, pe_to_lv, iso_hv_power_ctrl, iso_lv_power_ctrl)
    import numpy as np
    x = np.arange(len(pairs)); w = 0.2
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.bar(x - 1.5 * w, clearance_req, w, label="required clearance (impulse, PD2)", color="#bbbbbb")
    ax.bar(x - 0.5 * w, creepage_req, w, label="required creepage (PD2, group IIIa)", color="#777777")
    ax.bar(x + 0.5 * w, design, w, label="design value in 01_insulation_coordination.md", color="#2e8b57")
    ax.bar(x + 1.5 * w, drc, w, label="DRC rule minimum in SiC_DAB_6k6.kicad_dru", color="#c0392b")
    ax.set_xticks(x); ax.set_xticklabels(pairs); ax.set_ylabel("mm"); ax.grid(axis="y", alpha=0.3); ax.legend(fontsize=8)
    ax.set_title("Insulation distances: recalled table values (to re-check against the standard) vs the values enforced on the board", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "ch14_insulation_distances.png"), dpi=130); plt.close(fig)


if __name__ == "__main__":
    floorplan(); router_halos(); thermal_chain(); dm_cm_paths(); insulation_distances()
    print("figures written to", HERE)
