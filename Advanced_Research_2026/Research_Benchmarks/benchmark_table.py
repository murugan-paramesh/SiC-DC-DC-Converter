#!/usr/bin/env python3
"""
Benchmark table: this project's 6.6 kW DAB design and the 3 kW PSFB baseline against the published
6.6 kW-class isolated bidirectional DC-DC work recorded in
Advanced_Research_2026/Literature_Database/literature_2022_2026.csv.

Rules (honesty):
  * numbers from the literature are quoted ONLY from entries whose verification_status contains
    'confirmed' or 'accessible' and does not contain 'NOT CONFIRMED'; everything else goes into the
    'unverified' columns and is drawn with hollow markers;
  * every figure of this project is CALCULATED (loss model, no hardware) and is labelled so (L2);
  * our power density is a boxed-volume ESTIMATE from the PCB outline and the heatsink height
    (no mechanical CAD) and is labelled L1.
Outputs: results/benchmark_table.csv, results/benchmark_table.md, results/fig_benchmark.png,
         provenance.json.
"""
import os, sys, json, csv, time, hashlib, platform, importlib, datetime, math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DAB = os.path.join(REPO, "SiC_6k6_Industrial_DAB")
LIT = os.path.join(REPO, "Advanced_Research_2026", "Literature_Database", "literature_2022_2026.csv")
DESIGN = os.path.join(DAB, "04_Design_Calculations", "design_values.json")
PSFB_DOC = os.path.join(REPO, "docs", "02_design_calculations.md")
PSFB_SPEC = os.path.join(REPO, "docs", "01_specification.md")
OUT = os.path.join(HERE, "results")
os.makedirs(OUT, exist_ok=True)
T0 = time.time()

lit = pd.read_csv(LIT)
V = json.load(open(DESIGN))


def is_confirmed(status):
    s = str(status).lower()
    return ("confirmed" in s or "accessible" in s) and "not confirmed" not in s


lit["confirmed"] = lit["verification_status"].apply(is_confirmed)

# ---------------------------------------------------------------- this project's figures (calculated)
# DAB: efficiency curve 800/400 V from design_values.json (loss model of 04_Design_Calculations)
load, eta = V["eff_curves"]["800/400"]
eta_peak_dab = max(eta); load_peak_dab = load[int(np.argmax(eta))]
eta_full_dab = 100 * V["nominal"]["eta"]
eta_worst_corner = 100 * min(c["eta"] for c in V["corners"])
# power density estimate: PCB 340 x 250 mm (08_KiCad_PCB/README.md), height 70 mm assumed (E65 cores,
# 60 mm heatsink fins + base, TO-247 on edge); no enclosure, no fans
vol_dab_L = 0.340 * 0.250 * 0.070 * 1000
pd_dab = V["spec"]["P"] / vol_dab_L / 1000
# PSFB 3 kW (docs/02 loss budget, 91.1 W at full load, 97.1 %), part-load scaling as in tools/psfb_design.py
P_fixed, P_lin = 0.3 + 0.5 + 3.4 + 3.3 + 3.7 + 0.5 * 5.0, 7.4 + 2.2 + 4.8 + 1.5
P_total = 91.1; P_sq = P_total - P_fixed - P_lin
ld = np.linspace(0.1, 1.0, 91)
eta_psfb_curve = 100 * 3000 * ld / (3000 * ld + P_fixed + P_lin * ld + P_sq * ld ** 2)
eta_peak_psfb = float(eta_psfb_curve.max()); load_peak_psfb = float(ld[np.argmax(eta_psfb_curve)])
eta_full_psfb = float(eta_psfb_curve[-1])
vol_psfb_L = 0.260 * 0.200 * 0.050 * 1000           # 260 x 200 mm board, 50 mm height assumed (ETD59, heatsink bars)
pd_psfb = 3000 / vol_psfb_L / 1000

COLS = ["id", "source", "year", "topology", "devices", "fs_kHz", "power_kW", "voltage_ranges", "eta_peak_pct",
        "eta_full_pct", "power_density_kW_per_L", "control", "validation_level", "numbers_status", "unverified_numbers", "notes"]
