from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Callable


class DurableWorkflow:
    """Small checkpoint journal demonstrating resumability and idempotency."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS steps (
            run_id TEXT, step TEXT, status TEXT, output TEXT, attempts INTEGER,
            updated_at REAL, PRIMARY KEY(run_id, step))"""
        )
        self.connection.commit()

    def run(self, steps: list[tuple[str, Callable[[dict], dict]]], state: dict | None = None, run_id: str | None = None, max_attempts: int = 3) -> tuple[str, dict]:
        run_id = run_id or uuid.uuid4().hex
        state = dict(state or {})
        for name, operation in steps:
            row = self.connection.execute("SELECT status, output, attempts FROM steps WHERE run_id=? AND step=?", (run_id, name)).fetchone()
            if row and row[0] == "completed":
                state.update(json.loads(row[1]))
                continue
            attempts = int(row[2]) if row else 0
            while attempts < max_attempts:
                attempts += 1
                try:
                    output = operation(dict(state))
                    self._save(run_id, name, "completed", output, attempts)
                    state.update(output)
                    break
                except Exception as exc:
                    self._save(run_id, name, "failed", {"error": str(exc)}, attempts)
                    if attempts >= max_attempts:
                        raise
        return run_id, state

    def _save(self, run_id: str, step: str, status: str, output: dict, attempts: int) -> None:
        self.connection.execute(
            """INSERT INTO steps VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, step) DO UPDATE SET status=excluded.status,
            output=excluded.output, attempts=excluded.attempts, updated_at=excluded.updated_at""",
            (run_id, step, status, json.dumps(output, sort_keys=True), attempts, time.time()),
        )
        self.connection.commit()

