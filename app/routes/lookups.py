"""JSON lookup endpoints backed by the reference-data layer.

Used by the form helpers to auto-fill values (DVD household-production hours,
area-wage factor, worklife ratio, life expectancy) without leaving the page.
"""

from __future__ import annotations

import urllib.error

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_user
from datasets import (
    area_wage_factor,
    category_growth,
    household_production,
    life_expectancy,
    list_categories,
    long_term,
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


@router.get("/assumptions")
def assumptions(user: str = Depends(require_user)):
    """Suggested growth/discount anchors (in PERCENT, for the forms) from the
    SPF long-term medians, plus a citation string for the report appendix.

    discount_rate = 10-yr Treasury; cpi_inflation = CPI; wage_growth = CPI +
    productivity (a nominal-wage proxy); household_growth = CPI (ECI is not in
    the bundled data). All are starting anchors the user can edit, not opinions.
    """
    lt = long_term()
    cpi = lt.get("cpi_inflation") or 0.0
    prod = lt.get("productivity_growth") or 0.0
    bond = lt.get("bond_rate_10yr") or 0.0
    return {
        "discount_rate": round(bond, 2),
        "cpi_inflation": round(cpi, 2),
        "wage_growth": round(cpi + prod, 2),
        "household_growth": round(cpi, 2),
        "source": (
            f"SPF Q1 2026 long-term medians (2026–2035): CPI {cpi:.2f}%, "
            f"productivity {prod:.2f}%, 10-yr Treasury {bond:.2f}%"
        ),
    }


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
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        # FRED unreachable / slow / rate-limited: fail cleanly, not a 500.
        raise HTTPException(504, f"FRED is unreachable right now: {e}")
    except ValueError as e:
        raise HTTPException(502, f"FRED data problem: {e}")
