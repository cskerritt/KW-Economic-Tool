"""Life care plan route (DED Medical Care Cost Index).

Items are entered as a JSON array. growth_rate per item is a DECIMAL from the
Medical Care Cost Index (real medical inflation + expected general inflation).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth import require_user
from app.compute import compute, discount_mode_label
from app.deps import get_store
from storage import CaseStore

router = APIRouter(prefix="/lcp", tags=["lcp"])
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates")
)


def _parse_sources(raw) -> list:
    """Lookup provenance captured client-side (report-appendix metadata)."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (ValueError, TypeError):
        return []

_DEFAULT_ITEMS = [
    {"name": "Physician visits", "category": "Physician", "cost_per_unit": 200,
     "start_year": 2026, "end_year": 2028, "growth_rate": 0.037,
     "base_year": 2026, "units_per_year": 4, "source": "Dr. Smith 2026 fee schedule"},
    {"name": "Wheelchair", "category": "DME", "cost_per_unit": 3000,
     "start_year": 2026, "end_year": 2036, "growth_rate": 0.03,
     "base_year": 2026, "replacement_years": 5, "source": "Vendor quote"},
    {"name": "Home health aide", "category": "Attendant care", "cost_per_unit": 50000,
     "start_year": 2026, "end_year": 2027, "growth_rate": 0.035, "base_year": 2026,
     "units_per_year": 1, "overlaps_household": True, "source": "Agency rate"},
]


@router.get("", response_class=HTMLResponse)
def form(
    request: Request,
    user: str = Depends(require_user),
    store: CaseStore = Depends(get_store),
    case_id: int = 0,
):
    values = {"discount_rate": 3.0, "valuation_year": 2025,
              "discount_mode": "standard",
              "items_json": json.dumps(_DEFAULT_ITEMS, indent=2)}
    if case_id:
        case = store.get(case_id)
        if case and case.module == "lcp":
            values = {
                "discount_rate": case.inputs["discount_rate"] * 100,
                "valuation_year": case.inputs["valuation_year"],
                "discount_mode": case.inputs.get("discount_mode", "standard"),
                "sources_json": json.dumps(case.inputs.get("sources", [])),
                "items_json": json.dumps(case.inputs["items"], indent=2),
            }
    return templates.TemplateResponse(
        request, "lcp.html", {"user": user, "v": values, "case_id": case_id}
    )


@router.post("/calculate", response_class=HTMLResponse)
def calculate(
    request: Request,
    user: str = Depends(require_user),
    discount_rate: str = Form(...),
    valuation_year: int = Form(...),
    items_json: str = Form(...),
    discount_mode: str = Form("standard"),
    sources_json: str = Form("[]"),
    case_id: int = Form(0),
):
    inputs = {
        "discount_rate": float(discount_rate) / 100.0,
        "valuation_year": valuation_year,
        "discount_mode": discount_mode or "standard",
        "sources": _parse_sources(sources_json),
        "items": json.loads(items_json),
    }
    result = compute("lcp", inputs)
    return templates.TemplateResponse(
        request,
        "_lcp_result.html",
        {"result": result, "module": "lcp",
         "inputs_json": json.dumps(inputs), "case_id": case_id,
         "mode_label": discount_mode_label(inputs)},
    )