rows = []
# ---- literature rows: isolated bidirectional DC-DC converters only (gate-driver, device and review entries excluded)
conv_ids = ["L01", "L06", "L07", "L23", "L25"]
for _, r in lit[lit["id"].isin(conv_ids)].iterrows():
    conf = bool(r["confirmed"])
    unv = []
    row = dict(id=r["id"], source=f"{r['title']} ({r['venue']})", year=r["year"], topology=r["topology"], devices="not captured in database",
               fs_kHz="n/s", power_kW="n/s", voltage_ranges="not captured in database", eta_peak_pct="n/s", eta_full_pct="n/s",
               power_density_kW_per_L="not captured in database", control="not captured in database",
               validation_level=r["validation_method"], numbers_status="confirmed source" if conf else "UNVERIFIED",
               unverified_numbers="", notes=str(r["limitations"]))
    rows.append(row)
    if r["id"] == "L01":
        row.update(fs_kHz="n/s", power_kW=1.0, eta_peak_pct=92.6, control="hybrid phase-shift MPC, Bayesian-optimised weights",
                   validation_level="prototype measurements (abstract)", notes="1 kW laboratory prototype; low-voltage class; abstract only accessed")
    elif r["id"] == "L06":
        row.update(power_kW=6.6, devices="SiC (type not captured)", notes="6.6 kW class confirmed from the APEC programme; efficiency/fs not captured",
                   unverified_numbers="98 % figure found next to it in search results belongs to TI PMP21495 - NOT this paper")
    elif r["id"] == "L07":
        row.update(fs_kHz=500, power_kW=6.6, eta_peak_pct=98.0, devices="SiC MOSFETs (vendor design, part numbers not captured here)",
                   validation_level="vendor measurements (reference design test report)",
                   notes="resonant CLLC, not phase-shift DAB; vendor data, not peer-reviewed")
    elif r["id"] == "L23":
        row.update(power_kW=0.15, eta_peak_pct=99.1, notes="150 W prototype - NOT comparable to the 6.6 kW class; listed for the integrated-leakage transformer only")
    elif r["id"] == "L25":
        row.update(numbers_status="UNVERIFIED", unverified_numbers="3.3 kW, 500 kHz, bare-die SiC, leakage-integrated planar transformer (TRID record, not read)",
                   notes="date/venue not captured")
# ---- this project
rows.append(dict(id="OURS-DAB", source="SiC_6k6_Industrial_DAB (this repository, calculated design)", year=2026,
                 topology="single-phase DAB, SPS feed-forward + EPS voltage matching (TPS table optional)",
                 devices=f"{V['dev1']} (HV bridge) / {V['dev2']} (LV bridge), TO-247-4", fs_kHz=V["spec"]["fs"] / 1e3, power_kW=V["spec"]["P"] / 1e3,
                 voltage_ranges=f"HV {V['spec']['V1_min']:.0f}-{V['spec']['V1_max']:.0f} V / LV {V['spec']['V2_min']:.0f}-{V['spec']['V2_max']:.0f} V, bidirectional",
                 eta_peak_pct=f"{eta_peak_dab:.2f} (calculated, L2; at {load_peak_dab:.0f} % load, 800/400 V)",
                 eta_full_pct=f"{eta_full_dab:.2f} (calculated, L2; worst corner 850/300 V: {eta_worst_corner:.2f})",
                 power_density_kW_per_L=f"{pd_dab:.1f} (ESTIMATE, L1: 340 x 250 x 70 mm boxed, no enclosure/fans; objective MEC-01 >= 3)",
                 control="digital PI (600 Hz crossover) + inverse-SPS feed-forward + EPS matching; C2000 target; explicit MPC studied",
                 validation_level="L2 simulation (switched Python + ngspice), L3 SIL of the C control core; NO hardware",
                 numbers_status="calculated (this project)", unverified_numbers="",
                 notes="forced air 3 m/s; 2 oz 6-layer PCB; semiconductor data entered from memory of datasheets (flag verified=False)"))
