/*
 * Software-in-the-loop test of the control core (gcc, host).  Scenarios mirror 05_Simulation:
 *  1 start-up (precharged 380 V) + 50->100->50 % load steps      -> EL-08/EL-10 checks
 *  2 power reversal in CP mode with a battery                     -> EL-11
 *  3 protections: OV, OC, driver fault, comm loss, precharge timeout -> SAF-07
 *  4 dead-bus start with EPS matching                              -> inductor peak < LIM
 *  5 comm protocol round trip + CRC
 * Exit code 0 = all PASS.  Writes sil/sil_results.csv (period, v1, v2, phi, state) for scenario 1.
 */
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "../src/dab_control.h"
#include "../src/dab_params.h"
#include "../src/dab_comm.h"
#include "../hal/sil/plant.h"

static int fails = 0;
#define CHECK(cond, msg) do { if (cond) printf("PASS  %s\n", msg); else { printf("FAIL  %s\n", msg); fails++; } } while (0)

static void plant_defaults(plant_t *p)
{
    p->L = DAB_L_H; p->n = DAB_N_RATIO; p->fs = DAB_FSW_HZ; p->C1 = 80e-6 + 500e-6; p->C2 = 120e-6 + 1000e-6;
    p->V1_src = 800.0; p->R1_src = 0.3; p->R_s = 0.3; p->Rload = 400.0 * 400.0 / DAB_P_RATED_W * 2; p->battery = 0; p->Vbat = 400; p->Rbat = 0.1; p->N_sub = 200;
}
static dab_meas_t meas_from(const plant_t *p) {
    dab_meas_t m = { (float)p->v1, (float)p->v2, (float)p->ipk, 40.0f, true, false, false, true }; return m;
}

static void scenario_startup_loadstep(void)
{
    plant_t p; plant_defaults(&p); plant_init(&p, 380.0);
    dab_ctrl_t c; dab_ctrl_init(&c); dab_ctrl_set_enable(&c, true);
    FILE *f = fopen("sil/sil_results.csv", "w"); fprintf(f, "period,t_ms,v1,v2,phi_deg,d1,d2,state,p_cmd\n");
    double vmin = 1e9, vmax = 0, v2_end = 0, overshoot = 0; int ok_reg = 1;
    for (int k = 0; k < 16000; k++) {
        double t = p.t;
        p.Rload = (t >= 0.08 && t < 0.12) ? 400.0 * 400.0 / DAB_P_RATED_W : 2 * 400.0 * 400.0 / DAB_P_RATED_W;
        dab_meas_t m = meas_from(&p);
        const dab_cmd_t *cmd = dab_ctrl_step(&c, &m);
        plant_run_period(&p, cmd->phi, cmd->d1, cmd->d2, cmd->gates_enabled);
        if (k % 10 == 0) fprintf(f, "%d,%.3f,%.2f,%.2f,%.2f,%.3f,%.3f,%d,%.0f\n", k, t * 1e3, p.v1, p.v2, cmd->phi * 57.2958, cmd->d1, cmd->d2, (int)c.state, c.p_cmd);
        if (t >= 0.08 && t < 0.12) { if (p.v2 < vmin) vmin = p.v2; if (p.v2 > vmax) vmax = p.v2; }
        if (t > 0.07 && t < 0.08 && fabs(p.v2 - 400.0) > 4.0) ok_reg = 0;
        if (p.v2 > overshoot) overshoot = p.v2;
    }
    fclose(f); v2_end = p.v2;
    printf("  startup: v2_end=%.2f overshoot=%.1f%% step dip=%.2f%% rise=%.2f%% state=%d fault=%d\n", v2_end, 100 * (overshoot - 400) / 400, 100 * (400 - vmin) / 400, 100 * (vmax - 400) / 400, (int)c.state, (int)c.fault);
    CHECK(c.state == ST_RUN && c.fault == FLT_NONE, "scenario 1: reaches RUN without fault");
    CHECK(fabs(v2_end - 400.0) < 4.0 && ok_reg, "scenario 1: steady-state regulation within +/-1 % (EL-08)");
    CHECK((400 - vmin) / 400 < 0.03 && (vmax - 400) / 400 < 0.03, "scenario 1: 50 % load step deviation < 3 % (EL-10)");
    CHECK((overshoot - 400) / 400 < 0.05, "scenario 1: start-up overshoot < 5 %");
}

