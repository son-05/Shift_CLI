"""
autopilot/memory/store.py — Persistent command history
======================================================

Stored at: ~/.autopilot/history.db

Schema
------
  tasks           past automation tasks with summaries
  command_log     individual commands that were executed
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


def _autopilot_home() -> Path:
    home = Path.home() / ".autopilot"
    home.mkdir(parents=True, exist_ok=True)
    return home


def _default_db() -> Path:
    return _autopilot_home() / "history.db"


_DDL = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task        TEXT NOT NULL,
    summary     TEXT DEFAULT '',
    os_used     TEXT DEFAULT '',
    total_cmds  INTEGER DEFAULT 0,
    succeeded   INTEGER DEFAULT 0,
    failed      INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS command_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER REFERENCES tasks(id),
    step_number INTEGER DEFAULT 0,
    command     TEXT NOT NULL,
    explanation TEXT DEFAULT '',
    risk        TEXT DEFAULT 'safe',
    success     INTEGER DEFAULT 0,
    output      TEXT DEFAULT '',
    error       TEXT DEFAULT '',
    time_secs   REAL DEFAULT 0.0,
    created_at  TEXT NOT NULL
);
"""


class MemoryStore:
    """
    Persistent command history for AutoPilot.

    Usage
    -----
        mem = MemoryStore()
        mem.initialize()
        tid = mem.save_task("set up Python project", ...)
        mem.save_command(tid, 1, "mkdir my_project", ...)
        recent = mem.get_recent_tasks(5)
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else _default_db()
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def initialize(self) -> None:
        self._get_conn().executescript(_DDL)
        self._get_conn().commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def save_task(
        self,
        task: str,
        summary: str = "",
        os_used: str = "",
        total_cmds: int = 0,
        succeeded: int = 0,
        failed: int = 0,
    ) -> int:
        conn = self._get_conn()
        cur = conn.execute(
            "INSERT INTO tasks(task, summary, os_used, total_cmds, succeeded, failed, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (task, summary, os_used, total_cmds, succeeded, failed, _now()),
        )
        conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_recent_tasks(self, n: int = 5) -> list[dict[str, Any]]:
        rows = self._get_conn().execute(
            "SELECT id, task, summary, os_used, total_cmds, succeeded, failed, created_at "
            "FROM tasks ORDER BY id DESC LIMIT ?",
            (n,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "task": r["task"],
                "summary": r["summary"],
                "os_used": r["os_used"],
                "total_cmds": r["total_cmds"],
                "succeeded": r["succeeded"],
                "failed": r["failed"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def total_task_count(self) -> int:
        return self._get_conn().execute("SELECT COUNT(*) FROM tasks").fetchone()[0]

    def is_first_run(self) -> bool:
        return self.total_task_count() == 0

    def session_number(self) -> int:
        return self.total_task_count() + 1

    # ── Command Log ───────────────────────────────────────────────────────────

    def save_command(
        self,
        task_id: int,
        step_number: int,
        command: str,
        explanation: str = "",
        risk: str = "safe",
        success: bool = False,
        output: str = "",
        error: str = "",
        time_secs: float = 0.0,
    ) -> None:
        self._get_conn().execute(
            "INSERT INTO command_log(task_id, step_number, command, explanation, risk, "
            "success, output, error, time_secs, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (task_id, step_number, command, explanation, risk,
             1 if success else 0, output, error, time_secs, _now()),
        )
        self._get_conn().commit()

    def get_task_commands(self, task_id: int) -> list[dict[str, Any]]:
        rows = self._get_conn().execute(
            "SELECT step_number, command, explanation, risk, success, output, error, time_secs "
            "FROM command_log WHERE task_id = ? ORDER BY step_number",
            (task_id,),
        ).fetchall()
        return [
            {
                "step_number": r["step_number"],
                "command": r["command"],
                "explanation": r["explanation"],
                "risk": r["risk"],
                "success": bool(r["success"]),
                "output": r["output"],
                "error": r["error"],
                "time_secs": r["time_secs"],
            }
            for r in rows
        ]

    # ── Context for agent prompts ─────────────────────────────────────────────

    def build_context_string(self) -> str:
        recent = self.get_recent_tasks(3)
        if not recent:
            return ""
        lines = ["=== RECENT TASK HISTORY ==="]
        for t in recent:
            status = f"{t['succeeded']}/{t['total_cmds']} succeeded"
            lines.append(f"  - {t['task'][:80]} ({status})")
        lines.append("=== END HISTORY ===")
        return "\n".join(lines)


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")
