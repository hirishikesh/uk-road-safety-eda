# UK Road Safety EDA (2020–2024)

**Exploratory Data Analysis of 400,000+ road accident records across Great Britain**

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)](https://python.org)
[![pandas](https://img.shields.io/badge/pandas-2.0+-green?logo=pandas)](https://pandas.pydata.org)
[![Jupyter](https://img.shields.io/badge/Notebook-Colab-orange?logo=googlecolab)](YOUR_COLAB_LINK_HERE)
[![Data Source](https://img.shields.io/badge/Data-GOV.UK-red)](https://www.gov.uk/government/statistics/road-safety-data)

---

## Business Question

**What factors most strongly predict road accident severity in Great Britain, and how have accident patterns changed between 2020 and 2024?**

---

## Dataset

Source: [UK Department for Transport — Road Safety Data](https://www.gov.uk/government/statistics/road-safety-data)  
Three joinable tables: **Collisions · Vehicles · Casualties**  
Joined on: `accident_index`

| File | Rows (approx) | Size |
|---|---|---|
| Collisions | ~160,000 | 18.6 MB/yr |
| Vehicles | ~280,000 | 19.3 MB/yr |
| Casualties | ~200,000 | 9.9 MB/yr |

All data is official government statistics, publicly available under the Open Government Licence.

---

## Key Findings

> *(Update these once your analysis is complete)*

1. **Finding 1** — e.g. "Accidents are 40% more likely to result in serious injury on rural A-roads than urban roads, despite lower volume"
2. **Finding 2** — e.g. "Friday 17:00–19:00 accounts for the highest accident concentration across all 5 years"
3. **Finding 3** — e.g. "Young drivers (17–24) are over-represented in fatal accidents by 2.3× relative to their share of licence holders"

---

## Analysis Structure

```
01_data_loading.ipynb       — Load and join the 3 tables, initial inspection
02_data_cleaning.ipynb      — Handle nulls, encode categoricals, validate joins
03_eda_collisions.ipynb     — Temporal, geographic, and environmental analysis
04_eda_casualties.ipynb     — Severity, demographics, road user type analysis
05_statistical_tests.ipynb  — Hypothesis testing and correlation analysis
06_insights_summary.ipynb   — Business recommendations and visualisation summary
```

Or as a single notebook: `uk_road_safety_eda.ipynb`

---

## How to Run

### Option 1 — Google Colab (recommended)
Click the Colab badge above. No installation required.

### Option 2 — Local
```bash
git clone https://github.com/hirishikesh/uk-road-safety-eda
cd uk-road-safety-eda
pip install -r requirements.txt
jupyter notebook
```

**requirements.txt**
```
pandas>=2.0
numpy>=1.24
matplotlib>=3.7
seaborn>=0.12
scipy>=1.10
jupyter
```

---

## Repo Structure

```
uk-road-safety-eda/
├── notebooks/
│   └── uk_road_safety_eda.ipynb
├── data/
│   └── .gitkeep              ← data files not tracked (see download script)
├── download_data.py          ← script to fetch data directly from gov.uk
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Skills Demonstrated

- Multi-table dataset joining and merging (pandas merge)
- Large-scale data cleaning and preprocessing (400k+ rows)
- Temporal time series analysis
- Statistical hypothesis testing (chi-square, correlation significance)
- Data visualisation (matplotlib, seaborn)
- Business insight generation from raw government data

---

## Author

**Hirishikesh Parthasarathy**  
MSc Artificial Intelligence, University of Edinburgh  
[LinkedIn](https://linkedin.com/in/phirishikeshh) · [GitHub](https://github.com/hirishikesh)
