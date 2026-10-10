#!/usr/bin/env python3
"""
Fault tree analysis (FTA) for the 6.6 kW SiC DAB - three top events, minimal cut sets computed by boolean expansion.

Top events
  TE1  hazardous voltage at an accessible part (control/SELV circuits, connectors, service port, chassis)
  TE2  uncontrolled energy transfer / overcurrent: a shoot-through or inductor over-current that is not interrupted within
       the device withstand time (~ us) by a fast path (DESAT / comparator / firmware); the fuse (ms) only limits the
       consequence and is treated as a separate consequence barrier (TE2b = TE2 AND fuse fails to clear)
  TE3  thermal runaway (junction temperature runs past the limit without a trip)

Basic-event failure rates are ORDER-OF-MAGNITUDE class values in the style of IEC TR 62380 / SN 29500 tables, entered
as ASSUMPTIONS (no manufacturer FIT data, no field data). Each event has a mode: 'detected' (revealed on occurrence,
MTTR 48 h), 'latent' (revealed only by a proof test, interval 8760 h -> mean unavailability lambda T / 2) or 'demand'
(a probability per demand, e.g. a human action). 'house' events are design switches (rev A: no DESAT driver).

Quantification (rare-event approximation):
  cut-set frequency  F_c = sum_i lambda_i * prod_{j != i} q_j     (one event occurs while the others are unavailable)
  cut-set unavailability Q_c = prod_j q_j
  top-event frequency F ~ sum_c F_c ; probability over mission time T_m: P ~ 1 - exp(-F T_m)
  Fussell-Vesely importance  I_FV(e) = sum_{c contains e} F_c / F
Outputs: results/fta_cutsets.json, fta_cutsets.md, fta_trees.md (Mermaid), fig_fta_cutsets.png, provenance_fta.json
"""
import os, json, time, hashlib, platform, itertools
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE)); DAB = os.path.join(REPO, "SiC_6k6_Industrial_DAB")
RES = os.path.join(HERE, "results"); os.makedirs(RES, exist_ok=True); T0 = time.time()
FIT = 1e-9; MTTR = 48.0; T_PROOF = 8760.0; T_MISSION = 10 * 8760.0