rows.append(dict(id="OURS-PSFB", source="hardware/ + docs/ (this repository, 3 kW PSFB reference design, calculated)", year=2026,
                 topology="ZVS phase-shifted full bridge + centre-tapped synchronous rectifier (unidirectional)",
                 devices="C3M0060065K x4 (primary), IPP110N20N3 G x4 (SR), C3D04065A clamp diodes", fs_kHz=100.0, power_kW=3.0,
                 voltage_ranges="in 370-420 V (320 V derated) / out 48 V, 62.5 A",
                 eta_peak_pct=f"{eta_peak_psfb:.2f} (calculated, L2; at {100 * load_peak_psfb:.0f} % load, from the docs/02 loss budget scaling)",
                 eta_full_pct=f"{eta_full_psfb:.1f} (calculated, L2)",
                 power_density_kW_per_L=f"{pd_psfb:.1f} (ESTIMATE, L1: 260 x 200 x 50 mm boxed)",
                 control="UCC28951 analogue peak-current-mode PSFB controller, adaptive ZVS delays",
                 validation_level="L3 software-verified design (DRC 0 errors, gerbers), switched simulation; NO hardware",
                 numbers_status="calculated (this project)", unverified_numbers="",
                 notes="forced air 2 m/s; 4-layer 2 oz PCB; not bidirectional - baseline only"))

df = pd.DataFrame(rows, columns=COLS)
df.to_csv(os.path.join(OUT, "benchmark_table.csv"), index=False)

