"""Accounts, passwords and sessions.

Everything a signed-in user owns hangs off their user id: their connection, its
schema snapshot, and their conversations. Rather than thread that id through
every call site, the request handler puts it in a ContextVar and the stores read
it from there - so ``ConnectionStore()`` still means "this user's connection".

Hashing is `hashlib.scrypt`: a real password KDF, in the standard library, no
dependency to add.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.db.connection import app_cursor

SESSION_DAYS = int(os.getenv("AUTH_SESSION_DAYS", "30"))
MIN_PASSWORD = 8

# scrypt parameters. n is the cost; 2**14 is roughly 100ms here, which is the
# right order for a login and far too slow to grind offline.
SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}

# The signed-in user for the current request. Set by the auth dependency in
# api.py, read by the stores. Unset outside a request, which is why the tests
# and the CLI set it explicitly.
current_user: ContextVar[str | None] = ContextVar("current_user", default=None)


def user_id() -> str:
    """The signed-in user, or a clear error rather than a silent global read."""
    value = current_user.get()
    if value is None:
        raise RuntimeError("No signed-in user in this context.")
    return value


@dataclass(slots=True)
class User:
    id: str
    email: str
    created_at: datetime

    def public(self) -> dict[str, str]:
        return {"id": self.id, "email": self.email, "created_at": self.created_at.isoformat()}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = stored.split("$")
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), **SCRYPT)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def _token_hash(token: str) -> str:
    """Sessions are stored hashed: a leaked database must not hand over live
    sessions. Tokens are already high-entropy, so a plain digest is enough."""
    return hashlib.sha256(token.encode()).hexdigest()


class UserStore:
    def __init__(self) -> None:
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with app_cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    expires_at TIMESTAMPTZ NOT NULL
                );
                """
            )

    # -- accounts ----------------------------------------------------------

    def create(self, email: str, password: str) -> User:
        """Raises ValueError if the address is taken."""
        email = email.strip().lower()
        with app_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (user_id, email, password_hash)
                VALUES (%s, %s, %s)
                ON CONFLICT (email) DO NOTHING
                RETURNING user_id, email, created_at;
                """,
                (secrets.token_hex(16), email, hash_password(password)),
            )
            row = cursor.fetchone()

        if row is None:
            raise ValueError("That email address is already registered.")
        return User(id=row["user_id"], email=row["email"], created_at=row["created_at"])

    def authenticate(self, email: str, password: str) -> User | None:
        with app_cursor() as cursor:
            cursor.execute(
                "SELECT user_id, email, password_hash, created_at FROM users WHERE email = %s;",
                (email.strip().lower(),),
            )
            row = cursor.fetchone()

        # Hash anyway when the address is unknown, so a missing account and a
        # wrong password take the same time to answer.
        stored = row["password_hash"] if row else hash_password("no such user")
        if not verify_password(password, stored) or row is None:
            return None
        return User(id=row["user_id"], email=row["email"], created_at=row["created_at"])

    # -- sessions ----------------------------------------------------------

    def start_session(self, user: User) -> str:
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
        with app_cursor() as cursor:
            cursor.execute(
                "INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (%s, %s, %s);",
                (_token_hash(token), user.id, expires),
            )
        return token

    def user_for_token(self, token: str) -> User | None:
        with app_cursor() as cursor:
            cursor.execute(
                """
                SELECT u.user_id, u.email, u.created_at
                FROM auth_sessions s
                JOIN users u ON u.user_id = s.user_id
                WHERE s.token_hash = %s AND s.expires_at > NOW();
                """,
                (_token_hash(token),),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return User(id=row["user_id"], email=row["email"], created_at=row["created_at"])

    def end_session(self, token: str) -> None:
        with app_cursor() as cursor:
            cursor.execute("DELETE FROM auth_sessions WHERE token_hash = %s;", (_token_hash(token),))
