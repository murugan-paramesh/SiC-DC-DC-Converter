# 01 - Requirements specification: 6.6 kW bidirectional SiC DAB for industrial HVDC

Document ID: DAB-REQ-001, rev A (2026-10). Status: engineering baseline, not customer-contractual.

Every requirement has an ID used in the requirements traceability matrix (`03_RTM.csv`).
"Objective" values are design targets; "achieved" values live only in `18_Verification/` once a
tool or measurement has produced them.

## 1. Application and service conditions (explicit assumptions)

| ID | Requirement | Value / assumption | Rationale |
|---|---|---|---|
| APP-01 | Application | Isolated bidirectional DC-DC interface between an industrial 650-850 V DC bus (DC microgrid / HVDC distribution) and a 300-450 V DC port (battery string, LVDC distribution, PV/ESS interface) | user brief section 3 |
| APP-02 | Installation | Fixed installation inside an industrial enclosure (IP20 module in an IP54 cabinet), restricted-access area, qualified personnel | IEC 62477-1 scope |
| APP-03 | Regulated port | Forward mode (HV -> LV): the LV port voltage is regulated (constant-voltage with current limit, CC/CV for battery charging). Reverse mode (LV -> HV): the HV port voltage or the HV port power is regulated as commanded by the supervisory controller. Mode and reference come from the supervisory system over CAN; the converter never changes power direction autonomously. | prevents conflicting regulators on a shared bus |
| APP-04 | External sources / loads | HV bus: stiff DC bus with source impedance < 0.5 Ohm and bus capacitance >= 500 uF (other converters). LV port: battery string (internal resistance 20-200 mOhm) or DC load with >= 1 mF capacitance. Both ports must tolerate 10 % voltage steps. | sets control bandwidth and transient envelope |
| APP-05 | Precharge | Both DC links are precharged by external contactor + resistor assemblies controlled by the converter (interface signals only on this board); the converter must not be enabled until both links are within 5 % of the external bus voltage | avoids inrush into the film capacitors |
| APP-06 | Ambient temperature | -10 C to +45 C full power; +45 C to +55 C with linear derating to 70 %; storage -40 C to +85 C | industrial cabinet |
| APP-07 | Altitude | <= 2000 m without derating; 2000-4000 m with clearance correction factor per IEC 60664-1 Table A.2 (1.29 at 4000 m) and 10 % power derating per 1000 m | insulation coordination |
| APP-08 | Cooling | Baseline: forced air, 3 m/s across two extruded heatsinks (one per bridge) and the magnetics; option B: cold plate at <= 45 C inlet. Selection in `13_Thermal_Analysis/` | user brief section 14 |
| APP-09 | Pollution degree / OVC | Pollution degree 2 (enclosure), overvoltage category II for the DC ports (DC distribution with surge-limited sources); if connected to a mains-derived DC bus without further limitation, OVC III applies and clearances must be re-evaluated | IEC 62477-1 clause 4.3 |
| APP-10 | Service life / reliability | 10 years, 24/7, > 100 000 h MTBF objective at 45 C; capacitor lifetime >= 60 000 h at hot-spot temperature | industrial expectation |

## 2. Electrical requirements

| ID | Requirement | Value | Verification method |
|---|---|---|---|
| EL-01 | Rated continuous power | 6.6 kW, both directions | calc + sim + test (staged) |
| EL-02 | HV port voltage range | 650-850 V, nominal 800 V | calc (envelope map) |
| EL-03 | LV port voltage range | 300-450 V, nominal 400 V | calc (envelope map) |
| EL-04 | Full-power envelope | Full power required for 0.86 <= (V2*n/V1) <= 1.16 (see EL-04a); outside, the derating map of `04_Design_Calculations/` applies (current-limited) | calc |
| EL-04a | Derating | Device rms current <= rated and ZVS (energy criterion) at both bridges above 25 % load for the full-power envelope | calc + sim |
| EL-05 | Switching frequency | 100 kHz nominal (optimisation range 60-150 kHz) | design |
| EL-06 | Peak efficiency objective | >= 97.5 % (calculated; measured only in lab) | calc + test |
| EL-07 | Full-load efficiency objective | >= 96.5 % at 800/400 V | calc + test |
| EL-08 | Steady-state regulation | +/- 1 % of the regulated port voltage | sim + test |
| EL-09 | Output voltage ripple | <= 1 % p-p at the regulated port | calc + sim |
| EL-10 | Load transient | 50 % step: deviation <= 3 %, recovery < 5 ms | sim + test |
| EL-11 | Power-flow reversal | 0 -> full reverse in < 20 ms without over-voltage (> 5 %) on either port | sim + test |
| EL-12 | Current limit | Inductor peak current limited cycle-by-cycle at 1.4 x rated peak; average port current limited by control | sim + test |
| EL-13 | DC-link voltage ripple at 100 kHz | <= 2 % p-p on both links | calc |
| EL-14 | Control | Digital, TI C2000 class (TMS320F280049C), 100 kHz PWM, 100 kHz ISR | design |
| EL-15 | Communication | CAN 2.0B (500 kbit/s) isolated, plus UART service port; status/fault/measurement telemetry at >= 10 Hz | design |
| EL-16 | Auxiliary supply | 24 V DC +/- 20 %, < 1 A, from the cabinet aux bus (secondary-referenced control ground) | design |

