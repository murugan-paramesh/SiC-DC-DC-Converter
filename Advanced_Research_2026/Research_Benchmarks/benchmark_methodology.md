# Benchmark methodology - how a fair *measured* comparison would be done

Status: proposal (L0/L1). Nothing in this document has been executed; the project has no hardware
(see `README.md`). It defines the procedure that would make the numbers in `results/benchmark_table.*`
comparable with published measurements.

## 1. Why the present table is not a fair comparison

| Aspect | This project (DAB 6.6 kW, PSFB 3 kW) | Published work in the database |
|---|---|---|
| Origin of efficiency | loss model (`04_Design_Calculations`, `docs/02`), device data entered from memory of datasheets (`verified=False`) | measured on a prototype (L01, L23), or vendor test report (L07) |
| Load/voltage point | 800/400 V, 80 % load (peak), full load, and the 9 envelope corners | not stated for L01/L23; L07 at the vendor's conditions |
| Auxiliary power | 12 W fans/bias included in the DAB budget | usually excluded (gate-drive and control supplied externally) |
| Cooling | forced air 3 m/s (DAB), 2 m/s (PSFB) at 45-50 C ambient | not captured in the database |
| Voltage range | 650-850 V / 300-450 V bidirectional (DAB) | L07 CLLC is a 400 V-class EV charger stage at 500 kHz; L01 is a low-voltage 1 kW prototype |
| Topology | phase-shift DAB at 100 kHz | L07 is a resonant CLLC at 500 kHz (different loss mechanisms and magnetics) |
| Power density | boxed estimate (PCB outline x assumed height), no enclosure, no fans | not recorded for any confirmed entry |

A calculated efficiency is an upper bound on what a first prototype will reach (unmodelled PCB and
termination losses, gate-loop losses, core-loss derating with temperature and DC bias, tolerances);
2 oz copper and bus-bar loss is already the largest single uncertainty in the DAB budget (26 W
estimate, see `design_values.json`).

## 2. Test conditions for a measured comparison

1. **Operating points.** Efficiency at 10 / 20 / 30 / 50 / 75 / 100 % of rated power (the CEC
   weighting set) in both directions, at three voltage pairs: nominal (800/400 V), low HV / high LV
   (650/450 V) and high HV / low LV (850/300 V). Report the full matrix, not only the best point.
2. **Weighted efficiency.** Report the IEC 61683-style weighted efficiency (the standard defines the
   measurement of inverter efficiency at defined load fractions; the CEC weighting
   0.04/0.05/0.12/0.21/0.53/0.05 at 10/20/30/50/75/100 % and the EU weighting
   0.03/0.06/0.13/0.10/0.48/0.20 at 5/10/20/30/50/100 % are the usual published aggregates), in
   addition to peak and full-load values. Both weighted values must be computed from the same
   measured points; the load fractions and the weights used must be printed next to the result.
3. **Thermal steady state.** Each point is held until all monitored temperatures change by less than
   1 K over 10 min (heatsink NTCs, transformer hot spot, inductor, ambient); the ambient is logged
   and the fan speed / air velocity fixed and stated.
4. **Auxiliary power.** Measured separately (bias supply current x voltage) and reported both
   included and excluded, so that papers that exclude it can be compared.
5. **Bidirectional points.** Reverse-power points use the same instruments swapped in role; the
   direction convention is stated.
6. **Warm-up and repetition.** Three repetitions of the full matrix on different days; report the
   mean and the spread.

## 3. Instruments

* Power analyser with >= 4 channels (two voltage, two current), bandwidth >= 1 MHz for the
  switched-current channels, basic accuracy <= 0.05 % of reading + 0.05 % of range in the DC/
  low-frequency band (class of a Yokogawa WT5000 / ZES LMG671 - any equivalent instrument is
  acceptable; the model and calibration date are reported).
* Current: precision shunts or zero-flux (fluxgate) transducers on the DC ports (the DC-side
  currents carry 200 kHz ripple; the shunt bandwidth and phase correction must be stated).
  Hall-effect clamps are not acceptable for sub-0.5 % efficiency-difference claims.
* Voltage: direct sense at the converter terminals (four-wire), not at the source/load, so cable
  losses are excluded.
* Source/load: bidirectional DC supply and regenerative load (or two converters back-to-back with
  the loss measured as the difference, which halves the required accuracy but attributes the loss to
  both units).
* Thermal: thermocouples/NTCs at the semiconductor cases, transformer outer layer and inductor, IR
  camera for hot-spot search, anemometer for the air velocity across the heatsinks.
* Waveforms: oscilloscope >= 200 MHz with differential HV probes (checked for common-mode
  rejection at 100 kHz / 20 V/ns) and a current probe on the inductor for ZVS-edge verification.

## 4. Uncertainty

For efficiency eta = Pout/Pin with Pin and Pout measured independently, the relative uncertainty
is u(eta)/eta = sqrt( (u(Pin)/Pin)^2 + (u(Pout)/Pout)^2 ). With a 0.1 % power uncertainty per
channel (instrument + transducer, after calibration), u(eta) = 0.14 % absolute at eta ~ 98 %, i.e.
loss uncertainty of about 9 W at 6.6 kW - comparable to the 2 oz copper-loss estimate in the model.
Consequences:

* efficiency differences below ~0.3 % between two converters measured on different setups are not
  significant and must not be presented as a ranking;
* the loss-difference method (back-to-back, Pin - Pout measured with the same transducer) reduces
  the loss uncertainty to the transducer linearity term and is preferred for 98 %-class converters;
* report k = 2 expanded uncertainty with each efficiency value and show it as error bars in the
  comparison figure.

## 5. Power density

Report the volume of the power stage as a boxed envelope (length x width x height over components,
heatsinks included, fans and enclosure stated separately) and the cooling condition. Published
figures that do not state what the volume includes are not comparable and are listed as such.

## 6. What the project would report

* The full efficiency matrix (3 voltage pairs x 6 loads x 2 directions) with uncertainty, auxiliary
  power excluded and included, CEC- and EU-weighted values.
* ZVS verification at each point (drain-voltage waveform at every edge of both bridges).
* The measured-vs-calculated residual per loss element where separable (calorimetric or
  thermal-image attribution), closing the loop to `04_Design_Calculations`.
