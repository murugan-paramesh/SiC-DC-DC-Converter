/*
 * Conformance harness: drives the UNMODIFIED firmware control core (10_Firmware/src/dab_control.c) through every
 * (state, abstract input) combination enumerated by state_machine_check.py and prints the resulting state and gate
 * enable, one line per combination:  state_in,mask,clear,state_out,gates
 * Build (from state_machine_check.py):  gcc -O1 -std=c11 -I<fw>/src sm_conformance.c <fw>/src/dab_control.c -lm
 * Abstract input bits (mask): 0 enable, 1 precharge_ok, 2 v1_low, 3 v2_low, 4 v1_ov, 5 v2_ov, 6 ipk_over, 7 ot,
 *                             8 driver_fault, 9 hw_trip, 10 comm_lost, 11 ss_done, 12 pc_timeout
 * Timers are abstracted by setting t_state directly (the struct is public), see state_machine_check.py.
 */
#include <stdio.h>
#include <stdlib.h>
#include "dab_control.h"
#include "dab_params.h"

int main(void)
{
    for (int s = 0; s < 5; s++) {
        for (int clear = 0; clear < 2; clear++) {
            for (unsigned mask = 0; mask < (1u << 13); mask++) {
                int enable = mask & 1, pc_ok = (mask >> 1) & 1, v1_low = (mask >> 2) & 1, v2_low = (mask >> 3) & 1, v1_ov = (mask >> 4) & 1,
                    v2_ov = (mask >> 5) & 1, ipk = (mask >> 6) & 1, ot = (mask >> 7) & 1, drv = (mask >> 8) & 1, hw = (mask >> 9) & 1,
                    comm_lost = (mask >> 10) & 1, ss_done = (mask >> 11) & 1, pc_to = (mask >> 12) & 1;
                if ((v1_low && v1_ov) || (v2_low && v2_ov)) continue;      /* physically inconsistent */
                dab_ctrl_t c; dab_ctrl_init(&c);
                c.state = (dab_state_t)s; c.enable = enable != 0;
                if (s == ST_FAULT) c.fault = FLT_V1_OV;
                c.t_state = 0.0f;
                if (s == ST_SOFTSTART && ss_done) c.t_state = DAB_SOFT_START_S;            /* + Ts in the step -> ss_scale >= 1 */
                if (s == ST_PRECHARGE_WAIT && pc_to) c.t_state = 5.0f;                      /* + Ts -> > 5 s */
                dab_meas_t m;
                m.v1 = v1_ov ? 950.0f : (v1_low ? 500.0f : 800.0f);
                m.v2 = v2_ov ? 500.0f : (v2_low ? 200.0f : 400.0f);
                m.i_pk = ipk ? 40.0f : 10.0f; m.temp_c = ot ? 110.0f : 40.0f;
                m.precharge_ok = pc_ok != 0; m.driver_fault = drv != 0; m.hw_trip = hw != 0; m.comm_ok = comm_lost == 0;
                if (clear) dab_ctrl_clear_fault(&c);                                        /* asynchronous command before the ISR step */
                const dab_cmd_t *cmd = dab_ctrl_step(&c, &m);
                printf("%d,%u,%d,%d,%d\n", s, mask, clear, (int)c.state, cmd->gates_enabled ? 1 : 0);
            }
        }
    }
    return 0;
}
