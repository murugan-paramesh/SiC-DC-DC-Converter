# 09 - Component libraries

Project-local libraries generated into `../07_KiCad_Schematics/lib/` (`SiC_DAB.kicad_sym`,
`SiC_DAB.pretty/`) by `../dabtools/kicad_dab/gen_sch_dab.py` from `tools/kicad/symbols.py`,
`tools/kicad/footprints.py` (shared with the PSFB) plus `../dabtools/kicad_dab/libs_dab.py`.
Every design pin is checked to exist in both the symbol and the footprint
(`18_Verification/run_verification.py`). Pinouts flagged `pin_verified=False` in
`design_dab.py` (AMC1301, R12P21503D, PS9/PS10 1 W isolated 5 V module (part TBD), TCAN332, BoosterPack headers) must be checked
against the datasheets before fabrication.
