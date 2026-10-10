#!/usr/bin/env python3
"""
Parasitic_Extraction: closed-form partial-inductance extraction of the DAB power-board commutation loops
and one gate loop from the generated KiCad board geometry (no field solver, no measurement).

Usage:  python3 <path>/extract_parasitics.py [--board <file.kicad_pcb>]
        default board: SiC_6k6_Industrial_DAB/07_KiCad_Schematics/SiC_DAB_6k6.kicad_pcb

The board file is parsed with a small s-expression reader (numpy/scipy/matplotlib only); when the KiCad
python module `pcbnew` is importable the pad positions are cross-checked against it (max deviation reported).

Formulae (SI units):
  rectangular bar, partial self-inductance (Hoer & Love 1965 / Ruehli 1972, l >> w + t):
      L_p = mu0 l / (2 pi) * [ ln(2 l / (w + t)) + 1/2 + 0.2235 (w + t) / l ]
  two parallel filaments of length l at centre distance d (Grover), partial mutual inductance:
      M   = mu0 l / (2 pi) * [ ln( l/d + sqrt(1 + (l/d)^2) ) - sqrt(1 + (d/l)^2) + d/l ]
  go-and-return pair of bars:  L_loop = 2 (L_p - M)
  microstrip over a reference plane at height h (image current, w >> h):  L = mu0 h l / (w + 2 h)
  parallel-plane pair (spacing h, length l, effective width w):            L = mu0 h l / w
  via / pin through the stack (round conductor, radius r, length l):      L = mu0 l / (2 pi) * [ ln(2 l / r) - 3/4 ]
  loop inductance = sum of partial self-inductances of all segments in series - 2 sum of partial mutuals of
  anti-parallel neighbour segments (only the dominant pairs are included; others are neglected -> stated).
"""
import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DAB = os.path.join(REPO, "SiC_6k6_Industrial_DAB")
sys.path.insert(0, DAB)
RES = os.path.join(HERE, "results")
os.makedirs(RES, exist_ok=True)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch

from dabtools.dab.devices import DEVICES

MU0 = 4e-7 * math.pi
T0 = time.time()
C1, C2, C3, C4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
LOG = []


def log(s=""):
    print(s)
    LOG.append(s)


# ---------------------------------------------------------------------------
# Stack-up (SiC_6k6_Industrial_DAB/17_Manufacturing/stackup.md) -> copper depth below the top surface (mm)
# ---------------------------------------------------------------------------
STACK = [("F.Cu", 0.070), ("prepreg", 0.20), ("In1.Cu", 0.070), ("core", 0.50), ("In2.Cu", 0.070), ("prepreg", 0.50),
         ("In3.Cu", 0.070), ("core", 0.50), ("In4.Cu", 0.070), ("prepreg", 0.20), ("B.Cu", 0.070)]
DEPTH = {}
z = 0.0
for name, t in STACK:
    if name.endswith(".Cu"):
        DEPTH[name] = z + t / 2          # mid-copper depth
    z += t
BOARD_T = z
PLANE_NETS = {"HV_P": ["In2.Cu", "In4.Cu"], "HV_N": ["In1.Cu", "In3.Cu", "F.Cu", "B.Cu"],
              "LV_P": ["In2.Cu", "In4.Cu"], "LV_N": ["In1.Cu", "In3.Cu", "F.Cu", "B.Cu"]}

# Package / component assumptions (typical values, flagged; not measured)
ASSUME = dict(
    to247_lead_len_mm=15.0,      # effective lead + lead-frame length from die to the board surface (sensitivity 10-20 mm)
    to247_lead_w_mm=1.5, to247_lead_t_mm=0.6, to247_pin_pitch_mm=2.54,
    to247_pin_drill_mm=1.5,
    cap_esl_nH=1.2,              # 2220 MLCC / 100 nF 1 kV: typical ESL quoted by manufacturers ~1-1.5 nH
    via_drill_mm=0.4, via_dia_mm=0.8,
    gate_trace_w_mm=0.5,         # HV_GATE / LV_GATE net class width (dabtools/kicad_dab/gen_pcb_dab.py track_width)
    gate_pair_spacing_mm=1.0,    # centre spacing of the go/return gate traces (unrouted -> sensitivity 0.5-3 mm)
    ciss_nF=dict(C3M0032120K=1.9, C3M0016120K=3.4),   # datasheet-typical input capacitance, recalled, verified=False
    rg_int_ohm=dict(C3M0032120K=2.6, C3M0016120K=1.5),  # datasheet-typical internal gate resistance, recalled, verified=False
    driver_rout_ohm=1.0,
    t_fall_ns=[5.0, 10.0, 20.0, 40.0],   # hard turn-off current fall time assumptions (SiC with Rg_off 1.5 Ohm: 5-20 ns class)
    note="all entries are assumptions or recalled datasheet-typical values; none is measured",
)


# ---------------------------------------------------------------------------
# s-expression reader for .kicad_pcb
# ---------------------------------------------------------------------------
_TOK = re.compile(r'"(?:[^"\\]|\\.)*"|\(|\)|[^\s()"]+')


def parse_sexp(text):
    stack = [[]]
    for tok in _TOK.findall(text):
        if tok == "(":
            stack.append([])
        elif tok == ")":
            node = stack.pop()
            stack[-1].append(node)
        else:
            if tok.startswith('"'):
                tok = tok[1:-1]
            stack[-1].append(tok)
    return stack[0]


