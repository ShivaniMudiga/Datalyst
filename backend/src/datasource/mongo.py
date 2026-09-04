"""The MongoDB data source: collections read as tables, pipelines as queries.

The snapshot it produces is the same shape the PostgreSQL source produces, so
everything above the data source - describe(), the prompt, the schema screen,
suggested questions - works unchanged. Collections are tables, sampled fields
are columns, and there are no relationships because Mongo has no foreign keys.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import quote

from pymongo import MongoClient

from src.db.connection import ROW_CAP, STATEMENT_TIMEOUT_MS
from src.validator.pipeline_validator import PipelineValidator, parse
from src.validator.validation_result import ValidationResult

# Mongo has no catalogue, so the shape of a collection is inferred from a
# sample. Bigger is more accurate and slower; a hundred documents finds every
# field that appears in more than a few percent of them.
SAMPLE_SIZE = 100

CONNECT_TIMEOUT_MS = 8000

TYPE_NAMES = {
    bool: "bool",
    int: "int",
    float: "double",
    str: "string",
    dict: "object",
    list: "array",
    bytes: "binary",
    datetime: "date",
    Decimal: "decimal",
}


def uri(params: dict[str, str]) -> str:
    """A connection URI from the setup form.

    A host that already looks like a URI is passed through: that is the only
    practical way to reach Atlas (``mongodb+srv://``) or a replica set through
    a form with one host box.
    """
    host = (params.get("host") or "localhost").strip()
    if host.startswith("mongodb://") or host.startswith("mongodb+srv://"):
        return host

    port = params.get("port") or "27017"
    user = params.get("username") or ""
    password = params.get("password") or ""
    database = params.get("database") or ""

    auth = ""
    if user:
        auth = quote(user, safe="")
        if password:
            auth = f"{auth}:{quote(password, safe='')}"
        auth = f"{auth}@"

    # ponytail: authSource defaults to the database in the URI. Add an
    # authSource box if users turn up whose credentials live in `admin`.
    return f"mongodb://{auth}{host}:{port}/{database}"


def database_name(params: dict[str, str]) -> str:
    return params.get("database") or ""


# Postgres gets read-only from the connection itself: a role granted only
# SELECT, inside `default_transaction_read_only`. MongoDB has no equivalent -
# there is no read-only flag to pass a client - so the user's role is the only
# thing that would stop a write the pipeline validator missed. That makes the
# role the layer the validator sits in front of, and it is checked here, once,
# before a connection can be saved.
READ_ONLY_ROLES = frozenset({"read", "readAnyDatabase"})


def _write_privileges(client: MongoClient, database: str) -> str | None:
    """Why these credentials can write, or ``None`` if they cannot.

    A role that is not a known read-only one counts as writable, the same way
    the pipeline validator allowlists stages: `dbAdmin` cannot insert a
    document but can drop the collection, and an unrecognised custom role must
    not be assumed harmless.
    """
    info = client[database].command("connectionStatus")["authInfo"]

    if not info.get("authenticatedUsers"):
        return "this server has no access control"

    writable = sorted(
        {
            role["role"]
            for role in info.get("authenticatedUserRoles", [])
            if role["role"] not in READ_ONLY_ROLES
        }
    )
    return f"they hold {', '.join(writable)}" if writable else None


def check_connection(params: dict[str, str]) -> None:
    """Open one connection with these credentials. Raises if they do not work,
    or if they are allowed to write."""
    client = MongoClient(
        uri(params),
        serverSelectionTimeoutMS=CONNECT_TIMEOUT_MS,
        connectTimeoutMS=CONNECT_TIMEOUT_MS,
    )
    try:
        database = database_name(params)
        client[database].command("ping")

        writable = _write_privileges(client, database)
        if writable:
            raise ValueError(
                f"These credentials can write to {database}: {writable}. MongoDB "
                "cannot make a connection read-only, so the role is the only thing "
                "standing between the assistant and your data. Connect as a "
                "read-only user instead:\n"
                f'  db.createUser({{user: "reader", pwd: "...", '
                f'roles: [{{role: "read", db: "{database}"}}]}})'
            )
    finally:
        client.close()


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    for python_type, name in TYPE_NAMES.items():
        if isinstance(value, python_type):
            return name
    return type(value).__name__


def jsonable(value: Any) -> Any:
    """BSON down to something JSON, psycopg and pydantic all accept.

    ObjectId, Decimal128, Binary and friends reach the API response and the
    stored chat message; every one of them would fail to serialise there.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


class MongoDataSource:
    """Implements ``DataSource`` against a MongoDB database."""

    ENGINE = "MongoDB"

    QUERY_GUIDE = """- `run_query(sql)` takes ONE aggregation pipeline, as a JSON string:
  `{"collection": "orders", "pipeline": [{"$match": {...}}, {"$group": {...}}]}`
  The argument is called `sql` for historical reasons. It is a MongoDB
  aggregation pipeline, not SQL. Never send SQL.

Working with this database:

- Collections are listed above as if they were tables, and their fields as
  columns. The fields were inferred from a sample of documents, so a field can
  be missing from some documents - use `$ifNull` or `$exists` when it matters.
- A field listed with several types holds several types. Coerce before you
  compare.
- There are no foreign keys. Use `$lookup` only when the field names make the
  link unambiguous, and say so when you rely on one.
- Only reading stages are allowed. `$out`, `$merge`, `$where` and `$function`
  are rejected."""

    def __init__(self, params: dict[str, str] | None = None):
        self._params = params or {}
        self._client: MongoClient | None = None
        self._validator: PipelineValidator | None = None

    # -- connection --------------------------------------------------------

    def _database(self):
        if self._client is None:
            self._client = MongoClient(
                uri(self._params),
                serverSelectionTimeoutMS=CONNECT_TIMEOUT_MS,
                connectTimeoutMS=CONNECT_TIMEOUT_MS,
                maxPoolSize=int(os.getenv("DB_POOL_MAX", "8")),
            )
        return self._client[database_name(self._params)]

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    # -- reading the shape of the database ---------------------------------

    def introspect(self) -> dict[str, Any]:
        database = self._database()
        tables = []

        for name in sorted(database.list_collection_names()):
            collection = database[name]
            row_count = collection.estimated_document_count()

            seen: dict[str, set[str]] = {}
            present: dict[str, int] = {}
            sampled = 0

            for document in collection.aggregate(
                [{"$sample": {"size": SAMPLE_SIZE}}], maxTimeMS=STATEMENT_TIMEOUT_MS
            ):
                sampled += 1
                for field, value in document.items():
                    seen.setdefault(field, set()).add(_type_name(value))
                    present[field] = present.get(field, 0) + 1

            columns = [
                {
                    "name": field,
                    "type": "|".join(sorted(types)),
                    # A field missing from some sampled documents is, in
                    # practice, nullable.
                    "nullable": present[field] < sampled,
                    "primary_key": field == "_id",
                }
                for field, types in sorted(seen.items())
            ]

            tables.append(
                {
                    "name": name,
                    "row_count": row_count,
                    "columns": columns,
                    "foreign_keys": [],
                }
            )

        return {
            "database": database.name,
            "read_at": datetime.now(timezone.utc).isoformat(),
            "tables": tables,
            "relationships": [],
            "totals": {
                "tables": len(tables),
                "columns": sum(len(table["columns"]) for table in tables),
                "relationships": 0,
                "rows": sum(table["row_count"] for table in tables),
            },
        }

    # -- running a query ---------------------------------------------------

    def validate(self, statement: str) -> ValidationResult:
        if self._validator is None:
            from src.knowledge.snapshot import load_snapshot

            snapshot = load_snapshot()
            self._validator = PipelineValidator(
                collections={table["name"] for table in snapshot["tables"]}
                if snapshot
                else None
            )
        return self._validator.validate(statement)

    def execute(self, statement: str, row_cap: int | None = None) -> dict[str, Any]:
        cap = ROW_CAP if row_cap is None else row_cap
        request, failure = parse(statement)
        if failure is not None:
            raise ValueError(failure.message)

        # One past the cap, so a full page can be told from a truncated one.
        pipeline = [*request["pipeline"], {"$limit": cap + 1}]
        cursor = self._database()[request["collection"]].aggregate(
            pipeline, maxTimeMS=STATEMENT_TIMEOUT_MS
        )
        documents = list(cursor)

        truncated = len(documents) > cap
        documents = documents[:cap]

        return {
            "rows": [jsonable(document) for document in documents],
            "row_count": len(documents),
            "truncated": truncated,
            "row_cap": cap,
        }
