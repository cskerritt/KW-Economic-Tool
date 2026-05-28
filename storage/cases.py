"""Case repository: save, list, get, delete saved calculations."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


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
    def from_row(cls, row: sqlite3.Row) -> "SavedCase":
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
    """Thin repository over the ``cases`` table."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def save(self, module: str, title: str, inputs: dict, summary: dict) -> int:
        now = _now()
        cur = self.conn.execute(
            "INSERT INTO cases "
            "(module, title, created_at, updated_at, inputs_json, summary_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (module, title, now, now, json.dumps(inputs), json.dumps(summary)),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update(self, case_id: int, *, title: str, inputs: dict, summary: dict) -> None:
        self.conn.execute(
            "UPDATE cases SET title = ?, inputs_json = ?, summary_json = ?, "
            "updated_at = ? WHERE id = ?",
            (title, json.dumps(inputs), json.dumps(summary), _now(), case_id),
        )
        self.conn.commit()

    def list(self, module: str | None = None) -> list[SavedCase]:
        if module:
            rows = self.conn.execute(
                "SELECT * FROM cases WHERE module = ? ORDER BY updated_at DESC",
                (module,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM cases ORDER BY updated_at DESC"
            ).fetchall()
        return [SavedCase.from_row(r) for r in rows]

    def get(self, case_id: int) -> SavedCase | None:
        row = self.conn.execute(
            "SELECT * FROM cases WHERE id = ?", (case_id,)
        ).fetchone()
        return SavedCase.from_row(row) if row else None

    def delete(self, case_id: int) -> None:
        self.conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))
        self.conn.commit()
