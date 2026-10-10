#!/usr/bin/env python3
"""
FEM_Magnetics study: 2-D finite-difference magnetostatics of the E65/32/27 DAB transformer window
(leakage inductance, field map, proximity-effect AC resistance), a planar PCB-winding alternative and a
small Pareto study.  Regenerates everything in results/ and provenance.json.

Run:  python3 <path>/run_fem_magnetics.py          (any cwd, numpy/scipy/matplotlib only, < 10 min)
"""
import csv
import hashlib
import json
import math
import os
import platform
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DAB = os.path.join(REPO, "SiC_6k6_Industrial_DAB")
sys.path.insert(0, HERE)
sys.path.insert(0, DAB)
RES = os.path.join(HERE, "results")
os.makedirs(RES, exist_ok=True)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from fd_magnetostatic import (FDMagnetostatic, Rect, MU0, rho_cu, skin_depth, slab_loss_per_area,
                              dowell_fr, round_wire_factors)
from dabtools.dab import magnetics as mag

T0 = time.time()
np.random.seed(0)                     # no random numbers are used; fixed for the conventions
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"      # categorical slots 1-3 (fixed order)

DESIGN_PATH = os.path.join(DAB, "04_Design_Calculations", "design_values.json")
with open(DESIGN_PATH) as f:
    DESIGN = json.load(f)
TR = DESIGN["transformer"]
SPEC = DESIGN["spec"]
FS = SPEC["fs"]
V1 = SPEC["V1_nom"]
I1_RMS, I2_RMS = DESIGN["nominal"]["Irms1"], DESIGN["nominal"]["Irms2"]
L_EXT = DESIGN["L"]
T_CU = 100.0
MU_CORE = mag.MATERIALS["3C95"]["mu_i"]       # 3000, used for the ferrite region
T_CORE = 3.0e-3                                 # ferrite thickness modelled around the window (m)

LOG = []


def log(s=""):
    print(s)
    LOG.append(s)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# 1. Solver validation
# ---------------------------------------------------------------------------
def validate():
    log("== 1. Validation of the FD solver ==")
    bw, hw = mag.CORES["E65/32/27"]["bw"], mag.CORES["E65/32/27"]["hw"]
    h1 = h2 = 2.0e-3
    d = 1.0e-3
    rows = []
    L_an = MU0 / hw * (d + (h1 + h2) / 3)         # two full-height foils, 1 turn each, per metre depth
    for h in (0.4e-3, 0.2e-3, 0.1e-3, 0.05e-3):
        t = time.time()
        s = FDMagnetostatic(bw + 2 * T_CORE, hw + 2 * T_CORE, h)
        s.add(Rect(0, 0, bw + 2 * T_CORE, hw + 2 * T_CORE, mu_r=MU_CORE))
        s.add(Rect(T_CORE, T_CORE, T_CORE + bw, T_CORE + hw, mu_r=1.0))
        xa = T_CORE + 2.0e-3
        s.add(Rect(xa, T_CORE, xa + h1, T_CORE + hw, I=1.0, name="P"))
        s.add(Rect(xa + h1 + d, T_CORE, xa + h1 + d + h2, T_CORE + hw, I=-1.0, name="S"))
        s.solve()
        Lf, Ls = s.inductance(1.0, 1.0)
        rows.append(dict(h_mm=h * 1e3, unknowns=(s.nx + 1) * (s.ny + 1), L_fd_nH_per_m=Lf * 1e9,
                         L_source_form_nH_per_m=Ls * 1e9, L_analytic_nH_per_m=L_an * 1e9,
                         error_pct=100 * (Lf / L_an - 1), solve_s=time.time() - t))
        log(f"  foil leakage  h={h*1e3:.2f} mm  n={rows[-1]['unknowns']:7d}  L_fd={Lf*1e9:.3f} nH/m  "
            f"analytic={L_an*1e9:.3f}  err={rows[-1]['error_pct']:+.3f} %  ({rows[-1]['solve_s']:.1f} s)")
    # Validation 2: Dowell's formula for a 3 + 3 full-height foil winding (porosity 1): slab post-processing
    # driven by the FD field must reproduce Dowell's Fr for each frequency.
    m = 3
    tf = 0.25e-3
    gap = 0.1e-3
    h = 0.05e-3
    s = FDMagnetostatic(bw + 2 * T_CORE, hw + 2 * T_CORE, h)
    s.add(Rect(0, 0, bw + 2 * T_CORE, hw + 2 * T_CORE, mu_r=MU_CORE))
    s.add(Rect(T_CORE, T_CORE, T_CORE + bw, T_CORE + hw, mu_r=1.0))
    x = T_CORE + 1.0e-3
    foils = []
    for k in range(m):
        foils.append(Rect(x, T_CORE, x + tf, T_CORE + hw, I=1.0, name=f"P{k+1}")); x += tf + gap
    x += 0.5e-3
    for k in range(m):
        foils.append(Rect(x, T_CORE, x + tf, T_CORE + hw, I=-1.0, name=f"S{k+1}")); x += tf + gap
    for r in foils:
        s.add(r)
    s.solve()
    dow = []
    for f in (100e3, 300e3):
        Fr_fd = foil_winding_fr(s, foils[:m], f, vertical=True)
        Fr_dw = dowell_fr(tf, skin_depth(f, T_CU), m, 1.0)
        dow.append(dict(f_kHz=f / 1e3, layers=m, foil_mm=tf * 1e3, Fr_fd_slab=Fr_fd, Fr_dowell=Fr_dw,
                        error_pct=100 * (Fr_fd / Fr_dw - 1)))
        log(f"  Dowell check  f={f/1e3:.0f} kHz  m={m}  Fr(FD+slab)={Fr_fd:.4f}  Fr(Dowell)={Fr_dw:.4f}  "
            f"err={dow[-1]['error_pct']:+.2f} %")
    with open(os.path.join(RES, "validation_leakage_convergence.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    with open(os.path.join(RES, "validation_dowell.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dow[0].keys())); w.writeheader(); w.writerows(dow)
    fig, ax = plt.subplots(figsize=(5.5, 3.6))
    hs = [r["h_mm"] for r in rows]
    ax.plot(hs, [abs(r["error_pct"]) for r in rows], "o-", color=C1, lw=2, ms=6)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("cell size h (mm)"); ax.set_ylabel("|error| vs closed form (%)")
    ax.set_title("FD leakage of two full-height foils vs analytic", fontsize=10)
    ax.grid(True, which="both", alpha=0.3)
    for r in rows:
        ax.annotate(f"{r['error_pct']:+.3f} %", (r["h_mm"], abs(r["error_pct"])), textcoords="offset points",
                    xytext=(6, 4), fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(RES, "fig_validation_convergence.png"), dpi=150); plt.close(fig)
    return rows, dow


