#!/usr/bin/env python3
"""
Deterministic sketches for chapters 06-10 of the learning notes (matplotlib only, no data files,
no random numbers).  Run from any directory:  python3 <path>/make_figs_06_10.py
Writes fig06_design_flow.png, fig07_winding_arrangements.png, fig08_sim_timing.png,
fig09_control_state_machine.png, fig10_schematic_blocks.png next to this script.
"""
import os
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Circle

HERE = os.path.dirname(os.path.abspath(__file__))
BLUE, ORANGE, GREEN, GREY, RED = "#2a78d6", "#eb6834", "#1baf7a", "#8a8f98", "#c0392b"
plt.rcParams.update({"font.size": 9, "font.family": "DejaVu Sans"})


def box(ax, x, y, w, h, text, color=BLUE, fs=8.5, lw=1.2, fc="white"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                ec=color, fc=fc, lw=lw))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, wrap=True)


def arrow(ax, x0, y0, x1, y1, color=GREY, text="", fs=7.5, style="-|>"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=12, color=color, lw=1.0))
    if text:
        ax.text((x0 + x1) / 2, (y0 + y1) / 2 + 0.03, text, ha="center", va="bottom", fontsize=fs, color=color)


# ----------------------------------------------------------------------------- 06
def fig06():
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.set_xlim(0, 10); ax.set_ylim(0, 6); ax.axis("off")
    ax.set_title("dab_design.py: how the design numbers are produced (04_Design_Calculations)", fontsize=10)
    box(ax, 0.2, 4.9, 2.4, 0.9, "Specification\n6.6 kW, 650-850 V / 300-450 V\nfs 100 kHz, n = 2, phi_nom 28 deg", BLUE)
    box(ax, 3.3, 4.9, 2.4, 0.9, "Series inductance\nL = V1 n V2 phi(pi-phi) / (2 pi^2 fs P)\n-> 64 uH, Pmax 12.5 kW", BLUE)
    box(ax, 6.4, 4.9, 3.3, 0.9, "Devices (devices.py, verified=False)\nHV C3M0032120K, LV C3M0016120K\nt_dead 150 ns, C_par 60 pF", ORANGE)
    box(ax, 0.2, 3.2, 3.0, 1.1, "evaluate(V1, V2, P)\nDABPoint waveforms -> I_rms, I_pk,\nedge currents, ZVS margin,\nbridge_losses + 6 electro-thermal iterations", GREEN)
    box(ax, 3.6, 3.2, 2.9, 1.1, "Magnetics at nominal\ndesign_transformer (E65/32/27)\ndesign_inductor (E55/28/21)\nL_ext = L - Llk = 59.9 uH", GREEN)
    box(ax, 6.9, 3.2, 2.8, 1.1, "DC links\n4 x 20 uF / 1100 V, 4 x 30 uF / 700 V\nI_rms, ripple, ESR loss,\nbleeders (< 60 V in 5 min)", GREEN)
    box(ax, 0.2, 1.5, 3.0, 1.1, "Loss budget at 800/400 V\n14 items, 92.2 W\neta = 98.62 % (calculated)", ORANGE)
    box(ax, 3.6, 1.5, 2.9, 1.1, "Maps over 9 x 7 (V1, V2) grid\nderating (phi <= 60 deg, Ipk <= 24 A,\nTj <= 150 C) and SPS ZVS light-load limit", ORANGE)
    box(ax, 6.9, 1.5, 2.8, 1.1, "TPS search at 3 x 3 corners\nminimum rms with ZVS constraint\n+ efficiency vs load curves", ORANGE)
    box(ax, 2.0, 0.1, 6.0, 0.8, "design_values.json  +  design_report.md  +  img/*.png\n(consumed by 05, 06, 10, 11, 12, 13 and the KiCad generator)", RED, fc="#fff5f3")
    arrow(ax, 2.6, 5.35, 3.3, 5.35); arrow(ax, 5.7, 5.35, 6.4, 5.35)
    arrow(ax, 1.7, 4.9, 1.7, 4.3); arrow(ax, 5.0, 4.9, 5.0, 4.3); arrow(ax, 8.3, 4.9, 8.3, 4.3)
    arrow(ax, 1.7, 3.2, 1.7, 2.6); arrow(ax, 5.0, 3.2, 5.0, 2.6); arrow(ax, 8.3, 3.2, 8.3, 2.6)
    arrow(ax, 1.7, 1.5, 3.0, 0.9); arrow(ax, 5.0, 1.5, 5.0, 0.9); arrow(ax, 8.3, 1.5, 7.0, 0.9)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "fig06_design_flow.png"), dpi=140); plt.close(fig)


