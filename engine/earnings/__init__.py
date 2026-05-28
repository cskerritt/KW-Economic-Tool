"""Economic loss (lost earnings) via the Tinari algebraic method."""

from engine.earnings.aif import adjusted_income_factor
from engine.earnings.personal_injury import (
    PersonalInjuryResult,
    project_personal_injury,
)
from engine.earnings.projection import (
    YearInput,
    YearResult,
    EarningsResult,
    EarningsAssumptions,
    build_earnings_inputs,
    project_earnings,
)

__all__ = [
    "adjusted_income_factor",
    "YearInput",
    "YearResult",
    "EarningsResult",
    "EarningsAssumptions",
    "build_earnings_inputs",
    "project_earnings",
    "PersonalInjuryResult",
    "project_personal_injury",
]
