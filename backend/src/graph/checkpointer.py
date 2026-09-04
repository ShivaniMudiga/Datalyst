from langgraph.checkpoint.postgres import PostgresSaver

from src.db.connection import app_dsn


class GraphCheckpointer:
    """LangGraph's working state. Read-write, so it uses the app role."""

    def __init__(self):
        self._context = PostgresSaver.from_conn_string(app_dsn())
        self._checkpointer = None

    def get(self):
        if self._checkpointer is None:
            self._checkpointer = self._context.__enter__()
            self._checkpointer.setup()
        return self._checkpointer

    def close(self):
        if self._checkpointer is not None:
            self._context.__exit__(None, None, None)
            self._checkpointer = None
