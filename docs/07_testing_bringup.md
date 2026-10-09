# 07 - Test and bring-up procedure

Safety: the primary side carries 420 V DC with 40 uF of film capacitance. Use an isolated
oscilloscope or differential probes, a current-limited DC source for the first tests, and a
dummy load with a crowbar. Never probe the primary with a grounded scope.

## 1. Assembly checks (no power)

1. Visual inspection, solder joints on the TO-247 / TO-220 pins, polarity of C11-C16, C64, D3, D6.
2. Resistance checks: VBUS-PGND > 1 MOhm, VOUT-SGND > 10 kOhm, each gate-to-Kelvin source 10 k.
3. Isolation: 4 kVrms (or 5.6 kVDC) 60 s between the shorted primary nets and the shorted
   secondary nets; leakage < 1 mA. Measure creepage at the bias-module slots.
4. Magnetics: Lm, leakage, Lr, Lo as in docs/06. Record on the travel sheet.

## 2. Bias and control (no bus voltage)

1. Apply 12 V to J5 (current limit 0.5 A). Expect: VREF = 5.0 V (LED D6 on), VDD_IC ~12 V,
   PS1-PS4 outputs +15 V / -3 V relative to each Kelvin source, UCC27524 VDD 12 V.
   Idle current < 250 mA.
2. With SS/EN high, verify OUTA-OUTD at 100 kHz (TP8, TP9), OUTA/OUTB complementary with the
   DELAB dead time, OUTC/OUTD phase shifted by the error-amplifier demand (COMP high -> maximum
   phase shift since there is no output voltage).
3. Verify the gate waveforms at each MOSFET gate relative to its Kelvin source: +15 V / -3 V,
   rise/fall ~20 ns, no ringing above +19 V / -8 V.
4. Verify the SR gates (G_Q5..G_Q8) toggle with OUTE/OUTF; with DCM forced (short DCM to VREF)
   they must stay low.

## 3. Low-voltage power stage check

1. Apply 50 V DC to the input (current limit 2 A), 12 V bias, 2 Ohm load.
   Expect ~6 V output (48 V x 50/400), symmetrical SW_A / SW_B (TP1, TP2) waveforms, no
   saturation (watch the CS signal at TP6 for a linear ramp).
2. Raise to 100 V, check the output follows and the current limit (CS 2 V) engages correctly when
   the load is increased.

## 4. Full-voltage, soft-start and loop

1. 400 V input through a soft-start resistor, light load (5 A). Confirm 48.0 V +/- 0.5 V, adjust
   R45 if necessary.
2. Inject a 50 % load step; the deviation should be < 300 mV with ~100 us settling. Measure the
   loop with a network analyser across a 10 Ohm injection resistor in series with R43:
   crossover 5 - 8 kHz, phase margin > 60 deg. Re-tune R46/C56/C57 if the output capacitors differ.
3. Check ZVS: the drain-source voltage of each SiC MOSFET must reach zero before the gate rises
   at 25 %, 50 % and 100 % load; adjust R47/R48 (DELAB/DELCD) and the ADEL divider so the
   dead time just covers the resonant transition (86 ns at the ZVS boundary, 10 ns at full load).
4. SR timing: with the DELEF/ADELEF settings the body diodes must conduct < 50 ns per edge
   (observe the SR drain voltage); increase R49 if the SRs turn off too late (shoot-through),
   decrease it if the body-diode conduction is long.
5. Clamp diodes: LR_N must be clamped at VBUS + 1.5 V and PGND - 1.5 V; the SR drain voltage must
   not exceed 160 V at 420 V input.

## 5. Thermal and efficiency

1. Full load 62.5 A, 400 V, 50 C ambient equivalent (reduced airflow), 30 min: case temperatures
   Q1-Q4 < 90 C, Q5-Q8 < 95 C, T1 < 100 C, L2 < 110 C.
2. Efficiency at 10 / 25 / 50 / 75 / 100 % load with a precision power analyser; the model in
   docs/02 predicts 97 % at full load and > 95 % down to 25 %.
3. EMI pre-scan on the input and output cables; add the common-mode choke on the input harness
   if required.

## 6. Protection

* Output short at full voltage: the cycle-by-cycle limit holds the primary current at 16.7 A,
  the output folds back; no device damage after 10 s.
* Bias loss: pull J5 to 0 V at full load; all gates go low through the 10 k bleed resistors.
* Over-temperature: the NTC on J7 is read by the host through J6 (no on-board shutdown).
