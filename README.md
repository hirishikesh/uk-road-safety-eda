# UK Road Safety EDA: what makes a collision serious? (2021–2025)

> Analysis of **513,801 police-reported collisions, 937,265 vehicles and 652,821 casualties** in Great Britain. It finds that *who* is involved and *what kind of road* it happens on predict severity far more than weather. Delivered as a notebook, a written report and a Power BI dashboard.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/hirishikesh/uk-road-safety-eda/blob/main/notebooks/uk_road_safety_eda.ipynb)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)](https://python.org)
[![Power BI](https://img.shields.io/badge/Power%20BI-PBIP-F2C811?logo=powerbi&logoColor=black)](powerbi/)
[![Data](https://img.shields.io/badge/Data-DfT%20STATS19-red)](https://www.gov.uk/government/statistical-data-sets/road-safety-open-data)

**Business question:** what factors most strongly predict how severe a road collision is in Great Britain, and how have collision patterns changed between 2021 and 2025?

| Deliverable | Where |
|---|---|
| Analysis notebook (16 figures, statistical tests, severity model) | [`notebooks/uk_road_safety_eda.ipynb`](notebooks/uk_road_safety_eda.ipynb) |
| Written report (Markdown + PDF) | [`reports/REPORT.md`](reports/REPORT.md) · [`reports/UK_Road_Safety_Report.pdf`](reports/UK_Road_Safety_Report.pdf) |
| Power BI dashboard (5 pages, star schema, 17 DAX measures) | [`powerbi/`](powerbi/README.md) |

---

## Key findings

| # | Finding | Number |
|---|---|---|
| 1 | **Vulnerable road users carry half the deaths.** Pedestrians, cyclists, motorcyclists and e-scooter riders | **40%** of casualties, **51%** of deaths |
| 2 | **Motorcycle involvement is the strongest single predictor** of a killed-or-seriously-injured (KSI) outcome | odds ratio **2.93** (95% CI 2.87–2.98) |
| 3 | **Rural roads are where people die.** | **33%** of collisions, **63%** of fatal collisions |
| 4 | **60 mph roads** (97% rural, 90% single carriageway) have the most severe crashes | KSI rate **36.5%**, against 23.6% at 30 mph |
| 5 | **Night crashes are deadlier.** Fatal collisions per 1,000 collisions | **41.1** at 04:00, against **7.9** at 08:00 |
| 6 | **Age drives severity.** Deaths per 1,000 casualties | **42.3** at 75+, against **11.0** at 17–24 |
| 7 | **Weather is a weak factor.** Cramér's V with severity | **0.016**, against 0.105 for urban/rural |
| 8 | **Crashes are flat but more severe.** Change from 2021 to 2025 | collisions **+0.4%**, adjusted KSI casualties **+13.3%** |

Two claims in the earlier draft did not survive the full analysis. That young adults are over-represented in fatal casualties confused volume with severity: young people are involved more often, while older people are more likely to die. That fine weather "proves" crashes are behavioural is a base-rate effect.

![Odds ratios](reports/figures/16_odds_ratios.png)

---

## Method

```
DfT CSVs (3 tables) ──► src/prepare_data.py ──► data/processed/*.pkl ──► notebook ──► figures, key_numbers.json ──► REPORT.md / PDF
   + data guide          decode codes, flags,      data/powerbi/*.csv ──────────────────► Power BI (PBIP) dashboard
                         join integrity checks
```

- **Explicit unit of analysis.** Road-environment questions are answered per *collision* and people questions per *casualty*. The original notebook labelled casualty rows with collision severity, which double-counts multi-casualty crashes.
- **Severity adjusted for the reporting change.** The share of collisions recorded via the injury-based CRASH system rose from 49.6% to 86.5%, which inflates "serious" counts. All KSI figures use DfT's per-record adjustment: `KSI = fatal + P(serious)`. About a fifth of the recorded KSI rise is this artefact.
- **Effect sizes, not p-values.** With n ≈ 500k every chi-square test is significant, so factors are ranked by bias-corrected Cramér's V.
- **Multivariable model.** A fractional logistic regression (binomial GLM on the adjusted KSI probability, HC1 robust standard errors) separates overlapping factors, for example rural roads that are also fast, dark and carry more motorcycles. Hold-out AUC is 0.67.
- **Honest scope.** These are severity rates given a collision, not risk per mile, because STATS19 has no exposure data. See the report's limitations section.

---

## Quickstart

```bash
git clone https://github.com/hirishikesh/uk-road-safety-eda
cd uk-road-safety-eda
pip install -r requirements.txt
python download_data.py          # ~255 MB from data.dft.gov.uk into data/raw/
python -m src.prepare_data       # cleans + joins -> data/processed/ and data/powerbi/
jupyter notebook notebooks/uk_road_safety_eda.ipynb
```

To rebuild the PDF report, run `python -m src.build_report_pdf`. It needs Edge or Chrome. To rebuild or open the dashboard, see [`powerbi/README.md`](powerbi/README.md).

## Repo structure

```
uk-road-safety-eda/
├── download_data.py              # fetch the DfT CSVs + data guide
├── src/
│   ├── labels.py                 # decode STATS19 codes with DfT's official guide
│   ├── prepare_data.py           # clean, derive flags, join checks, Power BI export
│   ├── analysis.py               # severity rates + CIs, Cramér's V, severity model, plot style
│   └── build_report_pdf.py       # REPORT.md -> PDF
├── notebooks/uk_road_safety_eda.ipynb
├── reports/
│   ├── REPORT.md / UK_Road_Safety_Report.pdf
│   ├── key_numbers.json          # every headline number, generated by the notebook
│   └── figures/                  # 16 figures
├── powerbi/
│   ├── UKRoadSafety.pbip         # open this in Power BI Desktop
│   ├── UKRoadSafety.SemanticModel/  UKRoadSafety.Report/
│   ├── build_pbip.py             # generates the project from the CSV schema
│   └── validate_pbip.py          # validates it against Microsoft's JSON schemas
├── data/                         # raw/, processed/, powerbi/ (gitignored)
└── requirements.txt
```

## Tech stack

Python (pandas, NumPy, SciPy, statsmodels, scikit-learn, matplotlib) · Jupyter · Power BI (PBIP: TMDL semantic model and PBIR report, DAX) · data from DfT STATS19 under the Open Government Licence.

## Author

**Hirishikesh Parthasarathy** · MSc Artificial Intelligence, University of Edinburgh
[LinkedIn](https://linkedin.com/in/phirishikeshh) · [GitHub](https://github.com/hirishikesh)
