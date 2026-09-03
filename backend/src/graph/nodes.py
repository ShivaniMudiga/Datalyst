"""Nodes and routing functions for the conversational agent graph."""

import json
import os
from collections.abc import Mapping
from typing import Any, Literal

from src.agent.tools import FUNCTION_MAP
from src.auth import user_id
from src.graph.state import AgentState
from src.llm.zen_client import build_system_prompt, chat


def _field(value: Any, name: str, default: Any = None) -> Any:
    """Read a field from either an SDK object or a JSON-like mapping."""
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _assistant_message(message: Any) -> dict[str, Any]:
    """Convert the OpenAI SDK response into a message accepted by LangGraph."""
    tool_calls = _field(message, "tool_calls") or []
    serialized_calls = []

    for tool_call in tool_calls:
        function = _field(tool_call, "function")
        serialized_calls.append(
            {
                "id": _field(tool_call, "id"),
                "type": _field(tool_call, "type", "function"),
                "function": {
                    "name": _field(function, "name"),
                    "arguments": _field(function, "arguments", "{}"),
                },
            }
        )

    result: dict[str, Any] = {
        "role": "assistant",
        "content": _field(message, "content") or "",
    }
    if serialized_calls:
        result["tool_calls"] = serialized_calls
    return result


# Cached per connection: the prompt carries that database's purpose and
# schema, both of which change when the user switches database.
_prompt_cache: dict[str, str] = {}

NO_SCHEMA = (
    "No schema has been read yet. Tell the user to finish connecting a database "
    "in setup; do not guess at tables."
)


def reset_prompt_cache(connection_id: str | None = None) -> None:
    """Called when a connection's purpose or snapshot changes."""
    from src.agent.tools import active_connection_id

    _prompt_cache.pop(connection_id or active_connection_id(), None)


def system_prompt() -> str:
    """The purpose and the schema, threaded into every turn.

    Cached: it is identical on every turn until the user edits their purpose or
    re-reads the schema, and rebuilding it would hit the database each time.
    """
    from src.agent.tools import active_connection_id

    who = user_id()
    key = active_connection_id()
    if key not in _prompt_cache:
        from src.db.chat_store import ConnectionStore
        from src.knowledge.snapshot import describe, load_snapshot

        from src.agent.tools import data_source

        snapshot = load_snapshot()
        connection = ConnectionStore(who).get()
        source = data_source()
        _prompt_cache[key] = build_system_prompt(
            connection.purpose if connection else None,
            describe(snapshot) if snapshot else NO_SCHEMA,
            engine=source.ENGINE,
            query_guide=source.QUERY_GUIDE,
        )
    return _prompt_cache[key]


STEP_BUDGET = int(os.getenv("AGENT_STEP_BUDGET", "8"))

OUT_OF_STEPS = (
    "You have used the whole step budget for this question. Answer now with what "
    "you already have, and say plainly which part you could not establish."
)


def _steps_spent(history: list[Any]) -> int:
    """Tool-calling turns since the user's last message.

    The checkpointer keeps every earlier turn in the same thread, so counting
    the whole list would spend one conversation's budget on the next question.
    """
    start = 0
    for index, message in enumerate(history):
        if _field(message, "role") == "user":
            start = index
    return sum(1 for message in history[start:] if _field(message, "tool_calls"))


def call_llm(state: AgentState) -> dict[str, list[dict[str, Any]]]:
    """Ask the model what to do next, with the system prompt in front."""
    messages = [{"role": "system", "content": system_prompt()}, *state["messages"]]

    # Out of budget: the same call without tools. The model can only reply in
    # prose, so `should_continue` ends the turn - a confused model cannot spin.
    if _steps_spent(state["messages"]) >= STEP_BUDGET:
        messages.append({"role": "system", "content": OUT_OF_STEPS})
        return {"messages": [_assistant_message(chat(messages, tools=None))]}

    return {"messages": [_assistant_message(chat(messages))]}


def execute_tools(state: AgentState) -> dict[str, list[dict[str, Any]]]:
    """Run every tool requested by the latest assistant message."""
    assistant_message = state["messages"][-1]
    tool_messages: list[dict[str, Any]] = []

    for tool_call in _field(assistant_message, "tool_calls", []) or []:
        function = _field(tool_call, "function")
        tool_name = _field(function, "name")
        raw_arguments = _field(function, "arguments", "{}")

        try:
            arguments = json.loads(raw_arguments)
            if not isinstance(arguments, dict):
                raise ValueError("Tool arguments must be a JSON object.")
            tool = FUNCTION_MAP[tool_name]
            result = tool(**arguments)
        except Exception as error:
            # Tool failures are returned to the model so it can correct and retry.
            result = {"status": "tool_error", "message": str(error)}

        tool_messages.append(
            {
                "role": "tool",
                "tool_call_id": _field(tool_call, "id"),
                "content": json.dumps(result, default=str),
            }
        )

    return {"messages": tool_messages}


def should_continue(state: AgentState) -> Literal["execute_tools", "end"]:
    """Route tool-calling responses back through the tools; otherwise finish."""
    latest_message = state["messages"][-1]
    if _field(latest_message, "tool_calls", []) or []:
        return "execute_tools"
    return "end"
