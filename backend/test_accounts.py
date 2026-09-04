"""Accounts: sign-up, sign-in, and the isolation between two users.

    backend/.venv/bin/python test_accounts.py

The point of the feature is that one account cannot see another's chats,
connection or schema. That is asserted here against the real API, with two real
accounts, because it is the kind of thing that quietly stops being true.
"""

import secrets

from fastapi.testclient import TestClient

import api
from src.db.connection import close_all

client = TestClient(api.app)

PASSWORD = "a-good-enough-password"


def account() -> tuple[str, dict[str, str]]:
    """A fresh account and the headers that speak for it."""
    email = f"{secrets.token_hex(8)}@datalyst.test"
    response = client.post("/auth/signup", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return email, {"Authorization": f"Bearer {response.json()['token']}"}


def connect(headers: dict[str, str], purpose: str) -> None:
    """Point this account at the development database, the way setup does."""
    body = {
        "host": "localhost", "port": "5432", "database": "talk_to_my_data_v2",
        "username": "apple", "password": "", "purpose": purpose,
    }
    assert client.post("/connection", json=body, headers=headers).status_code == 201


def test_signup_rejects_bad_input():
    email = f"{secrets.token_hex(8)}@datalyst.test"
    assert client.post("/auth/signup", json={"email": "nope", "password": PASSWORD}).status_code == 400
    assert client.post("/auth/signup", json={"email": email, "password": "short"}).status_code == 400

    assert client.post("/auth/signup", json={"email": email, "password": PASSWORD}).status_code == 201
    duplicate = client.post("/auth/signup", json={"email": email, "password": PASSWORD})
    assert duplicate.status_code == 409, duplicate.text


def test_login_and_logout():
    email, headers = account()

    assert client.post("/auth/login", json={"email": email, "password": "wrong"}).status_code == 401
    # An unknown address answers exactly like a wrong password.
    unknown = client.post("/auth/login", json={"email": "nobody@datalyst.test", "password": PASSWORD})
    assert unknown.status_code == 401 and unknown.json()["detail"] == (
        client.post("/auth/login", json={"email": email, "password": "wrong"}).json()["detail"]
    )

    assert client.get("/auth/me", headers=headers).json()["email"] == email

    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401, "the token outlived logout"


def test_everything_needs_a_token():
    for method, path in (
        ("get", "/chats"), ("get", "/connection"), ("get", "/schema"),
        ("get", "/questions"), ("post", "/chat/stream"),
    ):
        response = (
            client.post(path, json={"message": "hi"}) if method == "post" else client.get(path)
        )
        assert response.status_code == 401, (path, response.status_code)

    assert client.get("/chats", headers={"Authorization": "Bearer not-a-real-token"}).status_code == 401


def test_one_account_cannot_see_another():
    _, alice = account()
    _, bob = account()

    connect(alice, "Alice's job.")
    assert client.get("/connection", headers=bob).json()["connection"] is None, (
        "a new account inherited someone else's connection"
    )

    # Alice's purpose reaches Alice only.
    assert client.get("/connection", headers=alice).json()["connection"]["purpose"] == "Alice's job."

    # A conversation of Alice's is invisible and unreachable to Bob.
    store = __import__("src.db.chat_store", fromlist=["ChatStore"]).ChatStore
    alice_id = client.get("/auth/me", headers=alice).json()["id"]
    chat_id = store(alice_id).create_session("chat-for-alice-" + secrets.token_hex(4)).id

    assert any(chat["id"] == chat_id for chat in client.get("/chats", headers=alice).json())
    assert not any(chat["id"] == chat_id for chat in client.get("/chats", headers=bob).json())
    assert client.get(f"/chats/{chat_id}/messages", headers=bob).status_code == 404, (
        "another account read a conversation by guessing its id"
    )

    # Bob has connected nothing, so there is no schema for him to read.
    assert client.get("/schema", headers=bob).status_code == 404


if __name__ == "__main__":
    for name, test in sorted(globals().items()):
        if name.startswith("test_"):
            test()
            print("ok ", name)
    print("\nall checks passed")
    close_all()
