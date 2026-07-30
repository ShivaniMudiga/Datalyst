"""High-level conversational facade for the LangGraph agent."""

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