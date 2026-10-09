/*
 * Hardware abstraction for TMS320F280049C (LAUNCHXL-F280049C BoosterPack headers or custom board).
 * STATUS: written against the C2000Ware driverlib API names; NOT compiled or tested in this
 * environment (no TI toolchain available).  Pin numbers of the BoosterPack headers must be
 * verified against the LaunchPad user's guide before use (see 07_KiCad_Schematics/controller sheet).
 */
#ifndef HAL_F28004X_H
#define HAL_F28004X_H
#include <stdint.h>
#include <stdbool.h>
#include "../../src/dab_control.h"

/* PWM allocation (all EPWM modules at 100 MHz TBCLK, up-down count, TBPRD = 500 -> 100 kHz)
 *   EPWM1  HV bridge leg A (A = high side Q1, B = low side Q2), master time base, SYNCO
 *   EPWM2  HV bridge leg B (Q3/Q4), TBPHS = 180 deg (half period) relative to EPWM1
 *   EPWM3  LV bridge leg A (Q5/Q6), TBPHS = phi  (outer phase shift)
 *   EPWM4  LV bridge leg B (Q7/Q8), TBPHS = phi + 180 deg
 * Inner duty D1/D2 (EPS/DPS) is implemented by shifting leg B of a bridge by (1 - D) * 180 deg
 * instead of 180 deg (the leg-shift method), so each leg still runs at 50 % with the dead band
 * inserted by the EPWM dead-band submodule (DBRED/DBFED = t_dead).
 * Trip: TZ1 (hardware OC comparator), TZ2 (gate-driver FLT wired-OR), TZ3 (DC-link OV comparator),
 * plus CMPSS on the inductor current sense for cycle-by-cycle limiting.
 */
#define HAL_TBCLK_HZ        100000000UL
#define HAL_TBPRD           500u          /* 100 kHz up-down */

void hal_init_clocks(void);
void hal_init_gpio(void);
void hal_init_pwm(float t_dead_s);
void hal_init_adc(void);
void hal_init_trip(void);
void hal_init_can(void);
void hal_init_sci(void);
void hal_pwm_apply(const dab_cmd_t *cmd);        /* phi (rad), d1, d2 -> TBPHS/CMP registers */
void hal_pwm_enable(bool en);                    /* gate enable: TZ force-off vs run */
void hal_adc_read(dab_meas_t *m);                /* called in the ISR after the SOC conversions */
bool hal_trip_latched(void);
void hal_trip_clear(void);
uint32_t hal_micros(void);
#endif
