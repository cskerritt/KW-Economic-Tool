"""Earnings module tests.

The golden case is the worked example from Tinari (2016), the Exposito
wrongful-death hypothetical. Reproducing it proves the engine implements the
algebraic method faithfully.

Tinari's printed total present value is $858,387. Our full-precision result is
~$858,384; the small gap is because the paper rounds each year's gross earnings
to whole dollars before computing, while the engine carries full precision.
Per-year figures match the paper's Exhibit 1 to the dollar.
"""

import math

from engine.earnings import (
    adjusted_income_factor,
    build_earnings_inputs,
    project_earnings,
    EarningsAssumptions,
)


# --- AIF unit tests ---------------------------------------------------------

def test_aif_matches_tinari_past_factor():
    # WLE 91.9%, UF 3.5%, TL 12%, PC 25%  ->  58.53%
    aif = adjusted_income_factor(0.919, 0.035, 0.12, 0.25)
    assert round(aif * 100, 2) == 58.53


def test_aif_matches_tinari_future_factor():
    # Same but PC 20%  ->  62.43%
    aif = adjusted_income_factor(0.919, 0.035, 0.12, 0.20)
    assert round(aif * 100, 2) == 62.43


def test_aif_no_fringe_equals_base_form():
    base = adjusted_income_factor(0.95, 0.04, 0.15, 0.0, fringe=0.0)
    expected = 0.95 * (1 - 0.04) * (1 - 0.15)
    assert math.isclose(base, expected)


def test_aif_fringe_not_taxed():
    # Wage base w = 0.95 * (1 - 0.04). With 6% fringe and 15% tax, the fringe
    # portion is not taxed: AIF = (w*(1+fb) - w*tl) * (1 - pc).
    w = 0.95 * (1 - 0.04)
    expected = (w * 1.06 - w * 0.15) * 1.0
    assert math.isclose(
        adjusted_income_factor(0.95, 0.04, 0.15, 0.0, fringe=0.06), expected
    )


def test_personal_consumption_zero_for_personal_injury():
    # PC = 0 should drop the consumption deduction entirely.
    aif = adjusted_income_factor(0.919, 0.035, 0.12, 0.0)
    expected = 0.919 * (1 - 0.035) * (1 - 0.12)
    assert math.isclose(aif, expected)


# --- Golden projection: Tinari Exposito case --------------------------------

def _exposito_assumptions() -> EarningsAssumptions:
    return EarningsAssumptions(
        base_earnings=93628.0,   # 2008 last full year
        base_year=2008,
        start_year=2009,         # year of death
        end_year=2022,           # statistical retirement
        valuation_year=2015,     # past = 2009-2015, future = 2016-2022
        growth_past=0.031,
        growth_future=0.038,
        growth_switch_year=2016,
        discount_rate=0.0325,
        worklife=0.919,
        unemployment=0.035,
        tax=0.12,
        fringe=0.0,
        personal_consumption_initial=0.25,
        personal_consumption_later=0.20,
        pc_switch_year=2016,
        partial_years={2009: 0.33, 2022: 0.26},
    )


def test_exposito_total_present_value_matches_paper():
    a = _exposito_assumptions()
    result = project_earnings(
        build_earnings_inputs(a), a.discount_rate, a.valuation_year
    )
    # Within $5 of the paper's printed $858,387 (rounding of annual gross).
    assert abs(result.total_present_value - 858_387) < 5
    # Frozen engine value, so future refactors cannot silently drift.
    assert round(result.total_present_value, 2) == 858_384.39


def test_exposito_uses_two_aif_values():
    a = _exposito_assumptions()
    result = project_earnings(
        build_earnings_inputs(a), a.discount_rate, a.valuation_year
    )
    aifs = sorted(round(v * 100, 2) for v in result.aif_values())
    assert aifs == [58.53, 62.43]


def test_exposito_first_and_last_year_present_values():
    a = _exposito_assumptions()
    result = project_earnings(
        build_earnings_inputs(a), a.discount_rate, a.valuation_year
    )
    by_year = {r.year: r for r in result.rows}
    # 2009 is a 33% partial past year: PV equals adjusted income (undiscounted).
    assert round(by_year[2009].present_value) == 18_645
    assert by_year[2009].is_future is False
    # 2016 is the first discounted future year (one period at 3.25%).
    assert round(by_year[2016].present_value) == 72_768
    assert by_year[2016].is_future is True


