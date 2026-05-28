"""SQLite connection and schema (stdlib sqlite3)."""

from __future__ import annotations

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    module      TEXT    NOT NULL,         -- 'earnings' | 'lcp' | 'lhhs'
    title       TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,         -- ISO-8601 UTC
    updated_at  TEXT    NOT NULL,
    inputs_json TEXT    NOT NULL,         -- canonical input dict (decimals)
    summary_json TEXT   NOT NULL          -- totals for listings
);
CREATE INDEX IF NOT EXISTS idx_cases_module ON cases(module);
"""


def connect(db_path: str) -> sqlite3.Connection:
    """Open a connection with row access by name and foreign keys on."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