def face_fields(s, r, vertical):
    """Tangential H on the two faces of a conductor rectangle, averaged along the face (A/m, FD current)."""
    Bx, By, Hx, Hy = s.fields()
    iy, ix = s.region_cells(r)
    iy, ix = iy.ravel(), ix.ravel()
    if vertical:            # layer is a vertical strip -> tangential field is Hy, faces at x0 and x1
        Ha = Hy[iy, ix[0] - 1].mean()
        Hb = Hy[iy, ix[-1] + 1].mean()
    else:                   # horizontal layer (PCB) -> tangential Hx, faces at y0 and y1
        Ha = Hx[iy[0] - 1, ix].mean()
        Hb = Hx[iy[-1] + 1, ix].mean()
    return Ha, Hb


def foil_winding_fr(s, rects, f, vertical, thickness=None):
    """Winding-level Fr = sum(P_ac) / sum(P_dc) from the 1-D slab solution with FD face fields."""
    Pac = Pdc = 0.0
    for r in rects:
        t = (r.x1 - r.x0) if vertical else (r.y1 - r.y0)
        if thickness is not None:
            t = thickness
        width = (r.y1 - r.y0) if vertical else (r.x1 - r.x0)
        Ha, Hb = face_fields(s, r, vertical)
        pa, pd = slab_loss_per_area(Ha * math.sqrt(2), Hb * math.sqrt(2), t, f, T_CU)
        Pac += pa * width; Pdc += pd * width
    return Pac / Pdc


# ---------------------------------------------------------------------------
# 2. Wound E65 transformer models
# ---------------------------------------------------------------------------
def wound_geometry(arrangement, extra_spacer=0.0):
    """
    Build the E65 window with litz layers from the design values.  Returns (solver-ready region list, info).
    Layers are rectangles: radial thickness = bundle diameter, axial extent = turns x bundle diameter.
    """
    c = mag.CORES["E65/32/27"]
    bw, hw, lw = c["bw"], c["hw"], c["lw"]
    N1, N2 = TR["N1"], TR["N2"]
    A1, A2 = TR["A1"], TR["A2"]
    d1 = math.sqrt(4 * A1 / math.pi / 0.5)         # litz bundle diameter at packing 0.5 (as in the design)
    d2 = math.sqrt(4 * A2 / math.pi / 0.5)
    t_ins = 3 * 50e-6                               # 3 x 50 um polyimide between P and S
    t_bob = 0.8e-3                                  # bobbin wall on the centre-leg side (assumption)
    layers1, layers2 = TR["layers1"], TR["layers2"]
    n_per1, n_per2 = N1 // layers1, N2 // layers2
    if arrangement == "P/2-S-P/2":
        order = [("P", n_per1), "ins", ("S", n_per2), ("S", n_per2), "ins", ("P", n_per1)]
    elif arrangement == "P-S":
        order = [("P", n_per1), ("P", n_per1), "ins", ("S", n_per2), ("S", n_per2)]
    elif arrangement == "P-S-P-S":
        order = [("P", n_per1), "ins", ("S", n_per2), "ins", ("P", n_per1), "ins", ("S", n_per2)]
    else:
        raise ValueError(arrangement)
    n_ins = sum(1 for o in order if o == "ins")
    radial_needed = layers1 * d1 + layers2 * d2 + n_ins * t_ins + t_bob + extra_spacer
    scale = 1.0
    if radial_needed > bw:
        # the design's bundle diameters (packing 0.5) do not fit radially -> compress bundles (higher packing)
        scale = (bw - n_ins * t_ins - t_bob - extra_spacer) / (layers1 * d1 + layers2 * d2)
    d1s, d2s = d1 * scale, d2 * scale
    axial_max = max(n_per1 * d1s, n_per2 * d2s)
    margin = (hw - axial_max) / 2
    regions = []
    x = T_CORE + t_bob
    for o in order:
        if o == "ins":
            x += t_ins + (extra_spacer if arrangement == "P-S" else 0.0)
            continue
        w, n = o
        d = d1s if w == "P" else d2s
        y0 = T_CORE + (hw - n * d) / 2
        I = n * 1.0 if w == "P" else -n * (N1 / N2) * 1.0      # I1 = 1 A reference, ampere-turn balance
        regions.append(Rect(x, y0, x + d, y0 + n * d, I=I, name=f"{w}{n}"))
        x += d
    info = dict(arrangement=arrangement, d1_mm=d1 * 1e3, d2_mm=d2 * 1e3, radial_needed_mm=radial_needed * 1e3,
                bw_mm=bw * 1e3, bundle_scale=scale, packing_equiv=0.5 / scale ** 2, margin_mm=margin * 1e3,
                margin_design_mm=6.0, n_per_layer=(n_per1, n_per2), extra_spacer_mm=extra_spacer * 1e3,
                fits_axially=margin >= 0, lw=lw, bw=bw, hw=hw)
    return regions, info


