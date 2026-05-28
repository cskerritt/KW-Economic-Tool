"""Loss of household services route (DED replacement-cost six-step).

Stages are entered as a JSON array. weekly_hours and hourly_value come from the
matched Expectancy Data DVD table; loss_percent (0..1) reflects functional
limitations and declining health.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth import require_user
from app.compute import compute
from app.deps import get_store
from datasets import list_demographics
from storage import CaseStore

router = APIRouter(prefix="/lhhs", tags=["lhhs"])
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates")
)

_DEFAULT_STAGES = [
    {"start_year": 2026, "end_year": 2028, "weekly_hours": 20,
     "hourly_value": 15, "loss_percent": 0.5},
    {"start_year": 2029, "end_year": 2030, "weekly_hours": 25,
     "hourly_value": 15, "loss_percent": 1.0},
]


@router.get("", response_class=HTMLResponse)
def form(
    request: Request,
    user: str = Depends(require_user),
    store: CaseStore = Depends(get_store),
    case_id: int = 0,
):
    values = {
        "base_year": 2026, "valuation_year": 2025, "growth_rate": 3.0,
        "discount_rate": 3.0, "area_wage_factor": 100.0, "self_consumption": 0.0,
        "stages_json": json.dumps(_DEFAULT_STAGES, indent=2),
    }
    if case_id:
        case = store.get(case_id)
        if case and case.module == "lhhs":
            i = case.inputs
            values = {
                "base_year": i["base_year"],
                "valuation_year": i["valuation_year"],
                "growth_rate": i["growth_rate"] * 100,
                "discount_rate": i["discount_rate"] * 100,
                "area_wage_factor": i.get("area_wage_factor", 1.0) * 100,
                "self_consumption": i.get("self_consumption", 0.0) * 100,
                "stages_json": json.dumps(i["stages"], indent=2),
            }
    return templates.TemplateResponse(
        request,
        "lhhs.html",
        {"user": user, "v": values, "case_id": case_id,
         "demographics": list_demographics()},
    )


@router.post("/calculate", response_class=HTMLResponse)
def calculate(
    request: Request,
    user: str = Depends(require_user),
    base_year: int = Form(...),
    valuation_year: int = Form(...),
    growth_rate: str = Form(...),
    discount_rate: str = Form(...),
    area_wage_factor: str = Form("100"),
    self_consumption: str = Form("0"),
    stages_json: str = Form(...),
    case_id: int = Form(0),
):
    inputs = {
        "base_year": base_year,
        "valuation_year": valuation_year,
        "growth_rate": float(growth_rate) / 100.0,
        "discount_rate": float(discount_rate) / 100.0,
        "area_wage_factor": float(area_wage_factor) / 100.0,
        "self_consumption": float(self_consumption) / 100.0,
        "stages": json.loads(stages_json),
    }
    result = compute("lhhs", inputs)
    return templates.TemplateResponse(
        request,
        "_lhhs_result.html",
        {"result": result, "module": "lhhs",
         "inputs_json": json.dumps(inputs), "case_id": case_id},
    )
