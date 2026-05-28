"""Growth and present-value primitives.

All rates are decimals: 3.25% is passed as 0.0325. Money is kept as float
during calculation and rounded only for display.
"""

from __future__ import annotations


def grow(base: float, rate: float, periods: int) -> float:
    """Compound ``base`` at ``rate`` for ``periods`` whole periods.

    grow(100, 0.05, 0) == 100
    grow(100, 0.05, 1) == 105
    """
    if periods < 0:
        raise ValueError("periods must be >= 0")
    return base * ((1.0 + rate) ** periods)


def grow_series(base: float, rates_by_period: list[float]) -> list[float]:
    """Grow ``base`` forward one period at a time using a per-period rate.

    Returns one value per entry in ``rates_by_period``. This supports a growth
    rate that changes over time (for example one rate for past years and a
    different rate for future years), which the Tinari example requires.

    grow_series(100, [0.10, 0.10]) == [110.0, 121.0]
    """
    out: list[float] = []
    value = base
    for rate in rates_by_period:
        value = value * (1.0 + rate)
        out.append(value)
    return out


def discount_factor(rate: float, periods: int) -> float:
    """Factor that converts a future amount ``periods`` out into present value.

    For periods <= 0 the factor is 1.0 (amount is already at or before the
    valuation date and is not discounted).
    """
    if periods <= 0:
        return 1.0
    return 1.0 / ((1.0 + rate) ** periods)


def present_value(amount: float, rate: float, periods: int) -> float:
    """Present value of a single future ``amount``.

    Amounts at or before the valuation date (periods <= 0) are returned
    unchanged, matching the forensic convention that past losses are not
    discounted (prejudgment interest, where applicable, is handled separately).
    """
    return amount * discount_factor(rate, periods)