def solve_window(bw, hw, regions, h):
    s = FDMagnetostatic(bw + 2 * T_CORE, hw + 2 * T_CORE, h)
    s.add(Rect(0, 0, bw + 2 * T_CORE, hw + 2 * T_CORE, mu_r=MU_CORE))
    s.add(Rect(T_CORE, T_CORE, T_CORE + bw, T_CORE + hw, mu_r=1.0))
    for r in regions:
        s.add(r)
    s.solve()
    return s


def litz_fr(s, regions, winding, f, n_strands, d_strand=0.1e-3):
    """Strand-level proximity + skin loss from the FD field inside the litz layer rectangles."""
    Bx, By, Hx, Hy = s.fields()
    Fs, G = round_wire_factors(d_strand, f, T_CU)
    a = d_strand / 2
    Pdc = Pprox = 0.0
    for r in regions:
        if not r.name.startswith(winding):
            continue
        n_turns = int(r.name[1:])
        I_turn = abs(r.I) / n_turns                           # current per turn (A, rms reference)
        iy, ix = s.region_cells(r)
        H2 = (Hx[iy, ix] ** 2 + Hy[iy, ix] ** 2)              # (A/m)^2 per cell, rms reference current
        n_cells = H2.size
        strands_per_cell = n_turns * n_strands / n_cells
        Pprox += float(np.sum(strands_per_cell * G * 2.0 * H2))     # peak^2 = 2 rms^2
        Pdc += n_turns * I_turn ** 2 * rho_cu(T_CU) / (n_strands * math.pi * a ** 2) * Fs
    Pdc0 = Pdc / Fs
    return (Pdc + Pprox) / Pdc0, Fs, Pprox / Pdc0


def one_d_litz_fr(regions, order_names, f, hw_eff, n_strands_P, n_strands_S):
    """
    1-D (Dowell-type field, Sullivan/Ferreira strand loss) estimate: the tangential field ramps linearly across
    each layer between the cumulative ampere-turn values on its faces, divided by the winding height hw_eff.
    """
    Fs_P, G_P = round_wire_factors(0.1e-3, f, T_CU)
    out = {}
    for wname, n_s in (("P", n_strands_P), ("S", n_strands_S)):
        Pdc = Pprox = 0.0
        H = 0.0
        for r in regions:                       # regions are ordered from the centre leg outward
            Ha = H
            H += r.I / hw_eff
            Hb = H
            if not r.name.startswith(wname):
                continue
            n_turns = int(r.name[1:]); I_turn = abs(r.I) / n_turns
            meanH2 = (Ha ** 2 + Ha * Hb + Hb ** 2) / 3
            Pprox += n_turns * n_s * G_P * 2 * meanH2
            Pdc += n_turns * I_turn ** 2 * rho_cu(T_CU) / (n_s * math.pi * (0.05e-3) ** 2)
        out[wname] = 1.0 * Fs_P + Pprox / Pdc
    return out