def child(node, key):
    for c in node:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return None


def children(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def fnum(x):
    return float(x)


def load_board(path):
    with open(path) as f:
        tree = parse_sexp(f.read())
    root = tree[0]
    nets = {}
    for n in children(root, "net"):
        nets[n[1]] = n[2] if len(n) > 2 else ""
    fps = {}
    for fp in children(root, "footprint"):
        at = child(fp, "at")
        x0, y0 = fnum(at[1]), fnum(at[2])
        rot = fnum(at[3]) if len(at) > 3 else 0.0
        ref = val = None
        for t in children(fp, "fp_text"):
            if t[1] == "reference": ref = t[2]
            if t[1] == "value": val = t[2]
        for pr in children(fp, "property"):
            if pr[1] == "Reference": ref = pr[2]
            if pr[1] == "Value": val = pr[2]
        pads = []
        c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        for p in children(fp, "pad"):
            pat = child(p, "at")
            px, py = fnum(pat[1]), fnum(pat[2])
            # KiCad: y axis down, footprint rotation counter-clockwise on screen
            ax, ay = x0 + px * c + py * s, y0 - px * s + py * c
            size = child(p, "size")
            drill = child(p, "drill")
            net = child(p, "net")
            layers = child(p, "layers")
            pads.append(dict(number=p[1], type=p[2], shape=p[3], x=ax, y=ay, w=fnum(size[1]), h=fnum(size[2]),
                             drill=(fnum(drill[1]) if drill and len(drill) > 1 and re.match(r"^[0-9.]+$", drill[1]) else 0.0),
                             net=(net[2] if net and len(net) > 2 else ""), layers=layers[1:] if layers else []))
        fps[ref] = dict(ref=ref, value=val, lib=fp[1], x=x0, y=y0, rot=rot, pads=pads)
    zones = []
    for zn in children(root, "zone"):
        nn = child(zn, "net_name")
        layer = child(zn, "layer")
        pts = []
        poly = child(zn, "polygon")
        if poly:
            for xy in children(child(poly, "pts"), "xy"):
                pts.append((fnum(xy[1]), fnum(xy[2])))
        if pts:
            xs, ys = zip(*pts)
            zones.append(dict(net=nn[1] if nn else "", layer=layer[1] if layer else "", x0=min(xs), y0=min(ys), x1=max(xs), y1=max(ys)))
    segs = []
    for sg in children(root, "segment"):
        a, b = child(sg, "start"), child(sg, "end")
        segs.append(dict(net=nets.get(child(sg, "net")[1], ""), layer=child(sg, "layer")[1], width=fnum(child(sg, "width")[1]),
                         x0=fnum(a[1]), y0=fnum(a[2]), x1=fnum(b[1]), y1=fnum(b[2])))
    vias = []
    for v in children(root, "via"):
        a = child(v, "at")
        vias.append(dict(net=nets.get(child(v, "net")[1], ""), x=fnum(a[1]), y=fnum(a[2]), size=fnum(child(v, "size")[1]),
                         drill=fnum(child(v, "drill")[1])))
    return dict(footprints=fps, zones=zones, segments=segs, vias=vias, nets=nets)


def crosscheck_pcbnew(path, board):
    try:
        import pcbnew
    except Exception:
        return dict(available=False)
    b = pcbnew.LoadBoard(path)
    dmax, n = 0.0, 0
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if ref not in board["footprints"]:
            continue
        mine = board["footprints"][ref]["pads"]
        for p in fp.Pads():
            same = [q for q in mine if q["number"] == p.GetNumber()]      # pad numbers may repeat (tab pads)
            if not same:
                continue
            d = min(math.hypot(p.GetPosition().x / 1e6 - q["x"], p.GetPosition().y / 1e6 - q["y"]) for q in same)
            dmax = max(dmax, d); n += 1
    return dict(available=True, version=pcbnew.Version(), pads_compared=n, max_pad_position_deviation_mm=dmax,
                tracks_in_board=len(list(b.GetTracks())))


# ---------------------------------------------------------------------------
# Partial-inductance formulae
# ---------------------------------------------------------------------------
def L_bar(l, w, t):
    """Hoer-Love / Ruehli rectangular bar partial self-inductance (H); l, w, t in m."""
    return MU0 * l / (2 * math.pi) * (math.log(2 * l / (w + t)) + 0.5 + 0.2235 * (w + t) / l)


def M_par(l, d):
    """Partial mutual inductance of two parallel filaments of equal length l at distance d (H)."""
    r = l / d
    return MU0 * l / (2 * math.pi) * (math.log(r + math.sqrt(1 + r * r)) - math.sqrt(1 + 1 / r ** 2) + 1 / r)


def L_round(l, r):
    """Straight round conductor partial self-inductance (valid for l >> r; clamped at 0 for l < ~1.1 r)."""
    return max(0.0, MU0 * l / (2 * math.pi) * (math.log(2 * l / r) - 0.75))


def L_microstrip(l, w, h):
    return MU0 * h * l / (w + 2 * h)


def L_plane_pair(l, w, h):
    return MU0 * h * l / w


# ---------------------------------------------------------------------------
# Loop geometry from the board
# ---------------------------------------------------------------------------
def pad(board, ref, net=None, number=None):
    for p in board["footprints"][ref]["pads"]:
        if (net is None or p["net"] == net) and (number is None or p["number"] == number):
            return p
    raise KeyError((ref, net, number))


def strip_rects(board, net, layer="B.Cu"):
    return [z for z in board["zones"] if z["net"] == net and z["layer"] == layer]


def commutation_loop(board, top, bot, caps, net_p, net_n, sw_net, dev, h_plane_mm=None, lead_len_mm=None, w_eff_mode="spread"):
    """
    Partial-inductance budget of the half-bridge commutation loop  C(+) -> top drain -> top source -> SW strip ->
    bottom drain -> bottom source -> C(-) -> planes.  Returns a dict with segments and totals.
    """
    A = ASSUME
    l_lead = (A["to247_lead_len_mm"] if lead_len_mm is None else lead_len_mm) * 1e-3
    w_l, t_l = A["to247_lead_w_mm"] * 1e-3, A["to247_lead_t_mm"] * 1e-3
    pT_d, pT_s = pad(board, top, net_p), pad(board, top, sw_net)
    pB_d, pB_s = pad(board, bot, sw_net), pad(board, bot, net_n)
    segs = []
    # 1. TO-247 leads: drain and source of each device, anti-parallel, 2 pitches apart (pads 2 and 4)
    L_lead = L_bar(l_lead, w_l, t_l)
    d_ds = math.hypot(pT_d["x"] - pT_s["x"], pT_d["y"] - pT_s["y"]) * 1e-3
    M_ds = M_par(l_lead, d_ds)
    for name in (f"{top} drain lead", f"{top} source lead", f"{bot} drain lead", f"{bot} source lead"):
        segs.append(dict(segment=name, formula="bar", l_mm=l_lead * 1e3, w_mm=w_l * 1e3, t_mm=t_l * 1e3, L_self_nH=L_lead * 1e9,
                         M_nH=-M_ds * 1e9, note=f"anti-parallel partner at {d_ds*1e3:.2f} mm -> -M"))
    # 2. switch-node strip on B.Cu between top source pin and bottom drain pin
    rects = strip_rects(board, sw_net)
    xa, xb = min(pT_s["x"], pB_d["x"]), max(pT_s["x"], pB_d["x"])
    bar = [z for z in rects if z["x0"] <= xa + 0.5 and z["x1"] >= xb - 0.5 and (z["y1"] - z["y0"]) < 6]
    if bar:
        zb = bar[0]
        w_s = (zb["y1"] - zb["y0"]) * 1e-3
    else:
        w_s = 3.0e-3
    l_s = (xb - xa) * 1e-3
    h_img = DEPTH["B.Cu"] - DEPTH["In4.Cu"]                   # nearest plane under the strip (In4 = power plane)
    L_s_free = L_bar(l_s, w_s, 70e-6)
    L_s_img = L_microstrip(l_s, w_s, h_img * 1e-3)
    segs.append(dict(segment=f"{sw_net} strip B.Cu", formula="bar (free) / microstrip over In4 (image)", l_mm=l_s * 1e3, w_mm=w_s * 1e3,
                     t_mm=0.07, L_self_nH=L_s_img * 1e9, M_nH=0.0, L_upper_nH=L_s_free * 1e9,
                     note=f"image plane at {h_img:.2f} mm; free-standing value {L_s_free*1e9:.1f} nH is the upper bound"))
    # 3. pins through the board to the planes (drain -> power plane In2, source -> reference plane In1)
    r_pin = A["to247_pin_drill_mm"] * 1e-3 / 2
    for name, lay in ((f"{top} drain pin to {net_p} plane", "In2.Cu"), (f"{bot} source pin to {net_n} plane", "In1.Cu")):
        lz = DEPTH[lay] * 1e-3
        segs.append(dict(segment=name, formula="round conductor", l_mm=lz * 1e3, w_mm=2 * r_pin * 1e3, t_mm=0, L_self_nH=L_round(lz, r_pin) * 1e9, M_nH=0.0,
                         note="pin section inside the board down to the first plane"))
    # 4. plane pair from the device pins (y_dev) to the capacitors (y_cap)
    cps = [pad(board, c, net_p) for c in caps]
    cns = [pad(board, c, net_n) for c in caps]
    y_dev = 0.5 * (pT_d["y"] + pB_s["y"])
    y_cap = np.mean([p["y"] for p in cps + cns])
    l_pl = abs(y_cap - y_dev) * 1e-3
    xs = [pT_d["x"], pB_s["x"]] + [p["x"] for p in cps + cns]
    span = (max(xs) - min(xs)) * 1e-3
    region = [zn for zn in board["zones"] if zn["net"] == net_p and zn["layer"] == "In2.Cu"]
    w_plane = (region[0]["x1"] - region[0]["x0"]) * 1e-3 if region else 0.113
    w_eff = min(span + l_pl, w_plane) if w_eff_mode == "spread" else span
    h = (DEPTH["In2.Cu"] - DEPTH["In1.Cu"]) if h_plane_mm is None else h_plane_mm
    n_pairs = 2 if h_plane_mm is None else 1                   # In1/In2 and In3/In4 pairs in parallel in the real stack
    L_pl = L_plane_pair(l_pl, w_eff, h * 1e-3) / n_pairs
    segs.append(dict(segment=f"{net_p}/{net_n} plane pair", formula="mu0 h l / w_eff (/2 for two pairs)", l_mm=l_pl * 1e3, w_mm=w_eff * 1e3, t_mm=h,
                     L_self_nH=L_pl * 1e9, M_nH=0.0, note=f"h = {h:.2f} mm, span of pins/pads {span*1e3:.1f} mm, 45-deg spreading, {n_pairs} pair(s)"))
    # 5. capacitor branch: n caps in parallel, each ESL + two vias to the planes
    n_c = len(caps)
    l_v = DEPTH["In2.Cu"] * 1e-3
    L_via = L_round(l_v, A["via_drill_mm"] * 1e-3 / 2)
    L_cap = (A["cap_esl_nH"] * 1e-9 + 2 * L_via) / n_c
    segs.append(dict(segment=f"{'+'.join(caps)} ESL + pad vias (parallel)", formula="ESL typ. + 2 vias, / n", l_mm=l_v * 1e3, w_mm=A["via_drill_mm"], t_mm=0,
                     L_self_nH=L_cap * 1e9, M_nH=0.0, note=f"ESL {A['cap_esl_nH']} nH typical per 2220 part, {n_c} parts in parallel"))
    L_total = sum(s["L_self_nH"] + s["M_nH"] for s in segs)
    L_upper = L_total - L_s_img * 1e9 + L_s_free * 1e9
    return dict(top=top, bottom=bot, caps=caps, device=dev, segments=segs, L_loop_nH=L_total, L_loop_upper_nH=L_upper,
                L_package_pair_nH=2 * (L_lead - M_ds) * 1e9 * 2, geometry=dict(y_dev_mm=y_dev, y_cap_mm=float(y_cap), span_mm=span * 1e3,
                strip_l_mm=l_s * 1e3, strip_w_mm=w_s * 1e3, plane_l_mm=l_pl * 1e3, w_eff_mm=w_eff * 1e3, h_pair_mm=h))


def gate_loop(board, dev_ref, drv_ref, gd_net, g_net, ks_net, vee_net, caps_vee, rg_on_ref, dev, spacing_mm=None):
    """
    Driver output -> GD trace -> Rg -> gate pin -> die -> Kelvin-source pin -> KS/VEE decoupling caps -> VEE trace -> driver.
    Uses routed tracks of the nets when present, otherwise the Manhattan distance between the connected pads.
    """
    A = ASSUME
    s_mm = A["gate_pair_spacing_mm"] if spacing_mm is None else spacing_mm
    w = A["gate_trace_w_mm"] * 1e-3
    segs = [sg for sg in board["segments"] if sg["net"] in (gd_net, vee_net, g_net, ks_net)]
    routed = len(segs) > 0
    p_drv_out = pad(board, drv_ref, gd_net)
    p_drv_vee = pad(board, drv_ref, vee_net)
    p_rg_in = pad(board, rg_on_ref, gd_net)
    p_rg_out = pad(board, rg_on_ref, g_net)
    p_gate = pad(board, dev_ref, g_net)
    p_ks = pad(board, dev_ref, ks_net)
    p_cvee = pad(board, caps_vee[0], vee_net)
    p_cks = pad(board, caps_vee[0], ks_net)

    def manh(a, b):
        return (abs(a["x"] - b["x"]) + abs(a["y"] - b["y"])) * 1e-3
    if routed:
        lengths = {}
        for sg in segs:
            lengths[sg["net"]] = lengths.get(sg["net"], 0.0) + math.hypot(sg["x1"] - sg["x0"], sg["y1"] - sg["y0"]) * 1e-3
        l_go = lengths.get(gd_net, manh(p_drv_out, p_rg_in))
        l_ret = lengths.get(vee_net, manh(p_cvee, p_drv_vee))
        l_g = lengths.get(g_net, manh(p_rg_out, p_gate))
        l_ks = lengths.get(ks_net, manh(p_ks, p_cks))
        w_used = float(np.mean([sg["width"] for sg in segs])) * 1e-3
    else:
        l_go, l_ret, l_g, l_ks = manh(p_drv_out, p_rg_in), manh(p_cvee, p_drv_vee), manh(p_rg_out, p_gate), manh(p_ks, p_cks)
        w_used = w
    l_pair = 0.5 * (l_go + l_ret)
    L_pair = 2 * (L_bar(l_pair, w_used, 70e-6) - M_par(l_pair, s_mm * 1e-3))
    L_pair_plane = 2 * L_microstrip(l_pair, w_used, DEPTH["In1.Cu"] * 1e-3)   # if a KS-referenced plane existed under the pair
    l_lead = A["to247_lead_len_mm"] * 1e-3
    d_gks = math.hypot(p_gate["x"] - p_ks["x"], p_gate["y"] - p_ks["y"]) * 1e-3
    L_leads = 2 * (L_bar(l_lead, A["to247_lead_w_mm"] * 1e-3, A["to247_lead_t_mm"] * 1e-3) - M_par(l_lead, d_gks))
    l_local = l_g + l_ks
    L_local = 2 * (L_bar(l_local / 2, w_used, 70e-6) - M_par(l_local / 2, 3e-3))      # local go/return near the device, ~3 mm apart
    L_cap = ASSUME["cap_esl_nH"] * 1e-9 / len(caps_vee)
    total = L_pair + L_leads + L_local + L_cap
    Ciss = A["ciss_nF"][dev] * 1e-9
    R = DEVICES_RG(rg_on_ref, board) + A["rg_int_ohm"][dev] + A["driver_rout_ohm"]
    zeta = R / (2 * math.sqrt(total / Ciss))
    f_ring = 1 / (2 * math.pi * math.sqrt(total * Ciss))
    return dict(device=dev_ref, driver=drv_ref, routed_tracks_used=routed, trace_width_mm=w_used * 1e3, pair_spacing_mm=s_mm,
                l_go_mm=l_go * 1e3, l_return_mm=l_ret * 1e3, l_gate_local_mm=l_g * 1e3, l_ks_local_mm=l_ks * 1e3,
                L_trace_pair_nH=L_pair * 1e9, L_trace_pair_if_plane_referenced_nH=L_pair_plane * 1e9, L_package_gate_ks_nH=L_leads * 1e9,
                L_local_nH=L_local * 1e9, L_cap_esl_nH=L_cap * 1e9, L_gate_loop_nH=total * 1e9,
                R_total_ohm=R, Ciss_nF=Ciss * 1e9, damping_ratio=zeta, R_critical_ohm=2 * math.sqrt(total / Ciss), f_ring_MHz=f_ring / 1e6)


def DEVICES_RG(rg_ref, board):
    v = board["footprints"][rg_ref]["value"]
    m = re.match(r"([0-9.]+)R?", v.replace("R", "."))
    try:
        return float(v.replace("R", ".").rstrip("."))
    except ValueError:
        return 3.3


# ---------------------------------------------------------------------------
# Overshoot
# ---------------------------------------------------------------------------
def overshoot(L_nH, dev, Vdc_list, I_list):
    d = DEVICES[dev]
    L = L_nH * 1e-9
    rows = []
    Coss = d["Coss_er"]
    for V in Vdc_list:
        for I in I_list:
            for tf in ASSUME["t_fall_ns"]:
                didt = I / (tf * 1e-9)
                Vos_L = L * didt
                Vos_Z = I * math.sqrt(L / Coss)          # energy / characteristic-impedance bound 0.5 L I^2 = 0.5 Coss V^2
                Vos = min(Vos_L, Vos_Z)                  # the L di/dt estimate is capped by the resonant bound
                rows.append(dict(V_dc=V, I_A=I, t_fall_ns=tf, didt_A_per_ns=didt / 1e9, Vos_Ldidt_V=Vos_L, Vos_Z0_bound_V=Vos_Z,
                                 Vos_est_V=Vos, Vds_peak_V=V + Vos, margin_to_1200V_V=1200 - V - Vos,
                                 f_ring_MHz=1 / (2 * math.pi * math.sqrt(L * Coss)) / 1e6))
    return rows


# ---------------------------------------------------------------------------
def geometry_figure(board, loop, fname, title):
    fig, ax = plt.subplots(figsize=(7.5, 5))
    refs = [loop["top"], loop["bottom"]] + loop["caps"]
    xs, ys = [], []
    for ref in refs:
        for p in board["footprints"][ref]["pads"]:
            col = {loop_net(loop, "p"): C1, loop_net(loop, "n"): C2}.get(p["net"], "#999999")
            if p["net"].startswith("SW_"):
                col = C3
            ax.add_patch(Rectangle((p["x"] - p["w"] / 2, p["y"] - p["h"] / 2), p["w"], p["h"], color=col, alpha=0.9))
            xs.append(p["x"]); ys.append(p["y"])
        fp = board["footprints"][ref]
        ax.annotate(ref, (fp["x"], fp["y"] - 4), ha="center", fontsize=8)
    sw = [z for z in board["zones"] if z["net"].startswith("SW_") and z["layer"] == "B.Cu"
          and z["x0"] >= min(xs) - 15 and z["x1"] <= max(xs) + 15 and z["y0"] <= max(ys) + 15]
    for z in sw:
        ax.add_patch(Rectangle((z["x0"], z["y0"]), z["x1"] - z["x0"], z["y1"] - z["y0"], fill=False, ec=C3, lw=1.2, ls="--"))
    g = loop["geometry"]
    ax.add_patch(Rectangle((min(xs) - 1, g["y_dev_mm"]), g["span_mm"] + 2, g["plane_l_mm"], fill=True, fc=C4, alpha=0.12, ec=C4, lw=1))
    ax.text(min(xs) + 1, g["y_dev_mm"] + g["plane_l_mm"] / 2, f"plane-pair section\nl = {g['plane_l_mm']:.0f} mm, w_eff = {g['w_eff_mm']:.0f} mm, h = {g['h_pair_mm']:.2f} mm",
            fontsize=7, va="center")
    ax.set_xlim(min(xs) - 12, max(xs) + 12); ax.set_ylim(max(ys) + 10, min(ys) - 10)
    ax.set_aspect("equal"); ax.set_xlabel("x (mm)"); ax.set_ylabel("y (mm, KiCad, down)")
    ax.set_title(title + f"\nblue: {loop_net(loop,'p')} pads, orange: {loop_net(loop,'n')} pads, aqua: switch node (dashed = B.Cu strip);  L_loop ~ {loop['L_loop_nH']:.0f} nH", fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(RES, fname), dpi=150); plt.close(fig)


def loop_net(loop, which):
    return loop["nets"][which]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default=os.path.join(DAB, "07_KiCad_Schematics", "SiC_DAB_6k6.kicad_pcb"))
    args = ap.parse_args()
    board = load_board(args.board)
    log(f"board: {args.board}")
    log(f"  footprints {len(board['footprints'])}, zones {len(board['zones'])}, track segments {len(board['segments'])}, vias {len(board['vias'])}")
    xc = crosscheck_pcbnew(args.board, board)
    log(f"  pcbnew cross-check: {xc}")
    log(f"  stack-up copper mid-depths (mm): " + ", ".join(f"{k} {v:.2f}" for k, v in DEPTH.items()) + f"; board {BOARD_T:.2f} mm")

    # (a) commutation loops
    log("\n== (a) Commutation loops ==")
    loops = {}
    for key, top, bot, caps, np_, nn_, sw, dev in (("HV_leg_A", "Q1", "Q2", ["C5", "C6"], "HV_P", "HV_N", "SW_A", "C3M0032120K"),
                                                  ("HV_leg_B", "Q3", "Q4", ["C7", "C8"], "HV_P", "HV_N", "SW_B", "C3M0032120K"),
                                                  ("LV_leg_C", "Q5", "Q6", ["C13", "C14"], "LV_P", "LV_N", "SW_C", "C3M0016120K"),
                                                  ("LV_leg_D", "Q7", "Q8", ["C15", "C16"], "LV_P", "LV_N", "SW_D", "C3M0016120K")):
        try:
            lp = commutation_loop(board, top, bot, caps, np_, nn_, sw, dev)
        except KeyError as e:
            log(f"  {key}: component/net not found {e} -> skipped"); continue
        lp["nets"] = dict(p=np_, n=nn_)
        loops[key] = lp
        log(f"  {key} ({top}/{bot}, {'+'.join(caps)}): L_loop = {lp['L_loop_nH']:.1f} nH (upper bound {lp['L_loop_upper_nH']:.1f} nH); "
            f"packages {lp['L_package_pair_nH']:.1f} nH; plane pair {[s for s in lp['segments'] if 'plane pair' in s['segment']][0]['L_self_nH']:.2f} nH")
        for s in lp["segments"]:
            log(f"      {s['segment']:38s} {s['formula']:40s} l={s['l_mm']:6.2f} w={s['w_mm']:6.2f} t={s['t_mm']:5.2f} mm  L={s['L_self_nH']:6.2f} nH  M={s['M_nH']:6.2f} nH")
    with open(os.path.join(RES, "loop_segments.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["loop", "segment", "formula", "l_mm", "w_mm", "t_mm", "L_self_nH", "M_nH", "note"])
        for k, lp in loops.items():
            for s in lp["segments"]:
                w.writerow([k, s["segment"], s["formula"], f"{s['l_mm']:.3f}", f"{s['w_mm']:.3f}", f"{s['t_mm']:.3f}", f"{s['L_self_nH']:.3f}", f"{s['M_nH']:.3f}", s["note"]])
    geometry_figure(board, loops["HV_leg_A"], "fig_loop_geometry_HV.png", "HV half-bridge leg A commutation loop (Q1/Q2, C5/C6) - top view")

    # sensitivities: plane spacing, lead length, spreading width
    log("\n  sensitivity (HV leg A):")
    sens = []
    for h in (0.2, 0.5, 1.0, 1.6, 2.3):
        lp = commutation_loop(board, "Q1", "Q2", ["C5", "C6"], "HV_P", "HV_N", "SW_A", "C3M0032120K", h_plane_mm=h)
        pl = [s for s in lp["segments"] if "plane pair" in s["segment"]][0]["L_self_nH"]
        sens.append(dict(parameter="plane spacing h (single pair)", value_mm=h, L_plane_nH=pl, L_loop_nH=lp["L_loop_nH"]))
        log(f"    h = {h:.1f} mm (single pair): plane section {pl:.2f} nH, loop {lp['L_loop_nH']:.1f} nH")
    for mode in ("spread", "span"):
        lp = commutation_loop(board, "Q1", "Q2", ["C5", "C6"], "HV_P", "HV_N", "SW_A", "C3M0032120K", w_eff_mode=mode)
        pl = [s for s in lp["segments"] if "plane pair" in s["segment"]][0]
        sens.append(dict(parameter=f"effective plane width ({mode})", value_mm=pl["w_mm"], L_plane_nH=pl["L_self_nH"], L_loop_nH=lp["L_loop_nH"]))
        log(f"    w_eff mode {mode}: w_eff = {pl['w_mm']:.1f} mm, plane section {pl['L_self_nH']:.2f} nH")
    for ll in (10.0, 15.0, 20.0):
        lp = commutation_loop(board, "Q1", "Q2", ["C5", "C6"], "HV_P", "HV_N", "SW_A", "C3M0032120K", lead_len_mm=ll)
        sens.append(dict(parameter="TO-247 effective lead length", value_mm=ll, L_plane_nH=float("nan"), L_loop_nH=lp["L_loop_nH"]))
        log(f"    lead length {ll:.0f} mm: packages {lp['L_package_pair_nH']:.1f} nH, loop {lp['L_loop_nH']:.1f} nH")
    with open(os.path.join(RES, "sensitivity.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sens[0].keys())); w.writeheader(); w.writerows(sens)

    # (b) gate loops
    log("\n== (b) Gate loops ==")
    gates = {}
    for dev_ref, drv, rg, caps, dev in (("Q1", "U1", "R102", None, "C3M0032120K"), ("Q5", "U3", "R116", None, "C3M0016120K")):
        try:
            # the VEE-KS decoupling capacitors of this device, found from the netlist
            cap_list = sorted(r for r, fp in board["footprints"].items() if r.startswith("C") and {p["net"] for p in fp["pads"]} == {f"VEE_{dev_ref}", f"KS_{dev_ref}"})
            if not cap_list:
                raise KeyError(f"no VEE_{dev_ref}-KS_{dev_ref} capacitor")
            g = gate_loop(board, dev_ref, drv, f"GD_{dev_ref}", f"G_{dev_ref}", f"KS_{dev_ref}", f"VEE_{dev_ref}", cap_list, rg, dev)
            g["vee_ks_caps"] = cap_list
            gates[dev_ref] = g
            log(f"  {dev_ref} <- {drv}: go {g['l_go_mm']:.1f} mm, return {g['l_return_mm']:.1f} mm (routed tracks: {g['routed_tracks_used']}), "
                f"pair {g['L_trace_pair_nH']:.0f} nH @ s = {g['pair_spacing_mm']:.1f} mm, package G/KS {g['L_package_gate_ks_nH']:.1f} nH, local {g['L_local_nH']:.1f} nH "
                f"-> L_gate = {g['L_gate_loop_nH']:.0f} nH; R = {g['R_total_ohm']:.1f} Ohm, Ciss = {g['Ciss_nF']:.1f} nF -> zeta = {g['damping_ratio']:.2f}, f_ring = {g['f_ring_MHz']:.1f} MHz")
        except KeyError as e:
            log(f"  {dev_ref}: not found {e}")
    gsens = []
    for s_mm in (0.5, 1.0, 2.0, 3.0, 5.0):
        g = gate_loop(board, "Q1", "U1", "GD_Q1", "G_Q1", "KS_Q1", "VEE_Q1", gates["Q1"]["vee_ks_caps"], "R102", "C3M0032120K", spacing_mm=s_mm)
        gsens.append(dict(pair_spacing_mm=s_mm, L_trace_pair_nH=g["L_trace_pair_nH"], L_gate_loop_nH=g["L_gate_loop_nH"], damping_ratio=g["damping_ratio"]))
    log("  gate pair spacing sensitivity: " + ", ".join(f"s={r['pair_spacing_mm']:.1f} mm -> {r['L_gate_loop_nH']:.0f} nH (zeta {r['damping_ratio']:.2f})" for r in gsens))
    log(f"  if the pair were referenced to a KS-potential plane at {DEPTH['In1.Cu']:.2f} mm: trace part {gates['Q1']['L_trace_pair_if_plane_referenced_nH']:.0f} nH")
    with open(os.path.join(RES, "gate_loop_sensitivity.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(gsens[0].keys())); w.writeheader(); w.writerows(gsens)

    # (c) overshoot
    log("\n== (c) Drain overshoot ==")
    with open(os.path.join(DAB, "04_Design_Calculations", "design_values.json")) as f:
        dv = json.load(f)
    I_nom = dv["nominal"]["Ipk1"]; I_corner = max(c["Ipk1"] for c in dv["corners"]); I_trip = dv["I_trip_hw"]
    ov = {}
    for key, dev, Vs, Is in (("HV_leg_A", "C3M0032120K", [800.0, 850.0], [I_nom, I_corner, I_trip]),
                             ("LV_leg_C", "C3M0016120K", [400.0, 450.0], [dv["nominal"]["Ipk2"], 2 * I_corner, 2 * I_trip])):
        L = loops[key]["L_loop_nH"]
        rows = overshoot(L, dev, Vs, Is)
        ov[key] = rows
        for r in rows:
            if r["t_fall_ns"] == 10.0:
                log(f"  {key} L={L:.0f} nH {dev}: Vdc={r['V_dc']:.0f} V, I={r['I_A']:.1f} A, tf=10 ns: L di/dt = {r['Vos_Ldidt_V']:.0f} V, Z0 bound = {r['Vos_Z0_bound_V']:.0f} V -> "
                    f"Vos ~ {r['Vos_est_V']:.0f} V, Vds,pk = {r['Vds_peak_V']:.0f} V, margin to 1200 V = {r['margin_to_1200V_V']:.0f} V")
    with open(os.path.join(RES, "overshoot.csv"), "w", newline="") as f:
        keys = ["loop"] + list(ov["HV_leg_A"][0].keys())
        w = csv.writer(f); w.writerow(keys)
        for k, rows in ov.items():
            for r in rows:
                w.writerow([k] + [f"{v:.3f}" if isinstance(v, float) else v for v in r.values()])
    fig, ax = plt.subplots(figsize=(6.5, 4))
    Ls = np.linspace(10, 80, 50)
    for I, col, lab in ((I_nom, C1, f"nominal I_pk {I_nom:.1f} A"), (I_corner, C2, f"corner I_pk {I_corner:.1f} A"), (I_trip, C3, f"hardware trip {I_trip:.0f} A")):
        v = [min(L * 1e-9 * I / 10e-9, I * math.sqrt(L * 1e-9 / DEVICES['C3M0032120K']['Coss_er'])) for L in Ls]
        ax.plot(Ls, v, color=col, lw=2, label=lab)
    ax.axvline(loops["HV_leg_A"]["L_loop_nH"], color="gray", ls="--", lw=1); ax.text(loops["HV_leg_A"]["L_loop_nH"] + 1, 20, "extracted HV loop", fontsize=8, color="gray")
    ax.axhline(1200 - 850, color="black", ls=":", lw=1); ax.text(12, 1200 - 850 + 8, "1200 V - 850 V bus", fontsize=8)
    ax.set_xlabel("commutation-loop inductance (nH)"); ax.set_ylabel("overshoot estimate (V), hard turn-off, t_f = 10 ns")
    ax.set_title("HV bridge drain overshoot: min(L di/dt, I sqrt(L/Coss,er)) - analytical, not measured", fontsize=9)
    ax.grid(True, alpha=0.3); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(RES, "fig_overshoot.png"), dpi=150); plt.close(fig)

    # (d) literature comparison (typical ranges, not measured here)
    lit = [
        dict(item="TO-247 package D-S partial inductance (one device)", typical_range_nH="7 - 15", this_work_nH=f"{loops['HV_leg_A']['L_package_pair_nH']/2:.1f}",
             source="typical range reported in literature / vendor application notes on TO-247 SiC layout; not measured here"),
        dict(item="discrete TO-247 half-bridge commutation loop (PCB, MLCC decoupling)", typical_range_nH="20 - 60", this_work_nH=f"{loops['HV_leg_A']['L_loop_nH']:.0f} - {loops['HV_leg_A']['L_loop_upper_nH']:.0f}",
             source="typical range reported in literature, not measured here"),
        dict(item="TO-247-4 (Kelvin) gate loop with driver within ~20 mm", typical_range_nH="10 - 30", this_work_nH=f"{gates['Q1']['L_gate_loop_nH']:.0f}",
             source="typical range reported in literature, not measured here; this board places the driver ~100 mm away at the isolation barrier"),
        dict(item="SMD (TO-263-7 / D2PAK-7) half-bridge loop", typical_range_nH="5 - 15", this_work_nH="n/a",
             source="typical range reported in literature, not measured here"),
        dict(item="power module (DBC, integrated DC link) loop", typical_range_nH="2 - 10", this_work_nH="n/a",
             source="typical range reported in literature, not measured here"),
    ]
    with open(os.path.join(RES, "literature_comparison.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lit[0].keys())); w.writeheader(); w.writerows(lit)
    log("\n== (d) literature comparison written (typical ranges, not measured here) ==")

    wall = time.time() - T0
    out = dict(board=args.board, board_sha256=sha256(args.board), pcbnew_crosscheck=xc, stackup_depth_mm=DEPTH, board_thickness_mm=BOARD_T,
               assumptions=ASSUME, loops=loops, loop_sensitivity=sens, gate_loops=gates, gate_sensitivity=gsens, overshoot=ov,
               literature=lit, wall_s=wall, maturity="L1 (analytical from geometry; no field solver, no measurement)")
    with open(os.path.join(RES, "parasitics.json"), "w") as f:
        json.dump(out, f, indent=1, default=float)
    with open(os.path.join(RES, "run_log.txt"), "w") as f:
        f.write("\n".join(LOG) + "\n")
    import scipy
    head = None
    try:
        ref = open(os.path.join(REPO, ".git", "HEAD")).read().strip()
        if ref.startswith("ref: "):
            p = os.path.join(REPO, ".git", ref[5:])
            head = open(p).read().strip() if os.path.exists(p) else None
            if head is None:
                for line in open(os.path.join(REPO, ".git", "packed-refs")):
                    if line.strip().endswith(ref[5:]): head = line.split()[0]
        else:
            head = ref
    except OSError:
        pass
    prov = dict(module="Advanced_Research_2026/Parasitic_Extraction", script="extract_parasitics.py", python=platform.python_version(),
                numpy=np.__version__, scipy=scipy.__version__, matplotlib=matplotlib.__version__, pcbnew=xc.get("version"), git_commit=head,
                inputs={"board (path used)": args.board, "board sha256": sha256(args.board),
                        "SiC_6k6_Industrial_DAB/04_Design_Calculations/design_values.json": sha256(os.path.join(DAB, "04_Design_Calculations", "design_values.json")),
                        "SiC_6k6_Industrial_DAB/dabtools/dab/devices.py": sha256(os.path.join(DAB, "dabtools", "dab", "devices.py")),
                        "SiC_6k6_Industrial_DAB/17_Manufacturing/stackup.md": sha256(os.path.join(DAB, "17_Manufacturing", "stackup.md"))},
                wall_time_s=wall, generated=time.strftime("%Y-%m-%d %H:%M:%S"), deterministic=True, outputs=sorted(os.listdir(RES)))
    with open(os.path.join(HERE, "provenance.json"), "w") as f:
        json.dump(prov, f, indent=1)
    log(f"\nwall time {wall:.1f} s; results in {RES}")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


if __name__ == "__main__":
    main()
