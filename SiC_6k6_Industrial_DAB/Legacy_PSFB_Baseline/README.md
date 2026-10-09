# Legacy PSFB baseline (3 kW, 400 V -> 48 V, ZVS phase-shifted full bridge)

The PSFB reference design is preserved unchanged at the repository root:

| Item | Path |
|---|---|
| Design calculations | `../../tools/psfb_design.py` -> `../../docs/02_design_calculations.md` |
| KiCad 7 project (schematic + PCB, generated) | `../../hardware/kicad/SiC_PSFB_3kW.kicad_pro` |
| Symbol / footprint libraries | `../../hardware/kicad/lib/` |
| Generators (shared with the DAB) | `../../tools/kicad/` (design.py, gen_schematic.py, boardgen.py, router.py) |
| Documentation | `../../docs/01..07_*.md` |
| Switched-model simulation | `../../simulation/psfb_sim.py` |
| BOM | `../../hardware/bom/` |

It serves as the comparative baseline in `02_Topology_Comparison/` and as the test bed for the
schematic/PCB generation chain reused by the DAB. Its PCB routing status is tracked in
`../../hardware/kicad/drc_summary.json`.
