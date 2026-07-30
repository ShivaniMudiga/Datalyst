"""Construction of the TalkToMyData LangGraph workflow."""

from langgraph.graph import END, START, StateGraph

from src.graph.nodes import call_llm, execute_tools, should_continue
from src.graph.state import AgentState
from src.graph.checkpointer import GraphCheckpointer


checkpointer = GraphCheckpointer()


def build_agent_graph():
    """Build and compile the LangGraph workflow."""

    workflow = StateGraph(AgentState)

    workflow.add_node("call_llm", call_llm)
    workflow.add_node("execute_tools", execute_tools)

    workflow.add_edge(START, "call_llm")

    workflow.add_conditional_edges(
        "call_llm",
        should_continue,
        {
            "execute_tools": "execute_tools",
            "end": END,
        },
    )

    workflow.add_edge("execute_tools", "call_llm")

    return workflow.compile(
        checkpointer=checkpointer.get()
    )