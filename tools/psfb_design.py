#!/usr/bin/env python3
"""
SiC ZVS Phase-Shifted Full-Bridge (PSFB) isolated DC-DC converter
Design calculation engine.

Running this script:
  * prints the full design calculation trail
  * writes docs/02_design_calculations.md
  * writes docs/img/*.png design charts
  * writes design/design_values.json consumed by the KiCad generator (tools/kicad)

All formulas are standard PSFB design equations (see TI SLUA560, Wolfspeed
application notes and Erickson/Maksimovic). Values marked "datasheet typ."
must be re-checked against the exact datasheet revision when ordering.
"""
import json, math, os, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
IMG = os.path.join(DOCS, "img")
os.makedirs(IMG, exist_ok=True)

# --------------------------------------------------------------------------
# 1. Specification
# --------------------------------------------------------------------------
spec = dict(
    Vin_nom=400.0, Vin_min=370.0, Vin_max=420.0, Vin_derate=320.0,
    Vout=48.0, Iout=62.5, Pout=3000.0,
    fsw=100e3,                 # per-switch frequency (transformer frequency)
    eff_target=0.96,
    ripple_pct=0.20,           # output inductor current ripple (p-p / Iout)
    Vout_ripple=0.10,          # V p-p at 2*fsw
    Tamb=50.0, Tj_max=125.0,
    iso_test_V=4000.0,         # Vrms, 1 min, primary-secondary (reinforced)
    creepage_mm=8.0,
)
T = 1.0 / spec["fsw"]

# --------------------------------------------------------------------------
# 2. Semiconductor data (datasheet typical values - verify on ordering)
# --------------------------------------------------------------------------
sic = dict(
    part="C3M0060065K", package="TO-247-4 (Kelvin source)",
    Vds=650.0, Rds_25=0.060, Rds_tj=0.090,  # ohm at 25C / ~125C
    Qg=36e-9, Qgd=12e-9, Coss_er=100e-12, Coss_tr=160e-12,
    Eoff_400V_10A=15e-6,     # J, turn-off energy (ZVS turn-on => Eon ~ 0)
    Vgs_on=15.0, Vgs_off=-3.0,
    RthJC=0.75,
)
sr = dict(
    part="IPP110N20N3 G", package="TO-220", Vds=200.0,
    Rds_25=0.0107, Rds_tj=0.017, Qg=100e-9, Qrr=150e-9, Coss=600e-12,
    Vgs_on=12.0, RthJC=0.6, n_parallel=2,
)
clamp = dict(part="C3D04065A", Vrrm=650.0, Vf=1.6, If_avg=4.0)

# --------------------------------------------------------------------------
# 3. Turns ratio and duty cycle
# --------------------------------------------------------------------------
Lr = 12e-6                     # external resonant (shim) inductor + leakage
Vo = spec["Vout"]; Io = spec["Iout"]
n = 6.0                        # Np/Ns (center-tapped secondary 18:3:3)
Np, Ns = 18, 3

def duty(Vin, Lr=Lr, n=n, Io=Io):
    """Effective duty D_eff (0..1) and total controller duty D with duty loss."""
    Vs = Vin / n
    Deff = Vo / Vs
    Ip = Io / n
    dD = 4 * Ip * Lr * spec["fsw"] / Vin         # duty lost during current reversal
    return Deff, Deff + dD, dD, Vs, Ip

rows_duty = []
for Vin in (spec["Vin_derate"], spec["Vin_min"], spec["Vin_nom"], spec["Vin_max"]):
    Deff, D, dD, Vs, Ip = duty(Vin)
    rows_duty.append((Vin, Vs, Deff, dD, D))
Deff_nom, D_nom, dD_nom, Vs_nom, Ip_nom = duty(spec["Vin_nom"])
Deff_min, D_min_vin, _, _, _ = duty(spec["Vin_min"])
Vsr_stress = 2 * spec["Vin_max"] / n            # center-tap rectifier stress (clamped)

# --------------------------------------------------------------------------
# 4. Primary / secondary currents
# --------------------------------------------------------------------------
# magnetising current
Lm = 1.0e-3
Im_pk = spec["Vin_nom"] * (D_nom * T / 2) / Lm / 2 + 0.0      # ~ V*t/(2L) triangular peak
Ip_pk = Io / n + Im_pk + 0.5 * spec["ripple_pct"] * Io / n   # reflected ripple + magnetising
Ip_rms = (Io / n) * math.sqrt(D_nom) * 1.05                    # trapezoid approx (+5% freewheeling)
Isec_rms_each = Io * math.sqrt(Deff_nom / 2 + (1 - Deff_nom) / 4)  # each half winding: Io during its active interval, Io/2 while freewheeling
Isr_rms = Isec_rms_each / sr["n_parallel"]                     # per SR device

