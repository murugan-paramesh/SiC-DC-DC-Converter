/* C implementation of the switched plant used in 05_Simulation (same equations). */
#include <math.h>
#include "plant.h"
#define TWO_PI 6.283185307179586
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
static double three(double th, double D, double shift)
{
    double x = fmod(th - shift + 4 * TWO_PI, TWO_PI), h = D * M_PI / 2;
    if (x > M_PI / 2 - h && x <= M_PI / 2 + h) return 1.0;
    if (x > 3 * M_PI / 2 - h && x <= 3 * M_PI / 2 + h) return -1.0;
    return 0.0;
}
void plant_init(plant_t *p, double v2_init) { p->v1 = p->V1_src; p->v2 = v2_init; p->iL = 0; p->t = 0; p->ipk = 0; }
void plant_run_period(plant_t *p, double phi, double d1, double d2, int gates)
{
    double Ts = 1.0 / p->fs, dt = Ts / p->N_sub; p->ipk = 0;
    for (int k = 0; k < p->N_sub; k++) {
        double th = (k + 0.5) / p->N_sub * TWO_PI;
        double s1 = gates ? three(th, d1, 0.0) : 0.0, s2 = gates ? three(th, d2, phi) : 0.0;
        double va = s1 * p->v1, vb = s2 * p->n * p->v2;
        p->iL += (va - vb - p->R_s * p->iL) / p->L * dt;
        double i_br1 = p->iL * s1, i_src = (p->V1_src - p->v1) / p->R1_src;
        p->v1 += (i_src - i_br1) / p->C1 * dt;
        double i_br2 = p->iL * s2 * p->n;
        double i_load = p->battery ? (p->v2 - p->Vbat) / p->Rbat : p->v2 / p->Rload;
        p->v2 += (i_br2 - i_load) / p->C2 * dt;
        if (fabs(p->iL) > p->ipk) p->ipk = fabs(p->iL);
        p->t += dt;
    }
}
