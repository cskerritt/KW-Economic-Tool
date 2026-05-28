"""Loss of household services module tests.

The DVD helper tests check the Dollar Value of a Day identities against the
worked figures in DED Chapter 6 (with a small tolerance for the book rounding
its hourly values). The projection golden case is a small, hand-verifiable
multi-stage case with frozen totals.
"""

import math

from engine.lhhs import (
    dollar_value_of_a_day,
    annual_value_from_hours,
    HouseholdStage,
    project_lhhs,
)


# --- DVD value helpers ------------------------------------------------------

def test_dollar_value_of_a_day_matches_ded_example():
    # DED: 14.46 weekly hours at $15.62 -> dollar value of a day ~ $32.28.
    assert math.isclose(
        dollar_value_of_a_day(14.46, 15.62), 32.28, abs_tol=0.02
    )


def test_annual_is_dvd_times_365_25():
    w, h = 20.53, 14.72
    assert math.isclose(
        annual_value_from_hours(w, h),
        dollar_value_of_a_day(w, h) * 365.25,
    )


# --- projection -------------------------------------------------------------

def _golden_stages() -> list[HouseholdStage]:
    return [
        HouseholdStage(2026, 2028, 20.0, 15.0, 0.5),   # partial loss
        HouseholdStage(2029, 2030, 25.0, 15.0, 1.0),   # full loss
    ]


def test_lhhs_total_present_value():
    r = project_lhhs(
        _golden_stages(),
        base_year=2026,
        valuation_year=2025,
        growth_rate=0.03,
        discount_rate=0.03,
        area_wage_factor=0.936,
        self_consumption=0.0,
    )
    assert round(r.total_present_value, 2) == 56_899.97
    assert len(r.rows) == 5


def test_lhhs_loss_percent_applied():
    r = project_lhhs(
        _golden_stages(),
        base_year=2026,
        valuation_year=2025,
        growth_rate=0.03,
        discount_rate=0.03,
        area_wage_factor=1.0,
        self_consumption=0.0,
    )
    # 2026 base annual value at 20 hrs / $15: 20*15/7*365.25.
    base = 20.0 * 15.0 / 7.0 * 365.25
    row_2026 = next(r for r in r.rows if r.year == 2026)
    # loss percent 0.5 applied, area factor 1.0, growth 0 periods (base year).
    assert math.isclose(row_2026.annual_loss, base * 0.5)


def test_lhhs_self_consumption_reduces_loss():
    full = project_lhhs(
        _golden_stages(), base_year=2026, valuation_year=2025,
        growth_rate=0.03, discount_rate=0.03,
    ).total_present_value
    reduced = project_lhhs(
        _golden_stages(), base_year=2026, valuation_year=2025,
        growth_rate=0.03, discount_rate=0.03, self_consumption=0.20,
    ).total_present_value
    assert math.isclose(reduced, full * 0.80)


def test_past_plus_future_equals_total():
    r = project_lhhs(
        _golden_stages(), base_year=2026, valuation_year=2025,
        growth_rate=0.03, discount_rate=0.03,
    )
    assert math.isclose(
        r.past_present_value + r.future_present_value, r.total_present_value
    )
