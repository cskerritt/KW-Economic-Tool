"""Project life-care-plan item costs to present value.

Each item is stated in today's dollars by the life care planner (per DED §903
cost-chart guidance: resource, purpose, provider, start/stop, unit cost, source,
and replacement cycle). The economist grows each occurrence to its year using
the item's category-specific growth rate (see ``growth.py``), then discounts to
present value, and sums per category and a lifetime total.

Two cost patterns are supported:

* Recurring annual cost: ``cost_per_unit * units_per_year`` every year from
  ``start_year`` to ``end_year`` (e.g. 4 physician visits a year).
* Periodic replacement: ``cost_per_unit`` occurs every ``replacement_years``
  starting at ``start_year`` (e.g. a wheelchair replaced every 5 years).

Set ``overlaps_household=True`` for attendant/home-care items that also appear
in the household-services analysis, so they can be netted out (avoid double
counting, per DED Chapter 6 / Ireland).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.common import grow, present_value


@dataclass(frozen=True)
class LCPItem:
    name: str
    category: str
    cost_per_unit: float          # today's dollars (in base_year)
    start_year: int
    end_year: int
    growth_rate: float            # category-specific, from medical_growth_rate
    base_year: int                # year cost_per_unit applies to
    units_per_year: float = 1.0   # used when replacement_years is None
    replacement_years: int | None = None  # if set, periodic replacement
    overlaps_household: bool = False
    source: str = ""

    def occurrence_years(self) -> list[int]:
        """Years in which a cost is incurred."""
        if self.start_year > self.end_year:
            return []
        if self.replacement_years:
            return list(
                range(self.start_year, self.end_year + 1, self.replacement_years)
            )
        return list(range(self.start_year, self.end_year + 1))

    def nominal_amount(self, year: int) -> float:
        """Grown (future-dollar) cost incurred in ``year``."""
        periods = year - self.base_year
        if periods < 0:
            raise ValueError("year precedes base_year")
        if self.replacement_years:
            base = self.cost_per_unit
        else:
            base = self.cost_per_unit * self.units_per_year
        return grow(base, self.growth_rate, periods)


@dataclass(frozen=True)
class LCPItemResult:
    name: str
    category: str
    overlaps_household: bool
    nominal_total: float          # sum of grown costs, undiscounted
    present_value: float
    occurrences: int


@dataclass
class LCPResult:
    items: list[LCPItemResult]
    category_present_value: dict[str, float]
    lifetime_present_value: float
    household_overlap_present_value: float  # net these out of LHHS if needed

    def lifetime_excluding_overlap(self) -> float:
        return self.lifetime_present_value - self.household_overlap_present_value


def project_lcp(
    items: list[LCPItem],
    discount_rate: float,
    valuation_year: int,
) -> LCPResult:
    """Project all items to present value with per-category and lifetime totals."""
    item_results: list[LCPItemResult] = []
    category_pv: dict[str, float] = {}
    lifetime_pv = 0.0
    overlap_pv = 0.0

    for item in items:
        nominal_total = 0.0
        item_pv = 0.0
        years = item.occurrence_years()
        for year in years:
            amount = item.nominal_amount(year)
            nominal_total += amount
            item_pv += present_value(amount, discount_rate, year - valuation_year)

        item_results.append(
            LCPItemResult(
                name=item.name,
                category=item.category,
                overlaps_household=item.overlaps_household,
                nominal_total=nominal_total,
                present_value=item_pv,
                occurrences=len(years),
            )
        )
        category_pv[item.category] = category_pv.get(item.category, 0.0) + item_pv
        lifetime_pv += item_pv
        if item.overlaps_household:
            overlap_pv += item_pv

    return LCPResult(
        items=item_results,
        category_present_value=category_pv,
        lifetime_present_value=lifetime_pv,
        household_overlap_present_value=overlap_pv,
    )