# --------------------------------------------------------------------------
# 5. ZVS analysis (lagging leg)
# --------------------------------------------------------------------------
C_tr = 50e-12                                                  # transformer winding capacitance
E_req = sic["Coss_er"] * spec["Vin_nom"] ** 2 + 0.5 * C_tr * spec["Vin_nom"] ** 2
Ip_zvs = math.sqrt(2 * E_req / Lr)                             # minimum primary current for ZVS
Io_zvs = (Ip_zvs - Im_pk) * n                                  # equivalent load current
ZVS_load_pct = 100 * Io_zvs / Io
C_eq = 2 * sic["Coss_er"] + C_tr
t_res = (math.pi / 2) * math.sqrt(Lr * C_eq)                   # quarter resonant period (dead time at boundary)
t_full = C_eq * spec["Vin_nom"] / (Io / n)                     # linear charge time at full load

# --------------------------------------------------------------------------
# 6. Transformer (ETD59, 3C95)
# --------------------------------------------------------------------------
core = dict(name="ETD59/31/22", material="3C95 (Ferroxcube) or PC95 (TDK)",
            Ae=3.68e-4, Ve=51.5e-6, Aw=3.66e-4, le=139e-3, lw=0.106)  # m2, m3, m2, m, mean turn length m
Ku, J = 0.30, 450e4                                                  # fill factor, A/m2
Pt = spec["Pout"] / spec["eff_target"] + math.sqrt(2) * spec["Pout"]   # VA (center-tapped)
Bpk_design = 0.125                                                     # T (dB = 0.25 Tpp)
Ap_req = Pt / (4 * Ku * (2 * Bpk_design) * spec["fsw"] * J)            # m^4
Ap_core = core["Ae"] * core["Aw"]
dB_nom = spec["Vin_nom"] * (D_nom * T / 2) / (Np * core["Ae"])         # T p-p at nominal
dB_max = spec["Vin_max"] * (0.95 * T / 2) / (Np * core["Ae"])          # worst case (max duty)
Pv_3C95 = lambda Bpk: 60e3 * (Bpk / 0.125) ** 2.5                      # W/m3 @100 kHz, 100C (Steinmetz fit)
P_core = Pv_3C95(dB_nom / 2) * core["Ve"]
# windings
A_pri = 600 * math.pi * (0.1e-3 / 2) ** 2                              # litz 600 x 0.1 mm
R_pri = 1.72e-8 * (1 + 0.004 * 75) * Np * core["lw"] / A_pri * 1.3     # +30% AC/litz penalty
P_pri_cu = Ip_rms ** 2 * R_pri
A_sec = 2 * 0.15e-3 * 38e-3                                            # 2 parallel foils 0.15 x 38 mm
R_sec = 1.72e-8 * (1 + 0.004 * 75) * Ns * core["lw"] / A_sec * 1.5     # foil AC penalty
P_sec_cu = 2 * Isec_rms_each ** 2 * R_sec
P_xfmr = P_core + P_pri_cu + P_sec_cu
skin_depth = math.sqrt(1.72e-8 / (math.pi * spec["fsw"] * 4e-7 * math.pi)) * 1e3  # mm

# --------------------------------------------------------------------------
# 7. Resonant inductor (ETD39, gapped)
# --------------------------------------------------------------------------
lr_core = dict(name="ETD39/20/13", Ae=1.25e-4, Ve=11.5e-6, lw=0.069)
N_lr = 10
B_lr = Lr * Ip_pk / (N_lr * lr_core["Ae"])
gap_lr = 4e-7 * math.pi * N_lr ** 2 * lr_core["Ae"] / Lr               # m (ignores fringing)
E_lr = 0.5 * Lr * Ip_pk ** 2
P_lr = Pv_3C95(B_lr) * lr_core["Ve"] + Ip_rms ** 2 * (1.72e-8 * 1.3 * N_lr * lr_core["lw"] / A_pri * 1.3)

