"""Thin SQLite wrapper. No ORM — schema changes frequently."""

import sqlite3
from pathlib import Path
from typing import Any

_DB_PATH: Path | None = None
_SCHEMA_PATH = Path(__file__).parent / "schema.sql"
_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def init_db(db_path: str | Path = "reviewtrace.db") -> None:
    """Initialize DB at given path, applying schema and any pending migrations."""
    global _DB_PATH
    _DB_PATH = Path(db_path)
    conn = _get_conn()
    _apply_schema(conn)
    _apply_migrations(conn)
    conn.close()


def _get_conn() -> sqlite3.Connection:
    if _DB_PATH is None:
        raise RuntimeError("DB not initialized — call init_db() first")
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def execute(sql: str, params: tuple[Any, ...] = ()) -> None:
    conn = _get_conn()
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def executemany(sql: str, params_seq: list[tuple[Any, ...]]) -> None:
    conn = _get_conn()
    try:
        conn.executemany(sql, params_seq)
        conn.commit()
    finally:
        conn.close()


def fetchall(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn = _get_conn()
    try:
        cur = conn.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def fetchone(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    conn = _get_conn()
    try:
        cur = conn.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema & migrations
# ---------------------------------------------------------------------------

def _apply_schema(conn: sqlite3.Connection) -> None:
    schema = _SCHEMA_PATH.read_text()
    conn.executescript(schema)
    conn.commit()


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply SQL migration files from migrations/ in order, skipping already-applied ones."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS _migrations (filename TEXT PRIMARY KEY, applied_at TEXT DEFAULT (datetime('now')))"
    )
    conn.commit()

    applied = {row[0] for row in conn.execute("SELECT filename FROM _migrations")}

    migration_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    for mf in migration_files:
        if mf.name in applied:
            continue
        conn.executescript(mf.read_text())
        conn.execute("INSERT INTO _migrations (filename) VALUES (?)", (mf.name,))
        conn.commit()


# ---------------------------------------------------------------------------
# Named query helpers (grow these as modules need them)
# ---------------------------------------------------------------------------

def insert_paper(paper: dict[str, Any]) -> None:
    execute(
        """
        INSERT OR IGNORE INTO papers
            (id, doi, arxiv_id, s2_paper_id, title, authors, year, venue, abstract,
             source_type, url, citation_count, reference_count)
        VALUES
            (:id, :doi, :arxiv_id, :s2_paper_id, :title, :authors, :year, :venue, :abstract,
             :source_type, :url, :citation_count, :reference_count)
        """,
        tuple(paper.get(k) for k in [
            "id", "doi", "arxiv_id", "s2_paper_id", "title", "authors", "year", "venue",
            "abstract", "source_type", "url", "citation_count", "reference_count",
        ]),
    )


def get_paper_by_id(paper_id: str) -> dict[str, Any] | None:
    return fetchone("SELECT * FROM papers WHERE id = ?", (paper_id,))


def get_paper_by_doi(doi: str) -> dict[str, Any] | None:
    return fetchone("SELECT * FROM papers WHERE doi = ?", (doi,))


def get_retrieval_path(paper_id: str) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT pr.citation_path, pr.retrieval_reason, rr.query, rr.source, rr.timestamp
        FROM paper_retrievals pr
        JOIN retrieval_runs rr ON pr.retrieval_run_id = rr.id
        WHERE pr.paper_id = ?
        ORDER BY pr.created_at
        """,
        (paper_id,),
    )
