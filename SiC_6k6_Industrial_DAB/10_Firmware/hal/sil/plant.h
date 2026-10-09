#ifndef PLANT_H
#define PLANT_H
typedef struct {
    double L, n, fs, C1, C2, V1_src, R1_src, Rload, Vbat, Rbat; int battery;
    double v1, v2, iL, t; int N_sub; double ipk; double R_s;
} plant_t;
void plant_init(plant_t *p, double v2_init);
void plant_run_period(plant_t *p, double phi, double d1, double d2, int gates);
#endif
