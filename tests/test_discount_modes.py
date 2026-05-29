"""Discounting modes: standard, nominal (#1), and total-offset (#2a/#2b).

The engine always discounts at the rate it is handed; these modes only change
which rates the compute layer feeds it, so:

* ``standard`` (default / no key) must be byte-identical to before -- the Tinari
  golden still reproduces.
* ``nominal`` keeps growth but drops discounting (future-dollar sum).
* ``offset_zero`` zeroes growth AND discount (classic total offset: sum of
  current-year-dollar values).
* ``offset_match`` discounts at the growth rate so the two cancel (today's
  dollars while still showing grown amounts); for LCP each item offsets at its
  own growth rate.
"""

from __future__ import annotations

import math

import pytest

from app.compute import compute
from engine.earnings import adjusted_income_factor

EARN = dict(
    case_type="WD", base_earnings=80000.0, base_year=2024,
    start_year=2025, end_year=2034, valuation_year=2025,
    growth_past=0.03, growth_future=0.03, growth_switch_year=2025,
    discount_rate=0.04, worklife=0.95, unemployment=0.04, tax=0.15,
    fringe=0.0, pc_initial=0.0,
)
LCP = dict(
    discount_rate=0.03, valuation_year=2025, items=[
        dict(name="MD", category="Phys", cost_per_unit=200, start_year=2026,
             end_year=2035, growth_rate=0.04, base_year=2024, units_per_year=4),
    ],
)
LHHS = dict(
    base_year=2024, valuation_year=2025, growth_rate=0.03, discount_rate=0.04,
    area_wage_factor=1.0, self_consumption=0.0,
    stages=[dict(start_year=2025, end_year=2034, weekly_hours=20,
                 hourly_value=15, loss_percent=1.0)],
)


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        compute("earnings", dict(EARN, discount_mode="bogus"))


def test_missing_mode_equals_standard():
    a = compute("earnings", EARN)
    b = compute("earnings", dict(EARN, discount_mode="standard"))
    assert math.isclose(a.total_present_value, b.total_present_value)


def test_standard_golden_unchanged():
    g = compute("earnings", dict(
        case_type="WD", base_earnings=93628.0, base_year=2008, start_year=2009,
        end_year=2022, valuation_year=2015, growth_past=0.031, growth_future=0.038,
        growth_switch_year=2016, discount_rate=0.0325, worklife=0.919,
        unemployment=0.035, tax=0.12, fringe=0.0, pc_initial=0.25, pc_later=0.20,
        pc_switch_year=2016, partial_years={"2009": 0.33, "2022": 0.26},
    ))
    assert round(g.total_present_value, 2) == 858384.39


# --- earnings ---------------------------------------------------------------

def test_earnings_offset_zero_is_sum_of_base_times_aif():
    r = compute("earnings", dict(EARN, discount_mode="offset_zero"))
    aif = adjusted_income_factor(0.95, 0.04, 0.15, 0.0)
    expected = 80000.0 * aif * 10  # 10 years, no growth, no discount
    assert math.isclose(r.total_present_value, expected, rel_tol=1e-9)
    # Every year shows the same ungrown gross.
    assert all(math.isclose(row.gross_earnings, 80000.0) for row in r.rows)


def test_earnings_nominal_drops_discount_only():
    nominal = compute("earnings", dict(EARN, discount_mode="nominal"))
    standard = compute("earnings", EARN)
    # Discount rate (4%) > 0, so removing it raises the total.
    assert nominal.total_present_value > standard.total_present_value
    # Growth is retained, so later years exceed the base.
    assert nominal.rows[-1].gross_earnings > 80000.0


def test_earnings_offset_match_discounts_at_growth():
    # Equivalent to entering discount == growth_future explicitly.
    via_mode = compute("earnings", dict(EARN, discount_mode="offset_match"))
    via_rate = compute("earnings", dict(EARN, discount_rate=EARN["growth_future"]))
    assert math.isclose(via_mode.total_present_value, via_rate.total_present_value)


# --- lcp --------------------------------------------------------------------

def test_lcp_offset_zero_is_undiscounted_base():
    r = compute("lcp", dict(LCP, discount_mode="offset_zero"))
    # 4 visits * $200 * 10 years, no growth, no discount.
    assert math.isclose(r.lifetime_present_value, 200 * 4 * 10)


def test_lcp_offset_match_offsets_each_item_at_its_own_growth():
    r = compute("lcp", dict(LCP, discount_mode="offset_match"))
    # base*(1+g)^(valuation-base) per occurrence: 800 * 1.04^(2025-2024) * 10.
    expected = 200 * 4 * (1.04 ** (2025 - 2024)) * 10
    assert math.isclose(r.lifetime_present_value, expected, rel_tol=1e-9)


def test_lcp_nominal_exceeds_standard():
    nominal = compute("lcp", dict(LCP, discount_mode="nominal"))
    standard = compute("lcp", LCP)
    assert nominal.lifetime_present_value > standard.lifetime_present_value


# --- lhhs -------------------------------------------------------------------

def test_lhhs_offset_zero_is_undiscounted_base():
    r = compute("lhhs", dict(LHHS, discount_mode="offset_zero"))
    annual = 20 * 15 / 7 * 365.25  # dollar value of a day * 365.25
    assert math.isclose(r.total_present_value, annual * 10, rel_tol=1e-9)


def test_lhhs_offset_match_equals_discount_at_growth():
    via_mode = compute("lhhs", dict(LHHS, discount_mode="offset_match"))
    via_rate = compute("lhhs", dict(LHHS, discount_rate=LHHS["growth_rate"]))
    assert math.isclose(via_mode.total_present_value, via_rate.total_present_value)


@pytest.mark.parametrize("module,inputs", [
    ("earnings", EARN), ("lcp", LCP), ("lhhs", LHHS)])
def test_nominal_not_below_standard_when_discount_positive(module, inputs):
    """With a positive discount rate, removing discounting never lowers the total."""
    def total(r):
        return getattr(r, "total_present_value", None) or r.lifetime_present_value
    nominal_total = total(compute(module, dict(inputs, discount_mode="nominal")))
    standard_total = total(compute(module, inputs))
    assert nominal_total >= standard_total - 1e-6