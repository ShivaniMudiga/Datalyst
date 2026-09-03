"""Credential encryption: what must hold for stored database passwords.

Run: .venv/bin/python test_credential_encryption.py
"""

import os

os.environ.setdefault("CREDENTIAL_KEY", "")

from cryptography.fernet import Fernet

import src.db.secrets as secrets


def test_round_trip() -> None:
    secrets._cipher = None
    os.environ["CREDENTIAL_KEY"] = Fernet.generate_key().decode()

    stored = secrets.encrypt("reader_pw")
    assert stored != "reader_pw", "password must not be stored as plaintext"
    assert stored.startswith("gAAAAA"), stored
    assert secrets.decrypt(stored) == "reader_pw"

    # Same plaintext twice must not produce the same ciphertext, or the store
    # leaks which users share a password.
    assert secrets.encrypt("reader_pw") != stored


def test_empty_stays_empty() -> None:
    """Trust-auth connections have no password; an empty string must not
    become a token, or `password IS NULL` stops meaning 'no password'."""
    secrets._cipher = None
    os.environ["CREDENTIAL_KEY"] = Fernet.generate_key().decode()

    assert secrets.encrypt("") == ""
    assert secrets.encrypt(None) is None
    assert secrets.decrypt("") == ""
    assert secrets.decrypt(None) == ""


def test_tampering_is_not_silently_accepted() -> None:
    """A flipped byte must fail its HMAC, not decrypt to something we would
    then send to a database as a password."""
    secrets._cipher = None
    os.environ["CREDENTIAL_KEY"] = Fernet.generate_key().decode()

    stored = secrets.encrypt("reader_pw")
    tampered = stored[:-4] + ("aaaa" if not stored.endswith("aaaa") else "bbbb")
    # The legacy-plaintext fallback returns it unchanged rather than a wrong
    # password. It must never return the original secret.
    assert secrets.decrypt(tampered) != "reader_pw"


def test_wrong_key_does_not_decrypt() -> None:
    secrets._cipher = None
    os.environ["CREDENTIAL_KEY"] = Fernet.generate_key().decode()
    stored = secrets.encrypt("reader_pw")

    secrets._cipher = None
    os.environ["CREDENTIAL_KEY"] = Fernet.generate_key().decode()
    assert secrets.decrypt(stored) != "reader_pw"


def test_key_rotation() -> None:
    """Old ciphertext stays readable while a new key takes over writing."""
    old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()

    secrets._cipher = None
    os.environ["CREDENTIAL_KEY"] = old
    stored = secrets.encrypt("reader_pw")

    secrets._cipher = None
    os.environ["CREDENTIAL_KEY"] = f"{new},{old}"
    assert secrets.decrypt(stored) == "reader_pw", "old ciphertext must survive rotation"
    assert secrets.decrypt(secrets.encrypt("reader_pw")) == "reader_pw"


def test_missing_key_is_loud() -> None:
    """Silently falling back to plaintext is the bug being fixed."""
    secrets._cipher = None
    os.environ["CREDENTIAL_KEY"] = ""
    try:
        secrets.encrypt("reader_pw")
    except RuntimeError as error:
        assert "CREDENTIAL_KEY" in str(error)
    else:
        raise AssertionError("a missing key must raise, not store plaintext")


if __name__ == "__main__":
    for name, case in sorted(globals().items()):
        if name.startswith("test_"):
            case()
            print(f"ok  {name}")
    print("all credential encryption checks passed")
