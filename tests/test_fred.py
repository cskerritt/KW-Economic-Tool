"""FRED CPI growth-helper tests.

The pure CAGR math and the category->series mapping are tested offline with
injected data (no network). A live FRED smoke test runs only when FRED_API_KEY
is set, so CI and local runs without a key stay hermetic.
"""

import math
import os

import pytest

from datasets.fred import (
    cagr,
    cpi_series,
    list_categories,
    overall_series_id,
    series_cagr,
)


# --- pure CAGR --------------------------------------------------------------

def test_cagr_basic_doubling():
    # 100 -> 200 over 10 years
    assert math.isclose(cagr(100.0, 200.0, 10), 2 ** (1 / 10) - 1)


def test_cagr_known_rate_roundtrips():
    # Grow 100 at 3% for 8 years, recover 3%.
    end = 100.0 * (1.03 ** 8)
    assert math.isclose(cagr(100.0, end, 8), 0.03, rel_tol=1e-12)


def test_cagr_rejects_nonpositive():
    with pytest.raises(ValueError):
        cagr(0.0, 100.0, 5)
    with pytest.raises(ValueError):
        cagr(100.0, 200.0, 0)


def test_series_cagr_uses_window_endpoints():
    pts = [(2015, 100.0), (2016, 103.0), (2017, 106.09),
           (2018, 109.27), (2019, 112.55), (2020, 115.93)]
    out = series_cagr(pts, years=5)
    assert out["base_year"] == 2015
    assert out["end_year"] == 2020
    assert math.isclose(out["rate"], cagr(100.0, 115.93, 5))


def test_series_cagr_needs_enough_points():
    with pytest.raises(ValueError):
        series_cagr([(2019, 100.0), (2020, 103.0)], years=5)


def test_series_cagr_annualizes_over_actual_span_with_gap():
    """If FRED is missing a year, the two endpoints span more calendar years
    than ``years``; the CAGR must annualize over the real span, not the literal
    ``years``, or it overstates the rate."""
    # Six points but 2017 is missing, so 5 steps back from 2021 lands on 2015 ->
    # a 6-year span, not 5.
    pts = [(2015, 100.0), (2016, 105.0), (2018, 115.0),
           (2019, 120.0), (2020, 125.0), (2021, 130.0)]
    out = series_cagr(pts, years=5)
    assert out["base_year"] == 2015 and out["end_year"] == 2021
    # Annualized over the true 6-year span.
    assert math.isclose(out["rate"], cagr(100.0, 130.0, 6))
    # The naive (buggy) 5-year denominator would be materially higher.
    assert out["rate"] < cagr(100.0, 130.0, 5)


# --- mapping ----------------------------------------------------------------

def test_mapping_has_overall_and_categories():
    series = cpi_series()
    assert "Overall CPI (all items)" in series
    assert overall_series_id() == "CPIAUCSL"
    cats = list_categories()
    assert "Medical care" in cats
    # the overall row is not offered as a selectable category
    assert "Overall CPI (all items)" not in cats


def test_category_growth_unknown_category_raises():
    from datasets.fred import category_growth
    with pytest.raises(KeyError):
        category_growth("Not a category", years=10, expected_general_inflation=0.02)


# --- composition (offline, monkeypatched fetch) -----------------------------

def test_category_growth_composition(monkeypatch):
    """Item growth = (category CAGR - overall CAGR) + general inflation."""
    import datasets.fred as fred

    canned = {
        "CPIMEDSL": [(y, 100.0 * (1.05 ** (y - 2014))) for y in range(2014, 2025)],
        "CPIAUCSL": [(y, 100.0 * (1.03 ** (y - 2014))) for y in range(2014, 2025)],
    }
    monkeypatch.setattr(
        fred, "fetch_annual_index",
        lambda series_id, *, years, api_key=None: canned[series_id],
    )
    out = fred.category_growth(
        "Medical care", years=10, expected_general_inflation=0.023
    )
    assert math.isclose(out["category_cagr"], 0.05, rel_tol=1e-9)
    assert math.isclose(out["overall_cagr"], 0.03, rel_tol=1e-9)
    assert math.isclose(out["real_medical_inflation"], 0.02, rel_tol=1e-9)
    assert math.isclose(out["item_growth_rate"], 0.02 + 0.023, rel_tol=1e-9)
    assert out["category_series_id"] == "CPIMEDSL"
    assert out["overall_series_id"] == "CPIAUCSL"
    assert "FRED CPIMEDSL" in out["source"]


# --- live smoke test (only with a real key) ---------------------------------

@pytest.mark.skipif(not os.getenv("FRED_API_KEY"), reason="no FRED_API_KEY")
def test_live_medical_care_growth_is_plausible():
    from datasets.fred import category_growth
    out = category_growth("Medical care", years=10, expected_general_inflation=0.0)
    # Medical care CPI has grown over the last decade; sanity bounds only.
    assert -0.05 < out["category_cagr"] < 0.15
    assert 0.0 < out["overall_cagr"] < 0.10