def test_past_plus_future_equals_total():
    a = _exposito_assumptions()
    result = project_earnings(
        build_earnings_inputs(a), a.discount_rate, a.valuation_year
    )
    assert math.isclose(
        result.past_present_value + result.future_present_value,
        result.total_present_value,
    )


# --- Personal-injury dual-stream (pre-injury minus residual) -----------------
#
# Unlike the wrongful-death example, the Tinari paper has no separate published
# worked PI figure. Correctness here rests on two pillars:
#   1. Each stream reproduces the audited algebraic method (the WD golden above
#      and the AIF unit tests fix the per-stream math).
#   2. The net loss is exactly pre-injury minus residual, year by year.
# The frozen totals below are regression anchors for a fully documented
# scenario so future refactors cannot silently drift the composed result.

from engine.earnings import project_personal_injury  # noqa: E402


def _pi_stream(
    base: float, worklife: float, unemployment: float, tax: float
) -> EarningsAssumptions:
    """An earnings stream on the Exposito timeline with PC fixed at 0 (PI)."""
    return EarningsAssumptions(
        base_earnings=base,
        base_year=2008,
        start_year=2009,
        end_year=2022,
        valuation_year=2015,
        growth_past=0.031,
        growth_future=0.038,
        growth_switch_year=2016,
        discount_rate=0.0325,
        worklife=worklife,
        unemployment=unemployment,
        tax=tax,
        fringe=0.0,
        personal_consumption_initial=0.0,
        personal_consumption_later=None,
        pc_switch_year=None,
        partial_years={2009: 0.33, 2022: 0.26},
    )


def _project(a: EarningsAssumptions):
    return project_earnings(build_earnings_inputs(a), a.discount_rate, a.valuation_year)


def test_pi_net_is_pre_minus_residual_each_year():
    """The net PI loss equals pre-injury minus residual, year by year."""
    pre = _project(_pi_stream(93628.0, 0.919, 0.035, 0.12))
    residual = _project(_pi_stream(40000.0, 0.85, 0.05, 0.10))
    net = project_personal_injury(pre, residual)

    res_by_year = {r.year: r for r in residual.rows}
    for row in net.rows:
        expected = pre_pv = next(
            p.present_value for p in pre.rows if p.year == row.year
        )
        expected = pre_pv - res_by_year[row.year].present_value
        assert math.isclose(row.present_value, expected)
    assert math.isclose(
        net.total_present_value,
        pre.total_present_value - residual.total_present_value,
    )


def test_pi_total_disability_equals_pre_injury_stream():
    """A zero residual stream (total disability) gives net == pre-injury loss.

    This makes the dual-stream result a strict generalization of the old
    single-stream PI behavior (PC = 0, no residual).
    """
    pre = _project(_pi_stream(93628.0, 0.919, 0.035, 0.12))
    zero_residual = _project(_pi_stream(0.0, 0.919, 0.035, 0.12))
    net = project_personal_injury(pre, zero_residual)
    assert math.isclose(net.total_present_value, pre.total_present_value)


def test_pi_dual_stream_golden_totals():
    """Frozen regression for the documented PI scenario.

    Pre-injury: Exposito earnings ($93,628 base, WLE 91.9%, UF 3.5%, TL 12%),
    personal consumption 0. Residual capacity: $40,000 base, WLE 85%, UF 5%,
    TL 10%, personal consumption 0. Same Exposito timeline, growth, discount,
    and partial years for both streams.
    """
    pre = _project(_pi_stream(93628.0, 0.919, 0.035, 0.12))
    residual = _project(_pi_stream(40000.0, 0.85, 0.05, 0.10))
    net = project_personal_injury(pre, residual)

    assert round(pre.total_present_value, 2) == 1_106_012.93
    assert round(residual.total_present_value, 2) == 440_021.60
    assert round(net.total_present_value, 2) == 665_991.33
    assert round(net.past_present_value, 2) == 318_250.52
    assert round(net.future_present_value, 2) == 347_740.81
    assert math.isclose(
        net.past_present_value + net.future_present_value,
        net.total_present_value,
    )
