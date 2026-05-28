"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator

from storage import CaseStore, connect

from app.config import settings


def get_store() -> Iterator[CaseStore]:
    """Yield a CaseStore backed by a fresh SQLite connection per request."""
    conn = connect(settings.db_path)
    try:
        yield CaseStore(conn)
    finally:
        conn.close()
