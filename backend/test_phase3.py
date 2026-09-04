"""Phase 3 self-check: the step budget and the streamed trace.

    backend/.venv/bin/python test_phase3.py

The model and the tools are faked - what is under test is the loop, not the
model. Needs the app database, for the checkpointer.
"""

import json
import uuid

from test_support import sign_in

USER_ID, TOKEN = sign_in()

from src.agent import tools as agent_tools
from src.agent.agent import ConversationalAgent
from src.db.connection import close_all
from src.graph import nodes

nodes.system_prompt = lambda: "test"

QUERY = json.dumps({"sql": "SELECT 1"})


def tool_call(index):
    return {
        "id": f"c{index}",
        "type": "function",
        "function": {"name": "run_query", "arguments": QUERY},
    }


def run(fake_chat, fake_run_query):
    """Drive one turn against a faked model and a faked tool."""
    nodes.chat = fake_chat
    agent_tools.FUNCTION_MAP["run_query"] = fake_run_query
    return list(ConversationalAgent(str(uuid.uuid4())).stream("a question"))


def steps(events):
    return [event for event in events if event["event"] == "step"]


def test_step_budget_stops_the_loop():
    """A model that never stops calling tools still has to produce an answer."""
    calls = {"n": 0}

    def fake_chat(messages, tools=True):
        if not tools:  # out of budget: no tools offered, so it must answer
            return {"content": "Here is what I found.", "tool_calls": None}
        calls["n"] += 1
        return {"content": "", "tool_calls": [tool_call(calls["n"])]}

    events = run(fake_chat, lambda sql: {"rows": [], "row_count": 0, "truncated": False})
    done = events[-1]

    assert calls["n"] == nodes.STEP_BUDGET, calls
    assert done["event"] == "done", done
    assert done["response"] == "Here is what I found.", done


def test_budget_is_per_question():
    """The checkpointer keeps earlier turns; they must not spend this turn."""
    history = [{"role": "user", "content": "first"}]
    history += [{"role": "assistant", "tool_calls": [tool_call(i)]} for i in range(20)]
    assert nodes._steps_spent(history) == 20

    history.append({"role": "user", "content": "second"})
    assert nodes._steps_spent(history) == 0


def test_trace_reports_a_correction():
    """A rejected query is a step that failed, then one that worked."""
    replies = iter(
        [
            {"content": "", "tool_calls": [tool_call(1)]},
            {"content": "", "tool_calls": [tool_call(2)]},
            {"content": "Answer.", "tool_calls": None},
        ]
    )
    results = iter(
        [
            {"status": "validation_failed", "error_type": "semantic", "message": "No such column."},
            {"rows": [{"n": 1}], "row_count": 1, "truncated": True},
        ]
    )

    events = run(lambda messages, tools=True: next(replies), lambda sql: next(results))
    trace = steps(events)

    assert [step["status"] for step in trace] == ["running", "failed", "running", "ok"], trace
    assert trace[1]["detail"] == "No such column.", trace[1]
    assert trace[3]["detail"] == "1 rows (capped)", trace[3]
    assert all(step["sql"] == "SELECT 1" for step in trace), trace

    done = events[-1]
    assert done["response"] == "Answer." and done["data"] == [{"n": 1}], done
    assert done["ms"] >= 0, done


def test_the_endpoint_streams_and_persists():
    """The frames the browser actually receives, and what is left in the store."""
    from fastapi.testclient import TestClient

    import api

    nodes.chat = lambda messages, tools=True: next(replies)
    agent_tools.FUNCTION_MAP["run_query"] = lambda sql: {
        "rows": [{"n": 1}], "row_count": 1, "truncated": False
    }
    replies = iter(
        [
            {"content": "", "tool_calls": [tool_call(1)]},
            {"content": "One row.", "tool_calls": None},
        ]
    )

    client = TestClient(api.app, headers={"Authorization": f"Bearer {TOKEN}"})
    with client.stream("POST", "/chat/stream", json={"message": "how many?"}) as response:
        assert response.status_code == 200, response.status_code
        frames = [
            json.loads(line.removeprefix("data: "))
            for line in response.iter_lines()
            if line.startswith("data: ")
        ]

    assert [frame["event"] for frame in frames] == ["start", "step", "step", "done"], frames
    chat_id = frames[0]["chat_id"]

    stored = client.get(f"/chats/{chat_id}/messages").json()
    assert [message["role"] for message in stored] == ["user", "assistant"], stored
    assert stored[0]["content"] == "how many?" and stored[1]["content"] == "One row."
    assert stored[1]["sql"] == "SELECT 1" and stored[1]["data"] == [{"n": 1}]
    # The first question names the conversation.
    assert any(chat["id"] == chat_id and chat["title"] == "how many?" for chat in client.get("/chats").json())


if __name__ == "__main__":
    for name, test in sorted(globals().items()):
        if name.startswith("test_"):
            test()
            print("ok ", name)
    print("\nall checks passed")
    close_all()
