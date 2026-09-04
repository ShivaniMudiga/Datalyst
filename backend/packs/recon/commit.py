"""The only code that changes the ledger's view of what is settled.

Everything here is deterministic. It takes a proposal the agent wrote and a
person approved, checks that the world still looks the way it did when the
proposal was made, and then does exactly what the proposal's `kind` says - no
interpretation, no model output reaching a decision.

Four properties this module exists to hold:

  gated        nothing applies from `proposed`; a person must approve, by name
  verified     the evidence is recomputed and re-hashed; a stale proposal is refused
  idempotent   applying twice changes one row, not two, and says so
  reversible   every apply records what it did, and `reverse` undoes exactly that

The model cannot call any of this. Its only reach into the database is the
runtime's read-only `run_query`, and its only write is a row in `resolutions`.

Applying needs `RECON_WRITE_DSN` set explicitly. A process that is only meant to
read and propose never holds credentials that can apply.

ponytail: locally that DSN is the same owner role as the reader. In anything
real it is a separate role with INSERT on `matches` and nothing else.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from hashlib import sha256

import psycopg
from psycopg.rows import dict_row

from packs.recon.propose import evidence_for

AGENT_TIER = "AGENT"


@contextmanager
def write_cursor():
    dsn = os.getenv("RECON_WRITE_DSN")
    if not dsn:
        raise PermissionError(
            "RECON_WRITE_DSN is not set: this process may read and propose, not apply."
        )
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        with connection.cursor() as cur:
            yield cur
        connection.commit()


def _audit(cur, actor, action, resolution, before=None, after=None, digest=None) -> None:
    cur.execute(
        """INSERT INTO audit_log (actor, action, resolution_id, exception_id,
                                  before_state, after_state, evidence_hash)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (actor, action, resolution["resolution_id"], resolution["exception_id"],
         json.dumps(before) if before else None,
         json.dumps(after) if after else None, digest),
    )


def _load(cur, resolution_id: int) -> dict:
    cur.execute("SELECT * FROM resolutions WHERE resolution_id = %s FOR UPDATE", (resolution_id,))
    resolution = cur.fetchone()
    if resolution is None:
        raise LookupError(f"no resolution {resolution_id}")
    return resolution


def decide(resolution_id: int, actor: str, accept: bool, note: str = "") -> dict:
    """A person accepts or rejects. Nothing is applied either way."""
    state = "approved" if accept else "rejected"
    with write_cursor() as cur:
        resolution = _load(cur, resolution_id)
        cur.execute(
            "UPDATE resolutions SET state = %s, decided_by = %s WHERE resolution_id = %s",
            (state, actor, resolution_id),
        )
        _audit(cur, actor, state, resolution,
               before={"state": resolution["state"]},
               after={"state": state, "note": note})
    return {"status": state, "resolution_id": resolution_id}


def _idempotency_key(cur, resolution: dict) -> str:
    """Stable across retries: the file that raised the exception, the exception,
    the decision taken, and what it names."""
    cur.execute(
        """SELECT b.file_hash FROM exceptions e
           JOIN settlement_lines l ON l.line_id = e.line_id
           JOIN settlement_batches b ON b.payout_id = l.payout_id
           WHERE e.exception_id = %s""",
        (resolution["exception_id"],),
    )
    row = cur.fetchone()
    source = row["file_hash"] if row else "ledger"
    targets = ",".join(str(target) for target in sorted(resolution["target_ids"]))
    return sha256(f"{source}:{resolution['exception_id']}:{resolution['kind']}:{targets}".encode()).hexdigest()


