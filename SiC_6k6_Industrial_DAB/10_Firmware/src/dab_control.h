/*
 * DAB digital control core - portable C (no MCU dependencies).
 * Executed once per switching period from the PWM ISR (C2000) or from the SIL harness.
 * Algorithm identical to tools/dab/control.py (reference implementation).
 */
#ifndef DAB_CONTROL_H
#define DAB_CONTROL_H
#include <stdint.h>
#include <stdbool.h>

typedef enum { ST_INIT = 0, ST_PRECHARGE_WAIT, ST_SOFTSTART, ST_RUN, ST_FAULT } dab_state_t;
typedef enum { FLT_NONE = 0, FLT_V1_OV, FLT_V1_UV, FLT_V2_OV, FLT_V2_UV, FLT_I_PK, FLT_OT, FLT_DRIVER, FLT_HW_TRIP, FLT_COMM, FLT_PRECHARGE } dab_fault_t;
typedef enum { MODE_CV = 0, MODE_CP } dab_mode_t;

typedef struct {
    float v1, v2;        /* link voltages (V) */
    float i_pk;          /* inductor peak current of the last period, HV side (A, magnitude) */
    float temp_c;        /* hottest heatsink NTC (C) */
    bool  precharge_ok;  /* external precharge contactor feedback */
    bool  driver_fault;  /* any gate-driver FLT pin active (DESAT/UVLO) */
    bool  hw_trip;       /* hardware comparator trip latched (OC/OV) */
    bool  comm_ok;       /* supervisory heartbeat alive */
} dab_meas_t;

typedef struct {
    float phi;           /* outer phase shift (rad), >0 power HV->LV */
    float d1, d2;        /* inner duty ratios (0..1) */
    bool  gates_enabled; /* false = all gates off */
} dab_cmd_t;

typedef struct {
    float kp, ki, ts, out_min, out_max, integ;
} dab_pi_t;

typedef struct {
    dab_state_t state;
    dab_fault_t fault;
    dab_mode_t  mode;
    float v2_ref, p_ref, p_cmd, p_cmd_slewed;
    float t_state;
    float ss_scale;
    float v2_start;      /* LV voltage at soft-start entry */
    bool  enable;
    dab_pi_t pi;
    dab_cmd_t cmd;
    uint32_t fault_log[8];   /* ring of (fault<<24 | period counter & 0xFFFFFF) */
    uint8_t  fault_log_idx;
    uint32_t period_counter;
} dab_ctrl_t;

void  dab_ctrl_init(dab_ctrl_t *c);
void  dab_ctrl_set_enable(dab_ctrl_t *c, bool en);
void  dab_ctrl_set_mode(dab_ctrl_t *c, dab_mode_t m, float v2_ref, float p_ref);
void  dab_ctrl_clear_fault(dab_ctrl_t *c);
const dab_cmd_t *dab_ctrl_step(dab_ctrl_t *c, const dab_meas_t *m);
float dab_phi_from_power(float p, float v1, float v2);
void  dab_eps_matching(float v1, float v2, float *d1, float *d2);
float dab_pi_step(dab_pi_t *pi, float err);
#endif