## 3. Isolation and safety (IEC 62477-1 / IEC 60664-1 basis)

| ID | Requirement | Value | Notes |
|---|---|---|---|
| SAF-01 | Isolation between HV port, LV port and control/aux circuits | Working voltage 850 V DC (HV), 450 V DC (LV). Insulation HV<->LV: basic (both are hazardous, both are isolated from earth by the system) **plus** reinforced isolation from both ports to the control/communication circuits (accessible / SELV). | the 3 kVrms brief figure is reviewed in `15_Safety_Reliability/01_insulation_coordination.md` |
| SAF-02 | Test voltages | HV<->LV: 2.5 kVrms 1 min (basic, 850 V working, OVC II) objective, verify in 15_...; ports<->control: 4 kVrms 1 min (reinforced) | derived from IEC 60664-1 impulse/AC withstand tables for the system voltage; final values after the insulation coordination study |
| SAF-03 | Creepage / clearance | HV<->LV >= 8.0 mm creepage (850 V working, PD2, material group IIIa, basic) and >= 5.5 mm clearance; ports<->control >= 11.5 mm creepage (reinforced); gate-driver and sensing isolators must carry a reinforced rating | IEC 60664-1 tables 2 and 4 |
| SAF-04 | DC-link discharge | Film capacitors discharged to < 60 V within 5 min by bleeder resistors (passive) and < 10 s by the external active discharge (interface signal) | IEC 62477-1 4.4.9 (figures to be confirmed) |
| SAF-05 | Protective earthing | Heatsinks and enclosure bonded to PE; PCB mounting holes bonded to the chassis | touch current |
| SAF-06 | Hardware protection | Independent of firmware: over-current (shunt/CT comparator), DC-link over-voltage (comparators) and gate-driver DESAT faults trip the PWM via the C2000 trip zone and a hardware latch | IEC 62477-1 single-fault requirement |
| SAF-07 | Firmware protection | Over-voltage, under-voltage, over-current, over-temperature, communication loss, precharge failure, driver fault -> safe state (all gates off), latched fault log | |
| SAF-08 | Energisation | No HV energisation of the prototype before an independent engineering review of this package and an approved laboratory procedure (`20_Experimental_Test_Plan/`) | user brief section 15 |

## 4. Mechanical / manufacturing

| ID | Requirement | Value |
|---|---|---|
| MEC-01 | Power density objective | >= 3 kW/L for the power stage (converter without enclosure) |
| MEC-02 | PCB | multilayer (6 layers evaluated), 2 oz outer / 2 oz inner, FR4 Tg >= 170 C, CTI >= 400 (material group II) |
| MEC-03 | Semiconductors | TO-247-4 on two heatsink bars or on a cold plate; Kelvin source used |
| MEC-04 | Connectors | M6 bus-bar studs for the HV and LV ports, pluggable control connectors, CAN D-sub or M12 |
| MEC-05 | Manufacturability | Standard PCB fab (min 0.2 mm track/space, 0.3 mm drill), reflow + selective wave |

## 5. Verification policy

A requirement is "verified" only when the referenced tool run (calculation script, simulation,
KiCad ERC/DRC, compiler, test) has actually completed and its output is stored under
`18_Verification/`. Items that need laboratory equipment are marked "not verifiable in this
environment".