# --------------------------------------------------------------------------
# 8. Output inductor (High Flux / Kool Mu toroid, 2 stacked 77439 size)
# --------------------------------------------------------------------------
dI = spec["ripple_pct"] * Io
Lo_req = (Vs_nom - Vo) * (Deff_nom * T / 2) / dI
AL_stack = 2 * 135e-9                                                  # 2 stacked 77439-A7 (60u)
N_lo = 5
le_lo = 0.107
Lo_0 = AL_stack * N_lo ** 2
H_lo = N_lo * (Io + dI / 2) / le_lo                                    # A/m
H_oe = H_lo / 79.577
perm_frac = 1 / (1 + (H_oe / 60) ** 1.4 * 0.75)                        # approx 60u Kool Mu roll-off
Lo_full = Lo_0 * perm_frac
dI_full = (Vs_nom - Vo) * (Deff_nom * T / 2) / Lo_full
A_lo = 12e-6                                                           # 2 x 6 mm flat wire
R_lo = 1.72e-8 * 1.3 * N_lo * 0.13 / A_lo
P_lo_cu = Io ** 2 * R_lo
P_lo_core = 1.5                                                        # W, estimate (small ripple flux)

# --------------------------------------------------------------------------
# 9. Capacitors
# --------------------------------------------------------------------------
f_rip = 2 * spec["fsw"]
Co_min_cap = dI_full / (8 * spec["Vout_ripple"] * f_rip)
ESR_max = spec["Vout_ripple"] / dI_full
Co_elec = 6 * 470e-6; ESR_elec = 0.020 / 6
Co_mlcc = 6 * 10e-6 * 0.6                                              # DC-bias derated
Co_total = Co_elec + Co_mlcc
Vo_rip_esr = dI_full * ESR_elec
Vo_rip_cap = dI_full / (8 * Co_total * f_rip)
# load step 50% at 5 kHz crossover
fc = 8e3
dV_step = 0.5 * Io / (2 * math.pi * fc * Co_total)
# input
Ic_in_rms = Ip_nom * math.sqrt(D_nom * (1 - D_nom)) + 1.0
Cin_film = 4 * 10e-6
dVin = Ip_nom * (D_nom * T / 2) / Cin_film

# --------------------------------------------------------------------------
# 10. Loss budget at full load, Vin nominal
# --------------------------------------------------------------------------
P_sic_cond = 4 * Ip_rms ** 2 * sic["Rds_tj"] / 2                       # each device conducts ~half period
P_sic_sw = 4 * sic["Eoff_400V_10A"] * (Ip_pk / 10.0) * spec["fsw"]     # ZVS: turn-off only
P_sic_gate = 4 * sic["Qg"] * (sic["Vgs_on"] - sic["Vgs_off"]) * spec["fsw"]
P_sr_cond = 4 * Isr_rms ** 2 * sr["Rds_tj"]
P_sr_gate = 4 * sr["Qg"] * sr["Vgs_on"] * spec["fsw"]
P_sr_body = 2 * 0.9 * Io * 100e-9 * 2 * spec["fsw"]                    # body diode conduction during SR dead times
C_snub = 470e-12
P_sr_snub = 2 * 2 * C_snub * Vsr_stress ** 2 * spec["fsw"]            # 2 RC snubbers, 2 transitions per cycle
P_clamp = 2 * clamp["Vf"] * 1.5                                        # ~1.5 A avg each clamp diode
P_cin = Ic_in_rms ** 2 * 0.010
P_co = (dI_full / math.sqrt(12)) ** 2 * ESR_elec
P_shunt = Io ** 2 * 0.5e-3
P_bias = 4 * 0.6 + 1.0                                                 # 4 isolated bias modules + control
P_misc = 5.0
losses = {
    "SiC conduction (4x)": P_sic_cond,
    "SiC turn-off switching (4x)": P_sic_sw,
    "SiC gate drive": P_sic_gate,
    "SR conduction (4x)": P_sr_cond,
    "SR body-diode / dead-time": P_sr_body,
    "SR gate drive": P_sr_gate,
    "SR RC snubbers": P_sr_snub,
    "Primary clamp diodes": P_clamp,
    "Transformer core": P_core,
    "Transformer copper": P_pri_cu + P_sec_cu,
    "Resonant inductor": P_lr,
    "Output inductor": P_lo_cu + P_lo_core,
    "Input capacitors": P_cin,
    "Output capacitors": P_co,
    "Output shunt": P_shunt,
    "Bias / control": P_bias,
    "Misc (PCB copper, connectors)": P_misc,
}
P_total = sum(losses.values())
eff = spec["Pout"] / (spec["Pout"] + P_total)

# thermal
Tj_sic = spec["Tamb"] + (P_sic_cond + P_sic_sw) / 4 * (sic["RthJC"] + 0.5 + 0.8)   # Rth pad + heatsink share
Tj_sr = spec["Tamb"] + (P_sr_cond + P_sr_body) / 4 * (sr["RthJC"] + 0.5 + 0.8)

