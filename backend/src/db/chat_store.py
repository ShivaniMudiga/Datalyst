from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from src.auth import user_id as auth_user_id
from src.db.connection import app_cursor
from src.db.secrets import decrypt, encrypt


_schema_ready = False


def _ensure_schema() -> None:
    """Every table, and the migrations onto the current shape. Once per process.

    Both stores need this and neither owns it: ``chat_sessions`` points at
    ``connections``, so the order matters and a per-store method cannot
    guarantee it. Running once per process also keeps the DDL off the request
    path, where it used to run on every store construction.
    """
    global _schema_ready
    if _schema_ready:
        return

    with app_cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS connections (
                connection_id TEXT PRIMARY KEY,
                db_type TEXT NOT NULL DEFAULT 'postgresql',
                host TEXT NOT NULL,
                port TEXT NOT NULL,
                database TEXT NOT NULL,
                username TEXT NOT NULL,
                password TEXT,
                permission TEXT NOT NULL DEFAULT 'read_only',
                purpose TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )

        # A connection used to be one row per user, keyed by the user's own id.
        # Those rows stay exactly as they are - their id simply stops meaning
        # "user" and starts meaning "connection", which is what `user_id`
        # below now carries. Their snapshots keep pointing at them.
        cursor.execute("ALTER TABLE connections ADD COLUMN IF NOT EXISTS user_id TEXT;")
        cursor.execute("UPDATE connections SET user_id = connection_id WHERE user_id IS NULL;")
        cursor.execute("ALTER TABLE connections ALTER COLUMN user_id SET NOT NULL;")
        cursor.execute(
            "ALTER TABLE connections ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS connections_user ON connections (user_id);")
        # One active connection per user, enforced by the database rather than
        # by whoever remembers to clear the old flag.
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS connections_one_active
            ON connections (user_id) WHERE is_active;
            """
        )
        # Reconnecting the same database must find the existing row - and its
        # chats - rather than pile up a duplicate.
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS connections_identity
            ON connections (user_id, db_type, host, port, database, username);
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_snapshots (
                snapshot_id BIGSERIAL PRIMARY KEY,
                connection_id TEXT NOT NULL REFERENCES connections(connection_id) ON DELETE CASCADE,
                snapshot JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                chat_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        # ON DELETE SET NULL, not CASCADE: disconnecting a database must not
        # silently delete the conversations you had about it.
        cursor.execute(
            """
            ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS connection_id TEXT
            REFERENCES connections(connection_id) ON DELETE SET NULL;
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS chat_sessions_connection ON chat_sessions (user_id, connection_id);"
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id BIGSERIAL PRIMARY KEY,
                chat_id TEXT NOT NULL REFERENCES chat_sessions(chat_id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sql TEXT,
                data JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )

    _schema_ready = True


@dataclass(slots=True)
class ChatSession:
    id: str
    title: str
    created_at: datetime


@dataclass(slots=True)
class ChatMessageRecord:
    role: str
    content: str
    sql: str | None
    data: list[dict[str, Any]] | None
    created_at: datetime