def wound_study():
    log("\n== 2. Wound E65/32/27 transformer (28:14 litz) ==")
    out = {}
    N1, N2 = TR["N1"], TR["N2"]
    # --- leakage breakdown for the design arrangement: closed forms vs FD with and without axial margins
    regions, info = wound_geometry("P/2-S-P/2")
    c = mag.CORES["E65/32/27"]
    d1, d2 = regions[0].x1 - regions[0].x0, regions[1].x1 - regions[1].x0
    t_ins = 3 * 50e-6
    b_wind = max(r.y1 for r in regions) - min(r.y0 for r in regions)
    L_1d_hw = 2 * MU0 * (N1 / 2) ** 2 * c["lw"] / c["hw"] * (t_ins + (d1 + d2) / 3)
    L_1d_b = L_1d_hw * c["hw"] / b_wind
    full = [Rect(r.x0, T_CORE, r.x1, T_CORE + c["hw"], I=r.I, name=r.name) for r in regions]
    s_full = solve_window(c["bw"], c["hw"], full, 0.05e-3)
    L_fd_full = s_full.inductance(1.0, c["lw"])[0]
    out["leakage_breakdown_P/2-S-P/2"] = dict(
        design_formula_uH=TR["Llk"] * 1e6,
        one_d_actual_layers_full_window_height_uH=L_1d_hw * 1e6,
        one_d_actual_layers_winding_height_uH=L_1d_b * 1e6,
        fd_full_height_layers_uH=L_fd_full * 1e6,
        winding_height_mm=b_wind * 1e3, window_height_mm=c["hw"] * 1e3, d1_mm=d1 * 1e3, d2_mm=d2 * 1e3,
        note="design formula: h_ins = 1 mm, full window height, /4 for interleaving; 1-D: two P/2-S/2 sections "
             "mu0 (N1/2)^2 lw/b (t_ins + (d1+d2)/3) each; FD full-height layers must match the 1-D full-window value")
    log(f"  leakage breakdown: design formula {TR['Llk']*1e6:.2f} uH | 1-D actual layers, b = hw: {L_1d_hw*1e6:.2f} uH | "
        f"1-D with winding height {b_wind*1e3:.1f} mm: {L_1d_b*1e6:.2f} uH | FD full-height layers: {L_fd_full*1e6:.2f} uH")
    for arr, L_ref, h in (("P/2-S-P/2", TR["Llk"], 0.05e-3), ("P-S", DESIGN["transformer_integrated_leakage"]["Llk"], 0.1e-3),
                          ("P-S-P-S", None, 0.1e-3)):
        regions, info = wound_geometry(arr)
        s = solve_window(info["bw"], info["hw"], regions, h)
        Lf, Ls = s.inductance(1.0, info["lw"])
        res = dict(info=info, Llk_fd_uH=Lf * 1e6, Llk_fd_source_form_uH=Ls * 1e6, Llk_analytic_uH=(L_ref * 1e6 if L_ref else None),
                   discrepancy_pct=(100 * (Lf / L_ref - 1) if L_ref else None), h_mm=h * 1e3)
        for f in (100e3, 300e3):
            Fr1, Fs1, pr1 = litz_fr(s, regions, "P", f, TR["strands1"])
            Fr2, Fs2, pr2 = litz_fr(s, regions, "S", f, TR["strands2"])
            res[f"Fr1_{int(f/1e3)}kHz"] = Fr1; res[f"Fr2_{int(f/1e3)}kHz"] = Fr2
            res[f"Fs_strand_{int(f/1e3)}kHz"] = Fs1
        # Dowell comparison: equivalent foil layers (bundle layers as foils with porosity = copper fraction)
        d_eq = skin_depth(FS, T_CU)
        m1 = TR["layers1"] if arr == "P-S" else max(1, TR["layers1"] / 2)
        res["Fr1_design_litz_dowell"] = mag.litz_rac_ratio(0.1e-3, d_eq, TR["strands1"], m1)
        b_w = max(r.y1 for r in regions) - min(r.y0 for r in regions)
        for f in (100e3, 300e3):
            od = one_d_litz_fr(regions, None, f, b_w, TR["strands1"], TR["strands2"])
            res[f"Fr1_1D_sullivan_{int(f/1e3)}kHz"] = od["P"]; res[f"Fr2_1D_sullivan_{int(f/1e3)}kHz"] = od["S"]
        res["Fr2_design_litz_dowell"] = mag.litz_rac_ratio(0.1e-3, d_eq, TR["strands2"], TR["layers2"] if arr == "P-S" else max(1, TR["layers2"] / 2))
        res["P_cu_100kHz_W"] = I1_RMS ** 2 * TR["R1dc"] * res["Fr1_100kHz"] + I2_RMS ** 2 * TR["R2dc"] * res["Fr2_100kHz"]
        res["P_cu_design_W"] = TR["P_cu"]
        Bx, By, Hx, Hy = s.fields()
        Hmag = np.hypot(Hx, Hy) * I1_RMS * math.sqrt(2)                # scaled to the nominal peak current
        res["H_peak_window_kA_per_m"] = float(Hmag.max() / 1e3)
        res["H_analytic_1D_kA_per_m"] = (N1 / 2 if arr != "P-S" else N1) * I1_RMS * math.sqrt(2) / info["hw"] / 1e3
        out[arr] = res
        log(f"  {arr:10s} h={h*1e3:.2f} mm  Llk_fd={Lf*1e6:.3f} uH  (source form {Ls*1e6:.3f})  analytic={L_ref*1e6 if L_ref else float('nan'):.3f} uH  "
            f"disc={res['discrepancy_pct'] if res['discrepancy_pct'] is not None else float('nan'):+.1f} %")
        log(f"             Fr1 100/300 kHz = {res['Fr1_100kHz']:.3f}/{res['Fr1_300kHz']:.3f}   Fr2 = {res['Fr2_100kHz']:.3f}/{res['Fr2_300kHz']:.3f}   "
            f"design (strand Dowell) Fr1={res['Fr1_design_litz_dowell']:.3f} Fr2={res['Fr2_design_litz_dowell']:.3f}   "
            f"1-D Sullivan Fr1/Fr2@100k={res['Fr1_1D_sullivan_100kHz']:.3f}/{res['Fr2_1D_sullivan_100kHz']:.3f}   Pcu={res['P_cu_100kHz_W']:.2f} W (design {TR['P_cu']:.2f})")
        log(f"             radial need {info['radial_needed_mm']:.2f} mm vs window {info['bw_mm']:.1f} mm -> bundle scale {info['bundle_scale']:.3f} "
            f"(packing {info['packing_equiv']:.2f}); axial margin {info['margin_mm']:.1f} mm (design states 6 mm)")
        if arr == "P/2-S-P/2":
            field_figure(s, regions, info["bw"], info["hw"], "fig_field_wound_interleaved.png",
                         "E65/32/27 window, P/2-S-P/2 litz,\n|H| at nominal peak current (2-D FD)", I1_RMS * math.sqrt(2))
            # mesh convergence of the leakage number for the main case
            conv = []
            for hh in (0.2e-3, 0.1e-3, 0.05e-3):
                ss = solve_window(info["bw"], info["hw"], regions, hh)
                conv.append(dict(h_mm=hh * 1e3, Llk_uH=ss.inductance(1.0, info["lw"])[0] * 1e6))
            res["mesh_convergence"] = conv
            log("             mesh convergence: " + ", ".join(f"h={c['h_mm']:.2f}: {c['Llk_uH']:.3f} uH" for c in conv))
        if arr == "P-S":
            field_figure(s, regions, info["bw"], info["hw"], "fig_field_wound_noninterleaved.png",
                         "E65/32/27 window, P-S (non-interleaved) litz,\n|H| at nominal peak current (2-D FD)", I1_RMS * math.sqrt(2))
    # leakage sensitivity to the P-S insulation thickness (interleaved)
    sens = []
    for t_extra in (0.0, 0.25e-3, 0.5e-3, 1.0e-3):
        regions, info = wound_geometry("P-S", extra_spacer=t_extra)
        s = solve_window(info["bw"], info["hw"], regions, 0.1e-3)
        sens.append(dict(extra_spacer_mm=t_extra * 1e3, Llk_uH=s.inductance(1.0, info["lw"])[0] * 1e6,
                         bundle_scale=info["bundle_scale"]))
    out["spacer_sensitivity_P-S"] = sens
    log("  P-S spacer sensitivity: " + ", ".join(f"+{x['extra_spacer_mm']:.2f} mm -> {x['Llk_uH']:.2f} uH (scale {x['bundle_scale']:.3f})" for x in sens))
    return out


