"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator

from storage import CaseStore, connect

from app.config import settings


def get_store() -> Iterator[CaseStore]:
    """Yield a CaseStore backed by a fresh connection per request (Postgres if
    DATABASE_URL is set, else SQLite)."""
    conn = connect(settings.db_target)
    try:
        yield CaseStore(conn)
    finally:
        conn.close()
