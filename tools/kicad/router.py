"""
Grid-based A* signal router for the PCB generator.

Two routing layers (F.Cu, B.Cu), 0.25 mm grid, through-hole vias.  Obstacles
are rasterised with the required clearance for the net being routed, so the
result is DRC-clean by construction (verified afterwards with KiCad's DRC).
"""
import heapq, math, os
import numpy as np

GRID = 0.25
MOUTH_COST = 40.0
TERM_COST = 15.0    # extra cost per cell within 1 mm of another net's terminal (stub exit, pad, pour goal)   # extra cost of a vertical F.Cu step in the 1.5 mm band outside a fan-out corridor mouth
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
        self.h_soft = []                          # Rects just outside the corridor mouths: vertical F.Cu moves are penalised
        self.h_both = []                          # Rects where vertical moves are forbidden on BOTH layers and no vias (module exits)
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

    def build_hboth(self):
        m = np.zeros((self.H, self.W), dtype=bool)
        for r in self.h_both:
            self._rasterize(m, r)
        return m

    def build_hsoft(self):
        m = np.zeros((self.H, self.W), dtype=bool)
        for r in self.h_soft:
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
        for rect in self.h_only + self.h_soft + self.h_both:   # no vias in the corridors nor in the mouth bands:
            self._rasterize(novia, rect.expand(self.via_size / 2))   # a via halo at the mouth seals the neighbouring exits
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
        # Each net marks a FULL halo (radius r) and a SMALL halo (radius r-1).  Two nets A, B whose
        # centre lines are d cells apart conflict when a cell lies in A_full & B_small (or vice versa),
        # i.e. when d <= r_A + r_B - 1  <=>  d < r_A + r_B.  With r = ceil(x - 0.5), x = (half-size +
        # clearance/2)/GRID, this flags exactly the pairs with d*GRID < hw_A + hw_B + clearance (the
        # DRC limit) for same-class pairs and is at most one cell conservative for mixed widths.
        clr = self.clearance_fn(net, net)
        hw = self.width_fn(net) / 2
        # r = ceil(x): ceil(x_A) + ceil(x_B) >= ceil(x_A + x_B), so the criterion is never permissive and
        # at most one cell conservative for mixed widths/classes.
        r_track = max(1, int(math.ceil((hw + clr / 2) / GRID - 1e-9)))
        r_via = max(1, int(math.ceil((self.via_size / 2 + clr / 2) / GRID - 1e-9)))
        return r_track, r_via

    # ------------------------------------------------------------------ negotiated routing state
    class _State:
        """Everything the negotiation and the hard pass share (also what ROUTER_DUMP pickles)."""
        pass

    def _mark(self, st, net, cells, sign):
        """Add/remove this net's FULL and SMALL halos as union masks (one count per net per cell)."""
        H, W = self.H, self.W
        r_t, r_v = self._halo_cells(net)
        mask = np.zeros((2, H, W), dtype=bool); mask_s = np.zeros((2, H, W), dtype=bool)
        prev = None
        for (L, j, i) in cells:
            if prev is not None and prev[0] != L:      # via: halo on both layers
                for m, r in ((mask, r_v), (mask_s, r_v - 1)):
                    j1, j2, i1, i2 = max(0, j - r), min(H - 1, j + r), max(0, i - r), min(W - 1, i + r)
                    m[:, j1:j2 + 1, i1:i2 + 1] = True
            for m, r in ((mask, r_t), (mask_s, r_t - 1)):
                j1, j2, i1, i2 = max(0, j - r), min(H - 1, j + r), max(0, i - r), min(W - 1, i + r)
                m[L, j1:j2 + 1, i1:i2 + 1] = True
            prev = (L, j, i)
        if sign > 0:
            st.usage[mask] += 1; st.usage_s[mask_s] += 1
        else:
            st.usage[mask] -= 1; st.usage_s[mask_s] -= 1

    def _blocked_for(self, st, net):
        if net not in st.static_blocked:
            st.static_blocked[net], st.static_novia[net] = self.build_blocked(net)
        return st.static_blocked[net], st.static_novia[net]

    def _add_term_cost(self, arr, terms, val, r=4):
        H, W = self.H, self.W
        for (x, y, layers) in terms:
            i, j = self._to_cell(x, y)
            arr[:, max(0, j - r):j + r + 1, max(0, i - r):i + r + 1] += val

    def _term_cost_for(self, st, net):
        tc = st.term_cost.copy()
        self._add_term_cost(tc, st.task_of.get(net, []), -TERM_COST)
        return np.maximum(tc, 0.0)

    def _halo_of(self, nets, st):
        """FULL-halo union mask (2,H,W) of the given routed nets."""
        tmp = self._State(); tmp.usage = np.zeros((2, self.H, self.W), dtype=np.int16); tmp.usage_s = tmp.usage.copy()
        for n in nets:
            if n in st.paths:
                self._mark(tmp, n, st.paths[n], +1)
        return tmp.usage > 0

    def _route_soft(self, st, net, terms, hard_nets=()):
        """Route against static obstacles with the other nets' copper as a soft cost (the copper of
        `hard_nets` as hard obstacles)."""
        blocked, novia = self._blocked_for(st, net)
        if hard_nets:
            r_t, r_v = self._halo_cells(net)
            occ = self._halo_of(hard_nets, st).astype(np.float32)
            blocked = blocked | (_maxfilt(occ, r_t - 1) > 0)
            nv = _maxfilt(occ, r_v - 1) > 0
            novia = novia | nv[0] | nv[1]
        own = st.paths.get(net)
        if own:
            self._mark(st, net, own, -1)
        # a path cell at (j,i) puts this net's halo over [j-r, j+r] x [i-r, i+r]: it conflicts with
        # every other halo inside that window, so the cost seen by A* is the Chebyshev max-filter of
        # (usage, history) with the net's own halo radius (not the raw per-cell value)
        r_t, r_v = self._halo_cells(net)
        base = st.usage.astype(np.float32) * st.pres_fac + st.history + self._term_cost_for(st, net)
        cost_map = _maxfilt(base, r_t - 1)
        cm_v = _maxfilt(base, r_v - 1); cost_map_via = np.maximum(cm_v[0], cm_v[1])
        res = self._route_net_cost(net, terms, blocked, novia, st.honly, (cost_map, cost_map_via), st.via_cost, st.turn_cost, st.max_nodes)
        if own:
            self._mark(st, net, own, +1)
        return res

    def _route_hard(self, st, net, terms, avoid=None, avoid_hard=False):
        """Route against the other routed copper as hard obstacles (full halo + own radius).
        `avoid`: {net: cells} of ripped-up nets whose old halos are kept free - as hard obstacles
        (avoid_hard, so the victims can be re-routed exactly as before) or as a strong soft cost."""
        H, W = self.H, self.W
        blocked, novia = self._blocked_for(st, net)
        r_t, r_v = self._halo_cells(net)
        occ = (st.usage > 0).astype(np.float32)
        cost = _maxfilt(self._term_cost_for(st, net), r_t - 1)
        if avoid:
            tmp = self._State(); tmp.usage = np.zeros((2, H, W), dtype=np.int16); tmp.usage_s = tmp.usage.copy()
            for n, cells in avoid.items():
                self._mark(tmp, n, cells, +1)
            if avoid_hard:
                occ = np.maximum(occ, (tmp.usage > 0).astype(np.float32))
            else:
                cost = cost + _maxfilt(tmp.usage.astype(np.float32) * 50.0, r_t - 1)
        hard_b = blocked | (_maxfilt(occ, r_t - 1) > 0)
        nv = _maxfilt(occ, r_v - 1) > 0
        hard_nv = novia | nv[0] | nv[1]
        cv = _maxfilt(cost, max(0, r_v - r_t)); cost_via = np.maximum(cv[0], cv[1])
        return self._route_net_cost(net, terms, hard_b, hard_nv, st.honly, (cost, cost_via), st.via_cost, st.turn_cost, st.max_nodes)

    def _unroute(self, st, net):
        if net in st.paths:
            self._mark(st, net, st.paths[net], -1); del st.paths[net]
        st.owner_count.pop(net, None)

    def _commit(self, st, net, cells, tracks, vias, ok=True):
        st.paths[net] = cells; self._mark(st, net, cells, +1); st.owner_count[net] = (tracks, vias, ok)

    def _conflicts(self, st):
        """Nets whose halo overlaps another net's halo (cell in one FULL and another SMALL halo)."""
        H, W = self.H, self.W
        over = (st.usage >= 2) & (st.usage_s >= 1)
        out = set()
        for net, cells in st.paths.items():
            r_t, _ = self._halo_cells(net)
            for (L, j, i) in cells[::max(1, r_t)]:
                j1, j2, i1, i2 = max(0, j - r_t), min(H - 1, j + r_t), max(0, i - r_t), min(W - 1, i + r_t)
                if over[L, j1:j2 + 1, i1:i2 + 1].any():
                    out.add(net); break
        return out, over

    def _sealers_of(self, st, net, terms, reach=1.25):
        """Routed nets with copper within `reach` mm of one of this net's terminals (they can seal a
        stub exit without ever overlapping the soft path, so the rip-up must include them)."""
        r = int(round(reach / GRID)); out = set()
        tcells = [self._to_cell(t[0], t[1]) for t in terms]
        for other, cells in st.paths.items():
            if other == net: continue
            for (L, j, i) in cells:
                if any(abs(j - tj) <= r and abs(i - ti) <= r for (ti, tj) in tcells):
                    out.add(other); break
        return out

    def _victims_of(self, st, net, cells):
        """Nets whose halo would overlap the halo of `cells` if they were marked for `net`."""
        self._mark(st, net, cells, +1)
        conf, _ = self._conflicts(st)
        self._mark(st, net, cells, -1)
        return conf - {net}

    def route_all(self, tasks, max_iter=14, pres_fac0=1.0, pres_growth=1.7, hist_fac=0.5, via_cost=25, turn_cost=0.6, max_nodes=2_500_000, log=print, debug_dir=None):
        H, W = self.H, self.W
        st = self._State()
        st.usage = np.zeros((2, H, W), dtype=np.int16)      # number of nets whose FULL halo covers each cell
        st.usage_s = np.zeros((2, H, W), dtype=np.int16)    # ... whose SMALL halo (r-1) covers each cell
        st.history = np.zeros((2, H, W), dtype=np.float32)
        st.paths = {}                                        # net -> list of (layer, j, i) path cells
        st.owner_count = {}                                  # net -> (tracks, vias, ok)
        st.static_blocked, st.static_novia, st.honly = {}, {}, self.build_honly()
        self._hsoft = self.build_hsoft(); self._hboth = self.build_hboth()
        st.via_cost, st.turn_cost, st.max_nodes = via_cost, turn_cost, max_nodes
        # one task per net: paths/usage are keyed by net name, so same-net tasks (e.g. several pads
        # of a zone-fallback net) are merged into one multi-terminal task
        merged = {}
        for net, terms in tasks:
            merged.setdefault(net, [])
            for t in terms:
                if t not in merged[net]:
                    merged[net].append(t)
        st.order = [(net, terms) for net, terms in merged.items()]
        st.task_of = dict(st.order)
        # soft cost around every terminal (stub exits, pads, pour goals): a track or via parked next to
        # another net's exit seals it; routes prefer to pass >= 1 mm away when they can
        st.term_cost = np.zeros((2, H, W), dtype=np.float32)
        for net, terms in st.order:
            self._add_term_cost(st.term_cost, terms, +TERM_COST)
        st.pres_fac = pres_fac0
        self.failed_terms = []
        conflict_nets = {t[0] for t in st.order}
        if os.environ.get("ROUTER_RESUME"):
            # replay the hard pass on a dumped negotiation state (same placement/config): skips ~1 h
            import pickle
            d = pickle.load(open(os.environ["ROUTER_RESUME"], "rb")); st = d["state"]
            if not hasattr(st, "term_cost"):
                st.term_cost = np.zeros((2, H, W), dtype=np.float32)
                for n_, t_ in st.order: self._add_term_cost(st.term_cost, t_, +TERM_COST)
            st.static_blocked, st.static_novia = {}, {}      # rebuilt against the current configuration
            log(f"  resumed negotiation state from {os.environ['ROUTER_RESUME']} ({len(st.pending)} pending nets)")
            max_iter = 0; conflict_nets = {n for n, _ in st.pending}
        for it in range(1, max_iter + 1):
            n_rerouted = 0
            for net, terms in st.order:
                if net not in conflict_nets:
                    continue
                self._unroute(st, net)
                cells, tracks, vias, ok = self._route_soft(st, net, terms)
                if cells:
                    self._commit(st, net, cells, tracks, vias, ok)
                else:
                    st.owner_count[net] = (tracks, vias, ok)   # nothing routable: stays incomplete
                n_rerouted += 1
            conflict_nets, over = self._conflicts(st)
            st.history += hist_fac * over.astype(np.float32)
            n_over = int(over.sum())
            if debug_dir:
                import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
                fig, ax = plt.subplots(1, 2, figsize=(14, 5))
                for L in (0, 1):
                    ax[L].imshow(np.where(over[L], 2, np.minimum(st.usage[L], 1)), origin="upper", cmap="hot", interpolation="nearest"); ax[L].set_title(f"iter {it} layer {L}: usage (1) and overlap (2)")
                fig.savefig(f"{debug_dir}/overlap_iter{it}.png", dpi=90); plt.close(fig)
                counts = []
                for net, cells in st.paths.items():
                    cnt = sum(1 for (L, j, i) in cells if over[L, j, i])
                    if cnt: counts.append((cnt, net))
                log("    worst nets by overlapped path cells: " + str(sorted(counts, reverse=True)[:12]))
            incomplete = [n for n, v in st.owner_count.items() if not v[2]]
            if self.failed_terms:
                log("    unreachable terminals: " + str(self.failed_terms[:8])); self.failed_terms = []
            log(f"  negotiation iter {it}: rerouted {n_rerouted}, overlapping cells {n_over}, conflicting nets {len(conflict_nets)}, incomplete nets {len(incomplete)}")
            if not conflict_nets and not incomplete:
                break
            conflict_nets |= set(incomplete)
            st.pres_fac *= pres_growth
        if conflict_nets:
            st.pending = [t for t in st.order if t[0] in conflict_nets]
            if os.environ.get("ROUTER_DUMP"):
                import pickle
                with open(os.environ["ROUTER_DUMP"], "wb") as fh:
                    pickle.dump(dict(router=self, state=st), fh)
            conflict_nets = self.hard_pass(st, log)
        # emit
        self.tracks_out, self.vias_out, self.failed = [], [], []
        for net, (tracks, vias, ok) in st.owner_count.items():
            self.tracks_out += tracks; self.vias_out += vias
            if not ok:
                self.failed.append((net, tracks[0][2:4] if tracks else (0, 0)))
        return not conflict_nets and not [n for n, v in st.owner_count.items() if not v[2]]

    def hard_pass(self, st, log=print, max_victims=12, depth=4):
        """
        Final pass for the nets still in conflict after the negotiation (st.pending): each is ripped up
        and re-routed against the other routed copper as hard obstacles, most constrained (most
        terminals) first; then a depth-limited rip-up-and-retry re-routes the nets a failing net
        overlaps.  State is snapshotted so a failed attempt restores the previous routing exactly.
        Emitted copper therefore never violates the clearance model; a net that cannot be routed is
        left unrouted (DRC reports it as unconnected).  Returns the set of nets left unrouted.
        """
        pending = sorted(st.pending, key=lambda t: -len(t[1]))
        still = []
        for net, terms in pending:
            self._unroute(st, net)
            cells, tracks, vias, ok = self._route_hard(st, net, terms)
            if cells and ok:
                self._commit(st, net, cells, tracks, vias)
            else:
                still.append((net, terms))
        log(f"  hard pass 1: {len(pending) - len(still)} of {len(pending)} conflicting nets re-routed cleanly")
        if self.failed_terms:
            log("    unreachable terminals (hard pass): " + str(self.failed_terms[:8])); self.failed_terms = []

        def snapshot():
            return st.usage.copy(), st.usage_s.copy(), dict(st.paths), dict(st.owner_count)
        def restore(snap):
            st.usage[...], st.usage_s[...] = snap[0], snap[1]
            st.paths.clear(); st.paths.update(snap[2]); st.owner_count.clear(); st.owner_count.update(snap[3])

        def hard_with_ripup(net, terms, depth, protected, trace):
            self._unroute(st, net)
            cells, tracks, vias, ok = self._route_hard(st, net, terms)
            if cells and ok:
                self._commit(st, net, cells, tracks, vias); return True
            if depth == 0:
                return False
            soft, _, _, sok = self._route_soft(st, net, terms, hard_nets=protected)
            if not soft or not sok:
                trace.append(("no-soft-path", net)); return False
            vict_soft = self._victims_of(st, net, soft)
            vict = (vict_soft | self._sealers_of(st, net, terms)) - protected
            if not vict or len(vict) > max_victims or (vict_soft & protected):
                trace.append(("blocked", net, sorted(vict_soft | protected)[:12]))
                return False
            snap = snapshot()
            old_paths = {v: st.paths[v] for v in vict if v in st.paths}
            for v in vict: self._unroute(st, v)
            cells, tracks, vias, ok = self._route_hard(st, net, terms, avoid=old_paths, avoid_hard=True)
            if not (cells and ok):
                self.failed_terms = []
                cells, tracks, vias, ok = self._route_hard(st, net, terms, avoid=old_paths)
            if not (cells and ok):
                restore(snap); trace.append(("hard-fail", net)); return False
            self._commit(st, net, cells, tracks, vias)
            for v in sorted(vict, key=lambda n: -len(st.task_of[n])):
                if not hard_with_ripup(v, st.task_of[v], depth - 1, protected | {net}, trace):
                    restore(snap); trace.append(("victim-fail", net, v)); return False
            trace.append((net, sorted(vict)))
            return True

        pending, still = still, []
        for net, terms in pending:
            trace = []
            if hard_with_ripup(net, terms, depth, set(), trace):
                log(f"    rip-up retry: {net} routed; {trace}")
            else:
                self._unroute(st, net); still.append((net, terms))
                log(f"    rip-up retry failed for {net}: {trace[-6:]}")
            self.failed_terms = []
        log(f"  hard pass 2 (rip-up retry): {len(pending) - len(still)} of {len(pending)} re-routed cleanly")
        # round 3: region re-route.  Rip up every net with copper within 3 mm of the failing net's
        # terminals, route the failing net first (hard, keeping the ripped nets' old space free where
        # possible), then re-route the ripped nets one by one with the rip-up retry.  Kept only if all
        # of them route cleanly.
        pending, still = still, []
        for net, terms in pending:
            self._unroute(st, net)
            ok_all = False; region = set()
            for reach in (3.0, 5.0, 8.0):          # widen the region when a stack of tracks seals the terminal
                region = self._sealers_of(st, net, terms, reach=reach)
                snap = snapshot(); ok_all = False
                if 0 < len(region) <= 40:
                    old = {v: st.paths[v] for v in region if v in st.paths}
                    for v in region: self._unroute(st, v)
                    cells, tracks, vias, ok = self._route_hard(st, net, terms, avoid=old)
                    if cells and ok:
                        self._commit(st, net, cells, tracks, vias); ok_all = True
                        for v in sorted(region, key=lambda n: -len(st.task_of[n])):
                            tr = []
                            if not hard_with_ripup(v, st.task_of[v], 2, {net}, tr):
                                ok_all = False; log(f"    region re-route of {net} (reach {reach}): {v} failed {tr[-3:]}"); break
                    else:
                        log(f"    region re-route of {net} (reach {reach}, {len(region)} nets): still unreachable {self.failed_terms[:2]}")
                    self.failed_terms = []
                else:
                    log(f"    region re-route of {net} (reach {reach}): region size {len(region)} not usable")
                if ok_all: break
                restore(snap); self._unroute(st, net)
            if ok_all:
                log(f"    region re-route: {net} routed after re-routing {sorted(region)}")
            else:
                self._unroute(st, net); still.append((net, terms))
        log(f"  hard pass 3 (region re-route): {len(pending) - len(still)} of {len(pending)} re-routed cleanly")
        for net, _ in still:
            st.owner_count[net] = ([], [], False)
        return {n for n, _ in still}

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
                self.failed_terms.append((net, best))
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
        cost_map, cost_map_via = cost_map
        hsoft = getattr(self, "_hsoft", None); hboth = getattr(self, "_hboth", None)
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
                if dj != 0 and hboth is not None and hboth[j, i] and (L, nj, ni) not in goals: continue
                if blocked[L, nj, ni] and (L, nj, ni) not in goals and (L, nj, ni) not in sources: continue
                c = gc + (1.5 if L == F else 1.0) + float(cost_map[L, nj, ni])
                if dj != 0 and L == F and hsoft is not None and hsoft[j, i]:
                    c += MOUTH_COST            # turning vertical right at a corridor mouth seals the other exits
                if pdir is not None and pdir != (dj, di): c += turn_cost
                if (L == F and dj != 0) or (L == B and di != 0): c += 0.15
                if c < g[L, nj, ni]:
                    g[L, nj, ni] = c; parent[L, nj, ni] = L * H * W + j * W + i
                    heapq.heappush(heap, (c + h(nj, ni), c, L, nj, ni))
            oL = 1 - L
            if not novia[j, i] and not blocked[oL, j, i]:
                c = gc + via_cost + float(cost_map_via[j, i]) * 4
                if c < g[oL, j, i]:
                    g[oL, j, i] = c; parent[oL, j, i] = L * H * W + j * W + i
                    heapq.heappush(heap, (c + h(j, i), c, oL, j, i))
        return None
