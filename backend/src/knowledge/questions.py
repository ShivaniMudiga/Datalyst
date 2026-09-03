"""Four questions to suggest, from the snapshot and the purpose.

Nothing here names a domain. The questions are specific to the user's database
because the snapshot and the purpose text are - and those are the only two
things in this system that know what business they are in.
"""

from __future__ import annotations

import json
from typing import Any

from src.llm.zen_client import complete
from src.knowledge.snapshot import describe

COUNT = 4

PROMPT = """You suggest opening questions for a data assistant.

The assistant has been given this job by its user:
{purpose}

It is connected to this database:
{schema}

Write exactly {count} questions the user is likely to want answered first.

Rules:
- Every question must be answerable with SQL against the tables above.
- Use the vocabulary of this database and this job. Never generic filler like
  "show me some data".
- Vary them: one overview, one comparison across a group, one that finds
  outliers or risks, one about change over time.
- At most 60 characters each. No trailing full stop.

Reply with only a JSON array of {count} strings."""


# Purpose text plus snapshot fully determines the answer, and the answer costs a
# model call, so the same pair is never asked twice.
_cache: dict[tuple[str, str], list[str]] = {}


def suggest(purpose: str, snapshot: dict[str, Any] | None) -> list[str]:
    if not snapshot or not snapshot.get("tables"):
        return []

    key = (purpose.strip(), snapshot.get("read_at", ""))
    if key in _cache:
        return _cache[key]

    try:
        reply = complete(
            PROMPT.format(
                purpose=purpose.strip() or "General analysis of this database.",
                schema=describe(snapshot),
                count=COUNT,
            )
        )
        questions = json.loads(_json_array(reply))
        questions = [q.strip() for q in questions if isinstance(q, str) and q.strip()]
        if len(questions) >= COUNT:
            _cache[key] = questions[:COUNT]
            return _cache[key]
    except Exception:
        pass  # a suggestion is a convenience; never fail setup over one

    _cache[key] = _from_snapshot(snapshot)
    return _cache[key]


def _json_array(reply: str) -> str:
    """Models like to wrap JSON in prose or a fence. Take the array."""
    start, end = reply.find("["), reply.rfind("]")
    return reply[start : end + 1] if start != -1 and end > start else reply


def _from_snapshot(snapshot: dict[str, Any]) -> list[str]:
    """A usable fallback built only from names in the schema.

    Domain-agnostic code, domain-specific output - the names come from the
    user's database, so this reads correctly whatever the database is about.
    """
    tables = sorted(snapshot["tables"], key=lambda t: -t["row_count"])
    if not tables:
        return []

    biggest = tables[0]
    numeric = _column(biggest, ("integer", "numeric", "bigint", "double precision", "real"))
    temporal = _column(biggest, ("date", "timestamp"))
    grouping = next(
        (
            r["to_table"]
            for r in snapshot["relationships"]
            if r["from_table"] == biggest["name"]
        ),
        None,
    )

    questions = [f"Give me an overview of {snapshot['database']}"]

    if grouping:
        questions.append(f"Compare {biggest['name']} across {grouping}")
    if numeric:
        questions.append(f"Which {biggest['name']} have the highest {numeric}?")
    if temporal:
        questions.append(f"How has {biggest['name']} changed over time?")

    for table in tables[1:]:
        if len(questions) >= COUNT:
            break
        questions.append(f"Summarise {table['name']}")

    return questions[:COUNT]


def _column(table: dict[str, Any], types: tuple[str, ...]) -> str | None:
    for column in table["columns"]:
        if column["primary_key"]:
            continue
        if any(column["type"].startswith(prefix) for prefix in types):
            return column["name"]
    return None
