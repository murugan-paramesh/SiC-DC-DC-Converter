# 02 - Operating envelope definition

The converter has four independent operating variables: V1 (650-850 V), V2 (300-450 V), power
(-6.6 ... +6.6 kW) and ambient temperature (-10 ... +55 C). The analysis in
`04_Design_Calculations/dab_design.py` evaluates a 3-D grid (V1, V2, P) and, for every point,
checks:

1. Phase shift required <= pi/3 (SPS) - keeps the reactive current acceptable and leaves
   control margin to the pi/2 maximum.
2. Device rms current <= rating at the junction-temperature limit (Tj <= 150 C with the heatsink
   model of `13_Thermal_Analysis/`).
3. ZVS energy criterion satisfied at both bridges (otherwise the point is allowed only with
   derated power where hard-switching loss keeps Tj in range).
4. Transformer peak flux <= 0.25 T (3C95, 100 C) and inductor current <= 1.4 x rated peak.

The result is the **feasibility and derating map** (`04_Design_Calculations/img/derating_map.png`)
and the table of maximum power per (V1, V2) corner. The guaranteed full-power envelope is then
stated as a requirement (EL-04) rather than silently assumed.

Dynamic limits: dV/dt of either port <= 100 V/ms (external contactor events are faster but the
converter is disabled during them), 10 % voltage steps on either port with the converter
running, power-reference slew limited to 2 kW/ms by the control firmware.
