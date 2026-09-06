"""PostgreSQL access layer (psycopg 3 + a process-wide connection pool).

Design goals:
- Call sites read like the classic SQLite layer:
  `db.execute(sql, params).fetchone()` and `row["col"]` both work because the
  pooled connection uses `row_factory=dict_row` and psycopg's
  `Connection.execute()` returns a cursor.
- One pooled connection per request via the `get_db` FastAPI dependency. The
  pool's context manager commits on clean exit and rolls back on exception.

Note: psycopg uses `%s` placeholders (not `?`), and a literal percent sign in
SQL must be written as `%%`.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"
# Legacy device tables kept alive for pre-12.9 clients (ADR-001). Applied after
# the core schema; delete together with the legacy endpoints.
LEGACY_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema_legacy.sql"

# Opened lazily in init_db() so the module can be imported without a reachable
# database (local syntax checks, tooling).
pool = ConnectionPool(
    conninfo=settings.database_url,
    min_size=settings.db_pool_min,
    max_size=settings.db_pool_max,
    kwargs={"row_factory": dict_row, "autocommit": False},
    open=False,
)


def init_db() -> None:
    """Open the pool and apply both schema files (idempotent — every statement
    is CREATE ... IF NOT EXISTS / ALTER ... IF NOT EXISTS).

    schema_legacy.sql alters tables the core creates, so the core runs first."""
    pool.open()
    core_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    legacy_sql = LEGACY_SCHEMA_PATH.read_text(encoding="utf-8")
    with pool.connection() as conn:
        # Plain DDL, no parameters → psycopg runs each whole multi-statement
        # script via the simple-query protocol.
        with conn.cursor() as cur:
            cur.execute(core_sql)
            cur.execute(legacy_sql)

    # Carry out any erasure that fell due while the server was down, so a
    # deletion never waits on a client happening to poll.
    from .routes.rules import run_due_erasures
    with pool.connection() as conn:
        run_due_erasures(conn)


def get_db() -> Iterator[psycopg.Connection]:
    """FastAPI dependency: a pooled connection, auto-returned to the pool.

    The pool context commits on success and rolls back on exception; route code
    may still call `db.commit()` explicitly (a redundant commit is harmless).
    """
    with pool.connection() as conn:
        yield conn
