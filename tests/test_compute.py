"""Tests for the shared compute path (canonical dict -> result -> summary).

These confirm the dict-driven path reproduces the same numbers as the engine
golden tests, so saved cases and the MCP server stay consistent with the UI.
"""

from app.compute import compute, summarize


EXPOSITO = {
    "case_type": "WD",
    "base_earnings": 93628.0,
    "base_year": 2008,
    "start_year": 2009,
    "end_year": 2022,
    "valuation_year": 2015,
    "growth_past": 0.031,
    "growth_future": 0.038,
    "growth_switch_year": 2016,
    "discount_rate": 0.0325,
    "worklife": 0.919,
    "unemployment": 0.035,
    "tax": 0.12,
    "fringe": 0.0,
    "pc_initial": 0.25,
    "pc_later": 0.20,
    "pc_switch_year": 2016,
    "partial_years": {"2009": 0.33, "2022": 0.26},
}

LCP = {
    "discount_rate": 0.03,
    "valuation_year": 2025,
    "items": [
        {"name": "Physician visits", "category": "Physician", "cost_per_unit": 200,
         "start_year": 2026, "end_year": 2028, "growth_rate": 0.04,
         "base_year": 2026, "units_per_year": 4},
        {"name": "Wheelchair", "category": "DME", "cost_per_unit": 3000,
         "start_year": 2026, "end_year": 2036, "growth_rate": 0.03,
         "base_year": 2026, "replacement_years": 5},
        {"name": "Home health aide", "category": "Attendant care",
         "cost_per_unit": 50000, "start_year": 2026, "end_year": 2027,
         "growth_rate": 0.035, "base_year": 2026, "units_per_year": 1,
         "overlaps_household": True},
    ],
}

LHHS = {
    "base_year": 2026,
    "valuation_year": 2025,
    "growth_rate": 0.03,
    "discount_rate": 0.03,
    "area_wage_factor": 0.936,
    "self_consumption": 0.0,
    "stages": [
        {"start_year": 2026, "end_year": 2028, "weekly_hours": 20,
         "hourly_value": 15, "loss_percent": 0.5},
        {"start_year": 2029, "end_year": 2030, "weekly_hours": 25,
         "hourly_value": 15, "loss_percent": 1.0},
    ],
}


def test_compute_earnings_matches_golden():
    r = compute("earnings", EXPOSITO)
    assert round(r.total_present_value, 2) == 858_384.39
    s = summarize("earnings", r)
    assert s["total_present_value"] == 858_384.39
    assert s["years"] == 14


def test_compute_earnings_personal_injury_drops_consumption():
    pi = dict(EXPOSITO, case_type="PI")
    r = compute("earnings", pi)
    # No personal consumption deducted -> larger loss than the WD case.
    assert r.total_present_value > compute("earnings", EXPOSITO).total_present_value


def test_compute_earnings_pi_no_residual_is_total_disability():
    """PI with no residual key == pre-injury stream (total disability)."""
    pi = dict(EXPOSITO, case_type="PI")
    r = compute("earnings", pi)
    # Matches the engine golden pre-injury PC=0 stream for the Exposito inputs.
    assert round(r.total_present_value, 2) == 1_106_012.93
    # Both component streams are retained on the result for the audit trail.
    assert round(r.pre_injury.total_present_value, 2) == 1_106_012.93
    assert r.residual.total_present_value == 0.0


def test_compute_earnings_pi_dual_stream_matches_engine_golden():
    """PI dual-stream through the dict path reproduces the engine golden net."""
    pi = dict(
        EXPOSITO,
        case_type="PI",
        residual={
            "base_earnings": 40000.0,
            "worklife": 0.85,
            "unemployment": 0.05,
            "tax": 0.10,
        },
    )
    r = compute("earnings", pi)
    assert round(r.total_present_value, 2) == 665_991.33
    s = summarize("earnings", r)
    assert s["total_present_value"] == 665_991.33
    assert s["years"] == 14


def test_compute_lcp_matches_golden():
    r = compute("lcp", LCP)
    assert round(r.lifetime_present_value, 2) == 108_413.68
    s = summarize("lcp", r)
    assert s["lifetime_excluding_overlap"] == 11_090.66


def test_compute_lhhs_matches_golden():
    r = compute("lhhs", LHHS)
    assert round(r.total_present_value, 2) == 56_899.97
    assert summarize("lhhs", r)["years"] == 5
