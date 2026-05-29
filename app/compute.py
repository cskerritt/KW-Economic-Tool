"""Shared compute path: canonical input dict -> engine result -> summary.

This module is the single place that turns stored/submitted inputs into engine
results. The web routes, export downloads, and MCP server all call it, so there
is exactly one code path to the math.

Canonical input dicts use DECIMAL rates (0.0325, not 3.25). Routes convert
percents to decimals before calling here, so what is stored and what the MCP
receives are unambiguous. It imports only the engine and the standard library
(no FastAPI), so it can be tested in isolation.
"""

from __future__ import annotations

from engine.earnings import (
    EarningsAssumptions,
    EarningsResult,
    PersonalInjuryResult,
    build_earnings_inputs,
    project_earnings,
    project_personal_injury,
)
from engine.lcp import LCPItem, LCPResult, project_lcp
from engine.lhhs import HouseholdStage, LHHSResult, project_lhhs

MODULES = ("earnings", "lcp", "lhhs")

# Discounting modes. The engine always discounts at the rate it is given; these
# modes only change which rates the compute layer feeds it, so the engine stays
# pure and the standard (default) path is byte-identical to before.
#
#   standard      use the entered growth and discount rates (present value).
#   nominal       keep growth, set discount = 0  -> future losses kept at their
#                 grown (future-dollar) value, undiscounted. (#1)
#   offset_zero   set growth = 0 AND discount = 0 -> classic total-offset: the
#                 sum of current-year-dollar values, no growth, no discount. (#2a)
#   offset_match  discount at the same rate as growth so they cancel exactly
#                 ("growth offsets discount"); nets future losses to today's
#                 dollars while still showing the grown amounts. (#2b)
DISCOUNT_MODES = ("standard", "nominal", "offset_zero", "offset_match")

DISCOUNT_MODE_LABELS = {
    "standard": "Standard (discounted to present value)",
    "nominal": "Undiscounted (nominal future dollars)",
    "offset_zero": "Total offset (no growth, no discount)",
    "offset_match": "Total offset (growth offsets discount)",
}


def discount_mode_label(inputs: dict) -> str:
    return DISCOUNT_MODE_LABELS.get(_mode(inputs), DISCOUNT_MODE_LABELS["standard"])


def _mode(inputs: dict) -> str:
    mode = str(inputs.get("discount_mode", "standard") or "standard")
    if mode not in DISCOUNT_MODES:
        raise ValueError(f"unknown discount_mode: {mode!r}")
    return mode


# --- earnings ---------------------------------------------------------------

def _partial_years(inputs: dict) -> dict[int, float]:
    return {int(k): float(v) for k, v in (inputs.get("partial_years") or {}).items()}


def _earnings_assumptions(
    inputs: dict,
    *,
    base_earnings: float,
    worklife: float,
    unemployment: float,
    tax: float,
    fringe: float,
    base_year: int,
    pc_initial: float = 0.0,
    pc_later: float | None = None,
    pc_switch_year: int | None = None,
    partial_years: dict[int, float] | None = None,
) -> EarningsAssumptions:
    """Build one earnings stream from the shared timeline plus stream-specific
    earnings and adjustment factors. The timeline (start/end/valuation/growth/
    discount) always comes from the top-level ``inputs`` so both PI streams stay
    aligned year for year."""
    return EarningsAssumptions(
        base_earnings=base_earnings,
        base_year=base_year,
        start_year=int(inputs["start_year"]),
        end_year=int(inputs["end_year"]),
        valuation_year=int(inputs["valuation_year"]),
        growth_past=float(inputs["growth_past"]),
        growth_future=float(inputs["growth_future"]),
        growth_switch_year=int(inputs["growth_switch_year"]),
        discount_rate=float(inputs["discount_rate"]),
        worklife=worklife,
        unemployment=unemployment,
        tax=tax,
        fringe=fringe,
        personal_consumption_initial=pc_initial,
        personal_consumption_later=pc_later,
        pc_switch_year=pc_switch_year,
        partial_years=_partial_years(inputs) if partial_years is None else partial_years,
    )


