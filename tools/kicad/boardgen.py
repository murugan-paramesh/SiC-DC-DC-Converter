"""
Reusable PCB generator (pcbnew API) driven by a BoardConfig.  Extracted from the PSFB
generator so that the DAB board uses exactly the same, already-exercised machinery:
footprint placement -> pours/planes -> explicit tracks -> fan-out stubs -> stitching vias ->
reload with project -> grid routing (router.py, rip-up) -> zone fill -> DRC report.
"""
import os, sys, json, math, functools, re, collections
import pcbnew
from .router import Router, NegotiatedRouter, Rect, F, B, GRID

print = functools.partial(print, flush=True)
MM = pcbnew.FromMM
V = lambda x, y: pcbnew.VECTOR2I_MM(x, y)
FULL, THERM = "full", "thermal"
LAYER_IDS = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu, "In1.Cu": pcbnew.In1_Cu, "In2.Cu": pcbnew.In2_Cu, "In3.Cu": pcbnew.In3_Cu, "In4.Cu": pcbnew.In4_Cu}


class BoardConfig:
    def __init__(self, **kw):
        self.project = kw["project"]; self.lib = kw["lib"]; self.outdir = kw["outdir"]; self.libdir = kw["libdir"]
        self.design = kw["design"]                       # module with build(), nets_of(), net_class()
        self.BW, self.BH = kw["BW"], kw["BH"]
        self.layers = kw.get("layers", 4)
        self.placement = kw["placement"]                 # ref -> (x, y, rot)
        self.zones = kw["zones"]                         # (net, layer, [rects], priority, conn)
        self.tracks = kw.get("tracks", [])               # (net, layer, x1, y1, x2, y2, w)
        self.keepout_rects = kw.get("keepout_rects", []) # rule areas (all copper layers) and router keepouts
        self.router_keepouts = kw.get("router_keepouts", [])  # extra router-only keepouts
        self.private = kw.get("private", [])             # (rect, [refs])
        self.fanout = kw.get("fanout", {})               # ref -> (short, long, width)
        self.plane_nets = set(kw.get("plane_nets", []))
        self.pair_clearance = kw["pair_clearance"]; self.track_width = kw["track_width"]
        self.dru_rules = kw.get("dru_rules", [])         # (name, condition, clearance_mm)
        self.dru_header = kw.get("dru_header", "")
        self.via_forbidden = kw.get("via_forbidden", lambda x, y: False)
        self.edge_slots = kw.get("edge_slots", [])       # (x1, y1, x2, y2)
        self.texts = kw.get("texts", [])                 # (text, x, y, layer, size, thick, rot)
        self.solid_zone_pads = set(kw.get("solid_zone_pads", []))   # (ref, pad): solid pour connection (no thermal spokes)
        self.exit_bands = kw.get("exit_bands", [])        # rects where tracks may only run straight out (no vertical moves, no vias)
        self.lines = kw.get("lines", [])                 # (x1, y1, x2, y2, layer, w)
        self.max_passes = kw.get("max_passes", 3)
        self.route_priority = kw.get("route_priority", {})
        self.zone_fallback_nets = set(kw.get("zone_fallback_nets", []))   # zone nets whose uncovered pads are routed to the pour
        self.board_thickness = kw.get("board_thickness", 2.0)
        self.min_clearance = kw.get("min_clearance", 0.2)


