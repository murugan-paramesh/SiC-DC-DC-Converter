"""
2-D finite-difference magnetostatic solver for transformer winding windows (numpy / scipy only).

Formulation
-----------
Planar 2-D (translational symmetry along the conductor direction z).  Vector potential A = A_z(x, y):

    -d/dx( nu dA/dx ) - d/dy( nu dA/dy ) = J_z,      nu = 1 / (mu0 mu_r)

    B_x = dA/dy,  B_y = -dA/dx,  H = B / (mu0 mu_r)

discretised on a uniform Cartesian grid (cell size h) with node-based A and cell-based material/source
data (five-point stencil, face reluctivity = mean of the two cells sharing the face).  Dirichlet A = 0
on the outer boundary; the ferrite core is modelled as a finite-permeability region (mu_r ~ 3000)
surrounding the window, so the high-mu boundary of the window appears naturally (flux enters the core
normally, tangential H ~ 0).  The linear system is solved with scipy.sparse.linalg.spsolve (SuperLU).

Energy and inductance (per unit depth; multiplied by the mean turn length lw for 3-D numbers):

    W' = 1/2 sum_cells B.H h^2      (field form)
    W' = 1/2 sum_nodes A J h^2      (source form, used as a consistency check)
    L  = 2 W' lw / I^2              (leakage inductance with N1 I1 = -N2 I2 in the window)

Limitations: 2-D (no end-winding / 3-D fringing), magnetostatic (no eddy currents in the field solve;
AC resistance is evaluated a posteriori from the DC field distribution, which is the Dowell/Ferreira
assumption), isotropic linear materials, rectangles aligned with the grid.
"""
import math
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.special import ber, bei, berp, beip, jv

MU0 = 4e-7 * math.pi
RHO_CU_20 = 1.72e-8


def rho_cu(T=100.0):
    return RHO_CU_20 * (1 + 0.00393 * (T - 20.0))


def skin_depth(f, T=100.0):
    return math.sqrt(rho_cu(T) / (math.pi * f * MU0))


class Rect:
    """Axis-aligned rectangle region [x0, x1] x [y0, y1] (m) with relative permeability and current I (A)."""

    def __init__(self, x0, y0, x1, y1, mu_r=None, I=0.0, name=""):
        # mu_r = None leaves the material of the cells unchanged (conductor regions default to air)
        self.x0, self.y0, self.x1, self.y1 = float(x0), float(y0), float(x1), float(y1)
        self.mu_r, self.I, self.name = mu_r, I, name

    @property
    def area(self):
        return (self.x1 - self.x0) * (self.y1 - self.y0)


class FDMagnetostatic:
    def __init__(self, Lx, Ly, h):
        self.Lx, self.Ly, self.h = Lx, Ly, h
        self.nx, self.ny = int(round(Lx / h)), int(round(Ly / h))
        self.h = Lx / self.nx                       # exact cell size in x; y uses the same h
        self.ny = int(round(Ly / self.h))
        self.Ly = self.ny * self.h
        self.xc = (np.arange(self.nx) + 0.5) * self.h   # cell centres
        self.yc = (np.arange(self.ny) + 0.5) * self.h
        self.mu_r = np.ones((self.ny, self.nx))
        self.J = np.zeros((self.ny, self.nx))
        self.regions = []
        self.A = None

    def _mask(self, r):
        ix = (self.xc >= r.x0) & (self.xc < r.x1)
        iy = (self.yc >= r.y0) & (self.yc < r.y1)
        return np.ix_(iy, ix)

    def add(self, r):
        m = self._mask(r)
        n_cells = len(m[0].ravel()) * len(m[1].ravel())
        if r.mu_r is not None:
            self.mu_r[m] = r.mu_r
        if r.I != 0.0:
            if n_cells == 0:
                raise ValueError(f"region {r.name} contains no cells at h = {self.h}")
            area_cells = n_cells * self.h ** 2
            self.J[m] += r.I / area_cells          # current enforced exactly on the rasterised area
        self.regions.append(r)
        return self

    def solve(self):
        nx, ny, h = self.nx, self.ny, self.h
        Nx, Ny = nx + 1, ny + 1                      # nodes
        nu = 1.0 / (MU0 * self.mu_r)
        # pad cells with the boundary material for the stencil at the edges
        nup = np.pad(nu, 1, mode="edge")
        # face reluctivities around node (i, j): node (i,j) is at the corner of cells (i-1..i, j-1..j)
        # east face between node (i,j) and (i+1,j) passes through cells (i, j-1) and (i, j)  [cell idx: x=i, y=j]
        # using padded cells: cell x index i -> nup[:, i+1]
        # arrays indexed [node_y, node_x]
        cell_sw = nup[0:Ny, 0:Nx]      # cell (x=i-1, y=j-1)
        cell_se = nup[0:Ny, 1:Nx + 1]  # cell (x=i,   y=j-1)
        cell_nw = nup[1:Ny + 1, 0:Nx]  # cell (x=i-1, y=j)
        cell_ne = nup[1:Ny + 1, 1:Nx + 1]
        nu_e = 0.5 * (cell_se + cell_ne)
        nu_w = 0.5 * (cell_sw + cell_nw)
        nu_n = 0.5 * (cell_nw + cell_ne)
        nu_s = 0.5 * (cell_sw + cell_se)
        # source at nodes: mean of the 4 surrounding cells
        Jp = np.pad(self.J, 1, mode="constant")
        Jn = 0.25 * (Jp[0:Ny, 0:Nx] + Jp[0:Ny, 1:Nx + 1] + Jp[1:Ny + 1, 0:Nx] + Jp[1:Ny + 1, 1:Nx + 1])
        idx = np.arange(Nx * Ny).reshape(Ny, Nx)
        interior = np.zeros((Ny, Nx), bool)
        interior[1:-1, 1:-1] = True
        diag = (nu_e + nu_w + nu_n + nu_s)
        rows, cols, vals = [], [], []

        def link(nu_f, dy, dx):
            m = interior.copy()
            r = idx[m]
            c = idx[1 + dy:Ny - 1 + dy, 1 + dx:Nx - 1 + dx].ravel()
            rows.append(r); cols.append(c); vals.append(-nu_f[m])

        link(nu_e, 0, 1); link(nu_w, 0, -1); link(nu_n, 1, 0); link(nu_s, -1, 0)
        rows.append(idx[interior]); cols.append(idx[interior]); vals.append(diag[interior])
        # Dirichlet boundary nodes: A = 0
        bnd = ~interior
        rows.append(idx[bnd]); cols.append(idx[bnd]); vals.append(np.ones(bnd.sum()))
        K = sp.csc_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(Nx * Ny, Nx * Ny))
        rhs = (Jn * h ** 2).ravel()
        rhs[bnd.ravel()] = 0.0
        A = spla.spsolve(K, rhs)
        self.A = A.reshape(Ny, Nx)
        self.Jn = Jn
        return self.A

    def fields(self):
        """Cell-centred B (T) and H (A/m) from the nodal A."""
        A, h = self.A, self.h
        Bx = 0.5 * ((A[1:, :-1] + A[1:, 1:]) - (A[:-1, :-1] + A[:-1, 1:])) / h
        By = -0.5 * ((A[:-1, 1:] + A[1:, 1:]) - (A[:-1, :-1] + A[1:, :-1])) / h
        Hx, Hy = Bx / (MU0 * self.mu_r), By / (MU0 * self.mu_r)
        return Bx, By, Hx, Hy

    def energy_per_depth(self):
        """Returns (W_field, W_source) in J/m."""
        Bx, By, Hx, Hy = self.fields()
        Wf = 0.5 * np.sum(Bx * Hx + By * Hy) * self.h ** 2
        Ws = 0.5 * np.sum(self.A * self.Jn) * self.h ** 2
        return Wf, Ws

    def inductance(self, I_ref, lw):
        Wf, Ws = self.energy_per_depth()
        return 2 * Wf * lw / I_ref ** 2, 2 * Ws * lw / I_ref ** 2

    def region_cells(self, r):
        return self._mask(r)


