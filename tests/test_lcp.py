"""Life care plan module tests.

The growth-rate tests check the DED §920 identity directly. The projection
golden case is a small, hand-verifiable set of items; the asserted totals are
frozen engine values so future refactors cannot silently drift.
"""

import math

from engine.lcp import (
    LCPItem,
    project_lcp,
    medical_growth_rate,
    real_medical_inflation,
)


# --- growth rate (DED §920) -------------------------------------------------

def test_real_medical_inflation_can_be_negative():
    # Some medical commodities fell over 2010-2020 per DED.
    assert math.isclose(real_medical_inflation(0.010, 0.018), -0.008)


def test_medical_growth_rate_identity():
    # real (category - overall) + expected general inflation
    # (0.031 - 0.017) + 0.023 = 0.037
    assert math.isclose(medical_growth_rate(0.031, 0.017, 0.023), 0.037)


# --- projection patterns ----------------------------------------------------

def test_recurring_item_occurrence_years():
    item = LCPItem("visits", "Physician", 200.0, 2026, 2028, 0.04, 2026,
                   units_per_year=4)
    assert item.occurrence_years() == [2026, 2027, 2028]


def test_replacement_item_occurrence_years():
    item = LCPItem("wheelchair", "DME", 3000.0, 2026, 2036, 0.03, 2026,
                   replacement_years=5)
    assert item.occurrence_years() == [2026, 2031, 2036]


# --- golden projection ------------------------------------------------------

def _golden_items() -> list[LCPItem]:
    return [
        LCPItem("Physician visits", "Physician", 200.0, 2026, 2028, 0.04, 2026,
                units_per_year=4),
        LCPItem("Wheelchair", "DME", 3000.0, 2026, 2036, 0.03, 2026,
                replacement_years=5),
        LCPItem("Home health aide", "Attendant care", 50000.0, 2026, 2027,
                0.035, 2026, units_per_year=1, overlaps_household=True),
    ]


def test_lcp_lifetime_and_category_totals():
    r = project_lcp(_golden_items(), discount_rate=0.03, valuation_year=2025)
    assert round(r.lifetime_present_value, 2) == 108_413.68
    assert round(r.category_present_value["Physician"], 2) == 2_352.79
    assert round(r.category_present_value["DME"], 2) == 8_737.86
    assert round(r.category_present_value["Attendant care"], 2) == 97_323.03


def test_lcp_household_overlap_netting():
    r = project_lcp(_golden_items(), discount_rate=0.03, valuation_year=2025)
    assert round(r.household_overlap_present_value, 2) == 97_323.03
    # Lifetime excluding the attendant-care overlap (to avoid double counting).
    assert round(r.lifetime_excluding_overlap(), 2) == 11_090.66


def test_lcp_category_total_equals_sum_of_items():
    r = project_lcp(_golden_items(), discount_rate=0.03, valuation_year=2025)
    assert math.isclose(
        sum(r.category_present_value.values()), r.lifetime_present_value
    )
