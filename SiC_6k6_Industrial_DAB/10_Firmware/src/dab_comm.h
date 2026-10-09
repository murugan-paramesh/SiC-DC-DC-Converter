/* Telemetry / command protocol (UART ASCII line protocol; CAN mapping in README). */
#ifndef DAB_COMM_H
#define DAB_COMM_H
#include <stdint.h>
#include "dab_control.h"
int  dab_comm_build_telemetry(char *buf, int buflen, const dab_ctrl_t *c, const dab_meas_t *m);
int  dab_comm_parse_command(const char *line, dab_ctrl_t *c);   /* returns 0 ok, -1 unknown, -2 bad arg */
uint16_t dab_crc16(const uint8_t *p, int n);
#endif
