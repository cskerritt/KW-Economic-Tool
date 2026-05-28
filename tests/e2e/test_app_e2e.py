"""Browser end-to-end tests (opt in with ``pytest -m e2e``).

Drives the real HTMX UI against a live server: every module's
calculate/save/reopen flow, the PI dual-stream toggle and net derivation, the
worklife/life-expectancy lookups, the FRED LCP growth helper, and every download
button (XLSX/DOCX/PDF). Golden values are asserted through the rendered page, so
this guards the whole web stack the way the unit tests guard the engine.
"""

from __future__ import annotations

import pytest

# Skip the whole module cleanly if playwright isn't installed (default dev env).
pytest.importorskip("playwright")

pytestmark = pytest.mark.e2e


def _calc(page) -> None:
    page.click("button:has-text('Calculate')")


def test_dashboard_loads(page, live_server):
    page.goto(live_server)
    page.wait_for_load_state("networkidle")
    assert "Forensic Economic Calculator" in page.content()


def test_earnings_wd_golden_save_reopen_downloads(page, live_server, tmp_path):
    page.goto(f"{live_server}/earnings")
    page.wait_for_load_state("networkidle")
    assert page.locator("input[name=base_earnings]").input_value() == "93628.0"

    _calc(page)
    page.wait_for_selector("text=Total present value")
    assert "$858,384.39" in page.inner_text("#result")  # Tinari golden

    # Save
    page.fill("#result input[name=title]", "E2E WD earnings")
    page.click("#result button:has-text('Save case')")
    page.wait_for_selector("#save-status:has-text('Saved')")

    # Downloads: XLSX (native) + PDF
    with page.expect_download() as di:
        page.click("#result button:has-text('Download XLSX')")
    xlsx = tmp_path / "e.xlsx"
    di.value.save_as(xlsx)
    assert xlsx.read_bytes()[:2] == b"PK" and xlsx.stat().st_size > 1000

    with page.expect_download() as di:
        page.click("#result button:has-text('Download PDF report')")
    pdf = tmp_path / "e.pdf"
    di.value.save_as(pdf)
    assert pdf.read_bytes()[:5] == b"%PDF-"

    # Reopen recomputes from storage (case id 1 is the first save on a fresh DB).
    page.goto(f"{live_server}/earnings?case_id=1")
    page.wait_for_load_state("networkidle")
    assert page.locator("input[name=base_earnings]").input_value() == "93628.0"


def test_earnings_lookups(page, live_server):
    page.goto(f"{live_server}/earnings")
    page.wait_for_load_state("networkidle")
    page.select_option("#wl_sex", "Men")
    page.select_option("#wl_state", "Active")
    page.select_option("#wl_edu", "High School Diploma")
    page.fill("#wl_age", "40")
    page.click("button:has-text('Set WLE factor')")
    page.wait_for_selector("#wl-msg:has-text('WLE factor set')")

    page.click("button:has-text('Life expectancy')")
    page.wait_for_selector("#wl-msg:has-text('Life expectancy')")
    assert "Life expectancy at birth" in page.inner_text("#wl-msg")


def test_earnings_pi_dual_stream(page, live_server):
    page.goto(f"{live_server}/earnings")
    page.wait_for_load_state("networkidle")
    assert not page.locator("#residual_fields").is_visible()  # hidden for WD

    page.select_option("#case_type", "PI")
    assert page.locator("#residual_fields").is_visible()
    page.fill("input[name=pc_initial]", "0")
    page.fill("input[name=pc_later]", "0")
    page.fill("input[name=pc_switch_year]", "")
    page.fill("input[name=residual_base_earnings]", "40000")
    page.fill("input[name=residual_worklife]", "85")
    page.fill("input[name=residual_unemployment]", "5")
    page.fill("input[name=residual_tax]", "10")
    _calc(page)
    page.wait_for_selector("#result:has-text('Net personal-injury loss')")
    body = page.inner_text("#result")
    assert "$1,106,012.93" in body  # pre-injury capacity
    assert "$665,991.33" in body    # net loss


def test_lcp_calculate_save_download(page, live_server, tmp_path):
    page.goto(f"{live_server}/lcp")
    page.wait_for_load_state("networkidle")
    _calc(page)
    page.wait_for_selector("#result:has-text('Lifetime present value')")
    page.fill("#result input[name=title]", "E2E LCP")
    page.click("#result button:has-text('Save case')")
    page.wait_for_selector("#save-status:has-text('Saved')")
    with page.expect_download() as di:
        page.click("#result button:has-text('Download XLSX')")
    x = tmp_path / "lcp.xlsx"
    di.value.save_as(x)
    assert x.read_bytes()[:2] == b"PK"


def test_lhhs_calculate_save_download(page, live_server, tmp_path):
    page.goto(f"{live_server}/lhhs")
    page.wait_for_load_state("networkidle")
    _calc(page)
    page.wait_for_selector("#result:has-text('Total present value')")
    page.fill("#result input[name=title]", "E2E LHHS")
    page.click("#result button:has-text('Save case')")
    page.wait_for_selector("#save-status:has-text('Saved')")
    with page.expect_download() as di:
        page.click("#result button:has-text('Download DOCX')")
    d = tmp_path / "lhhs.docx"
    di.value.save_as(d)
    assert d.read_bytes()[:2] == b"PK"


def test_lcp_growth_helper(page, live_server):
    """FRED is external. Require either a composed rate (reachable) or a clean
    error message (graceful degradation) -- never a hang or a 500. The
    composition math itself is covered by offline unit tests."""
    import os

    if not os.getenv("FRED_API_KEY"):
        pytest.skip("no FRED_API_KEY")

    page.goto(f"{live_server}/lcp")
    page.wait_for_load_state("networkidle")
    page.wait_for_function(
        "document.querySelector('#g_category') && "
        "document.querySelector('#g_category').options.length > 0"
    )
    assert page.locator("#g_category option").count() >= 4
    page.select_option("#g_category", "Medical care")
    page.fill("#g_years", "10")
    page.fill("#g_general", "2.3")
    page.click("button:has-text('Compute growth rate')")
    page.wait_for_function(
        "document.querySelector('#g-msg') && "
        "document.querySelector('#g-msg').innerText.trim() !== '' && "
        "document.querySelector('#g-msg').innerText.indexOf('Querying') === -1",
        timeout=30000,
    )
    msg = page.inner_text("#g-msg")
    assert ("growth_rate:" in msg) or ("Could not compute" in msg), msg
