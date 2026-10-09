# 04 - Schematic description

Project: `hardware/kicad/SiC_PSFB_3kW.kicad_pro` (KiCad 7 format, opens in KiCad 7/8/9).
The schematic is hierarchical: a root sheet with three sub-sheets. It is generated from
`tools/kicad/design.py`, which is the single source of truth for every component and net
(the same database produces the PCB and the BOM, so the three can never disagree).

Pins are connected with global labels (and power symbols for PGND / SGND / VBUS / VOUT /
+12V / VREF); components are grouped by function with a title above each group.

## Sheet 2 - Power Stage (`power_stage.kicad_sch`)

1. **Input** - J1/J2 ring-lug terminals, F1 fuse, C1-C4 film DC-link capacitors, C5/C6 MLCCs.
2. **SiC full bridge** - Q1/Q2 form leg A (switch node SW_A, driven by OUTA/OUTB), Q3/Q4 form
   leg B (SW_B, OUTC/OUTD). Each has a separate Kelvin-source net KS_Qx used only by the gate
   drive loop; the power source pins go to VBUS/SW/PGND.
3. **Resonant path** - SW_A -> L1 (12 uH) -> LR_N. D1 (to VBUS) and D2 (to PGND) clamp LR_N.
   C7 || C8 block DC -> PRI_1 -> CT1 primary (one-turn flying lead) -> PRI_2 -> T1 P+.
   T1 P- returns to SW_B.
4. **Synchronous rectifier** - T1 S1 = SEC_A to Q5 || Q6 drains, S2 = SEC_B to Q7 || Q8, all
   sources on SGND; R1/C9 and R2/C10 damp the residual ringing. The centre tap SEC_CT feeds L2.
5. **Output filter** - L2 -> VOUT, C11-C16 electrolytic, C17-C22 MLCC, R3 shunt in the return
   between SGND and the OUT_N terminal J4, J3 = VOUT terminal, CY1/CY2 across the barrier,
   test points, mounting holes.

## Sheet 3 - Primary Gate Drive (`gate_drive.kicad_sch`)

* U2 drives Q1 (channel A) and Q2 (channel B); U3 drives Q3/Q4. Inputs come straight from the
  controller (OUTA-OUTD), VCCI = +12 V, DIS tied low, DT programmed by R20/R21.
* Each MOSFET has its own isolated bias module PSx (+15 V = VDD_Qx, COM = KS_Qx, -3 V = VEE_Qx)
  with 10 uF + 1 uF on each rail, and the gate network: 5.1 Ohm turn-on (R22/25/28/31),
  2.2 Ohm turn-off via an SS14 Schottky (R23/26/29/32 + D10-D13), 10 k gate bleed to the Kelvin
  source (R24/27/30/33). The driver output pins swing between VEE_Qx and VDD_Qx.

## Sheet 4 - Control and SR Drive (`control.kicad_sch`)

* **Bias input** J5 (+12 V), D3 TVS, C64/C65 bulk and HF capacitors.
* **UCC28951** U1 with VDD RC filter (R40/C52/C53), VREF capacitor, EA+ 2.5 V divider, output
  voltage divider (R43/R44/R45), type-II compensator (R46/C56/C57), soft-start C58, timing and
  delay resistors (R47-R58, see docs/03).
* **Current sense** D4/D5 (two BAV99 form a bridge rectifier) -> burden R59 -> RC filter -> CS.
* **SR drive** U4 (OUTE -> SR_A -> Q5/Q6 gates, OUTF -> SR_B -> Q7/Q8), gate resistors R61-R68.
* **Interfaces** J6 signal header (VREF, EN, TEMP, IMON-, IMON+, COMP, SYNC, GND), J7 NTC with
  R69 pull-up, D6/R70 VREF indicator, test points TP6-TP9.

## Net naming

| Prefix | Side | Class (PCB clearance) |
|---|---|---|
| VIN_RAW, VBUS, PGND, SW_A, SW_B, LR_N, PRI_1, PRI_2 | primary power | PRI_POWER: 1.0 mm to other PRI_POWER, 8 mm to secondary |
| G_Q1..4, GD_Q*, RGOFF_Q*, KS_Q*, VDD_Q*, VEE_Q* | primary gate drive | PRI_GATE: 0.3 mm, 0.5 mm to PRI_POWER, 5.5 mm + slot to secondary |
| VOUT, SEC_A, SEC_B, SEC_CT, OUT_N | secondary power | SEC_POWER: 0.5 mm |
| everything else | secondary signal | 0.2 mm |

## Regenerating

```
python3 tools/psfb_design.py          # calculations -> design/design_values.json
python3 -m tools.kicad.gen_schematic  # symbols, schematic sheets, project file
python3 -m tools.kicad.gen_pcb        # footprints, placement, routing, zone fill, DRC
python3 -m tools.kicad.bom
```
`tools/kicad/check_netlist.py` compares the netlist exported by `kicad-cli` with the design database.
