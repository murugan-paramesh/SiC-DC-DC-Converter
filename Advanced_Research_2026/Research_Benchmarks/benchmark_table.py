#!/usr/bin/env python3
"""
Benchmark table: this project's 6.6 kW DAB design and the 3 kW PSFB baseline against the published
6.6 kW-class isolated bidirectional DC-DC work recorded in
Advanced_Research_2026/Literature_Database/literature_2022_2026.csv.

Rules (honesty):
  * numbers from the literature are quoted in the main columns ONLY from entries whose
    verification_status STARTS with 'confirmed' (57-entry database with `evidence` column); entries that
    are 'partially confirmed' or 'not found' have their numbers moved to the 'unverified_numbers' column
    and are drawn with hollow markers;
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
    """Only a status that STARTS with 'confirmed' qualifies; 'partially confirmed' and 'not found' do not."""
    return str(status).strip().lower().startswith("confirmed")


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
        "eta_full_pct", "power_density_kW_per_L", "control", "validation_level", "numbers_status", "unverified_numbers",
        "database_text", "notes"]
rows = []
# ---- literature rows: isolated bidirectional DC-DC converter hardware/designs in the database (device, gate-driver,
#      estimation-only and review entries excluded).  The quantitative figures below are transcribed from the database
#      fields power_rating / switching_freq / efficiency_reported (reproduced verbatim in `database_text`).
#      A figure is placed in the main columns only if the entry's verification_status starts with 'confirmed'.
LIT_ROWS = {
    # id: (devices, fs_kHz, power_kW, voltage_ranges, eta_peak_pct, control, notes)
    "L01": ("not captured", None, 1.0, "not captured", 92.6, "hybrid phase-shift MPC, Bayesian-optimised weights", "1 kW laboratory prototype, low efficiency level indicates a low-voltage class; abstract only"),
    "L06": ("SiC-FETs + monolithic bidirectional GaN, planar transformer", 50, 6.6, "200-800 V in / 400 V out", 98.0, "reconfigurable bridge (T-cell + half-bridge cell)", "figures from one abstract snippet; full text not read"),
    "L07": ("SiC MOSFETs (vendor design)", 500, 6.6, "not captured", 98.0, "not captured (vendor firmware)", "resonant CLLC/CLLLC, vendor claim; TI page not fetchable, seen on a third-party news page"),
    "L16": ("not captured", 20, 1.0, "300 V / 300 V", None, "moving-discretised-control-set MPC, TPS", "control paper, 1 kW experiment, no efficiency figure in the database"),
    "L17": ("not captured", None, 1.0, "not captured", None, "MPC + TPS", "control paper, 1 kW prototype"),
    "L23": ("not captured", 40, 0.15, "not captured", 99.1, "not captured (TMS320F28335)", "150 W - NOT comparable to the kW class; listed for the integrated-leakage transformer only"),
    "L25": ("bare-die SiC, leakage-integrated planar transformer", None, None, "not captured", None, "not captured", "year/venue/power/frequency not confirmed"),
    "L31": ("not captured", None, 2.0, "not captured", None, "n/a (modelling paper)", "2 kW hardware used for model validation only"),
    "L38": ("SiC", 50, 20.0, "not captured", 98.8, "ZVS-enhanced rms-current-minimised TPS", "20 kW class; aggregator page only"),
    "L46": ("GaN MBDS + SiC, planar transformer", None, 5.0, "wide range (values not captured)", 97.8, "reconfigurable bridge", "TPEL version of L06; 5 kW per ResearchGate summary conflicts with 6.6 kW APEC version"),
    "L47": ("650 V / 25 mOhm GaN", None, 6.6, "450 V class (title)", None, "not captured", "totem-pole PFC + DAB on-board charger; no efficiency/fs in accessible sources"),
    "L57": ("GaN, planar magnetics", 250, 3.3, "600 V in / 400 V out", None, "not captured", "PLECS simulation only - same evidence class as this project"),
}
for lid, (dev, fskhz, pkw, vr, etap, ctrl, note) in LIT_ROWS.items():
    r = lit.set_index("id").loc[lid]
    conf = bool(r["confirmed"])
    dbtext = f"power_rating='{r['power_rating']}'; switching_freq='{r['switching_freq']}'; efficiency_reported='{r['efficiency_reported']}'"
    fmt = lambda v: "n/s" if v is None else v
    row = dict(id=lid, source=f"{r['title']} ({r['venue']})", year=r["year"], topology=r["topology"], devices=dev, voltage_ranges=vr, control=ctrl,
               validation_level=r["validation_method"], numbers_status=("confirmed source" if conf else "UNVERIFIED (status: " + str(r["verification_status"])[:60] + ")"),
               database_text=dbtext, notes=note, power_density_kW_per_L="not recorded in database")
    if conf:
        row.update(fs_kHz=fmt(fskhz), power_kW=fmt(pkw), eta_peak_pct=fmt(etap), eta_full_pct="n/s", unverified_numbers="")
    else:
        row.update(fs_kHz="see unverified", power_kW="see unverified", eta_peak_pct="see unverified", eta_full_pct="n/s",
                   unverified_numbers=f"fs {fmt(fskhz)} kHz; P {fmt(pkw)} kW; eta_peak {fmt(etap)} %")
    rows.append(row)
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
                 numbers_status="calculated (this project)", unverified_numbers="", database_text="n/a",
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
                 numbers_status="calculated (this project)", unverified_numbers="", database_text="n/a",
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
    md.append("| " + " | ".join(str(r[c]).replace("|", "/") for c in COLS[:-2]) + " |")
md += ["", f"Rows: {len(rows)} ({len(LIT_ROWS)} literature entries, 2 project designs). "
       f"Confirmed literature rows with a quoted peak efficiency: {sum(1 for r in rows if r['numbers_status'] == 'confirmed source' and r['eta_peak_pct'] not in ('n/s', 'see unverified'))}; "
       f"unverified rows: {sum(1 for r in rows if r['numbers_status'].startswith('UNVERIFIED'))}.",
       "", "The `database_text` column of the CSV reproduces the literature-database fields the numbers were transcribed from."]
open(os.path.join(OUT, "benchmark_table.md"), "w").write("\n".join(md) + "\n")

# ---- figure
fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
conf_pts = [(r, LIT_ROWS[r["id"]]) for r in rows if r["id"] in LIT_ROWS and r["numbers_status"] == "confirmed source" and LIT_ROWS[r["id"]][1] and LIT_ROWS[r["id"]][4]]
unv_pts = [(r, LIT_ROWS[r["id"]]) for r in rows if r["id"] in LIT_ROWS and r["numbers_status"].startswith("UNVERIFIED") and LIT_ROWS[r["id"]][1] and LIT_ROWS[r["id"]][4]]
for r, (dev, fskhz, pkw, vr, etap, ctrl, note) in conf_pts:
    ax[0].scatter([fskhz], [etap], s=60 + 10 * pkw, marker="s", color="#1f77b4")
    ax[0].annotate(f"{r['id']} {pkw} kW (confirmed, measured)", (fskhz, etap), fontsize=7, xytext=(5, 4), textcoords="offset points")
for r, (dev, fskhz, pkw, vr, etap, ctrl, note) in unv_pts:
    ax[0].scatter([fskhz], [etap], s=60 + 10 * min(pkw, 10), marker="s", facecolors="none", edgecolors="#1f77b4")
    ax[0].annotate(f"{r['id']} {pkw} kW (UNVERIFIED)", (fskhz, etap), fontsize=7, xytext=(5, -10), textcoords="offset points", color="gray")
ax[0].scatter([V["spec"]["fs"] / 1e3], [eta_peak_dab], s=160, marker="*", color="#d62728", label=f"OURS DAB 6.6 kW peak {eta_peak_dab:.1f} % (CALCULATED L2)")
ax[0].scatter([V["spec"]["fs"] / 1e3], [eta_full_dab], s=60, marker="v", color="#d62728", label=f"OURS DAB full load {eta_full_dab:.1f} % (CALCULATED)")
ax[0].scatter([V["spec"]["fs"] / 1e3], [eta_worst_corner], s=40, marker="v", facecolors="none", edgecolors="#d62728", label=f"OURS DAB worst corner {eta_worst_corner:.1f} % (CALCULATED)")
ax[0].scatter([100], [eta_peak_psfb], s=120, marker="*", color="#ff7f0e", label=f"OURS PSFB 3 kW peak {eta_peak_psfb:.1f} % (CALCULATED L2)")
ax[0].scatter([100], [eta_full_psfb], s=60, marker="v", color="#ff7f0e", label=f"OURS PSFB full load {eta_full_psfb:.1f} % (CALCULATED)")
ax[0].scatter([], [], marker="s", color="#1f77b4", label="literature, confirmed entry (measured)")
ax[0].scatter([], [], marker="s", facecolors="none", edgecolors="#1f77b4", label="literature, UNVERIFIED entry")
ax[0].annotate("not plotted: L01 1 kW 92.6 % (fs not stated); entries without an efficiency figure", xy=(0.02, 0.02), xycoords="axes fraction", fontsize=7, color="gray")
ax[0].set_xscale("log"); ax[0].set_xlim(10, 1000); ax[0].set_ylim(96, 99.5)
ax[0].set_xlabel("switching frequency (kHz)"); ax[0].set_ylabel("peak efficiency (%)"); ax[0].set_title("Efficiency vs fs - ours are CALCULATED, theirs measured")
ax[0].grid(alpha=0.3, which="both"); ax[0].legend(fontsize=6.5, loc="lower right", bbox_to_anchor=(1.0, 0.06))
# power density vs power
ax[1].scatter([V["spec"]["P"] / 1e3], [pd_dab], s=160, marker="*", color="#d62728", label=f"OURS DAB {pd_dab:.1f} kW/L (ESTIMATE L1, boxed PCB + heatsinks)")
ax[1].scatter([3.0], [pd_psfb], s=120, marker="*", color="#ff7f0e", label=f"OURS PSFB {pd_psfb:.1f} kW/L (ESTIMATE L1)")
ax[1].axhline(3.0, color="gray", ls="--", lw=0.8, label="MEC-01 objective 3 kW/L (power stage, no enclosure)")
for r in rows:
    if r["id"] in LIT_ROWS and LIT_ROWS[r["id"]][2]:
        pw = LIT_ROWS[r["id"]][2]; ax[1].axvline(pw, color="#bbbbbb", lw=0.6, ls=":")
        ax[1].annotate(r["id"], (pw, 3.6 - 0.25 * (list(LIT_ROWS).index(r["id"]) % 6)), fontsize=6, color="gray", ha="center")
ax[1].annotate("no power density figure is recorded in the literature database for any entry\n(L47 claims 'high power density' in its title without a value);\nvertical dotted lines mark the published power levels only",
               xy=(0.02, 0.05), xycoords="axes fraction", fontsize=7, color="gray")
ax[1].set_xlim(0, 22); ax[1].set_ylim(0, 4); ax[1].set_xlabel("rated power (kW)"); ax[1].set_ylabel("power density (kW/L)")
ax[1].set_title("Power density vs power"); ax[1].grid(alpha=0.3); ax[1].legend(fontsize=6.5, loc="upper right")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_benchmark.png"), dpi=140); plt.close(fig)

summary = dict(n_rows=len(rows), literature_ids=list(LIT_ROWS), confirmed_ids=[r["id"] for r in rows if r["numbers_status"] == "confirmed source"],
               unverified_ids=[r["id"] for r in rows if r["numbers_status"].startswith("UNVERIFIED")],
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
