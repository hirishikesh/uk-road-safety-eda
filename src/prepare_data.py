"""Clean and join the three STATS19 tables.

Reads  data/raw/{collisions,vehicles,casualties}.csv   (run download_data.py first)
Writes data/processed/*.pkl   -> used by the notebook
       data/powerbi/*.csv     -> star schema loaded by the Power BI project

Usage:
    python -m src.prepare_data
"""
from pathlib import Path

import numpy as np
import pandas as pd

from src.labels import MISSING, decode, text_code_map

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
POWERBI = ROOT / "data" / "powerbi"

SEVERITY_ORDER = ["Fatal", "Serious", "Slight"]
DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTH_ORDER = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
TIME_BANDS = ["00-05 Night", "06-09 AM peak", "10-15 Daytime", "16-19 PM peak", "20-23 Evening"]
AGE_GROUPS = ["0-16", "17-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75+"]

MOTORCYCLE = {2, 3, 4, 5, 23, 97}
HGV = {20, 21, 98}
BUS = {10, 11}
CAR = {8, 9}
PEDAL_CYCLE = 1
E_SCOOTER = 33  # "Personal powered transporter" in the 2024 spec


def _vehicle_group(code: int) -> str:
    if code == PEDAL_CYCLE:
        return "Pedal cycle"
    if code in MOTORCYCLE:
        return "Motorcycle"
    if code in CAR:
        return "Car / taxi"
    if code == 19:
        return "Van (<=3.5t)"
    if code in HGV:
        return "HGV (>3.5t)"
    if code in BUS:
        return "Bus / minibus"
    if code == E_SCOOTER:
        return "E-scooter"
    if code in (-1, 99):
        return MISSING
    return "Other"


def _casualty_group(code: int) -> str:
    if code == 0:
        return "Pedestrian"
    if code == 1:
        return "Cyclist"
    if code in MOTORCYCLE:
        return "Motorcyclist"
    if code in CAR:
        return "Car occupant"
    if code == 19:
        return "Van occupant"
    if code in HGV:
        return "HGV occupant"
    if code in BUS:
        return "Bus / minibus occupant"
    if code == E_SCOOTER:
        return "E-scooter rider"
    if code in (-1, 99):
        return MISSING
    return "Other"


def _age_group(age: pd.Series) -> pd.Series:
    bins = [-0.5, 16.5, 24.5, 34.5, 44.5, 54.5, 64.5, 74.5, 200]
    out = pd.cut(age.where(age >= 0), bins=bins, labels=AGE_GROUPS)
    return out.astype(str).replace("nan", MISSING)


def _time_band(hour: pd.Series) -> pd.Series:
    bins = [-0.5, 5.5, 9.5, 15.5, 19.5, 23.5]
    return pd.cut(hour, bins=bins, labels=TIME_BANDS).astype(str).replace("nan", MISSING)


def _country(police_force: pd.Series) -> pd.Series:
    return np.select(
        [police_force >= 91, police_force.between(60, 63)], ["Scotland", "Wales"], default="England"
    )


def _simplify_light(code: pd.Series) -> pd.Series:
    return code.map({1: "Daylight", 4: "Dark - lit", 5: "Dark - unlit", 6: "Dark - unlit",
                     7: "Dark - lighting unknown"}).fillna(MISSING)


def _simplify_weather(code: pd.Series) -> pd.Series:
    return code.map({1: "Fine", 4: "Fine", 2: "Rain", 5: "Rain", 3: "Snow", 6: "Snow",
                     7: "Fog or mist", 8: "Other"}).fillna(MISSING)


def load_raw() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    kw = dict(low_memory=False)
    return (pd.read_csv(RAW / "collisions.csv", **kw),
            pd.read_csv(RAW / "vehicles.csv", **kw),
            pd.read_csv(RAW / "casualties.csv", **kw))