class BoardGen:
    def __init__(self, cfg):
        self.cfg = cfg
        self.PCB = os.path.join(cfg.outdir, f"{cfg.project}.kicad_pcb")
        self.PRO = os.path.join(cfg.outdir, f"{cfg.project}.kicad_pro")
        self.DRU = os.path.join(cfg.outdir, f"{cfg.project}.kicad_dru")
        self.zone_nets = {z[0] for z in cfg.zones}

    # ----------------------------------------------------------- primitives
    def add_track(self, board, net, layer, x1, y1, x2, y2, w):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(V(x1, y1)); t.SetEnd(V(x2, y2)); t.SetWidth(MM(w)); t.SetLayer(LAYER_IDS[layer] if isinstance(layer, str) else layer)
        t.SetNet(net); board.Add(t); return t

    def add_via(self, board, net, x, y, size=0.8, drill=0.4):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(V(x, y)); v.SetDrill(MM(drill)); v.SetWidth(MM(size)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(net); board.Add(v); return v

    def add_zone(self, board, net, layer, rect, prio, conn, name=""):
        z = pcbnew.ZONE(board)
        z.SetLayer(LAYER_IDS[layer]); z.SetNet(net)
        ol = z.Outline(); ol.NewOutline()
        x1, y1, x2, y2 = rect
        for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
            ol.Append(MM(x), MM(y))
        if hasattr(z, "SetAssignedPriority"): z.SetAssignedPriority(prio)
        else: z.SetPriority(prio)
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if conn == FULL else pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetMinThickness(MM(0.25)); z.SetLocalClearance(MM(0.5 if prio else 0.3))
        z.SetThermalReliefGap(MM(0.5)); z.SetThermalReliefSpokeWidth(MM(0.8))
        z.SetZoneName(name or f"{net.GetNetname()}_{layer}")
        board.Add(z); return z

    def add_rule_area(self, board, rect, layers):
        z = pcbnew.ZONE(board)
        z.SetIsRuleArea(True); z.SetDoNotAllowCopperPour(True); z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
        ls = pcbnew.LSET()
        for L in layers: ls.addLayer(L)
        z.SetLayerSet(ls)
        ol = z.Outline(); ol.NewOutline()
        x1, y1, x2, y2 = rect
        for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
            ol.Append(MM(x), MM(y))
        z.SetZoneName("isolation_keepout"); board.Add(z); return z

    def add_edge_rect(self, board, x1, y1, x2, y2):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_RECT); s.SetStart(V(x1, y1)); s.SetEnd(V(x2, y2))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); board.Add(s); return s

    def add_text(self, board, txt, x, y, layer=pcbnew.F_SilkS, size=2.0, thick=0.3, rot=0):
        t = pcbnew.PCB_TEXT(board); t.SetText(txt); t.SetPosition(V(x, y)); t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size))); t.SetTextThickness(MM(thick)); t.SetTextAngleDegrees(rot)
        board.Add(t); return t

    def add_line(self, board, x1, y1, x2, y2, layer, w=0.3):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(V(x1, y1)); s.SetEnd(V(x2, y2))
        s.SetLayer(layer); s.SetWidth(MM(w)); board.Add(s); return s

    @staticmethod
    def set_severities(ds):
        ignore = ["DRCE_OVERLAPPING_SILK", "DRCE_SILK_CLEARANCE", "DRCE_SILK_EDGE_CLEARANCE", "DRCE_LIB_FOOTPRINT_ISSUES", "DRCE_LIB_FOOTPRINT_MISMATCH", "DRCE_SILK_MASK_CLEARANCE"]
        warn = ["DRCE_STARVED_THERMAL", "DRCE_DANGLING_TRACK", "DRCE_ISOLATED_COPPER", "DRCE_COPPER_SLIVER"]
        try:
            for n in ignore:
                if hasattr(pcbnew, n): ds.m_DRCSeverities[getattr(pcbnew, n)] = pcbnew.RPT_SEVERITY_IGNORE
            for n in warn:
                if hasattr(pcbnew, n): ds.m_DRCSeverities[getattr(pcbnew, n)] = pcbnew.RPT_SEVERITY_WARNING
        except Exception as e:
            print("severity setup:", e)

    def write_dru(self):
        with open(self.DRU, "w") as fh:
            fh.write("(version 1)\n")
            if self.cfg.dru_header:
                fh.write(self.cfg.dru_header)
            for name, cond, clr in self.cfg.dru_rules:
                fh.write(f'(rule "{name}"\n  (condition "{cond}")\n  (constraint clearance (min {clr}mm)))\n')

    # ----------------------------------------------------------- board
    def build_board(self, comps, uuids):
        cfg = self.cfg
        board = pcbnew.CreateEmptyBoard()
        ds = board.GetDesignSettings()
        ds.SetCopperLayerCount(cfg.layers)
        ds.m_MinClearance = MM(cfg.min_clearance); ds.m_TrackMinWidth = MM(0.2); ds.m_ViasMinSize = MM(0.5); ds.m_ViasMinAnnularWidth = MM(0.15)
        ds.m_CopperEdgeClearance = MM(0.5); ds.m_HoleClearance = MM(0.25); ds.m_HoleToHoleMin = MM(0.25); ds.m_MinThroughDrill = MM(0.3)
        try: ds.SetBoardThickness(MM(cfg.board_thickness))
        except Exception: pass
        for name, lid in LAYER_IDS.items():
            if name.startswith("In") and int(name[2]) * 1 <= cfg.layers - 2:
                board.SetLayerName(lid, name)
        self.set_severities(ds)
        self.add_edge_rect(board, 0, 0, cfg.BW, cfg.BH)
        for x1, y1, x2, y2 in cfg.edge_slots:
            self.add_edge_rect(board, x1, y1, x2, y2)
        nets = {}
        for net in sorted(cfg.design.nets_of(comps)):
            if net.startswith("NC_"): continue
            ni = pcbnew.NETINFO_ITEM(board, net); board.Add(ni); nets[net] = ni
        for c in comps:
            if c.ref not in cfg.placement:
                raise SystemExit(f"no placement for {c.ref}")
            fp = pcbnew.FootprintLoad(cfg.libdir, c.footprint)
            if fp is None:
                raise SystemExit(f"footprint {c.footprint} not found in {cfg.libdir}")
            x, y, rot = cfg.placement[c.ref]
            fp.SetReference(c.ref); fp.SetValue(c.value)
            fp.SetPosition(V(x, y)); fp.SetOrientationDegrees(rot)
            sheet_uuid, sym_uuid = uuids["symbols"][c.ref]
            fp.SetPath(pcbnew.KIID_PATH(f"/{sheet_uuid}/{sym_uuid}"))
            fp.Value().SetVisible(False)
            fp.SetFPID(pcbnew.LIB_ID(cfg.lib, c.footprint))        # library nickname as in fp-lib-table
            ref = fp.Reference()
            ref.SetTextSize(pcbnew.VECTOR2I(MM(0.9), MM(0.9))); ref.SetTextThickness(MM(0.15))
            # reference designator just above the courtyard (clear of the pads, readable silk)
            bb = fp.GetBoundingBox(False, False)       # pads + graphics (courtyard), no text
            if bb.GetHeight() > 0:
                ref.SetPosition(pcbnew.VECTOR2I(bb.GetCenter().x, bb.GetTop() - MM(0.8)))
                ref.SetKeepUpright(True)
            for pad in fp.Pads():
                net = c.pins.get(pad.GetNumber())
                if net and not net.startswith("NC_"):
                    pad.SetNet(nets[net])
                if (c.ref, pad.GetNumber()) in cfg.solid_zone_pads:
                    pad.SetZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
            board.Add(fp)
        for net, layer, rects, prio, conn in cfg.zones:
            for k, r in enumerate(rects):
                self.add_zone(board, nets[net], layer, r, prio, conn, name=f"{net}_{layer}_{k}")
        cu_layers = [pcbnew.F_Cu, pcbnew.B_Cu] + [LAYER_IDS[f"In{i}.Cu"] for i in range(1, cfg.layers - 1)]
        for rct in cfg.keepout_rects:
            self.add_rule_area(board, rct, cu_layers)
        for net, layer, x1, y1, x2, y2, w in cfg.tracks:
            self.add_track(board, nets[net], layer, x1, y1, x2, y2, w)
        for txt, x, y, layer, size, thick, rot in cfg.texts:
            self.add_text(board, txt, x, y, layer=layer, size=size, thick=thick, rot=rot)
        for x1, y1, x2, y2, layer, w in cfg.lines:
            self.add_line(board, x1, y1, x2, y2, layer, w)
        return board, nets

    # ----------------------------------------------------------- geometry helpers
    @staticmethod
    def pad_info(board):
        out = []
        for fp in board.GetFootprints():
            fx, fy = pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)
            for pad in fp.Pads():
                bb = pad.GetBoundingBox()
                r = Rect(pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))
                layers = set()
                if pad.IsOnLayer(pcbnew.F_Cu): layers.add(F)
                if pad.IsOnLayer(pcbnew.B_Cu): layers.add(B)
                npth = pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH
                tht = pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH
                c = (pcbnew.ToMM(pad.GetPosition().x), pcbnew.ToMM(pad.GetPosition().y))
                out.append((fp.GetReference(), pad.GetNumber(), pad.GetNetname(), r, layers if not npth else {F, B}, c, tht, npth, (fx, fy)))
        return out

    def stitch_vias(self, board, nets, pads, router, extra_occupied=()):
        cfg = self.cfg
        occupied = [p[3] for p in pads] + list(extra_occupied)
        # never stitch inside a pour rectangle of another net (a via plus its clearance would cut a strip)
        zone_occ = [(net_, Rect(*r_).expand(1.0)) for net_, layer_, rects_, prio_, conn_ in cfg.zones if prio_ > 0 for r_ in rects_]
        def free(x, y, r=0.45):
            rr = Rect(x - r, y - r, x + r, y + r)
            for o in occupied:
                if not (rr.x2 < o.x1 - 0.25 or rr.x1 > o.x2 + 0.25 or rr.y2 < o.y1 - 0.25 or rr.y1 > o.y2 + 0.25):
                    return False
            if cfg.via_forbidden(x, y) or x < 1.5 or y < 1.5 or x > cfg.BW - 1.5 or y > cfg.BH - 1.5:
                return False
            return True
        count = 0
        for ref, num, net, r, layers, (cx, cy), tht, npth, (fx, fy) in pads:
            if tht or npth or net not in cfg.plane_nets or ref in cfg.fanout:
                continue
            w, h = r.x2 - r.x1, r.y2 - r.y1
            if w >= 5 and h >= 5:
                dx = 1 if cx > fx else -1
                cands = [((cx + dx * (w / 2 + 0.8)), cy + k) for k in (-2, 0, 2)]
            else:
                vert = abs(cy - fy) > abs(cx - fx)
                d = 0.95
                if vert:
                    cands = [(cx + w / 2 + d, cy), (cx - w / 2 - d, cy), (cx, cy + (h / 2 + d) * (1 if cy >= fy else -1))]
                else:
                    cands = [(cx, cy + h / 2 + d), (cx, cy - h / 2 - d), (cx + (w / 2 + d) * (1 if cx >= fx else -1), cy)]
            for (vx, vy) in cands:
                if not free(vx, vy) or any(zn != net and zr.contains(vx, vy) for zn, zr in zone_occ):
                    continue
                self.add_via(board, nets[net], vx, vy)
                self.add_track(board, nets[net], "F.Cu", cx, cy, vx, vy, min(0.6, max(0.3, min(w, h) - 0.1)))
                occupied.append(Rect(vx - 0.4, vy - 0.4, vx + 0.4, vy + 0.4))
                router.register_via(net, vx, vy)
                router.add_item(net, [F], Rect(min(cx, vx) - 0.3, min(cy, vy) - 0.3, max(cx, vx) + 0.3, max(cy, vy) + 0.3))
                count += 1
                if not (w >= 5 and h >= 5):
                    break
        print(f"stitching vias: {count}")

    def fanout_stubs(self, board, nets, pads, router):
        cfg = self.cfg
        terminals, stub_rects, cols = {}, [], {}
        for ref, num, net, r, layers, (cx, cy), tht, npth, (fx, fy) in pads:
            if ref in cfg.fanout:
                cols.setdefault((ref, -1 if cx < fx else 1), []).append((cy, cx, num, net))
        for (ref, d), plist in cols.items():
            short, long_, w = cfg.fanout[ref]
            plist.sort()
            xs, ys = [], []
            for k, (cy, cx, num, net) in enumerate(plist):
                L_ = short if k % 2 == 0 else long_
                if net in cfg.plane_nets:
                    L_ = long_          # plane via sits beyond the stub field, clear of the neighbours' long stubs
                ex = cx + d * L_
                if net:
                    self.add_track(board, nets[net], "F.Cu", cx, cy, ex, cy, w)
                    rr = Rect(min(cx, ex) - w / 2, cy - w / 2, max(cx, ex) + w / 2, cy + w / 2)
                    router.add_item(net, [F], rr); stub_rects.append(rr)
                    if net in cfg.plane_nets:
                        vx = ex + d * 1.2      # 1.2 mm beyond the long stubs: clear of the neighbouring stub exits
                        self.add_via(board, nets[net], vx, cy); router.register_via(net, vx, cy)
                        self.add_track(board, nets[net], "F.Cu", ex, cy, vx, cy, w)
                        stub_rects.append(Rect(vx - 0.5, cy - 0.5, vx + 0.5, cy + 0.5))
                    else:
                        terminals[(ref, num)] = (ex, cy, {F})
                xs.append(cx); ys.append(cy)
            pad_half = max(abs(p[3].x2 - p[3].x1) for p in pads if p[0] == ref) / 2
            inner = (min(xs) + pad_half) if d < 0 else (max(xs) - pad_half)
            outer = (min(xs) if d < 0 else max(xs)) + d * (short - 0.7)
            x1, x2 = sorted((inner, outer))
            router.keepouts.append(Rect(x1, min(ys) - 0.6, x2, max(ys) + 0.6))
            far = (min(xs) if d < 0 else max(xs)) + d * (long_ + 1.5)
            cx1, cx2 = sorted((outer, far))
            router.h_only.append(Rect(cx1, min(ys) - 1.0, cx2, max(ys) + 1.0))
            mx1, mx2 = sorted((far, far + d * 1.5))
            router.h_soft.append(Rect(mx1, min(ys) - 1.0, mx2, max(ys) + 1.0))   # mouth band: turn further out
        return terminals, stub_rects

    # ----------------------------------------------------------- routing
    def route(self, board, nets):
        cfg = self.cfg
        pads = self.pad_info(board)
        router = NegotiatedRouter(cfg.BW, cfg.BH, cfg.pair_clearance, cfg.track_width,
                                  keepouts=list(cfg.keepout_rects) + list(cfg.router_keepouts))
        router.h_both = [Rect(*b) for b in cfg.exit_bands]
        for ref, num, net, r, layers, c, tht, npth, fc in pads:
            router.add_item(net if net else "", layers, r)
        for net, layer, rects, prio, conn in cfg.zones:
            if prio == 0: continue
            L_ = F if layer == "F.Cu" else (B if layer == "B.Cu" else None)
            if L_ is None: continue
            for rct in rects:
                router.add_item(net, [L_], Rect(*rct))
        for net, layer, x1, y1, x2, y2, w in cfg.tracks:
            router.add_item(net, [F if layer == "F.Cu" else B], Rect(min(x1, x2) - w / 2, min(y1, y2) - w / 2, max(x1, x2) + w / 2, max(y1, y2) + w / 2))
        stubs, stub_rects = self.fanout_stubs(board, nets, pads, router)
        self.stitch_vias(board, nets, pads, router, extra_occupied=stub_rects)
        fp_nets = {}
        for ref, num, net, r, layers, c, tht, npth, fc in pads:
            if net: fp_nets.setdefault(ref, set()).add(net)
        for rct, refs in cfg.private:
            allowed = set()
            for ref in refs: allowed |= fp_nets.get(ref, set())
            router.add_private(rct, allowed)
        netpads = {}
        for ref, num, net, r, layers, c, tht, npth, fc in pads:
            if net and not npth:
                netpads.setdefault(net, []).append((ref, num, c, layers, tht, r))
        zone_rects = {}
        for net, layer, rects, prio, conn in cfg.zones:
            L_ = F if layer == "F.Cu" else (B if layer == "B.Cu" else None)
            for rct in rects: zone_rects.setdefault(net, []).append((rct, L_))
        tasks = []; blocked_cache = {}
        for net, plist in netpads.items():
            if net in self.zone_nets or net in cfg.zone_fallback_nets:
                uncovered = []
                for ref, num, c, layers, tht, r in plist:
                    # covered when inside a pour rectangle of its net on a layer it is on; a THT pin outside its
                    # plane region (bias-module GND pin in the barrier cut-out) gets a routed link to the pour
                    covered = any(x1 <= c[0] <= x2 and y1 <= c[1] <= y2 and (L_ in layers or tht)
                                  for (x1, y1, x2, y2), L_ in zone_rects.get(net, []))
                    if net in cfg.plane_nets and ref in cfg.fanout:
                        covered = True          # fan-out pin of a plane net: its stub via lands in the plane
                    if net in cfg.zone_fallback_nets and net not in self.zone_nets:
                        covered = True
                    if not covered:
                        uncovered.append((ref, num, c, layers))
                for ref, num, c, layers in uncovered:
                    best = None
                    for (x1, y1, x2, y2), L_ in zone_rects.get(net, []):
                        if L_ is None: continue
                        gx = min(max(c[0], x1 + 2), x2 - 2); gy = min(max(c[1], y1 + 2), y2 - 2)   # 2 mm inside the pour, clear of pad halos at its edge
                        d = abs(gx - c[0]) + abs(gy - c[1])
                        if best is None or d < best[0]: best = (d, gx, gy, L_)
                    if best:
                        # step the goal towards the pour centre until the cell is free for this net
                        d_, gx, gy, L_ = best
                        if net not in blocked_cache:
                            blocked_cache[net] = router.build_blocked(net)[0]
                        bl = blocked_cache[net]
                        for (x1, y1, x2, y2), LL in zone_rects.get(net, []):
                            if LL == L_ and x1 <= gx <= x2 and y1 <= gy <= y2:
                                cxm, cym = (x1 + x2) / 2, (y1 + y2) / 2
                                for _ in range(40):
                                    ci, cj = router._to_cell(gx, gy)
                                    if not bl[L_, cj, ci]: break
                                    gx += 0.25 if cxm > gx else (-0.25 if cxm < gx else 0)
                                    if abs(cxm - gx) < 0.5: gy += 0.25 if cym > gy else -0.25
                                break
                        tasks.append((net, [(c[0], c[1], layers), (gx, gy, {L_})]))
                continue
            terms = []
            for ref, num, c, layers, tht, r in plist:
                terms.append(stubs[(ref, num)] if (ref, num) in stubs else (c[0], c[1], layers))
            tasks.append((net, terms))
        def span(t):
            xs = [p[0] for p in t[1]]; ys = [p[1] for p in t[1]]
            return (max(xs) - min(xs)) + (max(ys) - min(ys))
        prio = cfg.route_priority
        tasks.sort(key=lambda t: (prio.get(t[0], 10), span(t)))
        router.route_all(tasks, max_iter=cfg.max_passes)
        for net, L_, x1, y1, x2, y2, w in router.tracks_out:
            self.add_track(board, nets[net], pcbnew.F_Cu if L_ == F else pcbnew.B_Cu, x1, y1, x2, y2, w)
        for net, x, y in router.vias_out:
            self.add_via(board, nets[net], x, y)
        print(f"routed tracks: {len(router.tracks_out)}, vias: {len(router.vias_out)}, failed terminals: {len(router.failed)}")
        for f_ in router.failed:
            print("   FAILED:", f_)
        return router.failed

    # ----------------------------------------------------------- drc + main
    def drc(self, board, report):
        pcbnew.WriteDRCReport(board, report, pcbnew.EDA_UNITS_MILLIMETRES, True)
        txt = open(report).read()
        kinds = collections.Counter(re.findall(r"^\[(\w+)\]", txt, re.M))
        sev = collections.Counter(re.findall(r"Severity: (\w+)", txt))
        unconnected = re.search(r"Found (\d+) unconnected", txt)
        return kinds, sev, int(unconnected.group(1)) if unconnected else -1, txt

    def main(self, do_route=True):
        cfg = self.cfg
        comps = cfg.design.build()
        uuids = json.load(open(os.path.join(cfg.outdir, "uuids.json")))
        self.write_dru()
        board, nets = self.build_board(comps, uuids)
        pcbnew.SaveBoard(self.PCB, board)
        print("board placed & saved; reloading with project")
        sm = pcbnew.GetSettingsManager(); sm.LoadProject(self.PRO)
        board = pcbnew.LoadBoard(self.PCB)
        try: board.SetProject(sm.GetProject(self.PRO))
        except Exception as e: print("SetProject:", e)
        all_nets = [n for n in cfg.design.nets_of(comps) if not n.startswith("NC_")]
        nets = {n: board.FindNet(n) for n in all_nets}
        failed = self.route(board, nets) if do_route else []
        board.BuildConnectivity()
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(self.PCB, board)
        print("zones filled, board saved. running DRC ...")
        rpt = os.path.join(cfg.outdir, "drc_report.txt")
        kinds, sev, unconnected, txt = self.drc(board, rpt)
        print("DRC summary:", dict(kinds)); print("severities:", dict(sev)); print("unconnected:", unconnected)
        summary = dict(failed_terminals=[(f_[0], f_[1][0], f_[1][1]) for f_ in failed], drc_kinds=dict(kinds), severities=dict(sev), unconnected=unconnected)
        json.dump(summary, open(os.path.join(cfg.outdir, "drc_summary.json"), "w"), indent=1)
        return failed, kinds, unconnected


def grp(var, names):
    return "(" + " || ".join(f"{var}.NetName == '{n}'" for n in names) + ")"


def pair(ga, gb):
    return f"({grp('A', ga)} && {grp('B', gb)}) || ({grp('A', gb)} && {grp('B', ga)})"
