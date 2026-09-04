"""The one action the agent has, and the only row it can ever write.

A proposal is not a decision. It records what the agent thinks, what it read to
think it, and how sure it is - and then stops. Nothing in this module touches
the ledger, closes an exception or creates a match; `commit.py` does that, and
the model cannot call it.

The evidence is not taken from the model. It is recomputed here from the
database, in a canonical query stored alongside the proposal, and hashed. At
apply time it is recomputed again and re-hashed: if the ledger moved underneath
the proposal, applying it is refused rather than applied to a world that no
longer exists.
"""

from __future__ import annotations

import json
from hashlib import sha256

from packs.recon.db import cursor

KINDS = ("link", "write_off", "escalate")

# What the proposal rests on: the disputed line, and every payment it names.
EVIDENCE = """
SELECT 'line' AS side, l.line_id::text AS id, l.gross_minor::text AS amount,
       l.settled_at::text AS at, coalesce(l.narration, '') AS detail
FROM exceptions e JOIN settlement_lines l ON l.line_id = e.line_id
WHERE e.exception_id = {exception_id}
UNION ALL
SELECT 'payment', p.payment_id::text, round(p.amount * 100)::text,
       p.captured_at::text, p.order_id::text
FROM payments p WHERE p.payment_id = ANY(ARRAY[{targets}]::int[])
ORDER BY 1, 2
"""


def evidence_for(exception_id: int, target_ids: list[int]) -> tuple[str, str, list]:
    statement = EVIDENCE.format(
        exception_id=int(exception_id),
        targets=", ".join(str(int(target)) for target in target_ids) or "NULL",
    )
    with cursor() as cur:
        cur.execute(statement)
        rows = cur.fetchall()
    digest = sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()
    return statement, digest, rows


def propose_resolution(
    exception_id: int,
    kind: str,
    reason: str,
    confidence: float,
    target_ids: list[int] | None = None,
    _cost: dict | None = None,
) -> dict:
    """Record one proposed resolution for one exception. Applies nothing."""
    targets = [int(target) for target in (target_ids or [])]

    if kind not in KINDS:
        return {"status": "rejected", "message": f"kind must be one of {', '.join(KINDS)}"}
    if not reason or len(reason.strip()) < 10:
        return {"status": "rejected", "message": "reason must say why, in a sentence"}
    if not 0 < float(confidence) <= 1:
        return {"status": "rejected", "message": "confidence must be between 0 and 1"}
    if kind == "link" and len(targets) != 1:
        return {"status": "rejected", "message": "a link names exactly one payment_id"}
    if kind != "link" and targets:
        return {"status": "rejected", "message": f"{kind} takes no target_ids"}

    with cursor() as cur:
        cur.execute(
            "SELECT exception_id, line_id, payment_id, status FROM exceptions WHERE exception_id = %s",
            (exception_id,),
        )
        exception = cur.fetchone()
        if exception is None:
            return {"status": "rejected", "message": f"no exception {exception_id}"}
        if exception["status"] != "open":
            return {"status": "rejected", "message": f"exception {exception_id} is {exception['status']}"}

        if kind == "link":
            if exception["line_id"] is None:
                return {"status": "rejected", "message": "only a settlement line can be linked"}
            cur.execute(
                """SELECT p.payment_id,
                          EXISTS (SELECT 1 FROM matches m WHERE m.payment_id = p.payment_id) AS taken
                   FROM payments p WHERE p.payment_id = %s AND p.payment_status = 'captured'""",
                (targets[0],),
            )
            target = cur.fetchone()
            if target is None:
                return {"status": "rejected", "message": f"payment {targets[0]} is not a captured payment"}
            if target["taken"]:
                return {"status": "rejected", "message": f"payment {targets[0]} is already settled by another line"}

    statement, digest, rows = evidence_for(exception_id, targets)

    with cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO resolutions (exception_id, kind, target_ids, confidence, reason,
                                     evidence_sql, evidence_hash, steps, corrections, latency_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING resolution_id
            """,
            (exception_id, kind, targets, confidence, reason.strip(), statement, digest,
             (_cost or {}).get("steps"), (_cost or {}).get("corrections"),
             (_cost or {}).get("latency_ms")),
        )
        resolution_id = cur.fetchone()["resolution_id"]
        cur.execute(
            """INSERT INTO audit_log (actor, action, resolution_id, exception_id, after_state, evidence_hash)
               VALUES ('agent', 'proposed', %s, %s, %s, %s)""",
            (resolution_id, exception_id, json.dumps({"kind": kind, "targets": targets,
                                                      "confidence": confidence}), digest),
        )

    return {
        "status": "proposed",
        "resolution_id": resolution_id,
        "message": "Recorded. A person decides whether it is applied; you cannot apply it.",
        "evidence_rows": len(rows),
    }


TOOL_DESCRIPTION = (
    "Propose one resolution for one exception, and stop. This records a proposal "
    "for a person to accept or reject - it never applies anything and never moves "
    "money. Use 'link' with exactly one payment_id when you can identify the "
    "counterpart, 'write_off' when the amount is immaterial and unidentifiable, "
    "and 'escalate' when a person must look. Say why in the reason."
)

TOOL_PARAMETERS = {
    "type": "object",
    "properties": {
        "exception_id": {"type": "integer"},
        "kind": {"type": "string", "enum": list(KINDS)},
        "reason": {"type": "string", "description": "One sentence: what you concluded and from what."},
        "confidence": {"type": "number", "description": "0 to 1."},
        "target_ids": {"type": "array", "items": {"type": "integer"},
                       "description": "For 'link': exactly one payment_id."},
    },
    "required": ["exception_id", "kind", "reason", "confidence"],
}
