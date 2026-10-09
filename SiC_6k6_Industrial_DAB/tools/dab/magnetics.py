"""
Magnetic component models: Steinmetz core loss (with the iGSE correction for the
piecewise-linear DAB flux waveform), Dowell AC resistance for foil/litz windings, and
area-product sizing.  Material data: Ferroxcube 3C95 / TDK N97 class MnZn ferrite
(Steinmetz parameters are curve fits of the published loss charts at 100 C; re-fit from the
datasheet before relying on absolute numbers).
"""
import math

MATERIALS = {
    # Pv = k * f^alpha * B^beta  (W/m3, f in Hz, B peak in T); fit valid 50-200 kHz, 100 C.
    # Check: 3C95 at 100 kHz / 100 mT -> 58 kW/m3 (datasheet chart ~60 kW/m3)
    "3C95": dict(k=1.63, alpha=1.42, beta=2.55, Bsat_100C=0.41, mu_i=3000, rho=4800),
    "N97": dict(k=1.8, alpha=1.40, beta=2.50, Bsat_100C=0.41, mu_i=2300, rho=4850),
    "3C97": dict(k=1.3, alpha=1.43, beta=2.60, Bsat_100C=0.41, mu_i=3000, rho=4800),
}

CORES = {
    # name: Ae (m2), Ve (m3), Aw (window area m2), le (m), lw (mean turn length m), window height (m), width (m)
    "E55/28/21": dict(Ae=3.54e-4, Ve=4.40e-5, Aw=2.80e-4, le=12.4e-2, lw=0.116, hw=37.0e-3, bw=10.1e-3),
    "E65/32/27": dict(Ae=5.40e-4, Ve=7.93e-5, Aw=3.94e-4, le=14.7e-2, lw=0.150, hw=44.2e-3, bw=11.7e-3),
    "ETD59/31/22": dict(Ae=3.68e-4, Ve=5.15e-5, Aw=3.66e-4, le=13.9e-2, lw=0.106, hw=41.2e-3, bw=10.7e-3),
    "PQ65/60": dict(Ae=6.70e-4, Ve=9.60e-5, Aw=2.72e-4, le=14.3e-2, lw=0.165, hw=36.5e-3, bw=9.9e-3),
    "E70/33/32": dict(Ae=6.83e-4, Ve=1.02e-4, Aw=4.45e-4, le=14.9e-2, lw=0.160, hw=43.6e-3, bw=12.4e-3),
    "ETD49/25/16": dict(Ae=2.11e-4, Ve=2.40e-5, Aw=2.73e-4, le=11.4e-2, lw=0.085, hw=33.5e-3, bw=9.8e-3),
    "ETD44/22/15": dict(Ae=1.73e-4, Ve=1.78e-5, Aw=2.13e-4, le=10.3e-2, lw=0.077, hw=29.5e-3, bw=9.0e-3),
    "ETD39/20/13": dict(Ae=1.25e-4, Ve=1.15e-5, Aw=1.78e-4, le=9.22e-2, lw=0.069, hw=25.7e-3, bw=7.1e-3),
}

RHO_CU_20 = 1.72e-8
MU0 = 4e-7 * math.pi


def steinmetz_loss(material, f, Bpk, Ve, igse_factor=1.0):
    m = MATERIALS[material]
    return m["k"] * f ** m["alpha"] * Bpk ** m["beta"] * Ve * igse_factor


def igse_correction(material, duty_square=1.0):
    """
    For a triangular/trapezoidal flux waveform the iGSE (Venkatachalam et al. 2002) predicts
    a loss ratio relative to a sinusoid of the same peak.  For a symmetrical triangular flux
    (square voltage, D = 1) the ratio is approx. (8/pi^2)^(beta-1)... a practical closed form is
    k_tri = (2/pi)^(alpha-1) * 8/pi^2 * ... ; here we use the tabulated ratio ~1.1-1.3 for
    beta 2.5-2.7, and 1.0 for sinusoidal excitation.  Returns the multiplier.
    """
    m = MATERIALS[material]
    return 1.0 + 0.4 * (m["beta"] - 2.0) * duty_square


def skin_depth(f, T=100.0):
    rho = RHO_CU_20 * (1 + 0.00393 * (T - 20))
    return math.sqrt(rho / (math.pi * f * MU0))