# ---- markdown table
md = ["# Benchmark table (generated by benchmark_table.py)", "",
      "Literature numbers appear in the main columns only when the database entry is marked confirmed/accessible; "
      "unverified numbers are in the separate `unverified numbers` column. Project numbers are CALCULATED (no hardware).", "",
      "| id | source | year | topology | devices | fs (kHz) | P (kW) | voltage ranges | eta peak (%) | eta full load (%) | power density (kW/L) | control | validation | numbers status | unverified numbers |",
      "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for r in rows:
    md.append("| " + " | ".join(str(r[c]).replace("|", "/") for c in COLS[:-1]) + " |")
md += ["", f"Rows: {len(rows)} ({len(conv_ids)} literature entries, 2 project designs). "
       f"Confirmed literature rows with at least one quantitative figure: {sum(1 for r in rows if r['numbers_status'] == 'confirmed source' and r['eta_peak_pct'] != 'n/s')}."]
open(os.path.join(OUT, "benchmark_table.md"), "w").write("\n".join(md) + "\n")

# ---- figure
fig, ax = plt.subplots(1, 2, figsize=(11, 4.4))
# efficiency vs fs
ax[0].scatter([500], [98.0], s=70, marker="s", color="#1f77b4", label="L07 TI PMP21495 CLLC 6.6 kW (vendor measured)")
ax[0].scatter([V["spec"]["fs"] / 1e3], [eta_peak_dab], s=110, marker="*", color="#d62728", label=f"OURS DAB 6.6 kW peak {eta_peak_dab:.1f} % (CALCULATED)")
ax[0].scatter([V["spec"]["fs"] / 1e3], [eta_full_dab], s=60, marker="v", color="#d62728", label=f"OURS DAB full load {eta_full_dab:.1f} % (CALCULATED)")
ax[0].scatter([V["spec"]["fs"] / 1e3], [eta_worst_corner], s=40, marker="v", facecolors="none", edgecolors="#d62728", label=f"OURS DAB worst corner {eta_worst_corner:.1f} % (CALCULATED)")
ax[0].scatter([100], [eta_peak_psfb], s=90, marker="*", color="#ff7f0e", label=f"OURS PSFB 3 kW peak {eta_peak_psfb:.1f} % (CALCULATED)")
ax[0].scatter([100], [eta_full_psfb], s=60, marker="v", color="#ff7f0e", label=f"OURS PSFB full load {eta_full_psfb:.1f} % (CALCULATED)")
ax[0].annotate("L01 1 kW hybrid-PS MPC: 92.6 % peak, fs not stated (confirmed abstract) - off scale\n"
               "L23 150 W: 99.1 %, fs not stated - not comparable\nL06 6.6 kW APEC 2025: efficiency/fs UNVERIFIED - not plotted",
               xy=(0.02, 0.03), xycoords="axes fraction", fontsize=7, color="gray")
ax[0].set_xscale("log"); ax[0].set_xlim(50, 1000); ax[0].set_ylim(96, 99.5)
ax[0].set_xlabel("switching frequency (kHz)"); ax[0].set_ylabel("efficiency (%)"); ax[0].set_title("Efficiency vs fs (ours: calculated, no hardware)")
ax[0].grid(alpha=0.3, which="both"); ax[0].legend(fontsize=6.5, loc="upper right")
# power density vs power
ax[1].scatter([V["spec"]["P"] / 1e3], [pd_dab], s=110, marker="*", color="#d62728", label=f"OURS DAB {pd_dab:.1f} kW/L (ESTIMATE L1, boxed PCB+heatsink)")
ax[1].scatter([3.0], [pd_psfb], s=90, marker="*", color="#ff7f0e", label=f"OURS PSFB {pd_psfb:.1f} kW/L (ESTIMATE L1)")
ax[1].axhline(3.0, color="gray", ls="--", lw=0.8, label="MEC-01 objective 3 kW/L (power stage, no enclosure)")
for pw, lab in ((6.6, "L07 (6.6 kW)"), (6.6, "L06 (6.6 kW)"), (1.0, "L01 (1 kW)"), (3.3, "L25 (3.3 kW, unverified)")):
    ax[1].axvline(pw, color="#bbbbbb", lw=0.6, ls=":")
ax[1].annotate("no power density is recorded in the literature database for any\nconfirmed entry (L01, L06, L07, L23) - vertical dotted lines mark\n"
               "their power levels only; L25 (3.3 kW) is unverified", xy=(0.02, 0.75), xycoords="axes fraction", fontsize=7, color="gray")
ax[1].set_xlim(0, 8); ax[1].set_ylim(0, 4); ax[1].set_xlabel("rated power (kW)"); ax[1].set_ylabel("power density (kW/L)")
ax[1].set_title("Power density vs power"); ax[1].grid(alpha=0.3); ax[1].legend(fontsize=6.5, loc="lower right")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_benchmark.png"), dpi=140); plt.close(fig)

summary = dict(n_rows=len(rows), literature_ids=conv_ids, confirmed_ids=[r["id"] for r in rows if r["numbers_status"] == "confirmed source"],
               unverified_ids=[r["id"] for r in rows if r["numbers_status"] == "UNVERIFIED"],
               ours=dict(dab=dict(eta_peak_pct=eta_peak_dab, eta_peak_load_pct=load_peak_dab, eta_full_pct=eta_full_dab, eta_worst_corner_pct=eta_worst_corner,
                                  power_density_kW_L_estimate=pd_dab, boxed_volume_L=vol_dab_L),
                         psfb=dict(eta_peak_pct=eta_peak_psfb, eta_peak_load_pct=100 * load_peak_psfb, eta_full_pct=eta_full_psfb,
                                   power_density_kW_L_estimate=pd_psfb, boxed_volume_L=vol_psfb_L,
                                   loss_split_W=dict(fixed=P_fixed, linear=P_lin, quadratic=P_sq, total=P_total))),
               literature_db_entries=int(len(lit)), literature_db_confirmed=int(lit["confirmed"].sum()))
json.dump(summary, open(os.path.join(OUT, "benchmark_summary.json"), "w"), indent=1)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def git_commit():
    try:
        head = open(os.path.join(REPO, ".git", "HEAD")).read().strip()
        if head.startswith("ref: "):
            ref = head[5:]; p = os.path.join(REPO, ".git", ref)
            if os.path.exists(p):
                return open(p).read().strip()
            for line in open(os.path.join(REPO, ".git", "packed-refs")):
                if line.strip().endswith(ref):
                    return line.split()[0]
        return head
    except Exception:
        return "unknown"


inputs = [LIT, DESIGN, PSFB_DOC, PSFB_SPEC, __file__]
prov = dict(script=os.path.relpath(__file__, REPO), generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            python=platform.python_version(), platform=platform.platform(),
            packages={m: importlib.import_module(m).__version__ for m in ("numpy", "pandas", "matplotlib")},
            git_commit=git_commit(), input_sha256={os.path.relpath(p, REPO): sha(p) for p in inputs}, seeds="none (deterministic table)",
            wall_time_s=time.time() - T0, outputs=sorted(os.listdir(OUT)))
json.dump(prov, open(os.path.join(HERE, "provenance.json"), "w"), indent=1)
print(json.dumps(summary, indent=1))
