"""The PostgreSQL data source: the one place a query reaches a user's database."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.db.connection import ROW_CAP, data_cursor
from src.validator.sql_validator import SQLValidator
from src.validator.validation_result import ValidationResult

# Data Runtime's own bookkeeping. It lives in the same database as the user's
# data during local development, and it is not the user's data: it must never
# appear in the schema map, the system prompt, or a suggested question.
INTERNAL_TABLES = frozenset(
    {
        "users",
        "auth_sessions",
        "connections",
        "schema_snapshots",
        "chat_sessions",
        "chat_messages",
        "checkpoints",
        "checkpoint_blobs",
        "checkpoint_writes",
        "checkpoint_migrations",
    }
)

TABLES_AND_COLUMNS = """
SELECT c.table_name, c.column_name, c.data_type, c.is_nullable, c.ordinal_position
FROM information_schema.columns c
JOIN information_schema.tables t
  ON t.table_schema = c.table_schema AND t.table_name = c.table_name
WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE'
ORDER BY c.table_name, c.ordinal_position;
"""

# One query for every key in the schema. Joining pg_constraint beats calling
# information_schema.key_column_usage once per table.
KEYS = """
SELECT
    con.contype                          AS kind,
    src.relname                          AS table_name,
    src_col.attname                      AS column_name,
    tgt.relname                          AS references_table,
    tgt_col.attname                      AS references_column
FROM pg_constraint con
JOIN pg_class src ON src.oid = con.conrelid
JOIN pg_namespace ns ON ns.oid = src.relnamespace
JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord) ON TRUE
JOIN pg_attribute src_col ON src_col.attrelid = src.oid AND src_col.attnum = k.attnum
LEFT JOIN pg_class tgt ON tgt.oid = con.confrelid
LEFT JOIN LATERAL unnest(con.confkey) WITH ORDINALITY AS f(attnum, ord)
     ON f.ord = k.ord
LEFT JOIN pg_attribute tgt_col ON tgt_col.attrelid = tgt.oid AND tgt_col.attnum = f.attnum
WHERE con.contype IN ('p', 'f') AND ns.nspname = 'public'
ORDER BY src.relname, k.ord;
"""


class PostgresDataSource:
    """Implements ``DataSource`` against the read-only pool."""

    ENGINE = "PostgreSQL"

    QUERY_GUIDE = """- `run_query(sql)` takes ONE read-only SQL statement. It validates the SQL,
  runs it read-only, and returns rows.

Working with this database:

- Do not query `information_schema`. The schema above is complete.
- One statement per call. No semicolon-separated batches."""

    def __init__(self, params: dict[str, str] | None = None):
        # The credentials this user connected with. The pool is keyed by them,
        # so two users on different databases never share a connection.
        self._params = params or None
        self._validator: SQLValidator | None = None

    # -- reading the shape of the database ---------------------------------

    def introspect(self) -> dict[str, Any]:
        with data_cursor(self._params) as cursor:
            cursor.execute("SELECT current_database() AS name")
            database = cursor.fetchone()["name"]

            cursor.execute(TABLES_AND_COLUMNS)
            column_rows = cursor.fetchall()

            cursor.execute(KEYS)
            key_rows = cursor.fetchall()

            column_rows = [
                row for row in column_rows if row["table_name"] not in INTERNAL_TABLES
            ]
            key_rows = [
                row
                for row in key_rows
                if row["table_name"] not in INTERNAL_TABLES
                and row["references_table"] not in INTERNAL_TABLES
            ]

            names = sorted({row["table_name"] for row in column_rows})
            row_counts: dict[str, int] = {}
            for name in names:
                # ponytail: exact count. Swap to pg_class.reltuples if a table
                # ever gets big enough that this makes setup feel slow.
                cursor.execute(f'SELECT count(*) AS n FROM public."{name}"')
                row_counts[name] = cursor.fetchone()["n"]

        primary_keys: dict[str, set[str]] = {}
        foreign_keys: dict[str, list[dict[str, Any]]] = {}
        relationships: list[dict[str, Any]] = []

        for row in key_rows:
            table = row["table_name"]
            if row["kind"] == "p":
                primary_keys.setdefault(table, set()).add(row["column_name"])
                continue
            foreign_keys.setdefault(table, []).append(
                {
                    "column": row["column_name"],
                    "references_table": row["references_table"],
                    "references_column": row["references_column"],
                }
            )
            relationships.append(
                {
                    "from_table": table,
                    "from_column": row["column_name"],
                    "to_table": row["references_table"],
                    "to_column": row["references_column"],
                }
            )

        columns_by_table: dict[str, list[dict[str, Any]]] = {}
        for row in column_rows:
            columns_by_table.setdefault(row["table_name"], []).append(
                {
                    "name": row["column_name"],
                    "type": row["data_type"],
                    "nullable": row["is_nullable"] == "YES",
                    "primary_key": row["column_name"]
                    in primary_keys.get(row["table_name"], set()),
                }
            )

        tables = [
            {
                "name": name,
                "row_count": row_counts[name],
                "columns": columns_by_table[name],
                "foreign_keys": foreign_keys.get(name, []),
            }
            for name in names
        ]

        return {
            "database": database,
            "read_at": datetime.now(timezone.utc).isoformat(),
            "tables": tables,
            "relationships": relationships,
            "totals": {
                "tables": len(tables),
                "columns": sum(len(table["columns"]) for table in tables),
                "relationships": len(relationships),
                "rows": sum(row_counts.values()),
            },
        }

    # -- running a query ---------------------------------------------------

    def validate(self, statement: str) -> ValidationResult:
        if self._validator is None:
            from src.knowledge.snapshot import column_index, load_snapshot

            snapshot = load_snapshot()
            self._validator = SQLValidator(
                schema=column_index(snapshot) if snapshot else None
            )
        return self._validator.validate(statement)

    def execute(self, statement: str, row_cap: int | None = None) -> dict[str, Any]:
        cap = ROW_CAP if row_cap is None else row_cap

        with data_cursor(self._params) as cursor:
            cursor.execute(statement)

            if cursor.description is None:
                return {"rows": [], "row_count": 0, "truncated": False, "row_cap": cap}

            rows = cursor.fetchmany(cap + 1)

        truncated = len(rows) > cap
        rows = rows[:cap]

        return {
            "rows": [dict(row) for row in rows],
            "row_count": len(rows),
            "truncated": truncated,
            "row_cap": cap,
        }
