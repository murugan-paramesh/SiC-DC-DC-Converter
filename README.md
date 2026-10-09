# SiC isolated DC-DC converters: PSFB 3 kW baseline and 6.6 kW bidirectional DAB research platform

Two complete, script-generated KiCad 7 hardware designs with their calculations, simulations, firmware
and documentation. Nothing here has been built or measured; every result is labelled by how it was
obtained (calculation, simulation, software-in-the-loop, DRC).

| Design | Where | Status |
|---|---|---|
| **PSFB 3 kW**, 400 V -> 48 V, SiC primary, synchronous rectification, UCC28951 | `hardware/kicad/SiC_PSFB_3kW.kicad_pro`, `docs/`, `tools/`, `simulation/` | schematic generated and netlist-verified; PCB generated with zones/planes and auto-routed signals (DRC state in `hardware/kicad/drc_summary.json`); switched simulation agrees with the design |
| **DAB 6.6 kW**, 650-850 V <-> 300-450 V bidirectional, SiC both bridges, C2000 control | `SiC_6k6_Industrial_DAB/` (see its README) | full research/engineering chain: requirements, models, design, simulation (Python + ngspice), control + firmware (SIL-tested), 6-layer KiCad PCB, thermal/EMI/safety/FMEA, optimisation, BOM, manufacturing outputs, verification report, research report, lab plan |

Shared tooling: `tools/kicad/` (symbol/footprint generators, hierarchical schematic generator,
`boardgen.py` PCB builder on the pcbnew API with a negotiated-congestion grid router and DRC).

Quick start (PSFB): `python3 tools/psfb_design.py && python3 -m tools.kicad.gen_schematic && python3 -m tools.kicad.gen_pcb`.
Quick start (DAB): see `SiC_6k6_Industrial_DAB/README.md`.

Safety: both designs carry hazardous voltages (420 V / 850 V DC). No prototype should be energised
before an independent engineering review and an approved laboratory procedure
(`SiC_6k6_Industrial_DAB/20_Experimental_Test_Plan/`).
