# Lifetime proxy comparison (daily damage, ratios relative to forced air; NOT years)

| variant | Tj HV max / mean (C) | Tj LV max / mean (C) | largest dTj cycle HV / LV (K) | cycles/day HV | mean loss (W) | hard-switched minutes | energy ratio | lifetime ratio LESIT HV / LV | lifetime ratio Bayerer HV / LV |
|---|---|---|---|---|---|---|---|---|---|
| natural | 94.5 / 53.0 | 64.0 / 45.8 | 67.0 / 35.4 | 14 | 24.3 | 581 | 1.000 | 0.01 / 0.10 | 0.06 / 0.23 |
| forced_air | 62.8 / 41.3 | 50.8 / 38.5 | 37.0 / 24.2 | 14 | 23.9 | 581 | 1.000 | 1.00 / 1.00 | 1.00 / 1.00 |
| liquid | 46.4 / 38.7 | 39.7 / 36.9 | 11.0 / 4.2 | 18 | 23.7 | 581 | 1.000 | 180.08 / 4478.87 | 130.70 / 5304.80 |
| slew_limited | 63.4 / 41.4 | 50.8 / 38.4 | 37.5 / 24.2 | 20 | 24.1 | 590 | 0.988 | 0.91 / 1.00 | 0.93 / 1.00 |
| fan_control | 62.9 / 45.6 | 56.7 / 42.8 | 35.4 / 28.9 | 16 | 24.1 | 581 | 1.000 | 0.91 / 0.39 | 1.06 / 0.68 |

Electro-thermal feedback: mean losses 23.9 W with Rds_on(Tj) vs 23.3 W at 25 C (+2.9 %).
Aging feedback (+5 % Rds_on, forced air): losses +1.6 %, daily damage proxy +0.6 % (LESIT, HV) / +0.4 % (Bayerer, HV) - self-acceleration is weak because Tj - Tcase is only a few kelvin in this design.
