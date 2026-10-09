# 15.1 - Insulation coordination and electrical safety (IEC 62477-1 / IEC 60664-1 basis)

Status: engineering analysis for an independent safety review; the numerical table values quoted
from IEC 60664-1 are recalled from the standard's tables (F.1, F.2, F.4, F.5) and **must be
re-checked against the current edition before release**. Nothing here is a certification.

## 1. Circuits and working voltages

| Circuit | Working voltage | Reference | Accessible? |
|---|---|---|---|
| HV port and HV bridge (V1) | 850 V DC max (system nominal 800 V) | floating DC bus, earthed enclosure | no (enclosure, tool access) |
| LV port and LV bridge (V2) | 450 V DC max | floating | no |
| Gate-drive secondary sides (8) | at the respective switch-node potential (0-850 V / 0-450 V) | - | no |
| Control / DSP / CAN / 24 V aux (SELV-class) | 24 V | earthed control ground (one point) | yes (connectors, service port) |
| Heatsinks, core, chassis | PE | protective earth | yes |

Decisive voltages (IEC 62477-1 4.4.7): DVC C for both power circuits (> 120 V DC); the control
circuit must be DVC A (SELV / PELV): **reinforced (or double) insulation between either power
circuit and the control circuit**; **basic insulation between HV and LV power circuits** (both
DVC C, both inaccessible; the system must provide protection on each) and **basic insulation to
PE** for each power circuit.

## 2. Overvoltage category, pollution degree, altitude

* Pollution degree 2 (cabinet, no conductive pollution) - PD2.
* OVC II assumed for the DC ports (sources are converters with surge limitation). If the HV DC bus
  is derived from a mains rectifier without limitation, OVC III applies and the impulse level steps
  up (6 kV -> 8 kV for the 1000 V system class); clearances below would then need recalculation.
* Altitude <= 2000 m (APP-07); correction factor 1.29 on clearances for 4000 m.
* Material group: FR4 with CTI >= 400 -> group II (if only CTI >= 175 is guaranteed: IIIa, larger creepage).

## 3. Required distances (recalled table values, to verify)

Rated impulse withstand for a system voltage of 1000 V (the next step above 850 V DC): OVC II 4 kV,
OVC III 6 kV. Clearance for 4 kV impulse (inhomogeneous field, PD2): 3.0 mm; for 6 kV: 5.5 mm.
Reinforced insulation uses the clearance of the next higher impulse level (6 kV -> 5.5 mm) and twice
the creepage of basic insulation.

| Pair | Insulation | Impulse | Clearance (mm) | Creepage PD2, group II / IIIa (mm) | Design value used |
|---|---|---|---|---|---|
| HV (850 V) - PE / chassis | basic | 4 kV | 3.0 | 850 V: 6.0 / 8.5 | 8.5 (slot/edge), 3.5 min clearance |
| HV - LV (850 V working) | basic | 4 kV | 3.0 | 6.0 / 8.5 | **9.0** (PCB barrier, rule area), 9.0 clearance |
| LV (450 V) - PE | basic | 2.5 kV | 1.5 | 450 V: 3.2 / 4.5 | 5.0 |
| HV - control | reinforced | 6 kV | 5.5 | 2 x (6.0 / 8.5) = 12 / 17 | **16.0** barrier on the PCB; at isolator footprints: component rating (see 4) |
| LV - control | reinforced | 4 kV (next step) | 3.0 | 2 x (3.2 / 4.5) = 6.4 / 9 | 10.0; isolator footprints per 4 |
| Gate-drive secondary - control (per driver) | reinforced | as HV-control / LV-control | | | isolator + bias-module rating; PCB slot under the bias modules |
| Within HV circuit (SW node - rail, functional) | functional | - | 1.0 mm (IPC-2221 external coated, 850 V: B4 0.6 mm) | - | 1.0 mm track/pour, TO-247 pin pitch 2.54 mm (0.64 mm pad gap with coating) |

