"""NVSR 2022 state life-expectancy lookups."""

from __future__ import annotations

from datasets.paths import read_csv

_SEX_COL = {"total": "total", "male": "male", "female": "female"}


def life_expectancy(area: str, sex: str = "total", at: str = "birth") -> float | None:
    """Life expectancy in years for a state/area and sex.

    Args:
        area: state name, "District of Columbia", or "United States".
        sex: "total", "male", or "female".
        at: "birth" or "65".
    """
    sex_key = _SEX_COL.get(sex.lower())
    if sex_key is None:
        raise ValueError("sex must be total, male, or female")
    fname = ("nvsr_life_expectancy/nvsr_tableA_life_expectancy_at_birth.csv"
             if str(at) == "birth"
             else "nvsr_life_expectancy/nvsr_tableB_life_expectancy_at_age_65.csv")
    col = f"{sex_key}_le_at_birth" if str(at) == "birth" else f"{sex_key}_le_at_65"
    q = area.strip().lower()
    for r in read_csv(fname):
        if r["area"].lower() == q:
            return float(r[col]) if r[col] else None
    return None
