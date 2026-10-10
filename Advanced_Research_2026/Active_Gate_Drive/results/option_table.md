
**C3M0032120K** (800 V; hard-switched at 3.0 A, ZVS at 9.8 A nominal / 19.6 A worst corner)

| option | hard dv/dt on/off (V/ns) | hard E_on+E_off (uJ) | hard P per edge at 100 kHz (W) | hard V_os (V) | ZVS dv/dt nom/worst (V/ns) | ZVS E_off model (uJ) | crosstalk margin ZVS nom/worst (V) | crosstalk margin at hard turn-on (V) | self-limiting dv/dt (V/ns) | I_cm worst (A) |
|---|---|---|---|---|---|---|---|---|---|---|
| A fixed Rg 3.3/3.3 | 31.4/4.7 | 91.0 | 9.1 | 9.0 | 15.2/30.6 | 0.155 | 1.32/-1.62 | -1.74 | 20.9 | 3.06 |
| B two-level 3.3/1.5 (current design, -3 V) | 31.4/4.7 | 91.0 | 9.1 | 9.0 | 15.2/30.6 | 0.155 | 2.29/-0.07 | -0.18 | 29.1 | 3.06 |
| B' two-level 3.3/1.5, -4 V bias | 31.4/4.7 | 91.0 | 9.1 | 9.0 | 15.2/30.6 | 0.155 | 3.29/0.93 | 0.82 | 35.2 | 3.06 |
| C two-level + Miller clamp (-3 V) | 31.4/4.7 | 91.0 | 9.1 | 9.0 | 15.2/30.6 | 0.155 | 2.87/0.97 | 0.87 | 29.1 | 3.06 |
| D slow Rg 10/10 (EMI-oriented) | 19.4/4.7 | 110.0 | 11.0 | 9.0 | 15.2/30.6 | 0.155 | -1.73/-5.22 | -2.94 | 10.1 | 3.06 |
| E multi-level (1 Ohm pre-plateau / 10 Ohm plateau) concept | 19.4/4.7 | 110.0 | 11.0 | 9.0 | 15.2/- | no gain (capacitive) | -/- | - | - | - |

**C3M0016120K** (400 V; hard-switched at 6.0 A, ZVS at 19.5 A nominal / 39.2 A worst corner)

| option | hard dv/dt on/off (V/ns) | hard E_on+E_off (uJ) | hard P per edge at 100 kHz (W) | hard V_os (V) | ZVS dv/dt nom/worst (V/ns) | ZVS E_off model (uJ) | crosstalk margin ZVS nom/worst (V) | crosstalk margin at hard turn-on (V) | self-limiting dv/dt (V/ns) | I_cm worst (A) |
|---|---|---|---|---|---|---|---|---|---|---|
| A fixed Rg 3.3/3.3 | 11.5/4.6 | 75.9 | 7.59 | 14.4 | 15.0/30.1 | 0.305 | -1.97/-4.35 | -0.93 | 8.2 | 3.01 |
| B two-level 3.3/1.5 (current design, -3 V) | 11.5/4.6 | 75.9 | 7.59 | 14.4 | 15.0/30.1 | 0.305 | -0.4/-3.02 | 0.59 | 12.3 | 3.01 |
| B' two-level 3.3/1.5, -4 V bias | 11.5/4.6 | 75.9 | 7.59 | 14.4 | 15.0/30.1 | 0.305 | 0.6/-2.02 | 1.59 | 14.9 | 3.01 |
| C two-level + Miller clamp (-3 V) | 11.5/4.6 | 75.9 | 7.59 | 14.4 | 15.0/30.1 | 0.305 | 0.87/-1.72 | 1.71 | 12.3 | 3.01 |
| D slow Rg 10/10 (EMI-oriented) | 6.8/4.3 | 221.8 | 22.18 | 14.4 | 15.0/30.1 | 0.305 | -4.68/-6.21 | -2.04 | 3.6 | 3.01 |
| E multi-level (1 Ohm pre-plateau / 10 Ohm plateau) concept | 6.8/4.3 | 221.8 | 22.18 | 14.4 | 15.0/- | no gain (capacitive) | -/- | - | - | - |
