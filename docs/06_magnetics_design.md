# 06 - Magnetics design

All numbers come from `tools/psfb_design.py` (docs/02). Build the three custom magnetics as
described here, then measure and record Lm, Lleak, Lr and Lo before the first power-up.

## T1 - main transformer

| Item | Specification |
|---|---|
| Core | ETD59/31/22, Ferroxcube 3C95 (or TDK PC95), ungapped, Ae = 368 mm2 |
| Bobbin | vertical 20-pin ETD59 bobbin; the PCB footprint has 2 rows x 8 pins at 5.08 mm pitch, 44 mm apart - adapt `Transformer_ETD59_PSFB` in `tools/kicad/footprints.py` to the chosen bobbin |
| Primary | 18 turns, litz 600 x 0.1 mm (4.7 mm2), split in two 9-turn layers (P/2 - S - P/2 interleaving) |
| Secondary | 2 x 3 turns copper foil 0.15 x 38 mm, two foils in parallel per half, centre tap brought out |
| Insulation | 3 layers of 50 um polyimide or polyester tape between every primary and secondary layer (reinforced), 4 mm margin tape at the winding ends, triple-insulated leads on the primary exit |
| Lm | ~1 mH (Al ~3100 nH/T2 for ungapped 3C95 ETD59; accept 0.7 - 1.3 mH) |
| Leakage (pri, sec shorted) | < 1.5 uH (interleaved); it adds to Lr |
| Flux density | 128 mT peak at 400 V, 150 mT worst case |
| Losses | 3.3 W core + 1.2 W primary + 4.7 W secondary |
| Test | 4 kVrms 60 s primary-secondary and primary-core |

Winding order (from the bobbin outwards): P1 (9 T) - tape - S1 foil (3 T, two foils) + S2 foil
(3 T, two foils) wound bifilar with the centre tap joined - tape - P2 (9 T). Pins: primary
start/finish each on two paralleled pins (pads 1 and 2), S1 on three pins (pad 3), centre tap on
two pins (pad 4), S2 on three pins (pad 5).

## L1 - resonant (shim) inductor

| Item | Specification |
|---|---|
| Core | ETD39/20/13, 3C95, Ae = 125 mm2, centre-leg gap 1.3 mm (adjust for 12 uH) |
| Winding | 10 turns litz 600 x 0.1 mm, single layer, keep the winding 2 mm away from the gap (fringing) |
| Peak flux | 118 mT at 12.3 A |
| Loss | ~1 W |
| Target | 12 uH +/- 10 % measured at 100 kHz with the transformer leakage in series |

## L2 - output inductor

| Item | Specification |
|---|---|
| Core | 2 x Magnetics 77439-A7 (Kool Mu 60u, OD 47 mm) stacked and taped; High Flux 58439 gives 20 % more inductance at full load |
| Winding | 5 turns of 2 x 6 mm flat copper (or 2 x AWG 8 in parallel), leads 1 mm thick fitting the 3.2 mm plated holes |
| Inductance | 6.8 uH at zero bias, 4.7 uH at 70 A |
| Ripple current | 14 A p-p (23 %) at full load |
| Loss | 4.7 W copper + ~1.5 W core |

## CT1 - current transformer

| Item | Specification |
|---|---|
| Core | ferrite toroid ~ 13 x 7 x 6 mm (Magnetics ZW42908TC or similar) |
| Secondary | 100 turns AWG 32 enamelled wire, terminated on the two secondary pads |
| Primary | one turn of the PRI_1 -> PRI_2 lead, triple-insulated wire rated 4 kV, passing through the toroid |
| Burden | 12 Ohm (R59) -> 1.48 V at full load, 2 V at the 16.7 A protection threshold |
| Magnetising current | < 1 % of the reflected current at 100 kHz with 1 mH secondary inductance |

Mount the toroid with its centre over the isolation barrier (footprint `CT_Toroid_Straddle`)
and keep the primary lead 8 mm from any secondary copper.
