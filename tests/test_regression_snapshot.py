"""Calculation-regression snapshot: no number may move silently.

For every scenario in the matrix, recompute through the real shared compute path
and deep-compare the full result (totals AND every year/item row) against the
frozen ``regression_baseline.json``. Any drift -- a changed total, a shifted
year value, a different AIF -- fails the test, naming the exact field.

The baseline is generated from the verified engine by
``generate_regression_baseline.py``. If a calculation change is intentional,
regenerate it; the JSON diff is then the reviewable record of what moved. The
source-document accuracy anchors (Tinari $858,384.39, etc.) are represented in
the matrix AND independently asserted in the per-module unit tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.compute import compute
from regression_scenarios import SCENARIOS
from regression_serialize import result_to_dict

# Tight tolerance: pure deterministic arithmetic should reproduce exactly; this
# only absorbs sub-cent floating-point noise, far below any real dollar change.
ABS_TOL = 1e-6
REL_TOL = 1e-9

BASELINE = json.loads(
    (Path(__file__).parent / "regression_baseline.json").read_text()
)


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= max(ABS_TOL, REL_TOL * max(abs(a), abs(b)))


def _diff(path: str, got, exp, out: list[str]) -> None:
    """Recursively compare nested dict/list structures, recording any mismatch."""
    if isinstance(exp, dict):
        assert isinstance(got, dict), f"{path}: expected object, got {type(got)}"
        assert set(got) == set(exp), (
            f"{path}: keys differ: +{set(got) - set(exp)} -{set(exp) - set(got)}"
        )
        for k in exp:
            _diff(f"{path}.{k}", got[k], exp[k], out)
    elif isinstance(exp, list):
        assert isinstance(got, list), f"{path}: expected list, got {type(got)}"
        assert len(got) == len(exp), f"{path}: length {len(got)} != {len(exp)}"
        for i, (g, e) in enumerate(zip(got, exp)):
            _diff(f"{path}[{i}]", g, e, out)
    elif isinstance(exp, bool):
        if got != exp:
            out.append(f"{path}: {got!r} != {exp!r}")
    elif isinstance(exp, (int, float)):
        if not _close(float(got), float(exp)):
            out.append(f"{path}: {got!r} != {exp!r}")
    else:
        if got != exp:
            out.append(f"{path}: {got!r} != {exp!r}")


def test_every_scenario_has_a_baseline():
    """Guard: a new scenario without a frozen baseline must not pass silently."""
    missing = [sc.id for sc in SCENARIOS if sc.id not in BASELINE]
    assert not missing, (
        f"no baseline for {missing}; run tests/generate_regression_baseline.py"
    )
    extra = [k for k in BASELINE if k not in {sc.id for sc in SCENARIOS}]
    assert not extra, f"baseline has stale scenarios {extra}; regenerate"


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.id)
def test_calculation_matches_baseline(scenario):
    expected = BASELINE[scenario.id]
    assert expected["module"] == scenario.module
    got = result_to_dict(scenario.module, compute(scenario.module, scenario.inputs))
    diffs: list[str] = []
    _diff(scenario.id, got, expected["result"], diffs)
    assert not diffs, "calculation regression:\n" + "\n".join(diffs)
