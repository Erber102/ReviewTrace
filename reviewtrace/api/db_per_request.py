"""Per-request SQLite helpers for endpoints that accept an optional db_path override.

The global db.connection module uses a single _DB_PATH and is not safe to mutate
per-request. This module opens a fresh connection for the given path instead.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import HTTPException


def validate_db_path(requested: str | None) -> Path | None:
    """Return the resolved db path, validated to be within the server working directory.

    Returns None when no override was requested (caller should use the default DB).
    Raises 403 for path-traversal attempts, 404 if the file does not exist.
    """
    if requested is None:
        return None
    candidate = Path(requested).resolve()
    try:
        candidate.relative_to(Path.cwd().resolve())
    except ValueError:
        raise HTTPException(
            status_code=403,
            detail="db_path must be inside the server working directory",
        )
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="db_path does not exist")
    return candidate


def _open(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def fetchall(db_path: Path | None, sql: str, params: tuple = ()) -> list[dict]:
    """Run a SELECT and return all rows. Uses the global DB when db_path is None."""
    if db_path is None:
        from reviewtrace.db import connection as db
        return db.fetchall(sql, params)
    conn = _open(db_path)
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def fetchone(db_path: Path | None, sql: str, params: tuple = ()) -> dict | None:
    """Run a SELECT and return one row. Uses the global DB when db_path is None."""
    if db_path is None:
        from reviewtrace.db import connection as db
        return db.fetchone(sql, params)
    conn = _open(db_path)
    try:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
