"""Two commands the demo needs, and nothing else.

  python -m packs.recon.demo prep     hold one payout file back for the stage
  python -m packs.recon.demo status   is this machine ready to demonstrate?
  python -m packs.recon.demo one      work one exception live, showing the work

`prep` exists because the most convincing beat is the rules running on a file
that arrives in front of the audience - and once everything is matched, running
the matcher again prints a column of zeros. So one file is withdrawn: its
batch, lines, matches and exceptions are deleted, and the remaining eight keep
the proposals the queue needs. The audit log keeps every proposal either way; it
has no foreign key and cannot be deleted from.

`status` exists because a demo that fails does so for boring reasons - a file
not ingested, the matcher not run, no exception left unworked for the live
moment, the other database never created. It checks all of those in a second
rather than on stage.
"""

from __future__ import annotations

import json
import sys

import psycopg

from packs.recon.agent import reader, work
from packs.recon.db import DSN, cursor

# The file the audience watches arrive. Ingesting it on stage is the only way
# the tier histogram has anything to print.
HELD_BACK = "razorpay-2026-07.csv"

CHECKS = """
SELECT (SELECT count(*) FROM settlement_batches)                            AS batches,
       (SELECT count(*) FROM settlement_lines)                              AS lines,
       (SELECT count(*) FROM matches)                                       AS matches,
       (SELECT count(*) FROM exceptions WHERE status = 'open')              AS open_exceptions,
       (SELECT count(*) FROM resolutions WHERE state = 'proposed')          AS awaiting,
       (SELECT count(*) FROM exceptions e
        WHERE e.status = 'open' AND e.reason_code = 'no_reference'
          AND NOT EXISTS (SELECT 1 FROM resolutions r
                          WHERE r.exception_id = e.exception_id
                            AND r.state IN ('proposed','approved','applied'))) AS unworked,
       (SELECT count(*) FROM settlement_batches WHERE file_name = %s)       AS held_back
"""


def prep() -> int:
    """Withdraw the held-back file so the stage has something to ingest."""
    with cursor(commit=True) as cur:
        cur.execute("SELECT payout_id FROM settlement_batches WHERE file_name = %s", (HELD_BACK,))
        batch = cur.fetchone()
        if not batch:
            print(f"{HELD_BACK} is already held back - nothing to do")
            return 0

        cur.execute("""DELETE FROM resolutions WHERE exception_id IN (
                         SELECT e.exception_id FROM exceptions e
                         JOIN settlement_lines l ON l.line_id = e.line_id
                         WHERE l.payout_id = %s)""", (batch["payout_id"],))
        dropped = cur.rowcount
        cur.execute("DELETE FROM settlement_batches WHERE payout_id = %s", (batch["payout_id"],))

        cur.execute("SELECT count(*) AS n FROM settlement_lines")
        remaining = cur.fetchone()["n"]

    print(f"withdrew {batch['payout_id']} ({dropped} of its proposals with it)")
    print(f"{remaining:,} lines remain matched, and the queue keeps their proposals")
    print(f"on stage: python -m packs.recon.ingest ../payouts/{HELD_BACK}")
    return 0

UNWORKED = """
SELECT e.exception_id, e.amount_minor, l.settled_at, l.narration, b.gateway
FROM exceptions e
JOIN settlement_lines l ON l.line_id = e.line_id
JOIN settlement_batches b ON b.payout_id = l.payout_id
WHERE e.status = 'open' AND e.reason_code = 'no_reference'
  AND NOT EXISTS (SELECT 1 FROM resolutions r WHERE r.exception_id = e.exception_id
                  AND r.state IN ('proposed','approved','applied'))
ORDER BY e.amount_minor DESC LIMIT 1
"""


def status() -> int:
    with cursor() as cur:
        cur.execute(CHECKS, (HELD_BACK,))
        state = cur.fetchone()

    other = "postgresql://data_runtime_reader:change_me@localhost:5432/leakage_check_transit"
    try:
        with psycopg.connect(other) as connection:
            connection.execute("SELECT 1 FROM stations LIMIT 1")
        portable = True
    except Exception:
        portable = False

    rows = [
        ("payout files ingested", state["batches"], state["batches"] >= 3,
         "python -m packs.recon.ingest --reset ../payouts/*.csv"),
        ("lines to reconcile", state["lines"], state["lines"] > 0, ""),
        ("matched by rule", state["matches"], state["matches"] > 0,
         "python -m packs.recon.match --reset"),
        ("exceptions in the queue", state["open_exceptions"], state["open_exceptions"] > 0, ""),
        ("proposals awaiting a person", state["awaiting"], state["awaiting"] >= 3,
         "python -m packs.recon.agent --all"),
        ("left unworked, for the live moment", state["unworked"], state["unworked"] >= 1,
         "leave at least one; --all works them all"),
        (f"{HELD_BACK} held back for the stage", "yes" if not state["held_back"] else "ALREADY INGESTED",
         not state["held_back"], "python -m packs.recon.demo prep"),
        ("the other database, for the last 15 seconds", "transit" if portable else "missing", portable,
         "psql -d postgres -f database/14_domain_leakage_check.sql"),
    ]

    failed = 0
    for label, value, ok, fix in rows:
        mark = "ok  " if ok else "NOT "
        print(f"  {mark}{label:<44} {value}")
        if not ok:
            failed += 1
            if fix:
                print(f"       → {fix}")
    print("\nready" if not failed else f"\n{failed} thing(s) to fix before demonstrating")
    return 0 if not failed else 1


def one() -> int:
    """Work a single exception with the model, printing each step as it happens."""
    with cursor() as cur:
        cur.execute(UNWORKED)
        exception = cur.fetchone()
    if not exception:
        print("nothing left unworked - every nameless exception already has a proposal")
        return 1

    print(f"exception {exception['exception_id']}  ·  {exception['gateway']}  ·  "
          f"₹{exception['amount_minor'] / 100:,.2f}")
    print(f"the gateway wrote: {exception['narration']!r}\n")

    def trace(name, arguments, result):
        if name == "query":
            status = result.get("status", "ok")
            detail = (f"{result.get('row_count', 0)} rows" if status == "ok"
                      else f"REJECTED by the validator: {result.get('error_type')}")
            print(f"  query    {arguments.get('sql', '')[:96]}\n           → {detail}")
        else:
            print(f"  propose  {json.dumps(arguments, default=str)[:140]}\n           → {result.get('status')}")

    source, validator = reader()
    result = work(exception, source, validator, trace=trace)
    print(f"\n{result.get('status')}"
          + (f" as resolution {result['resolution_id']}" if result.get("resolution_id") else ""))

    from src.db.connection import close_all
    close_all()
    return 0


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    sys.exit({"status": status, "one": one, "prep": prep}.get(command, status)())
