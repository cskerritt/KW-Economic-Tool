"""Project lost earnings year by year and reduce to present value.

The projection applies the Tinari Adjusted Income Factor (see ``aif.py``) to
grown gross earnings each year, then discounts future years to the valuation
date. Past years (at or before the valuation year) are not discounted.

The design separates two concerns:

* ``build_earnings_inputs`` expands high-level ``EarningsAssumptions`` into one
  fully-specified ``YearInput`` per year. This is where growth, the personal
  consumption step-down, and partial years are resolved.
* ``project_earnings`` consumes ``YearInput`` rows and produces results. It only
  applies the AIF and discounting, so it is trivial to test and to feed with
  hand-built rows (for example a year-by-year worklife probability spreadsheet).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.common import present_value
from engine.earnings.aif import adjusted_income_factor


@dataclass(frozen=True)
class YearInput:
    """One fully-resolved year of the projection."""

    year: int
    portion: float          # portion of the year in the loss period (0..1)
    gross_earnings: float    # grown gross earnings for the year
    worklife: float
    unemployment: float
    tax: float
    personal_consumption: float
    fringe: float = 0.0


@dataclass(frozen=True)
class YearResult:
    year: int
    portion: float
    gross_earnings: float
    aif: float
    adjusted_income: float
    present_value: float
    is_future: bool


@dataclass
class EarningsResult:
    rows: list[YearResult]
    total_present_value: float
    past_present_value: float
    future_present_value: float

    def aif_values(self) -> list[float]:
        """Distinct AIF values used, in order of first appearance."""
        seen: list[float] = []
        for r in self.rows:
            if r.aif not in seen:
                seen.append(r.aif)
        return seen


@dataclass
class EarningsAssumptions:
    """High-level inputs for a single earnings stream.

    For wrongful death set ``personal_consumption_*``. For personal injury set
    them to 0.0 and compute the loss as pre-injury minus residual capacity by
    running this twice and subtracting the results.
    """

    base_earnings: float
    base_year: int          # year the base earnings figure applies to
    start_year: int          # first year of the loss period
    end_year: int            # last year of the loss period
    valuation_year: int      # present reference; years after this are discounted

    growth_past: float
    growth_future: float
    growth_switch_year: int  # first year that uses growth_future

    discount_rate: float

    worklife: float
    unemployment: float
    tax: float
    fringe: float = 0.0

    personal_consumption_initial: float = 0.0
    personal_consumption_later: float | None = None
    pc_switch_year: int | None = None

    # portion of year for partial years, e.g. {2009: 0.33, 2022: 0.26}
    partial_years: dict[int, float] = field(default_factory=dict)

    def personal_consumption_for(self, year: int) -> float:
        if (
            self.pc_switch_year is not None
            and self.personal_consumption_later is not None
            and year >= self.pc_switch_year
        ):
            return self.personal_consumption_later
        return self.personal_consumption_initial


def grown_gross(
    base_earnings: float,
    base_year: int,
    year: int,
    growth_past: float,
    growth_future: float,
    switch_year: int,
) -> float:
    """Gross earnings for ``year``, compounded from ``base_earnings``.

    Each step year uses ``growth_future`` if that step year is at or after
    ``switch_year``, otherwise ``growth_past``. When ``year == base_year`` the
    base earnings are already stated in that year's dollars, so they are returned
    unchanged (zero growth periods) -- this supports a loss period that begins in
    the base year (e.g. a current-year injury). Growing backward is undefined, so
    a year before the base year is still rejected.
    """
    if year < base_year:
        raise ValueError("year must be on or after base_year")
    value = base_earnings
    for step_year in range(base_year + 1, year + 1):
        rate = growth_future if step_year >= switch_year else growth_past
        value *= 1.0 + rate
    return value


def build_earnings_inputs(a: EarningsAssumptions) -> list[YearInput]:
    """Expand assumptions into one ``YearInput`` per year of the loss period."""
    rows: list[YearInput] = []
    for year in range(a.start_year, a.end_year + 1):
        gross = grown_gross(
            a.base_earnings,
            a.base_year,
            year,
            a.growth_past,
            a.growth_future,
            a.growth_switch_year,
        )
        rows.append(
            YearInput(
                year=year,
                portion=a.partial_years.get(year, 1.0),
                gross_earnings=gross,
                worklife=a.worklife,
                unemployment=a.unemployment,
                tax=a.tax,
                personal_consumption=a.personal_consumption_for(year),
                fringe=a.fringe,
            )
        )
    return rows


def project_earnings(
    year_inputs: list[YearInput],
    discount_rate: float,
    valuation_year: int,
) -> EarningsResult:
    """Apply the AIF and discounting to produce the earnings result."""
    rows: list[YearResult] = []
    past_pv = 0.0
    future_pv = 0.0
    for yi in year_inputs:
        aif = adjusted_income_factor(
            worklife=yi.worklife,
            unemployment=yi.unemployment,
            tax=yi.tax,
            personal_consumption=yi.personal_consumption,
            fringe=yi.fringe,
        )
        adjusted_income = yi.portion * yi.gross_earnings * aif
        periods = yi.year - valuation_year
        pv = present_value(adjusted_income, discount_rate, periods)
        is_future = periods > 0
        if is_future:
            future_pv += pv
        else:
            past_pv += pv
        rows.append(
            YearResult(
                year=yi.year,
                portion=yi.portion,
                gross_earnings=yi.gross_earnings,
                aif=aif,
                adjusted_income=adjusted_income,
                present_value=pv,
                is_future=is_future,
            )
        )
    return EarningsResult(
        rows=rows,
        total_present_value=past_pv + future_pv,
        past_present_value=past_pv,
        future_present_value=future_pv,
    )
