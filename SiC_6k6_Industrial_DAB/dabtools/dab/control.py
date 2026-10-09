"""
Reference implementation (Python) of the digital DAB controller - the same algorithm as the C
control core in 10_Firmware/src/dab_control.c; the SIL test in 10_Firmware/sil compares both.

Structure (executes once per switching period, period k uses measurements of period k-1):
  1. measurement filtering (v1, v2, i_L peak / i2 average)
  2. mode: CV (voltage regulation of the LV port, forward) / CP (power command, either direction)
     / CC (current limit) with a state machine (INIT, PRECHARGE_WAIT, SOFTSTART, RUN, FAULT)
  3. feedforward: phi_ff = inverse SPS power equation for the requested power at the measured
     voltages (equation (4) of 03_Mathematical_Models)
  4. PI on the regulated quantity, output = power correction, anti-windup by clamping
  5. modulation: SPS, or TPS look-up (D1, D2) by voltage ratio d and power (table from
     04_Design_Calculations / 12_Optimization), phi limited to +/- phi_max
  6. protections: OV/UV/OC/OT -> FAULT (latched), cycle-by-cycle current limit is in hardware
"""
import math


class PI:
    def __init__(self, kp, ki, Ts, out_min, out_max):
        self.kp, self.ki, self.Ts, self.out_min, self.out_max = kp, ki, Ts, out_min, out_max
        self.integ = 0.0

    def step(self, err):
        u_p = self.kp * err
        u = u_p + self.integ
        if u > self.out_max:
            u = self.out_max
        elif u < self.out_min:
            u = self.out_min
        else:
            self.integ += self.ki * self.Ts * err          # integrate only when not saturated (clamping anti-windup)
        return u

    def reset(self, value=0.0):
        self.integ = value


