#!/usr/bin/env python3
"""
FMEDA-lite for the protection functions of the DAB (rev A schematic: UCC21520 drivers without DESAT, LM393 comparators,
AMC1301 sensing, CT 1:100, heatsink NTCs, PC817 interlock inputs, C2000 F280049C trip zones).

For each protection function the components in its chain are listed with their failure modes, a failure-rate share, the
effect on the function and the classification
    S  = safe (spurious trip / safe state),  DD = dangerous detected (a diagnostic reveals it before a demand),
    DU = dangerous undetected (revealed only by a demand or a proof test).
Diagnostic coverage DC = lambda_DD / (lambda_DD + lambda_DU);  safe failure fraction SFF = (lambda_S + lambda_DD) / lambda_total.
Rates are CLASS VALUES (IEC TR 62380 / SN 29500 order of magnitude), ASSUMPTIONS; mode splits are engineering judgement.
NO SIL claim, no PFD/PFH target: a SIL assignment needs certified data, a systematic-capability assessment and an
independent assessor; this table only ranks where diagnostics are missing.
Outputs: results/fmeda_lite.csv, fmeda_lite.md, fmeda_summary.json, provenance_fmeda.json
"""
import os, json, time, hashlib, platform, csv
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE)); DAB = os.path.join(REPO, "SiC_6k6_Industrial_DAB")
RES = os.path.join(HERE, "results"); os.makedirs(RES, exist_ok=True); T0 = time.time()

