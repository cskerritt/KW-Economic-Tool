"""Render an engine result to downloadable bytes (xlsx, docx, or PDF).

Each module has a natural spreadsheet/word format plus a shared PDF report:
    earnings -> xlsx, lcp -> xlsx, lhhs -> docx; any module -> pdf (fmt="pdf").
Returns (bytes, filename, media_type). Imports the export libraries lazily so
the rest of the app does not require them unless an export is requested.
"""

from __future__ import annotations

from io import BytesIO

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_PDF = "application/pdf"

_PDF_NAME = {
    "earnings": "economic_loss_report.pdf",
    "lcp": "life_care_plan_report.pdf",
    "lhhs": "household_services_report.pdf",
}


def export_result(
    module: str,
    result,
    *,
    fmt: str = "native",
    inputs: dict | None = None,
    firm: str = "Forensic Economic Analysis",
    author: str = "",
) -> tuple[bytes, str, str]:
    buf = BytesIO()

    if fmt == "pdf":
        from exports import pdf_report

        pdf_report(module, result, buf, inputs=inputs, firm=firm, author=author)
        if module not in _PDF_NAME:
            raise ValueError(f"unknown module: {module}")
        return buf.getvalue(), _PDF_NAME[module], _PDF

    from exports import earnings_workbook, lcp_workbook, lhhs_report

    sources = (inputs or {}).get("sources") or []

    if module == "earnings":
        earnings_workbook(result, buf, sources=sources)
        return buf.getvalue(), "economic_loss.xlsx", _XLSX
    if module == "lcp":
        lcp_workbook(result, buf, sources=sources)
        return buf.getvalue(), "life_care_plan.xlsx", _XLSX
    if module == "lhhs":
        lhhs_report(result, buf, sources=sources)
        return buf.getvalue(), "household_services.docx", _DOCX
    raise ValueError(f"unknown module: {module}")