def dowell_rac_ratio(h, delta, m_layers, porosity=0.8):
    """
    Dowell's AC/DC resistance ratio for a winding of m_layers foil layers of thickness h,
    skin depth delta, layer porosity factor eta (Dowell 1966, Hurley & Woelfle 2013).
    """
    x = h * math.sqrt(porosity) / delta
    if x < 1e-6:
        return 1.0
    sh, ch = math.sinh(2 * x), math.cosh(2 * x)
    s2, c2 = math.sin(2 * x), math.cos(2 * x)
    shx, chx = math.sinh(x), math.cosh(x)
    sx, cx = math.sin(x), math.cos(x)
    t1 = (sh + s2) / (ch - c2)
    t2 = (shx - sx) / (chx + cx)
    return x * (t1 + 2 * (m_layers ** 2 - 1) / 3 * t2)


def litz_rac_ratio(d_strand, delta, n_strands, m_layers_equiv):
    """Approximate litz AC resistance ratio (strand-level Dowell with effective layers)."""
    return dowell_rac_ratio(d_strand * 0.886, delta, m_layers_equiv * math.sqrt(n_strands) / 2, porosity=0.5)


def area_product_required(P_throughput, Bpk, J, f, Ku=0.3, Kf=4.0):
    """Ap = Pt / (Kf * Ku * Bpk*2 * f * J)   [m^4], Pt in VA, J in A/m2."""
    return P_throughput / (Kf * Ku * 2 * Bpk * f * J)


def turns_for_flux(V, D, f, Bpk, Ae):
    """Square-wave excitation: N = V * D / (4 * f * Bpk * Ae)   (Faraday, D = effective duty of V)."""
    return V * D / (4 * f * Bpk * Ae)


def peak_flux(V, D, f, N, Ae):
    return V * D / (4 * f * N * Ae)


def gap_for_inductance(L, N, Ae, mu_r_core=3000, le=0.1):
    """Centre-leg gap (m) for inductance L with N turns (fringing ignored, core reluctance included)."""
    return MU0 * N ** 2 * Ae / L - le / mu_r_core


