# 08 - PCB

The board file is part of the KiCad project in `../07_KiCad_Schematics/SiC_DAB_6k6.kicad_pcb` (one
project directory so that KiCad's schematic<->PCB link works without re-importing). Layout description,
regions, planes and rules: `../dabtools/kicad_dab/gen_pcb_dab.py` (docstring) and
`../17_Manufacturing/stackup.md`; DRC results: `../07_KiCad_Schematics/drc_report.txt` and
`drc_summary.json`; routing is produced by `tools/kicad/router.py` (negotiated congestion) and
checked by KiCad's DRC with the net-class rules in `SiC_DAB_6k6.kicad_dru`.