# ---- basic events: name -> (description, lambda [1/h], mode, source note) ------------------------------------------
BE = {
 # isolation barriers (reinforced: a single component failure is a single-point event)
 "ISO_DRV":   ("gate-driver isolation breakdown (8 x UCC21520, reinforced)", 8 * 0.5 * FIT, "detected", "class value for reinforced digital isolators, assumption"),
 "ISO_BIAS":  ("gate-bias DC-DC isolation breakdown (8 x R12P21503D, basic-class part - open item 15.1-4)", 8 * 1.0 * FIT, "detected", "assumption"),
 "ISO_AMC":   ("isolated amplifier / isolated 5 V supply breakdown (3 x AMC1301 + PS9/PS10)", (3 * 0.5 + 2 * 1.0) * FIT, "detected", "assumption"),
 "ISO_PCB":   ("PCB barrier tracking (contamination, 16 mm barrier, slots)", 0.5 * FIT, "detected", "assumption"),
 "DEV_PAD":   ("TO-247 insulating pad breakdown to the earthed heatsink (8 pads)", 8 * 0.5 * FIT, "latent", "assumption; revealed by hipot/PE test"),
 "PE_BOND":   ("PE bonding of heatsinks / chassis open (3 lugs, bonded through chassis)", 5 * FIT, "latent", "assumption; revealed by bonding test"),
 "BLEED":     ("bleeder chain open (HV or LV, 1.4 MOhm, SAF-04)", 2 * 0.2 * FIT, "latent", "film resistors, open mode"),
 "ACT_DIS":   ("external active discharge fails (system interface)", 10 * FIT, "latent", "assumption"),
 "ACCESS":    ("access to terminals within 5 min of de-energising, without voltage check (procedure violation)", 1e-3, "demand", "human-factor probability per access, assumption"),
 # overcurrent chain
 "DRV_HIGH":  ("gate-driver output stuck high / logic failure (8 channels)", 8 * 1.0 * FIT, "detected", "10 % of 10 FIT per driver"),
 "DRV_UVLO_LOSS": ("gate bias loss without UVLO action (partial-on)", 8 * 0.5 * FIT, "detected", "assumption"),
 "XTALK":     ("crosstalk false turn-on (design-margin event, see Active_Gate_Drive)", 5 * FIT, "detected", "placeholder; depends on the -3/-4 V bias decision"),
 "SW_PWM":    ("firmware/HAL PWM configuration error producing overlap (systematic)", 1e-4, "demand", "probability per release, assumption (no systematic-capability assessment)"),
 "MCU":       ("C2000 latch-up / runaway not caught by the watchdog", 50 * FIT * 0.1, "detected", "50 FIT, 90 % watchdog coverage assumed"),
 "CTRL_FAIL": ("control law demands excessive current (sensor gain fault, saturation, EPS limit error)", 20 * FIT, "detected", "aggregate of V1/V2 sensing failures, assumption"),
 "XFMR_SAT":  ("transformer / inductor saturation (DC bias, over-flux)", 5 * FIT, "detected", "assumption"),
 "LOAD_SHORT": ("external short at the LV or HV port", 100 * FIT, "detected", "system-level event, assumption"),
 "CMP_OC":    ("OC comparator (LM393) no-trip failure", 5 * FIT * 0.5, "latent", "stuck mode 50 %"),
 "CT_FAIL":   ("CT open / burden / rectifier failure (reads zero)", (1.0 + 0.2 + 2 * 0.5) * FIT, "latent", "no plausibility check in rev A (FMEA open item)"),
 "LOGIC_OR":  ("74HC32 / PROT_DIS wiring failure", 2 * FIT, "latent", "assumption"),
 "TZ_CFG":    ("EPWM trip-zone not armed (software/HAL)", 1e-4, "demand", "systematic, probability per release"),
 "FW_IPK":    ("firmware I_PK check fails (ADC path, MCU)", 10 * FIT, "detected", "shares the CT; independent only of the comparator"),
 "FUSE":      ("semiconductor fuse fails to clear within the coordinated I2t", 1 * FIT + 0.0, "latent", "assumption; plus coordination uncertainty"),
 "NO_DESAT":  ("rev A driver has no DESAT / short-circuit detection (house event)", 1.0, "house", "TRUE for UCC21520 rev A; FALSE with the UCC21710 upgrade"),
 # thermal
 "FAN":       ("fan failure (2 fans, either)", 2 * 15000 * FIT, "detected", "MTTF ~65 kh class, assumption; no tachometer in rev A"),
 "CLOG":      ("heatsink / filter clogging (airflow loss)", 500 * FIT, "latent", "environmental, assumption"),
 "TIM":       ("thermal-interface degradation (pad dry-out, pressure loss)", 100 * FIT, "latent", "assumption"),
 "AMB_HI":    ("ambient above 55 C in the cabinet", 1000 * FIT, "detected", "site-dependent, assumption"),
 "RDS_DEG":   ("device degradation raising losses (bond-wire fatigue, see SiC_Health_Monitoring)", 10 * FIT, "latent", "assumption"),
 "NTC":       ("heatsink NTC open / off the heatsink (reads cold)", 2 * 2 * FIT * 0.6, "latent", "open mode 60 %; no plausibility check"),
 "FW_OT":     ("firmware OT trip / derating not executed (ADC channel, MCU)", 10 * FIT, "detected", "assumption"),
 "HOST":      ("supervisory host does not act on the CAN temperature telemetry", 100 * FIT, "latent", "assumption"),
}

# ---- fault trees: gate name -> (type, [children]) ; children are gates or basic events -------------------------------
TREES = {
 "TE1_hazardous_voltage_accessible": ("OR", ["ISO_DRV", "ISO_BIAS", "ISO_AMC", "ISO_PCB", "G1_chassis_live", "G1_residual_energy"]),
 "G1_chassis_live":      ("AND", ["DEV_PAD", "PE_BOND"]),
 "G1_residual_energy":   ("AND", ["BLEED", "ACT_DIS", "ACCESS"]),
 "TE2_uncontrolled_energy_overcurrent": ("OR", ["G2_shoot_through", "G2_inductor_oc"]),
 "G2_shoot_through":     ("AND", ["G2_st_cause", "NO_DESAT"]),
 "G2_st_cause":          ("OR", ["DRV_HIGH", "DRV_UVLO_LOSS", "XTALK", "SW_PWM", "MCU"]),
 "G2_inductor_oc":       ("AND", ["G2_oc_cause", "G2_hw_oc_fail", "G2_fw_oc_fail"]),
 "TE2b_overcurrent_and_fuse_fails": ("AND", ["TE2_uncontrolled_energy_overcurrent", "FUSE"]),
 "G2_oc_cause":          ("OR", ["CTRL_FAIL", "XFMR_SAT", "LOAD_SHORT", "MCU"]),
 "G2_hw_oc_fail":        ("OR", ["CMP_OC", "CT_FAIL", "LOGIC_OR", "TZ_CFG"]),
 "G2_fw_oc_fail":        ("OR", ["FW_IPK", "CT_FAIL", "MCU"]),
 "TE3_thermal_runaway":  ("AND", ["G3_overheat_cause", "G3_protection_fail"]),
 "G3_overheat_cause":    ("OR", ["FAN", "CLOG", "TIM", "AMB_HI", "RDS_DEG"]),
 "G3_protection_fail":   ("AND", ["G3_local_fail", "HOST"]),
 "G3_local_fail":        ("OR", ["NTC", "FW_OT", "MCU"]),
}


