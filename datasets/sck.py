"""Skoog-Ciecka-Krueger worklife (WLE) and years-to-final-separation (YFS)."""

from __future__ import annotations

from datasets.paths import read_csv


def _norm(s: str) -> str:
    return "".join(c for c in s.lower() if c.isalnum())


def _find_file(index_csv: str, sex: str, initial_state: str, education: str) -> str:
    rows = read_csv(index_csv)
    sx, st, ed = _norm(sex), _norm(initial_state), _norm(education)
    for r in rows:
        if (_norm(r["sex"]) == sx
                and st in _norm(r["initial_state"])
                and (_norm(r["education"]) == ed or ed in _norm(r["education"]))):
            return r["file"]
    raise KeyError(f"No SCK table for {sex} / {initial_state} / {education}")


def _row_for_age(folder: str, fname: str, age: int) -> dict:
    rows = read_csv(f"{folder}/{fname}")
    for r in rows:
        if int(r["age"]) == int(age):
            return r
    raise KeyError(f"Age {age} not in {fname}")


def worklife_expectancy(sex: str, initial_state: str, education: str, age: int) -> dict:
    """WLE statistics row for the cohort and age (means, percentiles, SE)."""
    f = _find_file("sck_wle/_index.csv", sex, initial_state, education)
    return _row_for_age("sck_wle", f, age)


def years_to_final_separation(sex: str, initial_state: str, education: str, age: int) -> dict:
    """YFS statistics row for the cohort and age."""
    f = _find_file("sck_yfs/_index.csv", sex, initial_state, education)
    return _row_for_age("sck_yfs", f, age)


def worklife_ratio(sex: str, initial_state: str, education: str, age: int) -> float:
    """Worklife-to-separation ratio (WLE mean / YFS mean) for the Tinari WLE factor.

    This is the share of remaining years to final labor-force separation that
    are expected to be active (the Tinari ``WLE`` adjustment).
    """
    row = years_to_final_separation(sex, initial_state, education, age)
    yfs = float(row["yfs_mean"])
    wle = float(row["wle_mean"])
    return wle / yfs if yfs else 0.0
