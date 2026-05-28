"""Economic loss route (Tinari algebraic method).

Form rates are entered as percents and converted to a canonical input dict with
DECIMAL rates. That dict is what gets computed, embedded for save/export, and
stored. Compute itself lives in app.compute (the single shared path).
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
from storage import CaseStore

router = APIRouter(prefix="/earnings", tags=["earnings"])
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates")
)

# Default form values (percents where noted), reproducing the Tinari example.
# residual_* describe the post-injury residual earning capacity used only for
# personal-injury (PI) cases; they are ignored for wrongful death.
_DEFAULTS = {
    "case_type": "WD", "base_earnings": 93628.0, "base_year": 2008,
    "start_year": 2009, "end_year": 2022, "valuation_year": 2015,
    "growth_past": 3.1, "growth_future": 3.8, "growth_switch_year": 2016,
    "discount_rate": 3.25, "worklife": 91.9, "unemployment": 3.5, "tax": 12.0,
    "fringe": 0.0, "pc_initial": 25.0, "pc_later": 20.0, "pc_switch_year": 2016,
    "partial_years": "2009:0.33,2022:0.26",
    "residual_base_earnings": 0.0, "residual_worklife": 91.9,
    "residual_unemployment": 3.5, "residual_tax": 12.0, "residual_fringe": 0.0,
}


def _pct(value: str) -> float:
    return float(value) / 100.0


def _parse_partial_years(raw: str) -> dict[int, float]:
    out: dict[int, float] = {}
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        year_s, portion_s = chunk.split(":")
        out[int(year_s)] = float(portion_s)
    return out


def _canonical_inputs(form: dict) -> dict:
    """Form values (percents) -> canonical input dict (decimals)."""
    inputs = {
        "case_type": form["case_type"],
        "base_earnings": float(form["base_earnings"]),
        "base_year": int(form["base_year"]),
        "start_year": int(form["start_year"]),
        "end_year": int(form["end_year"]),
        "valuation_year": int(form["valuation_year"]),
        "growth_past": _pct(form["growth_past"]),
        "growth_future": _pct(form["growth_future"]),
        "growth_switch_year": int(form["growth_switch_year"]),
        "discount_rate": _pct(form["discount_rate"]),
        "worklife": _pct(form["worklife"]),
        "unemployment": _pct(form["unemployment"]),
        "tax": _pct(form["tax"]),
        "fringe": _pct(form["fringe"]),
        "pc_initial": _pct(form["pc_initial"]),
        "pc_later": _pct(form["pc_later"]),
        "pc_switch_year": int(form["pc_switch_year"]) if form["pc_switch_year"] else 0,
        "partial_years": {str(k): v
                          for k, v in _parse_partial_years(form["partial_years"]).items()},
    }
    # Personal injury: attach the residual (post-injury) capacity stream when a
    # positive residual base is supplied. Omitting it means total disability.
    if form["case_type"].upper() == "PI" and float(form.get("residual_base_earnings") or 0) > 0:
        inputs["residual"] = {
            "base_earnings": float(form["residual_base_earnings"]),
            "worklife": _pct(form["residual_worklife"]),
            "unemployment": _pct(form["residual_unemployment"]),
            "tax": _pct(form["residual_tax"]),
            "fringe": _pct(form["residual_fringe"]),
        }
    return inputs


def _inputs_to_form_values(inputs: dict) -> dict:
    """Canonical dict (decimals) -> form values (percents) for prefill."""
    py = ",".join(f"{k}:{v}" for k, v in (inputs.get("partial_years") or {}).items())
    res = inputs.get("residual") or {}
    return {
        "case_type": inputs.get("case_type", "WD"),
        "base_earnings": inputs["base_earnings"],
        "base_year": inputs["base_year"],
        "start_year": inputs["start_year"],
        "end_year": inputs["end_year"],
        "valuation_year": inputs["valuation_year"],
        "growth_past": inputs["growth_past"] * 100,
        "growth_future": inputs["growth_future"] * 100,
        "growth_switch_year": inputs["growth_switch_year"],
        "discount_rate": inputs["discount_rate"] * 100,
        "worklife": inputs["worklife"] * 100,
        "unemployment": inputs["unemployment"] * 100,
        "tax": inputs.get("tax", 0.0) * 100,
        "fringe": inputs.get("fringe", 0.0) * 100,
        "pc_initial": (inputs.get("pc_initial") or 0.0) * 100,
        "pc_later": (inputs.get("pc_later") or 0.0) * 100,
        "pc_switch_year": inputs.get("pc_switch_year") or "",
        "partial_years": py,
        "residual_base_earnings": res.get("base_earnings", 0.0),
        "residual_worklife": res.get("worklife", inputs["worklife"]) * 100,
        "residual_unemployment": res.get("unemployment", inputs.get("unemployment", 0.0)) * 100,
        "residual_tax": res.get("tax", inputs.get("tax", 0.0)) * 100,
        "residual_fringe": res.get("fringe", inputs.get("fringe", 0.0)) * 100,
    }


@router.get("", response_class=HTMLResponse)
def form(
    request: Request,
    user: str = Depends(require_user),
    store: CaseStore = Depends(get_store),
    case_id: int = 0,
):
    values = dict(_DEFAULTS)
    if case_id:
        case = store.get(case_id)
        if case and case.module == "earnings":
            values = _inputs_to_form_values(case.inputs)
    return templates.TemplateResponse(
        request,
        "earnings.html",
        {"user": user, "v": values, "case_id": case_id},
    )


@router.post("/calculate", response_class=HTMLResponse)
def calculate(
    request: Request,
    user: str = Depends(require_user),
    case_type: str = Form("WD"),
    base_earnings: str = Form(...),
    base_year: str = Form(...),
    start_year: str = Form(...),
    end_year: str = Form(...),
    valuation_year: str = Form(...),
    growth_past: str = Form(...),
    growth_future: str = Form(...),
    growth_switch_year: str = Form(...),
    discount_rate: str = Form(...),
    worklife: str = Form(...),
    unemployment: str = Form(...),
    tax: str = Form("0"),
    fringe: str = Form("0"),
    pc_initial: str = Form("0"),
    pc_later: str = Form("0"),
    pc_switch_year: str = Form(""),
    partial_years: str = Form(""),
    residual_base_earnings: str = Form("0"),
    residual_worklife: str = Form("0"),
    residual_unemployment: str = Form("0"),
    residual_tax: str = Form("0"),
    residual_fringe: str = Form("0"),
    case_id: int = Form(0),
):
    inputs = _canonical_inputs(locals())
    result = compute("earnings", inputs)
    return templates.TemplateResponse(
        request,
        "_earnings_result.html",
        {
            "result": result,
            "module": "earnings",
            "inputs_json": json.dumps(inputs),
            "case_id": case_id,
        },
    )