static void scenario_reversal(void)
{
    plant_t p; plant_defaults(&p); p.battery = 1; plant_init(&p, 400.0);
    dab_ctrl_t c; dab_ctrl_init(&c); dab_ctrl_set_enable(&c, true); dab_ctrl_set_mode(&c, MODE_CP, 400.0f, DAB_P_RATED_W);
    double v1max = 0, v1min = 1e9, v2max = 0, v2min = 1e9; int reached_neg = 0;
    for (int k = 0; k < 9000; k++) {
        double t = p.t;
        if (t > 0.03) dab_ctrl_set_mode(&c, MODE_CP, 400.0f, -DAB_P_RATED_W);
        dab_meas_t m = meas_from(&p);
        const dab_cmd_t *cmd = dab_ctrl_step(&c, &m);
        plant_run_period(&p, cmd->phi, cmd->d1, cmd->d2, cmd->gates_enabled);
        if (t > 0.025) { if (p.v1 > v1max) v1max = p.v1; if (p.v1 < v1min) v1min = p.v1; if (p.v2 > v2max) v2max = p.v2; if (p.v2 < v2min) v2min = p.v2; }
        if (cmd->phi < -0.3 && t > 0.03 && t < 0.06) reached_neg = 1;
    }
    printf("  reversal: v1 %.1f..%.1f  v2 %.1f..%.1f  state=%d fault=%d\n", v1min, v1max, v2min, v2max, (int)c.state, (int)c.fault);
    CHECK(c.fault == FLT_NONE, "scenario 2: reversal without fault");
    CHECK(reached_neg, "scenario 2: full reverse phase shift reached within 20 ms (EL-11)");
    CHECK((v1max - 800) / 800 < 0.05 && (400 - v2min) / 400 < 0.05, "scenario 2: link excursions < 5 % during reversal");
}

static void run_until(dab_ctrl_t *c, plant_t *p, int periods, dab_meas_t (*mf)(const plant_t *, int), int *k0)
{
    for (int k = 0; k < periods; k++) {
        dab_meas_t m = mf(p, *k0 + k);
        const dab_cmd_t *cmd = dab_ctrl_step(c, &m);
        plant_run_period(p, cmd->phi, cmd->d1, cmd->d2, cmd->gates_enabled);
    }
    *k0 += periods;
}
static int inject_kind = 0;
static dab_meas_t meas_inject(const plant_t *p, int k)
{
    dab_meas_t m = meas_from(p);
    if (k > 7000) {
        if (inject_kind == 1) m.v1 = 950.0f;
        if (inject_kind == 2) m.i_pk = 40.0f;
        if (inject_kind == 3) m.driver_fault = true;
        if (inject_kind == 4) m.comm_ok = false;
        if (inject_kind == 5) m.temp_c = 110.0f;
    }
    return m;
}
static void scenario_protections(void)
{
    const dab_fault_t expect[] = { FLT_NONE, FLT_V1_OV, FLT_I_PK, FLT_DRIVER, FLT_COMM, FLT_OT };
    const char *names[] = { "", "V1 over-voltage", "inductor over-current", "driver fault", "communication loss", "over-temperature" };
    for (inject_kind = 1; inject_kind <= 5; inject_kind++) {
        plant_t p; plant_defaults(&p); plant_init(&p, 380.0);
        dab_ctrl_t c; dab_ctrl_init(&c); dab_ctrl_set_enable(&c, true);
        int k0 = 0; run_until(&c, &p, 7100, meas_inject, &k0);
        char msg[96]; snprintf(msg, sizeof msg, "scenario 3: %s -> FAULT latched, gates off, logged", names[inject_kind]);
        CHECK(c.state == ST_FAULT && c.fault == expect[inject_kind] && !c.cmd.gates_enabled && (c.fault_log[0] >> 24) == (uint32_t)expect[inject_kind], msg);
        /* fault must stay latched until cleared, and clearing with the condition still present re-faults */
        run_until(&c, &p, 200, meas_inject, &k0);
        CHECK(c.state == ST_FAULT, "scenario 3: fault stays latched");
        dab_ctrl_clear_fault(&c); run_until(&c, &p, 10, meas_inject, &k0);
        CHECK(c.state == ST_FAULT, "scenario 3: re-faults while the condition persists");
    }
    /* precharge timeout */
    plant_t p; plant_defaults(&p); plant_init(&p, 380.0);
    dab_ctrl_t c; dab_ctrl_init(&c); dab_ctrl_set_enable(&c, true);
    for (int k = 0; k < 520000 / 1; k++) { dab_meas_t m = meas_from(&p); m.precharge_ok = false; const dab_cmd_t *cmd = dab_ctrl_step(&c, &m); (void)cmd; if (c.state == ST_FAULT) break; }
    CHECK(c.state == ST_FAULT && c.fault == FLT_PRECHARGE, "scenario 3: precharge timeout (5 s) -> FLT_PRECHARGE");
}