class ChatStore:
    """Conversations, scoped to one user.

    Every read filters on ``user_id``: a chat id is a UUID, but guessing is not
    the only way to reach one, so scoping is enforced in the query rather than
    left to the caller.
    """

    def __init__(self, user_id: str | None = None) -> None:
        self.user_id = user_id or auth_user_id()
        _ensure_schema()

    def list_sessions(self) -> list[ChatSession]:
        with app_cursor() as cursor:
            cursor.execute(
                """
                SELECT chat_id, title, created_at
                FROM chat_sessions
                WHERE user_id = %s
                  AND connection_id = (
                      SELECT connection_id FROM connections
                      WHERE user_id = %s AND is_active
                  )
                ORDER BY updated_at DESC, created_at DESC;
                """,
                (self.user_id, self.user_id),
            )
            rows = cursor.fetchall()

        return [
            ChatSession(id=row["chat_id"], title=row["title"], created_at=row["created_at"])
            for row in rows
        ]

    def get_session(self, chat_id: str) -> ChatSession | None:
        with app_cursor() as cursor:
            cursor.execute(
                """
                SELECT chat_id, title, created_at
                FROM chat_sessions
                WHERE chat_id = %s AND user_id = %s;
                """,
                (chat_id, self.user_id),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return ChatSession(id=row["chat_id"], title=row["title"], created_at=row["created_at"])

    def connection_for(self, chat_id: str) -> str | None:
        """The connection this conversation was started against.

        ``None`` for a conversation from before chats were tied to a
        connection. The caller decides what that means; the store does not
        guess.
        """
        with app_cursor() as cursor:
            cursor.execute(
                "SELECT connection_id FROM chat_sessions WHERE chat_id = %s AND user_id = %s;",
                (chat_id, self.user_id),
            )
            row = cursor.fetchone()
        return row["connection_id"] if row else None

    def create_session(self, chat_id: str, title: str = "New conversation") -> ChatSession:
        with app_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO chat_sessions (chat_id, user_id, title, connection_id)
                VALUES (%s, %s, %s,
                    (SELECT connection_id FROM connections WHERE user_id = %s AND is_active))
                ON CONFLICT (chat_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    updated_at = NOW()
                WHERE chat_sessions.user_id = EXCLUDED.user_id
                RETURNING chat_id, title, created_at;
                """,
                (chat_id, self.user_id, title, self.user_id),
            )
            row = cursor.fetchone()
        if row is None:  # the id exists and belongs to someone else
            raise ValueError("That conversation belongs to another account.")
        return ChatSession(id=row["chat_id"], title=row["title"], created_at=row["created_at"])

    def update_title(self, chat_id: str, title: str) -> None:
        with app_cursor() as cursor:
            cursor.execute(
                """
                UPDATE chat_sessions
                SET title = %s, updated_at = NOW()
                WHERE chat_id = %s AND user_id = %s;
                """,
                (title, chat_id, self.user_id),
            )

    def append_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        sql: str | None = None,
        data: list[dict[str, Any]] | None = None,
    ) -> None:
        with app_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO chat_messages (chat_id, role, content, sql, data)
                SELECT %s, %s, %s, %s, %s
                WHERE EXISTS (
                    SELECT 1 FROM chat_sessions WHERE chat_id = %s AND user_id = %s
                );
                """,
                (chat_id, role, content, sql, Json(data) if data is not None else None,
                 chat_id, self.user_id),
            )
            cursor.execute(
                """
                UPDATE chat_sessions
                SET updated_at = NOW()
                WHERE chat_id = %s AND user_id = %s;
                """,
                (chat_id, self.user_id),
            )

    def get_messages(self, chat_id: str) -> list[ChatMessageRecord]:
        with app_cursor() as cursor:
            cursor.execute(
                """
                SELECT m.role, m.content, m.sql, m.data, m.created_at
                FROM chat_messages m
                JOIN chat_sessions s ON s.chat_id = m.chat_id
                WHERE m.chat_id = %s AND s.user_id = %s
                ORDER BY m.id ASC;
                """,
                (chat_id, self.user_id),
            )
            rows = cursor.fetchall()

        messages: list[ChatMessageRecord] = []
        for row in rows:
            data = row["data"]
            normalized_data: list[dict[str, Any]] | None = None
            if isinstance(data, list) and all(isinstance(item, Mapping) for item in data):
                normalized_data = [dict(item) for item in data]

            messages.append(
                ChatMessageRecord(
                    role=row["role"],
                    content=row["content"],
                    sql=row["sql"],
                    data=normalized_data,
                    created_at=row["created_at"],
                )
            )

        return messages

@dataclass(slots=True)
class Connection:
    id: str
    db_type: str
    host: str
    port: str
    database: str
    username: str
    permission: str
    purpose: str
    created_at: datetime
    is_active: bool = True

    def public(self) -> dict[str, Any]:
        """Everything except the password. The password leaves this process
        only as part of a connection string."""
        return {
            "id": self.id,
            "db_type": self.db_type,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "permission": self.permission,
            "purpose": self.purpose,
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active,
        }


class ConnectionStore:
    """A user's database connections, and the snapshot read from each.

    A user may have several - one per database they have connected - and
    exactly one is active at a time. Everything that is "about a database"
    hangs off the connection rather than off the user: its purpose, its schema
    snapshot, and the conversations held against it. Switching database is
    therefore activation, not replacement, and switching back restores all
    three.
    """

    def __init__(self, user_id: str | None = None) -> None:
        self.ID = user_id or auth_user_id()
        _ensure_schema()

    # -- reads ------------------------------------------------------------

    def get(self) -> Connection | None:
        """The active connection."""
        row = self._row()
        return self._to_connection(row) if row else None

    def active_id(self) -> str | None:
        """The active connection's id: the key everything per-database uses."""
        row = self._row()
        return row["connection_id"] if row else None

    def list(self) -> list[Connection]:
        with app_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM connections WHERE user_id = %s
                ORDER BY is_active DESC, updated_at DESC;
                """,
                (self.ID,),
            )
            return [self._to_connection(row) for row in cursor.fetchall()]

    def credentials(self, connection_id: str | None = None) -> dict[str, str] | None:
        """Including the password, decrypted. For building the connection
        string only: it is stored encrypted and must not leave this method in
        any response."""
        row = self._row(connection_id)
        if row is None:
            return None
        return {
            "db_type": row["db_type"],
            "host": row["host"],
            "port": row["port"],
            "database": row["database"],
            "username": row["username"],
            "password": decrypt(row["password"]),
        }

    # -- writes -----------------------------------------------------------

    def save(self, **fields: Any) -> Connection:
        """Connect a database, and make it the active one.

        Reconnecting a database this user already has returns that same row,
        which is what makes its chats and its snapshot come back rather than
        starting over.
        """
        identity = (
            self.ID,
            fields.get("db_type", "postgresql"),
            fields["host"],
            str(fields["port"]),
            fields["database"],
            fields["username"],
        )
        with app_cursor() as cursor:
            # Deactivate first: one active row per user is a unique index, so
            # the two statements have to be this order, in one transaction.
            cursor.execute("UPDATE connections SET is_active = FALSE WHERE user_id = %s;", (self.ID,))
            cursor.execute(
                """
                INSERT INTO connections
                    (connection_id, user_id, db_type, host, port, database, username,
                     password, permission, purpose, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                ON CONFLICT (user_id, db_type, host, port, database, username) DO UPDATE SET
                    password = EXCLUDED.password, permission = EXCLUDED.permission,
                    purpose = CASE WHEN EXCLUDED.purpose = '' THEN connections.purpose
                                   ELSE EXCLUDED.purpose END,
                    is_active = TRUE, updated_at = NOW()
                RETURNING *;
                """,
                (
                    str(uuid4()),
                    *identity,
                    encrypt(fields.get("password")) or None,
                    fields.get("permission", "read_only"),
                    fields.get("purpose", ""),
                ),
            )
            row = cursor.fetchone()
        return self._to_connection(row)

    def activate(self, connection_id: str) -> Connection:
        """Switch to a connection this user already has."""
        with app_cursor() as cursor:
            cursor.execute("UPDATE connections SET is_active = FALSE WHERE user_id = %s;", (self.ID,))
            cursor.execute(
                """
                UPDATE connections SET is_active = TRUE, updated_at = NOW()
                WHERE connection_id = %s AND user_id = %s
                RETURNING *;
                """,
                (connection_id, self.ID),
            )
            row = cursor.fetchone()
        if row is None:
            raise ValueError("That connection belongs to another account.")
        return self._to_connection(row)

    def update_purpose(self, purpose: str) -> None:
        with app_cursor() as cursor:
            cursor.execute(
                """
                UPDATE connections SET purpose = %s, updated_at = NOW()
                WHERE user_id = %s AND is_active;
                """,
                (purpose, self.ID),
            )

    def save_snapshot(self, snapshot: dict[str, Any]) -> None:
        with app_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO schema_snapshots (connection_id, snapshot)
                SELECT connection_id, %s FROM connections WHERE user_id = %s AND is_active;
                """,
                (Json(snapshot), self.ID),
            )

    def get_snapshot(self) -> dict[str, Any] | None:
        with app_cursor() as cursor:
            cursor.execute(
                """
                SELECT s.snapshot, s.created_at FROM schema_snapshots s
                JOIN connections c ON c.connection_id = s.connection_id
                WHERE c.user_id = %s AND c.is_active
                ORDER BY s.snapshot_id DESC LIMIT 1;
                """,
                (self.ID,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        snapshot = dict(row["snapshot"])
        snapshot["stored_at"] = row["created_at"].isoformat()
        return snapshot

    # -- internals --------------------------------------------------------

    def _row(self, connection_id: str | None = None):
        """The named connection, or the active one."""
        with app_cursor() as cursor:
            if connection_id is None:
                cursor.execute(
                    "SELECT * FROM connections WHERE user_id = %s AND is_active;", (self.ID,)
                )
            else:
                cursor.execute(
                    "SELECT * FROM connections WHERE connection_id = %s AND user_id = %s;",
                    (connection_id, self.ID),
                )
            return cursor.fetchone()

    @staticmethod
    def _to_connection(row) -> Connection:
        return Connection(
            id=row["connection_id"],
            db_type=row["db_type"],
            host=row["host"],
            port=row["port"],
            database=row["database"],
            username=row["username"],
            permission=row["permission"],
            purpose=row["purpose"],
            created_at=row["created_at"],
            is_active=row["is_active"],
        )
