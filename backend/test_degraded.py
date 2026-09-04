"""R5 self-check: what happens when things go wrong.

Every assertion here is a failure that actually happened, or one that would cost
money if it did. The model is faked wherever the point is the loop rather than
the model - including the injection test, which does not ask whether the model
resists an instruction hidden in the data. It assumes the model obeys, and
asserts that obeying achieves nothing.

  python test_degraded.py
"""

import csv
import json
import os
import time
from pathlib import Path

import psycopg

from packs.recon import agent as recon_agent
from packs.recon.db import DSN, cursor
from packs.recon.ingest import ingest
from src.llm import zen_client

PAYOUTS = Path(__file__).resolve().parents[1] / "payouts"
SCRATCH = Path(os.environ.get("TMPDIR", "/tmp")) / "recon-degraded"


class FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class FakeCall:
    def __init__(self, name, arguments, call_id="c1"):
        self.id = call_id
        self.function = type("F", (), {"name": name, "arguments": arguments})()


def scripted(*messages):
    """A model that says exactly these things, in order, then gives up."""
    remaining = list(messages)

    def chat(_messages, tools=None):
        return remaining.pop(0) if remaining else FakeMessage(content="done")

    return chat


def run_agent(chat, exception):
    original = recon_agent.chat
    recon_agent.chat = chat
    try:
        source, validator = recon_agent.reader()
        return recon_agent.work(exception, source, validator)
    finally:
        recon_agent.chat = original


def an_exception():
    with cursor() as cur:
        cur.execute("""
            SELECT e.exception_id, e.amount_minor, l.settled_at, l.narration, b.gateway
            FROM exceptions e
            JOIN settlement_lines l ON l.line_id = e.line_id
            JOIN settlement_batches b ON b.payout_id = l.payout_id
            WHERE e.reason_code = 'no_reference' LIMIT 1""")
        return cur.fetchone()


# -- the loop survives a model that misbehaves -------------------------------

def test_malformed_tool_arguments():
    result = run_agent(scripted(
        FakeMessage(tool_calls=[FakeCall("query", "{not json at all")]),
        FakeMessage(content="I could not proceed."),
    ), an_exception())
    assert result["status"] == "gave_up", result


def test_unknown_tool_name():
    result = run_agent(scripted(
        FakeMessage(tool_calls=[FakeCall("delete_everything", "{}")]),
        FakeMessage(content="No such tool."),
    ), an_exception())
    assert result["status"] == "gave_up", result


def test_prose_where_a_tool_call_was_required():
    result = run_agent(scripted(FakeMessage(content="I think it is order 42.")), an_exception())
    assert result["status"] == "gave_up", result


def test_a_model_that_never_stops_is_stopped():
    turn = FakeMessage(tool_calls=[FakeCall("query", json.dumps({"sql": "SELECT 1"}))])
    result = run_agent(lambda *_, **__: turn, an_exception())
    assert result["status"] == "out_of_steps", result


# -- the gateway ------------------------------------------------------------

def _status_error(code):
    from openai import APIStatusError

    class Response:
        status_code = code
        headers = {}
        request = None

        def json(self):
            return {}

    return APIStatusError("upstream", response=Response(), body=None)


def test_a_transient_upstream_failure_is_retried():
    """The failure that ended a whole 37-exception run before it was fixed."""
    attempts = []

    def flaky():
        attempts.append(time.monotonic())
        if len(attempts) < 3:
            raise _status_error(503)
        return "recovered"

    os.environ["LLM_RETRIES"] = "4"
    zen_client.RETRIES = 4
    assert zen_client._with_retry(flaky) == "recovered"
    assert len(attempts) == 3, attempts


def test_our_own_bad_request_is_not_retried_into_a_wall():
    attempts = []

    def broken():
        attempts.append(1)
        raise _status_error(400)

    try:
        zen_client._with_retry(broken)
    except Exception:
        pass
    assert len(attempts) == 1, f"a 400 was retried {len(attempts)} times"


# -- the database -----------------------------------------------------------

def test_a_slow_query_is_killed_and_the_pool_survives():
    source, _ = recon_agent.reader()
    try:
        source.execute("SELECT pg_sleep(30)")
        raise AssertionError("a 30 second query was allowed to finish")
    except AssertionError:
        raise
    except Exception as error:
        assert "statement timeout" in str(error).lower(), error
    # The next query must still work: a failed statement cannot poison the pool.
    assert source.execute("SELECT 1 AS ok")["rows"][0]["ok"] == 1


# -- the files --------------------------------------------------------------

def test_a_replayed_file_changes_nothing():
    name = next(PAYOUTS.glob("*.csv"))
    with cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM settlement_lines")
        before = cur.fetchone()["n"]
    result = ingest(name)
    assert not result["ingested"], result
    with cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM settlement_lines")
        assert cur.fetchone()["n"] == before, "a replay changed the line count"


