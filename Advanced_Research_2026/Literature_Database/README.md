# Literature_Database — verified literature record for the 6.6 kW SiC DAB research platform

Maturity: L0 (literature record; no code, no measurements). Everything in this folder follows
`../MODULE_CONVENTIONS.md`: nothing is claimed that the accessible sources did not show, and entries that
could not be confirmed are kept and flagged rather than deleted, so the record of what was claimed earlier
is preserved.

## Files

| file | content |
|---|---|
| `literature_2022_2026.csv` | 57 entries, UTF-8, 16 columns: `id,title,authors,year,venue,doi_or_url,topology,power_rating,switching_freq,efficiency_reported,validation_method,strengths,limitations,research_gap_identified,verification_status,evidence` |
| `README.md` | this file |

The earlier recalled review (38 references, not verified against sources) is the engineering baseline's
`../../SiC_6k6_Industrial_DAB/01_Literature_Review/literature_review.md`; this folder supersedes it as the
citable record. The CSV is the only database file here.

## How the database was built

### Pass 1 (before 2026-10-10)
29 entries L01–L29 were collected from search-index snippets. Several were "seen only as a citation" or carried
a DOI "to verify". Their original status text has been replaced by one of four standard values (below) but
their original claims (title, numbers) were kept wherever they were not contradicted.

### Pass 2 — verification and extension, 2026-10-10
* Tool: `WebSearch` only. **Every `WebFetch`/`curl` request failed with DNS refusal** (`getaddrinfo ENOTFOUND`)
  — this applied to ieeexplore.ieee.org, jstage.jst.go.jp, doi.org, arxiv.org, mdpi.com, nature.com,
  link.springer.com, sciencedirect.com, researchgate.net, semanticscholar.org, api.crossref.org,
  api.openalex.org, pmc.ncbi.nlm.nih.gov, macau.uni-kiel.de and institutional repositories. The proxy
  status endpoint confirmed `CONNECT tunnel failed, response 403` for outbound hosts.
  **Consequently all evidence is search-result snippets**, i.e. the title/author/venue/abstract text that the
  search engine returned for a page. No full text and no PDF was read. Where a snippet contained numbers
  (power, fs, efficiency) they were copied; otherwise the field says `not in accessible sources`.
* ~75 queries were run. Representative query strings (all 2026-10-10):
  * exact titles in quotes (every L01–L29 entry), e.g. `"Moving Discretized Control Set Model-Predictive Control for Dual-Active Bridge With the Triple-Phase Shift"`;
  * bare DOIs, e.g. `10.1109/TPEL.2025.3629881`, `10.1587/elex.23.20260139`, `10.1109/TIM.2025.3635834`;
  * Xplore ids, e.g. `ieeexplore.ieee.org/document/10905834`;
  * topic queries for Task B: `dual active bridge model predictive control 2025 2026 IEEE Transactions on Power Electronics triple phase shift SiC prototype kW`,
    `dual active bridge digital twin parameter estimation online 2025 2026 …`, `SiC MOSFET online Rds_on OR "on-state resistance" OR "threshold voltage" condition monitoring in-converter 2025 2026 …`,
    `active gate driver SiC MOSFET 2025 IEEE Transactions on Power Electronics closed-loop dv/dt di/dt …`,
    `6.6 kW CLLC bidirectional on-board charger SiC 2025 …`, `6.6 kW dual active bridge SiC on-board charger 2025 2026 prototype efficiency …`,
    `planar transformer integrated leakage inductance dual active bridge 2025 2026 IEEE kW 100 kHz SiC`,
    `safe reinforcement learning OR "constrained reinforcement learning" power converter control 2025 2026 …`,
    `GaN dual active bridge record efficiency 99% 2025 …`, `physics-informed neural network power electronics 2025 2026 … dual active bridge`;
  * follow-up identity queries for each candidate found (title in quotes + venue).
* The `evidence` column of every row gives the URL(s) of the result page(s) and what the snippet showed.

### Status vocabulary (`verification_status`)
* `confirmed (title+venue+year seen)` — title, venue and year all appeared together in at least one snippet.
* `partially confirmed (<what>)` — only part of the bibliographic record was seen (e.g. title only on a repository list, or figures only on an aggregator).
* `not found - treat as unverified` — no matching record was returned by any query; the row is kept as a record of the earlier claim and must not be cited.
* `does not exist as described` — not used; no entry was positively shown to be fictitious, but see the three named papers below.

