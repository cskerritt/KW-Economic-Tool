"""Medical Care Cost Index growth rates.

Source: Determining Economic Damages (Prakash-Canjels), Chapter 9 §920.

The future growth rate for a life-care-plan item is the past *real* inflation
rate for the matched category plus the expected future general inflation rate:

    item growth rate = real medical inflation (matched category)
                       + expected general inflation (CBO CPI projection)

    real medical inflation = (recent inflation for the matched CPI category)
                             - (overall CPI inflation, same period)

Because medical growth varies widely by category, each item carries its own
rate. Match the CPI item category as closely as possible to the expense.
"""

from __future__ import annotations


def real_medical_inflation(
    category_cpi_inflation: float,
    overall_cpi_inflation: float,
) -> float:
    """Real medical inflation for a category = category inflation - overall CPI.

    May be negative (some medical commodities fell over 2010-2020 per DED).
    """
    return category_cpi_inflation - overall_cpi_inflation


def medical_growth_rate(
    category_cpi_inflation: float,
    overall_cpi_inflation: float,
    expected_general_inflation: float,
) -> float:
    """Future growth rate for an LCP item, per DED §920."""
    return (
        real_medical_inflation(category_cpi_inflation, overall_cpi_inflation)
        + expected_general_inflation
    )