# function, component, lambda_total_FIT (class value), failure mode, share, effect, class, diagnostic / justification
ROWS = [
 # ---- HV over-voltage (hardware comparator TZ3 + firmware FLT_V1_OV at 900 V; AMC1301 chain shared by both!) ----
 ("OV_HV", "divider R129/R130 (5 x 1M)", 1.0, "open", 0.9, "V1 reads ~0: no OV trip; firmware V1_UV in RUN trips", "DD", "UV window in RUN reveals a dead channel (not in PRECHARGE_WAIT)"),
 ("OV_HV", "divider R129/R130 (5 x 1M)", 1.0, "drift > 5 %", 0.1, "OV threshold shifted; no diagnostic", "DU", "no reference check"),
 ("OV_HV", "AMC1301 U5", 10.0, "fail low / output stuck", 0.4, "no OV trip (both HW and FW use the same channel)", "DD", "UV window in RUN"),
 ("OV_HV", "AMC1301 U5", 10.0, "fail high", 0.3, "spurious OV trip", "S", "-"),
 ("OV_HV", "AMC1301 U5", 10.0, "gain drift", 0.3, "threshold shifted", "DU", "no plausibility vs the LV side / power model"),
 ("OV_HV", "isolated 5 V PS9", 20.0, "output loss", 1.0, "AMC output to common-mode level: reads mid-scale", "DU", "mid-scale reading is inside the UV/OV window"),
 ("OV_HV", "TLV9062 U8 (diff-to-SE)", 5.0, "stuck / open", 1.0, "no OV trip or spurious", "DD", "UV window (fail low) - half of the modes assumed detected"),
 ("OV_HV", "LM393 U11 comparator", 5.0, "no trip (stuck low)", 0.5, "hardware OV path lost; firmware path remains", "DU", "no pulse test of the comparator"),
 ("OV_HV", "LM393 U11 comparator", 5.0, "spurious trip", 0.5, "safe", "S", "-"),
 ("OV_HV", "threshold resistor R159 8.2k", 0.2, "open / drift", 1.0, "HW threshold wrong", "DU", "-"),
 ("OV_HV", "74HC32 / PROT_DIS net", 2.0, "stuck inactive", 0.5, "HW trips do not reach the drivers/TZ", "DU", "no TZ read-back test at start-up in rev A"),
 ("OV_HV", "74HC32 / PROT_DIS net", 2.0, "stuck active", 0.5, "gates held off (safe)", "S", "-"),
 ("OV_HV", "C2000 ADC channel / ISR", 20.0, "wrong conversion / ISR stall", 0.5, "firmware OV lost; watchdog + HW comparator remain", "DD", "watchdog, HW comparator independent"),
 ("OV_HV", "C2000 ADC channel / ISR", 20.0, "latent register corruption", 0.5, "threshold constant corrupted", "DU", "no RAM/flash CRC check in rev A"),
 # ---- LV over-voltage ----
 ("OV_LV", "divider R134/R135 (2 x 1M)", 0.4, "open", 0.9, "V2 reads 0: V2_UV in RUN trips", "DD", "UV window in RUN"),
 ("OV_LV", "divider R134/R135 (2 x 1M)", 0.4, "drift", 0.1, "threshold shifted", "DU", "-"),
 ("OV_LV", "AMC1301 U6", 10.0, "fail low", 0.4, "no OV trip", "DD", "UV window in RUN"),
 ("OV_LV", "AMC1301 U6", 10.0, "fail high", 0.3, "spurious trip", "S", "-"),
 ("OV_LV", "AMC1301 U6", 10.0, "gain drift", 0.3, "regulated voltage wrong AND OV threshold shifted (common cause)", "DU", "regulation uses the same channel: a -20 % gain fault drives V2 to 500 V with the firmware blind; only the HW comparator at 490 V (same AMC!) - see HIL_Validation T16"),
 ("OV_LV", "isolated 5 V PS10", 20.0, "output loss", 1.0, "reads mid-scale", "DU", "-"),
 ("OV_LV", "TLV9062 U8/U9", 5.0, "stuck / open", 1.0, "", "DD", "UV window"),
 ("OV_LV", "LM393 U11 comparator", 5.0, "no trip", 0.5, "HW OV lost", "DU", "no pulse test"),
 ("OV_LV", "LM393 U11 comparator", 5.0, "spurious", 0.5, "safe", "S", "-"),
 ("OV_LV", "74HC32 / PROT_DIS net", 2.0, "stuck inactive", 0.5, "", "DU", "-"),
 ("OV_LV", "74HC32 / PROT_DIS net", 2.0, "stuck active", 0.5, "", "S", "-"),
 ("OV_LV", "C2000 ADC channel / ISR", 20.0, "conversion / stall", 0.5, "", "DD", "watchdog"),
 ("OV_LV", "C2000 ADC channel / ISR", 20.0, "latent corruption", 0.5, "", "DU", "-"),
 # ---- inductor over-current (CMPSS/LM393 on the CT burden, TZ1; firmware FLT_I_PK) ----
 ("OC", "CT1 (1:100) + one-turn lead", 1.0, "open secondary / lead off", 0.8, "reads 0: no OC detection at all (HW and FW share the CT)", "DU", "FMEA open item: plausibility check vs power model not implemented"),
 ("OC", "CT1 (1:100) + one-turn lead", 1.0, "ratio drift / saturation", 0.2, "threshold shifted", "DU", "-"),
 ("OC", "burden R141 6.2R", 0.2, "open", 0.7, "burden open: CT voltage rises -> spurious trip (safe) or damage", "S", "-"),
 ("OC", "burden R141 6.2R", 0.2, "short", 0.3, "reads 0: no OC detection", "DU", "-"),
 ("OC", "rectifier D30/D31 + peak hold", 2.0, "open / short", 1.0, "reads 0 or stuck", "DU", "-"),
 ("OC", "LM393 U10 comparator", 5.0, "no trip", 0.5, "HW OC lost; FW I_PK (10 us) remains", "DU", "no pulse test"),
 ("OC", "LM393 U10 comparator", 5.0, "spurious", 0.5, "safe", "S", "-"),
 ("OC", "74HC32 / PROT_DIS net", 2.0, "stuck inactive", 0.5, "", "DU", "-"),
 ("OC", "74HC32 / PROT_DIS net", 2.0, "stuck active", 0.5, "", "S", "-"),
 ("OC", "C2000 TZ1 / ADC / ISR", 20.0, "TZ not armed / ISR stall", 0.5, "FW path lost; HW comparator -> driver DIS pins still acts (PROT_DIS wired to the drivers directly)", "DD", "driver DIS path independent of the MCU"),
 ("OC", "C2000 TZ1 / ADC / ISR", 20.0, "latent corruption", 0.5, "", "DU", "-"),
 # ---- over-temperature (NTC on each heatsink -> ADC -> firmware FLT_OT at 95 C; no hardware path) ----
 ("OT", "NTC J18/J19 (10k)", 2.0, "open / detached", 0.6, "reads cold: OT undetected", "DU", "no plausibility check (temperature vs loss model); proposed in README"),
 ("OT", "NTC J18/J19 (10k)", 2.0, "short", 0.4, "reads hot: spurious trip", "S", "-"),
 ("OT", "pull-up / filter", 0.2, "open", 1.0, "reads hot (safe) or cold depending on topology", "DU", "assumed cold"),
 ("OT", "C2000 ADC / ISR", 20.0, "stall", 0.5, "watchdog -> gates off", "DD", "watchdog"),
 ("OT", "C2000 ADC / ISR", 20.0, "latent corruption", 0.5, "", "DU", "-"),
 # ---- interlock (precharge feedback PC817 -> precharge_ok; external enable) ----
 ("INTERLOCK", "PC817 U18/U19", 5.0, "LED open / CTR loss", 0.7, "precharge_ok never true -> PRECHARGE timeout -> FAULT (safe)", "S", "-"),
 ("INTERLOCK", "PC817 U18/U19", 5.0, "transistor short", 0.3, "precharge_ok stuck true: soft start into an un-precharged link; v1 > 600 V guard still required", "DU", "no self-test of the input"),
 ("INTERLOCK", "contactor feedback contact (external)", 50.0, "welded / wrong wiring", 0.3, "false precharge_ok", "DU", "-"),
 ("INTERLOCK", "contactor feedback contact (external)", 50.0, "open", 0.7, "timeout -> FAULT", "S", "-"),
 ("INTERLOCK", "firmware guard v1 > LIM_V1_UV", 1.0, "constant corruption", 1.0, "", "DU", "-"),
 # ---- desaturation / short-circuit (rev A: NONE - UCC21520 has no DESAT; fuse only) ----
 ("DESAT_SC", "UCC21520 (no DESAT) - fuse F1/F2 only", 1.0, "fuse fails to clear", 1.0, "device destruction / case rupture on a shoot-through", "DU", "rev A has no short-circuit detection: all shoot-through events rely on the fuse; the UCC21710 upgrade adds DESAT (<1 us)"),
 ("DESAT_SC", "driver UVLO (UCC21520)", 10.0, "UVLO lost", 0.2, "partial-on device", "DU", "-"),
 ("DESAT_SC", "driver UVLO (UCC21520)", 10.0, "spurious UVLO", 0.3, "gates off (safe)", "S", "-"),
 ("DESAT_SC", "driver UVLO (UCC21520)", 10.0, "other", 0.5, "no effect on protection", "S", "-"),
]


