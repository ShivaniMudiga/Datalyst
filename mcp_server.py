from mcp.server.fastmcp import FastMCP

from src.explorer.schema_explorer import SchemaExplorer
from src.executor.query_executor import QueryExecutor
from src.validator.sql_validator import SQLValidator


# Create MCP server
mcp = FastMCP("TalkToMyData2")


# Initialize your tools
schema_explorer = SchemaExplorer()
query_executor = QueryExecutor()
sql_validator = SQLValidator()


@mcp.tool()
def get_tables():
    """
    Get all tables available in the database.
    """
    return schema_explorer.get_tables()


@mcp.tool()
def get_columns(table_name: str):
    """
    Get columns and metadata of a specific table.
    """
    return schema_explorer.get_columns(table_name)


@mcp.tool()
def execute_sql(query: str):
    """
    Validate and execute a SQL query on PostgreSQL.
    """

    validation = sql_validator.validate(query)

    if not validation.valid:
        return {
        "status": "validation_failed",
        "query": query,
        "stage": validation.stage,
        "error_type": validation.error_type,
        "message": validation.message
    }

    return query_executor.execute(query)


if __name__ == "__main__":
    mcp.run()