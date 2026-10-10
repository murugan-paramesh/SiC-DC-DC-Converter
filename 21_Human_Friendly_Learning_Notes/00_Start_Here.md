# 00 Start here - how to use these notes

> These notes explain the whole repository - the 3 kW PSFB reference design, the 6.6 kW SiC dual
> active bridge (DAB) research platform and the 2026 advanced-research modules - from first
> principles to research level. They are written to be read in order, but every chapter stands alone.

## Who this is for

* **Beginners** (students, technicians, software people meeting power electronics for the first
  time): read the `Level 1 - Beginner` paragraphs and the basic viva questions of each chapter.
* **Engineers** (designing, reviewing or building a converter): read `Level 2 - Engineering`, the
  worked examples and the "How this chapter connects to the files" tables.
* **Researchers / graduate students**: read `Level 3 - Research`, the advanced viva questions and
  the 2026 modules (chapters 15-19), then `Advanced_Research_2026/`.

## Status tags used everywhere

| Tag | Meaning in this project |
|---|---|
| `[Implemented]` | code, schematic, layout or document exists in the repository at the path given |
| `[Simulated]` | a result produced by a simulation script in the repository (no hardware) |
| `[Verified]` | an automated check runs and passes (DRC, netlist check, SIL tests, unit tests) |
| `[Proposed]` | designed on paper, not implemented (e.g. the transition-time sensor, the HIL bench) |
| `[Not yet tested]` | implemented but without a passing check (e.g. the C2000 HAL, never compiled) |

**Nothing in this repository has been built, energised or measured.** Every efficiency, temperature
and EMI number is calculated or simulated. The maturity scale used by the research modules
(L0 concept ... L6 publication-ready with evidence) is explained in chapter 19; no deliverable is above
L3 (software-verified).

## Reading paths

| Goal | Chapters |
|---|---|
| Understand what a DAB is and why SiC | 01, 02, 03, 04 |
| Reproduce the design numbers | 05, 06, 07, 12 |
| Understand the control and firmware | 09, 16, 17 |
| Review the schematic and PCB | 10, 11, 14 |
| Prepare a viva / interview | every chapter's question lists, then 20 |
| Start research on the platform | 15-19, then `Advanced_Research_2026/00_Gap_Analysis_and_Plan.md` |

## Chapter map

| # | Chapter | Main project files |
|---|---|---|
| 01 | Electrical fundamentals | - |
| 02 | Power-electronics basics | `SiC_6k6_Industrial_DAB/02_Topology_Comparison/` |
| 03 | SiC devices | `dabtools/dab/devices.py`, `09_Component_Libraries/` |
| 04 | Topology and DAB operation | `03_Mathematical_Models/`, `dabtools/dab/dab_model.py` |
| 05 | Mathematical model | `03_Mathematical_Models/` |
| 06 | Design calculations | `04_Design_Calculations/` |
| 07 | Magnetics | `06_Magnetics/`, `Advanced_Research_2026/FEM_Magnetics/` |
| 08 | Simulation | `05_Simulation/`, `dabtools/dab/sim_switched.py` |
| 09 | Control and firmware | `11_Control_Algorithms/`, `10_Firmware/` |
| 10 | Schematics walkthrough | `07_KiCad_Schematics/`, `dabtools/kicad_dab/design_dab.py` |
| 11 | PCB layout | `08_KiCad_PCB/`, `tools/kicad/` |
| 12 | Thermal management | `13_Thermal_Analysis/`, `Advanced_Research_2026/Multiphysics_Models/` |
| 13 | EMI/EMC and filters | `14_EMI_EMC/` |
| 14 | Safety, insulation, FMEA | `15_Safety_Reliability/`, `Advanced_Research_2026/Reliability_Engineering/` |
| 15 | Optimisation and uncertainty | `12_Optimization/`, `Advanced_Research_2026/Robust_Optimization/`, `Uncertainty_Quantification/` |
| 16 | Digital twin and estimation | `Advanced_Research_2026/Digital_Twin/` |
| 17 | Advanced control: MPC, embedded AI, safe RL, PINN | `Advanced_Research_2026/Adaptive_MPC/`, `Embedded_AI/`, `Safe_RL_Research/`, `Physics_Informed_Models/` |
| 18 | Health monitoring, gate drive, reliability, cybersecurity | `Advanced_Research_2026/SiC_Health_Monitoring/`, `Active_Gate_Drive/`, `Reliability_Engineering/`, `Cybersecurity/` |
| 19 | Testing, HIL, manufacturing, benchmarks, research method | `20_Test_Plan/`, `17_Manufacturing/`, `Advanced_Research_2026/HIL_Validation/`, `Research_Benchmarks/`, `Verification_Evidence/` |
| 20 | Final learning guide | everything: summary, pitches, roadmap, master question list |

The combined textbook *Understanding the 6.6 kW SiC Dual Active Bridge Converter - From Electrical
Fundamentals to Advanced 2026 Power Electronics Research* is generated from these chapters by
`build_textbook.py` (Markdown, HTML and DOCX via pandoc; PDF via headless Chromium where available).

## How the notes stay synchronised with the files

Each chapter ends with a table of the files it describes and their status tag. `check_notes.py`
verifies that every path quoted in the notes exists in the repository and that every topic carries
the mandatory headings; run it before trusting a chapter.
