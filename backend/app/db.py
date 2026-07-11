"""Local Postgres access via a psycopg3 connection pool."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import get_settings

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=get_settings().database_dsn,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


@contextmanager
def cursor() -> Iterator[Any]:
    """Yield a dict-row cursor inside a transaction (commit on success)."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            yield cur
        conn.commit()


def fetchone(sql: str, params: tuple = ()) -> dict | None:
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def fetchall(sql: str, params: tuple = ()) -> list[dict]:
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def execute(sql: str, params: tuple = ()) -> dict | None:
    """Execute a write. Returns a row if the statement has RETURNING."""
    with cursor() as cur:
        cur.execute(sql, params)
        if cur.description is not None:
            return cur.fetchone()
        return None
