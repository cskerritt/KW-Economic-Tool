"""Dollar Value of a Day (DVD 2023) lookups."""

from __future__ import annotations

from functools import lru_cache

from datasets.paths import read_csv


def list_demographics() -> list[dict]:
    """All 385 demographic tables: {table, demographic, file, n_rows}."""
    return [dict(r) for r in read_csv("dvd/_index.csv")]


@lru_cache(maxsize=None)
def demographic_table(table_num: int) -> dict[str, dict]:
    """Return the table keyed by time-use category -> row of values."""
    rows = read_csv(f"dvd/dvd_table_{int(table_num):03d}.csv")
    return {r["time_use_category"]: r for r in rows}


def _f(x: str) -> float | None:
    return float(x) if x not in (None, "") else None


def household_production(table_num: int) -> dict:
    """Household-production summary for a demographic table.

    Returns weekly_hours, dollar_value_of_a_day, the implied blended hourly
    value, and the annualized value (dollar value of a day x 365.25).
    """
    row = demographic_table(table_num)["Household Production"]
    wh = _f(row["weekly_hours"])
    dvd = _f(row["dollar_value_of_a_day"])
    hourly = (dvd * 7.0 / wh) if (wh and dvd) else None
    return {
        "table": int(table_num),
        "weekly_hours": wh,
        "dollar_value_of_a_day": dvd,
        "hourly_value": hourly,
        "annual_value": (dvd * 365.25) if dvd is not None else None,
    }


@lru_cache(maxsize=None)
def _area_rows() -> tuple[dict, ...]:
    return read_csv("dvd/dvd_table_414_area_wage_adjustment.csv")


def area_wage_factor(area: str) -> float | None:
    """National-to-area wage factor (decimal) for a state or metro area.

    Case-insensitive exact, then substring match on the area label. Returns a
    decimal (e.g. 0.936 for 93.6%), or None if not found.
    """
    q = area.strip().lower()
    rows = _area_rows()
    exact = [r for r in rows if r["area"].lower() == q]
    hit = exact or [r for r in rows if q in r["area"].lower()]
    if not hit:
        return None
    return float(hit[0]["adjustment_pct"]) / 100.0
