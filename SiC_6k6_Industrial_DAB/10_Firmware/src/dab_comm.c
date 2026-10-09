#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "dab_comm.h"

uint16_t dab_crc16(const uint8_t *p, int n)             /* CRC-16/CCITT-FALSE */
{
    uint16_t crc = 0xFFFF;
    for (int i = 0; i < n; i++) {
        crc ^= (uint16_t)p[i] << 8;
        for (int b = 0; b < 8; b++) crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
    }
    return crc;
}

int dab_comm_build_telemetry(char *buf, int buflen, const dab_ctrl_t *c, const dab_meas_t *m)
{
    int n = snprintf(buf, (size_t)buflen, "$T,%u,%d,%d,%d,%.1f,%.1f,%.2f,%.1f,%.0f,%.4f,%.3f,%.3f",
                     (unsigned)c->period_counter, (int)c->state, (int)c->fault, (int)c->mode,
                     m->v1, m->v2, m->i_pk, m->temp_c, c->p_cmd, c->cmd.phi, c->cmd.d1, c->cmd.d2);
    if (n < 0 || n >= buflen - 8) return -1;
    uint16_t crc = dab_crc16((const uint8_t *)buf, n);
    n += snprintf(buf + n, (size_t)(buflen - n), "*%04X\n", crc);
    return n;
}

/* Commands: "$C,EN,1" "$C,EN,0" "$C,MODE,CV,400.0" "$C,MODE,CP,-3000" "$C,CLR" */
int dab_comm_parse_command(const char *line, dab_ctrl_t *c)
{
    if (strncmp(line, "$C,", 3) != 0) return -1;
    const char *p = line + 3;
    if (strncmp(p, "EN,", 3) == 0) { dab_ctrl_set_enable(c, atoi(p + 3) != 0); return 0; }
    if (strncmp(p, "CLR", 3) == 0) { dab_ctrl_clear_fault(c); return 0; }
    if (strncmp(p, "MODE,CV,", 8) == 0) { float v = (float)atof(p + 8); if (v < 250.0f || v > 460.0f) return -2; dab_ctrl_set_mode(c, MODE_CV, v, 0.0f); return 0; }
    if (strncmp(p, "MODE,CP,", 8) == 0) { float w = (float)atof(p + 8); if (w < -7000.0f || w > 7000.0f) return -2; dab_ctrl_set_mode(c, MODE_CP, c->v2_ref, w); return 0; }
    return -1;
}
