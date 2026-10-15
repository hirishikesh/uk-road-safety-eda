"""Shared helpers for the EDA notebook: severity rates, effect sizes, the severity model, plot style."""
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

from src.labels import MISSING

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "reports" / "figures"

# Palette: categorical slots 1-3, chart chrome and a one-hue sequential ramp
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#fcfcfb"
GREY_BAR = "#c3c2b7"
SEQ_BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def set_style() -> None:
    mpl.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"], "font.size": 10,
        "text.color": INK, "axes.labelcolor": INK_2, "axes.titlecolor": INK,
        "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.edgecolor": AXIS, "axes.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK_2, "ytick.labelcolor": INK_2,
        "legend.frameon": False, "lines.linewidth": 2,
        "figure.dpi": 110, "savefig.dpi": 150, "savefig.bbox": "tight",
    })


def save(fig, name: str) -> Path:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / f"{name}.png"
    fig.savefig(path)
    return path


# ── Rates ──────────────────────────────────────────────────────────────────────

def wilson_ci(k, n, z: float = 1.96):
    k, n = np.asarray(k, float), np.asarray(n, float)
    p = np.divide(k, n, out=np.zeros_like(k), where=n > 0)
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return centre - half, centre + half


def severity_rates(df: pd.DataFrame, by, min_n: int = 200, drop_missing: bool = True) -> pd.DataFrame:
    """Per group: n, adjusted KSI rate (%) with 95% CI, fatal rate per 1,000 with Wilson 95% CI.

    `df` is either collisions or casualties; both carry is_fatal and ksi_adjusted.
    """
    g = df.groupby(by, observed=True)
    out = pd.DataFrame({
        "n": g.size(),
        "fatal": g["is_fatal"].sum(),
        "ksi_rate": g["ksi_adjusted"].mean() * 100,
        "ksi_se": g["ksi_adjusted"].std() / np.sqrt(g.size()) * 100,
    })
    out["ksi_lo"] = out["ksi_rate"] - 1.96 * out["ksi_se"]
    out["ksi_hi"] = out["ksi_rate"] + 1.96 * out["ksi_se"]
    lo, hi = wilson_ci(out["fatal"], out["n"])
    out["fatal_per_1000"] = out["fatal"] / out["n"] * 1000
    out["fatal_lo"], out["fatal_hi"] = lo * 1000, hi * 1000
    out = out[out["n"] >= min_n]
    if drop_missing:
        idx = out.index if out.index.nlevels == 1 else out.index.get_level_values(0)
        out = out[~idx.isin([MISSING, "Other", "Unknown"])]
    return out.drop(columns="ksi_se")


def cramers_v(table: pd.DataFrame) -> tuple[float, float, float]:
    """Bias-corrected Cramér's V (Bergsma 2013), chi-square statistic and p-value."""
    chi2, p, _, _ = chi2_contingency(table)
    n = table.to_numpy().sum()
    r, k = table.shape
    phi2 = chi2 / n
    phi2c = max(0.0, phi2 - (k - 1) * (r - 1) / (n - 1))
    rc, kc = r - (r - 1) ** 2 / (n - 1), k - (k - 1) ** 2 / (n - 1)
    return float(np.sqrt(phi2c / min(kc - 1, rc - 1))), float(chi2), float(p)


def association_table(df: pd.DataFrame, factors: dict[str, str], target: str = "severity") -> pd.DataFrame:
    """Chi-square + Cramér's V of each factor against severity, ranked by effect size."""
    rows = []
    for col, label in factors.items():
        sub = df[~df[col].isin([MISSING])]
        tab = pd.crosstab(sub[col], sub[target])
        v, chi2, p = cramers_v(tab)
        rows.append({"factor": label, "levels": tab.shape[0], "n": int(tab.to_numpy().sum()),
                     "chi2": chi2, "dof": (tab.shape[0] - 1) * (tab.shape[1] - 1), "p_value": p,
                     "cramers_v": v})
    return pd.DataFrame(rows).sort_values("cramers_v", ascending=False).reset_index(drop=True)


# ── Plots ──────────────────────────────────────────────────────────────────────

def bar_rate(ax, tab: pd.DataFrame, value: str = "ksi_rate", lo: str = "ksi_lo", hi: str = "ksi_hi",
             order=None, highlight=None, fmt: str = "{:.1f}%", baseline: float | None = None,
             xlabel: str = "KSI rate (% of collisions, severity-adjusted)"):
    """Horizontal bars with 95% CI whiskers; `highlight` labels are drawn in orange, the rest blue."""
    tab = tab.loc[order] if order is not None else tab.sort_values(value)
    labels = [str(i) for i in tab.index]
    highlight = set(highlight or [])
    colors = [ORANGE if lab in highlight else BLUE for lab in labels]
    y = np.arange(len(tab))
    ax.barh(y, tab[value], color=colors, height=0.62, edgecolor=SURFACE, linewidth=2)
    ax.errorbar(tab[value], y, xerr=[tab[value] - tab[lo], tab[hi] - tab[value]],
                fmt="none", ecolor=INK_2, elinewidth=1, capsize=0)
    xmax = tab[hi].max() * 1.15
    for yi, val, top in zip(y, tab[value], tab[hi]):
        ax.text(top + xmax * 0.012, yi, fmt.format(val), va="center", fontsize=9, color=INK_2)
    if baseline is not None:
        ax.axvline(baseline, color=MUTED, linewidth=1)
        ax.text(baseline, -0.75, " overall", color=MUTED, fontsize=8, va="center")
    ax.set_yticks(y, labels)
    ax.set_xlim(0, xmax)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel(xlabel)
    return ax


