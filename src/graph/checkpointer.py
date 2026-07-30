from langgraph.checkpoint.postgres import PostgresSaver

from src.db.connection import DatabaseConnection


class GraphCheckpointer:

    def __init__(self):

        db = DatabaseConnection()

        self._context = PostgresSaver.from_conn_string(
            db.get_connection_uri()
        )

        self._checkpointer = None

    def get(self):
        """
        Returns a live PostgresSaver instance.
        """

        if self._checkpointer is None:
            self._checkpointer = self._context.__enter__()

        return self._checkpointer

    def close(self):
        """
        Closes the PostgresSaver.
        """

        if self._checkpointer is not None:
            self._context.__exit__(None, None, None)
            self._checkpointer = None