"""Paths and configuration files for the project."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(os.environ.get("OFFHOURS_ROOT", Path(__file__).resolve().parents[2]))


def _load_dotenv() -> None:
    """Load KEY=VALUE pairs from a gitignored .env into os.environ (never printed)."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

CONFIGS = ROOT / "configs"
# OFFHOURS_DATA_DIR moves the (gitignored) data store, e.g. to a short path on Windows where the
# repo path plus cache file names would exceed the 260-character limit.
DATA = Path(os.environ.get("OFFHOURS_DATA_DIR", ROOT / "data"))
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
REPORTS = ROOT / "reports"
TABLES = REPORTS / "tables"
FIGURES = REPORTS / "figures"
DUCKDB_PATH = PROCESSED / "offhours.duckdb"


@lru_cache
def load_yaml(name: str) -> dict:
    """Read configs/<name>.yaml."""
    with open(CONFIGS / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def cfg() -> dict:
    return load_yaml("config")


def overnight_mpids() -> list[str]:
    """MPIDs of the overnight-only ATSs marked include: true."""
    venues = load_yaml("overnight_venues")["venues"]
    return [m for m, v in venues.items() if v.get("include", True)]


def ensure_dirs() -> None:
    for p in (RAW, INTERIM, PROCESSED, TABLES, FIGURES, REPORTS / "note"):
        p.mkdir(parents=True, exist_ok=True)