def cut_sets(node):
    """Return the list of minimal cut sets (frozensets of basic events) of a gate by boolean expansion."""
    if node in BE:
        return [frozenset([node])]
    typ, ch = TREES[node]
    sets = [cut_sets(c) for c in ch]
    if typ == "OR":
        out = [s for lst in sets for s in lst]
    else:
        out = [frozenset().union(*combo) for combo in itertools.product(*sets)]
    return minimise(out)


def minimise(sets):
    sets = sorted(set(sets), key=len)
    out = []
    for s in sets:
        if not any(o <= s for o in out):
            out.append(s)
    return out


def rate_q(e):
    desc, lam, mode, _ = BE[e]
    if mode == "detected":  return lam, lam * MTTR
    if mode == "latent":    return lam, lam * T_PROOF / 2
    if mode == "demand":    return 0.0, lam
    if mode == "house":     return 0.0, lam
    raise ValueError(mode)


def quantify(cs):
    lam = {e: rate_q(e)[0] for e in cs}; q = {e: rate_q(e)[1] for e in cs}
    Q = float(np.prod([q[e] for e in cs]))
    F = 0.0
    for e in cs:
        if lam[e] > 0:
            F += lam[e] * float(np.prod([q[j] for j in cs if j != e]))
    return F, Q


def analyse(top, house_overrides=None):
    saved = {}
    for k, v in (house_overrides or {}).items():
        saved[k] = BE[k]; BE[k] = (v[0], v[1], v[2], v[3])
    cs = cut_sets(top)
    rows = []
    for c in cs:
        F, Q = quantify(c)
        rows.append(dict(cut_set=sorted(c), order=len(c), frequency_per_h=F, unavailability=Q))
    F_top = sum(r["frequency_per_h"] for r in rows)
    for r in rows: r["share"] = r["frequency_per_h"] / F_top if F_top > 0 else 0.0
    rows.sort(key=lambda r: -r["frequency_per_h"])
    fv = {}
    for r in rows:
        for e in r["cut_set"]: fv[e] = fv.get(e, 0.0) + r["share"]
    for k, v in saved.items(): BE[k] = v
    return dict(top=top, n_cut_sets=len(rows), min_order=min(r["order"] for r in rows), frequency_per_h=F_top, frequency_per_year=F_top * 8760,
                probability_10y=1 - np.exp(-F_top * T_MISSION), cut_sets=rows, fussell_vesely=dict(sorted(fv.items(), key=lambda kv: -kv[1])))


def mermaid(top):
    lines = ["```mermaid", "graph TD"]
    def walk(n):
        if n in BE:
            lines.append(f'  {n}(["{n}<br/>{BE[n][0][:48]}"])'); return
        typ, ch = TREES[n]
        lines.append(f'  {n}{{"{n} [{typ}]"}}')
        for c in ch:
            walk(c); lines.append(f"  {c} --> {n}")
    walk(top); lines.append("```"); return "\n".join(lines)


