"""FRED-backed CPI growth rates for the LCP Medical Care Cost Index helper.

This is the only place in the project that makes a network call, and it lives in
the datasets (reference-data) layer on purpose: the pure engine never touches
the network. It uses the standard library only (``urllib``) so no dependency is
added.

It turns FRED CPI index series into a compound annual growth rate (CAGR) over a
lookback window, then composes a per-item LCP growth rate using the engine's
DED Medical Care Cost Index formula:

    item growth = (category CAGR - overall CPI CAGR) + expected general inflation

The category-to-series mapping is auditable reference data in
``data/fred/cpi_series.csv``. The FRED API key is read from ``FRED_API_KEY`` and
is never stored in code or committed.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import date

from datasets.paths import read_csv
from engine.lcp import medical_growth_rate, real_medical_inflation

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"


# --- series mapping (auditable reference data) ------------------------------

def cpi_series() -> dict[str, dict[str, str]]:
    """Friendly category name -> {series_id, role, note} from the mapping CSV."""
    return {
        row["category"]: {
            "series_id": row["series_id"],
            "role": row["role"],
            "note": row.get("note", ""),
        }
        for row in read_csv("fred/cpi_series.csv")
    }


def overall_series_id() -> str:
    for cat in cpi_series().values():
        if cat["role"] == "overall":
            return cat["series_id"]
    raise KeyError("no overall-CPI row (role=overall) in data/fred/cpi_series.csv")


def list_categories() -> list[str]:
    """Category names that carry their own growth rate (role=category)."""
    return [c for c, v in cpi_series().items() if v["role"] == "category"]


# --- pure CAGR math (no network; unit-tested offline) -----------------------

def cagr(first_value: float, last_value: float, years: float) -> float:
    """Compound annual growth rate between two index levels over ``years``."""
    if years <= 0:
        raise ValueError("years must be > 0")
    if first_value <= 0:
        raise ValueError("first_value must be > 0")
    return (last_value / first_value) ** (1.0 / years) - 1.0


def series_cagr(annual_points: list[tuple[int, float]], years: int) -> dict:
    """CAGR over the last ``years`` of annual (year, index_value) points.

    ``annual_points`` must be sorted ascending by year. Uses the point ``years``
    entries back from the latest as the base. The CAGR is annualized over the
    ACTUAL calendar span between the two endpoints (``end_year - base_year``),
    not the requested ``years`` -- if FRED has a gap and an entry is missing, the
    two endpoints can be more than ``years`` calendar years apart, and using the
    literal ``years`` as the denominator would overstate the rate. Returns the
    rate plus the endpoints used, so the result is fully traceable.
    """
    pts = [p for p in annual_points if p[1] is not None]
    if len(pts) < years + 1:
        raise ValueError(
            f"need {years + 1} annual points for a {years}-year CAGR, "
            f"have {len(pts)}"
        )
    base_year, base_val = pts[-(years + 1)]
    end_year, end_val = pts[-1]
    span = end_year - base_year
    if span <= 0:
        raise ValueError("endpoints must span at least one year")
    return {
        "rate": cagr(base_val, end_val, span),
        "base_year": base_year,
        "base_value": base_val,
        "end_year": end_year,
        "end_value": end_val,
    }


# --- FRED fetch (network; integration-only) ---------------------------------

def _api_key(explicit: str | None = None) -> str:
    key = explicit or os.getenv("FRED_API_KEY", "")
    if not key:
        raise RuntimeError(
            "FRED_API_KEY is not set; cannot query FRED. Set it in the "
            "environment (never commit it)."
        )
    return key


def fetch_annual_index(
    series_id: str,
    *,
    years: int,
    api_key: str | None = None,
    timeout: float = 15.0,
) -> list[tuple[int, float]]:
    """Fetch annual-average index levels for ``series_id`` from FRED.

    Returns ascending (year, value) points covering at least ``years`` + 1 years.
    Annual averaging (``frequency=a``) smooths monthly noise and makes the CAGR
    reproducible.
    """
    key = _api_key(api_key)
    start = date(date.today().year - (years + 2), 1, 1).isoformat()
    params = urllib.parse.urlencode(
        {
            "series_id": series_id,
            "api_key": key,
            "file_type": "json",
            "frequency": "a",
            "aggregation_method": "avg",
            "observation_start": start,
        }
    )
    req = urllib.request.Request(f"{FRED_OBSERVATIONS_URL}?{params}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (https FRED)
        payload = json.loads(resp.read().decode("utf-8"))
    points: list[tuple[int, float]] = []
    for obs in payload.get("observations", []):
        value = obs.get("value")
        if value in (None, ".", ""):
            continue
        points.append((int(obs["date"][:4]), float(value)))
    points.sort()
    return points


# --- composition: per-item LCP growth rate ----------------------------------

def category_growth(
    category: str,
    *,
    years: int,
    expected_general_inflation: float,
    api_key: str | None = None,
) -> dict:
    """Compose an LCP item growth rate for ``category`` from FRED CPI series.

    Returns the final item growth rate and every component (category CAGR,
    overall CPI CAGR, real medical inflation, expected general inflation) plus
    the series ids, window, and as-of date so the figure is fully traceable and
    can be snapshotted with the saved case.
    """
    series = cpi_series()
    if category not in series or series[category]["role"] != "category":
        raise KeyError(f"unknown CPI category: {category!r}")
    cat_id = series[category]["series_id"]
    ov_id = overall_series_id()

    cat = series_cagr(fetch_annual_index(cat_id, years=years, api_key=api_key), years)
    overall = series_cagr(fetch_annual_index(ov_id, years=years, api_key=api_key), years)

    real = real_medical_inflation(cat["rate"], overall["rate"])
    item_growth = medical_growth_rate(
        cat["rate"], overall["rate"], expected_general_inflation
    )

    return {
        "category": category,
        "category_series_id": cat_id,
        "overall_series_id": ov_id,
        "lookback_years": years,
        "category_cagr": cat["rate"],
        "overall_cagr": overall["rate"],
        "real_medical_inflation": real,
        "expected_general_inflation": expected_general_inflation,
        "item_growth_rate": item_growth,
        "window": {
            "category": {"from": cat["base_year"], "to": cat["end_year"]},
            "overall": {"from": overall["base_year"], "to": overall["end_year"]},
        },
        "as_of": date.today().isoformat(),
        "source": (
            f"FRED {cat_id} vs {ov_id}, {years}-yr CAGR "
            f"({cat['base_year']}-{cat['end_year']}); "
            f"+{expected_general_inflation:.4f} general inflation; "
            f"as of {date.today().isoformat()}"
        ),
    }
