"""Print the Tinari (2016) Exposito worked example schedule.

Run from the repo root:  python examples/exposito.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.earnings import (  # noqa: E402
    EarningsAssumptions,
    build_earnings_inputs,
    project_earnings,
)


def main() -> None:
    a = EarningsAssumptions(
        base_earnings=93628.0,
        base_year=2008,
        start_year=2009,
        end_year=2022,
        valuation_year=2015,
        growth_past=0.031,
        growth_future=0.038,
        growth_switch_year=2016,
        discount_rate=0.0325,
        worklife=0.919,
        unemployment=0.035,
        tax=0.12,
        personal_consumption_initial=0.25,
        personal_consumption_later=0.20,
        pc_switch_year=2016,
        partial_years={2009: 0.33, 2022: 0.26},
    )
    result = project_earnings(
        build_earnings_inputs(a), a.discount_rate, a.valuation_year
    )

    header = f"{'Year':>4} {'Part':>5} {'Gross':>12} {'AIF':>7} {'AdjInc':>12} {'PV':>12}"
    print(header)
    print("-" * len(header))
    for r in result.rows:
        print(
            f"{r.year:>4} {r.portion:>5.0%} {r.gross_earnings:>12,.0f} "
            f"{r.aif:>7.2%} {r.adjusted_income:>12,.0f} {r.present_value:>12,.0f}"
        )
    print("-" * len(header))
    print(f"Past PV:   {result.past_present_value:>12,.2f}")
    print(f"Future PV: {result.future_present_value:>12,.2f}")
    print(f"TOTAL PV:  {result.total_present_value:>12,.2f}")
    print("Tinari published total: 858,387")


if __name__ == "__main__":
    main()
