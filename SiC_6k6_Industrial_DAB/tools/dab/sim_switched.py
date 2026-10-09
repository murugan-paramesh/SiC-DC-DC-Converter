"""
Switched-model simulation of the DAB with a digital controller in the loop.

Plant: ideal bridges (dead time optional), series inductance L, ideal transformer n, DC-link
capacitors C1/C2 with ESR, HV port = voltage source with series resistance (stiff bus), LV port
= capacitor + load (resistor / current sink / battery with R_int).  Integration: fixed step,
dt = Ts / N_sub.  The controller (tools/dab/control.py) runs once per switching period, like
the C2000 ISR, and sets the phase shift (and D1/D2) for the next period -> one-period delay.
"""
import math
import numpy as np


class DABPlant:
    def __init__(self, L, n, fs, C1, C2, V1_src, R1_src, load, dead_time=0.0, N_sub=200):
        self.L, self.n, self.fs, self.C1, self.C2 = L, n, fs, C1, C2
        self.V1_src, self.R1_src = V1_src, R1_src
        self.load = load                       # callable(v2, t) -> load current drawn from the LV link (A, >0 = sink)
        self.N_sub = N_sub
        self.Ts = 1 / fs; self.dt = self.Ts / N_sub
        self.v1 = V1_src; self.v2 = 0.0; self.iL = 0.0
        self.t = 0.0
        self.dead = dead_time

    def period_voltages(self, phi, D1, D2):
        """Bridge voltages over one period for the commanded (phi, D1, D2); returns arrays (N_sub)."""
        th = (np.arange(self.N_sub) + 0.5) / self.N_sub * 2 * math.pi
        def three(amp, D, shift):
            x = (th - shift) % (2 * math.pi); h = D * math.pi / 2
            v = np.zeros_like(x)
            v[(x > math.pi / 2 - h) & (x <= math.pi / 2 + h)] = amp
            v[(x > 3 * math.pi / 2 - h) & (x <= 3 * math.pi / 2 + h)] = -amp
            return v
        return three(1.0, D1, 0.0), three(1.0, D2, phi)

    def run_period(self, phi, D1=1.0, D2=1.0, record=False):
        s1, s2 = self.period_voltages(phi, D1, D2)
        rec = [] if record else None
        for k in range(self.N_sub):
            va = s1[k] * self.v1                      # HV bridge voltage (uses the actual link voltage)
            vb = s2[k] * self.n * self.v2             # LV bridge voltage referred to HV side
            self.iL += (va - vb) / self.L * self.dt
            # HV link: source through R1_src, bridge draws iL*s1
            i_br1 = self.iL * s1[k]
            i_src = (self.V1_src - self.v1) / self.R1_src
            self.v1 += (i_src - i_br1) / self.C1 * self.dt
            # LV link: bridge delivers iL*s2*n, load draws load(v2)
            i_br2 = self.iL * s2[k] * self.n
            self.v2 += (i_br2 - self.load(self.v2, self.t)) / self.C2 * self.dt
            self.t += self.dt
            if record:
                rec.append((self.t, va, vb, self.iL, self.v1, self.v2, i_br1, i_br2))
        return rec

    def state(self):
        return dict(v1=self.v1, v2=self.v2, iL=self.iL, t=self.t)
