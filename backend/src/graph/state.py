"""State definitions for the TalkToMyData LangGraph workflow."""

from typing import Annotated, Any

from typing_extensions import TypedDict


def append_messages(
    existing: list[dict[str, Any]], updates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Append OpenAI-compatible messages without converting their format.

    The existing Zen client consumes OpenAI SDK message dictionaries directly,
    so preserving that representation avoids an adapter layer at every LLM call.
    """
    return [*existing, *updates]


class AgentState(TypedDict):
    """
    Shared state that flows through every node in the graph.
    """

    # The reducer appends node output instead of replacing the conversation.
    # Additional fields (for example, ``last_sql`` or ``retry_count``) can be
    # added here later without changing the graph's control flow.
    messages: Annotated[list[dict[str, Any]], append_messages]
