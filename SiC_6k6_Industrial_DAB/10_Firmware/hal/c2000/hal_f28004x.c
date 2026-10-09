/* See hal_f28004x.h for status.  Driverlib calls follow the C2000Ware 5.x API. */
#include <math.h>
#include "hal_f28004x.h"
#ifdef __TMS320C28XX__
#include "driverlib.h"
#include "device.h"
#endif

#ifdef __TMS320C28XX__
static inline uint16_t rad_to_counts(float phi)
{
    /* TBPHS in counts of the full period (2*TBPRD counts up-down) */
    float c = phi / (2.0f * 3.14159265f) * (2.0f * HAL_TBPRD);
    if (c < 0) c += 2.0f * HAL_TBPRD;
    return (uint16_t)c;
}

void hal_init_pwm(float t_dead_s)
{
    uint16_t db = (uint16_t)(t_dead_s * HAL_TBCLK_HZ);
    const uint32_t base[4] = { EPWM1_BASE, EPWM2_BASE, EPWM3_BASE, EPWM4_BASE };
    SysCtl_disablePeripheral(SYSCTL_PERIPH_CLK_TBCLKSYNC);
    for (int i = 0; i < 4; i++) {
        EPWM_setTimeBasePeriod(base[i], HAL_TBPRD);
        EPWM_setTimeBaseCounterMode(base[i], EPWM_COUNTER_MODE_UP_DOWN);
        EPWM_setClockPrescaler(base[i], EPWM_CLOCK_DIVIDER_1, EPWM_HSCLOCK_DIVIDER_1);
        EPWM_setCounterCompareValue(base[i], EPWM_COUNTER_COMPARE_A, HAL_TBPRD / 2);
        EPWM_setActionQualifierAction(base[i], EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_HIGH, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPA);
        EPWM_setActionQualifierAction(base[i], EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_LOW, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPA);
        EPWM_setDeadBandDelayMode(base[i], EPWM_DB_RED, true); EPWM_setDeadBandDelayMode(base[i], EPWM_DB_FED, true);
        EPWM_setDeadBandDelayPolarity(base[i], EPWM_DB_FED, EPWM_DB_POLARITY_ACTIVE_LOW);
        EPWM_setRisingEdgeDelayCount(base[i], db); EPWM_setFallingEdgeDelayCount(base[i], db);
        EPWM_setPhaseShift(base[i], 0); EPWM_enablePhaseShiftLoad(base[i]);
        EPWM_setSyncOutPulseMode(base[i], EPWM_SYNC_OUT_PULSE_ON_COUNTER_ZERO);
    }
    EPWM_disablePhaseShiftLoad(EPWM1_BASE);                      /* master */
    EPWM_setPhaseShift(EPWM2_BASE, HAL_TBPRD);                    /* 180 deg */
    EPWM_setInterruptSource(EPWM1_BASE, EPWM_INT_TBCTR_ZERO); EPWM_enableInterrupt(EPWM1_BASE); EPWM_setInterruptEventCount(EPWM1_BASE, 1);
    EPWM_enableADCTrigger(EPWM1_BASE, EPWM_SOC_A); EPWM_setADCTriggerSource(EPWM1_BASE, EPWM_SOC_A, EPWM_SOC_TBCTR_ZERO);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_TBCLKSYNC);
}

void hal_pwm_apply(const dab_cmd_t *cmd)
{
    /* leg-shift implementation of the inner duty: leg B of a bridge shifted by D*180 deg */
    float phiA_legB = cmd->d1 * 3.14159265f;
    float phiB_legA = cmd->phi + (1.0f - cmd->d2) * 3.14159265f * 0.5f;   /* centre the LV pulse on phi */
    float phiB_legB = phiB_legA + cmd->d2 * 3.14159265f;
    EPWM_setPhaseShift(EPWM2_BASE, rad_to_counts(phiA_legB));
    EPWM_setPhaseShift(EPWM3_BASE, rad_to_counts(phiB_legA));
    EPWM_setPhaseShift(EPWM4_BASE, rad_to_counts(phiB_legB));
}