# ----------------------------------------------------------------------------- 07
def fig07():
    fig, axs = plt.subplots(1, 2, figsize=(9, 4.2))
    for ax, title, layers in ((axs[0], "P/2 - S - P/2 interleaved (baseline)\nLlk ~ 4.1 uH, Fr 1.04 / 1.08",
                               [("P/2", BLUE, 14), ("S", ORANGE, 14), ("P/2", BLUE, 14)]),
                              (axs[1], "P - S non-interleaved (integrated-leakage option)\nLlk ~ 16.4 uH, Fr 1.15 / 1.31",
                               [("P", BLUE, 28), ("S", ORANGE, 14)])):
        ax.set_xlim(0, 10); ax.set_ylim(0, 6); ax.axis("off"); ax.set_title(title, fontsize=9)
        # core legs
        ax.add_patch(Rectangle((0.3, 0.5), 1.0, 5.0, fc="#d9d9d9", ec="k")); ax.text(0.8, 3.0, "centre\nleg", ha="center", va="center", fontsize=7)
        ax.add_patch(Rectangle((8.7, 0.5), 1.0, 5.0, fc="#d9d9d9", ec="k")); ax.text(9.2, 3.0, "outer\nleg", ha="center", va="center", fontsize=7)
        # winding layers from the centre leg outwards (radial direction = x)
        x = 1.6
        widths = [1.6] * len(layers)
        for (name, col, turns), w in zip(layers, widths):
            ax.add_patch(Rectangle((x, 1.0), w, 4.0, fc=col, ec="k", alpha=0.5))
            ax.text(x + w / 2, 3.0, f"{name}\n{turns} t", ha="center", va="center", fontsize=8)
            x += w + 0.3
            if name.startswith("S") or (name == "P" and len(layers) == 2):
                ax.add_patch(Rectangle((x - 0.3, 1.0), 0.3, 4.0, fc="#f7e38a", ec="none"))
        ax.text(x - 0.15, 0.7, "3 x 50 um\npolyimide", ha="center", fontsize=6.5)
        # MMF diagram under the window
        ax.text(5.0, 0.25, "MMF across the window: interleaving halves the peak MMF -> leakage / 4, lower proximity loss",
                ha="center", fontsize=6.5, color=GREY)
    fig.suptitle("E65/32/27 window cross-section sketch (not to scale): winding arrangements of dabtools/dab/magnetics.py", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "fig07_winding_arrangements.png"), dpi=140); plt.close(fig)


