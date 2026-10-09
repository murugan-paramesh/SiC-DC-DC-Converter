# SiC 6.6 kW Industrial Bidirectional DAB - research and engineering package

Bidirectional dual active bridge, 650-850 V DC <-> 300-450 V DC, 6.6 kW, 100 kHz, 1200 V SiC on
both bridges, TI C2000 digital control. Everything in this directory is generated or verified by
scripts; **no hardware has been built, energised or measured**. The PSFB 3 kW design at the
repository root is the preserved baseline (`Legacy_PSFB_Baseline/README.md`).

## Directory map

| Folder | Content | How it was verified |
|---|---|---|
| `00_Requirements/` | existing-project audit, requirements with explicit service conditions, operating-envelope definition, RTM (`03_RTM.csv`) | reviewed; status column refreshed by `18_Verification/run_verification.py` |
| `01_Literature_Review/` | 38 references (DAB, modulation, SiC, magnetics, control, standards) with a citation-policy note | recalled, to cross-check |
| `02_Topology_Comparison/` | `topology_comparison.py` -> quantitative PSFB/DAB/CLLLC/2-ph/3-ph comparison, decision | script run |
| `03_Mathematical_Models/` | derivations (SPS/EPS/DPS/TPS, ZVS, losses, averaged model) ; code in `dabtools/dab/` | numeric vs closed form < 0.1 % |
| `04_Design_Calculations/` | `dab_design.py` -> `design_values.json`, `design_report.md`, derating/ZVS maps, loss budget, DC link, protection thresholds | script run |
| `05_Simulation/` | closed-loop switched model (`run_switched_sim.py`), ngspice switching model (`gen_spice.py`), results + plots | both run; agree with analysis |
| `06_Magnetics/` | transformer/inductor design, core comparison, insulation, test procedure | script run |
| `07_KiCad_Schematics/` | **KiCad 7 project** `SiC_DAB_6k6.kicad_pro` (5 sheets, 259 components) + the 6-layer PCB `SiC_DAB_6k6.kicad_pcb`, libraries, DRC report | netlist export = design database; DRC via pcbnew (see 18) |
| `08_KiCad_PCB/` | layout description and stack-up pointers (the PCB file lives with the project in 07) | - |
| `09_Component_Libraries/` | pointer to `07_KiCad_Schematics/lib/` and the generators | pin-existence check |
| `10_Firmware/` | portable C control core, protocol, C2000 HAL (not compiled), SIL harness (`make test`) | 35 SIL checks pass (gcc) |
| `11_Control_Algorithms/` | loop design, modulation comparison, MPC alternative, `control_params.json` | script run |
| `12_Optimization/` | exhaustive design-space exploration, Pareto front, sensitivities | script run |
| `13_Thermal_Analysis/` | losses -> Tj, cooling options, derating | script run |
| `14_EMI_EMC/` | DM/CM estimate, filter, standards, pre-compliance plan | script run |
| `15_Safety_Reliability/` | insulation coordination (IEC 62477-1/60664-1 basis), protection coordination, FMEA | analysis |
| `16_BOM/` | BOM with ratings/derating, flags for unverified parts, off-board items | generated |
| `17_Manufacturing/` | stack-up, notes, `export_outputs.py` (gerbers, drill, pos, PDFs) | kicad-cli |
| `18_Verification/` | `run_verification.py` -> `verification_report.md` (what ran, what passed) | - |
| `19_Research_Report/` | `build_report.py` -> `report.md` (28 chapters, numbers pulled from result files) | generated |
| `20_Experimental_Test_Plan/` | staged laboratory plan, instruments, criteria, safety controls | procedure only |
| `dabtools/` | Python packages: `dab/` (models), `kicad_dab/` (design database, schematic/PCB/BOM generators) | - |

## Reproduce everything

```
cd SiC_6k6_Industrial_DAB
pip install numpy matplotlib            # KiCad 7 (kicad-cli + pcbnew python), ngspice, gcc required
python3 02_Topology_Comparison/topology_comparison.py
python3 04_Design_Calculations/dab_design.py
python3 06_Magnetics/transformer_design.py
python3 05_Simulation/run_switched_sim.py && python3 05_Simulation/gen_spice.py
python3 11_Control_Algorithms/control_design.py
python3 12_Optimization/optimize.py
python3 13_Thermal_Analysis/thermal_analysis.py && python3 14_EMI_EMC/emi_analysis.py
(cd 10_Firmware && python3 tools/gen_params.py && make test)
python3 dabtools/kicad_dab/gen_sch_dab.py        # schematic + libraries + netlist check
python3 dabtools/kicad_dab/gen_pcb_dab.py        # placement, planes, routing, zone fill, DRC (long)
python3 dabtools/kicad_dab/bom_dab.py
python3 17_Manufacturing/export_outputs.py
python3 18_Verification/run_verification.py
python3 19_Research_Report/build_report.py
```

## Completion matrix

See `18_Verification/verification_report.md` for the current tool results and
`00_Requirements/03_RTM.csv` for the per-requirement status. Summary of the states used:
*completed* (artefact exists and its generator ran), *generated but not verified* (C2000 HAL,
BoosterPack mapping, bias-module choice), *simulation-validated* (control, power stage),
*engineering-reviewed* (none yet - independent review required), *experimentally validated*
(none), *blocked* (push to GitHub pending repository access), *remaining work* (chapter 23 of
the report).
