"""Construction of the TalkToMyData LangGraph workflow."""

from langgraph.graph import END, START, StateGraph

from src.graph.nodes import call_llm, execute_tools, should_continue
from src.graph.state import AgentState


def build_agent_graph():
    """Compile the reusable conversational tool-calling graph.

    Checkpointing can be enabled later by passing a checkpointer to ``compile``
    without changing nodes or routing.
    """
    workflow = StateGraph(AgentState)
    workflow.add_node("call_llm", call_llm)
    workflow.add_node("execute_tools", execute_tools)
    workflow.add_edge(START, "call_llm")
    workflow.add_conditional_edges(
        "call_llm",
        should_continue,
        {"execute_tools": "execute_tools", "end": END},
    )
    workflow.add_edge("execute_tools", "call_llm")
    return workflow.compile()
