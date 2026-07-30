"""High-level conversational facade for the LangGraph agent."""

from src.graph.graph_builder import build_agent_graph
from src.agent.tools import FUNCTION_MAP
from src.graph.state import AgentState
from src.llm.zen_client import SYSTEM_PROMPT


class ConversationalAgent:
    """Keeps LangGraph message state for the lifetime of the process."""

    def __init__(self) -> None:
        self._graph = build_agent_graph()
        self._state: AgentState = {
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}]
        }

    def ask(self, prompt: str) -> str:
        """Run one conversational turn and retain it for later follow-ups."""
        self._state["messages"].append({"role": "user", "content": prompt})
        self._state = self._graph.invoke(self._state)
        final_message = self._state["messages"][-1]
        if isinstance(final_message, dict):
            return str(final_message.get("content") or "")
        return str(getattr(final_message, "content", "") or "")


_default_agent = ConversationalAgent()


def ask(prompt: str) -> str:
    """Backward-compatible entry point backed by one persistent agent."""
    return _default_agent.ask(prompt)
