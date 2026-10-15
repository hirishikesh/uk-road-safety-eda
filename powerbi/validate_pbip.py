"""Validate every JSON file of the Power BI project against Microsoft's published schemas.

Each file's "$schema" URL is fetched (with all referenced sub-schemas) from the
microsoft/json-schemas GitHub repo and cached under .cache/json-schemas/.

Usage:
    python powerbi/validate_pbip.py
"""
import json
import sys
import urllib.request
from pathlib import Path

from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path(__file__).resolve().parent
CACHE = ROOT / ".cache" / "json-schemas"
MS_PREFIX = "https://developer.microsoft.com/json-schemas/"
RAW_PREFIX = "https://raw.githubusercontent.com/microsoft/json-schemas/main/"


def _fetch(uri: str) -> dict:
    local = CACHE / uri.removeprefix(MS_PREFIX)
    if not local.exists():
        local.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(uri.replace(MS_PREFIX, RAW_PREFIX)) as r:
            local.write_bytes(r.read())
    return json.loads(local.read_text(encoding="utf-8"))


def _retrieve(uri: str) -> Resource:
    return Resource.from_contents(_fetch(uri), default_specification=DRAFT7)


def main() -> int:
    registry = Registry(retrieve=_retrieve)
    files = [p for p in PROJECT.rglob("*") if p.suffix in {".json", ".pbir", ".pbism", ".pbip"}
             and "StaticResources" not in p.parts and ".pbi" not in p.parts]
    errors = 0
    for path in sorted(files):
        doc = json.loads(path.read_text(encoding="utf-8"))
        schema_uri = doc.get("$schema")
        if not schema_uri:
            print(f"[skip] {path.relative_to(PROJECT)} (no $schema)")
            continue
        schema = _fetch(schema_uri)
        validator = Draft7Validator(schema, registry=registry)
        problems = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        for e in problems:
            print(f"[FAIL] {path.relative_to(PROJECT)} at /{'/'.join(map(str, e.path))}: {e.message[:300]}")
        errors += len(problems)
    print(f"{len(files)} files checked, {errors} schema errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
