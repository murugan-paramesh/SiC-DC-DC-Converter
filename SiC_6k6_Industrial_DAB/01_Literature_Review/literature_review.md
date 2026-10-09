# 01 - Literature review

Scope: isolated bidirectional DC-DC conversion for industrial high-voltage DC systems, with
emphasis on the dual active bridge (DAB), its modulation and control, SiC device application,
high-frequency magnetics and the applicable safety / EMC framework.

Citation policy: every entry below is a publication the author of this package is confident
exists with the stated authors, venue and year. Volume/page details have been given only where
recalled with confidence; **the list must be cross-checked against IEEE Xplore / the publisher
before it is used in a submitted thesis or paper**, and no DOI has been invented. Where a claim
in this package relies on a specific result, the reference number is given in the text.

## 1. Dual active bridge: origin and characterisation

[1] R. W. A. A. De Doncker, D. M. Divan and M. H. Kheraluwala, "A three-phase soft-switched
high-power-density DC/DC converter for high-power applications," IEEE Transactions on Industry
Applications, vol. 27, no. 1, pp. 63-73, Jan./Feb. 1991. - Introduces the (three-phase) DAB and the
phase-shift power-transfer principle.

[2] M. N. Kheraluwala, R. W. Gascoigne, D. M. Divan and E. D. Baumann, "Performance
characterization of a high-power dual active bridge DC-to-DC converter," IEEE Transactions on
Industry Applications, vol. 28, no. 6, pp. 1294-1301, Nov./Dec. 1992. - Single-phase DAB, SPS power
equation P = V1 V2' phi (pi - phi) / (2 pi^2 f L), ZVS boundaries versus voltage ratio d.

[3] S. Inoue and H. Akagi, "A bidirectional DC-DC converter for an energy storage system with
galvanic isolation," IEEE Transactions on Power Electronics, vol. 22, no. 6, pp. 2299-2306,
Nov. 2007. - DAB for energy storage, efficiency and dead-time considerations at 20 kHz.

[4] B. Zhao, Q. Song, W. Liu and Y. Sun, "Overview of dual-active-bridge isolated bidirectional
DC-DC converter for high-frequency-link power-conversion system," IEEE Transactions on Power
Electronics, vol. 29, no. 8, pp. 4091-4106, Aug. 2014. - Survey of DAB topologies, modulation
(SPS/EPS/DPS/TPS) and control; starting point for the modulation comparison in 03/11.

[5] N. Hou and Y. W. Li, "Overview and comparison of modulation and control strategies for a
nonresonant single-phase dual-active-bridge DC-DC converter," IEEE Transactions on Power
Electronics, vol. 35, no. 3, pp. 3148-3172, Mar. 2020. - Recent systematic comparison used to
position the control choices of this project.

## 2. Loss modelling and efficiency-optimal modulation

[6] F. Krismer and J. W. Kolar, "Accurate power loss model derivation of a high-current dual
active bridge converter for an automotive application," IEEE Transactions on Industrial
Electronics, vol. 57, no. 3, pp. 881-891, Mar. 2010. - Loss model structure (conduction, switching
with Coss energy, magnetics, capacitors) reproduced in `tools/dab/losses.py`.

[7] F. Krismer and J. W. Kolar, "Efficiency-optimized high-current dual active bridge converter
for automotive applications," IEEE Transactions on Industrial Electronics, vol. 59, no. 7,
pp. 2745-2760, Jul. 2012.

[8] F. Krismer and J. W. Kolar, "Closed form solution for minimum conduction loss modulation of
DAB converters," IEEE Transactions on Power Electronics, vol. 27, no. 1, pp. 174-188, Jan. 2012.
- Analytical TPS solution; the brute-force optimiser in `dab_model.tps_search` is validated
against the qualitative behaviour described here (reduced rms current at d != 1).

[9] F. Krismer, "Modeling and optimization of bidirectional dual active bridge DC-DC converter
topologies," Ph.D. dissertation, ETH Zurich, 2010. - Comprehensive reference for DAB design
optimisation including magnetics and thermal models.

