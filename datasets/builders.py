"""Turn reference data into engine-ready inputs.

These helpers bridge ``datasets`` (CSV lookups) and the canonical input dicts the
engine/compute path consumes, so a case can be built from a DVD table number, a
residence, and a worker cohort rather than hand-keyed values.
"""

from __future__ import annotations

from datasets import dvd, sck, spf


def lhhs_stage_from_dvd(
    table_num: int,
    start_year: int,
    end_year: int,
    loss_percent: float,
) -> dict:
    """Build one LHHS stage dict from a DVD demographic table.

    Uses the table's Household Production weekly hours and the implied blended
    hourly value, so the stage reproduces that table's annual household-
    production value before the loss percent and area factor are applied.
    """
    hp = dvd.household_production(table_num)
    return {
        "start_year": int(start_year),
        "end_year": int(end_year),
        "weekly_hours": hp["weekly_hours"],
        "hourly_value": hp["hourly_value"],
        "loss_percent": float(loss_percent),
    }


def lhhs_inputs_from_dvd(
    table_num: int,
    *,
    base_year: int,
    valuation_year: int,
    growth_rate: float,
    discount_rate: float,
    loss_percent: float,
    start_year: int,
    end_year: int,
    area: str | None = None,
    self_consumption: float = 0.0,
) -> dict:
    """Build a complete LHHS canonical input dict from a DVD table and residence."""
    factor = dvd.area_wage_factor(area) if area else 1.0
    if factor is None:
        factor = 1.0
    return {
        "base_year": base_year,
        "valuation_year": valuation_year,
        "growth_rate": growth_rate,
        "discount_rate": discount_rate,
        "area_wage_factor": factor,
        "self_consumption": self_consumption,
        "stages": [
            lhhs_stage_from_dvd(table_num, start_year, end_year, loss_percent)
        ],
    }


def earnings_worklife_factor(sex: str, initial_state: str, education: str, age: int) -> float:
    """Tinari WLE adjustment from SCK (worklife / years-to-final-separation)."""
    return sck.worklife_ratio(sex, initial_state, education, age)


def assumption_defaults() -> dict:
    """Suggested growth/discount anchors (decimals) from SPF long-term medians.

    growth uses the 10-year median CPI inflation; discount uses the 10-year
    median nominal Treasury bond rate. These are starting points, not opinions.
    """
    lt = spf.long_term()
    return {
        "growth_rate": (lt["cpi_inflation"] or 0) / 100.0,
        "discount_rate": (lt["bond_rate_10yr"] or 0) / 100.0,
        "real_gdp_growth": (lt["real_gdp_growth"] or 0) / 100.0,
    }
