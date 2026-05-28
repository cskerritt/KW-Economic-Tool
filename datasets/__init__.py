"""Reference-data access layer.

Loads the extracted CSVs under ``data/`` and exposes typed lookups (area-wage
factors, DVD household-production hours/values, worklife expectancy, life
expectancy, fringe rates, long-term economic assumptions). Pure standard
library, no third-party dependencies.

The engine stays pure math; this package turns reference data into the inputs
the engine consumes. See ``datasets.builders`` for dataset-to-engine helpers.
"""

from datasets.dvd import (
    list_demographics,
    demographic_table,
    household_production,
    area_wage_factor,
)
from datasets.sck import worklife_expectancy, years_to_final_separation, worklife_ratio
from datasets.nvsr import life_expectancy
from datasets.ecec import fringe_rate
from datasets.spf import long_term
from datasets.fred import (
    cagr,
    category_growth,
    cpi_series,
    list_categories,
    series_cagr,
)

__all__ = [
    "list_demographics",
    "demographic_table",
    "household_production",
    "area_wage_factor",
    "worklife_expectancy",
    "years_to_final_separation",
    "worklife_ratio",
    "life_expectancy",
    "fringe_rate",
    "long_term",
    "cagr",
    "category_growth",
    "cpi_series",
    "list_categories",
    "series_cagr",
]