void hal_pwm_enable(bool en)
{
    const uint32_t base[4] = { EPWM1_BASE, EPWM2_BASE, EPWM3_BASE, EPWM4_BASE };
    for (int i = 0; i < 4; i++) {
        if (en) EPWM_clearTripZoneFlag(base[i], EPWM_TZ_FLAG_OST | EPWM_TZ_FLAG_CBC | EPWM_TZ_INTERRUPT);
        else    EPWM_forceTripZoneEvent(base[i], EPWM_TZ_FORCE_EVENT_OST);
    }
}

void hal_init_adc(void)
{
    /* ADCA: A0 V1 (AMC1311 output), A1 V2, A2 I_L (CT burden peak-hold), A3 NTC; 12-bit, SOC0..3 on EPWM1 SOCA */
    ADC_setPrescaler(ADCA_BASE, ADC_CLK_DIV_4_0); ADC_setMode(ADCA_BASE, ADC_RESOLUTION_12BIT, ADC_MODE_SINGLE_ENDED);
    ADC_enableConverter(ADCA_BASE);
    for (int ch = 0; ch < 4; ch++) ADC_setupSOC(ADCA_BASE, (ADC_SOCNumber)ch, ADC_TRIGGER_EPWM1_SOCA, (ADC_Channel)ch, 20);
}
void hal_adc_read(dab_meas_t *m)
{
    m->v1 = (float)ADC_readResult(ADCARESULT_BASE, ADC_SOC_NUMBER0) * (1000.0f / 4096.0f);   /* 0..1000 V scale (AMC1311, 2 V FS) */
    m->v2 = (float)ADC_readResult(ADCARESULT_BASE, ADC_SOC_NUMBER1) * (500.0f / 4096.0f);
    m->i_pk = (float)ADC_readResult(ADCARESULT_BASE, ADC_SOC_NUMBER2) * (40.0f / 4096.0f);
    m->temp_c = ntc_to_celsius(ADC_readResult(ADCARESULT_BASE, ADC_SOC_NUMBER3));
    m->precharge_ok = GPIO_readPin(PIN_PRECHARGE_OK);
    m->driver_fault = !GPIO_readPin(PIN_DRV_FLT_N);
    m->hw_trip = hal_trip_latched();
}
void hal_init_trip(void)
{
    /* TZ1 = OC comparator, TZ2 = driver FLT wired-OR, TZ3 = OV comparator: one-shot trip on all EPWMs */
    const uint32_t base[4] = { EPWM1_BASE, EPWM2_BASE, EPWM3_BASE, EPWM4_BASE };
    for (int i = 0; i < 4; i++) {
        EPWM_enableTripZoneSignals(base[i], EPWM_TZ_SIGNAL_OSHT1 | EPWM_TZ_SIGNAL_OSHT2 | EPWM_TZ_SIGNAL_OSHT3);
        EPWM_setTripZoneAction(base[i], EPWM_TZ_ACTION_EVENT_TZA, EPWM_TZ_ACTION_LOW);
        EPWM_setTripZoneAction(base[i], EPWM_TZ_ACTION_EVENT_TZB, EPWM_TZ_ACTION_LOW);
    }
}
bool hal_trip_latched(void) { return (EPWM_getTripZoneFlagStatus(EPWM1_BASE) & EPWM_TZ_FLAG_OST) != 0; }
void hal_trip_clear(void) { hal_pwm_enable(true); }
#else
/* host stubs so the file is at least syntax-checked by gcc */
void hal_init_pwm(float t_dead_s) { (void)t_dead_s; }
void hal_pwm_apply(const dab_cmd_t *cmd) { (void)cmd; }
void hal_pwm_enable(bool en) { (void)en; }
void hal_init_adc(void) {}
void hal_adc_read(dab_meas_t *m) { (void)m; }
void hal_init_trip(void) {}
bool hal_trip_latched(void) { return false; }
void hal_trip_clear(void) {}
#endif
void hal_init_clocks(void) {}
void hal_init_gpio(void) {}
void hal_init_can(void) {}
void hal_init_sci(void) {}
uint32_t hal_micros(void) { return 0; }
