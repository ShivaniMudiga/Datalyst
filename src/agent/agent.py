import json

from mcp_server import (
    get_tables,
    get_columns,
    execute_sql
)

from src.llm.zen_client import (
    chat,
    SYSTEM_PROMPT
)


FUNCTION_MAP = {
    "get_tables": get_tables,
    "get_columns": get_columns,
    "execute_sql": execute_sql
}


def ask(prompt: str):

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": prompt
        }
    ]

    while True:

        message = chat(messages)

        # Final answer from the model
        if not message.tool_calls:
            return message.content

        # Store assistant message
        messages.append(message)

        # Execute all requested tools
        for tool_call in message.tool_calls:

            tool_name = tool_call.function.name

            arguments = json.loads(tool_call.function.arguments)

            result = FUNCTION_MAP[tool_name](**arguments)

            # Return tool result to the model
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, default=str)
                }
            )