[10] H. Bai and C. Mi, "Eliminate reactive power and increase system efficiency of isolated
bidirectional dual-active-bridge DC-DC converters using novel dual-phase-shift control," IEEE
Transactions on Power Electronics, vol. 23, no. 6, pp. 2905-2914, Nov. 2008. - DPS modulation.

[11] B. Zhao, Q. Song and W. Liu, "Power characterization of isolated bidirectional
dual-active-bridge DC-DC converter with dual-phase-shift control," IEEE Transactions on Power
Electronics, vol. 27, no. 9, pp. 4172-4176, Sep. 2012.

[12] G. G. Oggier, G. O. Garcia and A. R. Oliva, "Switching control strategy to minimize dual
active bridge converter losses," IEEE Transactions on Power Electronics, vol. 24, no. 7,
pp. 1826-1838, Jul. 2009. - Extends the soft-switching range with reduced-duty modulation.

[13] A. K. Jain and R. Ayyanar, "PWM control of dual active bridge: comprehensive analysis and
experimental verification," IEEE Transactions on Power Electronics, vol. 26, no. 4,
pp. 1215-1227, Apr. 2011.

[14] J. Everts, F. Krismer, J. Van den Keybus, J. Driesen and J. W. Kolar, "Optimal ZVS
modulation of single-phase single-stage bidirectional DAB AC-DC converters," IEEE Transactions
on Power Electronics, vol. 29, no. 8, pp. 3954-3970, Aug. 2014. - ZVS conditions including the
charge-based (Qoss) criterion that the energy criterion used here approximates conservatively.

## 3. Alternative topologies used in the comparison

[15] R. Redl, N. O. Sokal and L. Balogh, "A novel soft-switching full-bridge DC/DC converter:
analysis, design considerations, and experimental results at 1.5 kW, 100 kHz," IEEE Transactions
on Power Electronics, vol. 6, no. 3, pp. 408-418, Jul. 1991. - PSFB with primary clamp diodes
(the baseline PSFB in `Legacy_PSFB_Baseline/` uses this clamp).

[16] J. A. Sabate, V. Vlatkovic, R. B. Ridley, F. C. Lee and B. H. Cho, "Design considerations
for high-voltage high-power full-bridge zero-voltage-switched PWM converter," in Proc. IEEE
APEC, 1990, pp. 275-284.

[17] B. Yang, F. C. Lee, A. J. Zhang and G. Huang, "LLC resonant converter for front end DC/DC
conversion," in Proc. IEEE APEC, 2002. - LLC gain characteristic used for the CLLLC comparison.

[18] J.-H. Jung, H.-S. Kim, M.-H. Ryu and J.-W. Baek, "Design methodology of bidirectional CLLC
resonant converter for high-frequency isolation of DC distribution systems," IEEE Transactions
on Power Electronics, vol. 28, no. 4, pp. 1741-1755, Apr. 2013. - Bidirectional resonant
alternative; its narrow gain range is the main argument against it for 650-850 / 300-450 V.

[19] G. Ortiz, J. Biela, D. Bortis and J. W. Kolar, "1 Megawatt, 20 kHz, isolated, bidirectional
12 kV to 1.2 kV DC-DC converter for renewable energy applications," in Proc. IPEC (ECCE Asia),
2010. - DAB in high-voltage DC renewable interfaces.

## 4. SiC devices and gate drive

[20] J. Millan, P. Godignon, X. Perpina, A. Perez-Tomas and J. Rebollo, "A survey of wide bandgap
power semiconductor devices," IEEE Transactions on Power Electronics, vol. 29, no. 5,
pp. 2155-2163, May 2014.

[21] Wolfspeed, "C3M0032120K Silicon Carbide Power MOSFET, C3M MOSFET technology, N-channel
enhancement mode," datasheet (current revision to be downloaded and archived in 16_BOM/datasheets).

[22] Wolfspeed, "C3M0016120K Silicon Carbide Power MOSFET," datasheet (idem).

