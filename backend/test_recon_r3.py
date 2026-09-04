"""R3 self-check: the gate.

The agent's proposals are only interesting if they cannot become actions on
their own. Everything here tries to get a change into the ledger without a
person, and asserts that it fails - and then checks that the one legitimate
route is idempotent, verified, audited and reversible.

  python test_recon_r3.py
"""

import os
from pathlib import Path

import psycopg

from packs.recon.db import DSN, cursor
from packs.recon.propose import propose_resolution

os.environ.setdefault("RECON_WRITE_DSN", DSN)

from packs.recon import commit  # noqa: E402  - after the DSN is in place

ACTOR = "selfcheck@datalyst.test"


def one(cur, sql, params=()):
    cur.execute(sql, params)
    row = cur.fetchone()
    return row["value"] if row else None


def counts(cur) -> tuple[int, int]:
    return (one(cur, "SELECT count(*) AS value FROM matches"),
            one(cur, "SELECT count(*) AS value FROM exceptions WHERE status = 'open'"))


def raises(action, fragment: str) -> None:
    try:
        action()
    except Exception as error:
        assert fragment in str(error), f"expected {fragment!r}, got {error}"
        return
    raise AssertionError(f"expected a failure mentioning {fragment!r}")


def main() -> None:
    # 1. There is no path from the agent to the committer. Not a policy, a fact
    #    about the import graph and the tool list it is given.
    agent_source = (Path(__file__).parent / "packs/recon/agent.py").read_text()
    assert "commit" not in agent_source.replace("`commit.py`", "").replace("commit.py", ""), \
        "the agent module references the committer"
    from packs.recon.agent import TOOLS as AGENT_TOOLS
    offered = {tool["function"]["name"] for tool in AGENT_TOOLS}
    assert offered == {"query", "propose_resolution"}, f"the agent was handed {offered}"

    # 2. Applying needs credentials a proposing process does not have.
    saved = os.environ.pop("RECON_WRITE_DSN")
    raises(lambda: commit.apply(1, ACTOR), "may read and propose, not apply")
    os.environ["RECON_WRITE_DSN"] = saved

    with cursor() as cur:
        target = cur.execute("""
            SELECT e.exception_id, b.payment_id
            FROM exceptions e
            JOIN settlement_lines l ON l.line_id = e.line_id
            JOIN recon_labels b ON b.payout_id = l.payout_id AND b.line_seq = l.line_seq
            WHERE e.status = 'open' AND e.reason_code = 'no_reference'
              AND b.payment_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM matches m WHERE m.payment_id = b.payment_id)
              AND NOT EXISTS (SELECT 1 FROM resolutions r WHERE r.exception_id = e.exception_id
                              AND r.state IN ('proposed','approved','applied'))
            LIMIT 1""").fetchone()
        assert target, "no free exception to test the gate with"
        before = counts(cur)

    # 3. Proposing changes nothing but the proposals table.
    proposal = propose_resolution(
        target["exception_id"], "link", "self-check: linking a known counterpart",
        0.9, [target["payment_id"]],
    )
    assert proposal["status"] == "proposed", proposal
    resolution_id = proposal["resolution_id"]
    with cursor() as cur:
        assert counts(cur) == before, "proposing changed the ledger"

    # 4. A proposal cannot apply itself.
    refused = commit.apply(resolution_id, ACTOR)
    assert refused["status"] == "refused" and "approved" in refused["message"], refused

    # 5. The state machine is in the database, so code that forgets it still obeys.
    with psycopg.connect(DSN) as connection:
        raises(lambda: connection.execute(
            "UPDATE resolutions SET state = 'applied' WHERE resolution_id = %s", (resolution_id,)),
            "illegal resolution transition")
        connection.rollback()
        raises(lambda: connection.execute(
            "UPDATE resolutions SET state = 'approved' WHERE resolution_id = %s", (resolution_id,)),
            "a decision needs a decider")
        connection.rollback()

    # 6. A person approves, by name.
    assert commit.decide(resolution_id, ACTOR, accept=True)["status"] == "approved"

    # 7. Evidence is re-checked at apply time, not trusted from proposal time.
    with cursor(commit=True) as cur:
        cur.execute("""UPDATE settlement_lines SET narration = narration || ' [moved]'
                       WHERE line_id = (SELECT line_id FROM exceptions WHERE exception_id = %s)""",
                    (target["exception_id"],))
    stale = commit.apply(resolution_id, ACTOR)
    assert stale["status"] == "refused" and "evidence changed" in stale["message"], stale
    with cursor(commit=True) as cur:
        cur.execute("""UPDATE settlement_lines SET narration = replace(narration, ' [moved]', '')
                       WHERE line_id = (SELECT line_id FROM exceptions WHERE exception_id = %s)""",
                    (target["exception_id"],))

    # 8. The one legitimate route, and it is idempotent.
    applied = commit.apply(resolution_id, ACTOR)
    assert applied["status"] == "applied", applied
    with cursor() as cur:
        after = counts(cur)
        assert after[0] == before[0] + 1, "applying did not record exactly one match"
        assert after[1] < before[1], "applying closed no exception"

    again = commit.apply(resolution_id, ACTOR)
    assert again["status"] == "already_applied", again
    with cursor() as cur:
        assert counts(cur) == after, "applying twice changed the ledger twice"

    # 9. Reversible, exactly.
    reversed_result = commit.reverse(resolution_id, ACTOR)
    assert reversed_result["status"] == "reversed", reversed_result
    with cursor() as cur:
        assert counts(cur) == before, "reversing did not restore the ledger"
    assert commit.reverse(resolution_id, ACTOR)["status"] == "refused", "reversed twice"

    # 10. Every step left a trail, and the trail cannot be edited away.
    with cursor() as cur:
        cur.execute("SELECT action FROM audit_log WHERE resolution_id = %s ORDER BY audit_id",
                    (resolution_id,))
        trail = [row["action"] for row in cur.fetchall()]
    assert trail == ["proposed", "approved", "refused_stale_evidence", "applied", "reversed"], trail

    with psycopg.connect(DSN) as connection:
        for statement in ("UPDATE audit_log SET actor = 'someone else'",
                          "DELETE FROM audit_log", "TRUNCATE audit_log"):
            raises(lambda s=statement: connection.execute(s), "append-only")
            connection.rollback()

    # 11. The role the model reads with cannot write a proposal, let alone a match.
    reader = os.getenv("RECON_READER_DSN",
                       "postgresql://data_runtime_reader:change_me@localhost:5432/kartly")
    with psycopg.connect(reader) as connection:
        for statement in ("INSERT INTO resolutions (exception_id, kind, confidence, reason, "
                          "evidence_sql, evidence_hash) VALUES (1,'link',1,'x','x','x')",
                          "INSERT INTO matches (line_id, payment_id, match_tier, confidence) "
                          "VALUES (1, 1, 'AGENT', 1)"):
            raises(lambda s=statement: connection.execute(s), "read-only transaction")
            connection.rollback()

    print(f"ok - proposal {resolution_id}: proposed, refused, approved, refused again on stale "
          f"evidence, applied once, applied twice with no second effect, reversed")
    print("ok - the agent holds no route to the committer, and the log cannot be edited, "
          "deleted or truncated")


if __name__ == "__main__":
    main()