def test_a_truncated_or_malformed_file_is_refused():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    source = next(PAYOUTS.glob("*.csv"))
    rows = source.read_text().splitlines()

    header_only = SCRATCH / "header-only.csv"
    header_only.write_text(rows[0] + "\n")
    try:
        ingest(header_only)
        raise AssertionError("a file with no lines was accepted")
    except ValueError as error:
        assert "no lines" in str(error), error

    missing_column = SCRATCH / "missing-column.csv"
    columns = rows[0].split(",")
    keep = [index for index, name in enumerate(columns) if name != "net_minor"]
    with missing_column.open("w", newline="") as handle:
        writer = csv.writer(handle)
        for line in rows[:20]:
            cells = next(csv.reader([line]))
            writer.writerow([cells[index] for index in keep])
    try:
        ingest(missing_column)
        raise AssertionError("a file missing a money column was accepted")
    except ValueError as error:
        assert "net_minor" in str(error), error


# -- the matcher ------------------------------------------------------------

def test_a_payout_dated_before_its_capture_never_matches():
    """Clock skew, or a mislabelled file. Money cannot settle before it is taken."""
    from packs.recon.match import run

    with cursor(commit=True) as cur:
        cur.execute("""SELECT p.payment_id, p.gateway_reference, p.captured_at,
                              round(p.amount*100) AS gross, round(p.gateway_fee*100) AS fee
                       FROM payments p
                       WHERE p.gateway_reference IS NOT NULL AND p.payment_status = 'captured'
                         AND NOT EXISTS (SELECT 1 FROM matches m WHERE m.payment_id = p.payment_id)
                       LIMIT 1""")
        payment = cur.fetchone()
        assert payment, "no unmatched capture to build the case from"

        cur.execute("""INSERT INTO settlement_batches
            (payout_id, gateway, payout_date, currency, file_name, file_hash, line_count, net_total_minor)
            VALUES ('skew-probe', 'razorpay', current_date, 'INR', 'skew-probe', 'skew-probe', 1, 0)
            ON CONFLICT (payout_id) DO NOTHING""")
        cur.execute("""INSERT INTO settlement_lines
            (payout_id, line_seq, settled_at, gateway_reference, currency,
             gross_minor, fee_minor, net_minor, narration)
            VALUES ('skew-probe', 1, %s, %s, 'INR', %s, %s, %s, 'clock skew probe')
            RETURNING line_id""",
            (payment["captured_at"] - __import__("datetime").timedelta(days=1),
             payment["gateway_reference"], payment["gross"], payment["fee"],
             payment["gross"] - payment["fee"]))
        line_id = cur.fetchone()["line_id"]

    try:
        run(reset=False)
        with cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM matches WHERE line_id = %s", (line_id,))
            assert cur.fetchone()["n"] == 0, \
                "a payout dated before its capture was matched"
    finally:
        with cursor(commit=True) as cur:
            cur.execute("DELETE FROM settlement_batches WHERE payout_id = 'skew-probe'")


def test_currencies_are_never_compared():
    with cursor() as cur:
        cur.execute("""SELECT count(*) AS n FROM matches m
                       JOIN settlement_lines l ON l.line_id = m.line_id
                       WHERE l.currency <> 'INR' AND m.match_tier IN ('T0','T1','T1b','T2')""")
        assert cur.fetchone()["n"] == 0, "a foreign-currency line matched on an exact-amount tier"


# -- instructions hidden in the data ----------------------------------------

def test_an_instruction_in_the_data_achieves_nothing_even_if_obeyed():
    """The question is not whether the model resists. Assume it does not.

    A row value is text from the outside world, and it reaches the model's
    context. So the test hands the model the worst case - it *obeys* the
    injected instruction and emits the destructive statement - and asserts that
    obeying gets it nowhere: the validator refuses the statement, and the role
    it would run as could not execute it either.
    """
    injection = "'; DROP TABLE users; --"
    obedient = scripted(
        FakeMessage(tool_calls=[FakeCall("query", json.dumps({"sql": "DROP TABLE users"}))]),
        FakeMessage(tool_calls=[FakeCall("query", json.dumps({"sql": f"SELECT 1{injection}"}))]),
        FakeMessage(content="I could not do that."),
    )
    result = run_agent(obedient, an_exception())
    assert result["status"] == "gave_up", result

    source, validator = recon_agent.reader()
    for statement in ("DROP TABLE users", "DELETE FROM payments",
                      "UPDATE payments SET amount = 0", "SELECT 1; DROP TABLE users"):
        assert not validator.validate(statement).valid, f"the validator allowed: {statement}"

    # And the gate below it: the role the model reads as cannot write at all.
    reader_dsn = os.getenv("RECON_READER_DSN",
                           "postgresql://data_runtime_reader:change_me@localhost:5432/kartly")
    with psycopg.connect(reader_dsn) as connection:
        try:
            connection.execute("CREATE TABLE injected (x int)")
            raise AssertionError("the reader role created a table")
        except psycopg.errors.ReadOnlySqlTransaction:
            connection.rollback()

    # And the only write the model has is a closed enum it cannot widen.
    from packs.recon.propose import propose_resolution
    refused = propose_resolution(an_exception()["exception_id"], "drop_everything",
                                 "an instruction found in a row said to", 1.0)
    assert refused["status"] == "rejected", refused


def main() -> None:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"  ok  {test.__name__.replace('test_', '').replace('_', ' ')}")
    print(f"{len(tests)} degraded paths held")

    # The read-only pool is a background thread pool; without this every run
    # ends in four "couldn't stop thread" warnings that look like a fault.
    from src.db.connection import close_all
    close_all()


if __name__ == "__main__":
    main()