# --------------------------------------------------------------------------
# 11. Control: UCC28951, peak current mode, type-II compensation
# --------------------------------------------------------------------------
Rload = Vo / Io
f_p = 1 / (2 * math.pi * Rload * Co_total)
f_esr = 1 / (2 * math.pi * ESR_elec * Co_elec)
# feedback divider
Vref_fb = 2.5
R_top = 20e3; R_bot = R_top * Vref_fb / (Vo - Vref_fb)
R_bot_std = 1.1e3
Vo_set = Vref_fb * (R_top + R_bot_std) / R_bot_std
# current sense
CT_ratio = 100.0
Ip_oc = 1.5 * Ip_pk
R_burden = 2.0 / (Ip_oc / CT_ratio)                   # UCC28951 CS OC threshold 2.0 V
R_burden_std = 12.0
Ip_oc_std = 2.0 * CT_ratio / R_burden_std
Vcs_fl = Ip_pk / CT_ratio * R_burden_std
# modulator gain (peak CM): Gm ~ Rload*Ns/Np / Rsense_eff * ...
Rsense_eff = R_burden_std / CT_ratio / n                # ohm referred to output current
G_mod_dc = Rload / Rsense_eff / 3.0                     # /3 : COMP-to-CS internal divider in UCC28951
G_plant = lambda f: G_mod_dc / math.sqrt(1 + (f / f_p) ** 2) * math.sqrt(1 + (f / f_esr) ** 2)
# type II: Zi = R_top, Zf = Rz + 1/sCz || Cp
G_needed = 1 / G_plant(fc)                             # mid-band compensator gain Rz/R_top
Rz = G_needed * R_top
Cz = 1 / (2 * math.pi * f_p * 1.5 * Rz)                 # zero at ~1.5*f_p
Cp = 1 / (2 * math.pi * f_esr * Rz)                     # pole at ESR zero
def std(v, series=(1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2)):
    e = math.floor(math.log10(v)); m = v / 10 ** e
    best = min(series, key=lambda s: abs(s - m))
    return best * 10 ** e
Rz_std, Cz_std, Cp_std = std(Rz), std(Cz), std(Cp)
# loop gain
def loop_gain(f):
    s = 2j * math.pi * f
    Zf = Rz_std + 1 / (s * Cz_std)
    Zf = Zf * (1 / (s * Cp_std)) / (Zf + 1 / (s * Cp_std))
    Gc = Zf / R_top          # inverting EA; the modulator closes the loop with negative feedback
    Gp = G_mod_dc / (1 + s * Rload * Co_total) * (1 + s * ESR_elec * Co_elec)
    return Gc * Gp
fv = np.logspace(1, 5, 400)
Lg = np.array([loop_gain(f) for f in fv])
mag = 20 * np.log10(np.abs(Lg)); ph = np.degrees(np.angle(-Lg))  # phase relative to -180
idx = np.argmin(np.abs(mag))
f_cross = fv[idx]; pm = 180 + np.degrees(np.angle(Lg[idx]))
# dead-time / delays
t_delay_ab = max(t_res, 60e-9)
t_delay_cd = max(t_res, 60e-9)
soft_start_ms = 20.0
C_ss = soft_start_ms * 1e-3 * 25e-6 / 5.0               # Iss 25 uA charging to ~5 V
# gate resistors
R_g_on, R_g_off = 5.1, 2.2
I_g_pk = (sic["Vgs_on"] - sic["Vgs_off"]) / (R_g_on + 1.0 + 1.5)       # + internal + driver Rout
# UCC21520 dead-time safety resistor
R_dt = 2.2e3; t_dt_driver = 10e-9 * R_dt / 1e3

# --------------------------------------------------------------------------
# 12. PCB copper
# --------------------------------------------------------------------------
def ipc_width(I, dT=20, oz=2.0):
    """IPC-2221 external trace width (mm) for current I at temperature rise dT."""
    k = 0.048
    A_mil2 = (I / (k * dT ** 0.44)) ** (1 / 0.725)
    t_mil = oz * 1.378
    w_mil = A_mil2 / t_mil
    return w_mil * 0.0254
w_pri = ipc_width(Ip_rms); w_sec = ipc_width(Isec_rms_each); w_out = ipc_width(Io)

# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------
vals = dict(spec=spec, sic=sic, sr=sr, n=n, Np=Np, Ns=Ns, Lr=Lr, Lm=Lm,
            Deff_nom=Deff_nom, D_nom=D_nom, dD_nom=dD_nom, Ip_pk=Ip_pk, Ip_rms=Ip_rms,
            Isec_rms_each=Isec_rms_each, Isr_rms=Isr_rms, Vsr_stress=Vsr_stress,
            Ip_zvs=Ip_zvs, ZVS_load_pct=ZVS_load_pct, t_res=t_res, t_full=t_full,
            core=core, dB_nom=dB_nom, P_core=P_core, Lo_0=Lo_0, Lo_full=Lo_full, N_lo=N_lo,
            dI_full=dI_full, Co_total=Co_total, losses=losses, P_total=P_total, eff=eff,
            R_top=R_top, R_bot=R_bot_std, Vo_set=Vo_set, R_burden=R_burden_std, Ip_oc=Ip_oc_std,
            Rz=Rz_std, Cz=Cz_std, Cp=Cp_std, f_cross=f_cross, pm=pm, C_ss=C_ss,
            R_g_on=R_g_on, R_g_off=R_g_off, R_dt=R_dt, w_pri=w_pri, w_sec=w_sec, w_out=w_out,
            Tj_sic=Tj_sic, Tj_sr=Tj_sr, Ic_in_rms=Ic_in_rms, dVin=dVin)
os.makedirs(os.path.join(ROOT, "design"), exist_ok=True)
with open(os.path.join(ROOT, "design", "design_values.json"), "w") as f:
    json.dump(vals, f, indent=2, default=float)

# ---- charts ---------------------------------------------------------------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.3})

# (a) ZVS boundary vs Lr
fig, ax = plt.subplots(figsize=(6, 3.6))
Lr_v = np.linspace(4e-6, 30e-6, 100)
for Vin in (370, 400, 420):
    Ereq = sic["Coss_er"] * Vin ** 2 + 0.5 * C_tr * Vin ** 2
    Iz = np.sqrt(2 * Ereq / Lr_v)
    ax.plot(Lr_v * 1e6, 100 * (Iz - Im_pk) * n / Io, label=f"Vin = {Vin} V")
ax.axvline(Lr * 1e6, color="k", ls="--", lw=1, label=f"chosen Lr = {Lr*1e6:.0f} uH")
ax.set_xlabel("Resonant inductance Lr (uH)"); ax.set_ylabel("Min. load for lagging-leg ZVS (%)")
ax.set_title("ZVS boundary vs resonant inductance"); ax.legend(); ax.set_ylim(0, 80)
fig.tight_layout(); fig.savefig(os.path.join(IMG, "zvs_boundary.png"), dpi=150); plt.close(fig)

# (b) duty cycle vs Vin
fig, ax = plt.subplots(figsize=(6, 3.6))
Vin_v = np.linspace(300, 430, 100)
for frac in (1.0, 0.5, 0.1):
    Dv = [duty(v, Io=Io * frac)[1] for v in Vin_v]
    ax.plot(Vin_v, Dv, label=f"{int(frac*100)} % load")
ax.axhline(0.95, color="r", ls="--", lw=1, label="controller max duty")
ax.axvspan(spec["Vin_min"], spec["Vin_max"], color="g", alpha=0.08, label="full-power input range")
ax.set_xlabel("Input voltage (V)"); ax.set_ylabel("Total duty cycle D (incl. duty loss)")
ax.set_title("Duty cycle vs input voltage (n = 6, Lr = 12 uH)"); ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(IMG, "duty_vs_vin.png"), dpi=150); plt.close(fig)

# (c) loss breakdown
fig, ax = plt.subplots(figsize=(7, 4))
names = list(losses.keys()); valsl = [losses[k] for k in names]
order = np.argsort(valsl)[::-1]
ax.barh([names[i] for i in order][::-1], [valsl[i] for i in order][::-1], color="#3b6ea5")
ax.set_xlabel("Loss (W)"); ax.set_title(f"Loss budget at 3 kW / 400 V in: {P_total:.0f} W total, eta = {100*eff:.1f} %")
fig.tight_layout(); fig.savefig(os.path.join(IMG, "loss_budget.png"), dpi=150); plt.close(fig)

# (d) efficiency vs load (scaled loss model)
fig, ax = plt.subplots(figsize=(6, 3.6))
load = np.linspace(0.1, 1.0, 50)
P_fixed = P_sic_gate + P_sr_gate + P_bias + P_core + P_sr_snub + 0.5 * P_misc
P_lin = P_sic_sw + P_sr_body + P_clamp + P_lo_core
P_sq = P_total - P_fixed - P_lin
Pl = P_fixed + P_lin * load + P_sq * load ** 2
ax.plot(100 * load, 100 * spec["Pout"] * load / (spec["Pout"] * load + Pl))
ax.set_xlabel("Load (%)"); ax.set_ylabel("Efficiency (%)"); ax.set_ylim(90, 99)
ax.set_title("Estimated efficiency vs load (400 V in, 48 V out)")
fig.tight_layout(); fig.savefig(os.path.join(IMG, "efficiency_vs_load.png"), dpi=150); plt.close(fig)