def subtitle(ax, text: str) -> None:
    """Grey line under the (already set) axes title."""
    ax.set_title(ax.get_title(loc="left"), loc="left", pad=22)
    ax.text(0, 1.015, text, transform=ax.transAxes, fontsize=9, color=INK_2, va="bottom")


# ── Severity model ─────────────────────────────────────────────────────────────

MODEL_TERMS = {
    "speed_limit_label": "30 mph",
    "urban_rural": "Urban",
    "light": "Daylight",
    "weather": "Fine",
    "surface": "Dry",
    "road_type": "Single carriageway",
    "junction": "Not at junction",
    "time_band": "10-15 Daytime",
    "vehicles": "2",
    "year": 2021,
}
MODEL_FLAGS = ["is_weekend", "pedestrian_casualty", "involves_motorcycle", "involves_pedal_cycle",
               "involves_hgv", "involves_bus", "involves_escooter", "young_driver", "older_driver"]


def model_frame(col: pd.DataFrame) -> pd.DataFrame:
    """Collision-level design frame with simplified, complete categorical predictors."""
    d = col[col["speed_limit_label"].ne(MISSING) & col["urban_rural"].ne(MISSING)
            & col["light"].ne(MISSING)].copy()
    d["surface"] = d["road_surface"].map({"Dry": "Dry", "Wet or damp": "Wet",
                                          "Frost or ice": "Ice or snow", "Snow": "Ice or snow"}).fillna("Other / unknown")
    d["junction"] = np.where(d["junction_detail"].eq("Not at junction or within 20 metres"), "Not at junction",
                             np.where(d["junction_detail"].eq(MISSING), "Unknown", "At junction"))
    d["road_type"] = d["road_type"].where(d["road_type"].isin(
        ["Single carriageway", "Dual carriageway", "Roundabout", "One way street", "Slip road"]), "Other / unknown")
    d["weather"] = d["weather"].replace({MISSING: "Other / unknown", "Other": "Other / unknown"})
    d["light"] = d["light"].replace({"Dark - lighting unknown": "Dark - unlit"})
    d["vehicles"] = np.where(d["number_of_vehicles"] >= 3, "3+", d["number_of_vehicles"].clip(1, 3).astype(str))
    d["y"] = d["ksi_adjusted"].clip(0, 1)
    return d


def model_formula() -> str:
    terms = [f"C({c}, Treatment({ref!r}))" for c, ref in MODEL_TERMS.items()]
    return "y ~ " + " + ".join(terms + MODEL_FLAGS)


def fit_severity_model(d: pd.DataFrame):
    """Fractional logit (Papke & Wooldridge): binomial GLM on the severity-adjusted KSI
    probability, with heteroskedasticity-robust standard errors."""
    import statsmodels.formula.api as smf
    import statsmodels.api as sm
    return smf.glm(model_formula(), data=d, family=sm.families.Binomial()).fit(cov_type="HC1")


def odds_ratio_table(result) -> pd.DataFrame:
    ci = result.conf_int()
    t = pd.DataFrame({"odds_ratio": np.exp(result.params), "lo": np.exp(ci[0]), "hi": np.exp(ci[1]),
                      "p_value": result.pvalues}).drop(index="Intercept")
    t.index = [_pretty_term(i) for i in t.index]
    return t


def _pretty_term(term: str) -> str:
    if term.startswith("C("):
        var = term[2:term.index(",")]
        level = term.split("[T.")[1].rstrip("]")
        names = {"speed_limit_label": "Speed limit", "urban_rural": "Area", "light": "Light",
                 "weather": "Weather", "surface": "Surface", "road_type": "Road type",
                 "junction": "Junction", "time_band": "Time", "vehicles": "Vehicles involved", "year": "Year"}
        return f"{names.get(var, var)}: {level}"
    return {"is_weekend": "Weekend", "pedestrian_casualty": "Pedestrian hit",
            "involves_motorcycle": "Motorcycle involved", "involves_pedal_cycle": "Pedal cycle involved",
            "involves_hgv": "HGV involved", "involves_bus": "Bus involved",
            "involves_escooter": "E-scooter involved", "young_driver": "Driver aged 17-24",
            "older_driver": "Driver aged 75+"}.get(term, term)
