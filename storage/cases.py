"""Case repository: save, list, get, delete saved calculations.

Backend-agnostic: works against either a stdlib ``sqlite3`` connection or a
psycopg (Postgres) connection. The only dialect differences are the parameter
placeholder (``?`` vs ``%s``) and that we always read the new row id back with
``RETURNING id`` (supported by SQLite >= 3.35 and Postgres) instead of relying on
``cursor.lastrowid``. Rows are name-addressable on both backends, so
``SavedCase.from_row`` is unchanged.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class SavedCase:
    id: int
    module: str
    title: str
    created_at: str
    updated_at: str
    inputs: dict
    summary: dict

    @classmethod
    def from_row(cls, row: Any) -> "SavedCase":
        return cls(
            id=row["id"],
            module=row["module"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            inputs=json.loads(row["inputs_json"]),
            summary=json.loads(row["summary_json"]),
        )


class CaseStore:
    """Thin repository over the ``cases`` table (SQLite or Postgres)."""

    def __init__(self, conn: Any):
        self.conn = conn
        # SQLite uses ? placeholders; psycopg (Postgres) uses %s.
        self.ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"

    def _q(self, sql: str) -> str:
        """Render placeholders for the active backend."""
        return sql.replace("?", self.ph)

    def save(self, module: str, title: str, inputs: dict, summary: dict) -> int:
        now = _now()
        cur = self.conn.cursor()
        try:
            cur.execute(
                self._q(
                    "INSERT INTO cases "
                    "(module, title, created_at, updated_at, inputs_json, summary_json) "
                    "VALUES (?, ?, ?, ?, ?, ?) RETURNING id"
                ),
                (module, title, now, now, json.dumps(inputs), json.dumps(summary)),
            )
            new_id = int(cur.fetchone()["id"])
        finally:
            cur.close()
        self.conn.commit()
        return new_id

    def update(self, case_id: int, *, title: str, inputs: dict, summary: dict) -> None:
        cur = self.conn.cursor()
        try:
            cur.execute(
                self._q(
                    "UPDATE cases SET title = ?, inputs_json = ?, summary_json = ?, "
                    "updated_at = ? WHERE id = ?"
                ),
                (title, json.dumps(inputs), json.dumps(summary), _now(), case_id),
            )
        finally:
            cur.close()
        self.conn.commit()

    def list(self, module: str | None = None) -> list[SavedCase]:
        cur = self.conn.cursor()
        try:
            if module:
                cur.execute(
                    self._q(
                        "SELECT * FROM cases WHERE module = ? ORDER BY updated_at DESC"
                    ),
                    (module,),
                )
            else:
                cur.execute("SELECT * FROM cases ORDER BY updated_at DESC")
            rows = cur.fetchall()
        finally:
            cur.close()
        return [SavedCase.from_row(r) for r in rows]

    def get(self, case_id: int) -> SavedCase | None:
        cur = self.conn.cursor()
        try:
            cur.execute(self._q("SELECT * FROM cases WHERE id = ?"), (case_id,))
            row = cur.fetchone()
        finally:
            cur.close()
        return SavedCase.from_row(row) if row else None

    def delete(self, case_id: int) -> None:
        cur = self.conn.cursor()
        try:
            cur.execute(self._q("DELETE FROM cases WHERE id = ?"), (case_id,))
        finally:
            cur.close()
        self.conn.commit()