def _apply_link(cur, resolution: dict) -> dict:
    """Record the match the agent proposed, and close both sides of the gap."""
    payment_id = resolution["target_ids"][0]
    cur.execute("SELECT line_id FROM exceptions WHERE exception_id = %s", (resolution["exception_id"],))
    line_id = cur.fetchone()["line_id"]

    cur.execute(
        """INSERT INTO matches (line_id, payment_id, match_tier, confidence, matched_by)
           VALUES (%s, %s, %s, %s, 'agent') RETURNING match_id""",
        (line_id, payment_id, AGENT_TIER, resolution["confidence"]),
    )
    match_id = cur.fetchone()["match_id"]

    cur.execute(
        """UPDATE exceptions SET status = 'resolved'
           WHERE status = 'open' AND (exception_id = %s OR payment_id = %s)
           RETURNING exception_id""",
        (resolution["exception_id"], payment_id),
    )
    closed = [row["exception_id"] for row in cur.fetchall()]
    return {"match_id": match_id, "closed_exceptions": closed}


def _apply_status(cur, resolution: dict, status: str) -> dict:
    cur.execute(
        "UPDATE exceptions SET status = %s WHERE exception_id = %s RETURNING exception_id",
        (status, resolution["exception_id"]),
    )
    return {"closed_exceptions": [row["exception_id"] for row in cur.fetchall()], "status": status}


def apply(resolution_id: int, actor: str) -> dict:
    """Carry out an approved resolution. Safe to call twice."""
    with write_cursor() as cur:
        resolution = _load(cur, resolution_id)

        if resolution["state"] == "applied":
            return {"status": "already_applied", "resolution_id": resolution_id,
                    "effect": resolution["applied_effect"],
                    "message": "this resolution was already applied; nothing changed"}
        if resolution["state"] != "approved":
            return {"status": "refused", "resolution_id": resolution_id,
                    "message": f"only an approved resolution can be applied (state: {resolution['state']})"}

        _, digest, _ = evidence_for(resolution["exception_id"], list(resolution["target_ids"]))
        if digest != resolution["evidence_hash"]:
            _audit(cur, actor, "refused_stale_evidence", resolution,
                   before={"evidence_hash": resolution["evidence_hash"]},
                   after={"evidence_hash": digest})
            return {"status": "refused", "resolution_id": resolution_id,
                    "message": "the evidence changed since this was proposed; re-propose against current data"}

        key = _idempotency_key(cur, resolution)
        if resolution["kind"] == "link":
            effect = _apply_link(cur, resolution)
        elif resolution["kind"] == "write_off":
            effect = _apply_status(cur, resolution, "written_off")
        else:
            effect = _apply_status(cur, resolution, "escalated")

        cur.execute(
            """UPDATE resolutions SET state = 'applied', idempotency_key = %s, applied_effect = %s
               WHERE resolution_id = %s""",
            (key, json.dumps(effect), resolution_id),
        )
        _audit(cur, actor, "applied", resolution,
               before={"state": "approved"}, after={"state": "applied", **effect}, digest=digest)

    return {"status": "applied", "resolution_id": resolution_id, "effect": effect}


def reverse(resolution_id: int, actor: str) -> dict:
    """Undo exactly what was applied, and say so in the log."""
    with write_cursor() as cur:
        resolution = _load(cur, resolution_id)
        if resolution["state"] != "applied":
            return {"status": "refused", "resolution_id": resolution_id,
                    "message": f"only an applied resolution can be reversed (state: {resolution['state']})"}

        effect = resolution["applied_effect"] or {}
        if effect.get("match_id"):
            cur.execute("DELETE FROM matches WHERE match_id = %s", (effect["match_id"],))
        if effect.get("closed_exceptions"):
            cur.execute(
                "UPDATE exceptions SET status = 'open' WHERE exception_id = ANY(%s)",
                (effect["closed_exceptions"],),
            )

        cur.execute("UPDATE resolutions SET state = 'reversed' WHERE resolution_id = %s", (resolution_id,))
        _audit(cur, actor, "reversed", resolution,
               before={"state": "applied", **effect}, after={"state": "reversed"})

    return {"status": "reversed", "resolution_id": resolution_id, "undid": effect}