def field_figure(s, regions, bw, hw, fname, title, I_scale):
    Bx, By, Hx, Hy = s.fields()
    H = np.hypot(Hx, Hy) * I_scale / 1e3
    X = s.xc * 1e3; Y = s.yc * 1e3
    fig, ax = plt.subplots(figsize=(4.8, 7.5) if hw > bw else (8.5, 4.6))
    pm = ax.pcolormesh(X, Y, H, cmap="viridis", shading="auto", rasterized=True)
    cb = fig.colorbar(pm, ax=ax, fraction=0.046, pad=0.03); cb.set_label("|H| (kA/m, peak)")
    Xn = np.arange(s.nx + 1) * s.h * 1e3; Yn = np.arange(s.ny + 1) * s.h * 1e3
    Az = s.A * I_scale
    lv = np.linspace(Az.min(), Az.max(), 25)
    ax.contour(Xn, Yn, Az, levels=lv, colors="white", linewidths=0.5, alpha=0.8)
    for r in regions:
        ax.add_patch(Rectangle((r.x0 * 1e3, r.y0 * 1e3), (r.x1 - r.x0) * 1e3, (r.y1 - r.y0) * 1e3, fill=False,
                               ec=C2 if r.name.startswith("P") else C3, lw=1.0))
    ax.add_patch(Rectangle((T_CORE * 1e3, T_CORE * 1e3), bw * 1e3, hw * 1e3, fill=False, ec="black", lw=1.0, ls="--"))
    ax.set_aspect("equal"); ax.set_xlabel("x (mm) - radial, centre leg at left"); ax.set_ylabel("y (mm) - axial")
    ax.set_title(title + "\nwhite: flux lines (A_z contours); orange: primary,\naqua: secondary; dashed: window edge", fontsize=8, wrap=True)
    fig.tight_layout(); fig.savefig(os.path.join(RES, fname), dpi=160); plt.close(fig)


# ---------------------------------------------------------------------------
# 3. Planar alternative (ELP 64/10/50 class core, 6-layer 2 oz PCB windings)
# ---------------------------------------------------------------------------
PLANAR_CORE = dict(name="ELP64/10/50 (planar E64) pair", Ae=519e-6, Ve=40.7e-6, le=79.9e-3, bw=21.8e-3, hw=10.2e-3,
                   leg=10.2e-3, depth=50.8e-3, A=64e-3, H=20.4e-3,
                   note="catalogue values recalled from the Ferroxcube planar E64/10/50 data; verify before use")
PCB = dict(t_cu=70e-6, t_ps=0.42e-3, t_pp=0.21e-3, gap_boards=0.49e-3, margin=1.0e-3, s_track=0.5e-3,
           note="2 oz copper, 0.42 mm dielectric between P and S layers (solid insulation for 800 V class),"
                " 0.21 mm between same-winding layers, 0.49 mm between stacked boards; h = 0.035 mm snaps these")
COST = dict(E65_half=5.0, ELP64_half=8.0, litz294_per_m=3.0, litz588_per_m=5.0, bobbin_tape_labour=18.0,
            pcb6L_2oz_per_cm2=0.6, pcb_setup=5.0, planar_assembly=10.0,
            note="order-of-magnitude 2026 small-quantity estimates, not quotations")