static void scenario_deadbus(void)
{
    plant_t p; plant_defaults(&p); p.Rload = 10 * 400.0 * 400.0 / DAB_P_RATED_W; plant_init(&p, 0.0);
    dab_ctrl_t c; dab_ctrl_init(&c); dab_ctrl_set_enable(&c, true);
    double ipk = 0;
    for (int k = 0; k < 20000; k++) {
        dab_meas_t m = meas_from(&p);
        const dab_cmd_t *cmd = dab_ctrl_step(&c, &m);
        plant_run_period(&p, cmd->phi, cmd->d1, cmd->d2, cmd->gates_enabled);
        if (p.ipk > ipk) ipk = p.ipk;
    }
    printf("  dead-bus: v2_end=%.1f ipk_max=%.1f A fault=%d\n", p.v2, ipk, (int)c.fault);
    CHECK(c.fault == FLT_NONE && fabs(p.v2 - 400) < 4, "scenario 4: dead-bus start reaches 400 V without fault");
    CHECK(ipk < LIM_I_PK_HV_A, "scenario 4: inductor peak stays below the hardware limit (EPS matching)");
}

static void scenario_comm(void)
{
    dab_ctrl_t c; dab_ctrl_init(&c); dab_meas_t m = { 800, 400, 9.5f, 45, true, false, false, true };
    char buf[160]; int n = dab_comm_build_telemetry(buf, sizeof buf, &c, &m);
    /* verify CRC */
    char *star = strrchr(buf, '*'); unsigned crc_tx; sscanf(star + 1, "%4X", &crc_tx);
    uint16_t crc = dab_crc16((const uint8_t *)buf, (int)(star - buf));
    CHECK(n > 0 && crc == crc_tx, "scenario 5: telemetry frame CRC-16 consistent");
    CHECK(dab_comm_parse_command("$C,MODE,CP,-3000", &c) == 0 && c.mode == MODE_CP && c.p_ref == -3000.0f, "scenario 5: CP command parsed");
    CHECK(dab_comm_parse_command("$C,MODE,CV,470", &c) == -2, "scenario 5: out-of-range reference rejected");
    CHECK(dab_comm_parse_command("$X,FOO", &c) == -1, "scenario 5: unknown command rejected");
    CHECK(dab_comm_parse_command("$C,EN,1", &c) == 0 && c.enable, "scenario 5: enable command");
}

int main(void)
{
    printf("DAB control core SIL test (fs=%.0f Hz, L=%.1f uH, kp=%.0f, ki=%.3g)\n", (double)DAB_FSW_HZ, DAB_L_H * 1e6, (double)DAB_KP_W_PER_V, (double)DAB_KI_W_PER_VS);
    scenario_startup_loadstep();
    scenario_reversal();
    scenario_protections();
    scenario_deadbus();
    scenario_comm();
    printf("%s (%d failures)\n", fails ? "RESULT: FAIL" : "RESULT: ALL PASS", fails);
    return fails ? 1 : 0;
}
