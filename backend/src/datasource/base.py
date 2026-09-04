"""The database boundary.

Everything the rest of the app knows about a database goes through this
protocol, and every choice of engine goes through ``create`` below. Nothing
above this line branches on ``db_type``.
"""

from __future__ import annotations

from typing import Any, Protocol

from src.validator.validation_result import ValidationResult

MONGO = "mongodb"


class DataSource(Protocol):
    # Named in the system prompt, and the engine-specific half of it.
    ENGINE: str
    QUERY_GUIDE: str

    def introspect(self) -> dict[str, Any]:
        """Read the whole schema once: tables, columns, keys, row counts."""

    def validate(self, statement: str) -> ValidationResult:
        """Check a statement without running it."""

    def execute(self, statement: str, row_cap: int | None = None) -> dict[str, Any]:
        """Run a validated read and return capped rows."""


def create(db_type: str | None, params: dict[str, str] | None = None) -> DataSource:
    """The data source for a connection. The only place engines are chosen."""
    if (db_type or "").lower() == MONGO:
        from src.datasource.mongo import MongoDataSource

        return MongoDataSource(params)

    from src.datasource.postgres import PostgresDataSource

    return PostgresDataSource(params)


def check(params: dict[str, str]) -> None:
    """Open one connection with these credentials. Raises if they do not work."""
    if (params.get("db_type") or "").lower() == MONGO:
        from src.datasource.mongo import check_connection

        return check_connection(params)

    from src.db.connection import check_data_connection

    return check_data_connection(params)
