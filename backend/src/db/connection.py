"""Pooled PostgreSQL access.

Two pools, deliberately separated:

``app_pool``   read-write - accounts, chat sessions, messages, checkpoints.
``data_pool``  read-only  - every query the model generates, plus schema
                            introspection. That connection's own role, not
                            Python, is what stands between the model and the
                            data.

There is one data pool per set of credentials, keyed by DSN: users sign in to
their own databases, and a single shared pool would hand one user's queries to
another user's database.

A pooled connection is checked out per query and rolled back on the way out,
so a failed query can never poison the next one.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

STATEMENT_TIMEOUT_MS = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "15000"))
ROW_CAP = int(os.getenv("DB_ROW_CAP", "500"))
POOL_MAX = int(os.getenv("DB_POOL_MAX", "8"))

_pools: dict[str, ConnectionPool] = {}


def _dsn(user: str, password: str | None) -> str:
    auth = quote(user, safe="")
    if password:
        auth = f"{auth}:{quote(password, safe='')}"
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "talk_to_my_data_v2")
    return f"postgresql://{auth}@{host}:{port}/{name}"


def app_dsn() -> str:
    """The read-write role. Owns the application's own tables."""
    return _dsn(os.getenv("DB_USER", "postgres"), os.getenv("DB_PASSWORD"))


def data_dsn(params: dict[str, str] | None = None) -> str:
    """The read-only connection: this user's database, read-only, timeout-bounded.

    Without credentials it falls back to the DB_* environment, which is what
    the local development database and the test scripts use.
    """
    if params:
        host = params.get("host", "localhost")
        port = params.get("port", "5432")
        name = params.get("database", "")
        user = params.get("username", "")
        password = params.get("password") or None
        auth = quote(user, safe="")
        if password:
            auth = f"{auth}:{quote(password, safe='')}"
        return f"postgresql://{auth}@{host}:{port}/{name}"

    user = os.getenv("DB_READONLY_USER")
    if user:
        return _dsn(user, os.getenv("DB_READONLY_PASSWORD"))
    return app_dsn()


def check_data_connection(params: dict[str, str]) -> None:
    """Open one connection with these credentials. Raises if they do not work."""
    import psycopg

    host = params.get("host", "localhost")
    port = params.get("port", "5432")
    name = params.get("database", "")
    user = params.get("username", "")
    password = params.get("password") or None
    auth = quote(user, safe="")
    if password:
        auth = f"{auth}:{quote(password, safe='')}"

    with psycopg.connect(
        f"postgresql://{auth}@{host}:{port}/{name}", connect_timeout=8
    ) as connection:
        connection.execute("SELECT 1")


def _configure(read_only: bool):
    def configure(conn) -> None:
        conn.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")
        if read_only:
            conn.execute("SET default_transaction_read_only = on")
        conn.commit()

    return configure


def _pool(name: str, dsn: str, read_only: bool) -> ConnectionPool:
    pool = _pools.get(name)
    if pool is None:
        pool = ConnectionPool(
            dsn,
            min_size=1,
            max_size=POOL_MAX,
            kwargs={"row_factory": dict_row},
            configure=_configure(read_only),
            open=False,
        )
        pool.open()
        _pools[name] = pool
    return pool


def app_pool() -> ConnectionPool:
    return _pool("app", app_dsn(), read_only=False)


def data_pool(params: dict[str, str] | None = None) -> ConnectionPool:
    """The read-only pool for these credentials. Keyed by DSN, so two users on
    the same database share one pool and two users on different databases can
    never share a connection."""
    dsn = data_dsn(params)
    return _pool(f"data:{dsn}", dsn, read_only=True)


def close_data_pool(params: dict[str, str] | None = None) -> None:
    """Drop the pool for these credentials, after the connection changes."""
    pool = _pools.pop(f"data:{data_dsn(params)}", None)
    if pool is not None:
        pool.close()


@contextmanager
def data_cursor(params: dict[str, str] | None = None):
    """A cursor on a read-only, timeout-bounded transaction. Never commits."""
    with data_pool(params).connection() as conn:
        with conn.cursor() as cursor:
            yield cursor
        conn.rollback()


@contextmanager
def app_cursor(commit: bool = True):
    """A cursor on the read-write pool. Commits on clean exit, rolls back on error."""
    with app_pool().connection() as conn:
        with conn.cursor() as cursor:
            yield cursor
        if not commit:
            conn.rollback()


def close_all() -> None:
    while _pools:
        _, pool = _pools.popitem()
        pool.close()
