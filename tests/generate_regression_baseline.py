"""Generate (freeze) the calculation-regression baseline.

Run this ONLY to (re)create ``regression_baseline.json`` from the current,
verified engine. Every value it writes becomes the locked expectation that
``test_regression_snapshot.py`` defends against. Regenerate it only when a
calculation change is intended and justified against the source documents -- a
diff of this file is then the exact, reviewable record of which numbers moved.

    python tests/generate_regression_baseline.py

Not collected by pytest (no ``test_`` prefix).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from the repo root; make the engine/app importable.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from app.compute import compute  # noqa: E402
from regression_scenarios import SCENARIOS  # noqa: E402
from regression_serialize import result_to_dict  # noqa: E402

BASELINE_PATH = REPO_ROOT / "tests" / "regression_baseline.json"


def build() -> dict:
    data: dict[str, dict] = {}
    for sc in SCENARIOS:
        result = compute(sc.module, sc.inputs)
        data[sc.id] = {"module": sc.module, "result": result_to_dict(sc.module, result)}
    return data


def main() -> None:
    data = build()
    BASELINE_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    n_rows = sum(
        len(v["result"].get("rows", v["result"].get("items", [])))
        for v in data.values()
    )
    print(f"wrote {len(data)} scenarios ({n_rows} rows/items) to {BASELINE_PATH}")


if __name__ == "__main__":
    main()