### Result of pass 2
| group | confirmed | partially confirmed | not found |
|---|---|---|---|
| original L01–L29 | 20 | 7 (L05, L06, L07, L11, L25, L26, L27) | 2 (L08, L18) |
| new L30–L57 (28 added) | 23 | 5 (L36, L38, L44, L45, L46) | 0 |
| total 57 | 43 | 12 | 2 |

Corrections made to original rows: L03 is IECON 2024 (not TIM 2025); L04 full title/authors/DOI found;
L13 year 2020 → 2021 (TIE 68(2)); L20 title and topology corrected (three-port active bridge, not DAB);
L10 abstract claims corrected; L16/L17/L22/L24 full author lists and page ranges added; L06 title completed.

## Summary table of confirmed entries
(abbreviated; the CSV holds the full text. "n/a" = not applicable to this kind of paper; "not in accessible
sources" = the snippet did not show the number.)

| id | year | venue | topology | power | fs | efficiency | validation |
|---|---|---|---|---|---|---|---|
| L01 | 2026 | IEICE Electronics Express (advance online publication, arti… | DAB (hybrid phase shift) | 1 kW prototype | not in accessible sources | 92.6 % peak vs 88.2 % SPS; current stress -44.7 % (abstract) | prototype measurements |
| L02 | 2026 | IEEE Transactions on Power Electronics vol. 41 no. 1 pp. 49… | DAB TPS | not stated in abstract | not stated in abstract | not stated in abstract | comparative experiments (prototype) |
| L03 | 2024 | IECON 2024 - 50th Annual Conference of the IEEE Industrial … | DAB | not in accessible sources | not in accessible sources | n/a (voltage-prediction twin) | microcontroller implementation of XGBoost and DNN twin… |
| L04 | 2024 | IEEE Transactions on Instrumentation and Measurement vol. 73 | buck prototype (generic method) | not in accessible sources | not in accessible sources | n/a | buck prototype; PSO fit of a Simulink replica to a few… |
| L09 | 2026 | IEEE Transactions on Industrial Electronics vol. 73 no. 1 p… | generic converters | n/a | n/a | n/a | simulation |
| L10 | 2025 | arXiv 2508.02887 (v1 2025-08-04, cs.LG) | generic converters | n/a | n/a | n/a | simulation |
| L12 | 2025 | IEEE Transactions on Instrumentation and Measurement (early… | SiC devices | 1.2 kV / 30 A devices in half-bridge te… | n/a | indicator: peak of gate HF switching-oscillation current, ~… | accelerated high-field gate aging; half-bridge switchi… |
| L13 | 2021 | IEEE Transactions on Industrial Electronics vol. 68 no. 2 p… | SiC devices | n/a | n/a | n/a | power-cycling experiments |
| L14 | 2023 | IEEE Transactions on Power Electronics vol. 38 no. 9 pp. 11… | buck converter | n/a | n/a | Rds_on within +/-5 % | experiment |
| L15 | 2023 | IET Power Electronics vol. 16 no. 12 pp. 1984-1995 | DAB EPS | n/a | n/a | n/a | experiment |
| L16 | 2020 | IEEE Transactions on Power Electronics vol. 35 no. 8 pp. 86… | DAB TPS | 1 kW (300 V / 300 V) | 20 kHz | n/a | experiment |
| L17 | 2021 | IEEE Access vol. 9 pp. 98603-98614 (2021) | DAB TPS | 1 kW laboratory prototype (per Research… | n/a | n/a | experiment |
| L19 | 2025 | IEEE Open Journal of Power Electronics vol. 6 pp. 1769-1802 | various | n/a | n/a | n/a | review |
| L20 | 2026 | Electronics (MDPI) vol. 15 no. 8 art. 1563 (published 2026-… | three-port active bridge (TAB), shipboard zo… | n/a | n/a | n/a | DDPG tuning of d1, d2, gamma to minimise total loss at… |
| L21 | 2026 | Micromachines vol. 17 no. 5 art. 558 (published 2026-04-30) | gate driver | 400 V / 40 A double-pulse test; 180 nm … | n/a (dv/dt 4.8 V/ns at turn-o… | turn-on loss -35.1 %, turn-off loss -33.2 % vs passive driv… | experiment |
| L22 | 2020 | IEEE Transactions on Power Electronics vol. 35 no. 2 pp. 18… | gate driver | n/a | n/a | n/a | double-pulse tests vs two-stage turn-off and commercia… |
| L23 | 2025 | Scientific Reports (published 2025-10-13) | DAB integrated-leakage transformer | 150 W prototype | 40 kHz (per one search summar… | up to 99.1 % (150 W) | ANSYS Maxwell FEA + 150 W prototype with TMS320F28335 |
| L24 | 2024 | IEEE Access vol. 12 pp. 112278-112289 | DAB planar transformer | n/a | n/a | n/a | 3-D FEA + prototype experiments |
| L28 | 2026 | arXiv 2608.30915 | buck converter case study (generic method) | n/a | n/a | n/a | 30 hardware configurations of a buck converter; sparse… |
| L29 | 2026 | arXiv 2609.00218 | buck converter (synthetic + hardware data) | n/a | n/a | n/a | Bayesian MAP + Laplace posterior on differentiable mod… |
| L30 | 2025 | arXiv 2502.17452 (submitted 2025-02-08, eess.SP) | DAB, TPS, GaN | 2 kW GaN prototype (stated in one searc… | 100 kHz (same caveat) | +1.4 % average efficiency vs non-adaptive TPS under an emul… | PINN trained on mixed hardware + frequency-domain-mode… |
| L31 | 2025 | IEEE Transactions on Industrial Electronics vol. 72 no. 2 p… | DAB family (non-resonant, resonant, multilev… | 2 kW hardware | not in accessible sources | not in accessible sources | 2 kW hardware experiments; transfer from one non-reson… |
| L32 | 2024 | IEEE Transactions on Power Electronics (published online 20… | DAB | not in accessible sources | not in accessible sources | not in accessible sources | not in accessible sources |
| L33 | 2025 | arXiv 2504.20528 (2025-04-29); accepted ECCE Asia 2025 | buck converter | not in accessible sources | not in accessible sources | median estimation errors < 7 % (L), 5 % (C), 2 % (R), 11 % … | loss-landscape analysis + experiments on buck converter |
| L34 | 2025 | arXiv 2512.12026 (v1 2025-12-12, eess.SY) | generic; validated on a DAB | 1500 W DAB | not in accessible sources | n/a (surrogate >7x faster than real time; >95 % design-time… | cloud-to-edge deployment on a 1500 W DAB; comparison w… |
| L35 | 2026 | IEEE Transactions on Power Electronics vol. 41 no. 3 pp. 31… | DAB | not in accessible sources | not in accessible sources | not in accessible sources | experiments on a DAB prototype |
| L37 | 2025 | IEEE Access vol. 13 pp. 152748-152761 | DAB TPS (review) | n/a | n/a | n/a | review |
| L39 | 2025 | IEEE Transactions on Power Electronics vol. 40 no. 9 pp. 12… | SiC MOSFET (buck converter demonstration) | not in accessible sources | not in accessible sources | indicator change 5.61 % / 5 % / 8.33 % after 160 h HTGB(+/-… | accelerated gate aging + DPT + buck converter online m… |
| L40 | 2025 | Electronics (MDPI) vol. 14 no. 4 art. 771 (2025-02-16) | SiC MOSFET | not in accessible sources | not in accessible sources | indicator +6.55 % after 42 h HTGB at 32 V; 0.103 % change o… | HTGB aging; temperature sweep; bus voltage/load/bond-w… |
| L41 | 2025 | Engineering Applications of Artificial Intelligence vol. 15… | MOSFET aging data (device level) | n/a | n/a | n/a | benchmark of classical tracking, statistical, NN and T… |
| L42 | 2026 | arXiv 2608.08363 (Aug 2026, eess.SY / cs.LG) | SiC MOSFET power modules (sintered packaging) | n/a | n/a | n/a | features from Tj swing, mean Tj and Miner's-rule damag… |
| L43 | 2026 | arXiv 2604.15714; presented at ICONS 2026 (per UW-Madison l… | generic converter (R_s, C estimation) | n/a | n/a | R_s error 10.2 %, C error 8.8 % on EMI-corrupted waveforms;… | simulation with EMI-corrupted waveforms; SNN + ODE loss |
| L47 | 2024 | Micromachines vol. 15 no. 12 art. 1470 | totem-pole PFC + DAB DC-DC stage, 650 V / 25… | 6.6 kW (+1 kW aux) | not in accessible sources | not in accessible sources | hardware implementation (abstract) |
| L48 | 2025 | IEEE Transactions on Power Electronics vol. 40 no. 4 pp. 56… | multi-active-bridge integrated multiwinding … | not in accessible sources | not in accessible sources | not in accessible sources | magnetic-circuit analysis + 3-D FEA + cross-shaped-cor… |
| L49 | 2024 | IEEE Transactions on Industrial Electronics vol. 71 no. 11 … | two-level voltage source converter | not in accessible sources | not in accessible sources | n/a | VSC testbed experiments |
| L50 | 2026 | arXiv 2603.07964 (2026-03-09) | power inverter (kW-level hardware) | kilowatt-level platform | not in accessible sources | n/a (microsecond inference after distillation) | hardware experiments; policy distillation with adaptiv… |
| L51 | 2025 | IET Power Electronics vol. 18 no. 1 | review | n/a | n/a | n/a | review |
| L52 | 2026 | Electronics (MDPI) vol. 15 no. 13 art. 2903 | DAB (nonlinear model incl. parasitics) | not in accessible sources | not in accessible sources | n/a | simulation + real-time emulation (abstract) |
| L53 | 2026 | IEEE Access vol. 14 pp. 12337-12353 | DAB DPS | not in accessible sources | not in accessible sources | n/a | Bode verification + HIL simulation of a virtual DAB |
| L54 | 2025 | Electronics (MDPI) vol. 14 no. 15 art. 3031 (2025-07-30) | DAB TPS | not in accessible sources | not in accessible sources | not in accessible sources | KKT/Lagrange optimisation; prototype not confirmed in … |
| L55 | 2026 | arXiv 2603.21128 (2026-03-22); accepted IEEE IDCD 2026 | boost converter | not in accessible sources | not in accessible sources | n/a | experiments on a commercial boost module |
| L56 | 2025 | Scientific Reports (2025) | series-resonant DAB, TPS + variable fs | 300 W laboratory prototype | variable (value not in snippe… | gain stated qualitatively vs literature; no percentage in s… | 300 W prototype, buck and boost modes |
| L57 | 2025 | 2025 IEEE Energy Conversion Congress and Exposition Asia (E… | GaN DAB with planar transformer | 3.3 kW, 600 V in / 400 V out | 250 kHz | loss comparison vs SiC-DAB in PLECS; no efficiency percenta… | PLECS simulation (hardware not confirmed) |

## Research gaps identified (supporting entry ids)

* **No published safe / constrained RL for an isolated DC-DC (DAB) converter.** The only safe-RL converter
  paper found is for a two-level VSC (L49, TIE 2024); DRL for DAB is efficiency-tuning without constraints
  (L20, L18-unverified); the 2025 review (L19) lists safe exploration as open. → `Safe_RL_Research` gap stands.
* **DAB digital twin with physical-parameter estimation and uncertainty bounds is not yet published for a DAB.**
  Published DAB twins predict voltage only (L03); one-cycle/PSO twins (L04), differentiable-simulation (L28),
  Bayesian/Laplace (L29), PINN (L33) and SNN (L43) estimators are all demonstrated on buck converters; the
  only DAB PINN estimator (L30, preprint; L05 ECCE 2025 title only) gives point estimates without
  uncertainty. L29 even reports that MOSFET Rds_on is weakly identifiable with normal sensing.
  → `Digital_Twin` + `Uncertainty_Quantification` contribution is open; L30/L05 must be cited as precedents.
* **MPC for DAB under parameter drift**: robust MPC under EPS (L15), parameter-less predictive control (L35),
  MPC with low-cost online L identification (L36), digital-twin-as-model MPC (L34), hybrid-PS MPC with
  online identification + Bayesian weight tuning at 1 kW (L01) and AI-model TPS control (L02) exist; none
  reports a ZVS-margin-aware or health-aware MPC at kW/800 V class. → `Adaptive_MPC` positioning.
* **SiC health indicators that decouple temperature from degradation inside a running converter**: gate-current
  dI/dt peak (L39), turn-off ringing minimum (L40), gate-oscillation amplitude (L12), Rds_on without current
  sensing (L14), body-diode drop (L13) are device-level or buck-level demonstrations; none is shown on a DAB
  bridge with ZVS transitions. Forecasting benchmark (L41) and physics-guided module models (L42) give the
  RUL layer. → `SiC_Health_Monitoring` must state device-level provenance of every indicator.
* **Active gate drive trade-off (loss vs dv/dt vs overshoot) is documented at 400–600 V / 40–200 A** (L21, L44,
  L45, L22) but not for 1200 V C3M devices at 800 V bus. → `Active_Gate_Drive`.
* **Integrated-leakage magnetics**: accurate analytical leakage estimation with air paths (L24, L48), coil
  arrangement at 150 W/40 kHz (L23), planar GaN DAB 3.3 kW/250 kHz in simulation (L57), Kiel planar 6.6 kW/50 kHz
  (L06). No published 100 kHz, 6.6 kW SiC DAB with leakage-integrated planar transformer was found. → `FEM_Magnetics`.
* **Efficiency benchmarks for the 6.6 kW class**: 98 % peak at 50 kHz (L06, abstract snippet), 98.8 % at
  20 kW/50 kHz TPS (L38, aggregator only), 97.8 % 5 kW (L46), TI CLLLC ~500 kHz 98 % (L07), GaN 6.6 kW OBC (L47),
  older SiC 6.6 kW OBCs 96–97 % (search snippets, not entered). A 100 kHz SiC phase-shift DAB must be compared
  with these frequency and topology differences stated. → `Research_Benchmarks`.
* **Physics-informed modelling**: hierarchical/topology-transferable networks (L31, L32, L09), neural ODE twins
  (L10), PINN-in-MPC (L55); L41/L43 show cost/accuracy limits. → `Physics_Informed_Models` should benchmark
  against L31/L09 rather than claim novelty of "physics-informed DAB model".

## Papers named in the research specification that could NOT be confirmed

1. **"DAB digital twin — IEEE Transactions on Instrumentation and Measurement 2025" (L03).** No TIM 2025 paper
   on a DAB digital twin was returned by any query (titles, DOI prefix `10.1109/TIM.2025`, topic). The
   closest real sources are: Bayindir et al., *Design and Analysis of Digital Twin Models for Dual Active
   Bridge*, **IECON 2024** (Xplore 10905834; XGBoost/DNN twins predicting output voltage — no parameter
   estimation) — now stored as L03 with corrected venue; and Liu/Qing/Chen, *One-Cycle Digital Twin-Based
   Multiparameter Identification…*, **TIM vol. 73, 2024** (DOI 10.1109/TIM.2024.3488158, buck converter) — L04.
   A TIM 2025 paper on a *grid-connected inverter* twin (DOI 10.1109/TIM.2025.3628417) was mentioned in one
   snippet but is not a DAB paper and was not entered.
2. **Kiel APEC 2025 "98 %" claim (L06).** In pass 1 the 98 % could not be tied to the Kiel paper. In pass 2 one
   search snippet of the Kiel repository PDF abstract read: "A 6.6 kW/50 kHz prototype with a 98% peak
   efficiency for 200 V to 800 V input voltage and 400 V output voltage is fabricated". The paper (Barzegarkhoo,
   Groon, Sengupta, Liserre, DOI 10.1109/APEC48143.2025.10977430) therefore exists and its abstract does state
   98 % — but the PDF could not be opened, the efficiency curve was not seen, and the journal version (L46,
   TPEL 2025) is summarised by ResearchGate with "5 kW prototype, 97.8 % peak". Status kept at
   *partially confirmed*; cite as "98 % peak claimed in abstract at 50 kHz" only.
3. **"Data-light parameter estimation for DAB converters using a PINN, Xie et al., ECCE 2025" (L05).** The title
   *Robust data-light parameter estimation for DAB converters with physics-informed neural network*, ECCE 2025
   pp. 1–7, appears only inside the reference list of a 2026 arXiv preprint; the first author's name was cut
   off, "Xie" is unconfirmed, and no Xplore record was returned. Closest accessible source: Dey & Mallik,
   arXiv 2502.17452 (L30), PINN estimating L and R_eq for an adaptive-TPS DAB.
   Two further pass-1 rows remain **not found**: L08 (*physics-enhanced hierarchical neural network*, DOI
   10.1109/TPEL.2025.3629881 — no record; closest real work is the ModNet/CirNet hierarchy of PE-GPT,
   arXiv 2403.14059) and L18 (*TD3 vs PI vs MPC for DAB on RTDS*, DOI 10.1007/s40998-025-01007-w — no record).

## What this database does not do
* It does not contain any full-text reading; abstracts quoted in `evidence` are search snippets.
* It does not rank papers; `strengths/limitations/research_gap_identified` are the author's reading of the
  snippet and are not peer-reviewed judgements.
* DOIs were never constructed from URL patterns; where a DOI was not shown, the field says so and gives a URL.

Validation command (run from this folder):
`python3 -c "import csv; rows=list(csv.DictReader(open('literature_2022_2026.csv'))); print(len(rows), set(len(r) for r in rows))"` → `57 {16}` on 2026-10-10.
