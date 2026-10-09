"""
Grid-based A* signal router for the PCB generator.

Two routing layers (F.Cu, B.Cu), 0.25 mm grid, through-hole vias.  Obstacles
are rasterised with the required clearance for the net being routed, so the
result is DRC-clean by construction (verified afterwards with KiCad's DRC).
"""
import heapq, math
import numpy as np

GRID = 0.25
F, B = 0, 1
LAYER_NAMES = {F: "F.Cu", B: "B.Cu"}
DIRS4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


class Rect:
    __slots__ = ("x1", "y1", "x2", "y2")

    def __init__(self, x1, y1, x2, y2):
        self.x1, self.y1, self.x2, self.y2 = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)

    def expand(self, d):
        return Rect(self.x1 - d, self.y1 - d, self.x2 + d, self.y2 + d)

    def contains(self, x, y):
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2


class Pad:
    def __init__(self, ref, number, net, rect, layers, center):
        self.ref, self.number, self.net, self.rect, self.layers, self.center = ref, number, net, rect, layers, center


class Router:
    def __init__(self, width_mm, height_mm, clearance_fn, width_fn, keepouts=(), via_size=0.8, via_drill=0.4):
        self.W = int(round(width_mm / GRID)) + 1
        self.H = int(round(height_mm / GRID)) + 1
        self.clearance_fn = clearance_fn          # (net, other_net) -> required clearance mm
        self.width_fn = width_fn                  # net -> track width mm
        self.via_size, self.via_drill = via_size, via_drill
        # static obstacles: list of (net, layerset, rect) for pads/zones/tracks
        self.items = []                           # (net, layers(frozenset), Rect)
        self.keepouts = [Rect(*k) for k in keepouts]   # all layers, all nets
        self.private = []                         # (Rect, set(nets)) : only listed nets may route inside
        self.h_only = []                          # Rects where F.Cu moves must be horizontal (fan-out corridors)
        self.tracks_out = []                      # (net, layer, x1,y1,x2,y2,width)
        self.vias_out = []                        # (net, x, y)
        self.failed = []
        self.routed_items = []                    # obstacle items created by routing (for rip-up)

    # ------------------------------------------------------------------
    def add_item(self, net, layers, rect):
        self.items.append((net, frozenset(layers), rect))

    def add_private(self, rect, nets):
        self.private.append((Rect(*rect), set(nets)))

    def _to_cell(self, x, y):
        return int(round(x / GRID)), int(round(y / GRID))

    def _rasterize(self, grid, rect, value=True):
        """Mark cells whose centre lies inside rect."""
        i1 = max(0, int(math.ceil(rect.x1 / GRID))); i2 = min(self.W - 1, int(math.floor(rect.x2 / GRID)))
        j1 = max(0, int(math.ceil(rect.y1 / GRID))); j2 = min(self.H - 1, int(math.floor(rect.y2 / GRID)))
        if i2 >= i1 and j2 >= j1:
            grid[j1:j2 + 1, i1:i2 + 1] = value

    def build_honly(self):
        m = np.zeros((self.H, self.W), dtype=bool)
        for r in self.h_only:
            self._rasterize(m, r)
        return m

    def build_blocked(self, net):
        """Blocked-cell maps for routing `net` on each layer, and the no-via map."""
        hw = self.width_fn(net) / 2
        blocked = np.zeros((2, self.H, self.W), dtype=bool)
        novia = np.zeros((self.H, self.W), dtype=bool)
        vr = self.via_size / 2
        for inet, layers, rect in self.items:
            if inet == net:
                # own copper: free, but no vias inside pads of own net (keeps vias out of pads)
                self._rasterize(novia, rect.expand(vr))
                continue
            clr = self.clearance_fn(net, inet)
            e = rect.expand(clr + hw)
            for L in layers:
                self._rasterize(blocked[L], e)
            # via clearance: via must stay clr away from other-net copper on any layer it touches
            self._rasterize(novia, rect.expand(clr + vr))
        for k in self.keepouts:
            e = k.expand(hw)
            self._rasterize(blocked[F], e); self._rasterize(blocked[B], e); self._rasterize(novia, k.expand(vr))
        for rect, allowed in self.private:
            if net not in allowed:
                self._rasterize(blocked[F], rect); self._rasterize(blocked[B], rect); self._rasterize(novia, rect)
        for rect in self.h_only:
            self._rasterize(novia, rect.expand(self.via_size / 2))
        # board edge
        m = int(round(1.0 / GRID))
        blocked[:, :m, :] = True; blocked[:, -m:, :] = True; blocked[:, :, :m] = True; blocked[:, :, -m:] = True
        return blocked, novia

    # ------------------------------------------------------------------
    def route_net(self, net, terminals, via_cost=25, turn_cost=0.6, max_nodes=2_500_000):
        """
        terminals: list of (x, y, layers) connection points (pads / stub ends / zone goals).
        Routes a minimum-spanning sequence: each new terminal is connected to the
        already-routed tree.  Returns True if all terminals connected.
        """
        if len(terminals) < 2:
            return True
        blocked, novia = self.build_blocked(net)
        honly = self.build_honly()
        # source tree cells: set of (layer, j, i)
        tree = set()
        order = list(terminals)
        # start with the terminal nearest to the centroid of all terminals
        cx = sum(t[0] for t in order) / len(order); cy = sum(t[1] for t in order) / len(order)
        order.sort(key=lambda t: (t[0] - cx) ** 2 + (t[1] - cy) ** 2)
        first = order.pop(0)
        for L in first[2]:
            tree.add((L, *reversed(self._to_cell(first[0], first[1]))))
        ok = True
        while order:
            # pick the terminal closest to the tree (manhattan to any tree cell is expensive; use nearest terminal-to-tree-cell sample)
            tcells = np.array([(c[2], c[1]) for c in tree])
            best, bestd = None, 1e18
            for t in order:
                ci, cj = self._to_cell(t[0], t[1])
                d = np.min(np.abs(tcells[:, 0] - ci) + np.abs(tcells[:, 1] - cj))
                if d < bestd:
                    best, bestd = t, d
            order.remove(best)
            goal = set()
            gi, gj = self._to_cell(best[0], best[1])
            for L in best[2]:
                goal.add((L, gj, gi))
            path = self._astar(tree, goal, blocked, novia, via_cost, turn_cost, max_nodes, honly)
            if path is None:
                self.failed.append((net, best))
                ok = False
                # still add the terminal so later terminals can connect to it
                for L in best[2]:
                    tree.add((L, gj, gi))
                continue
            self._emit(net, path)
            for c in path:
                tree.add(c)
        return ok

    def _astar(self, sources, goals, blocked, novia, via_cost, turn_cost, max_nodes, honly=None):
        H, W = self.H, self.W
        INF = np.float32(1e30)
        g = np.full((2, H, W), INF, dtype=np.float32)
        parent = np.full((2, H, W), -1, dtype=np.int64)
        goal_list = [(gj, gi) for (_, gj, gi) in goals]
        def h(j, i):
            return min(abs(j - gj) + abs(i - gi) for gj, gi in goal_list)
        heap = []
        for (L, j, i) in sources:
            if blocked[L, j, i]:
                # a source inside blocked area (e.g. pad centre adjacent to other pads) - allow starting there
                pass
            g[L, j, i] = 0
            heapq.heappush(heap, (h(j, i), 0.0, L, j, i))
        goals_set = goals
        expanded = 0
        while heap:
            f_, gc, L, j, i = heapq.heappop(heap)
            if gc > g[L, j, i]:
                continue
            if (L, j, i) in goals_set:
                return self._backtrack(parent, (L, j, i), sources)
            expanded += 1
            if expanded > max_nodes:
                return None
            p = parent[L, j, i]
            pdir = None
            if p >= 0:
                pL, pj, pi = p // (H * W), (p // W) % H, p % W
                pdir = (j - pj, i - pi)
            for dj, di in DIRS4:
                nj, ni = j + dj, i + di
                if nj < 0 or ni < 0 or nj >= H or ni >= W:
                    continue
                if dj != 0 and L == F and honly is not None and honly[j, i] and (L, nj, ni) not in goals_set:
                    continue                      # fan-out corridor: no vertical runs on F.Cu
                if blocked[L, nj, ni] and (L, nj, ni) not in goals_set and (L, nj, ni) not in sources:
                    continue
                c = gc + (1.5 if L == F else 1.0)       # long runs prefer B.Cu, keeps F.Cu free around SMD pads
                if pdir is not None and pdir != (dj, di):
                    c += turn_cost
                # layer preference: F horizontal, B vertical (mild)
                if (L == F and dj != 0) or (L == B and di != 0):
                    c += 0.15
                if c < g[L, nj, ni]:
                    g[L, nj, ni] = c
                    parent[L, nj, ni] = L * H * W + j * W + i
                    heapq.heappush(heap, (c + h(nj, ni), c, L, nj, ni))
            # via
            oL = 1 - L
            if not novia[j, i] and not blocked[oL, j, i]:
                c = gc + via_cost
                if c < g[oL, j, i]:
                    g[oL, j, i] = c
                    parent[oL, j, i] = L * H * W + j * W + i
                    heapq.heappush(heap, (c + h(j, i), c, oL, j, i))
        return None

    def _backtrack(self, parent, node, sources):
        H, W = self.H, self.W
        path = [node]
        while node not in sources:
            p = parent[node]
            node = (int(p // (H * W)), int((p // W) % H), int(p % W))
            path.append(node)
        path.reverse()
        return path

    def _emit(self, net, path):
        """Convert a cell path into track segments and vias."""
        w = self.width_fn(net)
        seg_start = path[0]
        for k in range(1, len(path)):
            a, b = path[k - 1], path[k]
            if a[0] != b[0]:                       # via
                self._flush(net, seg_start, a, w)
                self.vias_out.append((net, a[2] * GRID, a[1] * GRID))
                self.register_via(net, a[2] * GRID, a[1] * GRID, routed=True)
                seg_start = b
                continue
            if k + 1 < len(path):
                c = path[k + 1]
                if c[0] == b[0] and (b[1] - a[1], b[2] - a[2]) == (c[1] - b[1], c[2] - b[2]):
                    continue                        # collinear, keep going
            self._flush(net, seg_start, b, w)
            seg_start = b
        # register routed copper as obstacles for the next nets
        hw = w / 2
        for (L, j, i) in path:
            it = (net, frozenset([L]), Rect(i * GRID - hw, j * GRID - hw, i * GRID + hw, j * GRID + hw))
            self.items.append(it); self.routed_items.append(it)

    def _flush(self, net, a, b, w):
        if a == b:
            return
        self.tracks_out.append((net, a[0], a[2] * GRID, a[1] * GRID, b[2] * GRID, b[1] * GRID, w))

    def what_blocks(self, net, x, y):
        """Items whose expanded rectangle covers (x, y) when routing `net` (diagnostic)."""
        hw = self.width_fn(net) / 2
        out = []
        for k, (inet, layers, rect) in enumerate(self.items):
            if inet == net:
                continue
            e = rect.expand(self.clearance_fn(net, inet) + hw)
            if e.contains(x, y):
                out.append((inet, sorted(layers), round(rect.x1, 2), round(rect.y1, 2), round(rect.x2, 2), round(rect.y2, 2)))
        return out

    def rip_up(self, nets):
        """Remove routed copper of the given nets (tracks, vias and their obstacle items)."""
        nets = set(nets)
        self.tracks_out = [t for t in self.tracks_out if t[0] not in nets]
        self.vias_out = [v for v in self.vias_out if v[0] not in nets]
        self.items = [it for it in self.items if not (it[0] in nets and it in self.routed_items)]
        self.routed_items = [it for it in self.routed_items if it[0] not in nets]

    def debug_dump(self, net, x, y, r=4.0):
        """ASCII dump of the blocked maps around (x, y) for routing `net` ('#' blocked, '.' free, '*' centre)."""
        blocked, novia = self.build_blocked(net)
        ci, cj = self._to_cell(x, y)
        n = int(r / GRID)
        out = [f"--- {net} around ({x:.2f},{y:.2f})  left=F.Cu  right=B.Cu  (cell {GRID} mm)"]
        for j in range(cj - n, cj + n + 1):
            row = []
            for L in (F, B):
                for i in range(ci - n, ci + n + 1):
                    if 0 <= j < self.H and 0 <= i < self.W:
                        row.append("*" if (i, j) == (ci, cj) else ("#" if blocked[L, j, i] else "."))
                    else:
                        row.append(" ")
                row.append("   ")
            out.append("".join(row))
        return "\n".join(out)

    def register_via(self, net, x, y, routed=False):
        vr = self.via_size / 2
        it = (net, frozenset([F, B]), Rect(x - vr, y - vr, x + vr, y + vr))
        self.items.append(it)
        if routed:
            self.routed_items.append(it)


# ---------------------------------------------------------------------------
# Negotiated-congestion routing (PathFinder style)
# ---------------------------------------------------------------------------
def _maxfilt(a, r):
    """Chebyshev (square window, radius r cells) maximum filter over the last two axes of a (2,H,W) array."""
    if r <= 0:
        return a
    out = a
    for axis in (1, 2):
        src = out; out = src.copy()
        for s in range(1, r + 1):
            hi = [slice(None)] * 3; lo = [slice(None)] * 3
            hi[axis] = slice(s, None); lo[axis] = slice(None, -s)
            np.maximum(out[tuple(hi)], src[tuple(lo)], out=out[tuple(hi)])
            np.maximum(out[tuple(lo)], src[tuple(hi)], out=out[tuple(lo)])
    return out


class NegotiatedRouter(Router):
    """
    All nets are routed against the static obstacles only; copper of other nets is a soft
    penalty (present usage x pres_fac + history).  Nets whose halos overlap are re-routed with
    increasing penalties until no overlap remains (or max_iter).  Standard PathFinder scheme
    (McMurchie & Ebeling 1995) on the 2-layer grid; the result is then checked by KiCad DRC.
    """

    def _halo_cells(self, net):
        """Chebyshev halo radius (cells) of this net's tracks and vias against a typical neighbour."""
        # halo = own half width + half the clearance (+0.01 mm guard): two halos touch exactly when the
        # centre spacing equals hw_a + hw_b + clearance, i.e. the DRC limit
        # clearance against nets of the same class (routed signal nets only meet signal nets of their
        # own side; cross-side isolation distances are enforced by the static obstacle maps)
        clr = self.clearance_fn(net, net)
        hw = self.width_fn(net) / 2
        r_track = int(math.ceil((hw + clr / 2 + 0.01) / GRID))
        r_via = int(math.ceil((self.via_size / 2 + clr / 2 + 0.01) / GRID))
        return r_track, r_via

    def route_all(self, tasks, max_iter=14, pres_fac0=1.0, pres_growth=1.7, hist_fac=0.5, via_cost=25, turn_cost=0.6, max_nodes=2_500_000, log=print, debug_dir=None):
        H, W = self.H, self.W
        self._class_samples = sorted({t[0] for t in tasks})[:12]
        usage = np.zeros((2, H, W), dtype=np.int16)      # number of nets occupying (halo) each cell
        owner_count = {}                                   # net -> cells list
        history = np.zeros((2, H, W), dtype=np.float32)
        paths = {}                                         # net -> list of (layer, j, i) full path cells (all segments)
        halos = {}                                         # net -> list of (L, j1, j2, i1, i2) halo boxes marked
        static_blocked, static_novia, honly = {}, {}, self.build_honly()

        def blocked_for(net):
            if net not in static_blocked:
                static_blocked[net], static_novia[net] = self.build_blocked(net)
            return static_blocked[net], static_novia[net]

        def mark(net, cells, sign):
            """Add/remove this net's halo as a UNION mask (one count per net per cell)."""
            r_t, r_v = self._halo_cells(net)
            mask = np.zeros((2, H, W), dtype=bool)
            prev = None
            for (L, j, i) in cells:
                if prev is not None and prev[0] != L:      # via: halo on both layers
                    j1, j2, i1, i2 = max(0, j - r_v), min(H - 1, j + r_v), max(0, i - r_v), min(W - 1, i + r_v)
                    mask[:, j1:j2 + 1, i1:i2 + 1] = True
                j1, j2, i1, i2 = max(0, j - r_t), min(H - 1, j + r_t), max(0, i - r_t), min(W - 1, i + r_t)
                mask[L, j1:j2 + 1, i1:i2 + 1] = True
                prev = (L, j, i)
            if sign > 0:
                usage[mask] += 1
            else:
                usage[mask] -= 1
            return None

        def route_one(net, terms, pres_fac):
            blocked, novia = blocked_for(net)
            # own usage must not penalise itself: temporarily subtract
            own = paths.get(net)
            if own:
                mark(net, own, -1)
            # a path cell at (j,i) puts this net's halo over [j-r, j+r] x [i-r, i+r]: it conflicts with
            # every other halo inside that window, so the cost seen by A* is the Chebyshev max-filter of
            # (usage, history) with the net's own halo radius (not the raw per-cell value)
            r_t, _ = self._halo_cells(net)
            cost_map = _maxfilt(usage.astype(np.float32) * pres_fac + history, r_t)
            res = self._route_net_cost(net, terms, blocked, novia, honly, cost_map, via_cost, turn_cost, max_nodes)
            if own:
                mark(net, own, +1)
            return res

        order = list(tasks)
        pres_fac = pres_fac0
        conflict_nets = {t[0] for t in order}
        for it in range(1, max_iter + 1):
            n_rerouted = 0
            for net, terms in order:
                if net not in conflict_nets:
                    continue
                if net in paths:
                    mark(net, paths[net], -1); del paths[net]
                cells, tracks, vias, ok = route_one(net, terms, pres_fac)
                if cells:
                    paths[net] = cells
                    mark(net, cells, +1)
                    owner_count[net] = (tracks, vias, ok)
                n_rerouted += 1
            # find conflicts: nets whose halo covers a cell used by >= 2 nets
            over = usage >= 2
            conflict_nets = set()
            for net, cells in paths.items():
                r_t, r_v = self._halo_cells(net)
                for (L, j, i) in cells[::max(1, r_t)]:
                    j1, j2, i1, i2 = max(0, j - r_t), min(H - 1, j + r_t), max(0, i - r_t), min(W - 1, i + r_t)
                    if over[L, j1:j2 + 1, i1:i2 + 1].any():
                        conflict_nets.add(net); break
            history += hist_fac * over.astype(np.float32)
            n_over = int(over.sum())
            if debug_dir:
                import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
                fig, ax = plt.subplots(1, 2, figsize=(14, 5))
                for L in (0, 1):
                    ax[L].imshow(np.where(over[L], 2, np.minimum(usage[L], 1)), origin="upper", cmap="hot", interpolation="nearest"); ax[L].set_title(f"iter {it} layer {L}: usage (1) and overlap (2)")
                fig.savefig(f"{debug_dir}/overlap_iter{it}.png", dpi=90); plt.close(fig)
                counts = []
                for net, cells in paths.items():
                    cnt = sum(1 for (L, j, i) in cells if over[L, j, i])
                    if cnt: counts.append((cnt, net))
                log("    worst nets by overlapped path cells: " + str(sorted(counts, reverse=True)[:12]))
            incomplete = [n for n, v in owner_count.items() if not v[2]]
            log(f"  negotiation iter {it}: rerouted {n_rerouted}, overlapping cells {n_over}, conflicting nets {len(conflict_nets)}, incomplete nets {len(incomplete)}")
            if not conflict_nets and not incomplete:
                break
            conflict_nets |= set(incomplete)
            pres_fac *= pres_growth
        # emit
        self.tracks_out, self.vias_out, self.failed = [], [], []
        for net, (tracks, vias, ok) in owner_count.items():
            self.tracks_out += tracks; self.vias_out += vias
            if not ok:
                self.failed.append((net, tracks[0][2:4] if tracks else (0, 0)))
        if conflict_nets:
            for net in conflict_nets:
                self.failed.append((net, (-1, -1)))
        return not conflict_nets and not [n for n, v in owner_count.items() if not v[2]]

    def _route_net_cost(self, net, terminals, blocked, novia, honly, cost_map, via_cost, turn_cost, max_nodes):
        """Like route_net but with an additive per-cell cost map; returns (cells, tracks, vias, ok)."""
        tree = set(); cells_all = []; tracks = []; vias = []
        order = list(terminals)
        cx = sum(t[0] for t in order) / len(order); cy = sum(t[1] for t in order) / len(order)
        order.sort(key=lambda t: (t[0] - cx) ** 2 + (t[1] - cy) ** 2)
        first = order.pop(0)
        for L in first[2]:
            tree.add((L, *reversed(self._to_cell(first[0], first[1]))))
        ok = True
        w = self.width_fn(net)
        while order:
            tcells = np.array([(c[2], c[1]) for c in tree])
            best, bestd = None, 1e18
            for t in order:
                ci, cj = self._to_cell(t[0], t[1])
                d = np.min(np.abs(tcells[:, 0] - ci) + np.abs(tcells[:, 1] - cj))
                if d < bestd: best, bestd = t, d
            order.remove(best)
            gi, gj = self._to_cell(best[0], best[1])
            goal = {(L, gj, gi) for L in best[2]}
            path = self._astar_cost(tree, goal, blocked, novia, honly, cost_map, via_cost, turn_cost, max_nodes)
            if path is None:
                ok = False
                for L in best[2]: tree.add((L, gj, gi))
                continue
            # segments
            seg_start = path[0]
            for k in range(1, len(path)):
                a, b = path[k - 1], path[k]
                if a[0] != b[0]:
                    if seg_start != a: tracks.append((net, seg_start[0], seg_start[2] * GRID, seg_start[1] * GRID, a[2] * GRID, a[1] * GRID, w))
                    vias.append((net, a[2] * GRID, a[1] * GRID)); seg_start = b; continue
                if k + 1 < len(path):
                    c = path[k + 1]
                    if c[0] == b[0] and (b[1] - a[1], b[2] - a[2]) == (c[1] - b[1], c[2] - b[2]): continue
                if seg_start != b: tracks.append((net, seg_start[0], seg_start[2] * GRID, seg_start[1] * GRID, b[2] * GRID, b[1] * GRID, w))
                seg_start = b
            for c in path: tree.add(c)
            cells_all += path
        return cells_all, tracks, vias, ok

    def _astar_cost(self, sources, goals, blocked, novia, honly, cost_map, via_cost, turn_cost, max_nodes):
        H, W = self.H, self.W
        INF = np.float32(1e30)
        g = np.full((2, H, W), INF, dtype=np.float32)
        parent = np.full((2, H, W), -1, dtype=np.int64)
        goal_list = [(gj, gi) for (_, gj, gi) in goals]
        def h(j, i):
            return min(abs(j - gj) + abs(i - gi) for gj, gi in goal_list)
        heap = []
        for (L, j, i) in sources:
            g[L, j, i] = 0; heapq.heappush(heap, (h(j, i), 0.0, L, j, i))
        expanded = 0
        while heap:
            f_, gc, L, j, i = heapq.heappop(heap)
            if gc > g[L, j, i]: continue
            if (L, j, i) in goals: return self._backtrack(parent, (L, j, i), sources)
            expanded += 1
            if expanded > max_nodes: return None
            p = parent[L, j, i]; pdir = None
            if p >= 0:
                pj, pi = (p // W) % H, p % W; pdir = (j - pj, i - pi)
            for dj, di in DIRS4:
                nj, ni = j + dj, i + di
                if nj < 0 or ni < 0 or nj >= H or ni >= W: continue
                if dj != 0 and L == F and honly[j, i] and (L, nj, ni) not in goals: continue
                if blocked[L, nj, ni] and (L, nj, ni) not in goals and (L, nj, ni) not in sources: continue
                c = gc + (1.5 if L == F else 1.0) + float(cost_map[L, nj, ni])
                if pdir is not None and pdir != (dj, di): c += turn_cost
                if (L == F and dj != 0) or (L == B and di != 0): c += 0.15
                if c < g[L, nj, ni]:
                    g[L, nj, ni] = c; parent[L, nj, ni] = L * H * W + j * W + i
                    heapq.heappush(heap, (c + h(nj, ni), c, L, nj, ni))
            oL = 1 - L
            if not novia[j, i] and not blocked[oL, j, i]:
                c = gc + via_cost + float(cost_map[oL, j, i]) * 4
                if c < g[oL, j, i]:
                    g[oL, j, i] = c; parent[oL, j, i] = L * H * W + j * W + i
                    heapq.heappush(heap, (c + h(j, i), c, oL, j, i))
        return None
