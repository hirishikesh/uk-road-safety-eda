"""Decode STATS19 integer codes using DfT's official data guide (data/raw/data_guide.xlsx)."""
from functools import lru_cache
from pathlib import Path

import pandas as pd

GUIDE_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "data_guide.xlsx"
MISSING = "Missing / unknown"

# Codes the guide uses for "no information"; they are collapsed into one label.
_MISSING_LABELS = ("data missing or out of range", "unknown", "undefined", "not known")


@lru_cache(maxsize=1)
def _guide() -> pd.DataFrame:
    g = pd.read_excel(GUIDE_PATH, sheet_name="2024_code_list")
    g.columns = [c.strip().lower() for c in g.columns]
    g = g.rename(columns={"field name": "field", "code/format": "code"})
    return g


def text_code_map(field: str) -> dict[str, str]:
    """{code: label} for fields whose codes are strings, e.g. ONS district codes."""
    rows = _guide()[lambda g: g["field"] == field]
    return dict(zip(rows["code"].astype(str).str.strip(), rows["label"].astype(str).str.strip()))


def code_map(field: str, table: str | None = None) -> dict[int, str]:
    """Return {code: label} for a field, collapsing the various 'unknown' codes."""
    g = _guide().assign(code=lambda d: pd.to_numeric(d["code"], errors="coerce")).dropna(subset=["code"])
    rows = g[g["field"] == field]
    if table is not None:
        rows = rows[rows["table"] == table]
    mapping = {}
    for code, label in zip(rows["code"].astype(int), rows["label"]):
        if code in mapping:
            continue
        if pd.isna(label) or str(label).strip().lower().startswith(_MISSING_LABELS):
            label = MISSING
        mapping[code] = str(label).strip()
    return mapping


def decode(series: pd.Series, field: str, table: str | None = None) -> pd.Series:
    """Map integer codes to labels; anything not in the guide becomes MISSING."""
    return series.map(code_map(field, table)).fillna(MISSING)
