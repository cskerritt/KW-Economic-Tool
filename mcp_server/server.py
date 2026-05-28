"""MCP server with one tool per damages module.

Each tool takes the canonical input dict (DECIMAL rates) and returns the engine
summary plus the year-by-year (or per-item) rows, so Claude Code can drive a
full calculation and reuse the exact logic the web app uses.
"""

from __future__ import annotations

from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from app.compute import compute, summarize

mcp = FastMCP("forensic-calc")


def _rows(result) -> list[dict]:
    rows = getattr(result, "rows", None)
    if rows is not None:
        return [asdict(r) for r in rows]
    items = getattr(result, "items", None)
    if items is not None:
        return [asdict(i) for i in items]
    return []


@mcp.tool()
def compute_earnings(inputs: dict) -> dict:
    """Economic loss via the Tinari algebraic method.

    inputs keys (decimal rates): case_type ('WD'|'PI'), base_earnings, base_year,
    start_year, end_year, valuation_year, growth_past, growth_future,
    growth_switch_year, discount_rate, worklife, unemployment, tax, fringe,
    pc_initial, pc_later, pc_switch_year, partial_years (dict of year->portion).
    """
    result = compute("earnings", inputs)
    return {"summary": summarize("earnings", result), "rows": _rows(result)}


@mcp.tool()
def compute_lcp(inputs: dict) -> dict:
    """Life care plan cost projection (DED Medical Care Cost Index).

    inputs keys: discount_rate (decimal), valuation_year, items (list of cost
    item dicts: name, category, cost_per_unit, start_year, end_year, growth_rate,
    base_year, units_per_year, replacement_years, overlaps_household, source).
    """
    result = compute("lcp", inputs)
    return {
        "summary": summarize("lcp", result),
        "category_present_value": result.category_present_value,
        "rows": _rows(result),
    }


@mcp.tool()
def compute_lhhs(inputs: dict) -> dict:
    """Loss of household services (DED replacement-cost six-step).

    inputs keys: base_year, valuation_year, growth_rate (decimal), discount_rate
    (decimal), area_wage_factor, self_consumption, stages (list of stage dicts:
    start_year, end_year, weekly_hours, hourly_value, loss_percent).
    """
    result = compute("lhhs", inputs)
    return {"summary": summarize("lhhs", result), "rows": _rows(result)}


@mcp.tool()
def lookup_area_wage_factor(area: str) -> dict:
    """DVD Table 414 national-to-area wage factor (decimal) for a state or metro."""
    from datasets import area_wage_factor
    return {"area": area, "factor": area_wage_factor(area)}


@mcp.tool()
def lookup_household_production(table_num: int) -> dict:
    """DVD household-production weekly hours, dollar value of a day, hourly value,
    and annual value for a demographic table number (1-385)."""
    from datasets import household_production
    return household_production(table_num)


@mcp.tool()
def lookup_life_expectancy(area: str, sex: str = "total", at: str = "birth") -> dict:
    """NVSR 2022 life expectancy (years). at = 'birth' or '65'."""
    from datasets import life_expectancy
    return {"area": area, "sex": sex, "at": at,
            "life_expectancy": life_expectancy(area, sex, at)}


@mcp.tool()
def lookup_worklife(sex: str, initial_state: str, education: str, age: int) -> dict:
    """SCK worklife expectancy row plus the worklife-to-separation ratio."""
    from datasets import worklife_expectancy, worklife_ratio
    return {"row": worklife_expectancy(sex, initial_state, education, age),
            "worklife_ratio": worklife_ratio(sex, initial_state, education, age)}


@mcp.tool()
def lookup_fringe_rate(ownership: str = "private", basis: str = "wages") -> dict:
    """ECEC fringe-benefit loading rate (decimal)."""
    from datasets import fringe_rate
    return {"ownership": ownership, "basis": basis,
            "fringe_rate": fringe_rate(ownership, basis)}


@mcp.tool()
def lookup_long_term_assumptions() -> dict:
    """SPF 10-year median forecasts (percent): CPI, PCE, real GDP, bond rate, etc."""
    from datasets import long_term
    return long_term()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
