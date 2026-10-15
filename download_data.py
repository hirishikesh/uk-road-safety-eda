"""Download the DfT STATS19 road safety data (last 5 years) into data/raw/.

Usage:
    python download_data.py            # skip files that already exist
    python download_data.py --force    # re-download everything
"""
import sys
import urllib.request
from pathlib import Path

BASE = "https://data.dft.gov.uk/road-accidents-safety-data"
FILES = {
    "collisions.csv": f"{BASE}/dft-road-casualty-statistics-collision-last-5-years.csv",
    "vehicles.csv": f"{BASE}/dft-road-casualty-statistics-vehicle-last-5-years.csv",
    "casualties.csv": f"{BASE}/dft-road-casualty-statistics-casualty-last-5-years.csv",
    "data_guide.xlsx": (
        "https://assets.publishing.service.gov.uk/media/6ab2a71d997a4b2950cced58/"
        "dft-road-casualty-statistics-road-safety-open-dataset-data-guide-2025.xlsx"
    ),
}

RAW_DIR = Path(__file__).resolve().parent / "data" / "raw"


def main(force: bool = False) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        dest = RAW_DIR / name
        if dest.exists() and not force:
            print(f"[skip] {name} already exists")
            continue
        print(f"[get ] {name} <- {url}")
        tmp = dest.with_suffix(dest.suffix + ".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(dest)
        print(f"       {dest.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main(force="--force" in sys.argv)
