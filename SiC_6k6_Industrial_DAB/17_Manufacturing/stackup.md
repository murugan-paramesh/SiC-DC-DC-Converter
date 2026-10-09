# 17.1 - PCB stack-up and fabrication specification (DAB power board)

| # | Layer | Material | Thickness | Function |
|---|---|---|---|---|
| 1 | F.Cu | Cu 70 um (2 oz) | 0.070 | components, pours, gate/sense tracks |
| - | prepreg | FR4 2 x 2116, Tg >= 170 C | 0.20 | |
| 2 | In1.Cu | Cu 70 um | 0.070 | reference planes HV_N / GND / LV_N |
| - | core | FR4 | 0.50 | |
| 3 | In2.Cu | Cu 70 um | 0.070 | power planes HV_P / GND / LV_P |
| - | prepreg | FR4 | 0.50 | |
| 4 | In3.Cu | Cu 70 um | 0.070 | reference planes (duplicate of In1) |
| - | core | FR4 | 0.50 | |
| 5 | In4.Cu | Cu 70 um | 0.070 | power planes (duplicate of In2) |
| - | prepreg | FR4 | 0.20 | |
| 6 | B.Cu | Cu 70 um | 0.070 | switch-node strips, signals, fills |
| | total | | ~2.4 mm | |

Justification: six layers give two plane pairs per region (reference plane 0.2 mm under each outer
layer: low-inductance DC-link decoupling loops and return paths for the gate/sense tracks), with
2 oz copper on all layers so that the 450 V / 16.5 A LV link and the switch-node strips are
carried on planes rather than discrete bus bars. Four layers would force the LV_N/LV_P planes onto the
outer layers where the components sit; eight layers add cost without a routing need (the signal
density is low). Material: FR4 Tg 170 C, CTI >= 400 (material group II) for the creepage values of
15.1; dielectric 0.5 mm core between the HV_N and HV_P planes gives > 20 kV/mm margin at 850 V.

Fabrication rules used by the generated design: min track/space 0.2 mm (signals), min drill 0.3 mm,
via 0.8/0.4 mm (annular 0.2 mm), plated slots 1.6 mm (bias modules), M6 holes 6.5 mm, edge
clearance 0.5 mm, solder mask over all internal pours, ENIG finish (fine-pitch TSSOP on the
LaunchPad side is off-board), silkscreen white, HV warning legends.

Electrical test: 100 % netlist test; hipot of the bare board between the HV, LV and CTRL net groups is
not possible on the fab tester - done on the assembled board (20_Experimental_Test_Plan).
