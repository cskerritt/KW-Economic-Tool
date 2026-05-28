"""Tests for the reference-data access layer and builders.

Anchor values are taken directly from the source documents, so these double as
a check that the CSVs are still correctly aligned.
"""

import math

from datasets import (
    area_wage_factor, household_production, life_expectancy, fringe_rate,
    long_term, worklife_expectancy, worklife_ratio, list_demographics,
)
from datasets.builders import (
    lhhs_inputs_from_dvd, lhhs_stage_from_dvd, assumption_defaults,
)
from app.compute import compute


# --- DVD ---------------------------------------------------------------------

def test_dvd_index_has_385_tables():
    assert len(list_demographics()) == 385


def test_area_wage_factor_state_and_metro():
    assert math.isclose(area_wage_factor("Alabama"), 0.8077, abs_tol=1e-9)
    assert math.isclose(area_wage_factor("Napa, CA"), 1.2217, abs_tol=1e-9)
    assert area_wage_factor("Nowhere County, ZZ") is None


def test_household_production_table1():
    hp = household_production(1)
    assert math.isclose(hp["weekly_hours"], 12.37)
    assert math.isclose(hp["dollar_value_of_a_day"], 35.63)
    # annual = dollar value of a day x 365.25
    assert math.isclose(hp["annual_value"], 35.63 * 365.25)
    # implied hourly reproduces the dollar value of a day
    assert math.isclose(hp["hourly_value"] * hp["weekly_hours"] / 7.0,
                        hp["dollar_value_of_a_day"], abs_tol=1e-6)


# --- NVSR --------------------------------------------------------------------

def test_life_expectancy_lookups():
    assert life_expectancy("New Jersey", "male", "birth") == 77.1
    assert life_expectancy("United States", "total", "birth") == 77.5
    assert life_expectancy("United States", "total", "65") == 18.9


# --- ECEC --------------------------------------------------------------------

def test_fringe_rate_private():
    # Table 1: private total benefits 13.79 / wages 32.36.
    assert math.isclose(fringe_rate("private", "wages"), 13.79 / 32.36, abs_tol=1e-9)
    assert math.isclose(fringe_rate("private", "compensation"), 13.79 / 46.15, abs_tol=1e-9)


# --- SPF ---------------------------------------------------------------------

def test_long_term_anchors():
    lt = long_term()
    assert lt["real_gdp_growth"] == 2.10
    assert lt["bond_rate_10yr"] == 4.00
    assert lt["cpi_inflation"] == 2.30


def test_assumption_defaults_decimals():
    d = assumption_defaults()
    assert math.isclose(d["growth_rate"], 0.0230)
    assert math.isclose(d["discount_rate"], 0.0400)


# --- SCK ---------------------------------------------------------------------

def test_worklife_lookup_and_ratio():
    row = worklife_expectancy("Men", "Active", "High School Diploma", 40)
    assert int(row["age"]) == 40
    assert float(row["wle_mean"]) > 0
    r = worklife_ratio("Men", "Active", "High School Diploma", 40)
    assert 0.0 < r <= 1.0


# --- builders integrate with the engine -------------------------------------

def test_lhhs_stage_from_dvd_shape():
    stage = lhhs_stage_from_dvd(1, 2026, 2030, 0.5)
    assert stage["weekly_hours"] > 0 and stage["hourly_value"] > 0
    assert stage["loss_percent"] == 0.5


def test_lhhs_inputs_from_dvd_compute():
    inputs = lhhs_inputs_from_dvd(
        1, base_year=2024, valuation_year=2025, growth_rate=0.03,
        discount_rate=0.03, loss_percent=1.0, start_year=2026, end_year=2030,
        area="Alabama",
    )
    # area factor pulled from Table 414
    assert math.isclose(inputs["area_wage_factor"], 0.8077, abs_tol=1e-9)
    result = compute("lhhs", inputs)
    assert result.total_present_value > 0
    assert len(result.rows) == 5
