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
                self.register_via(net, a[2] * GRID, a[1] * GRID)
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
            self.items.append((net, frozenset([L]), Rect(i * GRID - hw, j * GRID - hw, i * GRID + hw, j * GRID + hw)))

    def _flush(self, net, a, b, w):
        if a == b:
            return
        self.tracks_out.append((net, a[0], a[2] * GRID, a[1] * GRID, b[2] * GRID, b[1] * GRID, w))

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

    def register_via(self, net, x, y):
        vr = self.via_size / 2
        self.items.append((net, frozenset([F, B]), Rect(x - vr, y - vr, x + vr, y + vr)))
