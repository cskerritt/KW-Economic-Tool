"""Tests for the shared rate primitives."""

import math

from engine.common import grow, grow_series, present_value, discount_factor


def test_grow_zero_periods_is_identity():
    assert grow(100.0, 0.05, 0) == 100.0


def test_grow_compounds():
    assert math.isclose(grow(100.0, 0.05, 2), 110.25)


def test_grow_series_changing_rate():
    # 100 grown 3.1% then 3.8%
    out = grow_series(100.0, [0.031, 0.038])
    assert math.isclose(out[0], 103.1)
    assert math.isclose(out[1], 103.1 * 1.038)


def test_discount_factor_past_is_one():
    assert discount_factor(0.0325, 0) == 1.0
    assert discount_factor(0.0325, -3) == 1.0


def test_present_value_future():
    assert math.isclose(present_value(1032.5, 0.0325, 1), 1000.0)


def test_present_value_past_not_discounted():
    assert present_value(5000.0, 0.05, 0) == 5000.0
