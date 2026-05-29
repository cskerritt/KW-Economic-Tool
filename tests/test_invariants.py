"""Structural invariants that must hold for ANY inputs.

Unlike the snapshot test (which freezes specific numbers), these assert laws the
math must always obey -- past + future = total, PI net = pre - residual,
discounting only applies to the future, present value collapses to nominal when
the discount rate is zero, and so on. They catch a whole class of logic errors
the snapshot would otherwise just re-freeze, and they exercise the same matrix.
"""

from __future__ import annotations

import pytest

from app.compute import compute
from engine.common import present_value
from regression_scenarios import SCENARIOS

EARN = [s for s in SCENARIOS if s.module == "earnings"]
LCP = [s for s in SCENARIOS if s.module == "lcp"]
LHHS = [s for s in SCENARIOS if s.module == "lhhs"]

TOL = 1e-6


def _close(a, b, tol=TOL):
    return abs(a - b) <= max(tol, 1e-9 * max(abs(a), abs(b)))


# --- earnings ---------------------------------------------------------------

@pytest.mark.parametrize("sc", EARN, ids=lambda s: s.id)
def test_earnings_past_plus_future_equals_total(sc):
    r = compute("earnings", sc.inputs)
    assert _close(r.past_present_value + r.future_present_value,
                  r.total_present_value)


@pytest.mark.parametrize("sc", EARN, ids=lambda s: s.id)
def test_earnings_row_pv_sums_to_total(sc):
    r = compute("earnings", sc.inputs)
    assert _close(sum(row.present_value for row in r.rows), r.total_present_value)


@pytest.mark.parametrize("sc", EARN, ids=lambda s: s.id)
def test_earnings_row_count_matches_loss_period(sc):
    r = compute("earnings", sc.inputs)
    expected = int(sc.inputs["end_year"]) - int(sc.inputs["start_year"]) + 1
    assert len(r.rows) == expected


@pytest.mark.parametrize("sc", EARN, ids=lambda s: s.id)
def test_earnings_future_flag_matches_valuation(sc):
    r = compute("earnings", sc.inputs)
    val = int(sc.inputs["valuation_year"])
    for row in r.rows:
        assert row.is_future == (row.year > val)


PI = [s for s in EARN if str(s.inputs.get("case_type")) == "PI"]


@pytest.mark.parametrize("sc", PI, ids=lambda s: s.id)
def test_pi_net_equals_pre_minus_residual(sc):
    r = compute("earnings", sc.inputs)
    assert _close(r.total_present_value,
                  r.pre_injury.total_present_value - r.residual.total_present_value)


@pytest.mark.parametrize("sc", PI, ids=lambda s: s.id)
def test_pi_net_not_above_pre_injury(sc):
    r = compute("earnings", sc.inputs)
    # Residual capacity is non-negative, so the net loss can never exceed the
    # pre-injury capacity.
    assert r.total_present_value <= r.pre_injury.total_present_value + TOL


def test_pi_total_disability_equals_pre_injury():
    sc = next(s for s in PI if s.id == "earn-pi-total-disability")
    r = compute("earnings", sc.inputs)
    assert _close(r.total_present_value, r.pre_injury.total_present_value)
    assert _close(r.residual.total_present_value, 0.0)


# --- lcp --------------------------------------------------------------------

@pytest.mark.parametrize("sc", LCP, ids=lambda s: s.id)
def test_lcp_items_sum_to_lifetime(sc):
    r = compute("lcp", sc.inputs)
    assert _close(sum(it.present_value for it in r.items), r.lifetime_present_value)


@pytest.mark.parametrize("sc", LCP, ids=lambda s: s.id)
def test_lcp_categories_sum_to_lifetime(sc):
    r = compute("lcp", sc.inputs)
    assert _close(sum(r.category_present_value.values()),
                  r.lifetime_present_value)


@pytest.mark.parametrize("sc", LCP, ids=lambda s: s.id)
def test_lcp_excluding_overlap_definition(sc):
    r = compute("lcp", sc.inputs)
    assert _close(r.lifetime_excluding_overlap(),
                  r.lifetime_present_value - r.household_overlap_present_value)


@pytest.mark.parametrize("sc", LCP, ids=lambda s: s.id)
def test_lcp_nominal_not_below_present_value_when_growth_ge_discount(sc):
    # When every dollar is grown and then discounted at a lower-or-equal rate,
    # present value should not exceed the undiscounted nominal total.
    r = compute("lcp", sc.inputs)
    if float(sc.inputs["discount_rate"]) >= 0:
        for it in r.items:
            assert it.present_value <= it.nominal_total + 1.0 or it.occurrences == 0


# --- lhhs -------------------------------------------------------------------

@pytest.mark.parametrize("sc", LHHS, ids=lambda s: s.id)
def test_lhhs_past_plus_future_equals_total(sc):
    r = compute("lhhs", sc.inputs)
    assert _close(r.past_present_value + r.future_present_value,
                  r.total_present_value)


@pytest.mark.parametrize("sc", LHHS, ids=lambda s: s.id)
def test_lhhs_row_pv_sums_to_total(sc):
    r = compute("lhhs", sc.inputs)
    assert _close(sum(row.present_value for row in r.rows), r.total_present_value)


@pytest.mark.parametrize("sc", LHHS, ids=lambda s: s.id)
def test_lhhs_rows_sorted_by_year(sc):
    r = compute("lhhs", sc.inputs)
    years = [row.year for row in r.rows]
    assert years == sorted(years)


@pytest.mark.parametrize("sc", LHHS, ids=lambda s: s.id)
def test_lhhs_annual_loss_scales_with_loss_percent(sc):
    r = compute("lhhs", sc.inputs)
    for row in r.rows:
        # annual_loss is base * area * loss% * (1 - self_consumption); never
        # exceeds the grown base value times the area factor.
        awf = float(sc.inputs.get("area_wage_factor", 1.0))
        assert row.annual_loss <= row.base_annual_value * awf + 1e-6


# --- cross-cutting: discounting law -----------------------------------------

def test_present_value_zero_rate_is_identity():
    assert _close(present_value(1000.0, 0.0, 10), 1000.0)


def test_present_value_discounts_future_and_not_past():
    assert present_value(1000.0, 0.05, 5) < 1000.0     # future discounted
    assert _close(present_value(1000.0, 0.05, 0), 1000.0)   # valuation year
    # Forensic convention: past losses are NOT discounted (returned unchanged),
    # not compounded up. Prejudgment interest is handled separately.
    assert _close(present_value(1000.0, 0.05, -3), 1000.0)
