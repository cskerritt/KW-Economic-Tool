"""Export accuracy: the numbers a user downloads equal the engine's numbers.

The existing export tests only confirm the files are well-formed (not corrupt).
These go further: they parse the values back OUT of every exported xlsx / docx /
pdf and assert each one equals the engine result it was built from. This closes
the gap where a formatting bug (wrong cell, wrong column, dropped row) could ship
a pretty file with the wrong numbers.

Driven by the same scenario matrix as the snapshot test, so accuracy is checked
across the full range of inputs, not just one example per module.
"""

from __future__ import annotations

from io import BytesIO

import pytest

from app.compute import compute
from app.exporting import export_result
from regression_scenarios import SCENARIOS

EARN = [s for s in SCENARIOS if s.module == "earnings"]
LCP = [s for s in SCENARIOS if s.module == "lcp"]
LHHS = [s for s in SCENARIOS if s.module == "lhhs"]

CENT = 0.01  # xlsx stores raw floats; allow only sub-cent FP noise


def _close(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) <= tol


# --- earnings xlsx ----------------------------------------------------------

@pytest.mark.parametrize("sc", EARN, ids=lambda s: s.id)
def test_earnings_xlsx_values_match_engine(sc):
    openpyxl = pytest.importorskip("openpyxl")
    result = compute("earnings", sc.inputs)
    content, _, _ = export_result("earnings", result)
    wb = openpyxl.load_workbook(BytesIO(content))
    ws = wb["Earnings"]

    # Data rows: [year, portion, gross, aif, adjusted_income, present_value].
    data = [r for r in ws.iter_rows(min_row=2, values_only=True)
            if r[0] is not None and isinstance(r[0], (int, float))]
    assert len(data) == len(result.rows)
    for cells, row in zip(data, result.rows):
        assert int(cells[0]) == row.year
        assert _close(cells[1], row.portion)
        assert _close(cells[2], row.gross_earnings)
        assert _close(cells[3], row.aif)
        assert _close(cells[4], row.adjusted_income)
        assert _close(cells[5], row.present_value)

    totals = {r[0]: r[5] for r in ws.iter_rows(min_row=2, values_only=True)
              if isinstance(r[0], str)}
    assert _close(totals["Past present value"], result.past_present_value, CENT)
    assert _close(totals["Future present value"], result.future_present_value, CENT)
    assert _close(totals["Total present value"], result.total_present_value, CENT)


# --- lcp xlsx ---------------------------------------------------------------

@pytest.mark.parametrize("sc", LCP, ids=lambda s: s.id)
def test_lcp_xlsx_values_match_engine(sc):
    openpyxl = pytest.importorskip("openpyxl")
    result = compute("lcp", sc.inputs)
    content, _, _ = export_result("lcp", result)
    wb = openpyxl.load_workbook(BytesIO(content))

    ws = wb["LCP items"]
    rows = [r for r in ws.iter_rows(min_row=2, values_only=True) if r[0]]
    assert len(rows) == len(result.items)
    for cells, it in zip(rows, result.items):
        assert cells[0] == it.name
        assert cells[1] == it.category
        assert int(cells[2]) == it.occurrences
        assert _close(cells[3], it.nominal_total)
        assert _close(cells[4], it.present_value)

    ws2 = wb["Summary"]
    pairs = [(r[0], r[1]) for r in ws2.iter_rows(min_row=2, values_only=True)
             if r[0] is not None]
    cats = {k: v for k, v in pairs if k in result.category_present_value}
    for cat, pv in result.category_present_value.items():
        assert _close(cats[cat], pv)
    totals = {k: v for k, v in pairs}
    assert _close(totals["Lifetime present value"],
                  result.lifetime_present_value, CENT)
    assert _close(totals["Household-services overlap"],
                  result.household_overlap_present_value, CENT)
    assert _close(totals["Lifetime excluding overlap"],
                  result.lifetime_excluding_overlap(), CENT)


# --- lhhs docx --------------------------------------------------------------

@pytest.mark.parametrize("sc", LHHS, ids=lambda s: s.id)
def test_lhhs_docx_values_match_engine(sc):
    docx = pytest.importorskip("docx")
    result = compute("lhhs", sc.inputs)
    content, _, _ = export_result("lhhs", result)
    doc = docx.Document(BytesIO(content))
    table = doc.tables[0]

    body = table.rows[1:]  # skip header
    assert len(body) == len(result.rows)
    for trow, row in zip(body, result.rows):
        c = [cell.text for cell in trow.cells]
        assert c[0] == str(row.year)
        assert c[1] == f"${row.base_annual_value:,.0f}"
        assert c[2] == f"{row.loss_percent * 100:.0f}%"
        assert c[3] == f"${row.annual_loss:,.0f}"
        assert c[4] == f"${row.present_value:,.0f}"

    text = "\n".join(p.text for p in doc.paragraphs)
    assert f"Past present value: {result.past_present_value:,.2f}" in text
    assert f"Future present value: {result.future_present_value:,.2f}" in text
    assert f"Total present value: {result.total_present_value:,.2f}" in text


# --- pdf (all modules) ------------------------------------------------------

def _pdf_text(module, result, inputs) -> str:
    pypdf = pytest.importorskip("pypdf")
    pytest.importorskip("reportlab")
    content, _, media = export_result(
        module, result, fmt="pdf", inputs=inputs,
        firm="Test Firm", author="Test Author",
    )
    assert media == "application/pdf"
    reader = pypdf.PdfReader(BytesIO(content))
    return "".join(page.extract_text() for page in reader.pages)


@pytest.mark.parametrize("sc", EARN, ids=lambda s: s.id)
def test_earnings_pdf_shows_totals(sc):
    result = compute("earnings", sc.inputs)
    text = _pdf_text("earnings", result, sc.inputs)
    assert f"${result.total_present_value:,.2f}" in text
    assert f"${result.past_present_value:,.2f}" in text
    assert f"${result.future_present_value:,.2f}" in text
    if hasattr(result, "pre_injury"):
        assert f"${result.pre_injury.total_present_value:,.2f}" in text
        assert f"${result.residual.total_present_value:,.2f}" in text


@pytest.mark.parametrize("sc", LCP, ids=lambda s: s.id)
def test_lcp_pdf_shows_totals(sc):
    result = compute("lcp", sc.inputs)
    text = _pdf_text("lcp", result, sc.inputs)
    assert f"${result.lifetime_present_value:,.2f}" in text
    assert f"${result.lifetime_excluding_overlap():,.2f}" in text


@pytest.mark.parametrize("sc", LHHS, ids=lambda s: s.id)
def test_lhhs_pdf_shows_totals(sc):
    result = compute("lhhs", sc.inputs)
    text = _pdf_text("lhhs", result, sc.inputs)
    assert f"${result.total_present_value:,.2f}" in text
    assert f"${result.past_present_value:,.2f}" in text
    assert f"${result.future_present_value:,.2f}" in text
