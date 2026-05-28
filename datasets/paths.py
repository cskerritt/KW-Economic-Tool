"""Locate the data directory and provide a small CSV reader."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def data_path(*parts: str) -> Path:
    return DATA_DIR.joinpath(*parts)


@lru_cache(maxsize=None)
def read_csv(rel_path: str) -> tuple[dict, ...]:
    """Read a CSV under data/ into a tuple of dict rows (cached)."""
    path = data_path(rel_path)
    with open(path, newline="", encoding="utf-8") as f:
        return tuple(dict(r) for r in csv.DictReader(f))
