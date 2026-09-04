"""The agent, working the exceptions no rule could place.

It gets one exception at a time and two tools: a read-only query, and the one
action it has - propose a resolution. It cannot apply anything, and there is no
code path from here to `commit.py`.

Its whole job is the part a rule genuinely cannot do: read the gateway's free
text, decide which order it is talking about, and check that story against the
ledger. Roughly half of these narrations carry a batch number rather than an
order id, so the answer is often "a person should look at this" - and saying so
is a correct answer, not a failure.

  python -m packs.recon.agent --limit 5
"""

from __future__ import annotations

import argparse
import json
import os
import time

from packs.recon.db import cursor
from packs.recon.propose import TOOL_DESCRIPTION, TOOL_PARAMETERS, propose_resolution
from src.datasource.base import create
from src.llm.zen_client import chat

STEP_BUDGET = 6

SYSTEM = """You are reconciling a payment gateway's settlement file against the
merchant's own ledger, in PostgreSQL.

A settlement line could not be matched by any rule because the gateway did not
echo its reference. All you have is the amount, the date and the free text the
gateway wrote. Your job is to work out which captured payment it is - or to say
honestly that you cannot.

The tables that matter:
  payments          the ledger. payment_id, order_id, gateway, amount (rupees),
                    gateway_fee, captured_at, payment_status, gateway_reference
  settlement_lines  the file as received, including `narration`
  matches           what is already accounted for. A payment that appears here
                    is taken, and cannot be the answer.

How to work:
1. Read the narration. It may contain an order id in any human shape, or it may
   contain only the gateway's own batch number, which identifies nothing.
2. If you think you have an order id, check it: does that order have a captured
   payment, on this gateway, for this exact amount, before this settlement date,
   that is not already in `matches`? A number that looks like an order id but
   fails those checks is a false lead - say so and escalate.
3. Amounts in `payments` are rupees; the line is in paise. Compare with
   round(amount * 100).
4. Then call propose_resolution exactly once, and stop.

Only propose `link` when the checks in step 2 all passed. `escalate` is the
right answer whenever the narration names nothing you could verify - it is not a
failure, and a wrong link costs more than an escalation."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query",
            "description": "Run one read-only SQL query against the merchant's database.",
            "parameters": {
                "type": "object",
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_resolution",
            "description": TOOL_DESCRIPTION,
            "parameters": TOOL_PARAMETERS,
        },
    },
]

OPEN_EXCEPTIONS = """
SELECT e.exception_id, e.amount_minor, l.settled_at, l.narration, b.gateway
FROM exceptions e
JOIN settlement_lines l ON l.line_id = e.line_id
JOIN settlement_batches b ON b.payout_id = l.payout_id
WHERE e.status = 'open' AND e.reason_code = 'no_reference'
  AND NOT EXISTS (SELECT 1 FROM resolutions r
                  WHERE r.exception_id = e.exception_id
                    AND r.state IN ('proposed', 'approved', 'applied'))
ORDER BY e.amount_minor DESC
LIMIT %s
"""


def reader():
    """The model's only reach into the database: the runtime's read-only role,
    inside a read-only transaction, with the runtime's timeout and row cap.

    The validator is built here rather than taken from the data source, because
    the source's own `validate` loads the *signed-in user's* stored snapshot and
    there is no signed-in user in a pack script. Same validator, same four
    stages - it is only the schema it checks against that comes from a fresh
    introspection instead of a session.
    """
    from src.knowledge.snapshot import column_index
    from src.validator.sql_validator import SQLValidator

    source = create("postgresql", {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "database": os.getenv("RECON_DATABASE", "kartly"),
        "username": os.getenv("DB_READONLY_USER", "data_runtime_reader"),
        "password": os.getenv("DB_READONLY_PASSWORD", ""),
    })
    return source, SQLValidator(schema=column_index(source.introspect()))


def work(exception: dict, source, validator) -> dict:
    """One exception, one proposal, at most STEP_BUDGET model turns."""
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps({
            "exception_id": exception["exception_id"],
            "gateway": exception["gateway"],
            "amount_minor": exception["amount_minor"],
            "settled_at": str(exception["settled_at"]),
            "narration": exception["narration"],
        })},
    ]

    cost = {"steps": 0, "corrections": 0, "latency_ms": 0}
    started = time.monotonic()

    for _ in range(STEP_BUDGET):
        cost["steps"] += 1
        message = chat(messages, tools=TOOLS)
        calls = getattr(message, "tool_calls", None) or []
        messages.append({
            "role": "assistant",
            "content": message.content or "",
            **({"tool_calls": [
                {"id": call.id, "type": "function",
                 "function": {"name": call.function.name, "arguments": call.function.arguments}}
                for call in calls]} if calls else {}),
        })
        if not calls:
            return {"status": "gave_up", "message": message.content}

        for call in calls:
            name = call.function.name
            try:
                arguments = json.loads(call.function.arguments or "{}")
                if name == "query":
                    sql = arguments.get("sql", "")
                    validation = validator.validate(sql)
                    if validation.valid:
                        result = source.execute(sql)
                    else:
                        cost["corrections"] += 1
                        result = {"status": "validation_failed", "error_type": validation.error_type,
                                  "message": validation.message}
                elif name == "propose_resolution":
                    cost["latency_ms"] = int((time.monotonic() - started) * 1000)
                    result = propose_resolution(**arguments, _cost=cost)
                else:
                    result = {"status": "tool_error", "message": f"no tool named {name}"}
            except Exception as error:
                result = {"status": "tool_error", "message": str(error)}

            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(result, default=str)})
            if name == "propose_resolution" and result.get("status") == "proposed":
                return result

    return {"status": "out_of_steps"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--all", action="store_true", help="every open nameless exception")
    args = parser.parse_args()

    with cursor() as cur:
        cur.execute(OPEN_EXCEPTIONS, (10000 if args.all else args.limit,))
        queue = cur.fetchall()

    source, validator = reader()
    for exception in queue:
        # A queue of 37 must not be ended by whatever went wrong on number 3.
        try:
            result = work(exception, source, validator)
        except Exception as error:
            result = {"status": "failed", "message": str(error)[:80]}
        print(f"  #{exception['exception_id']:<5} {exception['narration'][:44]:<46} "
              f"{result.get('status'):<10} {result.get('resolution_id', '')}")


if __name__ == "__main__":
    main()