def main():
    agg = {}
    for fn, comp, lam, mode, share, effect, cls, diag in ROWS:
        a = agg.setdefault(fn, dict(S=0.0, DD=0.0, DU=0.0))
        a[cls] += lam * share
    out = {}
    md = ["# FMEDA-lite summary (class failure rates in FIT, assumptions; NO SIL claim)\n", "| protection function | lambda_S | lambda_DD | lambda_DU | DC = DD/(DD+DU) | SFF | comment |", "|---|---|---|---|---|---|---|"]
    comments = {"OV_HV": "AMC1301 channel shared by HW and FW paths (common cause); comparator untested",
                "OV_LV": "gain drift of U6 is common cause for regulation and OV (see HIL T16)",
                "OC": "CT is a single point for HW and FW; plausibility check is the cheapest DC gain",
                "OT": "firmware-only; NTC open reads cold (DU)", "INTERLOCK": "stuck-true input is DU; v1 guard mitigates",
                "DESAT_SC": "rev A: no detection, DC = 0 by construction"}
    for fn, a in agg.items():
        tot = a["S"] + a["DD"] + a["DU"]; dc = a["DD"] / (a["DD"] + a["DU"]) if a["DD"] + a["DU"] > 0 else float("nan"); sff = (a["S"] + a["DD"]) / tot
        out[fn] = dict(lambda_S_FIT=round(a["S"], 2), lambda_DD_FIT=round(a["DD"], 2), lambda_DU_FIT=round(a["DU"], 2), DC=round(dc, 3), SFF=round(sff, 3))
        md.append(f"| {fn} | {a['S']:.1f} | {a['DD']:.1f} | {a['DU']:.1f} | {100*dc:.0f} % | {100*sff:.0f} % | {comments.get(fn,'')} |")
    md += ["", "Rev A diagnostic gaps ranked by lambda_DU: " + ", ".join(f"{k} ({v['lambda_DU_FIT']} FIT)" for k, v in sorted(out.items(), key=lambda kv: -kv[1]["lambda_DU_FIT"])),
           "", "Proposed diagnostics (each converts the named DU modes to DD): (1) CT plausibility: |i_pk| vs the SPS power model at the commanded phi (OC: CT open/short, rectifier); "
           "(2) comparator pulse test at start-up: inject a test level into the LM393 inputs through a DAC/GPIO and expect PROT_DIS (OV/OC comparators, 74HC32, TZ arming); "
           "(3) NTC plausibility: heatsink temperature vs the loss model and vs the second NTC (OT: NTC open); (4) V1/V2 cross-check: V2 x n vs V1 at the EPS matching point and the HV/LV power balance (AMC gain drift); "
           "(5) flash/RAM CRC of the parameter block (threshold corruption); (6) DESAT driver upgrade (UCC21710) for the short-circuit function."]
    with open(os.path.join(RES, "fmeda_lite.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["function", "component", "lambda_class_FIT", "failure_mode", "mode_share", "effect", "class", "diagnostic_or_justification"])
        for r in ROWS: w.writerow(r)
    open(os.path.join(RES, "fmeda_lite.md"), "w").write("\n".join(md) + "\n")
    json.dump(out, open(os.path.join(RES, "fmeda_summary.json"), "w"), indent=1)
    print("\n".join(md))
    def hs(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
    head = open(os.path.join(REPO, ".git", "HEAD")).read().strip(); commit = head
    if head.startswith("ref:"):
        rp = os.path.join(REPO, ".git", head[5:]); commit = open(rp).read().strip() if os.path.exists(rp) else head
    json.dump(dict(script="fmeda_lite.py", python=platform.python_version(), numpy=np.__version__, git_commit=commit, wall_time_s=round(time.time() - T0, 2), deterministic="no random numbers",
                   inputs={os.path.relpath(f, REPO): hs(f) for f in [os.path.join(DAB, "15_Safety_Reliability", "02_FMEA.csv"), os.path.join(DAB, "16_BOM", "bom.csv")]}),
              open(os.path.join(RES, "provenance_fmeda.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
