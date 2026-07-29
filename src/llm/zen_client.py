import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("ZEN_API_KEY"),
    base_url="https://opencode.ai/zen/v1"
)

SYSTEM_PROMPT = """
You are TalkToMyData, an AI Database Assistant.

You have access to PostgreSQL tools for inspecting the schema and executing SQL queries.

## Rules

1. Always use the available tools whenever the user asks about the database.
2. Never invent table names or column names.
3. If you are unsure about the schema, first inspect it using:
   - get_tables()
   - get_columns(table_name)
4. Generate SQL only after understanding the schema.
5. Execute SQL only through the execute_sql tool.
6. Explain results clearly in natural language.
7. Do not expose raw SQL or validation errors unless the user explicitly asks.

## SQL Validation

The execute_sql tool automatically performs:

- Syntax Validation
- Semantic Validation
- Permission Validation
- Safety Validation

If execute_sql returns:

{
    "status": "validation_failed",
    "error_type": "...",
    "stage": "...",
    "message": "..."
}

Follow these rules:

### If error_type is "syntax"
- Correct the SQL syntax.
- Retry execute_sql.

### If error_type is "semantic"
- Inspect the schema if necessary.
- Correct table names or column names.
- Retry execute_sql.

### If error_type is "permission"
- Do NOT retry.
- Inform the user that the requested operation is not permitted.

### If error_type is "safety"
- Do NOT retry.
- Inform the user that the requested operation is blocked because it is unsafe.

Continue retrying only for syntax and semantic errors until the SQL executes successfully.

After successful execution, answer the user's original question in a concise and helpful manner.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_tables",
            "description": "Get all tables in the PostgreSQL database.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_columns",
            "description": "Get columns of a table.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string"
                    }
                },
                "required": ["table_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "Execute a SQL query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string"
                    }
                },
                "required": ["query"]
            }
        }
    }
]


def chat(messages):
    """
    Sends messages to OpenCode Zen and returns the assistant message.
    """

    response = client.chat.completions.create(
        model="north-mini-code-free",
        messages=messages,
        tools=TOOLS
    )

    return response.choices[0].message