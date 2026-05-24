"""SQLite history cache for `comps show` / `comps why`.

Keyed by terminal session. We persist the result rows of the last search
so `show N` and `why A B` can refer to them by rank.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

HISTORY_DIR = Path.home() / ".comps"
HISTORY_DB = HISTORY_DIR / "history.db"


def _session_key() -> str:
    # Prefer the parent shell PID; fall back to TTY name.
    return os.environ.get("COMPS_SESSION") or str(os.getppid())


def _conn() -> sqlite3.Connection:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(HISTORY_DB)
    conn.execute(
        """
        create table if not exists searches (
            session   text not null,
            ts        text not null,
            query     text not null,
            results   text not null,
            primary key (session, ts)
        )
        """
    )
    return conn


def save(query: str, results: list[dict]) -> None:
    ts = datetime.now(UTC).isoformat()
    with _conn() as c:
        c.execute(
            "insert into searches (session, ts, query, results) values (?, ?, ?, ?)",
            (_session_key(), ts, query, json.dumps(results)),
        )


def last(session: str | None = None) -> tuple[str, list[dict]] | None:
    sess = session or _session_key()
    with _conn() as c:
        row = c.execute(
            "select query, results from searches where session = ? order by ts desc limit 1",
            (sess,),
        ).fetchone()
    if not row:
        return None
    return row[0], json.loads(row[1])
