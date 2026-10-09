# tools/kicad - script-generated KiCad 7 projects

Both boards in this repository (PSFB reference design, 6.6 kW DAB platform) are produced
end-to-end by Python: symbol/footprint libraries, hierarchical schematics, placement, pours,
fan-out, signal routing and the KiCad DRC run. Nothing is hand-edited in the KiCad GUI, so a
change in the design tables regenerates everything reproducibly.

| module | role |
|---|---|
| `sexpr.py` | tiny s-expression writer |
| `symbols.py`, `footprints.py` | generic symbol/footprint builders and the shared libraries |
| `design.py` | PSFB component/net tables (the DAB equivalent is `SiC_6k6_Industrial_DAB/dabtools/kicad_dab/design_dab.py`) |
| `gen_schematic.py` | label-netlist hierarchical schematic writer; `check_netlist.py` compares the kicad-cli netlist with the design tables |
| `boardgen.py` | `BoardConfig`/`BoardGen`: board outline, placement, pours, rule areas, plane stitching vias, fine-pitch fan-out, routing, zone fill, DRC report and `drc_summary.json` |
| `router.py` | grid router (below) |
| `plot_board.py` | matplotlib renderer of a board region (`python3 -m tools.kicad.plot_board board.kicad_pcb out.png x1 y1 x2 y2 [--nets a,b]`) for layout review |
| `gen_pcb.py` | PSFB board configuration (`python3 -m tools.kicad.gen_pcb`) |
| `bom.py` | PSFB BOM |

## Router (`router.py`)

Two-layer (F.Cu/B.Cu) grid router on a 0.25 mm grid, used for the signal and auxiliary-power
nets; power paths are pours and pre-placed wide tracks.

* **Static obstacles.** Every pad, pour rectangle, pre-placed track, stub and plane via is an
  item with a net. For the net being routed, items of other nets are dilated by
  `clearance(net, other) + width(net)/2` (per layer); the no-via map is dilated by
  `clearance + via/2`. Clearances come from the board's net-class function, so the isolation
  distances (8 mm PSFB, 12/10/8/5.5 mm DAB) are hard obstacles, never soft costs. Keep-out
  rectangles, private regions (bias-module pin fields) and the board edge are added on top.
* **Fine-pitch fan-out.** Pins of listed ICs get alternating short/long stubs; plane-net pins get a
  long stub with a via 1.2 mm beyond it. A hard keep-out covers the pad field, and a
  "horizontal-only, via-free" corridor extends 1.5 mm beyond the long stubs so no net can fence
  the stub exits.
* **Negotiated congestion (PathFinder, McMurchie & Ebeling 1995).** All nets are routed by A*
  against the static obstacles; copper of other routed nets is a soft cost (present usage x
  `pres_fac` + history). Each net marks a *full* halo (radius `r = ceil((w/2 + clearance/2)/grid)`)
  and a *small* halo (`r-1`); two nets conflict when a cell lies in one net's full halo and the
  other's small halo, i.e. exactly when their centre lines are closer than
  `w_a/2 + w_b/2 + clearance`. The A* cost for a track cell is the Chebyshev maximum filter of the
  usage map with the net's own radius (the via cost uses the via radius on both layers), so a
  re-routed net accounts for its own halo. Conflicting nets are re-routed with `pres_fac`
  growing by 1.7 per iteration.
* **Hard pass.** Nets still in conflict after `max_passes` iterations are ripped up and re-routed
  one by one against the other routed copper as hard obstacles; a bounded rip-up-and-retry then
  re-routes the nets a failing net overlaps (accepted only if every victim routes cleanly). A net
  that cannot be routed this way is left unrouted, which KiCad's DRC reports as an unconnected
  item - the router never emits copper that violates its clearance model. Unreachable terminals
  (static enclosure, usually a placement problem) are listed in the log.
* **Verification.** The result is always checked by KiCad's own DRC (`drc_report.txt`,
  `drc_summary.json`): clearance, hole clearance, courtyards, unconnected items, starved thermal
  reliefs. The custom `.kicad_dru` rules for the isolation classes are part of that run.

Diagnostics used during layout work: `NegotiatedRouter.route_all(..., debug_dir=...)` writes
per-iteration overlap maps; `Router.debug_dump(net, x, y)` prints the blocked/horizontal-only/no-via
maps around a point, `Router.what_blocks(net, x, y)` lists the items that block it.
