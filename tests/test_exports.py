"""Export tests.

The exporters do no math; these confirm each format produces a well-formed,
non-trivial file for every module from the shared compute path. PDF generation
needs reportlab (the optional 'export' extra), so the PDF tests skip cleanly if
it is absent.
"""

import pytest

from app.compute import compute
from app.exporting import export_result

# Inline canonical inputs (decimal rates) mirroring the compute golden cases.
EXPOSITO = {
    "case_type": "WD", "base_earnings": 93628.0, "base_year": 2008,
    "start_year": 2009, "end_year": 2022, "valuation_year": 2015,
    "growth_past": 0.031, "growth_future": 0.038, "growth_switch_year": 2016,
    "discount_rate": 0.0325, "worklife": 0.919, "unemployment": 0.035,
    "tax": 0.12, "fringe": 0.0, "pc_initial": 0.25, "pc_later": 0.20,
    "pc_switch_year": 2016, "partial_years": {"2009": 0.33, "2022": 0.26},
}
LCP = {
    "discount_rate": 0.03, "valuation_year": 2025,
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
    "base_year": 2026, "valuation_year": 2025, "growth_rate": 0.03,
    "discount_rate": 0.03, "area_wage_factor": 0.936, "self_consumption": 0.0,
    "stages": [
        {"start_year": 2026, "end_year": 2028, "weekly_hours": 20,
         "hourly_value": 15, "loss_percent": 0.5},
        {"start_year": 2029, "end_year": 2030, "weekly_hours": 25,
         "hourly_value": 15, "loss_percent": 1.0},
    ],
}

PI_DUAL = dict(
    EXPOSITO,
    case_type="PI",
    residual={"base_earnings": 40000.0, "worklife": 0.85,
              "unemployment": 0.05, "tax": 0.10},
)


def _result(module, inputs):
    return compute(module, inputs)


@pytest.mark.parametrize(
    "module,inputs,ext,sig",
    [
        ("earnings", EXPOSITO, "economic_loss.xlsx", b"PK"),
        ("lcp", LCP, "life_care_plan.xlsx", b"PK"),
        ("lhhs", LHHS, "household_services.docx", b"PK"),
    ],
)
def test_native_export_is_wellformed(module, inputs, ext, sig):
    pytest.importorskip("openpyxl")
    pytest.importorskip("docx")
    content, filename, media_type = export_result(module, _result(module, inputs))
    assert filename == ext
    assert content[:2] == sig  # xlsx and docx are zip containers
    assert len(content) > 1000


@pytest.mark.parametrize(
    "module,inputs",
    [
        ("earnings", EXPOSITO),
        ("earnings", PI_DUAL),
        ("lcp", LCP),
        ("lhhs", LHHS),
    ],
)
def test_pdf_export_is_wellformed(module, inputs):
    pytest.importorskip("reportlab")
    content, filename, media_type = export_result(
        module, _result(module, inputs), fmt="pdf", inputs=inputs,
        firm="Test Firm", author="Test Author",
    )
    assert media_type == "application/pdf"
    assert filename.endswith("_report.pdf")
    assert content[:5] == b"%PDF-"
    assert b"%%EOF" in content[-1024:]
    assert len(content) > 1500


def test_pdf_unknown_module_rejected():
    pytest.importorskip("reportlab")
    with pytest.raises(ValueError):
        export_result("nope", object(), fmt="pdf", inputs={})