def planar_geometry(n_cores, N1, N2, k_boards, layer_order, t_ps=None):
    """Layer order per board e.g. 'PSPSPP'; turns per layer split as evenly as possible."""
    pc = PLANAR_CORE
    t_ps = PCB["t_ps"] if t_ps is None else t_ps
    bw, hw = pc["bw"], pc["hw"]
    nP = layer_order.count("P"); nS = layer_order.count("S")

    def split(N, n):
        base = N // n; r = N % n
        return [base + 1 if i < r else base for i in range(n)]
    tP, tS = split(N1, nP), split(N2, nS)
    # board thickness
    thick = len(layer_order) * PCB["t_cu"]
    for a, b in zip(layer_order[:-1], layer_order[1:]):
        thick += t_ps if a != b else PCB["t_pp"]
    stack = k_boards * thick + (k_boards - 1) * PCB["gap_boards"]
    fits = stack <= hw - 2 * 0.5e-3
    y = T_CORE + (hw - stack) / 2
    regions = []
    widths = {}
    iP = iS = 0
    for b in range(k_boards):
        for li, w in enumerate(layer_order):
            n = tP[iP] if w == "P" else tS[iS]
            if w == "P": iP = (iP + 1) % nP
            else: iS = (iS + 1) % nS
            wt = (bw - 2 * PCB["margin"] - (n - 1) * PCB["s_track"]) / n
            widths[w] = min(widths.get(w, 1.0), wt)
            I_turn = (1.0 if w == "P" else -(N1 / N2)) / k_boards
            for t in range(n):
                x0 = T_CORE + PCB["margin"] + t * (wt + PCB["s_track"])
                regions.append(Rect(x0, y, x0 + wt, y + PCB["t_cu"], I=I_turn, name=f"{w}1"))
            y += PCB["t_cu"]
            if li < len(layer_order) - 1:
                y += t_ps if layer_order[li + 1] != w else PCB["t_pp"]
        y += PCB["gap_boards"]
    lw = 2 * (pc["leg"] + pc["depth"] * n_cores) + math.pi * bw
    info = dict(n_cores=n_cores, N1=N1, N2=N2, k_boards=k_boards, layer_order=layer_order, board_mm=thick * 1e3,
                stack_mm=stack * 1e3, fits=fits, wP_mm=widths["P"] * 1e3, wS_mm=widths["S"] * 1e3, lw=lw,
                bw=bw, hw=hw, Ae=pc["Ae"] * n_cores, Ve=pc["Ve"] * n_cores, t_ps_mm=t_ps * 1e3)
    return regions, info


def planar_variant(label, n_cores, N1, N2, k_boards, layer_order, make_fig=False, t_ps=None):
    regions, info = planar_geometry(n_cores, N1, N2, k_boards, layer_order, t_ps)
    h = 0.035e-3
    if not info["fits"]:
        log(f"  {label:34s} stack {info['stack_mm']:.2f} mm exceeds the {info['hw']*1e3:.1f} mm window: not solved (infeasible)")
        return dict(variant=label, type="planar", **{k: v for k, v in info.items() if k not in ("bw", "hw")}, Llk_uH=float("nan"),
                    P_cu_W=float("nan"), P_core_W=float("nan"), P_total_W=float("nan"), volume_cm3=float("nan"), cost_EUR=float("nan"))
    s = solve_window(info["bw"], info["hw"], regions, h)
    Lf, Ls = s.inductance(1.0, info["lw"])
    P_rects = [r for r in regions if r.name.startswith("P")]
    S_rects = [r for r in regions if r.name.startswith("S")]
    res = dict(variant=label, type="planar", **{k: v for k, v in info.items() if k not in ("bw", "hw")},
               Llk_uH=Lf * 1e6, Llk_source_form_uH=Ls * 1e6, h_mm=h * 1e3)
    rho = rho_cu(T_CU)
    A_P = info["wP_mm"] * 1e-3 * PCB["t_cu"] * k_boards
    A_S = info["wS_mm"] * 1e-3 * PCB["t_cu"] * k_boards
    R1 = rho * N1 * info["lw"] / A_P; R2 = rho * N2 * info["lw"] / A_S
    res.update(R1dc_mOhm=R1 * 1e3, R2dc_mOhm=R2 * 1e3, J1_A_per_mm2=I1_RMS / A_P / 1e6, J2_A_per_mm2=I2_RMS / A_S / 1e6)
    for f in (100e3, 300e3):
        res[f"Fr1_{int(f/1e3)}kHz"] = foil_winding_fr(s, P_rects, f, vertical=False)
        res[f"Fr2_{int(f/1e3)}kHz"] = foil_winding_fr(s, S_rects, f, vertical=False)
    # Dowell for the same layer count (uniform-foil assumption, porosity = copper fraction of the layer)
    por = (info["wP_mm"] * 1e-3 * (N1 / layer_order.count("P"))) / info["bw"]
    res["Fr1_dowell_equiv"] = dowell_fr(PCB["t_cu"], skin_depth(FS, T_CU), layer_order.count("P") / 2 if "S" in layer_order[1:-1] else layer_order.count("P"), por)
    res["P_cu_W"] = I1_RMS ** 2 * R1 * res["Fr1_100kHz"] + I2_RMS ** 2 * R2 * res["Fr2_100kHz"]
    Bpk = V1 / (4 * FS * N1 * info["Ae"])
    res["Bpk_T"] = Bpk
    res["P_core_W"] = mag.steinmetz_loss("3C95", FS, Bpk, info["Ve"], mag.igse_correction("3C95", 1.0))
    res["P_total_W"] = res["P_cu_W"] + res["P_core_W"]
    pc = PLANAR_CORE
    core_box = pc["A"] * pc["H"] * pc["depth"] * n_cores
    res["volume_cm3"] = core_box * 1.3 * 1e6                 # +30 % for PCB overhang / terminations
    pcb_area_cm2 = (pc["A"] + 10e-3) * (pc["depth"] * n_cores + 2 * (pc["bw"] + 5e-3)) * 1e4
    res["cost_EUR"] = 2 * n_cores * COST["ELP64_half"] + k_boards * (pcb_area_cm2 * COST["pcb6L_2oz_per_cm2"] + COST["pcb_setup"]) + COST["planar_assembly"]
    res["Llk_over_Lext_pct"] = 100 * Lf / L_EXT
    log(f"  {label:34s} Llk={Lf*1e6:.3f} uH  Fr1/Fr2@100k={res['Fr1_100kHz']:.2f}/{res['Fr2_100kHz']:.2f}  @300k={res['Fr1_300kHz']:.2f}/{res['Fr2_300kHz']:.2f}  "
        f"J1/J2={res['J1_A_per_mm2']:.0f}/{res['J2_A_per_mm2']:.0f} A/mm2  Pcu={res['P_cu_W']:.1f} W  Pcore={res['P_core_W']:.1f} W  "
        f"B={Bpk:.3f} T  vol={res['volume_cm3']:.0f} cm3  fits={info['fits']}  stack={info['stack_mm']:.2f}/{info['hw']*1e3:.1f} mm")
    if make_fig:
        field_figure(s, regions, info["bw"], info["hw"], "fig_field_planar.png",
                     f"Planar E64/10/50 x{n_cores}, {k_boards} x 6-layer 2 oz boards ({layer_order}), |H| at nominal peak (2-D FD)",
                     I1_RMS * math.sqrt(2))
    return res


