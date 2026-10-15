"""Generate the Power BI Project (PBIP: TMDL semantic model + PBIR report) for the dashboard.

Reads the CSV headers/dtypes in data/powerbi/ (run `python -m src.prepare_data` first) and writes
    powerbi/UKRoadSafety.pbip
    powerbi/UKRoadSafety.SemanticModel/   (TMDL)
    powerbi/UKRoadSafety.Report/          (PBIR)

Usage:
    python powerbi/build_pbip.py                 # DataFolder = this repo's data/powerbi/
    python powerbi/build_pbip.py --data-folder "D:/somewhere/powerbi/"
"""
import argparse
import json
import shutil
import uuid
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
NAME = "UKRoadSafety"
SM_DIR = HERE / f"{NAME}.SemanticModel"
RPT_DIR = HERE / f"{NAME}.Report"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
VISUAL_SCHEMA = f"{SCHEMA}/item/report/definition/visualContainer/2.10.0/schema.json"
NS = uuid.UUID("6f1c2b8e-2d0a-4b5e-9a57-3e1f9c1d7a42")

# Palette (matches the notebook figures)
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK_2, PAGE_BG = "#0b0b0b", "#52514e", "#F4F4F1"
SEQ_LO, SEQ_HI = "#cde2fb", "#0d366b"


