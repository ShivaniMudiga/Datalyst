"""High-level conversational facade for the LangGraph agent."""

from time import perf_counter
from typing import Any

from src.graph.graph_builder import build_agent_graph


class ConversationalAgent:
    """Conversation state is managed by the LangGraph checkpointer."""

    def __init__(self, thread_id: str) -> None:
        self._graph = build_agent_graph()
        self.thread_id = thread_id

    def ask(self, prompt: str) -> str:
        """Run one conversational turn."""

        config = {
            "configurable": {
                "thread_id": self.thread_id
            }
        }

        result = self._graph.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            },
            config=config
        )

        final_message = result["messages"][-1]

        if isinstance(final_message, dict):
            return str(final_message.get("content") or "")

        return str(getattr(final_message, "content", "") or "")

    def ask_for_evaluation(self, prompt: str) -> dict[str, Any]:
        """Run one turn and expose SQL output for the isolated evaluator.

        This does not alter ``ask`` or the graph routing.  A fresh evaluator
        thread can call this method to compare the output of ``execute_sql``
        with a benchmark's directly executed ground-truth query.
        """
        started_at = perf_counter()
        config = {"configurable": {"thread_id": self.thread_id}}

        try:
            result = self._graph.invoke(
                {
                    "messages": [{"role": "user", "content": prompt}],
                    "execution_result": None,
                },
                config=config,
            )
            final_message = result["messages"][-1]
            answer = (
                str(final_message.get("content") or "")
                if isinstance(final_message, dict)
                else str(getattr(final_message, "content", "") or "")
            )
            return {
                "question": prompt,
                "answer": answer,
                "execution_result": result.get("execution_result"),
                "latency": perf_counter() - started_at,
                "error": None,
            }
        except Exception as error:
            return {
                "question": prompt,
                "answer": "",
                "execution_result": None,
                "latency": perf_counter() - started_at,
                "error": str(error),
            }
