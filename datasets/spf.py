"""Survey of Professional Forecasters (Q1 2026) long-term assumptions.

Returns the median long-term (10-year, 2026-2035) forecasts useful as growth
and discount assumption anchors. Values are percents as published (2.10 = 2.10%);
divide by 100 for engine decimals.
"""

from __future__ import annotations

from datasets.paths import read_csv

_HORIZON = "2026-2035"


def _median(rows, key_field, key_value):
    for r in rows:
        if r[key_field] == key_value and r["statistic"] == "MEDIAN" and r["horizon"] == _HORIZON:
            return float(r["value"])
    return None


def long_term() -> dict:
    """10-year median forecasts: CPI, PCE, real GDP growth, productivity,
    stock returns, 10-year bond rate, 3-month bill returns (all in percent)."""
    t8 = read_csv("spf/spf_table8_longterm_inflation.csv")
    t9 = read_csv("spf/spf_table9_longterm_additional.csv")
    return {
        "cpi_inflation": _median(t8, "index", "cpi"),
        "pce_inflation": _median(t8, "index", "pce"),
        "real_gdp_growth": _median(t9, "series", "real_gdp_growth"),
        "productivity_growth": _median(t9, "series", "productivity_growth"),
        "stock_returns_sp500": _median(t9, "series", "stock_returns_sp500"),
        "bond_rate_10yr": _median(t9, "series", "bond_rate_10yr"),
        "bill_returns_3mo": _median(t9, "series", "bill_returns_3mo"),
    }
