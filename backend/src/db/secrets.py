"""Encryption for the one secret this app stores: the user's database password.

Everything else a user gives us is either hashed (their own password, their
session token) or not a secret at all. A connected database's password cannot
be hashed - we have to send it to their server - so it is encrypted at rest
instead, and the key lives outside the database it protects.

Fernet is AES-128-CBC with an HMAC-SHA256 tag, which means a tampered
ciphertext fails to decrypt rather than decrypting to garbage we would then
send somewhere as a password.
"""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

ENV_VAR = "CREDENTIAL_KEY"

_cipher: MultiFernet | None = None


def cipher() -> MultiFernet:
    """The cipher, built once.

    Keys are comma-separated, newest first: everything is encrypted with the
    first and decrypted with whichever one matches, so a key can be rotated by
    prepending the new one and re-running the migration below.
    """
    global _cipher
    if _cipher is None:
        raw = (os.getenv(ENV_VAR) or "").strip()
        if not raw:
            raise RuntimeError(
                f"{ENV_VAR} is not set, and it is the only thing standing between "
                "a copy of this database and every connected database's password. "
                f"Generate one with:  python -m src.db.secrets --new-key"
            )
        try:
            _cipher = MultiFernet([Fernet(key.strip()) for key in raw.split(",") if key.strip()])
        except (ValueError, TypeError) as error:
            raise RuntimeError(f"{ENV_VAR} is not a valid Fernet key: {error}") from error
    return _cipher


def encrypt(secret: str | None) -> str | None:
    """Ciphertext for storage. ``None`` and empty stay as they are: there is
    nothing to protect, and a stored empty string must not become a token."""
    if not secret:
        return secret
    return cipher().encrypt(secret.encode()).decode()


def decrypt(stored: str | None) -> str:
    if not stored:
        return ""
    try:
        return cipher().decrypt(stored.encode()).decode()
    except InvalidToken:
        # ponytail: rows written before encryption existed are plaintext. Run
        # `--migrate` once, then delete this branch so an unencrypted password
        # becomes an error instead of a silent success.
        return stored


def _migrate() -> None:
    """Encrypt every password still stored in plaintext. Safe to re-run."""
    from src.db.connection import app_cursor

    with app_cursor() as cursor:
        cursor.execute("SELECT connection_id, password FROM connections WHERE password IS NOT NULL;")
        rows = cursor.fetchall()

        migrated = 0
        for row in rows:
            stored = row["password"]
            try:
                cipher().decrypt(stored.encode())
                continue  # already encrypted
            except InvalidToken:
                pass
            cursor.execute(
                "UPDATE connections SET password = %s WHERE connection_id = %s;",
                (encrypt(stored), row["connection_id"]),
            )
            migrated += 1

    print(f"encrypted {migrated} of {len(rows)} stored password(s)")


if __name__ == "__main__":
    import sys

    if "--new-key" in sys.argv:
        print(Fernet.generate_key().decode())
    elif "--migrate" in sys.argv:
        _migrate()
    else:
        print(__doc__)
        print("usage: python -m src.db.secrets [--new-key | --migrate]")
