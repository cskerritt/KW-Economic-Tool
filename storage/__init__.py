"""Case persistence using the Python standard library (sqlite3).

Kept dependency-free and importable without the web layer so it can be tested
in isolation. Stores the canonical input dict for each saved case (as JSON) plus
a small summary for listings. Results are recomputed from the stored inputs on
load, so a case reproduces exactly from its inputs.
"""

from storage.db import connect, init_db
from storage.cases import CaseStore, SavedCase

__all__ = ["connect", "init_db", "CaseStore", "SavedCase"]
