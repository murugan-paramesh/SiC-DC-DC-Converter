"""
Loss models for the DAB power stage (per operating point).

Semiconductors (per device):
  P_cond  = I_rms_dev^2 * Rds(on)(Tj)                        channel conduction
  P_diode = Vsd * I_avg_dead * t_dead * 2 * fs                body-diode conduction during dead time
  P_off   = Eoff(V, I) * fs * k_zvs                           turn-off loss (ZVS turn-on => no Eon);
                                                              k_zvs accounts for the share of the
                                                              datasheet Eoff that is really dissipated
                                                              in the device under ZVS (Coss energy is
                                                              recycled); default 0.35 (assumption)
  P_hard  = (Eon + Eoff) * fs                                 if the edge is NOT ZVS (energy criterion)
  P_gate  = Qg * (Vgs_on - Vgs_off) * fs                      (dissipated in gate resistors/driver)
Capacitors:  P = I_rms^2 * ESR.
Magnetics:   see magnetics.py (Steinmetz core loss + Dowell AC resistance).
"""
import math
from .devices import DEVICES, rds_on


def eoff_scaled(dev, V, I):
    """Scale the datasheet turn-off energy linearly with current and voltage (first-order)."""
    d = DEVICES[dev]
    key = [k for k in d if k.startswith("Eoff_")][0]
    _, vs, is_ = key.split("_")
    Vref, Iref = float(vs[:-1]), float(is_[:-1])
    return d[key] * (V / Vref) * (I / Iref)


def eon_scaled(dev, V, I):
    d = DEVICES[dev]
    key = [k for k in d if k.startswith("Eon_")][0]
    _, vs, is_ = key.split("_")
    Vref, Iref = float(vs[:-1]), float(is_[:-1])
    return d[key] * (V / Vref) * (I / Iref)


def bridge_losses(dev, Vdc, I_rms_dev, I_sw_edges, fs, Tj, t_dead, I_min_zvs, n_parallel=1, k_zvs=0.35):
    """
    Losses of one full bridge (4 switch positions) at one operating point.
    I_sw_edges: list of currents (A, >0 favourable) at the switching edges of this bridge
                (two per half period for a full bridge); hard switching assumed if below I_min_zvs.
    Returns dict with per-bridge totals and the per-device junction temperature driver.
    """
    d = DEVICES[dev]
    R = rds_on(dev, Tj) / n_parallel
    P_cond = 4 * I_rms_dev ** 2 * R
    P_off, P_hard, P_diode = 0.0, 0.0, 0.0
    for i_sw in I_sw_edges:
        i_abs = abs(i_sw)
        # each edge switches one leg: one device turns off (Eoff) and the other turns on
        if i_sw >= I_min_zvs:
            P_off += eoff_scaled(dev, Vdc, i_abs) * fs * k_zvs
            P_diode += d["Vsd"] * i_abs * t_dead * fs * 0.5
        else:
            P_hard += (eon_scaled(dev, Vdc, max(i_abs, 1.0)) + eoff_scaled(dev, Vdc, max(i_abs, 1.0))) * fs
            # plus the full Coss energy of the leg dumped at turn-on
            P_hard += d["Coss_er"] * Vdc ** 2 * fs
    P_gate = 4 * n_parallel * d["Qg"] * (d["Vgs_on"] - d["Vgs_off"]) * fs
    total = P_cond + P_off + P_hard + P_diode
    return dict(P_cond=P_cond, P_off=P_off, P_hard=P_hard, P_diode=P_diode, P_gate=P_gate,
                P_total=total, P_per_device=total / 4)


def capacitor_loss(I_rms, ESR):
    return I_rms ** 2 * ESR