# ---------------------------------------------------------------------------
# Design routines used by 04_Design_Calculations and 06_Magnetics
# ---------------------------------------------------------------------------
def design_transformer(V1, V2, n, fs, I1_rms, I2_rms, P, core="E65/32/27", material="3C95",
                       Bpk_target=0.13, T=100.0, interleaved=True, Ku_max=0.70):
    """
    Square-wave (D = 1) DAB transformer on an E core pair.  Returns a dict with turns, flux,
    core loss (Steinmetz with iGSE multiplier), winding geometry, Dowell AC resistance,
    copper loss, fill factor and a leakage inductance estimate for the chosen arrangement.
    """
    c = CORES[core]; m = MATERIALS[material]
    N1 = math.ceil(turns_for_flux(V1, 1.0, fs, Bpk_target, c["Ae"]))
    N2 = max(1, round(N1 / n))
    N1 = round(N2 * n)                         # keep the exact ratio
    Bpk = peak_flux(V1, 1.0, fs, N1, c["Ae"])
    P_core = steinmetz_loss(material, fs, Bpk, c["Ve"], igse_correction(material, 1.0))
    delta = skin_depth(fs, T)
    rho = RHO_CU_20 * (1 + 0.00393 * (T - 20))
    # primary: litz, strand 0.1 mm, J ~ 4 A/mm2
    J = 4.0e6
    A1 = I1_rms / J; A2 = I2_rms / J
    strand_d = 0.1e-3; strand_a = math.pi * (strand_d / 2) ** 2
    n1_strands = math.ceil(A1 / strand_a); n2_strands = math.ceil(A2 / strand_a)
    A1 = n1_strands * strand_a; A2 = n2_strands * strand_a
    # litz bundle diameter (packing factor 0.5), layers that fit in the window height
    d1 = math.sqrt(4 * A1 / math.pi / 0.5); d2 = math.sqrt(4 * A2 / math.pi / 0.5)
    turns_per_layer1 = max(1, int(c["hw"] * 0.9 / d1)); layers1 = math.ceil(N1 / turns_per_layer1)
    turns_per_layer2 = max(1, int(c["hw"] * 0.9 / d2)); layers2 = math.ceil(N2 / turns_per_layer2)
    # Dowell with litz strands (effective layers = physical layers of bundles, strand-level porosity)
    m_eff1 = layers1 if not interleaved else max(1, layers1 / 2)
    m_eff2 = layers2 if not interleaved else max(1, layers2 / 2)
    Fr1 = litz_rac_ratio(strand_d, delta, n1_strands, m_eff1)
    Fr2 = litz_rac_ratio(strand_d, delta, n2_strands, m_eff2)
    R1dc = rho * N1 * c["lw"] / A1; R2dc = rho * N2 * c["lw"] / A2
    P_cu = I1_rms ** 2 * R1dc * Fr1 + I2_rms ** 2 * R2dc * Fr2
    fill = (N1 * A1 / 0.5 + N2 * A2 / 0.5) / c["Aw"]        # bundle area / window (litz packing 0.5); copper fill = 0.5 * fill
    # leakage inductance (Hurley & Woelfle, 2-winding, referred to primary):
    # L_lk = mu0 N1^2 lw / bw * (h_ins + (h1 + h2)/3) ; interleaving P/2-S-P/2 divides by ~4
    h1 = layers1 * d1; h2 = layers2 * d2; h_ins = 1.0e-3            # 1 mm reinforced insulation
    Llk = MU0 * N1 ** 2 * c["lw"] / c["hw"] * (h_ins + (h1 + h2) / 3)
    if interleaved:
        Llk /= 4
    # interwinding capacitance (parallel plate, insulation 1 mm, eps_r 3.5)
    C_iw = 3.5 * 8.854e-12 * (N1 * d1 * c["lw"]) / h_ins if not interleaved else 2 * 3.5 * 8.854e-12 * (N1 * d1 * c["lw"]) / h_ins
    # thermal: natural + forced air, surface area approx 2 x core surface
    area = 2 * (c["le"] * 0.03 + 2 * c["Ae"]) * 4
    dT = (P_core + P_cu) / (12.0 * area)                    # 12 W/m2K forced air (3 m/s)
    return dict(core=core, material=material, N1=N1, N2=N2, Bpk=Bpk, P_core=P_core, P_cu=P_cu, P_total=P_core + P_cu,
                R1dc=R1dc, R2dc=R2dc, Fr1=Fr1, Fr2=Fr2, strands1=n1_strands, strands2=n2_strands, layers1=layers1, layers2=layers2,
                A1=A1, A2=A2, fill=fill, fill_ok=fill <= Ku_max, Llk=Llk, C_iw=C_iw, delta=delta, dT=dT,
                Ae=c["Ae"], Ve=c["Ve"], Aw=c["Aw"], Lm=None)


def design_inductor(L, I_pk, I_rms, fs, core="E55/28/21", material="3C95", Bpk_max=0.2, T=100.0):
    """Gapped ferrite series inductor: turns, gap, flux, losses (triangular-ish current)."""
    c = CORES[core]
    N = math.ceil(L * I_pk / (Bpk_max * c["Ae"]))
    Bpk = L * I_pk / (N * c["Ae"])
    gap = gap_for_inductance(L, N, c["Ae"], 3000, c["le"])
    # AC flux swing: the inductor sees the full DAB voltage difference; approximate ripple flux = Bpk (bipolar)
    P_core = steinmetz_loss(material, fs, Bpk, c["Ve"], igse_correction(material, 1.0))
    delta = skin_depth(fs, T)
    rho = RHO_CU_20 * (1 + 0.00393 * (T - 20))
    J = 4.0e6
    A = I_rms / J; strand_a = math.pi * (0.05e-3) ** 2; strands = math.ceil(A / strand_a); A = strands * strand_a
    d = math.sqrt(4 * A / math.pi / 0.5)
    tpl = max(1, int(c["hw"] * 0.9 / d)); layers = math.ceil(N / tpl)
    Fr = litz_rac_ratio(0.1e-3, delta, strands, layers) * 1.3     # +30 % for fringing-field loss near the gap
    Rdc = rho * N * c["lw"] / A
    P_cu = I_rms ** 2 * Rdc * Fr
    E = 0.5 * L * I_pk ** 2
    return dict(core=core, material=material, N=N, Bpk=Bpk, gap=gap, P_core=P_core, P_cu=P_cu, P_total=P_core + P_cu,
                strands=strands, layers=layers, Rdc=Rdc, Fr=Fr, E=E, fill=N * A / 0.5 / c["Aw"])