## 4. Isolating components across the barriers

| Component | Function | Isolation rating (datasheet, to verify) | Note |
|---|---|---|---|
| UCC21710 (x8) | gate driver | 5.7 kVrms reinforced (VDE 0884-11, UL 1577), 8 mm creepage package | the PCB creepage between pin rows (~8.5 mm) relies on the certified component; a 1.6 mm slot is routed under each driver to raise the PCB creepage to > 12 mm |
| Isolated gate bias modules (x8, 2 W, +15/-4 V) | driver supply | 5.2 kVDC/1 min class (RECOM R12P2 / Murata MGJ2) - **basic-class component**; two in series are not used, so the bias module isolation must be upgraded to a reinforced-rated part (e.g. Murata MGJ3 reinforced series) or a transformer-based bias with reinforced construction | **open item for the safety review** |
| AMC1311 (x2) | DC-link voltage sense | 7 kVpk reinforced (DWV package, 8.5 mm creepage) | |
| CT (series-inductor current) | current sense | one-turn TIW primary through a toroid, 8 mm spacing | |
| CAN isolator ISO1042 | fieldbus | 5 kVrms reinforced | |
| Transformer | HV-LV power | basic 850 V: 3 x 50 um polyimide, margins 6 mm, 2.5 kVrms test | core on PE: basic to both windings |

## 5. Test voltages (routine / type)

* HV - LV (basic, 850 V working, 4 kV impulse): AC withstand 2.5 kVrms 60 s (type), 1 s routine; or 3.5 kV DC.
* HV - control (reinforced): 4.0 kVrms 60 s (type) - the certified isolators are rated 5.7 kVrms.
* LV - control (reinforced): 3.0 kVrms 60 s.
* Each power circuit - PE: 2.5 kVrms (HV), 1.5 kVrms (LV).
* Partial discharge: PD extinction > 1.1 x working peak voltage for the reinforced barriers (62477-1 type test).

The 3 kVrms figure of the brief is therefore **not sufficient as the single isolation value**: the
HV-to-control reinforced barrier needs 4 kVrms-class testing, while HV-LV basic insulation needs 2.5 kVrms.

## 6. Protective functions (coordination)

| Hazard | First line (hardware, < 1 us) | Second line (firmware, 10 us) | Third line (system) |
|---|---|---|---|
| Shoot-through / short circuit | UCC21710 DESAT (< 1 us, soft turn-off) -> FLT wired-OR -> EPWM TZ2 | FLT_DRIVER latch | fuse in HV port (semiconductor fuse 16 A, I2t coordinated with the device) |
| Inductor over-current | CMPSS on CT signal -> TZ1 cycle-by-cycle at 32 A (HV) | FLT_I_PK | - |
| DC-link over-voltage | comparator 920 V / 490 V -> TZ3 | FLT_V1_OV at 900 V / FLT_V2_OV 480 V | external chopper / contactor |
| Loss of gate bias | driver UVLO (12 V) -> FLT | FLT_DRIVER | - |
| Over-temperature | - | NTC 95 C sink -> FLT_OT, derating from 55 C ambient | fan monitoring by host |
| Loss of control / comm | watchdog (DSP) -> gates off | FLT_COMM after 500 ms | contactor open by supervisory |
| Residual energy | bleeder resistors: < 60 V in 5 min (SAF-04) | - | active discharge command (interface) |
| Precharge failure | - | 5 s timeout -> FLT_PRECHARGE | contactor interlock |

## 7. Energisation policy

No high-voltage energisation of a prototype until (a) this analysis and the PCB have been reviewed
by an independent qualified engineer, (b) the magnetics have passed their hipot tests, (c) the
laboratory procedure of 20_Experimental_Test_Plan has been approved, with isolated instrumentation,
interlocked HV supply and an emergency-stop that opens both port contactors and discharges the links.