def wound_variant_row(label, arr, res_w):
    c = mag.CORES["E65/32/27"]
    core_box = 65e-3 * 64.6e-3 * 27e-3
    N1, N2 = TR["N1"], TR["N2"]
    cost = 4 * COST["E65_half"] + N1 * c["lw"] * COST["litz294_per_m"] + N2 * c["lw"] * COST["litz588_per_m"] + COST["bobbin_tape_labour"]
    return dict(variant=label, type="wound", arrangement=arr, Llk_uH=res_w["Llk_fd_uH"], Fr1_100kHz=res_w["Fr1_100kHz"],
                Fr2_100kHz=res_w["Fr2_100kHz"], Fr1_300kHz=res_w["Fr1_300kHz"], Fr2_300kHz=res_w["Fr2_300kHz"],
                P_cu_W=res_w["P_cu_100kHz_W"], P_core_W=TR["P_core"], P_total_W=res_w["P_cu_100kHz_W"] + TR["P_core"],
                Bpk_T=TR["Bpk"], volume_cm3=core_box * 1.15 * 1e6, cost_EUR=cost, Llk_over_Lext_pct=100 * res_w["Llk_fd_uH"] * 1e-6 / L_EXT,
                fits=res_w["info"]["fits_axially"], J1_A_per_mm2=I1_RMS / TR["A1"] / 1e6, J2_A_per_mm2=I2_RMS / TR["A2"] / 1e6,
                note=f"bundle scale {res_w['info']['bundle_scale']:.3f} to fit radially")


