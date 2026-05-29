"""Route-level tests: malformed calculation input yields 422, not 500.

These drive the FastAPI app in-process with the TestClient (auth disabled) and
confirm the global bad-input handler turns the crashes a user can trigger from
the forms -- malformed item JSON, empty numeric fields, bad partial-years,
out-of-range years -- into clean 422 responses instead of opaque 500s. A valid
request still returns 200 with the rendered result, so the handler doesn't mask
the happy path.
"""

from __future__ import annotations

import os

os.environ.setdefault("AUTH_DISABLED", "true")
os.environ.setdefault("SESSION_SECRET", "test-secret")

import pytest  # noqa: E402

pytest.importorskip("httpx")  # TestClient needs httpx

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)

_GOOD_EARNINGS = {
    "case_type": "WD", "base_earnings": "93628", "base_year": "2008",
    "start_year": "2009", "end_year": "2012", "valuation_year": "2010",
    "growth_past": "3.1", "growth_future": "3.8", "growth_switch_year": "2011",
    "discount_rate": "3.25", "worklife": "91.9", "unemployment": "3.5",
    "tax": "12", "fringe": "0", "pc_initial": "25", "pc_later": "20",
    "pc_switch_year": "2011", "partial_years": "2009:0.33",
}


def test_valid_earnings_calculate_is_200():
    r = client.post("/earnings/calculate", data=_GOOD_EARNINGS)
    assert r.status_code == 200
    assert "Total present value" in r.text


def test_earnings_empty_required_field_is_422():
    # Empty required field: FastAPI's own validation returns 422 (also not a 500).
    bad = dict(_GOOD_EARNINGS, base_earnings="")
    r = client.post("/earnings/calculate", data=bad)
    assert r.status_code == 422


def test_earnings_bad_partial_years_is_422():
    bad = dict(_GOOD_EARNINGS, partial_years="2009:0.33:oops")
    r = client.post("/earnings/calculate", data=bad)
    assert r.status_code == 422


def test_earnings_nonnumeric_field_is_422():
    bad = dict(_GOOD_EARNINGS, base_earnings="abc")
    r = client.post("/earnings/calculate", data=bad)
    assert r.status_code == 422


def test_lcp_malformed_items_json_is_422():
    r = client.post("/lcp/calculate", data={
        "discount_rate": "3", "valuation_year": "2025", "items_json": "{not json",
    })
    assert r.status_code == 422
    assert "Invalid input" in r.text


def test_lcp_item_start_before_base_is_422():
    items = (
        '[{"name":"X","category":"C","cost_per_unit":100,'
        '"start_year":2025,"end_year":2030,"growth_rate":0.03,"base_year":2026}]'
    )
    r = client.post("/lcp/calculate", data={
        "discount_rate": "3", "valuation_year": "2025", "items_json": items,
    })
    assert r.status_code == 422


def test_save_unknown_module_is_404():
    r = client.post("/nope/save", data={"title": "t", "inputs_json": "{}"})
    assert r.status_code == 404