class DABController:
    STATES = ("INIT", "PRECHARGE_WAIT", "SOFTSTART", "RUN", "FAULT")

    def __init__(self, L, n, fs, kp, ki, P_max=6600.0, phi_max=math.radians(60), v2_ref=400.0,
                 limits=None, tps_table=None, soft_start_s=0.05):
        self.L, self.n, self.fs, self.Ts = L, n, fs, 1 / fs
        self.pi = PI(kp, ki, self.Ts, -P_max, P_max)
        self.P_max, self.phi_max = P_max, phi_max
        self.v2_ref, self.P_ref, self.mode = v2_ref, 0.0, "CV"
        self.lim = limits or dict(v1_ov=900, v1_uv=600, v2_ov=480, v2_uv=250, i_pk=32, T_max=95)
        self.tps_table = tps_table
        self.state = "INIT"; self.fault = None; self.t_state = 0.0
        self.soft_start_s = soft_start_s
        self.phi, self.D1, self.D2 = 0.0, 1.0, 1.0
        self.ss_scale = 0.0
        self.v2_start = 0.0
        self.log = []
        self.D_min = 0.12
        self.phi_dead_comp = 0.0          # rad, set from t_dead: 2*pi*fs*t_dead*0.5 (edge-average); 0 = disabled
        self.use_eps = True

    # --- helpers ------------------------------------------------------------
    V2_FLOOR = 40.0        # V: below this the power command is interpreted as a current command at the floor voltage

    def phi_from_power(self, P, v1, v2):
        """
        Inverse of P = v1 n v2 phi (pi - phi) / (2 pi^2 fs L) written in the current form
        I2 = P / v2 = n v1 phi (pi - phi) / (2 pi^2 fs L), which stays defined for v2 -> 0.
        Includes first-order dead-time compensation (the dead time removes ~2 pi fs t_dead of
        effective phase on one edge per half period, see 05_Simulation spice results).
        """
        if v1 < 50:
            return 0.0
        I2 = P / max(v2, self.V2_FLOOR)
        Imax = self.n * v1 / (8 * self.fs * self.L)             # at phi = pi/2
        I2 = max(-0.98 * Imax, min(0.98 * Imax, I2))
        c = 2 * math.pi ** 2 * self.fs * self.L * abs(I2) / (self.n * v1)
        phi = (math.pi - math.sqrt(max(0.0, math.pi ** 2 - 4 * c))) / 2
        phi = phi + self.phi_dead_comp
        return math.copysign(min(phi, self.phi_max), I2)

    def eps_matching(self, v1, v2):
        """
        Voltage-matching extended phase shift: reduce the inner duty of the bridge with the
        higher voltage so that v1 D1 ~= n v2 D2.  Limits the inductor peak current when the
        ratio d is far from 1 (dead-bus start, battery at low state of charge).
        """
        d = self.n * v2 / max(v1, 1.0)
        if d < 1.0:
            return max(self.D_min, min(1.0, d)), 1.0
        return 1.0, max(self.D_min, min(1.0, 1.0 / d))

    def check_protection(self, m):
        L = self.lim
        if m["v1"] > L["v1_ov"]: return "V1_OV"
        if m["v2"] > L["v2_ov"]: return "V2_OV"
        if self.state == "RUN" and m["v1"] < L["v1_uv"]: return "V1_UV"
        if self.state == "RUN" and m["v2"] < L["v2_uv"]: return "V2_UV"
        if abs(m["i_pk"]) > L["i_pk"]: return "I_PK"
        if m.get("T", 25) > L["T_max"]: return "OT"
        if self.state != "INIT" and not m.get("comm_ok", True): return "COMM"
        return None

    # --- main ISR -----------------------------------------------------------
    def step(self, m, enable=True):
        """m: dict(v1, v2, i_pk, T, precharge_ok). Returns (phi, D1, D2)."""
        f = self.check_protection(m)
        if f and self.state != "FAULT":
            self.state, self.fault = "FAULT", f
        if self.state == "FAULT":
            self.phi = 0.0; self.pi.reset(); self.ss_scale = 0.0
            return 0.0, 1.0, 1.0
        if self.state == "INIT":
            if enable: self.state, self.t_state = "PRECHARGE_WAIT", 0.0
            return 0.0, 1.0, 1.0
        if self.state == "PRECHARGE_WAIT":
            if m.get("precharge_ok", True) and m["v1"] > self.lim["v1_uv"]:
                self.state, self.t_state, self.ss_scale = "SOFTSTART", 0.0, 0.0
                self.v2_start = m["v2"]                       # ramp from the precharged voltage, not from 0
                self.pi.reset()
            return 0.0, 1.0, 1.0
        if not enable:
            self.state = "INIT"; self.phi = 0.0; return 0.0, 1.0, 1.0
        self.t_state += self.Ts
        if self.state == "SOFTSTART":
            self.ss_scale = min(1.0, self.t_state / self.soft_start_s)
            if self.ss_scale >= 1.0: self.state = "RUN"
        scale = self.ss_scale if self.state == "SOFTSTART" else 1.0
        # --- regulation
        if self.mode == "CV":
            ref = self.v2_start + (self.v2_ref - self.v2_start) * scale if self.state == "SOFTSTART" else self.v2_ref
            err = ref - m["v2"]
            P_ff = 0.0                                   # (optional) load-current feedforward: m.get('i2',0)*m['v2']
            P_cmd = self.pi.step(err) + P_ff
        else:                                            # CP: power command, feedforward dominant, PI trims v2
            P_cmd = self.P_ref * scale
        P_cmd = max(-self.P_max, min(self.P_max, P_cmd))
        self.phi = self.phi_from_power(P_cmd, m["v1"], m["v2"])
        # --- modulation
        self.D1, self.D2 = 1.0, 1.0
        if self.use_eps:
            self.D1, self.D2 = self.eps_matching(m["v1"], m["v2"])
        if self.tps_table:
            d = self.n * m["v2"] / max(m["v1"], 1.0)
            self.D1, self.D2 = self.tps_table(d, P_cmd)
        self.log.append((self.state, P_cmd, self.phi))
        return self.phi, self.D1, self.D2
