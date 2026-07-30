"""The single registry of MCP tools available to the conversational agent."""

from collections.abc import Callable
from typing import Any


def _get_tables() -> Any:
    """Load and invoke the existing MCP tool only when the model requests it."""
    from mcp_server import get_tables

    return get_tables()


def _get_columns(table_name: str) -> Any:
    """Load and invoke the existing MCP tool only when the model requests it."""
    from mcp_server import get_columns

    return get_columns(table_name)


def _execute_sql(query: str) -> Any:
    """Load and invoke the existing validation-backed MCP tool on demand."""
    from mcp_server import execute_sql

    return execute_sql(query)


FUNCTION_MAP: dict[str, Callable[..., Any]] = {
    "get_tables": _get_tables,
    "get_columns": _get_columns,
    "execute_sql": _execute_sql,
}
