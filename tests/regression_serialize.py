"""Turn an engine result into a plain JSON-able dict for snapshotting.

Used by both the baseline generator and the snapshot regression test, so the
frozen baseline and the live comparison are produced by identical code. Captures
every number the engine emits: the totals AND every year/item row, so a
regression anywhere in the projection (not just in a grand total) is caught.
"""

from __future__ import annotations

from typing import Any


def result_to_dict(module: str, result: Any) -> dict:
    if module == "earnings":
        return _earnings(result)
    if module == "lcp":
        return _lcp(result)
    if module == "lhhs":
        return _lhhs(result)
    raise ValueError(f"unknown module: {module}")


def _earnings(r: Any) -> dict:
    d: dict[str, Any] = {
        "total_present_value": r.total_present_value,
        "past_present_value": r.past_present_value,
        "future_present_value": r.future_present_value,
        "rows": [
            {
                "year": row.year,
                "portion": row.portion,
                "gross_earnings": row.gross_earnings,
                "aif": row.aif,
                "adjusted_income": row.adjusted_income,
                "present_value": row.present_value,
                "is_future": row.is_future,
            }
            for row in r.rows
        ],
    }
    # Personal-injury results retain both component streams.
    if hasattr(r, "pre_injury"):
        d["pre_injury_total"] = r.pre_injury.total_present_value
        d["residual_total"] = r.residual.total_present_value
    return d


def _lcp(r: Any) -> dict:
    return {
        "lifetime_present_value": r.lifetime_present_value,
        "household_overlap_present_value": r.household_overlap_present_value,
        "lifetime_excluding_overlap": r.lifetime_excluding_overlap(),
        "category_present_value": dict(r.category_present_value),
        "items": [
            {
                "name": it.name,
                "category": it.category,
                "overlaps_household": it.overlaps_household,
                "nominal_total": it.nominal_total,
                "present_value": it.present_value,
                "occurrences": it.occurrences,
            }
            for it in r.items
        ],
    }


def _lhhs(r: Any) -> dict:
    return {
        "total_present_value": r.total_present_value,
        "past_present_value": r.past_present_value,
        "future_present_value": r.future_present_value,
        "rows": [
            {
                "year": row.year,
                "base_annual_value": row.base_annual_value,
                "loss_percent": row.loss_percent,
                "annual_loss": row.annual_loss,
                "present_value": row.present_value,
                "is_future": row.is_future,
            }
            for row in r.rows
        ],
    }
