"""High-level conversational facade for the LangGraph agent."""

import json
import time
from collections.abc import Iterator, Mapping
from typing import Any

from src.graph.graph_builder import build_agent_graph


class ConversationalAgent:
    """Conversation state is managed by the LangGraph checkpointer."""

    def __init__(self, thread_id: str) -> None:
        self._graph = build_agent_graph()
        self.thread_id = thread_id

    def ask(self, prompt: str) -> str:
        """Run one conversational turn."""

        return self.ask_with_metadata(prompt)["response"]

    def ask_with_metadata(self, prompt: str) -> dict[str, Any]:
        """Run one turn and return UI-friendly output from its tool trace."""

        for event in self.stream(prompt):
            if event["event"] == "done":
                return event
        return {"response": "", "sql": None, "data": None}

    def stream(self, prompt: str) -> Iterator[dict[str, Any]]:
        """One turn, as it happens.

        An answer takes seconds to tens of seconds. Emitting a step the moment
        the model asks for it, and again when it comes back, is what separates
        a slow answer from an app that looks hung.
        """

        started = time.monotonic()
        config = {"configurable": {"thread_id": self.thread_id}}
        messages: list[Any] = []
        pending: dict[str, dict[str, Any]] = {}

        updates = self._graph.stream(
            {"messages": [{"role": "user", "content": prompt}]},
            config=config,
            stream_mode="updates",
        )

        for chunk in updates:
            for update in chunk.values():
                for message in (update or {}).get("messages", []):
                    messages.append(message)
                    yield from self._steps(message, pending)

        response = str(self._field(messages[-1], "content", "") or "") if messages else ""
        sql, data = self._query_metadata(messages)
        yield {
            "event": "done",
            "response": response,
            "sql": sql,
            "data": data,
            "ms": int((time.monotonic() - started) * 1000),
        }

    def _steps(self, message: Any, pending: dict[str, dict[str, Any]]) -> Iterator[dict[str, Any]]:
        """Turn one message into trace steps: requested, then resolved."""

        for tool_call in self._field(message, "tool_calls", []) or []:
            function = self._field(tool_call, "function", {})
            try:
                arguments = json.loads(self._field(function, "arguments", "{}"))
            except (TypeError, json.JSONDecodeError):
                arguments = {}
            step = {
                "event": "step",
                "id": self._field(tool_call, "id"),
                "tool": self._field(function, "name"),
                "sql": arguments.get("sql") if isinstance(arguments, Mapping) else None,
                "status": "running",
                "detail": None,
            }
            pending[step["id"]] = step
            yield dict(step)

        if self._field(message, "role") != "tool":
            return

        step = pending.get(self._field(message, "tool_call_id"))
        if step is None:
            return
        try:
            result = json.loads(self._field(message, "content", "null"))
        except (TypeError, json.JSONDecodeError):
            result = None

        status = result.get("status") if isinstance(result, Mapping) else None
        if status in {"validation_failed", "execution_failed", "tool_error"}:
            step |= {"status": "failed", "detail": result.get("message")}
        elif isinstance(result, Mapping) and "row_count" in result:
            capped = " (capped)" if result.get("truncated") else ""
            step |= {"status": "ok", "detail": f"{result['row_count']} rows{capped}"}
        else:
            step |= {"status": "ok", "detail": "schema"}
        yield dict(step)

    @staticmethod
    def _field(value: Any, name: str, default: Any = None) -> Any:
        if isinstance(value, Mapping):
            return value.get(name, default)
        return getattr(value, name, default)

    def _query_metadata(self, messages: list[Any]) -> tuple[str | None, list[dict[str, Any]] | None]:
        """Find the latest run_query call and its corresponding tool result."""
        sql_by_call_id: dict[str, str] = {}
        latest_sql: str | None = None
        latest_data: list[dict[str, Any]] | None = None

        for message in messages:
            if self._field(message, "role") == "assistant":
                for tool_call in self._field(message, "tool_calls", []) or []:
                    function = self._field(tool_call, "function", {})
                    if self._field(function, "name") != "run_query":
                        continue
                    try:
                        arguments = json.loads(self._field(function, "arguments", "{}"))
                        sql = arguments.get("sql")
                    except (TypeError, json.JSONDecodeError):
                        sql = None
                    if isinstance(sql, str):
                        call_id = self._field(tool_call, "id")
                        if isinstance(call_id, str):
                            sql_by_call_id[call_id] = sql
                        latest_sql = sql

            if self._field(message, "role") == "tool":
                call_id = self._field(message, "tool_call_id")
                if call_id not in sql_by_call_id:
                    continue
                try:
                    value = json.loads(self._field(message, "content", "null"))
                except (TypeError, json.JSONDecodeError):
                    continue
                rows = value.get("rows") if isinstance(value, Mapping) else value
                if isinstance(rows, list) and all(isinstance(row, Mapping) for row in rows):
                    latest_data = [dict(row) for row in rows]

        return latest_sql, latest_data
