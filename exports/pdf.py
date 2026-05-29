"""PDF report export (reportlab) for all three damages modules.

A narrative expert-report style document: title block, cited methodology, the
assumptions that drove the calculation, a year-by-year (or item) results table,
and the present-value totals. Like the xlsx and docx exporters, this module does
NO math - it only formats the engine's typed result plus the canonical input
dict that produced it.

reportlab is a pure-Python dependency (no system libraries), so this works on a
plain Railway container. It is imported lazily by ``app.exporting`` so the rest
of the app does not require it unless a PDF is requested.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

NAVY = colors.HexColor("#1f2a44")
GOLD = colors.HexColor("#8c6a1f")
LIGHT = colors.HexColor("#eef1f6")
GREY = colors.HexColor("#666666")

_TITLE = {
    "earnings": "Economic Loss — Lost Earnings",
    "lcp": "Life Care Plan — Cost Projection",
    "lhhs": "Loss of Household Services",
}

# Display labels for the discounting basis (kept here so the exporter has no
# dependency on the app layer). Mirrors app.compute.DISCOUNT_MODE_LABELS.
_MODE_LABEL = {
    "standard": "Standard (discounted to present value)",
    "nominal": "Undiscounted (nominal future dollars)",
    "offset_zero": "Total offset (no growth, no discount)",
    "offset_match": "Total offset (growth offsets discount)",
}


def _mode(inputs: dict) -> str:
    m = str(inputs.get("discount_mode", "standard") or "standard")
    return m if m in _MODE_LABEL else "standard"

_METHOD = {
    "earnings": (
        "Lost earnings are computed by the Tinari algebraic method (Tinari, "
        '"Demonstrating Lost Earnings: Algebraic vs. Spreadsheet Method," The '
        "Earnings Analyst, Vol. 15, 2016). An Adjusted Income Factor combining "
        "worklife, unemployment, fringe, tax, and (in wrongful death) personal "
        "consumption is applied to grown gross earnings each year; future years "
        "are discounted to present value at the net discount rate."
    ),
    "lcp": (
        "Life care plan costs follow the DED Medical Care Cost Index method "
        "(Determining Economic Damages, Ch. 9 §920/§903). Each item is "
        "grown at its category-specific medical growth rate across its frequency "
        "and replacement cycle, then discounted to present value and summed per "
        "category and as a lifetime total."
    ),
    "lhhs": (
        "Loss of household services uses the DED replacement-cost six-step method "
        "(Determining Economic Damages, Ch. 6) with weekly hours and values from "
        "the Expectancy Data Dollar Value of a Day tables, grown for wage "
        "inflation and discounted to present value."
    ),
}


# --- formatting helpers (display only) --------------------------------------

def _money(v: float) -> str:
    return f"${v:,.0f}"


def _money2(v: float) -> str:
    return f"${v:,.2f}"


def _pct(decimal_rate: float, places: int = 2) -> str:
    return f"{decimal_rate * 100:.{places}f}%"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    s: dict[str, ParagraphStyle] = {}
    s["firm"] = ParagraphStyle(
        "firm", parent=base["Normal"], fontName="Helvetica-Bold",
        fontSize=10, textColor=GOLD, spaceAfter=2,
    )
    s["title"] = ParagraphStyle(
        "title", parent=base["Title"], fontName="Helvetica-Bold",
        fontSize=18, textColor=NAVY, spaceAfter=2, alignment=0,
    )
    s["sub"] = ParagraphStyle(
        "sub", parent=base["Normal"], fontSize=9, textColor=GREY, spaceAfter=10,
    )
    s["h2"] = ParagraphStyle(
        "h2", parent=base["Heading2"], fontName="Helvetica-Bold",
        fontSize=11, textColor=NAVY, spaceBefore=12, spaceAfter=4,
    )
    s["body"] = ParagraphStyle(
        "body", parent=base["Normal"], fontSize=9.5, leading=13, spaceAfter=6,
    )
    s["cell"] = ParagraphStyle("cell", parent=base["Normal"], fontSize=8.5, leading=11)
    s["foot"] = ParagraphStyle(
        "foot", parent=base["Normal"], fontSize=8, textColor=GREY, alignment=TA_CENTER,
    )
    return s


def _kv_table(rows: list[tuple[str, str]]) -> Table:
    data = [[k, v] for k, v in rows]
    t = Table(data, colWidths=[2.4 * inch, 4.1 * inch], hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("TEXTCOLOR", (0, 0), (0, -1), NAVY),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def _data_table(headers: list[str], rows: list[list[str]], col_widths: list[float],
                right_cols: tuple[int, ...]) -> Table:
    data = [headers] + rows
    t = Table(data, colWidths=col_widths, hAlign="LEFT", repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, NAVY),
    ]
    for c in right_cols:
        style.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
    t.setStyle(TableStyle(style))
    return t


def _totals_table(rows: list[tuple[str, float]]) -> Table:
    data = [[label, _money2(value)] for label, value in rows]
    t = Table(data, colWidths=[4.9 * inch, 1.6 * inch], hAlign="LEFT")
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEABOVE", (0, -1), (-1, -1), 0.75, NAVY),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, -1), (-1, -1), NAVY),
    ]
    t.setStyle(TableStyle(style))
    return t


# --- per-module content -----------------------------------------------------

def _earnings_flowables(result: Any, inputs: dict, st: dict) -> list:
    is_pi = hasattr(result, "pre_injury")
    flow: list = []

    # Assumptions
    flow.append(Paragraph("Assumptions", st["h2"]))
    rows = [
        ("Case type", "Personal injury" if is_pi else "Wrongful death"),
        ("Base earnings", f"{_money(float(inputs.get('base_earnings', 0)))} "
                          f"({inputs.get('base_year', '')})"),
        ("Loss period",
         f"{inputs.get('start_year', '')}–{inputs.get('end_year', '')}, "
         f"valued at {inputs.get('valuation_year', '')}"),
        ("Wage growth",
         f"{_pct(float(inputs.get('growth_past', 0)))} past / "
         f"{_pct(float(inputs.get('growth_future', 0)))} future "
         f"(switch {inputs.get('growth_switch_year', '')})"),
        ("Discount rate", _pct(float(inputs.get("discount_rate", 0)))),
        ("Discounting basis", _MODE_LABEL[_mode(inputs)]),
        ("Worklife ratio", _pct(float(inputs.get("worklife", 0)))),
        ("Unemployment factor", _pct(float(inputs.get("unemployment", 0)))),
        ("Tax rate", _pct(float(inputs.get("tax", 0)))),
        ("Fringe rate", _pct(float(inputs.get("fringe", 0)))),
    ]
    if not is_pi:
        rows.append((
            "Personal consumption",
            f"{_pct(float(inputs.get('pc_initial', 0)))}"
            + (f" → {_pct(float(inputs['pc_later']))} from {inputs.get('pc_switch_year')}"
               if inputs.get("pc_later") not in (None, "", 0, 0.0) and inputs.get("pc_switch_year")
               else ""),
        ))
    else:
        res = inputs.get("residual") or {}
        if float(res.get("base_earnings", 0) or 0) > 0:
            rows.append((
                "Residual capacity",
                f"{_money(float(res['base_earnings']))} base, "
                f"WLE {_pct(float(res.get('worklife', 0)))}, "
                f"UF {_pct(float(res.get('unemployment', 0)))}, "
                f"tax {_pct(float(res.get('tax', 0)))}",
            ))
        else:
            rows.append(("Residual capacity", "None (total disability)"))
    flow.append(_kv_table(rows))

    # PI stream summary
    if is_pi:
        flow.append(Paragraph("Net loss derivation", st["h2"]))
        flow.append(_totals_table([
            ("Pre-injury earning capacity (present value)", result.pre_injury.total_present_value),
            ("Less: residual (post-injury) capacity", result.residual.total_present_value),
            ("Net personal-injury loss", result.total_present_value),
        ]))

    # Year-by-year table
    flow.append(Paragraph("Year-by-year projection", st["h2"]))
    headers = ["Year", "Portion", "Gross earnings", "AIF", "Adjusted income", "Present value"]
    data_rows = [
        [
            str(r.year), f"{r.portion * 100:.0f}%", _money(r.gross_earnings),
            f"{r.aif * 100:.2f}%", _money(r.adjusted_income), _money(r.present_value),
        ]
        for r in result.rows
    ]
    flow.append(_data_table(
        headers, data_rows,
        [0.6 * inch, 0.65 * inch, 1.35 * inch, 0.7 * inch, 1.4 * inch, 1.3 * inch],
        right_cols=(2, 3, 4, 5),
    ))
    flow.append(Spacer(1, 8))
    flow.append(_totals_table([
        ("Past present value", result.past_present_value),
        ("Future present value", result.future_present_value),
        ("Total present value", result.total_present_value),
    ]))
    return flow


def _lcp_flowables(result: Any, inputs: dict, st: dict) -> list:
    flow: list = []
    flow.append(Paragraph("Assumptions", st["h2"]))
    flow.append(_kv_table([
        ("Discount rate", _pct(float(inputs.get("discount_rate", 0)))),
        ("Discounting basis", _MODE_LABEL[_mode(inputs)]),
        ("Valuation year", str(inputs.get("valuation_year", ""))),
        ("Line items", str(len(result.items))),
    ]))

    flow.append(Paragraph("Cost items", st["h2"]))
    headers = ["Item", "Category", "Occurrences", "Nominal total", "Present value", "Overlaps LHHS"]
    data_rows = [
        [
            it.name, it.category, str(it.occurrences),
            _money(it.nominal_total), _money(it.present_value),
            "yes" if it.overlaps_household else "",
        ]
        for it in result.items
    ]
    flow.append(_data_table(
        headers, data_rows,
        [1.7 * inch, 1.1 * inch, 0.85 * inch, 1.05 * inch, 1.0 * inch, 0.8 * inch],
        right_cols=(2, 3, 4),
    ))

    flow.append(Paragraph("By category (present value)", st["h2"]))
    flow.append(_kv_table([
        (cat, _money2(pv)) for cat, pv in result.category_present_value.items()
    ]))

    flow.append(Spacer(1, 8))
    flow.append(_totals_table([
        ("Lifetime present value", result.lifetime_present_value),
        ("Household-services overlap (net out of LHHS)", result.household_overlap_present_value),
        ("Lifetime excluding overlap", result.lifetime_excluding_overlap()),
    ]))
    return flow


def _lhhs_flowables(result: Any, inputs: dict, st: dict) -> list:
    flow: list = []
    flow.append(Paragraph("Assumptions", st["h2"]))
    flow.append(_kv_table([
        ("Base year", str(inputs.get("base_year", ""))),
        ("Valuation year", str(inputs.get("valuation_year", ""))),
        ("Wage growth", _pct(float(inputs.get("growth_rate", 0)))),
        ("Discount rate", _pct(float(inputs.get("discount_rate", 0)))),
        ("Area-wage factor", _pct(float(inputs.get("area_wage_factor", 1.0)))),
        ("Self-consumption", _pct(float(inputs.get("self_consumption", 0)))),
        ("Discounting basis", _MODE_LABEL[_mode(inputs)]),
    ]))

    flow.append(Paragraph("Year-by-year projection", st["h2"]))
    headers = ["Year", "Annual value (grown)", "Loss %", "Annual loss", "Present value"]
    data_rows = [
        [
            str(r.year), _money(r.base_annual_value), f"{r.loss_percent * 100:.0f}%",
            _money(r.annual_loss), _money(r.present_value),
        ]
        for r in result.rows
    ]
    flow.append(_data_table(
        headers, data_rows,
        [0.8 * inch, 1.7 * inch, 0.9 * inch, 1.4 * inch, 1.4 * inch],
        right_cols=(1, 2, 3, 4),
    ))
    flow.append(Spacer(1, 8))
    flow.append(_totals_table([
        ("Past present value", result.past_present_value),
        ("Future present value", result.future_present_value),
        ("Total present value", result.total_present_value),
    ]))
    return flow


_SECTION = {
    "earnings": _earnings_flowables,
    "lcp": _lcp_flowables,
    "lhhs": _lhhs_flowables,
}


def _appendix_flowables(sources: list, st: dict) -> list:
    """Render the raw look-up data behind the numbers as a report appendix."""
    if not sources:
        return []
    flow: list = [PageBreak(), Paragraph("Appendix: raw data and sources", st["h2"])]
    for src in sources:
        flow.append(Paragraph(src.get("title", ""), st["h2"]))
        if src.get("citation"):
            flow.append(Paragraph(src["citation"], st["sub"]))
        cols = src.get("columns") or []
        rows = src.get("rows") or []
        if cols and rows:
            data_rows = [[str(c) for c in row] for row in rows]
            n = max(len(cols), 1)
            flow.append(_data_table(
                [str(c) for c in cols], data_rows,
                [6.5 * inch / n] * n, right_cols=(),
            ))
            flow.append(Spacer(1, 8))
    return flow


def pdf_report(
    module: str,
    result: Any,
    buf,
    *,
    inputs: dict | None = None,
    firm: str = "Forensic Economic Analysis",
    author: str = "",
) -> None:
    """Render ``result`` (with its ``inputs``) to a styled PDF into ``buf``."""
    if module not in _SECTION:
        raise ValueError(f"unknown module: {module}")
    inputs = inputs or {}
    st = _styles()

    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
        title=_TITLE[module], author=author or firm,
    )

    flow: list = [
        Paragraph(firm, st["firm"]),
        Paragraph(_TITLE[module], st["title"]),
        Paragraph(f"Prepared {date.today():%B %-d, %Y}", st["sub"]),
        HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=8),
        Paragraph("Methodology", st["h2"]),
        Paragraph(_METHOD[module], st["body"]),
    ]
    flow.extend(_SECTION[module](result, inputs, st))
    flow.extend(_appendix_flowables(inputs.get("sources") or [], st))

    if author:
        flow.append(Spacer(1, 24))
        flow.append(HRFlowable(width="40%", thickness=0.5, color=GREY, spaceAfter=4))
        flow.append(Paragraph(author, st["body"]))

    flow.append(Spacer(1, 10))
    mode = _mode(inputs)
    if mode == "standard":
        basis = ("Past losses are not discounted; future losses are discounted "
                 "to the valuation date.")
    elif mode == "nominal":
        basis = ("Losses are stated in nominal (future) dollars; no discounting "
                 "to present value has been applied.")
    else:
        basis = ("Losses are stated on a total-offset basis "
                 f"({_MODE_LABEL[mode].split('(')[1].rstrip(')')}).")
    flow.append(Paragraph(
        "Every figure traces to an input, a formula, and a cited source. " + basis,
        st["foot"],
    ))

    doc.build(flow)