[23] Texas Instruments, "UCC21710 10-A source/sink reinforced isolated single channel gate driver
for SiC/IGBT with active protection, isolated analog sensing and high-CMTI," datasheet
SLUSD39 (revision to be verified).

[24] Texas Instruments, "TMS320F28004x Real-Time Microcontrollers," datasheet SPRS945, and
"TMS320F28004x Technical Reference Manual," SPRUI33.

## 5. High-frequency magnetics

[25] P. L. Dowell, "Effects of eddy currents in transformer windings," Proceedings of the IEE,
vol. 113, no. 8, pp. 1387-1394, Aug. 1966. - AC resistance model in `tools/dab/magnetics.py`.

[26] K. Venkatachalam, C. R. Sullivan, T. Abdallah and H. Tacca, "Accurate prediction of ferrite
core loss with nonsinusoidal waveforms using only Steinmetz parameters," in Proc. IEEE COMPEL,
2002, pp. 36-41. - iGSE, used to correct the Steinmetz loss for the DAB flux waveform.

[27] W. G. Hurley and W. H. Woelfle, Transformers and Inductors for Power Electronics: Theory,
Design and Applications. Chichester, U.K.: Wiley, 2013. - Area-product sizing, leakage estimation.

[28] R. W. Erickson and D. Maksimovic, Fundamentals of Power Electronics, 2nd ed. Norwell, MA:
Kluwer, 2001 (3rd ed., Springer, 2020). - Averaged modelling, magnetics design procedures.

[29] C. R. Sullivan, "Optimal choice for number of strands in a litz-wire transformer winding,"
IEEE Transactions on Power Electronics, vol. 14, no. 2, pp. 283-291, Mar. 1999.

## 6. Control

[30] L. Chen, S. Shao, Q. Xiao, L. Tarisciotti, P. W. Wheeler and T. Dragicevic, "Model predictive
control for dual-active-bridge converters supplying pulsed power loads in naval DC micro-grids,"
IEEE Transactions on Power Electronics, vol. 35, no. 2, pp. 1957-1966, Feb. 2020. - MPC for DAB,
the research alternative evaluated in `11_Control_Algorithms/`.

[31] S. Buso and P. Mattavelli, Digital Control in Power Electronics, 2nd ed. Morgan & Claypool,
2015. - Sampling/PWM delay modelling, discrete PI design, anti-windup.

## 7. Standards (normative references, not reproduced)

[32] IEC 62477-1:2012 + A1:2016, Safety requirements for power electronic converter systems and
equipment - Part 1: General.

[33] IEC 60664-1:2020, Insulation coordination for equipment within low-voltage supply systems -
Part 1: Principles, requirements and tests.

[34] IEC 61800-3:2017, Adjustable speed electrical power drive systems - Part 3: EMC requirements
and specific test methods (used by analogy for industrial power converters installed in cabinets).

[35] CISPR 11:2015 / EN 55011, Industrial, scientific and medical equipment - Radio-frequency
disturbance characteristics - Limits and methods of measurement.

[36] IEC 61000-6-2 and IEC 61000-6-4, Generic standards - Immunity / emission for industrial
environments.

[37] IPC-2221B, Generic Standard on Printed Board Design (conductor spacing, current capacity).

[38] IPC-2152, Standard for Determining Current Carrying Capacity in Printed Board Design.

## 8. Research gap addressed by this package (honest statement)

The DAB, its modulations and SiC implementation are mature research subjects ([1]-[14]). This
package does **not** claim a new topology or a new modulation. Its contribution is an openly
reproducible, tool-verified engineering chain (analytical model -> loss/thermal model ->
multi-objective optimisation -> switching-level simulation -> firmware software-in-the-loop ->
generated KiCad schematic and routed PCB with safety-rule DRC) for an industrial 6.6 kW,
800 V / 400 V design point, with every assumption exposed in scripts. Any novelty claim would
require experimental validation that is outside the present (software-only) environment.