# (e) loop gain bode
fig, (a1, a2) = plt.subplots(2, 1, figsize=(6, 5), sharex=True)
a1.semilogx(fv, mag); a1.set_ylabel("Loop gain (dB)"); a1.axhline(0, color="k", lw=0.8)
a1.set_title(f"Voltage loop (peak CM): fc = {f_cross/1e3:.1f} kHz, PM = {pm:.0f} deg")
a2.semilogx(fv, np.degrees(np.angle(Lg))); a2.set_ylabel("Phase (deg)"); a2.set_xlabel("Frequency (Hz)")
a2.axhline(-180, color="r", lw=0.8, ls="--")
fig.tight_layout(); fig.savefig(os.path.join(IMG, "loop_bode.png"), dpi=150); plt.close(fig)

# ---- markdown report ------------------------------------------------------
def md():
    L = []
    w = L.append
    w("# 02 - Design calculations\n")
    w("_Generated by `tools/psfb_design.py`. Re-run the script after changing any input._\n")
    w("## 1. Specification\n")
    w("| Parameter | Value |\n|---|---|")
    w(f"| Input voltage (full power) | {spec['Vin_min']:.0f} - {spec['Vin_max']:.0f} V DC (nominal {spec['Vin_nom']:.0f} V, from PFC) |")
    w(f"| Input voltage (derated power) | down to {spec['Vin_derate']:.0f} V (hold-up) |")
    w(f"| Output | {Vo:.0f} V / {Io:.1f} A / {spec['Pout']/1e3:.1f} kW |")
    w(f"| Switching frequency | {spec['fsw']/1e3:.0f} kHz per switch (output ripple at {2*spec['fsw']/1e3:.0f} kHz) |")
    w(f"| Topology | ZVS phase-shifted full bridge, centre-tapped secondary, synchronous rectification, primary clamp diodes |")
    w(f"| Isolation | reinforced, {spec['iso_test_V']:.0f} Vrms test, >= {spec['creepage_mm']:.0f} mm creepage/clearance |")
    w(f"| Efficiency target | >= {100*spec['eff_target']:.0f} % at full load |\n")

    w("## 2. Turns ratio and duty cycle\n")
    w(f"Transformer ratio chosen **n = Np/Ns = {n:.0f}** ({Np}:{Ns}:{Ns}), resonant inductance **Lr = {Lr*1e6:.0f} uH**.\n")
    w("Duty loss during primary current reversal: dD = 4 * Ip * Lr * fsw / Vin\n")
    w("| Vin (V) | Vsec (V) | D_eff | duty loss dD | total D |\n|---|---|---|---|---|")
    for Vin, Vs, Deff, dD, D in rows_duty:
        w(f"| {Vin:.0f} | {Vs:.1f} | {Deff:.3f} | {dD:.3f} | {D:.3f} |")
    w(f"\nAt {spec['Vin_derate']:.0f} V the total duty exceeds the controller limit, so the output is current-limited (hold-up derating).")
    w(f"SR drain stress (centre-tap, clamped by the primary clamp diodes): 2 * Vin_max / n = **{Vsr_stress:.0f} V** -> 200 V MOSFETs ({sr['part']}).\n")
    w("![duty](img/duty_vs_vin.png)\n")

    w("## 3. Currents\n")
    w("| Quantity | Value |\n|---|---|")
    w(f"| Primary reflected load current Io/n | {Io/n:.1f} A |")
    w(f"| Magnetising current peak (Lm = {Lm*1e3:.1f} mH) | {Im_pk:.2f} A |")
    w(f"| Primary peak current | {Ip_pk:.1f} A |")
    w(f"| Primary RMS current | {Ip_rms:.1f} A |")
    w(f"| Secondary half-winding RMS | {Isec_rms_each:.1f} A |")
    w(f"| Per SR MOSFET RMS ({sr['n_parallel']} in parallel) | {Isr_rms:.1f} A |")
    w(f"| Input capacitor RMS current | {Ic_in_rms:.1f} A |\n")

    w("## 4. ZVS of the lagging leg\n")
    w(f"Energy to swing the leg: E = Coss(er) * Vin^2 + 0.5 * Ctr * Vin^2 = {E_req*1e6:.1f} uJ "
      f"(Coss(er) = {sic['Coss_er']*1e12:.0f} pF per device, Ctr = {C_tr*1e12:.0f} pF).\n")
    w(f"Minimum primary current: Ip_zvs = sqrt(2E/Lr) = **{Ip_zvs:.2f} A** -> ZVS maintained down to about **{ZVS_load_pct:.0f} % load** "
      f"(magnetising current included). Below that the lagging leg switches with partial ZVS; the SiC Coss energy at 400 V is small (~{E_req*1e6:.0f} uJ -> {E_req*spec['fsw']*2:.1f} W worst case).\n")
    w(f"Resonant transition time at the boundary: t = (pi/2) * sqrt(Lr * Ceq) = **{t_res*1e9:.0f} ns**; at full load the linear charge time is {t_full*1e9:.0f} ns. "
      f"UCC28951 adaptive delays (ADEL/ADELEF) are set to cover {t_full*1e9:.0f} - {t_res*1e9:.0f} ns, with a {t_dt_driver*1e9:.0f} ns hard minimum in the UCC21520 (R_DT = {R_dt/1e3:.1f} k).\n")
    w("![zvs](img/zvs_boundary.png)\n")

    w("## 5. Main transformer\n")
    w(f"Throughput VA for a centre-tapped secondary: Pt = Pout/eta + sqrt(2) * Pout = {Pt:.0f} VA. "
      f"Required area product (Ku = {Ku}, J = {J/1e4:.0f} A/cm^2, Bpk = {Bpk_design} T): Ap = **{Ap_req*1e8:.1f} cm^4**; "
      f"{core['name']} provides {Ap_core*1e8:.1f} cm^4.\n")
    w("| Item | Value |\n|---|---|")
    w(f"| Core | {core['name']}, {core['material']}, ungapped (Lm ~ {Lm*1e3:.0f} mH) |")
    w(f"| Turns | Np = {Np}, Ns = {Ns} + {Ns} (centre-tapped) |")
    w(f"| Flux swing at 400 V nominal | {dB_nom*1e3:.0f} mT p-p (Bpk = {dB_nom/2*1e3:.0f} mT) |")
    w(f"| Flux swing worst case (420 V, D = 0.95) | {dB_max*1e3:.0f} mT p-p |")
    w(f"| Core loss | {P_core:.1f} W |")
    w(f"| Primary winding | litz 600 x 0.1 mm ({A_pri*1e6:.2f} mm^2), R = {R_pri*1e3:.1f} mOhm, P = {P_pri_cu:.1f} W |")
    w(f"| Secondary windings | 2 x copper foil 0.15 x 38 mm in parallel per half ({A_sec*1e6:.1f} mm^2), R = {R_sec*1e3:.2f} mOhm, P = {P_sec_cu:.1f} W total |")
    w(f"| Skin depth at {spec['fsw']/1e3:.0f} kHz | {skin_depth:.2f} mm |")
    w(f"| Winding arrangement | S1 - P/2 - S2 - P/2 interleaved (foil secondaries), 3 layers reinforced tape between P and S |")
    w(f"| Total transformer loss | {P_xfmr:.1f} W |\n")

    w("## 6. Resonant (shim) inductor\n")
    w(f"Lr = {Lr*1e6:.0f} uH on {lr_core['name']} (3C95), N = {N_lr} turns litz, air gap ~ {gap_lr*1e3:.2f} mm (centre leg, before fringing correction). "
      f"Bpk = {B_lr*1e3:.0f} mT at Ip_pk = {Ip_pk:.1f} A, stored energy {E_lr*1e6:.0f} uJ, estimated loss {P_lr:.1f} W. "
      f"Transformer leakage (~1 uH) adds to this; measure and trim the gap.\n")

    w("## 7. Output inductor\n")
    w(f"Required for {100*spec['ripple_pct']:.0f} % ripple: Lo = (Vsec - Vo) * D_eff * T/2 / dI = **{Lo_req*1e6:.1f} uH**.\n")
    w(f"Design: 2 stacked Magnetics 77439-A7 (Kool Mu 60u, OD 47 mm) or 58439 (High Flux), N = {N_lo} turns of 2 x 6 mm flat copper. "
      f"L0 = {Lo_0*1e6:.1f} uH, H = {H_oe:.0f} Oe at peak current -> {100*perm_frac:.0f} % permeability -> **L = {Lo_full*1e6:.1f} uH at full load**, ripple {dI_full:.1f} A p-p ({100*dI_full/Io:.0f} %). "
      f"Copper loss {P_lo_cu:.1f} W (R = {R_lo*1e3:.2f} mOhm).\n")

    w("## 8. Capacitors\n")
    w(f"Output: ripple spec {spec['Vout_ripple']*1e3:.0f} mV p-p -> ESR < {ESR_max*1e3:.1f} mOhm and C > {Co_min_cap*1e6:.0f} uF. "
      f"Chosen 6 x 470 uF / 63 V low-ESR electrolytic (ESR {ESR_elec*1e3:.0f} mOhm parallel) + 6 x 10 uF / 100 V X7S MLCC. "
      f"Ripple: ESR term {Vo_rip_esr*1e3:.0f} mV, capacitive term {Vo_rip_cap*1e3:.0f} mV. 50 % load step at fc = {fc/1e3:.0f} kHz: dV ~ {dV_step*1e3:.0f} mV.\n")
    w(f"Input: 4 x 10 uF / 450 V film (B32778) + 2 x 0.47 uF / 630 V MLCC at the bridge. Ripple {dVin:.1f} V p-p, capacitor RMS current {Ic_in_rms:.1f} A. "
      f"Bulk hold-up capacitance is provided by the PFC stage.\n")

    w("## 9. Loss budget and efficiency (400 V in, full load)\n")
    w("| Loss element | W |\n|---|---|")
    for k, v in losses.items():
        w(f"| {k} | {v:.1f} |")
    w(f"| **Total** | **{P_total:.1f}** |")
    w(f"\n**Estimated efficiency: {100*eff:.1f} %** (target {100*spec['eff_target']:.0f} %).\n")
    w(f"Junction temperatures (Tamb {spec['Tamb']:.0f} C, forced air, extruded heatsinks): SiC ~ {Tj_sic:.0f} C, SR ~ {Tj_sr:.0f} C.\n")
    w("![loss](img/loss_budget.png)\n\n![eff](img/efficiency_vs_load.png)\n")

    w("## 10. Control loop (UCC28951, peak current mode)\n")
    w("| Item | Value |\n|---|---|")
    w(f"| Feedback divider | R_top = 2 x {R_top/2/1e3:.1f} k (series), R_bot = {R_bot_std/1e3:.2f} k -> Vout = {Vo_set:.2f} V with EA+ = {Vref_fb} V |")
    w(f"| Current transformer | 1:{CT_ratio:.0f}, burden R = {R_burden_std:.0f} Ohm (calc. {R_burden:.1f} Ohm) |")
    w(f"| CS at full load / OC threshold | {Vcs_fl:.2f} V / 2.0 V -> cycle-by-cycle limit at Ip = {Ip_oc_std:.1f} A ({Ip_oc_std*n:.0f} A output) |")
    w(f"| Plant pole / ESR zero | {f_p:.0f} Hz / {f_esr/1e3:.1f} kHz |")
    w(f"| Type-II compensator | Rz = {Rz_std/1e3:.1f} k, Cz = {Cz_std*1e9:.0f} nF, Cp = {Cp_std*1e12:.0f} pF |")
    w(f"| Crossover / phase margin | {f_cross/1e3:.1f} kHz / {pm:.0f} deg |")
    w(f"| Soft start | C_SS = {C_ss*1e6:.2f} uF -> ~{soft_start_ms:.0f} ms |")
    w(f"| Gate resistors (SiC) | R_on = {R_g_on} Ohm, R_off = {R_g_off} Ohm (diode), peak gate current ~{I_g_pk:.1f} A |")
    w("\n![bode](img/loop_bode.png)\n")

    w("## 11. PCB copper requirements (IPC-2221, 2 oz outer, 20 K rise)\n")
    w("| Net | Current | Min. width (single layer) | Implementation |\n|---|---|---|---|")
    w(f"| Primary loop (VBUS, SW, PRI) | {Ip_rms:.1f} A rms | {w_pri:.1f} mm | 6 mm tracks + In2 plane |")
    w(f"| Secondary windings (SEC_A/B) | {Isec_rms_each:.1f} A rms | {w_sec:.1f} mm | polygon pours on F.Cu + B.Cu |")
    w(f"| Output (VOUT, SGND) | {Io:.1f} A | {w_out:.1f} mm | pours on F.Cu, In2.Cu, B.Cu stitched with vias |")
    return "\n".join(L) + "\n"

with open(os.path.join(DOCS, "02_design_calculations.md"), "w") as f:
    f.write(md())

if __name__ == "__main__":
    print(md())
