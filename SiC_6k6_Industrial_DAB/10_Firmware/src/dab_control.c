#include <math.h>
#include "dab_control.h"
#include "dab_params.h"

#define PI_F 3.14159265358979f

float dab_pi_step(dab_pi_t *pi, float err)
{
    float u = pi->kp * err + pi->integ;
    if (u > pi->out_max) u = pi->out_max;
    else if (u < pi->out_min) u = pi->out_min;
    else pi->integ += pi->ki * pi->ts * err;      /* clamping anti-windup */
    return u;
}

/* Inverse SPS power equation in current form: I2 = n V1 phi (pi - phi) / (2 pi^2 fs L) */
float dab_phi_from_power(float p, float v1, float v2)
{
    if (v1 < 50.0f) return 0.0f;
    float v2f = v2 > DAB_V2_FLOOR_V ? v2 : DAB_V2_FLOOR_V;
    float i2 = p / v2f;
    float imax = DAB_N_RATIO * v1 / (8.0f * DAB_FSW_HZ * DAB_L_H);
    if (i2 > 0.98f * imax) i2 = 0.98f * imax;
    if (i2 < -0.98f * imax) i2 = -0.98f * imax;
    float c = 2.0f * PI_F * PI_F * DAB_FSW_HZ * DAB_L_H * fabsf(i2) / (DAB_N_RATIO * v1);
    float disc = PI_F * PI_F - 4.0f * c;
    if (disc < 0.0f) disc = 0.0f;
    float phi = (PI_F - sqrtf(disc)) * 0.5f + DAB_PHI_DEAD_COMP;
    if (phi > DAB_PHI_MAX_RAD) phi = DAB_PHI_MAX_RAD;
    return i2 >= 0.0f ? phi : -phi;
}

void dab_eps_matching(float v1, float v2, float *d1, float *d2)
{
    float d = DAB_N_RATIO * v2 / (v1 > 1.0f ? v1 : 1.0f);
    *d1 = 1.0f; *d2 = 1.0f;
    if (d < 1.0f) { *d1 = d < DAB_D_MIN ? DAB_D_MIN : d; }
    else          { float x = 1.0f / d; *d2 = x < DAB_D_MIN ? DAB_D_MIN : x; }
}

static void log_fault(dab_ctrl_t *c, dab_fault_t f)
{
    c->fault_log[c->fault_log_idx & 7u] = ((uint32_t)f << 24) | (c->period_counter & 0xFFFFFFu);
    c->fault_log_idx++;
}

static dab_fault_t check_protection(const dab_ctrl_t *c, const dab_meas_t *m)
{
    if (m->hw_trip) return FLT_HW_TRIP;
    if (m->driver_fault) return FLT_DRIVER;
    if (m->v1 > LIM_V1_OV_V) return FLT_V1_OV;
    if (m->v2 > LIM_V2_OV_V) return FLT_V2_OV;
    if (c->state == ST_RUN && m->v1 < LIM_V1_UV_V) return FLT_V1_UV;
    if (c->state == ST_RUN && m->v2 < LIM_V2_UV_V) return FLT_V2_UV;
    if (fabsf(m->i_pk) > LIM_I_PK_HV_A) return FLT_I_PK;
    if (m->temp_c > LIM_T_MAX_C) return FLT_OT;
    if (c->state != ST_INIT && !m->comm_ok) return FLT_COMM;
    return FLT_NONE;
}

void dab_ctrl_init(dab_ctrl_t *c)
{
    c->state = ST_INIT; c->fault = FLT_NONE; c->mode = MODE_CV;
    c->v2_ref = DAB_V2_REF_V; c->p_ref = 0.0f; c->p_cmd = 0.0f; c->p_cmd_slewed = 0.0f;
    c->t_state = 0.0f; c->ss_scale = 0.0f; c->enable = false; c->v2_start = 0.0f;
    c->pi.kp = DAB_KP_W_PER_V; c->pi.ki = DAB_KI_W_PER_VS; c->pi.ts = DAB_TS_S;
    c->pi.out_min = -DAB_P_MAX_W; c->pi.out_max = DAB_P_MAX_W; c->pi.integ = 0.0f;
    c->cmd.phi = 0.0f; c->cmd.d1 = 1.0f; c->cmd.d2 = 1.0f; c->cmd.gates_enabled = false;
    for (int i = 0; i < 8; i++) c->fault_log[i] = 0;
    c->fault_log_idx = 0; c->period_counter = 0;
}