# ----------------------------------------------------------------------------- 08
def fig08():
    fig, axs = plt.subplots(2, 1, figsize=(9, 5.6))
    ax = axs[0]; ax.set_xlim(0, 10); ax.set_ylim(0, 3); ax.axis("off")
    ax.set_title("DABPlant.run_period: the controller runs once per period, its output is applied one period later", fontsize=9)
    for k in range(4):
        x0 = 0.5 + k * 2.3
        ax.add_patch(Rectangle((x0, 1.2), 2.1, 0.8, fc="#eef4fb", ec=BLUE))
        ax.text(x0 + 1.05, 1.6, f"period k{'' if k == 0 else '+' + str(k)}\nN_sub = 200 cells, dt = 50 ns", ha="center", va="center", fontsize=7.5)
        ax.add_patch(Circle((x0, 2.4), 0.12, fc=ORANGE, ec="none"))
        ax.text(x0, 2.7, "ISR: measure v1, v2, i_pk\ncompute phi, D1, D2", ha="center", fontsize=6.8)
        ax.add_patch(FancyArrowPatch((x0 + 0.05, 2.3), (x0 + 2.4, 2.05), arrowstyle="-|>", mutation_scale=10, color=ORANGE, lw=0.9, connectionstyle="arc3,rad=-0.25"))
    ax.text(5.0, 0.6, "measurement of period k  ->  command for period k+1  (delay 1 Ts, plus 0.5 Ts PWM averaging = 1.5 Ts in the loop design)", ha="center", fontsize=7.5, color=GREY)
    ax = axs[1]; ax.set_xlim(0, 10); ax.set_ylim(-1.6, 1.8); ax.axis("off")
    ax.set_title("period_voltages(): the 2026 defect - positive and negative pulses built independently could differ by one cell", fontsize=9)
    n = 20
    xs = [0.5 + 9.0 * i / n for i in range(n + 1)]
    for i in range(n):
        ax.add_patch(Rectangle((xs[i], -1.3), xs[i + 1] - xs[i], 2.6, fc="none", ec="#e0e0e0", lw=0.5))
    # wrong: positive pulse 6 cells, negative 7 cells
    for i in range(3, 9):
        ax.add_patch(Rectangle((xs[i], 0), xs[i + 1] - xs[i], 1.0, fc=RED, alpha=0.35, ec="none"))
    for i in range(12, 19):
        ax.add_patch(Rectangle((xs[i], -1.0), xs[i + 1] - xs[i], 1.0, fc=RED, alpha=0.35, ec="none"))
    ax.text(xs[18] + 0.1, -0.5, "extra cell\n-> DC volt-second\n-> DC current through R_s", fontsize=7, color=RED, va="center")
    # right: rolled by N_sub/2
    for i in range(3, 9):
        ax.add_patch(Rectangle((xs[i], 0), xs[i + 1] - xs[i], 1.0, fc="none", ec=GREEN, lw=1.5))
    for i in range(13, 19):
        ax.add_patch(Rectangle((xs[i], -1.0), xs[i + 1] - xs[i], 1.0, fc="none", ec=GREEN, lw=1.5))
    ax.plot([0.5, 9.5], [0, 0], color="k", lw=0.6)
    ax.text(0.5, 1.5, "red fill = two independent comparisons (old);  green outline = negative pulse = positive pulse rolled by exactly N_sub/2 (fixed)", fontsize=7.5)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "fig08_sim_timing.png"), dpi=140); plt.close(fig)