# ---------------------------------------------------------------------------
# AC resistance from the DC field distribution (Dowell / Ferreira type post-processing)
# ---------------------------------------------------------------------------
def slab_loss_per_area(Ha, Hb, t, f, T=100.0, n=400):
    """
    1-D eddy-current solution in a conducting slab of thickness t with tangential field amplitudes
    Ha (face y=0) and Hb (face y=t), peak values.  Returns (P_ac, P_dc) in W/m^2 (time average).
    H(y) = [Ha sinh(k(t-y)) + Hb sinh(k y)] / sinh(k t),  k = (1+j)/delta,  J = -dH/dy.
    """
    sigma = 1.0 / rho_cu(T)
    if f <= 0:
        Jdc = (Hb - Ha) / t
        return 0.5 * Jdc ** 2 / sigma * t, 0.5 * Jdc ** 2 / sigma * t
    d = skin_depth(f, T)
    k = (1 + 1j) / d
    y = np.linspace(0, t, n)
    dH = (-Ha * k * np.cosh(k * (t - y)) + Hb * k * np.cosh(k * y)) / np.sinh(k * t)
    J = -dH
    P_ac = np.trapezoid(0.5 * np.abs(J) ** 2 / sigma, y)
    Jdc = (Hb - Ha) / t
    P_dc = 0.5 * Jdc ** 2 / sigma * t
    return P_ac, P_dc


def dowell_fr(t, delta, m, porosity=1.0):
    """Dowell AC/DC ratio for m foil layers of thickness t (same expression as dabtools.dab.magnetics)."""
    x = t * math.sqrt(porosity) / delta
    if x < 1e-6:
        return 1.0
    sh, ch = math.sinh(2 * x), math.cosh(2 * x)
    s2, c2 = math.sin(2 * x), math.cos(2 * x)
    t1 = (sh + s2) / (ch - c2)
    t2 = (math.sinh(x) - math.sin(x)) / (math.cosh(x) + math.cos(x))
    return x * (t1 + 2 * (m ** 2 - 1) / 3 * t2)


def round_wire_factors(d, f, T=100.0):
    """
    Ferreira (1994) exact skin and proximity factors for a round conductor of diameter d.
    Returns (Fs, G) with Fs = R_skin / R_dc and G [Ohm] such that P_prox per unit length = G * He_pk^2.
    Checked against the low-frequency limit  G -> pi sigma w^2 mu0^2 a^4 / 8.
    """
    sigma = 1.0 / rho_cu(T)
    dl = skin_depth(f, T)
    xi = d / (math.sqrt(2) * dl)
    if xi < 1e-3:
        w = 2 * math.pi * f
        return 1.0, math.pi * sigma * w ** 2 * MU0 ** 2 * (d / 2) ** 4 / 8
    b0r, b0i, b1r, b1i = ber(xi), bei(xi), berp(xi), beip(xi)
    z = xi * np.exp(3j * math.pi / 4)
    v2 = jv(2, z)
    b2r, b2i = v2.real, v2.imag
    Fs = xi / 2 * (b0r * b1i - b0i * b1r) / (b1r ** 2 + b1i ** 2)
    G = -2 * math.pi * xi / sigma * (b2r * b1r + b2i * b1i) / (b0r ** 2 + b0i ** 2)
    return float(Fs), float(G)
