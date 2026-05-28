"""Shared calculation primitives used by every damages module."""

from engine.common.rates import (
    grow,
    grow_series,
    present_value,
    discount_factor,
)

__all__ = ["grow", "grow_series", "present_value", "discount_factor"]