def _project(a: EarningsAssumptions) -> EarningsResult:
    return project_earnings(build_earnings_inputs(a), a.discount_rate, a.valuation_year)


def _earnings_rates(inputs: dict) -> dict:
    """Return {growth_past, growth_future, discount_rate} adjusted for the mode.

    The timeline (start/end/valuation/switch) is unchanged; only the rates move.
    """
    gp = float(inputs["growth_past"])
    gf = float(inputs["growth_future"])
    dr = float(inputs["discount_rate"])
    mode = _mode(inputs)
    if mode == "nominal":
        dr = 0.0
    elif mode == "offset_zero":
        gp = gf = 0.0
        dr = 0.0
    elif mode == "offset_match":
        # Discount future years at the future growth rate so they cancel.
        dr = gf
    return {"growth_past": gp, "growth_future": gf, "discount_rate": dr}


def earnings_result(inputs: dict) -> EarningsResult | PersonalInjuryResult:
    inputs = {**inputs, **_earnings_rates(inputs)}
    is_pi = str(inputs.get("case_type", "WD")).upper() == "PI"

    if not is_pi:
        # Wrongful death: a single stream with the personal-consumption deduction.
        a = _earnings_assumptions(
            inputs,
            base_earnings=float(inputs["base_earnings"]),
            base_year=int(inputs["base_year"]),
            worklife=float(inputs["worklife"]),
            unemployment=float(inputs["unemployment"]),
            tax=float(inputs.get("tax", 0.0)),
            fringe=float(inputs.get("fringe", 0.0)),
            pc_initial=float(inputs.get("pc_initial", 0.0)),
            pc_later=inputs.get("pc_later"),
            pc_switch_year=inputs.get("pc_switch_year") or None,
        )
        return _project(a)

    # Personal injury: pre-injury capacity minus residual capacity, PC = 0 on
    # both streams. The residual stream is optional; absent or zero-base it means
    # total disability and the net loss equals the pre-injury stream.
    pre = _project(
        _earnings_assumptions(
            inputs,
            base_earnings=float(inputs["base_earnings"]),
            base_year=int(inputs["base_year"]),
            worklife=float(inputs["worklife"]),
            unemployment=float(inputs["unemployment"]),
            tax=float(inputs.get("tax", 0.0)),
            fringe=float(inputs.get("fringe", 0.0)),
        )
    )
    res = inputs.get("residual") or {}
    residual = _project(
        _earnings_assumptions(
            inputs,
            base_earnings=float(res.get("base_earnings", 0.0)),
            # Residual capacity defaults to the pre-injury cohort/timeline but
            # each adjustment factor can be overridden for the impaired worker.
            base_year=int(res.get("base_year", inputs["base_year"])),
            worklife=float(res.get("worklife", inputs["worklife"])),
            unemployment=float(res.get("unemployment", inputs.get("unemployment", 0.0))),
            tax=float(res.get("tax", inputs.get("tax", 0.0))),
            fringe=float(res.get("fringe", inputs.get("fringe", 0.0))),
        )
    )
    return project_personal_injury(pre, residual)


def _earnings_summary(r: EarningsResult | PersonalInjuryResult) -> dict:
    return {
        "total_present_value": round(r.total_present_value, 2),
        "past_present_value": round(r.past_present_value, 2),
        "future_present_value": round(r.future_present_value, 2),
        "years": len(r.rows),
    }


# --- life care plan ---------------------------------------------------------

def _lcp_item(i: dict, *, growth_override: float | None = None) -> LCPItem:
    return LCPItem(
        name=i["name"],
        category=i["category"],
        cost_per_unit=float(i["cost_per_unit"]),
        start_year=int(i["start_year"]),
        end_year=int(i["end_year"]),
        growth_rate=(growth_override if growth_override is not None
                     else float(i["growth_rate"])),
        base_year=int(i["base_year"]),
        units_per_year=float(i.get("units_per_year", 1.0)),
        replacement_years=(int(i["replacement_years"])
                           if i.get("replacement_years") else None),
        overlaps_household=bool(i.get("overlaps_household", False)),
        source=i.get("source", ""),
    )