def pareto(rows):
    keys = ["variant", "type", "Llk_uH", "Llk_over_Lext_pct", "Fr1_100kHz", "Fr2_100kHz", "Fr1_300kHz", "Fr2_300kHz", "J1_A_per_mm2",
            "J2_A_per_mm2", "P_cu_W", "P_core_W", "P_total_W", "Bpk_T", "volume_cm3", "cost_EUR", "fits"]
    with open(os.path.join(RES, "pareto_variants.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    # non-dominated set on (P_total, volume, Llk) minimisation among feasible variants
    feas = [r for r in rows if r["fits"]]
    for r in rows:
        r["pareto_optimal"] = bool(r["fits"]) and not any(
            (o is not r) and o["P_total_W"] <= r["P_total_W"] and o["volume_cm3"] <= r["volume_cm3"] and o["Llk_uH"] <= r["Llk_uH"]
            and (o["P_total_W"] < r["P_total_W"] or o["volume_cm3"] < r["volume_cm3"] or o["Llk_uH"] < r["Llk_uH"]) for o in feas)
    fig, axs = plt.subplots(1, 2, figsize=(10, 4.4))
    for ax, ykey, ylab in ((axs[0], "volume_cm3", "volume incl. winding (cm3)"), (axs[1], "Llk_uH", "leakage inductance (uH, HV side)")):
        for i, r in enumerate(feas):
            col = C1 if r["type"] == "wound" else C2
            ax.scatter(r["P_total_W"], r[ykey], s=90 if r["pareto_optimal"] else 45, color=col, marker="o",
                       edgecolors="black" if r["pareto_optimal"] else col, linewidths=1.2, zorder=3)
            ax.annotate(r["variant"].split(" ")[0], (r["P_total_W"], r[ykey]), textcoords="offset points",
                        xytext=(6, 5 if i % 2 == 0 else -11), fontsize=8)
        ax.set_xlabel("total transformer loss at nominal point (W)"); ax.set_ylabel(ylab); ax.grid(True, alpha=0.3)
    axs[1].set_yscale("log")
    axs[0].scatter([], [], color=C1, label="wound litz E65"); axs[0].scatter([], [], color=C2, label="planar ELP64 PCB")
    axs[0].scatter([], [], facecolors="none", edgecolors="black", label="Pareto-optimal (loss, volume, Llk)")
    axs[0].legend(fontsize=7, loc="upper right")
    fig.suptitle("Wound vs planar variants: loss - volume - leakage (2-D FD, nominal 800 V / 400 V / 6.6 kW); labels: see pareto_variants.csv", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(RES, "fig_pareto.png"), dpi=150); plt.close(fig)


def main():
    val_rows, dow = validate()
    wound = wound_study()
    log("\n== 3. Planar PCB-winding alternative ==")
    log(f"  core: {PLANAR_CORE['name']}  Ae={PLANAR_CORE['Ae']*1e6:.0f} mm2  window {PLANAR_CORE['bw']*1e3:.1f} x {PLANAR_CORE['hw']*1e3:.1f} mm  ({PLANAR_CORE['note']})")
    planar_rows = [
        planar_variant("P1 1xELP64 30:15 3 boards PSPSPP", 1, 30, 15, 3, "PSPSPP"),
        planar_variant("P2 2xELP64 16:8 3 boards PSPSPP", 2, 16, 8, 3, "PSPSPP", make_fig=True),
        planar_variant("P3 2xELP64 16:8 2 boards PSPSPP", 2, 16, 8, 2, "PSPSPP"),
        planar_variant("P4 2xELP64 16:8 3 boards PPPPSS", 2, 16, 8, 3, "PPPPSS"),
        planar_variant("P5 2xELP64 16:8 4 boards PSPSPP 0.21mm P-S (basic ins.)", 2, 16, 8, 4, "PSPSPP", t_ps=0.21e-3),
        planar_variant("P6 2xELP64 16:8 4 boards PSPSPP 0.42mm P-S", 2, 16, 8, 4, "PSPSPP"),
    ]
    rows = [wound_variant_row("W1 E65 P/2-S-P/2 (design)", "P/2-S-P/2", wound["P/2-S-P/2"]),
            wound_variant_row("W2 E65 P-S", "P-S", wound["P-S"]),
            wound_variant_row("W3 E65 P-S-P-S", "P-S-P-S", wound["P-S-P-S"])] + planar_rows
    log("\n== 4. Pareto study ==")
    pareto(rows)
    for r in rows:
        log(f"  {r['variant']:60s} P={r['P_total_W']:6.1f} W  V={r['volume_cm3']:6.0f} cm3  Llk={r['Llk_uH']:7.3f} uH  cost~{r['cost_EUR']:5.0f} EUR  "
            f"fits={r['fits']}  pareto={r['pareto_optimal']}")
    wall = time.time() - T0
    results = dict(validation=dict(leakage_convergence=val_rows, dowell=dow), wound=wound, planar=planar_rows, pareto=rows,
                   planar_core=PLANAR_CORE, pcb_stack=PCB, cost_model=COST, wall_s=wall,
                   notes=["2-D planar approximation of the window cross-section; no 3-D end effects; conductors as uniform-J rectangles",
                          "AC resistance from the magnetostatic (DC) field distribution (Dowell/Ferreira assumption); fundamental only",
                          "no FEM package available; in-house finite-difference solver validated against closed forms"])
    with open(os.path.join(RES, "fem_results.json"), "w") as f:
        json.dump(results, f, indent=1, default=float)
    with open(os.path.join(RES, "run_log.txt"), "w") as f:
        f.write("\n".join(LOG) + "\n")
    import scipy
    head = None
    try:
        with open(os.path.join(REPO, ".git", "HEAD")) as f:
            ref = f.read().strip()
        if ref.startswith("ref: "):
            p = os.path.join(REPO, ".git", ref[5:])
            if os.path.exists(p):
                head = open(p).read().strip()
            else:
                with open(os.path.join(REPO, ".git", "packed-refs")) as f:
                    for line in f:
                        if line.strip().endswith(ref[5:]):
                            head = line.split()[0]
        else:
            head = ref
    except OSError:
        pass
    prov = dict(module="Advanced_Research_2026/FEM_Magnetics", script="run_fem_magnetics.py", python=platform.python_version(),
                numpy=np.__version__, scipy=scipy.__version__, matplotlib=matplotlib.__version__, git_commit=head,
                inputs={os.path.relpath(DESIGN_PATH, REPO): sha256(DESIGN_PATH),
                        "SiC_6k6_Industrial_DAB/dabtools/dab/magnetics.py": sha256(mag.__file__),
                        "Advanced_Research_2026/FEM_Magnetics/fd_magnetostatic.py": sha256(os.path.join(HERE, "fd_magnetostatic.py"))},
                wall_time_s=wall, generated=time.strftime("%Y-%m-%d %H:%M:%S"), deterministic=True,
                outputs=sorted(os.listdir(RES)))
    with open(os.path.join(HERE, "provenance.json"), "w") as f:
        json.dump(prov, f, indent=1)
    log(f"\nwall time {wall:.1f} s; results in {RES}")


if __name__ == "__main__":
    main()
