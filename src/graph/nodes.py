"""Nodes and routing functions for the conversational agent graph."""

import json
from collections.abc import Mapping
from typing import Any, Literal

from src.agent.tools import FUNCTION_MAP
from src.graph.state import AgentState
from src.llm.zen_client import chat


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


def call_llm(state: AgentState) -> dict[str, list[dict[str, Any]]]:
    """Ask the existing OpenCode Zen client for the next assistant message."""
    message = chat(state["messages"])
    return {"messages": [_assistant_message(message)]}


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
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
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