def main():
    results = {}
    md = ["# FTA results (generated by fta.py; all rates are assumptions, see README)\n"]
    for top in ("TE1_hazardous_voltage_accessible", "TE2_uncontrolled_energy_overcurrent", "TE2b_overcurrent_and_fuse_fails", "TE3_thermal_runaway"):
        r = analyse(top); results[top] = r
        md += [f"## {top}", f"minimal cut sets: {r['n_cut_sets']}, lowest order {r['min_order']}, top-event frequency {r['frequency_per_year']:.2e} /year, P(10 y) = {r['probability_10y']:.2e}\n",
               "| cut set | order | frequency (/year) | share |", "|---|---|---|---|"]
        for c in r["cut_sets"][:12]:
            md.append(f"| {' AND '.join(c['cut_set'])} | {c['order']} | {c['frequency_per_h']*8760:.2e} | {100*c['share']:.1f} % |")
        md += ["", "Fussell-Vesely importance (top 6): " + ", ".join(f"{k} {v:.2f}" for k, v in list(r["fussell_vesely"].items())[:6]), ""]
    # design variant: DESAT driver (house event false) for TE2
    r2b = analyse("TE2_uncontrolled_energy_overcurrent", house_overrides={"NO_DESAT": ("DESAT present (UCC21710 upgrade): residual 1 % non-coverage", 0.01, "house", "assumed DESAT coverage 99 %")})
    results["TE2_with_DESAT_driver"] = r2b
    md += ["## TE2 with the UCC21710 (DESAT) upgrade, DESAT coverage 99 % assumed", f"frequency {r2b['frequency_per_year']:.2e} /year (rev A: {results['TE2_uncontrolled_energy_overcurrent']['frequency_per_year']:.2e}), ratio {results['TE2_uncontrolled_energy_overcurrent']['frequency_per_year']/r2b['frequency_per_year']:.1f}", ""]
    # variant: CT plausibility check in firmware (CT_FAIL becomes detected)
    r2c = analyse("TE2_uncontrolled_energy_overcurrent", house_overrides={"CT_FAIL": (BE["CT_FAIL"][0] + " - with firmware plausibility check", BE["CT_FAIL"][1], "detected", "FMEA open item closed")})
    results["TE2_with_CT_plausibility"] = r2c
    r3b = analyse("TE3_thermal_runaway", house_overrides={"NTC": (BE["NTC"][0] + " - with plausibility check (NTC vs loss model)", BE["NTC"][1], "detected", "proposed diagnostic")})
    results["TE3_with_NTC_plausibility"] = r3b
    md += [f"## TE2 with a CT plausibility check: frequency {r2c['frequency_per_year']:.2e} /year", f"## TE3 with an NTC plausibility check: frequency {r3b['frequency_per_year']:.2e} /year (rev A: {results['TE3_thermal_runaway']['frequency_per_year']:.2e})", ""]
    open(os.path.join(RES, "fta_cutsets.md"), "w").write("\n".join(md) + "\n")
    open(os.path.join(RES, "fta_trees.md"), "w").write("# Fault trees (Mermaid, generated by fta.py)\n\n" + "\n\n".join(mermaid(t) for t in ("TE1_hazardous_voltage_accessible", "TE2_uncontrolled_energy_overcurrent", "TE3_thermal_runaway")) + "\n")
    results["basic_events"] = {k: dict(description=v[0], rate_or_prob=v[1], mode=v[2], note=v[3]) for k, v in BE.items()}
    results["parameters"] = dict(MTTR_h=MTTR, proof_test_h=T_PROOF, mission_h=T_MISSION)
    json.dump(results, open(os.path.join(RES, "fta_cutsets.json"), "w"), indent=1, default=float)
    fig, ax = plt.subplots(1, 3, figsize=(14, 4.2))
    for a, top in zip(ax, ("TE1_hazardous_voltage_accessible", "TE2_uncontrolled_energy_overcurrent", "TE3_thermal_runaway")):
        r = results[top]; cs = r["cut_sets"][:8]
        a.barh([" & ".join(c["cut_set"]) for c in cs][::-1], [c["frequency_per_h"] * 8760 for c in cs][::-1])
        a.set_xscale("log"); a.set_xlabel("cut-set frequency (/year)"); a.set_title(f"{top}\nF = {r['frequency_per_year']:.1e}/y", fontsize=9); a.tick_params(axis="y", labelsize=6.5)
    fig.suptitle("Minimal cut sets (assumed class failure rates - order of magnitude only)"); fig.tight_layout(); fig.savefig(os.path.join(RES, "fig_fta_cutsets.png"), dpi=130); plt.close(fig)
    print("\n".join(md))
    def hs(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
    head = open(os.path.join(REPO, ".git", "HEAD")).read().strip(); commit = head
    if head.startswith("ref:"):
        rp = os.path.join(REPO, ".git", head[5:]); commit = open(rp).read().strip() if os.path.exists(rp) else head
    json.dump(dict(script="fta.py", python=platform.python_version(), numpy=np.__version__, git_commit=commit, wall_time_s=round(time.time() - T0, 2), deterministic="no random numbers",
                   inputs={os.path.relpath(f, REPO): hs(f) for f in [os.path.join(DAB, "15_Safety_Reliability", "02_FMEA.csv"), os.path.join(DAB, "15_Safety_Reliability", "01_insulation_coordination.md")]}),
              open(os.path.join(RES, "provenance_fta.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
