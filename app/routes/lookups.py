"""JSON lookup endpoints backed by the reference-data layer.

Used by the form helpers to auto-fill values (DVD household-production hours,
area-wage factor, worklife ratio, life expectancy) without leaving the page.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_user
from datasets import (
    area_wage_factor,
    category_growth,
    household_production,
    life_expectancy,
    list_categories,
    worklife_expectancy,
    worklife_ratio,
)

router = APIRouter(prefix="/lookups", tags=["lookups"])


@router.get("/dvd")
def dvd(table_num: int, user: str = Depends(require_user)):
    if not 1 <= table_num <= 385:
        raise HTTPException(404, "DVD table must be 1-385")
    return household_production(table_num)


@router.get("/area")
def area(area: str, user: str = Depends(require_user)):
    return {"area": area, "factor": area_wage_factor(area)}


@router.get("/worklife")
def worklife(
    sex: str,
    initial_state: str,
    education: str,
    age: int,
    user: str = Depends(require_user),
):
    try:
        row = worklife_expectancy(sex, initial_state, education, age)
        ratio = worklife_ratio(sex, initial_state, education, age)
    except KeyError as e:
        raise HTTPException(404, str(e))
    return {"wle_mean": float(row["wle_mean"]), "worklife_ratio": ratio}


@router.get("/life-expectancy")
def life(area: str, sex: str = "total", at: str = "birth",
         user: str = Depends(require_user)):
    return {"area": area, "sex": sex, "at": at,
            "life_expectancy": life_expectancy(area, sex, at)}


@router.get("/lcp-categories")
def lcp_categories(user: str = Depends(require_user)):
    """CPI medical categories available for the LCP growth-rate helper."""
    return {"categories": list_categories()}


@router.get("/lcp-growth")
def lcp_growth(
    category: str,
    years: int = 10,
    general_inflation: float = 0.0,
    user: str = Depends(require_user),
):
    """Compose an LCP item growth rate from FRED CPI series (Medical Care Cost
    Index). general_inflation is a DECIMAL (e.g. 0.023 for the CBO 2.3% CPI
    projection). Returns the rate plus its components and source for the audit
    trail. 503 if FRED_API_KEY is not configured; 404 for an unknown category."""
    if not 1 <= years <= 30:
        raise HTTPException(400, "years must be 1-30")
    try:
        return category_growth(
            category, years=years, expected_general_inflation=general_inflation
        )
    except KeyError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:  # missing FRED_API_KEY
        raise HTTPException(503, str(e))
    except ValueError as e:
        raise HTTPException(502, f"FRED data problem: {e}")
