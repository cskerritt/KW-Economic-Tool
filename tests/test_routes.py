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


# --- discounting mode selector flows through the form to the result --------

def test_forms_render_discount_mode_selector():
    for path in ("/earnings", "/lcp", "/lhhs"):
        assert 'name="discount_mode"' in client.get(path).text


@pytest.mark.parametrize("mode,label", [
    ("standard", "Standard (discounted to present value)"),
    ("nominal", "Undiscounted (nominal future dollars)"),
    ("offset_zero", "Total offset (no growth, no discount)"),
    ("offset_match", "Total offset (growth offsets discount)"),
])
def test_earnings_discount_mode_labels_result(mode, label):
    r = client.post("/earnings/calculate", data=dict(_GOOD_EARNINGS, discount_mode=mode))
    assert r.status_code == 200
    assert label in r.text


# --- unauthenticated UX: browser page loads redirect to login --------------

def test_anonymous_browser_page_redirects_to_login():
    """A 401 (raised by require_user for anonymous users) should redirect a
    full-page browser GET to /auth/login, while HTMX and JSON clients still get
    a plain 401. Force the 401 via a dependency override so we don't depend on
    real auth state."""
    from fastapi import HTTPException

    from app.auth import require_user

    def _deny():
        raise HTTPException(status_code=401, detail="Sign in required.")

    app.dependency_overrides[require_user] = _deny
    try:
        r = client.get("/", headers={"accept": "text/html"}, follow_redirects=False)
        assert r.status_code == 302 and r.headers["location"] == "/auth/login"
        assert client.get("/", headers={"accept": "text/html", "hx-request": "true"},
                          follow_redirects=False).status_code == 401
        assert client.get("/", headers={"accept": "application/json"},
                          follow_redirects=False).status_code == 401
        assert client.get("/healthz").status_code == 200  # public, unaffected
    finally:
        app.dependency_overrides.pop(require_user, None)


# --- lookup endpoints: confirm the route wiring + returned values -----------
# These lock the HTTP layer (query-param names, status codes, and the exact
# values surfaced from the CSVs) so a future column/param rename can't silently
# break a form helper. Values are cross-checked against the source data files.

def test_lookup_worklife_returns_csv_values():
    r = client.get("/lookups/worklife", params={
        "sex": "Men", "initial_state": "Active",
        "education": "High School Diploma", "age": 45,
    })
    assert r.status_code == 200
    d = r.json()
    assert d["wle_mean"] == 16.67                      # WLE table, age 45
    assert abs(d["worklife_ratio"] - 16.67 / 21.17) < 1e-9  # YFS-derived ratio


def test_lookup_worklife_unknown_cohort_is_404():
    r = client.get("/lookups/worklife", params={
        "sex": "Martian", "initial_state": "Active", "education": "X", "age": 45,
    })
    assert r.status_code == 404


def test_lookup_worklife_out_of_range_age_is_404():
    r = client.get("/lookups/worklife", params={
        "sex": "Men", "initial_state": "Active",
        "education": "High School Diploma", "age": 999,
    })
    assert r.status_code == 404


def test_lookup_life_expectancy_birth_and_65():
    rb = client.get("/lookups/life-expectancy", params={
        "area": "California", "sex": "total", "at": "birth"})
    assert rb.status_code == 200 and rb.json()["life_expectancy"] == 79.3
    r65 = client.get("/lookups/life-expectancy", params={
        "area": "California", "sex": "male", "at": "65"})
    assert r65.json()["life_expectancy"] == 18.3


def test_lookup_life_expectancy_unknown_area_is_null():
    r = client.get("/lookups/life-expectancy", params={"area": "Atlantis"})
    assert r.status_code == 200 and r.json()["life_expectancy"] is None


def test_lookup_dvd_returns_household_production():
    r = client.get("/lookups/dvd", params={"table_num": 1})
    assert r.status_code == 200
    d = r.json()
    assert d["weekly_hours"] == 12.37
    assert d["dollar_value_of_a_day"] == 35.63
    assert abs(d["annual_value"] - 35.63 * 365.25) < 1e-6


def test_lookup_dvd_out_of_range_is_404():
    assert client.get("/lookups/dvd", params={"table_num": 999}).status_code == 404
    assert client.get("/lookups/dvd", params={"table_num": 0}).status_code == 404


def test_lookup_area_factor_and_unknown():
    r = client.get("/lookups/area", params={"area": "California"})
    assert r.status_code == 200 and abs(r.json()["factor"] - 1.1385) < 1e-9
    assert client.get("/lookups/area", params={"area": "Nowhere"}).json()["factor"] is None


def test_lookup_lcp_categories_nonempty():
    r = client.get("/lookups/lcp-categories")
    assert r.status_code == 200
    cats = r.json()["categories"]
    assert "Medical care" in cats and len(cats) >= 1


def test_lookup_lcp_growth_years_out_of_range_is_400():
    r = client.get("/lookups/lcp-growth", params={"category": "Medical care", "years": 99})
    assert r.status_code == 400


def test_lookup_lcp_growth_without_api_key_is_503(monkeypatch):
    # No FRED_API_KEY -> clean 503, never a 500.
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    r = client.get("/lookups/lcp-growth", params={
        "category": "Medical care", "years": 10, "general_inflation": 0.023})
    assert r.status_code == 503
