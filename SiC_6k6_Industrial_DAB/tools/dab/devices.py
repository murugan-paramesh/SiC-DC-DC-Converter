"""
Semiconductor parameter sets.

VALUES ARE DATASHEET-TYPICAL FIGURES ENTERED FROM MEMORY OF THE PUBLISHED DATASHEETS AND
MUST BE RE-VERIFIED AGAINST THE CURRENT DATASHEET REVISION BEFORE ANY PROCUREMENT OR TEST
(flag: verified=False).  The loss model exposes its sensitivity to these numbers in
04_Design_Calculations so a corrected value can be substituted and the whole chain re-run.
"""

DEVICES = {
    "C3M0032120K": dict(
        manufacturer="Wolfspeed", package="TO-247-4 (Kelvin source)", Vds=1200.0, Id_25=63.0,
        Rds_25=0.032, Rds_150=0.052,            # Ohm, typ. (Rds(on) rises ~1.6x at 150 C for Gen3 SiC)
        Qg=87e-9, Qgs=24e-9, Qgd=29e-9,         # C at 15 V / -4 V
        Coss_800V=100e-12, Coss_er=170e-12, Coss_tr=320e-12, Qoss_800V=200e-9,
        Eon_800V_20A=270e-6, Eoff_800V_20A=55e-6,   # J, with datasheet test conditions (hard switching)
        Vgs_on=15.0, Vgs_off=-4.0, Vgs_th=2.5, Vsd=4.0,  # body-diode forward voltage at 20 A, Vgs = -4 V
        RthJC=0.45, Tj_max=175.0, verified=False,
        datasheet="https://www.wolfspeed.com/products/power/sic-mosfets/1200v-silicon-carbide-mosfets/c3m0032120k/"),
    "C3M0016120K": dict(
        manufacturer="Wolfspeed", package="TO-247-4 (Kelvin source)", Vds=1200.0, Id_25=115.0,
        Rds_25=0.016, Rds_150=0.027,
        Qg=180e-9, Qgs=48e-9, Qgd=62e-9,
        Coss_800V=200e-12, Coss_er=350e-12, Coss_tr=650e-12, Qoss_800V=420e-9,
        Eon_800V_40A=600e-6, Eoff_800V_40A=120e-6,
        Vgs_on=15.0, Vgs_off=-4.0, Vgs_th=2.5, Vsd=4.2,
        RthJC=0.30, Tj_max=175.0, verified=False,
        datasheet="https://www.wolfspeed.com/products/power/sic-mosfets/1200v-silicon-carbide-mosfets/c3m0016120k/"),
    "C3M0060065K": dict(   # PSFB baseline device, for the topology comparison
        manufacturer="Wolfspeed", package="TO-247-4", Vds=650.0, Id_25=37.0, Rds_25=0.060, Rds_150=0.090,
        Qg=36e-9, Coss_er=100e-12, Coss_tr=160e-12, Qoss_400V=60e-9, Eoff_400V_10A=15e-6,
        Vgs_on=15.0, Vgs_off=-3.0, Vsd=3.5, RthJC=0.75, Tj_max=175.0, verified=False, datasheet=""),
}


def rds_on(dev, Tj):
    """Linear interpolation of Rds(on) between 25 C and 150 C (extrapolated above)."""
    d = DEVICES[dev]
    return d["Rds_25"] + (d["Rds_150"] - d["Rds_25"]) * (Tj - 25.0) / 125.0
