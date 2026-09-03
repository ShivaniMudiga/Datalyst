"""Phase 2 self-check: DataSource, snapshot, purpose threading, suggestions.

    backend/.venv/bin/python test_phase2.py
"""

import re
from pathlib import Path

from fastapi.testclient import TestClient

import api
from test_support import sign_in
from src.datasource.postgres import PostgresDataSource
from src.db.chat_store import ConnectionStore
from src.db.connection import close_all
from src.graph.nodes import reset_prompt_cache, system_prompt
from src.knowledge.questions import _from_snapshot
from src.knowledge.snapshot import column_index, describe

USER_ID, TOKEN = sign_in()
client = TestClient(api.app, headers={"Authorization": f"Bearer {TOKEN}"})
PURPOSE = "You are an operations analyst. Track throughput and flag bottlenecks."


def test_introspection():
    snapshot = PostgresDataSource().introspect()
    tables = {table["name"]: table for table in snapshot["tables"]}

    assert "employees" in tables, sorted(tables)
    employees = tables["employees"]
    assert employees["row_count"] > 0
    assert any(c["name"] == "employee_id" and c["primary_key"] for c in employees["columns"])
    assert any(
        fk["column"] == "department_id" and fk["references_table"] == "departments"
        for fk in employees["foreign_keys"]
    ), employees["foreign_keys"]

    totals = snapshot["totals"]
    assert totals["tables"] == len(snapshot["tables"])
    assert totals["relationships"] == len(snapshot["relationships"])
    assert totals["columns"] == sum(len(t["columns"]) for t in snapshot["tables"])

    # The shape the semantic validator needs comes straight off the snapshot,
    # so validation never re-reads information_schema.
    index = column_index(snapshot)
    assert index["employees"]["salary"]["data_type"]
    assert "employees.department_id -> departments.department_id" in describe(snapshot)


def test_setup_flow():
    bad = client.post("/connection/test", json={
        "host": "localhost", "port": "5432", "database": "no_such_database",
        "username": "apple", "password": "",
    }).json()
    assert bad["ok"] is False and bad["message"], bad

    good = {"host": "localhost", "port": "5432", "database": "talk_to_my_data_v2",
            "username": "apple", "password": "", "purpose": PURPOSE}
    assert client.post("/connection/test", json=good).json()["ok"] is True

    saved = client.post("/connection", json=good)
    assert saved.status_code == 201, saved.text
    assert "password" not in saved.json(), "the password must never leave the server"
    assert saved.json()["purpose"] == PURPOSE

    assert client.get("/connection").json()["connection"]["database"] == "talk_to_my_data_v2"


def test_analyse_streams_real_counts():
    with client.stream("POST", "/schema/analyse") as response:
        events = [
            line[6:] for line in response.iter_lines() if line.startswith("data: ")
        ]

    import json
    parsed = [json.loads(event) for event in events]
    steps = [event for event in parsed if event["event"] == "step"]
    done = [event for event in parsed if event["event"] == "done"]

    assert len(steps) == 5, [s["key"] for s in steps]
    assert done, parsed[-1]

    snapshot = done[0]["snapshot"]
    tables = next(s for s in steps if s["key"] == "tables")
    assert tables["result"] == f"{snapshot['totals']['tables']} found"

    stored = client.get("/schema").json()
    assert stored["totals"] == snapshot["totals"]


def test_purpose_reaches_every_turn():
    reset_prompt_cache()
    prompt = system_prompt()
    assert PURPOSE in prompt, "the purpose is not in the system prompt"
    assert "employees" in prompt, "the schema is not in the system prompt"

    client.patch("/connection/purpose", json={"purpose": "Something else entirely."})
    assert "Something else entirely." in system_prompt()

    client.patch("/connection/purpose", json={"purpose": PURPOSE})


def test_suggested_questions():
    body = client.get("/questions").json()["questions"]
    assert len(body) == 4, body
    assert all(0 < len(question) < 120 for question in body), body

    # The offline fallback must still produce questions about *this* database.
    fallback = _from_snapshot(client.get("/schema").json())
    assert len(fallback) == 4, fallback
    assert any("employees" in question for question in fallback), fallback


def test_no_domain_words_in_the_product():
    """Rule 1: only the schema and the purpose know the domain.

    Any domain noun hard-coded into source or interface strings would survive a
    swap to a hospital's database and read as nonsense. This is that check.
    """
    banned = re.compile(
        r"\b(student|students|merchant|merchants|patient|patients|hospital|"
        r"college|university|invoice|invoices|shipment|shipments)\b",
        re.IGNORECASE,
    )
    roots = [Path("src"), Path("../frontend/src")]
    offenders = []

    for root in roots:
        for path in root.rglob("*"):
            if path.suffix not in {".py", ".ts", ".tsx", ".css"}:
                continue
            for number, line in enumerate(path.read_text().splitlines(), start=1):
                if banned.search(line):
                    offenders.append(f"{path}:{number}: {line.strip()}")

    assert not offenders, "domain words in the product:\n" + "\n".join(offenders)


# Ordered, not alphabetical: nothing can be read until a database is connected.
TESTS = (
    test_setup_flow,
    test_introspection,
    test_analyse_streams_real_counts,
    test_purpose_reaches_every_turn,
    test_suggested_questions,
    test_no_domain_words_in_the_product,
)

if __name__ == "__main__":
    ConnectionStore()
    for test in TESTS:
        test()
        print(f"ok  {test.__name__}")
    close_all()
    print("\nall checks passed")
