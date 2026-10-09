#!/usr/bin/env python3
"""Render a region of a .kicad_pcb (pads, tracks, vias, zones outlines) to PNG with matplotlib.

usage: python3 -m tools.kicad.plot_board board.kicad_pcb out.png [x1 y1 x2 y2] [--nets a,b,c]
"""
import sys
import pcbnew
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle

COL = {pcbnew.F_Cu: ("#c83232", 0.75), pcbnew.B_Cu: ("#3264c8", 0.75)}


def plot(path, out, region=None, nets=None, dpi=200):
    board = pcbnew.LoadBoard(path)
    fig, ax = plt.subplots(figsize=(12, 12))
    nm = lambda t: board.GetNetInfo().GetNetItem(t.GetNetCode()).GetNetname() if t.GetNetCode() else ""
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            c = pad.GetPosition(); sz = pad.GetSize()
            x, y = c.x / 1e6, c.y / 1e6; w, h = sz.x / 1e6, sz.y / 1e6
            if pad.GetOrientation().AsDegrees() % 180 == 90: w, h = h, w
            if region and not (region[0] - 2 <= x <= region[2] + 2 and region[1] - 2 <= y <= region[3] + 2): continue
            ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc="#999999", ec="k", lw=0.3, alpha=0.8))
            ax.text(x, y, nm(pad), fontsize=3, ha="center", va="center")
    for t in board.GetTracks():
        n = nm(t)
        if nets and n not in nets: continue
        if t.GetClass() == "PCB_VIA":
            c = t.GetPosition(); x, y = c.x / 1e6, c.y / 1e6
            if region and not (region[0] <= x <= region[2] and region[1] <= y <= region[3]): continue
            ax.add_patch(Circle((x, y), t.GetWidth() / 2e6, fc="#22aa22", ec="k", lw=0.3, alpha=0.9))
            ax.text(x, y, n, fontsize=3, ha="center", va="center")
        else:
            s, e = t.GetStart(), t.GetEnd(); L = t.GetLayer()
            col, alpha = COL.get(L, ("#888888", 0.5))
            x1, y1, x2, y2 = s.x / 1e6, s.y / 1e6, e.x / 1e6, e.y / 1e6
            if region and not (max(x1, x2) >= region[0] and min(x1, x2) <= region[2] and max(y1, y2) >= region[1] and min(y1, y2) <= region[3]): continue
            ax.plot([x1, x2], [y1, y2], color=col, lw=t.GetWidth() / 1e6 * 72 / 25.4 * (12 / ((region[2] - region[0]) if region else 260)) * 10, alpha=alpha, solid_capstyle="round")
            ax.text((x1 + x2) / 2, (y1 + y2) / 2, n, fontsize=2.5, color=col, ha="center", va="center")
    if region: ax.set_xlim(region[0], region[2]); ax.set_ylim(region[3], region[1])
    else:
        bb = board.GetBoardEdgesBoundingBox(); ax.set_xlim(bb.GetLeft() / 1e6, bb.GetRight() / 1e6); ax.set_ylim(bb.GetBottom() / 1e6, bb.GetTop() / 1e6)
    ax.set_aspect("equal"); ax.grid(True, lw=0.2); fig.savefig(out, dpi=dpi); plt.close(fig)


if __name__ == "__main__":
    a = sys.argv[1:]
    nets = None
    if "--nets" in a:
        k = a.index("--nets"); nets = set(a[k + 1].split(",")); del a[k:k + 2]
    region = tuple(float(v) for v in a[2:6]) if len(a) >= 6 else None
    plot(a[0], a[1], region, nets)
