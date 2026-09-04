"""The tools the model can call.

``get_schema`` never touches the database - it returns what was read once at
setup. ``run_query`` is the only path from the model to the user's data.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.auth import user_id
from src.datasource.base import DataSource, create

# One source per connection, not per user: a user may have several databases
# connected and one active. Keying by user would answer a question against
# whichever of their databases happened to be cached first.
_sources: dict[str, DataSource] = {}


def active_connection_id() -> str:
    """The connection this user is on. Resolved per call, because switching
    database has to take effect on the next question, not the next restart."""
    from src.db.chat_store import ConnectionStore

    connection_id = ConnectionStore(user_id()).active_id()
    if connection_id is None:
        raise RuntimeError("No database is connected.")
    return connection_id


def data_source() -> DataSource:
    """The source for the database this user is on. Built once, then reused."""
    from src.db.chat_store import ConnectionStore

    who = user_id()
    key = active_connection_id()
    if key not in _sources:
        credentials = ConnectionStore(who).credentials() or {}
        _sources[key] = create(credentials.get("db_type"), credentials)
    return _sources[key]


def reset_data_source(connection_id: str | None = None) -> None:
    """Called when a connection's credentials or snapshot change."""
    source = _sources.pop(connection_id or active_connection_id(), None)
    if source is not None and hasattr(source, "close"):
        source.close()


def close_all_sources() -> None:
    """Shutdown only: every Mongo client this process opened."""
    while _sources:
        _, source = _sources.popitem()
        if hasattr(source, "close"):
            source.close()


def get_schema() -> Any:
    from src.knowledge.snapshot import load_snapshot

    snapshot = load_snapshot()
    if snapshot is None:
        return {"status": "no_schema", "message": "No schema has been read yet."}
    return {
        "database": snapshot["database"],
        "tables": snapshot["tables"],
        "relationships": snapshot["relationships"],
    }


def run_query(sql: str) -> Any:
    """Validate, then execute. ``sql`` carries whatever query language the
    connected engine speaks - SQL for Postgres, a JSON pipeline for MongoDB.

    ponytail: the argument stays named `sql` for both. Renaming it would mean
    a migration on chat_messages.sql and a change in the frontend for no
    behaviour. Rename if a third engine arrives.

    A rejection is a message to the model, not an exception - it carries the error_type the model needs to decide whether to
    fix and retry or to stop and explain."""
    source = data_source()
    validation = source.validate(sql)

    if not validation.valid:
        return {
            "status": "validation_failed",
            "sql": sql,
            "stage": validation.stage,
            "error_type": validation.error_type,
            "message": validation.message,
        }

    try:
        return source.execute(sql)
    except Exception as error:
        return {
            "status": "execution_failed",
            "sql": sql,
            "error_type": "execution",
            "message": str(error),
        }


FUNCTION_MAP: dict[str, Callable[..., Any]] = {
    "get_schema": get_schema,
    "run_query": run_query,
}