# ----------------------------------------------------------------------------- 09
def fig09():
    fig, axs = plt.subplots(1, 2, figsize=(10, 4.6))
    ax = axs[0]; ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")
    ax.set_title("State machine (dab_control.c / control.py)", fontsize=9)
    states = {"INIT": (1.5, 8.5), "PRECHARGE_WAIT": (5.0, 8.5), "SOFTSTART": (5.0, 5.5), "RUN": (5.0, 2.5), "FAULT": (8.6, 5.5)}
    for name, (x, y) in states.items():
        col = RED if name == "FAULT" else BLUE
        ax.add_patch(FancyBboxPatch((x - 1.3, y - 0.5), 2.6, 1.0, boxstyle="round,pad=0.02,rounding_size=0.2", ec=col, fc="white", lw=1.3))
        ax.text(x, y, name, ha="center", va="center", fontsize=8.5, color=col)
    arrow(ax, 2.8, 8.5, 3.7, 8.5, text="enable")
    arrow(ax, 5.0, 8.0, 5.0, 6.0, text="precharge_ok and v1 > 600 V")
    arrow(ax, 5.0, 5.0, 5.0, 3.0, text="t > 50 ms (ss_scale = 1)")
    arrow(ax, 6.3, 8.7, 8.6, 6.0, color=RED, text="t > 5 s: FLT_PRECHARGE")
    arrow(ax, 6.3, 5.5, 7.3, 5.5, color=RED)
    arrow(ax, 6.3, 2.5, 8.6, 5.0, color=RED, text="any protection")
    arrow(ax, 8.6, 6.0, 2.0, 9.0, color=GREY, text="clear_fault (re-faults if condition persists)")
    arrow(ax, 3.7, 2.5, 1.5, 8.0, color=GREY, text="enable = 0")
    ax.text(5.0, 0.6, "FAULT: gates off, PI integrator reset, fault logged (ring of 8)", ha="center", fontsize=7.5, color=RED)
    ax = axs[1]; ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")
    ax.set_title("Control path executed once per 10 us period", fontsize=9)
    box(ax, 0.3, 8.3, 4.2, 1.1, "reference: v2_ref (CV) ramped from v2_start\nduring soft start; P_ref x scale (CP)", BLUE)
    box(ax, 0.3, 6.4, 4.2, 1.1, "PI: kp 1689 W/V, ki 1.27e6 W/(V s)\nclamping anti-windup, +/- 1.1 P_rated", BLUE)
    box(ax, 0.3, 4.5, 4.2, 1.1, "slew limit 2 kW/ms (CP mode)", BLUE)
    box(ax, 0.3, 2.6, 4.2, 1.1, "phi_from_power: inverse SPS equation in\ncurrent form I2 = P / max(v2, 40 V)\n+ dead-time compensation 0.047 rad", GREEN)
    box(ax, 0.3, 0.7, 4.2, 1.1, "eps_matching: D of the higher-voltage bridge\n= d = n v2 / v1 (min 0.12)", GREEN)
    box(ax, 5.6, 2.6, 4.1, 3.0, "C2000 ePWM (HAL, not compiled)\nEPWM1 master, EPWM2 TBPHS = D1 x 180 deg\nEPWM3/4 TBPHS = phi (+ D2 x 180 deg)\ndead band 150 ns, TZ1-3 trips", ORANGE)
    box(ax, 5.6, 6.4, 4.1, 3.0, "check_protection (every period)\nhw_trip, driver_fault, V1/V2 OV,\nV1/V2 UV (RUN only), |i_pk| > 32 A,\nT > 95 C, comm loss", RED, fc="#fff5f3")
    for y in (8.3, 6.4, 4.5, 2.6):
        arrow(ax, 2.4, y, 2.4, y - 0.8)
    arrow(ax, 4.5, 3.15, 5.6, 3.6, text="phi")
    arrow(ax, 4.5, 1.25, 5.6, 3.0, text="D1, D2")
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "fig09_control_state_machine.png"), dpi=140); plt.close(fig)


