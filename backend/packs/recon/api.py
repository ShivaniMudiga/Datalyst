"""HTTP for the reconciliation pack.

Mounted by the runtime's generic pack loader, which finds this module without
knowing what it is for. Everything domain-specific stops at this file.

Every write goes through `commit.py`. This router does not touch `matches`,
`exceptions` or `resolutions` itself - it only asks a person's identity of the
runtime's session and hands it to the committer, so the audit log records who,
not "the API".
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from packs.recon import commit
from packs.recon.db import cursor

router = APIRouter(tags=["reconciliation"])

SUMMARY = """
SELECT (SELECT count(*) FROM settlement_lines)                              AS lines,
       (SELECT count(*) FROM matches WHERE matched_by = 'rule')             AS by_rule,
       (SELECT count(*) FROM matches WHERE matched_by = 'agent')            AS by_agent,
       (SELECT count(*) FROM exceptions WHERE status = 'open')              AS open_exceptions,
       (SELECT coalesce(sum(net_minor), 0)::bigint FROM settlement_lines)   AS settled_minor,
       (SELECT coalesce(sum(amount_minor), 0)::bigint FROM exceptions
        WHERE status = 'open')                                              AS at_risk_minor,
       (SELECT count(*) FROM resolutions WHERE state = 'proposed')          AS awaiting_review
"""

QUEUE = """
SELECT e.exception_id, e.reason_code, e.amount_minor, e.status,
       l.line_id, l.settled_at, l.narration, l.currency,
       b.gateway, b.payout_id,
       r.resolution_id, r.kind, r.target_ids, r.confidence, r.reason,
       r.state AS resolution_state, r.steps, r.corrections, r.latency_ms, r.evidence_sql
FROM exceptions e
LEFT JOIN settlement_lines l   ON l.line_id = e.line_id
LEFT JOIN settlement_batches b ON b.payout_id = l.payout_id
LEFT JOIN LATERAL (
  SELECT * FROM resolutions r
  WHERE r.exception_id = e.exception_id AND r.state <> 'rejected'
  ORDER BY r.resolution_id DESC LIMIT 1
) r ON TRUE
WHERE (%(status)s = 'all' OR e.status = %(status)s)
  AND (%(reason)s = 'all' OR e.reason_code = %(reason)s)
ORDER BY e.amount_minor DESC
LIMIT %(limit)s
"""

AUDIT = """
SELECT audit_id, actor, action, resolution_id, exception_id, after_state, at
FROM audit_log ORDER BY audit_id DESC LIMIT %s
"""


class Decision(BaseModel):
    accept: bool
    note: str = ""


def _actor(user) -> str:
    """Who the audit log will name. A person, never 'the API'."""
    return getattr(user, "email", None) or str(getattr(user, "id", "unknown"))


def build(signed_in) -> APIRouter:
    """The runtime hands in its own auth dependency; the pack does not invent one."""

    @router.get("/summary")
    def summary(user=Depends(signed_in)) -> dict:
        with cursor() as cur:
            cur.execute(SUMMARY)
            row = cur.fetchone()
        matched = row["by_rule"] + row["by_agent"]
        return {**row, "matched": matched,
                "match_rate": matched / row["lines"] if row["lines"] else 0}

    @router.get("/exceptions")
    def queue(status: str = "open", reason: str = "all", limit: int = 200,
              user=Depends(signed_in)) -> list[dict]:
        with cursor() as cur:
            cur.execute(QUEUE, {"status": status, "reason": reason, "limit": min(limit, 500)})
            return cur.fetchall()

    @router.post("/resolutions/{resolution_id}/decide")
    def decide(resolution_id: int, decision: Decision, user=Depends(signed_in)) -> dict:
        try:
            return commit.decide(resolution_id, _actor(user), decision.accept, decision.note)
        except LookupError as error:
            raise HTTPException(404, str(error)) from error
        except PermissionError as error:
            raise HTTPException(403, str(error)) from error

    @router.post("/resolutions/{resolution_id}/apply")
    def apply(resolution_id: int, user=Depends(signed_in)) -> dict:
        try:
            return commit.apply(resolution_id, _actor(user))
        except LookupError as error:
            raise HTTPException(404, str(error)) from error
        except PermissionError as error:
            # Not a server fault: this deployment is not configured to act.
            raise HTTPException(403, str(error)) from error

    @router.post("/resolutions/{resolution_id}/reverse")
    def reverse(resolution_id: int, user=Depends(signed_in)) -> dict:
        try:
            return commit.reverse(resolution_id, _actor(user))
        except LookupError as error:
            raise HTTPException(404, str(error)) from error
        except PermissionError as error:
            raise HTTPException(403, str(error)) from error

    @router.get("/audit")
    def audit(limit: int = 100, user=Depends(signed_in)) -> list[dict]:
        with cursor() as cur:
            cur.execute(AUDIT, (min(limit, 500),))
            return cur.fetchall()

    return router