def clean_vehicles(v: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({
        "collision_index": v["collision_index"],
        "vehicle_reference": v["vehicle_reference"],
        "vehicle_type": decode(v["vehicle_type"], "vehicle_type"),
        "vehicle_group": v["vehicle_type"].map(_vehicle_group),
        "vehicle_manoeuvre": decode(v["vehicle_manoeuvre"], "vehicle_manoeuvre"),
        "journey_purpose": decode(v["journey_purpose_of_driver"], "journey_purpose_of_driver"),
        "first_point_of_impact": decode(v["first_point_of_impact"], "first_point_of_impact"),
        "left_carriageway": np.where(v["vehicle_leaving_carriageway"] > 0, "Yes",
                                     np.where(v["vehicle_leaving_carriageway"] == 0, "No", MISSING)),
        "sex_of_driver": decode(v["sex_of_driver"], "sex_of_driver"),
        "age_of_driver": v["age_of_driver"].where(v["age_of_driver"] >= 0),
        "driver_age_group": _age_group(v["age_of_driver"]),
        "propulsion": decode(v["propulsion_code"], "propulsion_code"),
        "age_of_vehicle": v["age_of_vehicle"].where(v["age_of_vehicle"] >= 0),
        "is_escooter": v["escooter_flag"].eq(1).astype(int),
        "is_motor_vehicle": (~v["vehicle_type"].isin([PEDAL_CYCLE, E_SCOOTER, 16, 22, -1, 99])).astype(int),
    })
    out["vehicle_type_code"] = v["vehicle_type"]
    return out


def clean_casualties(k: pd.DataFrame) -> pd.DataFrame:
    sev = k["casualty_severity"]
    return pd.DataFrame({
        "collision_index": k["collision_index"],
        "vehicle_reference": k["vehicle_reference"],
        "casualty_reference": k["casualty_reference"],
        "casualty_class": decode(k["casualty_class"], "casualty_class"),
        "sex": decode(k["sex_of_casualty"], "sex_of_casualty"),
        "age": k["age_of_casualty"].where(k["age_of_casualty"] >= 0),
        "age_group": _age_group(k["age_of_casualty"]),
        "casualty_type": decode(k["casualty_type"], "casualty_type"),
        "road_user": k["casualty_type"].map(_casualty_group),
        "severity": sev.map(dict(enumerate(SEVERITY_ORDER, start=1))),
        "is_fatal": sev.eq(1).astype(int),
        "is_serious": sev.eq(2).astype(int),
        # DfT severity adjustment: probability the casualty would be recorded as serious
        # under an injury-based reporting system (fatal casualties are 0 here).
        "adj_serious": k["casualty_adjusted_severity_serious"],
        "ksi_adjusted": sev.eq(1) + k["casualty_adjusted_severity_serious"],
        "imd_decile": k["casualty_imd_decile"].where(k["casualty_imd_decile"] > 0),
        "injury_based_reporting": k["casualty_injury_based"],
    })


def clean_collisions(c: pd.DataFrame, veh: pd.DataFrame, cas: pd.DataFrame) -> pd.DataFrame:
    sev = c["collision_severity"]
    date = pd.to_datetime(c["date"], format="%d/%m/%Y")
    hour = pd.to_datetime(c["time"], format="%H:%M", errors="coerce").dt.hour

    out = pd.DataFrame({
        "collision_index": c["collision_index"],
        "date": date,
        "year": date.dt.year,
        "month_num": date.dt.month,
        "month": date.dt.month.map(dict(enumerate(MONTH_ORDER, start=1))),
        "day_of_week": date.dt.day_name(),
        "is_weekend": date.dt.dayofweek.ge(5).astype(int),
        "hour": hour,
        "time_band": _time_band(hour),
        "severity": sev.map(dict(enumerate(SEVERITY_ORDER, start=1))),
        "is_fatal": sev.eq(1).astype(int),
        "is_serious": sev.eq(2).astype(int),
        "adj_serious": c["collision_adjusted_severity_serious"],
        "ksi_adjusted": sev.eq(1) + c["collision_adjusted_severity_serious"],
        "reporting_system": np.where(c["collision_injury_based"] == 1,
                                     "Injury-based (CRASH)", "Officer judgement"),
        "number_of_vehicles": c["number_of_vehicles"],
        "number_of_casualties": c["number_of_casualties"],
        "country": _country(c["police_force"]),
        "police_force": decode(c["police_force"], "police_force"),
        "local_authority": c["local_authority_ons_district"].map(
            text_code_map("local_authority_ons_district")).fillna(MISSING),
        "urban_rural": decode(c["urban_or_rural_area"], "urban_or_rural_area"),
        "road_class": decode(c["first_road_class"], "first_road_class"),
        "road_type": decode(c["road_type"], "road_type"),
        "speed_limit": c["speed_limit"].where(c["speed_limit"] > 0),
        "junction_detail": decode(c["junction_detail"], "junction_detail"),
        "junction_control": decode(c["junction_control"], "junction_control"),
        "pedestrian_crossing": decode(c["pedestrian_crossing"], "pedestrian_crossing"),
        "light_conditions": decode(c["light_conditions"], "light_conditions"),
        "light": _simplify_light(c["light_conditions"]),
        "weather_conditions": decode(c["weather_conditions"], "weather_conditions"),
        "weather": _simplify_weather(c["weather_conditions"]),
        "high_winds": c["weather_conditions"].isin([4, 5, 6]).astype(int),
        "road_surface": decode(c["road_surface_conditions"], "road_surface_conditions"),
        "trunk_road": decode(c["trunk_road_flag"], "trunk_road_flag"),
        "latitude": c["latitude"],
        "longitude": c["longitude"],
    })
    out["urban_rural"] = out["urban_rural"].replace("Unallocated", MISSING)
    out["speed_limit_label"] = out["speed_limit"].map(
        lambda s: f"{int(s)} mph" if pd.notna(s) else MISSING)

    # Collision-level flags derived from the vehicle and casualty tables
    vflags = veh.assign(
        involves_motorcycle=veh["vehicle_type_code"].isin(MOTORCYCLE),
        involves_pedal_cycle=veh["vehicle_type_code"].eq(PEDAL_CYCLE),
        involves_hgv=veh["vehicle_type_code"].isin(HGV),
        involves_bus=veh["vehicle_type_code"].isin(BUS),
        involves_escooter=veh["is_escooter"].eq(1),
        young_driver=veh["is_motor_vehicle"].eq(1) & veh["age_of_driver"].between(17, 24),
        older_driver=veh["is_motor_vehicle"].eq(1) & veh["age_of_driver"].ge(75),
        driver_left_carriageway=veh["left_carriageway"].eq("Yes"),
    ).groupby("collision_index")[[
        "involves_motorcycle", "involves_pedal_cycle", "involves_hgv", "involves_bus",
        "involves_escooter", "young_driver", "older_driver", "driver_left_carriageway",
    ]].any()
    cflags = cas.assign(pedestrian_casualty=cas["road_user"].eq("Pedestrian")) \
                .groupby("collision_index")[["pedestrian_casualty"]].any()
    out = out.merge(vflags, on="collision_index", how="left").merge(cflags, on="collision_index", how="left")
    flag_cols = list(vflags.columns) + list(cflags.columns)
    out[flag_cols] = out[flag_cols].fillna(False).astype(int)
    return out


def build_dim_date(start: str, end: str) -> pd.DataFrame:
    d = pd.DataFrame({"date": pd.date_range(start, end, freq="D")})
    d["year"] = d["date"].dt.year
    d["quarter"] = "Q" + d["date"].dt.quarter.astype(str)
    d["month_num"] = d["date"].dt.month
    d["month"] = d["date"].dt.strftime("%b")
    d["year_month"] = d["date"].dt.strftime("%Y-%m")
    d["day_num"] = d["date"].dt.dayofweek + 1
    d["day_of_week"] = d["date"].dt.day_name()
    d["is_weekend"] = d["day_num"].ge(6).astype(int)
    return d


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    POWERBI.mkdir(parents=True, exist_ok=True)

    print("Loading raw CSVs ...")
    c_raw, v_raw, k_raw = load_raw()
    print(f"  collisions {c_raw.shape}, vehicles {v_raw.shape}, casualties {k_raw.shape}")

    veh = clean_vehicles(v_raw)
    cas = clean_casualties(k_raw)
    col = clean_collisions(c_raw, veh, cas)

    # Join integrity checks
    assert col["collision_index"].is_unique
    assert cas["collision_index"].isin(col["collision_index"]).all()
    assert veh["collision_index"].isin(col["collision_index"]).all()

    # Year on casualty / vehicle rows makes casualty-level analysis convenient
    year = col.set_index("collision_index")["year"]
    cas["year"] = cas["collision_index"].map(year)
    veh["year"] = veh["collision_index"].map(year)

    for name, df in [("collisions", col), ("vehicles", veh), ("casualties", cas)]:
        df.to_pickle(PROCESSED / f"{name}.pkl")
        print(f"  wrote processed/{name}.pkl {df.shape}")

    # Power BI star schema
    dim_date = build_dim_date(f"{col['year'].min()}-01-01", f"{col['year'].max()}-12-31")
    exports = {
        "fact_collisions": col.drop(columns=["year", "month_num", "month", "day_of_week", "is_weekend"]),
        "fact_casualties": cas.drop(columns=["year"]),
        "fact_vehicles": veh.drop(columns=["year", "vehicle_type_code"]),
        "dim_date": dim_date,
    }
    for name, df in exports.items():
        df.to_csv(POWERBI / f"{name}.csv", index=False, date_format="%Y-%m-%d")
        print(f"  wrote powerbi/{name}.csv {df.shape}")


if __name__ == "__main__":
    main()
