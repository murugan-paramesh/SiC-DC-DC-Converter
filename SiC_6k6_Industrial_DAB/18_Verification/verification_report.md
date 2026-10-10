# 18 - Verification report

Run on 2026-10-10 07:48 in the software environment (KiCad 7.0.11 CLI/pcbnew, ngspice 42, gcc, Python). No hardware test was performed.

| Check | Status | Detail |
|---|---|---|
| script 02_Topology_Comparison/topology_comparison.py | PASS | exit 0 |
| script 04_Design_Calculations/dab_design.py | PASS | exit 0 |
| script 06_Magnetics/transformer_design.py | PASS | exit 0 |
| script 11_Control_Algorithms/control_design.py | PASS | exit 0 |
| script 13_Thermal_Analysis/thermal_analysis.py | PASS | exit 0 |
| script 14_EMI_EMC/emi_analysis.py | PASS | exit 0 |
| ngspice vs analytical (power, rms current) | PASS | dP = 0.5 %, dI_rms = 0.6 % |
| ngspice ZVS at all 8 edges (nominal) | PASS | {'A1_vds_at_turnon_pu': 0.002, 'A2_vds_at_turnon_pu': 0.002, 'B1_vds_at_turnon_pu': 0.005, 'B2_vds_at_turnon_pu': 0.004} |
| switched sim: regulation +/-1 % (EL-08) | PASS | v2 = 400.00 V |
| switched sim: 50 % load step < 3 % (EL-10) | PASS | dip = 0.37 % |
| switched sim: reversal without fault, links < 5 % (EL-11) | PASS | {'v1_max': 802.5875451238527, 'v1_min': 797.2372314551599, 'v2_max': 401.77912002938007, 'v2_min': 398.21212691468605, 'fault': None} |
| switched sim: dead-bus start under hardware current limit | PASS | {'v2_final': 400.01227815498817, 'ipk_max': 20.1921780048628, 'fault': None, 't_to_90pct_ms': 45.02000000077961} |
| calc efficiency objectives (EL-06/07, analytical only) | PASS | eta_nom = 98.62 %, peak = 98.66 % (not measured) |
| firmware control core SIL (gcc) | PASS | RESULT: ALL PASS (0 failures) |
| C2000 HAL host syntax check (not a target build) | PASS | gcc -fsyntax-only; TI toolchain not available |
| DAB schematic generation + kicad-cli netlist export + match | PASS | schematic: 261 symbols; netlist match: True |
| symbol/footprint pin mapping (every design pin exists in symbol and footprint) | PASS | 0 mismatches [] |
| component pinouts flagged for datasheet verification | INFO | AMC1301, BoosterPack J1/J3, BoosterPack J2/J4, BoosterPack PWM, ISO 5V/5V 1W SIP-7, R12P21503D, TCAN332 |
| ERC-lite: no single-pin nets except the documented reserved header pins | PASS | unexpected []; reserved (design_dab.RESERVED_SINGLE_PIN_NETS): ['GPIO_SYNC', 'I2C_SCL', 'I2C_SDA', 'I2_REF_OUT', 'RESET_N', 'SPI_CLK', 'SPI_CS', 'SPI_MISO', 'SPI_MOSI'] |
| DAB PCB: KiCad DRC errors | PASS | errors 0, unconnected 0, kinds {'silk_overlap': 11, 'silk_over_copper': 27, 'silk_edge_clearance': 16, 'track_dangling': 9} |
| DAB PCB: unrouted connections | PASS | 0 unconnected items, failed terminals 0 |
| PSFB PCB: KiCad DRC errors | PASS | errors 0, unconnected 0, kinds {'silk_overlap': 13, 'silk_over_copper': 18, 'silk_edge_clearance': 9} |
| PSFB PCB: unrouted connections | PASS | 0 unconnected items, failed terminals 0 |
| RTM status column refreshed | INFO | 30 requirements |

**0 failed checks, 22 passed, 2 informational.**
