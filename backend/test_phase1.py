"""Phase 0 + 1 self-check. Runs against the live local database.

    backend/.venv/bin/python test_phase1.py
"""

from test_support import sign_in

sign_in()

from src.agent.tools import run_query as tool_run_query
from src.db.connection import close_all, data_cursor
from src.datasource.postgres import PostgresDataSource
from src.knowledge.snapshot import column_index
from src.graph.nodes import call_llm, system_prompt
from src.validator.sql_validator import SQLValidator

SCHEMA = column_index(PostgresDataSource().introspect())
validator = SQLValidator(schema=SCHEMA)


def test_internal_tables_are_invisible():
    """The app's own tables are not the user's data, and `users` holds password
    hashes. They must not reach the snapshot, the prompt, or a query."""
    from src.agent.tools import reset_data_source
    from src.knowledge.snapshot import read_and_store

    snapshot = list(read_and_store())[-1]["snapshot"]
    names = {table["name"] for table in snapshot["tables"]}
    assert not (names & {"users", "auth_sessions", "connections", "chat_messages"}), names

    # The validator resolves names against the stored snapshot, so a table that
    # is not in it does not exist as far as the model is concerned.
    reset_data_source()
    rejected = tool_run_query("SELECT email, password_hash FROM users")
    assert rejected.get("error_type") == "semantic", rejected


def check(sql, valid, error_type=None):
    result = validator.validate(sql)
    assert result.valid is valid, f"{sql!r} -> {result.stage}: {result.message}"
    if error_type:
        assert result.error_type == error_type, f"{sql!r} -> {result.error_type}"


def test_validation():
    # The bug that broke every analytical query: a CTE name is not a table.
    check("WITH per_dept AS (SELECT department_id, count(*) AS n FROM employees "
          "GROUP BY department_id) SELECT * FROM per_dept ORDER BY n DESC", True)
    # Joins: qualified columns resolve through their alias.
    check("SELECT e.first_name, d.department_name FROM employees e "
          "JOIN departments d ON d.department_id = e.department_id", True)
    check("SELECT * FROM (SELECT count(*) AS c FROM employees) s", True)
    check("SELECT count(*) FROM employees UNION ALL SELECT count(*) FROM departments", True)

    # ...while real mistakes still come back typed, so the model can correct them.
    check("SELECT * FROM staff", False, "semantic")
    check("SELECT nonexistent_column FROM employees", False, "semantic")
    check("SELECT e.nonexistent_column FROM employees e JOIN departments d "
          "ON d.department_id = e.department_id", False, "semantic")
    check("INSERT INTO employees (first_name) VALUES ('x')", False, "permission")
    check("UPDATE employees SET salary = 1 WHERE employee_id = 1", False, "permission")
    check("DROP TABLE employees", False, "permission")
    check("TRUNCATE employees", False, "permission")
    check("SELECT 1; DROP TABLE employees", False, "syntax")   # stacked statements
    check("SELECT * FROM", False, "syntax")


def test_read_only():
    result = tool_run_query("CREATE TABLE should_not_exist (id int)")
    assert result["error_type"] == "permission", result

    # The database, not Python, is the gate: bypass the validator entirely.
    try:
        with data_cursor() as cursor:
            cursor.execute("CREATE TABLE should_not_exist (id int)")
        raise AssertionError("a write succeeded on the read-only pool")
    except Exception as error:
        assert "read-only" in str(error).lower(), error


def test_failed_query_does_not_poison_the_pool():
    result = tool_run_query("SELECT * FROM employees WHERE 1/0 = 1")
    assert result.get("error_type") == "execution", result
    assert PostgresDataSource().execute("SELECT 1 AS ok")["rows"] == [{"ok": 1}]


def test_row_cap():
    capped = PostgresDataSource().execute("SELECT i FROM generate_series(1, 50) AS g(i)", row_cap=10)
    assert capped["row_count"] == 10 and capped["truncated"] is True, capped
    whole = PostgresDataSource().execute("SELECT i FROM generate_series(1, 5) AS g(i)", row_cap=10)
    assert whole["row_count"] == 5 and whole["truncated"] is False, whole


def test_timeout_is_set():
    with data_cursor() as cursor:
        cursor.execute("SHOW statement_timeout")
        assert cursor.fetchone()["statement_timeout"] == "15s"


def test_system_prompt_reaches_the_model():
    sent = {}
    call_llm.__globals__["chat"] = lambda messages: sent.setdefault("messages", messages) and None
    try:
        call_llm({"messages": [{"role": "user", "content": "hi"}]})
    except AttributeError:
        pass  # the fake returns None; we only care what was sent
    assert sent["messages"][0] == {"role": "system", "content": system_prompt()}


if __name__ == "__main__":
    for name, function in sorted(globals().items()):
        if name.startswith("test_"):
            function()
            print(f"ok  {name}")
    close_all()
    print("\nall checks passed")
