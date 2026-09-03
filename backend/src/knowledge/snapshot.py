"""The schema, understood once and stored.

Every question after setup reads this, not ``information_schema``. That is the
difference between a tool that re-reads your database on every message and one
that understands it.
"""

from __future__ import annotations

from typing import Any, Iterator

from src.datasource.base import DataSource
from src.db.chat_store import ConnectionStore

STEPS = (
    ("connect", "Connecting"),
    ("tables", "Reading tables"),
    ("columns", "Reading columns"),
    ("relationships", "Mapping foreign keys"),
    ("rows", "Sampling row counts"),
)


def build_snapshot(source: DataSource | None = None) -> dict[str, Any]:
    from src.agent.tools import data_source

    return (source or data_source()).introspect()


def read_and_store(source: DataSource | None = None) -> Iterator[dict[str, Any]]:
    """Yield one progress event per step, then the finished snapshot.

    The read takes seconds, not milliseconds, so the caller streams it. The
    counts reported are the real ones - the steps are labels on work that has
    genuinely happened, never a fake progress animation.
    """
    snapshot = build_snapshot(source)
    totals = snapshot["totals"]

    results = {
        "connect": snapshot["database"],
        "tables": f"{totals['tables']} found",
        "columns": f"{totals['columns']} found",
        "relationships": f"{totals['relationships']} found",
        "rows": f"{totals['rows']:,}",
    }

    for index, (key, label) in enumerate(STEPS, start=1):
        yield {
            "event": "step",
            "key": key,
            "label": label,
            "result": results[key],
            "index": index,
            "total": len(STEPS),
        }

    ConnectionStore().save_snapshot(snapshot)
    yield {"event": "done", "snapshot": snapshot}


def load_snapshot() -> dict[str, Any] | None:
    return ConnectionStore().get_snapshot()


def column_index(snapshot: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    """The ``{table: {column: {...}}}`` shape the semantic validator wants."""
    return {
        table["name"]: {
            column["name"]: {"data_type": column["type"], "nullable": column["nullable"]}
            for column in table["columns"]
        }
        for table in snapshot["tables"]
    }


def describe(snapshot: dict[str, Any]) -> str:
    """The snapshot as compact text for the model's context.

    Deliberately terse: this sits in every prompt, so a wasted token here is a
    wasted token on every single turn.
    """
    lines = [f"Database: {snapshot['database']}", ""]

    for table in snapshot["tables"]:
        columns = ", ".join(
            f"{column['name']} {column['type']}{' PK' if column['primary_key'] else ''}"
            for column in table["columns"]
        )
        lines.append(f"{table['name']} ({table['row_count']} rows): {columns}")

    if snapshot["relationships"]:
        lines.append("")
        lines.append("Relationships:")
        lines += [
            f"  {r['from_table']}.{r['from_column']} -> {r['to_table']}.{r['to_column']}"
            for r in snapshot["relationships"]
        ]

    return "\n".join(lines)
