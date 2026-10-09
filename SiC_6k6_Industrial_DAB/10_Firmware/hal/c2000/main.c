/* Target application skeleton (F280049C).  NOT compiled here - see README. */
#include "hal_f28004x.h"
#include "../../src/dab_control.h"
#include "../../src/dab_params.h"
#include "../../src/dab_comm.h"
static dab_ctrl_t g_ctrl; static dab_meas_t g_meas; static volatile uint32_t g_isr_count;
static char g_tx[160];

/* 100 kHz ISR: EPWM1 counter-zero -> ADC SOC -> this handler at end of conversion */
void epwm1_isr(void)
{
    hal_adc_read(&g_meas);
    g_meas.comm_ok = true;                    /* set false by the CAN heartbeat watchdog in main loop */
    const dab_cmd_t *cmd = dab_ctrl_step(&g_ctrl, &g_meas);
    hal_pwm_apply(cmd);
    hal_pwm_enable(cmd->gates_enabled);
    g_isr_count++;
}

int main(void)
{
    hal_init_clocks(); hal_init_gpio(); hal_init_pwm(DAB_T_DEAD_S); hal_init_adc(); hal_init_trip(); hal_init_can(); hal_init_sci();
    dab_ctrl_init(&g_ctrl);
    uint32_t last_tx = 0;
    for (;;) {
        if (g_isr_count - last_tx >= 10000u) {          /* 10 Hz telemetry */
            last_tx = g_isr_count;
            dab_comm_build_telemetry(g_tx, sizeof g_tx, &g_ctrl, &g_meas);
            /* sci_write(g_tx); can_send_status(&g_ctrl, &g_meas); */
        }
        /* poll command queue: dab_comm_parse_command(line, &g_ctrl); */
    }
}
