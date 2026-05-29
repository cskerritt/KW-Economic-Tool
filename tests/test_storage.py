"""Persistence tests.

The core suite runs against an in-memory SQLite database. An optional roundtrip
exercises the Postgres backend too; it is skipped unless ``TEST_DATABASE_URL``
points at a throwaway Postgres database (a dedicated var, never DATABASE_URL, so
the test can never touch a production database).
"""

import os

import pytest

from storage import connect, init_db, CaseStore


def _store() -> CaseStore:
    conn = connect(":memory:")
    init_db(conn)
    return CaseStore(conn)


def test_save_and_get_roundtrip():
    store = _store()
    inputs = {"base_earnings": 93628.0, "partial_years": {"2009": 0.33}}
    summary = {"total_present_value": 858384.39}
    case_id = store.save("earnings", "Exposito", inputs, summary)
    loaded = store.get(case_id)
    assert loaded is not None
    assert loaded.module == "earnings"
    assert loaded.title == "Exposito"
    assert loaded.inputs == inputs
    assert loaded.summary["total_present_value"] == 858384.39


def test_list_filters_by_module():
    store = _store()
    store.save("earnings", "A", {}, {})
    store.save("lcp", "B", {}, {})
    store.save("earnings", "C", {}, {})
    assert {c.title for c in store.list("earnings")} == {"A", "C"}
    assert len(store.list()) == 3


def test_update_changes_fields():
    store = _store()
    cid = store.save("lhhs", "Draft", {"x": 1}, {"t": 1})
    store.update(cid, title="Final", inputs={"x": 2}, summary={"t": 2})
    loaded = store.get(cid)
    assert loaded.title == "Final"
    assert loaded.inputs == {"x": 2}
    assert loaded.summary == {"t": 2}


def test_delete_removes_case():
    store = _store()
    cid = store.save("lcp", "Temp", {}, {})
    store.delete(cid)
    assert store.get(cid) is None


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="set TEST_DATABASE_URL to a throwaway Postgres db to run",
)
def test_postgres_roundtrip():
    """Same save/get/list/delete contract against a real Postgres backend."""
    conn = connect(os.environ["TEST_DATABASE_URL"])
    try:
        init_db(conn)
        store = CaseStore(conn)
        inputs = {"base_earnings": 93628.0, "partial_years": {"2009": 0.33}}
        summary = {"total_present_value": 858384.39}
        cid = store.save("earnings", "PG roundtrip", inputs, summary)
        loaded = store.get(cid)
        assert loaded is not None
        assert loaded.inputs == inputs
        assert loaded.summary["total_present_value"] == 858384.39
        assert any(c.id == cid for c in store.list("earnings"))
        store.update(cid, title="PG final", inputs={"x": 2}, summary={"t": 2})
        assert store.get(cid).title == "PG final"
        store.delete(cid)
        assert store.get(cid) is None
    finally:
        conn.close()
