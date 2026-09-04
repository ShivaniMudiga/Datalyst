"""Conversations belong to the database they were asked against.

Run: .venv/bin/python test_connection_scoping.py
"""

from uuid import uuid4

from src.auth import current_user
from src.db.chat_store import ChatStore, ConnectionStore
from src.db.connection import app_cursor

PG = {"db_type": "postgresql", "host": "localhost", "port": "5432",
      "database": "alpha_db", "username": "reader", "password": "pw1", "purpose": "alpha"}
MONGO = {"db_type": "mongodb", "host": "localhost", "port": "27017",
         "database": "beta_db", "username": "reader", "password": "pw2", "purpose": "beta"}


def _fresh_user() -> str:
    who = f"test-{uuid4()}"
    current_user.set(who)
    return who


def _cleanup(who: str) -> None:
    with app_cursor() as cursor:
        cursor.execute("DELETE FROM chat_sessions WHERE user_id = %s;", (who,))
        cursor.execute("DELETE FROM connections WHERE user_id = %s;", (who,))


def test_chats_are_scoped_to_their_connection() -> None:
    who = _fresh_user()
    try:
        connections, chats = ConnectionStore(who), ChatStore(who)

        alpha = connections.save(**PG)
        chats.create_session("chat-alpha", "about alpha")
        assert [c.title for c in chats.list_sessions()] == ["about alpha"]

        # Switching database must not carry the old conversation across.
        beta = connections.save(**MONGO)
        assert beta.id != alpha.id, "a second database must be a second connection"
        assert chats.list_sessions() == [], "alpha's chats must not show under beta"

        chats.create_session("chat-beta", "about beta")
        assert [c.title for c in chats.list_sessions()] == ["about beta"]

        # ...and switching back must bring it back, not lose it.
        connections.activate(alpha.id)
        assert [c.title for c in chats.list_sessions()] == ["about alpha"]
    finally:
        _cleanup(who)


def test_reconnecting_the_same_database_reuses_it() -> None:
    """Otherwise every reconnect orphans the previous chats and snapshot."""
    who = _fresh_user()
    try:
        connections, chats = ConnectionStore(who), ChatStore(who)
        first = connections.save(**PG)
        chats.create_session("chat-1", "kept")

        again = connections.save(**PG)
        assert again.id == first.id, "the same database must not become a second connection"
        assert [c.title for c in chats.list_sessions()] == ["kept"]
        assert len(connections.list()) == 1
    finally:
        _cleanup(who)


def test_exactly_one_connection_is_active() -> None:
    who = _fresh_user()
    try:
        connections = ConnectionStore(who)
        connections.save(**PG)
        beta = connections.save(**MONGO)

        active = [c for c in connections.list() if c.is_active]
        assert len(active) == 1, active
        assert active[0].id == beta.id
        assert connections.active_id() == beta.id
    finally:
        _cleanup(who)


def test_snapshot_and_purpose_follow_the_connection() -> None:
    """Switching back must not force a re-read of a schema already read."""
    who = _fresh_user()
    try:
        connections = ConnectionStore(who)
        alpha = connections.save(**PG)
        connections.save_snapshot({"database": "alpha_db", "tables": []})

        beta = connections.save(**MONGO)
        assert connections.get_snapshot() is None, "beta must not inherit alpha's schema"
        connections.save_snapshot({"database": "beta_db", "tables": []})

        connections.activate(alpha.id)
        assert connections.get_snapshot()["database"] == "alpha_db"
        assert connections.get().purpose == "alpha"

        connections.activate(beta.id)
        assert connections.get_snapshot()["database"] == "beta_db"
        assert connections.get().purpose == "beta"
    finally:
        _cleanup(who)


def test_credentials_are_per_connection() -> None:
    who = _fresh_user()
    try:
        connections = ConnectionStore(who)
        alpha = connections.save(**PG)
        connections.save(**MONGO)

        assert connections.credentials()["password"] == "pw2"          # active
        assert connections.credentials(alpha.id)["password"] == "pw1"  # by id
    finally:
        _cleanup(who)


def test_a_chat_knows_which_database_it_belongs_to() -> None:
    """What the API guard uses to refuse answering a Postgres conversation
    with a Mongo schema."""
    who = _fresh_user()
    try:
        connections, chats = ConnectionStore(who), ChatStore(who)
        alpha = connections.save(**PG)
        chats.create_session("chat-alpha", "about alpha")
        assert chats.connection_for("chat-alpha") == alpha.id

        beta = connections.save(**MONGO)
        assert chats.connection_for("chat-alpha") != beta.id
    finally:
        _cleanup(who)


def test_another_users_connection_cannot_be_activated() -> None:
    mine, theirs = _fresh_user(), _fresh_user()
    try:
        current_user.set(theirs)
        stolen = ConnectionStore(theirs).save(**PG)

        current_user.set(mine)
        try:
            ConnectionStore(mine).activate(stolen.id)
        except ValueError:
            pass
        else:
            raise AssertionError("activating another account's connection must fail")
    finally:
        _cleanup(mine)
        _cleanup(theirs)


if __name__ == "__main__":
    for name, case in sorted(globals().items()):
        if name.startswith("test_"):
            case()
            print(f"ok  {name}")
    print("all connection scoping checks passed")