void dab_ctrl_set_enable(dab_ctrl_t *c, bool en) { c->enable = en; }
void dab_ctrl_set_mode(dab_ctrl_t *c, dab_mode_t m, float v2_ref, float p_ref) { c->mode = m; c->v2_ref = v2_ref; c->p_ref = p_ref; }
void dab_ctrl_clear_fault(dab_ctrl_t *c) { if (c->state == ST_FAULT) { c->state = ST_INIT; c->fault = FLT_NONE; } }

static void gates_off(dab_ctrl_t *c)
{
    c->cmd.phi = 0.0f; c->cmd.d1 = 1.0f; c->cmd.d2 = 1.0f; c->cmd.gates_enabled = false;
    c->pi.integ = 0.0f; c->p_cmd_slewed = 0.0f; c->ss_scale = 0.0f;
}

const dab_cmd_t *dab_ctrl_step(dab_ctrl_t *c, const dab_meas_t *m)
{
    c->period_counter++;
    dab_fault_t f = check_protection(c, m);
    if (f != FLT_NONE && c->state != ST_FAULT) { c->state = ST_FAULT; c->fault = f; log_fault(c, f); }
    switch (c->state) {
    case ST_FAULT:
        gates_off(c); return &c->cmd;
    case ST_INIT:
        gates_off(c);
        if (c->enable) { c->state = ST_PRECHARGE_WAIT; c->t_state = 0.0f; }
        return &c->cmd;
    case ST_PRECHARGE_WAIT:
        gates_off(c);
        c->t_state += DAB_TS_S;
        if (!c->enable) { c->state = ST_INIT; return &c->cmd; }
        if (m->precharge_ok && m->v1 > LIM_V1_UV_V) { c->state = ST_SOFTSTART; c->t_state = 0.0f; c->ss_scale = 0.0f; c->pi.integ = 0.0f; c->v2_start = m->v2; }
        else if (c->t_state > 5.0f) { c->state = ST_FAULT; c->fault = FLT_PRECHARGE; log_fault(c, FLT_PRECHARGE); }
        return &c->cmd;
    default: break;
    }
    if (!c->enable) { c->state = ST_INIT; gates_off(c); return &c->cmd; }
    c->t_state += DAB_TS_S;
    float scale = 1.0f;
    if (c->state == ST_SOFTSTART) {
        c->ss_scale = c->t_state / DAB_SOFT_START_S;
        if (c->ss_scale >= 1.0f) { c->ss_scale = 1.0f; c->state = ST_RUN; }
        scale = c->ss_scale;
    }
    /* regulation */
    float p_cmd;
    if (c->mode == MODE_CV) {
        float ref = (c->state == ST_SOFTSTART) ? c->v2_start + (c->v2_ref - c->v2_start) * scale : c->v2_ref;
        p_cmd = dab_pi_step(&c->pi, ref - m->v2);
    } else {
        p_cmd = c->p_ref * scale;
    }
    if (p_cmd > DAB_P_MAX_W) p_cmd = DAB_P_MAX_W;
    if (p_cmd < -DAB_P_MAX_W) p_cmd = -DAB_P_MAX_W;
    /* reference slew limit (CP mode and reversal) */
    float dmax = DAB_SLEW_W_PER_S * DAB_TS_S;
    if (c->mode == MODE_CP) {
        if (p_cmd > c->p_cmd_slewed + dmax) p_cmd = c->p_cmd_slewed + dmax;
        if (p_cmd < c->p_cmd_slewed - dmax) p_cmd = c->p_cmd_slewed - dmax;
    }
    c->p_cmd_slewed = p_cmd; c->p_cmd = p_cmd;
    /* modulation */
    c->cmd.phi = dab_phi_from_power(p_cmd, m->v1, m->v2);
    dab_eps_matching(m->v1, m->v2, &c->cmd.d1, &c->cmd.d2);
    c->cmd.gates_enabled = true;
    return &c->cmd;
}