def lcp_result(inputs: dict) -> LCPResult:
    mode = _mode(inputs)
    valuation_year = int(inputs["valuation_year"])

    if mode == "offset_match":
        # Each item is discounted at its OWN growth rate so the two cancel; a
        # single global discount rate cannot express that, so project per item
        # and merge. Growth is kept (shown grown, then offset to today's dollars).
        merged_items: list = []
        category_pv: dict[str, float] = {}
        lifetime = overlap = 0.0
        for i in inputs["items"]:
            item = _lcp_item(i)
            r = project_lcp([item], item.growth_rate, valuation_year)
            merged_items.extend(r.items)
            for cat, pv in r.category_present_value.items():
                category_pv[cat] = category_pv.get(cat, 0.0) + pv
            lifetime += r.lifetime_present_value
            overlap += r.household_overlap_present_value
        return LCPResult(
            items=merged_items,
            category_present_value=category_pv,
            lifetime_present_value=lifetime,
            household_overlap_present_value=overlap,
        )

    growth_override = 0.0 if mode == "offset_zero" else None
    discount_rate = 0.0 if mode in ("nominal", "offset_zero") else float(inputs["discount_rate"])
    items = [_lcp_item(i, growth_override=growth_override) for i in inputs["items"]]
    return project_lcp(items, discount_rate, valuation_year)


def _lcp_summary(r: LCPResult) -> dict:
    return {
        "lifetime_present_value": round(r.lifetime_present_value, 2),
        "household_overlap_present_value": round(
            r.household_overlap_present_value, 2
        ),
        "lifetime_excluding_overlap": round(r.lifetime_excluding_overlap(), 2),
        "items": len(r.items),
    }


# --- loss of household services --------------------------------------------

def lhhs_result(inputs: dict) -> LHHSResult:
    stages = [
        HouseholdStage(
            start_year=int(s["start_year"]),
            end_year=int(s["end_year"]),
            weekly_hours=float(s["weekly_hours"]),
            hourly_value=float(s["hourly_value"]),
            loss_percent=float(s["loss_percent"]),
        )
        for s in inputs["stages"]
    ]
    growth = float(inputs["growth_rate"])
    discount = float(inputs["discount_rate"])
    mode = _mode(inputs)
    if mode == "nominal":
        discount = 0.0
    elif mode == "offset_zero":
        growth = 0.0
        discount = 0.0
    elif mode == "offset_match":
        discount = growth

    return project_lhhs(
        stages,
        base_year=int(inputs["base_year"]),
        valuation_year=int(inputs["valuation_year"]),
        growth_rate=growth,
        discount_rate=discount,
        area_wage_factor=float(inputs.get("area_wage_factor", 1.0)),
        self_consumption=float(inputs.get("self_consumption", 0.0)),
    )


def _lhhs_summary(r: LHHSResult) -> dict:
    return {
        "total_present_value": round(r.total_present_value, 2),
        "past_present_value": round(r.past_present_value, 2),
        "future_present_value": round(r.future_present_value, 2),
        "years": len(r.rows),
    }


# --- dispatch ---------------------------------------------------------------

_RESULT = {"earnings": earnings_result, "lcp": lcp_result, "lhhs": lhhs_result}
_SUMMARY = {"earnings": _earnings_summary, "lcp": _lcp_summary, "lhhs": _lhhs_summary}


def compute(module: str, inputs: dict):
    """Return the engine result object for ``module`` from ``inputs``."""
    if module not in _RESULT:
        raise ValueError(f"unknown module: {module}")
    return _RESULT[module](inputs)


def summarize(module: str, result) -> dict:
    """Return a small JSON-friendly summary of a result for listings/MCP."""
    return _SUMMARY[module](result)