# ----------------------------------------------------------------------------- 10
def fig10():
    fig, ax = plt.subplots(figsize=(10, 5.6))
    ax.set_xlim(0, 12); ax.set_ylim(0, 7); ax.axis("off")
    ax.set_title("SiC_DAB_6k6 schematic: five sheets and the three isolation regions (design_dab.py)", fontsize=10)
    ax.add_patch(Rectangle((0.2, 0.3), 3.4, 6.2, fc="#fdeeea", ec="none")); ax.text(1.9, 6.25, "HV region (850 V)", ha="center", fontsize=8.5, color=RED)
    ax.add_patch(Rectangle((4.3, 0.3), 3.4, 6.2, fc="#eef7f0", ec="none")); ax.text(6.0, 6.25, "control region (SELV)", ha="center", fontsize=8.5, color=GREEN)
    ax.add_patch(Rectangle((8.4, 0.3), 3.4, 6.2, fc="#fff3e6", ec="none")); ax.text(10.1, 6.25, "LV region (450 V)", ha="center", fontsize=8.5, color=ORANGE)
    for x in (3.6, 7.7):
        ax.add_patch(Rectangle((x, 0.3), 0.7, 6.2, fc="white", ec=GREY, ls="--", lw=0.8))
        ax.text(x + 0.35, 0.45, "16 mm\nbarrier", ha="center", fontsize=6.5, color=GREY)
    box(ax, 0.4, 4.6, 3.0, 1.3, "hv_bridge.kicad_sch\nJ1/J2 studs, F1 16 A, C1-C4 20 uF/1100 V\nR1-R4 bleeders, CY1/CY2 Y1 4.7 nF, J21 PE_HV\nQ1-Q4 C3M0032120K, C5-C8 100 nF/1 kV\nJ3 SW_A -> L1, J4 SW_B -> T1", RED, fs=7)
    box(ax, 8.6, 4.6, 3.0, 1.3, "lv_bridge.kicad_sch\nJ5/J6 studs, F2 32 A, C9-C12 30 uF/700 V\nR5/R6 bleeders, CY3/CY4, J22 PE_LV\nQ5-Q8 C3M0016120K, C13-C16 220 nF/630 V\nR7 1 mOhm shunt, J7/J8 SW_C/SW_D -> T1", ORANGE, fs=7)
    box(ax, 4.5, 4.6, 3.0, 1.3, "gate_drive.kicad_sch\nU1-U4 UCC21520DW (straddle the barriers)\nPS1-PS8 R12P21503D +15/-3 V bias\nRg on 3.3 R, off 1.5 R + SS14, 10k bleed\nDT 2.2k ~ 22 ns interlock", GREEN, fs=7)
    box(ax, 4.5, 2.6, 3.0, 1.5, "sensing_protection.kicad_sch\nU5/U6 AMC1301 V1/V2 (PS9/PS10 iso 5 V)\nU7 AMC1301 shunt I2, CT1 1:100 + 6.2 R burden\nU8/U9 TLV9062, U10/U11 LM393 (OC 2.0 V,\nOV 920 / 490 V) -> PROT_DIS, U12 74HC32", GREEN, fs=7)
    box(ax, 4.5, 0.6, 3.0, 1.5, "control_aux.kicad_sch\nJ10-J12 LaunchPad F280049C headers\nJ13 24 V -> U13 TSR 3-24120 12 V -> U14 5 V\n-> U15 3.3 V; U16 TCAN332 CAN; U17 ULN2003A\nrelays/fans; U18/U19 PC817 interlocks; J20 PE", GREEN, fs=7)
    arrow(ax, 3.4, 5.25, 4.5, 5.25, text="G_Q1..4 / KS")
    arrow(ax, 7.5, 5.25, 8.6, 5.25, text="G_Q5..8 / KS")
    arrow(ax, 3.4, 3.4, 4.5, 3.4, text="HV_P/HV_N divider, SW_A via CT1")
    arrow(ax, 8.6, 3.4, 7.5, 3.4, text="LV divider, shunt Kelvin")
    arrow(ax, 6.0, 2.6, 6.0, 2.1, text="PROT_DIS, V1_SE, V2_SE, I_L, I2_SE")
    arrow(ax, 6.0, 4.1, 6.0, 4.6, text="PROT_DIS -> driver DIS")
    ax.text(1.9, 3.0, "external magnetics module:\nT1 E65/32/27 28:14\nL1 E55/28/21 59.9 uH\n(M6 studs J3, J4, J7, J8, J9)", ha="center", fontsize=7.5, color=GREY)
    ax.text(10.1, 3.0, "three PE lugs J20/J21/J22\nbonded through the chassis,\nnever by PCB copper", ha="center", fontsize=7.5, color=GREY)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "fig10_schematic_blocks.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    fig06(); fig07(); fig08(); fig09(); fig10()
    print("figures written to", HERE)