def tag(*parts: str) -> str:
    """Deterministic lineage tag so regenerating does not churn the files."""
    return str(uuid.uuid5(NS, "/".join(parts)))


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, obj) -> None:
    write(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


# ══════════════════════════════════════════════════════════════════════════════
# Semantic model (TMDL)
# ══════════════════════════════════════════════════════════════════════════════

TABLES = ["dim_date", "fact_collisions", "fact_casualties", "fact_vehicles"]

HIDDEN = {"collision_index", "vehicle_reference", "casualty_reference", "latitude", "longitude",
          "is_fatal", "is_serious", "adj_serious", "ksi_adjusted", "day_num", "month_num"}
SORT_BY = {("dim_date", "month"): "month_num", ("dim_date", "day_of_week"): "day_num"}

MEASURES = {
    "fact_collisions": [
        ("Collisions", "COUNTROWS ( fact_collisions )", "#,0", "Collisions"),
        ("Fatal Collisions", "SUM ( fact_collisions[is_fatal] )", "#,0", "Collisions"),
        ("KSI Collisions (adj)", "SUM ( fact_collisions[ksi_adjusted] )", "#,0", "Collisions"),
        ("KSI Rate (adj)", "DIVIDE ( [KSI Collisions (adj)], [Collisions] )", "0.0%", "Collisions"),
        ("KSI Rate (recorded)",
         'DIVIDE ( CALCULATE ( [Collisions], fact_collisions[severity] <> "Slight" ), [Collisions] )',
         "0.0%", "Collisions"),
        ("Fatal per 1,000 Collisions", "DIVIDE ( [Fatal Collisions], [Collisions] ) * 1000", "0.0", "Collisions"),
        ("Injury-based Reporting %",
         'DIVIDE ( CALCULATE ( [Collisions], fact_collisions[reporting_system] = "Injury-based (CRASH)" ), [Collisions] )',
         "0.0%", "Data quality"),
        ("Collisions YoY %",
         "VAR cur = [Collisions]\n"
         "VAR prev = CALCULATE ( [Collisions], DATEADD ( dim_date[date], -1, YEAR ) )\n"
         "RETURN IF ( NOT ISBLANK ( prev ), DIVIDE ( cur - prev, prev ) )",
         "+0.0%;-0.0%;0.0%", "Collisions"),
    ],
    "fact_casualties": [
        ("Casualties", "COUNTROWS ( fact_casualties )", "#,0", "Casualties"),
        ("Fatalities", "SUM ( fact_casualties[is_fatal] )", "#,0", "Casualties"),
        ("KSI Casualties (adj)", "SUM ( fact_casualties[ksi_adjusted] )", "#,0", "Casualties"),
        ("Casualty KSI Rate (adj)", "DIVIDE ( [KSI Casualties (adj)], [Casualties] )", "0.0%", "Casualties"),
        ("Deaths per 1,000 Casualties", "DIVIDE ( [Fatalities], [Casualties] ) * 1000", "0.0", "Casualties"),
        ("Share of Casualties",
         "DIVIDE ( [Casualties], CALCULATE ( [Casualties], ALLSELECTED ( fact_casualties[road_user] ) ) )",
         "0.0%", "Casualties"),
        ("Share of Fatalities",
         "DIVIDE ( [Fatalities], CALCULATE ( [Fatalities], ALLSELECTED ( fact_casualties[road_user] ) ) )",
         "0.0%", "Casualties"),
    ],
    "fact_vehicles": [
        ("Vehicles", "COUNTROWS ( fact_vehicles )", "#,0", "Vehicles"),
        ("Driver Collision KSI Rate (adj)",
         "AVERAGEX ( FILTER ( fact_vehicles, fact_vehicles[is_motor_vehicle] = 1 ),\n"
         "    RELATED ( fact_collisions[ksi_adjusted] ) )",
         "0.0%", "Vehicles"),
    ],
}

RELATIONSHIPS = [
    ("fact_collisions", "date", "dim_date", "date"),
    ("fact_casualties", "collision_index", "fact_collisions", "collision_index"),
    ("fact_vehicles", "collision_index", "fact_collisions", "collision_index"),
]


def _column_types(csv: Path) -> dict[str, str]:
    sample = pd.read_csv(csv, low_memory=False)
    types = {}
    for col, dt in sample.dtypes.items():
        if col == "date":
            types[col] = "dateTime"
        elif pd.api.types.is_integer_dtype(dt):
            types[col] = "int64"
        elif pd.api.types.is_float_dtype(dt):
            types[col] = "double"
        else:
            types[col] = "string"
    return types


M_TYPES = {"dateTime": "type date", "int64": "Int64.Type", "double": "type number", "string": "type text"}
FORMATS = {"dateTime": "dd/mm/yyyy", "int64": "0", "double": "0.##"}


def _indent(text: str, tabs: int) -> str:
    return "\n".join("\t" * tabs + line for line in text.splitlines())


def table_tmdl(name: str, types: dict[str, str]) -> str:
    out = [f"table {name}", f"\tlineageTag: {tag(name)}"]
    if name == "dim_date":
        out.append("\tdataCategory: Time")
    out.append("")

    for m_name, expr, fmt, folder in MEASURES.get(name, []):
        if "\n" in expr:
            out.append(f"\tmeasure '{m_name}' =")
            out.append(_indent(expr, 3))
        else:
            out.append(f"\tmeasure '{m_name}' = {expr}")
        out += [f"\t\tformatString: {fmt}", f"\t\tdisplayFolder: {folder}",
                f"\t\tlineageTag: {tag(name, 'measure', m_name)}", ""]

    for col, dtype in types.items():
        is_key = name == "dim_date" and col == "date"
        summarize = "none" if dtype in ("string", "dateTime") or col in ("year", "hour", "speed_limit") \
            or col.startswith(("is_", "involves_", "month", "day", "age", "imd", "high_", "number_")) else "sum"
        out.append(f"\tcolumn {col}")
        out.append(f"\t\tdataType: {dtype}")
        if is_key:
            out.append("\t\tisKey")
        if dtype in FORMATS:
            out.append(f"\t\tformatString: {FORMATS[dtype]}")
        if col in HIDDEN:
            out.append("\t\tisHidden")
        out += [f"\t\tlineageTag: {tag(name, col)}", f"\t\tsummarizeBy: {summarize}", f"\t\tsourceColumn: {col}"]
        if (name, col) in SORT_BY:
            out.append(f"\t\tsortByColumn: {SORT_BY[(name, col)]}")
        out += ["", "\t\tannotation SummarizationSetBy = Automatic", ""]
        if dtype == "dateTime":
            out[-1:] = ["", "\t\tannotation UnderlyingDateTimeDataType = Date", ""]

    type_list = ", ".join(f'{{"{c}", {M_TYPES[t]}}}' for c, t in types.items())
    m = (
        "let\n"
        f'    Source = Csv.Document(File.Contents(DataFolder & "{name}.csv"), '
        "[Delimiter=\",\", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),\n"
        "    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),\n"
        f'    Typed = Table.TransformColumnTypes(Headers, {{{type_list}}}, "en-US")\n'
        "in\n"
        "    Typed"
    )
    out += [f"\tpartition {name} = m", "\t\tmode: import", "\t\tsource =", _indent(m, 4), "",
            "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(out)


def build_semantic_model(data_folder: str) -> None:
    defs = SM_DIR / "definition"
    write_json(SM_DIR / "definition.pbism", {
        "$schema": f"{SCHEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}})
    write(defs / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n\n")
    write(defs / "model.tmdl", "\n".join([
        "model Model",
        "\tculture: en-GB",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tdiscourageImplicitMeasures",
        "\tsourceQueryCulture: en-GB",
        "\tdataAccessOptions",
        "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull",
        "",
        "annotation __PBI_TimeIntelligenceEnabled = 0",
        "",
        f"annotation PBI_QueryOrder = {json.dumps(['DataFolder'] + TABLES)}",
        "",
        *[f"ref table {t}" for t in TABLES],
        "",
    ]))
    folder = data_folder.replace("\\", "/").rstrip("/") + "/"
    write(defs / "expressions.tmdl", "\n".join([
        "/// Folder containing the CSVs written by `python -m src.prepare_data` (must end with a slash)",
        f'expression DataFolder = "{folder}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
        f"\tlineageTag: {tag('DataFolder')}",
        "",
        "\tannotation PBI_ResultType = Text",
        "",
    ]))
    rels = []
    for f_tab, f_col, t_tab, t_col in RELATIONSHIPS:
        rels += [f"relationship {tag('rel', f_tab, t_tab)}", f"\tfromColumn: {f_tab}.{f_col}",
                 f"\ttoColumn: {t_tab}.{t_col}", ""]
    write(defs / "relationships.tmdl", "\n".join(rels))

    for t in TABLES:
        csv = ROOT / "data" / "powerbi" / f"{t}.csv"
        write(defs / "tables" / f"{t}.tmdl", table_tmdl(t, _column_types(csv)))


# ══════════════════════════════════════════════════════════════════════════════
# Report (PBIR)
# ══════════════════════════════════════════════════════════════════════════════

def lit(value) -> dict:
    """PBIR literal: strings are single-quoted, numbers carry a D suffix, booleans lowercase."""
    if isinstance(value, bool):
        v = "true" if value else "false"
    elif isinstance(value, (int, float)):
        v = f"{value}D"
    else:
        v = "'" + str(value).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": v}}}


def color(hex_: str) -> dict:
    return {"solid": {"color": lit(hex_)}}


def col(entity: str, prop: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def meas(entity: str, prop: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def ref(field: dict) -> str:
    inner = field.get("Column") or field.get("Measure")
    return f"{inner['Expression']['SourceRef']['Entity']}.{inner['Property']}"


def proj(field: dict, display: str | None = None, active: bool = False) -> dict:
    p = {"field": field, "queryRef": ref(field),
         "nativeQueryRef": display or (field.get("Column") or field.get("Measure"))["Property"]}
    if display:
        p["displayName"] = display
    if active:
        p["active"] = True
    return p


class Page:
    def __init__(self, name: str, display: str, title: str, subtitle: str):
        self.name, self.display = name, display
        self.visuals: list[dict] = []
        self.z = 0
        self.textbox(24, 12, 1232, 64, [
            [{"value": title, "textStyle": {"fontWeight": "bold", "fontSize": "20pt", "color": INK}}],
            [{"value": subtitle, "textStyle": {"fontSize": "10pt", "color": INK_2}}],
        ], name="header")

    # ── containers ─────────────────────────────────────────────────────────────
    def _add(self, vname: str, x, y, w, h, visual: dict, title: str | None = None) -> None:
        self.z += 1000
        container = {
            "$schema": VISUAL_SCHEMA,
            "name": f"{self.name}_{vname}"[:50],
            "position": {"x": x, "y": y, "z": self.z, "height": h, "width": w, "tabOrder": self.z},
            "visual": visual,
        }
        if title is not None:
            visual.setdefault("visualContainerObjects", {})["title"] = [{"properties": {
                "show": lit(True), "text": lit(title), "fontSize": lit(11), "bold": lit(True),
                "fontColor": color(INK)}}]
        self.visuals.append(container)

    def textbox(self, x, y, w, h, paragraphs: list[list[dict]], name: str) -> None:
        self._add(name, x, y, w, h, {
            "visualType": "textbox",
            "objects": {"general": [{"properties": {"paragraphs": [{"textRuns": runs} for runs in paragraphs]}}]},
            "visualContainerObjects": {"background": [{"properties": {"show": lit(False)}}]},
        })

    def slicer(self, name, x, y, w, field: dict, title: str, h=56) -> None:
        self._add(name, x, y, w, h, {
            "visualType": "slicer",
            "query": {"queryState": {"Values": {"projections": [proj(field, active=True)]}}},
            "objects": {
                "data": [{"properties": {"mode": lit("Dropdown")}}],
                "header": [{"properties": {"show": lit(True), "text": lit(title)}}],
            },
            "drillFilterOtherVisuals": True,
        })

    def card(self, name, x, y, w, h, measure: dict, label: str) -> None:
        self._add(name, x, y, w, h, {
            "visualType": "card",
            "query": {"queryState": {"Values": {"projections": [proj(measure, label)]}}},
            "objects": {
                "labels": [{"properties": {"fontSize": lit(24), "color": color(INK), "labelDisplayUnits": lit(1)}}],
                "categoryLabels": [{"properties": {"show": lit(True), "fontSize": lit(10), "color": color(INK_2)}}],
            },
            "drillFilterOtherVisuals": True,
        })

    def chart(self, name, vtype, x, y, w, h, title, category: dict, values: list[tuple[dict, str]],
              series: dict | None = None, sort: tuple[dict, str] | None = None,
              colors: list[str] | None = None, labels: bool = True) -> None:
        state = {"Category": {"projections": [proj(category, active=True)]},
                 "Y": {"projections": [proj(f, d) for f, d in values]}}
        if series is not None:
            state["Series"] = {"projections": [proj(series)]}
        query = {"queryState": state}
        if sort is not None:
            query["sortDefinition"] = {"sort": [{"field": sort[0], "direction": sort[1]}], "isDefaultSort": True}
        objects = {"legend": [{"properties": {"show": lit(series is not None or len(values) > 1),
                                              "position": lit("Top")}}]}
        if labels:
            objects["labels"] = [{"properties": {"show": lit(True), "color": color(INK_2), "fontSize": lit(8)}}]
        if colors:
            objects["dataPoint"] = [
                {"properties": {"fill": color(c)}, "selector": {"metadata": ref(f)}}
                for (f, _), c in zip(values, colors)]
        self._add(name, x, y, w, h, {"visualType": vtype, "query": query, "objects": objects,
                                     "drillFilterOtherVisuals": True}, title)

    def table(self, name, x, y, w, h, title, fields: list[tuple[dict, str]], sort: tuple[dict, str]) -> None:
        self._add(name, x, y, w, h, {
            "visualType": "tableEx",
            "query": {"queryState": {"Values": {"projections": [proj(f, d) for f, d in fields]}},
                      "sortDefinition": {"sort": [{"field": sort[0], "direction": sort[1]}],
                                         "isDefaultSort": True}},
            "drillFilterOtherVisuals": True,
        }, title)

    def heatmap(self, name, x, y, w, h, title, rows: dict, columns: dict, value: dict) -> None:
        self._add(name, x, y, w, h, {
            "visualType": "pivotTable",
            "query": {"queryState": {
                "Rows": {"projections": [proj(rows, active=True)]},
                "Columns": {"projections": [proj(columns, active=True)]},
                "Values": {"projections": [proj(value)]},
            }},
            "objects": {
                "values": [{
                    "properties": {"backColor": {"solid": {"color": {"expr": {"FillRule": {
                        "Input": value,
                        "FillRule": {"linearGradient2": {
                            "min": {"color": {"Literal": {"Value": f"'{SEQ_LO}'"}}},
                            "max": {"color": {"Literal": {"Value": f"'{SEQ_HI}'"}}},
                            "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'asZero'"}}},
                        }},
                    }}}}}},
                    "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": ref(value)},
                }],
                "subTotals": [{"properties": {"rowSubtotals": lit(False), "columnSubtotals": lit(False)}}],
                "grid": [{"properties": {"gridVertical": lit(False), "gridHorizontal": lit(False)}}],
            },
            "drillFilterOtherVisuals": True,
        }, title)

    def standard_slicers(self, y=84) -> None:
        self.slicer("s_year", 24, y, 200, col("dim_date", "year"), "Year")
        self.slicer("s_country", 236, y, 200, col("fact_collisions", "country"), "Country")
        self.slicer("s_area", 448, y, 200, col("fact_collisions", "urban_rural"), "Urban / rural")
        self.slicer("s_force", 660, y, 260, col("fact_collisions", "police_force"), "Police force")
        self.slicer("s_road_class", 932, y, 200, col("fact_collisions", "road_class"), "Road class")

    def write(self, pages_dir: Path) -> None:
        write_json(pages_dir / self.name / "page.json", {
            "$schema": f"{SCHEMA}/item/report/definition/page/2.1.0/schema.json",
            "name": self.name, "displayName": self.display, "displayOption": "FitToPage",
            "height": 720, "width": 1280,
            "objects": {"background": [{"properties": {"color": color(PAGE_BG), "transparency": lit(0)}}]},
        })
        for v in self.visuals:
            write_json(pages_dir / self.name / "visuals" / v["name"] / "visual.json", v)


def build_pages() -> list[Page]:
    C, K, V, D = "fact_collisions", "fact_casualties", "fact_vehicles", "dim_date"
    pages = []

    # ── Overview ───────────────────────────────────────────────────────────────
    p = Page("overview", "Overview", "UK Road Safety 2021–2025",
             "Police-reported injury collisions in Great Britain (DfT STATS19). KSI = killed or seriously "
             "injured, using DfT's severity adjustment for the move to injury-based reporting.")
    p.standard_slicers()
    kpis = [(meas(C, "Collisions"), "Collisions"), (meas(K, "Casualties"), "Casualties"),
            (meas(K, "Fatalities"), "Fatalities"), (meas(K, "KSI Casualties (adj)"), "KSI casualties (adj)"),
            (meas(C, "KSI Rate (adj)"), "KSI rate of collisions (adj)")]
    w = (1232 - 4 * 16) / 5
    for i, (m, label) in enumerate(kpis):
        p.card(f"kpi{i}", 24 + i * (w + 16), 152, w, 92, m, label)
    p.chart("monthly", "lineChart", 24, 260, 760, 220, "Collisions per month",
            col(D, "year_month"), [(meas(C, "Collisions"), "Collisions")], labels=False,
            sort=(col(D, "year_month"), "Ascending"))
    p.chart("ksi_year", "clusteredColumnChart", 800, 260, 456, 220,
            "KSI share of collisions: recorded vs severity-adjusted",
            col(D, "year"), [(meas(C, "KSI Rate (recorded)"), "Recorded"), (meas(C, "KSI Rate (adj)"), "Adjusted")],
            sort=(col(D, "year"), "Ascending"), colors=[ORANGE, BLUE])
    p.chart("users_ksi", "clusteredBarChart", 24, 496, 600, 208,
            "Chance a casualty is killed or seriously injured, by road user",
            col(K, "road_user"), [(meas(K, "Casualty KSI Rate (adj)"), "KSI rate")],
            sort=(meas(K, "Casualty KSI Rate (adj)"), "Descending"))
    p.chart("speed_ksi", "clusteredBarChart", 640, 496, 616, 208, "KSI rate by speed limit",
            col(C, "speed_limit_label"), [(meas(C, "KSI Rate (adj)"), "KSI rate")],
            sort=(col(C, "speed_limit_label"), "Ascending"))
    pages.append(p)

    # ── When ───────────────────────────────────────────────────────────────────
    p = Page("when", "When", "When collisions happen — and when they are worst",
             "Volume follows traffic; severity peaks at night when roads are empty, fast and dark.")
    p.standard_slicers()
    p.heatmap("heat", 24, 152, 1232, 270, "Collisions by day of week and hour",
              col(D, "day_of_week"), col(C, "hour"), meas(C, "Collisions"))
    p.chart("hour_volume", "clusteredColumnChart", 24, 438, 600, 266, "Collisions by hour of day",
            col(C, "hour"), [(meas(C, "Collisions"), "Collisions")], sort=(col(C, "hour"), "Ascending"), labels=False)
    p.chart("hour_fatal", "lineChart", 640, 438, 616, 266, "Fatal collisions per 1,000 collisions, by hour",
            col(C, "hour"), [(meas(C, "Fatal per 1,000 Collisions"), "Fatal per 1,000")],
            sort=(col(C, "hour"), "Ascending"), colors=[ORANGE], labels=False)
    pages.append(p)

    # ── Where ──────────────────────────────────────────────────────────────────
    p = Page("where", "Where", "Where collisions are most severe",
             "Rural, high-speed and unlit roads produce the most severe outcomes; weather matters little.")
    p.standard_slicers()
    p.chart("speed_area", "clusteredColumnChart", 24, 152, 600, 270,
            "Fatal collisions per 1,000 by speed limit: urban vs rural",
            col(C, "speed_limit_label"), [(meas(C, "Fatal per 1,000 Collisions"), "Fatal per 1,000")],
            series=col(C, "urban_rural"), sort=(col(C, "speed_limit_label"), "Ascending"))
    p.chart("light", "clusteredBarChart", 640, 152, 300, 270, "Fatal per 1,000 by light",
            col(C, "light"), [(meas(C, "Fatal per 1,000 Collisions"), "Fatal per 1,000")],
            sort=(meas(C, "Fatal per 1,000 Collisions"), "Descending"))
    p.chart("weather", "clusteredBarChart", 956, 152, 300, 270, "KSI rate by weather",
            col(C, "weather"), [(meas(C, "KSI Rate (adj)"), "KSI rate")],
            sort=(meas(C, "KSI Rate (adj)"), "Descending"))
    p.chart("road_type", "clusteredBarChart", 24, 438, 600, 266, "KSI rate by road type",
            col(C, "road_type"), [(meas(C, "KSI Rate (adj)"), "KSI rate")],
            sort=(meas(C, "KSI Rate (adj)"), "Descending"))
    p.chart("force", "clusteredBarChart", 640, 438, 616, 266, "KSI rate by police force (scroll)",
            col(C, "police_force"), [(meas(C, "KSI Rate (adj)"), "KSI rate")],
            sort=(meas(C, "KSI Rate (adj)"), "Descending"))
    pages.append(p)

    # ── Who ────────────────────────────────────────────────────────────────────
    p = Page("who", "Who", "Who is hurt",
             "Vulnerable road users carry half the deaths; the chance of dying climbs steeply with age.")
    p.standard_slicers()
    p.chart("user_share", "clusteredBarChart", 24, 152, 600, 270, "Share of casualties vs share of deaths",
            col(K, "road_user"), [(meas(K, "Share of Casualties"), "Share of casualties"),
                                  (meas(K, "Share of Fatalities"), "Share of deaths")],
            sort=(meas(K, "Share of Fatalities"), "Descending"), colors=[BLUE, ORANGE])
    p.table("user_table", 640, 152, 616, 270, "Road-user summary",
            [(col(K, "road_user"), "Road user"), (meas(K, "Casualties"), "Casualties"),
             (meas(K, "Fatalities"), "Deaths"), (meas(K, "Casualty KSI Rate (adj)"), "KSI rate (adj)"),
             (meas(K, "Deaths per 1,000 Casualties"), "Deaths per 1,000")],
            sort=(meas(K, "Fatalities"), "Descending"))
    p.chart("age_volume", "clusteredColumnChart", 24, 438, 400, 266, "Casualties by age",
            col(K, "age_group"), [(meas(K, "Casualties"), "Casualties")],
            sort=(col(K, "age_group"), "Ascending"), labels=False)
    p.chart("age_fatal", "lineChart", 440, 438, 400, 266, "Deaths per 1,000 casualties, by age",
            col(K, "age_group"), [(meas(K, "Deaths per 1,000 Casualties"), "Deaths per 1,000")],
            sort=(col(K, "age_group"), "Ascending"), colors=[ORANGE])
    p.chart("driver_age", "clusteredBarChart", 856, 438, 400, 266,
            "KSI rate of collisions by motor-vehicle driver age",
            col(V, "driver_age_group"), [(meas(V, "Driver Collision KSI Rate (adj)"), "KSI rate")],
            sort=(col(V, "driver_age_group"), "Ascending"))
    pages.append(p)

    # ── Notes ──────────────────────────────────────────────────────────────────
    p = Page("notes", "Notes", "About this dashboard", "Definitions, method and caveats.")
    bullets = [
        ("Source. ", "Department for Transport STATS19 open data, 'last 5 years' collision, vehicle and "
                     "casualty files (2021–2025), decoded with DfT's 2025 data guide."),
        ("KSI (adj). ", "Killed or seriously injured. Police forces are moving to the injury-based CRASH "
                        "system, which records more injuries as serious. DfT publishes the probability that each "
                        "record would be 'serious' under injury-based reporting; KSI (adj) = fatal + that probability."),
        ("Rates are severity, not risk. ", "STATS19 has no traffic volumes, so a rate here is the severity of a "
                                          "collision given that it happened, not the risk per mile travelled."),
        ("Filters. ", "Year, country, area, police force and road class filter collisions and, through them, "
                      "casualties and vehicles. Road-user and age fields filter casualty measures only."),
        ("Refresh. ", "python download_data.py && python -m src.prepare_data, then Refresh in Power BI. "
                      "If the CSVs live elsewhere, change the DataFolder parameter (Transform data > Edit parameters)."),
        ("Full analysis. ", "notebooks/uk_road_safety_eda.ipynb and reports/REPORT.md in the GitHub repo."),
    ]
    p.textbox(24, 100, 1232, 520, [
        [{"value": head, "textStyle": {"fontWeight": "bold", "fontSize": "11pt"}},
         {"value": body, "textStyle": {"fontSize": "11pt"}}] for head, body in bullets
    ], name="notes_body")
    pages.append(p)
    return pages


THEME = {
    "name": "UK Road Safety",
    "dataColors": [BLUE, ORANGE, AQUA, "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
    "background": "#FFFFFF",
    "foreground": INK,
    "tableAccent": BLUE,
}


def build_report() -> None:
    write_json(RPT_DIR / "definition.pbir", {
        "$schema": f"{SCHEMA}/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}},
    })
    defs = RPT_DIR / "definition"
    write_json(defs / "version.json", {
        "$schema": f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    version_at_import = {"visual": "1.8.95", "report": "2.0.95", "page": "1.3.95"}
    write_json(defs / "report.json", {
        "$schema": f"{SCHEMA}/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "CY24SU10", "reportVersionAtImport": version_at_import, "type": "SharedResources"},
            "customTheme": {"name": "UKRoadSafetyTheme.json", "reportVersionAtImport": version_at_import,
                            "type": "RegisteredResources"},
        },
        "objects": {"section": [{"properties": {"verticalAlignment": lit("Top")}}]},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": "UKRoadSafetyTheme.json", "path": "UKRoadSafetyTheme.json", "type": "CustomTheme"}]},
        ],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                     "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                     "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True},
    })
    base_theme = HERE / "assets" / "CY24SU10.json"
    shutil.copyfile(base_theme, RPT_DIR / "StaticResources" / "SharedResources" / "BaseThemes" / "CY24SU10.json")
    write_json(RPT_DIR / "StaticResources" / "RegisteredResources" / "UKRoadSafetyTheme.json", THEME)

    pages = build_pages()
    write_json(defs / "pages" / "pages.json", {
        "$schema": f"{SCHEMA}/item/report/definition/pagesMetadata/1.1.0/schema.json",
        "pageOrder": [p.name for p in pages], "activePageName": pages[0].name})
    for p in pages:
        p.write(defs / "pages")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-folder", default=str(ROOT / "data" / "powerbi"))
    args = ap.parse_args()

    for d in (SM_DIR / "definition", RPT_DIR / "definition"):
        if d.exists():
            shutil.rmtree(d)
    (RPT_DIR / "StaticResources" / "SharedResources" / "BaseThemes").mkdir(parents=True, exist_ok=True)

    write_json(HERE / f"{NAME}.pbip", {
        "$schema": f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    build_semantic_model(args.data_folder)
    build_report()
    print(f"wrote {HERE / (NAME + '.pbip')}")


if __name__ == "__main__":
    main()
