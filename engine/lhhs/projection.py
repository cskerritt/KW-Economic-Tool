"""Loss of household services projection (replacement-cost / six-step method).

Source: Determining Economic Damages (Prakash-Canjels), Chapter 6.

Step 1 method: replacement cost. Step 2-3 valuation: weekly hours from the
Expectancy Data Dollar Value of a Day (DVD) table for the matched demographic,
valued at the embedded OES hourly wage. DVD defines:

    dollar value of a day = weekly_hours * hourly_value / 7
    annual value          = dollar value of a day * 365.25

Step 4 update: demographic life-cycle stages (each a span of years with its own
weekly hours, hourly value, and loss percent) plus wage growth. Step 5: loss
period and declining health (expressed via per-stage loss percent and stage end
years). Step 6: self-consumption adjustment. The optional national-to-area wage
factor is DVD Table 414.

The annual loss in a year is:

    grown_annual_value * area_wage_factor * loss_percent * (1 - self_consumption)

discounted to the valuation year.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.common import grow, present_value


def dollar_value_of_a_day(weekly_hours: float, hourly_value: float) -> float:
    """DVD dollar value of a day = weekly hours * hourly value / 7."""
    return weekly_hours * hourly_value / 7.0


def annual_value_from_hours(weekly_hours: float, hourly_value: float) -> float:
    """Annual household-production value = dollar value of a day * 365.25."""
    return dollar_value_of_a_day(weekly_hours, hourly_value) * 365.25


@dataclass(frozen=True)
class HouseholdStage:
    """One demographic life-cycle stage of the loss.

    A stage covers ``start_year`` through ``end_year`` inclusive and carries the
    DVD weekly hours and hourly value for the matched demographic during that
    span, plus the loss percent (the share of services lost, reflecting
    functional limitations and, in step 5, declining health).
    """

    start_year: int
    end_year: int
    weekly_hours: float
    hourly_value: float
    loss_percent: float          # 0..1, share of services lost in this stage

    def base_annual_value(self) -> float:
        return annual_value_from_hours(self.weekly_hours, self.hourly_value)


@dataclass(frozen=True)
class LHHSYearResult:
    year: int
    base_annual_value: float     # grown, pre loss-percent
    loss_percent: float
    annual_loss: float           # after area, loss percent, self-consumption
    present_value: float
    is_future: bool


@dataclass
class LHHSResult:
    rows: list[LHHSYearResult]
    total_present_value: float
    past_present_value: float
    future_present_value: float


def project_lhhs(
    stages: list[HouseholdStage],
    *,
    base_year: int,
    valuation_year: int,
    growth_rate: float,
    discount_rate: float,
    area_wage_factor: float = 1.0,
    self_consumption: float = 0.0,
) -> LHHSResult:
    """Project household-services loss to present value across all stages.

    Args:
        stages: life-cycle stages, expected to be non-overlapping and ordered.
        base_year: year the DVD hourly values apply to (growth starts here).
        valuation_year: present reference; years after it are discounted.
        growth_rate: wage growth for household-production values (e.g. ECI).
        discount_rate: net discount rate.
        area_wage_factor: DVD Table 414 national-to-area factor (default 1.0).
        self_consumption: share consumed by the injured/decedent (default 0.0).
    """
    rows: list[LHHSYearResult] = []
    past_pv = 0.0
    future_pv = 0.0

    for stage in stages:
        for year in range(stage.start_year, stage.end_year + 1):
            grown = grow(stage.base_annual_value(), growth_rate, year - base_year)
            annual_loss = (
                grown
                * area_wage_factor
                * stage.loss_percent
                * (1.0 - self_consumption)
            )
            periods = year - valuation_year
            pv = present_value(annual_loss, discount_rate, periods)
            is_future = periods > 0
            if is_future:
                future_pv += pv
            else:
                past_pv += pv
            rows.append(
                LHHSYearResult(
                    year=year,
                    base_annual_value=grown,
                    loss_percent=stage.loss_percent,
                    annual_loss=annual_loss,
                    present_value=pv,
                    is_future=is_future,
                )
            )

    rows.sort(key=lambda r: r.year)
    return LHHSResult(
        rows=rows,
        total_present_value=past_pv + future_pv,
        past_present_value=past_pv,
        future_present_value=future_pv,
    )
