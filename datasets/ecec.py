"""ECEC (Dec 2025) employer-cost / fringe-benefit lookups."""

from __future__ import annotations

from datasets.paths import read_csv

_OWN = {"civilian": "civilian", "private": "private", "stategov": "stategov",
        "state": "stategov", "government": "stategov"}


def _norm(s: str) -> str:
    return "".join(c for c in s.lower() if c.isalnum())


def _table1():
    return read_csv("ecec/ecec_table1_by_ownership.csv")


def _component_cost(component_norm: str, ownership_col: str) -> float | None:
    for r in _table1():
        if _norm(r["compensation_component"]).startswith(component_norm):
            v = r[f"{ownership_col}_cost"]
            return float(v) if v else None
    return None


def fringe_rate(ownership: str = "private", basis: str = "wages") -> float:
    """Fringe-benefit loading rate (decimal) for the Tinari FB factor.

    Args:
        ownership: "private" (default), "civilian", or "stategov".
        basis: "wages" -> total benefits / wages and salaries (default);
               "compensation" -> total benefits / total compensation.
    Returns:
        Total employer benefit cost expressed as a fraction of the chosen base.
    """
    col = _OWN.get(ownership.lower())
    if col is None:
        raise ValueError("ownership must be private, civilian, or stategov")
    benefits = _component_cost("totalbenefits", col)
    if basis == "wages":
        base = _component_cost("wagesandsalaries", col)
    else:
        base = _component_cost("totalcompensation", col)
    if not benefits or not base:
        raise KeyError("ECEC components not found")
    return benefits / base
