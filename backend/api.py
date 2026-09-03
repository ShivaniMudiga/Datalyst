"""REST adapter for the TalkToMyData conversational agent."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from threading import Lock
from typing import Any

import json

logger = logging.getLogger("data_runtime")

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.agent.agent import ConversationalAgent
from src.agent.tools import close_all_sources, data_source, reset_data_source
from src.auth import MIN_PASSWORD, User, UserStore, current_user
from src.datasource.base import MONGO, check
from src.db.chat_store import ChatStore, ConnectionStore
from src.db.connection import close_data_pool
from src.graph.nodes import reset_prompt_cache
from src.knowledge import questions as suggested_questions
from src.knowledge.snapshot import load_snapshot, read_and_store
from src.utils.uuid_manager import create_thread_id


class ConnectionRequest(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: str = Field(default="5432", max_length=8)
    database: str = Field(min_length=1, max_length=128)
    username: str = Field(min_length=1, max_length=128)
    password: str = ""
    db_type: str = "postgresql"
    permission: str = "read_only"
    purpose: str = Field(default="", max_length=2000)


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class PurposeRequest(BaseModel):
    purpose: str = Field(default="", max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    chat_id: str | None = None


class ChatSummary(BaseModel):
    id: str
    title: str
    created_at: str | None = None


def _sse(event: Mapping[str, Any]) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sql: str | None = None
    data: list[dict[str, Any]] | None = None
    created_at: str


app = FastAPI(title="TalkToMyData API", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_users = UserStore()


@app.middleware("http")
async def attach_user(request: Request, call_next):
    """Resolve the bearer token once, for the whole request.

    The user id goes into a ContextVar here rather than in a dependency: a sync
    endpoint runs in a worker thread that copies this context, and a value set
    inside a dependency's own thread would not survive that hop. The stores read
    the ContextVar, which is what keeps ``ConnectionStore()`` meaning "this
    user's connection" without threading an id through every call site.
    """
    token = (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
    user = await run_in_threadpool(_users.user_for_token, token) if token else None
    current_user.set(user.id if user else None)
    request.state.user = user
    request.state.token = token
    return await call_next(request)


def signed_in(request: Request) -> User:
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return user


def _new_chat(user: User) -> ChatSummary:
    chat_id = create_thread_id()
    session = ChatStore(user.id).create_session(chat_id)
    return ChatSummary(id=session.id, title=session.title, created_at=session.created_at.isoformat())


@app.on_event("shutdown")
def _close_pools() -> None:
    from src.db.connection import close_all

    close_all_sources()  # closes any Mongo clients
    close_all()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------


@app.post("/auth/signup", status_code=201)
def sign_up(body: Credentials) -> dict[str, Any]:
    email = body.email.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    if len(body.password) < MIN_PASSWORD:
        raise HTTPException(
            status_code=400, detail=f"Use a password of at least {MIN_PASSWORD} characters."
        )

    try:
        user = _users.create(email, body.password)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    return {"token": _users.start_session(user), "user": user.public()}


@app.post("/auth/login")
def log_in(body: Credentials) -> dict[str, Any]:
    user = _users.authenticate(body.email, body.password)
    if user is None:
        # One message for both cases: which half was wrong is not the caller's
        # business, and saying would enumerate registered addresses.
        raise HTTPException(status_code=401, detail="That email and password do not match.")
    return {"token": _users.start_session(user), "user": user.public()}


@app.post("/auth/logout", status_code=204)
def log_out(request: Request) -> None:
    token = getattr(request.state, "token", "")
    if token:
        _users.end_session(token)


@app.get("/auth/me")
def me(user: User = Depends(signed_in)) -> dict[str, Any]:
    return user.public()


@app.get("/chats", response_model=list[ChatSummary])
def get_chats(user: User = Depends(signed_in)) -> list[ChatSummary]:
    return [
        ChatSummary(id=session.id, title=session.title, created_at=session.created_at.isoformat())
        for session in ChatStore(user.id).list_sessions()
    ]


@app.get("/chats/{chat_id}/messages", response_model=list[ChatMessageResponse])
def get_chat_messages(chat_id: str, user: User = Depends(signed_in)) -> list[ChatMessageResponse]:
    store = ChatStore(user.id)
    if store.get_session(chat_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    messages = store.get_messages(chat_id)
    return [
        ChatMessageResponse(
            id=f"{chat_id}-{index}",
            role=message.role,
            content=message.content,
            sql=message.sql,
            data=message.data,
            created_at=message.created_at.isoformat(),
        )
        for index, message in enumerate(messages, start=1)
    ]


@app.post("/chat/stream")
def chat_stream(request: ChatRequest, user: User = Depends(signed_in)) -> StreamingResponse:
    """One turn, streamed.

    An answer is several queries and takes seconds to tens of seconds. The trace
    steps go out as they happen; ``done`` carries the answer itself.

    ponytail: the trace is streamed but not stored. It is what makes the wait
    legible, and a reloaded conversation still shows the SQL and the result.
    Add a `trace` column when someone needs to review a past run.
    """
    store = ChatStore(user.id)
    chat_id = request.chat_id
    if chat_id is None:
        chat_id = _new_chat(user).id
    elif store.get_session(chat_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    else:
        # A conversation belongs to the database it was started against. Left
        # unchecked, resuming one after switching database answers a question
        # about Postgres tables using a Mongo schema, and the history reads as
        # if it were all one conversation about one database.
        active = ConnectionStore(user.id).active_id()
        belongs_to = store.connection_for(chat_id)
        if belongs_to is not None and belongs_to != active:
            raise HTTPException(
                status_code=409,
                detail="This conversation belongs to a different database. "
                "Switch back to it, or start a new conversation here.",
            )

    question = request.message.strip()

    def events():
        # The generator runs after the endpoint returns, in a context that no
        # longer carries the middleware's user. Set it again for the agent.
        current_user.set(user.id)
        yield _sse({"event": "start", "chat_id": chat_id})
        store.append_message(chat_id, "user", question)

        session = store.get_session(chat_id)
        if session is not None and session.title == "New conversation":
            store.update_title(chat_id, question[:64])

        try:
            for event in ConversationalAgent(chat_id).stream(question):
                if event["event"] == "done":
                    store.append_message(
                        chat_id, "assistant", event["response"], event.get("sql"), event.get("data")
                    )
                yield _sse(event)
        except Exception:
            logger.exception("chat %s failed: %s", chat_id, question)
            yield _sse(
                {
                    "event": "error",
                    "message": "The database assistant could not complete this request. "
                    "Check the backend logs and database connection settings.",
                }
            )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Setup: connection, purpose, schema
# ---------------------------------------------------------------------------


@app.get("/connection")
def get_connection(user: User = Depends(signed_in)) -> dict[str, Any]:
    connection = ConnectionStore(user.id).get()
    snapshot = load_snapshot() if connection else None
    return {
        "connection": connection.public() if connection else None,
        "has_snapshot": snapshot is not None,
    }


@app.post("/connection/test")
def test_connection(request: ConnectionRequest, user: User = Depends(signed_in)) -> dict[str, Any]:
    """Test before saving. The user must not be able to advance into a failure."""
    try:
        check(request.model_dump())
    except Exception as error:
        # The driver's own message, verbatim: it names the actual problem far
        # better than anything this layer could paraphrase.
        return {"ok": False, "message": str(error).strip()}
    return {"ok": True, "message": f"Connected to {request.database}."}


@app.post("/connection", status_code=201)
def save_connection(request: ConnectionRequest, user: User = Depends(signed_in)) -> dict[str, Any]:
    try:
        check(request.model_dump())
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error).strip()) from error

    _preview_snapshots.pop(user.id, None)

    store = ConnectionStore(user.id)
    previous = store.credentials()
    connection = store.save(**request.model_dump())

    # The pool for the database we just left can go. Its source and prompt
    # stay: they are keyed by connection, so they are still correct if the
    # user switches back, and re-reading them costs a schema read.
    if previous and previous.get("db_type") != MONGO:
        close_data_pool(previous)
    # This connection's own caches do have to go - the credentials may have
    # changed underneath them.
    reset_data_source(connection.id)
    reset_prompt_cache(connection.id)
    return connection.public()


@app.get("/connections")
def list_connections(user: User = Depends(signed_in)) -> list[dict[str, Any]]:
    """Every database this user has connected. The active one is first."""
    return [connection.public() for connection in ConnectionStore(user.id).list()]


@app.post("/connections/{connection_id}/activate")
def activate_connection(connection_id: str, user: User = Depends(signed_in)) -> dict[str, Any]:
    """Switch back to a database already connected, with its purpose, its
    stored schema and its conversations."""
    try:
        connection = ConnectionStore(user.id).activate(connection_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return connection.public()


@app.patch("/connection/purpose")
def update_purpose(request: PurposeRequest, user: User = Depends(signed_in)) -> dict[str, Any]:
    store = ConnectionStore(user.id)
    if store.get() is None:
        raise HTTPException(status_code=404, detail="No database is connected.")
    store.update_purpose(request.purpose)
    reset_prompt_cache(store.active_id())
    return {"purpose": request.purpose}


# One per user: the purpose screen previews questions against a database whose
# schema has not been stored yet, and reading it again per keystroke is slow.
_preview_snapshots: dict[str, dict[str, Any]] = {}


def _snapshot_for_preview(user: User) -> dict[str, Any] | None:
    """The stored snapshot, or a live read if the schema has not been read yet.

    The purpose screen has to show real questions about the real database before
    the user commits, and at that point nothing has been stored. Read once and
    keep it for the rest of the process; the analysing step stores the real one.
    """
    snapshot = load_snapshot()
    if snapshot is not None:
        return snapshot
    if user.id not in _preview_snapshots and ConnectionStore(user.id).get() is not None:
        try:
            _preview_snapshots[user.id] = data_source().introspect()
        except Exception:
            return None
    return _preview_snapshots.get(user.id)


@app.post("/purpose/preview")
def preview_purpose(request: PurposeRequest, user: User = Depends(signed_in)) -> dict[str, list[str]]:
    """What this purpose will make the assistant suggest, before committing to it."""
    return {"questions": suggested_questions.suggest(request.purpose, _snapshot_for_preview(user))}


@app.get("/questions")
def get_questions(user: User = Depends(signed_in)) -> dict[str, list[str]]:
    connection = ConnectionStore(user.id).get()
    purpose = connection.purpose if connection else ""
    return {"questions": suggested_questions.suggest(purpose, load_snapshot())}


@app.get("/schema")
def get_schema(user: User = Depends(signed_in)) -> dict[str, Any]:
    snapshot = load_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="The schema has not been read yet.")
    return snapshot


@app.post("/schema/analyse")
def analyse_schema(user: User = Depends(signed_in)) -> StreamingResponse:
    """Read the database once, streaming a line per step.

    It takes seconds, not milliseconds. A spinner over a fifteen-second wait is
    indistinguishable from a hung app, so the steps are sent as they complete.

    A POST, not a GET, because EventSource cannot send an Authorization header
    and a token does not belong in a URL.
    """

    def events():
        current_user.set(user.id)  # the generator runs outside the request context
        try:
            for event in read_and_store():
                yield _sse(event)
            connection_id = ConnectionStore(user.id).active_id()
            reset_data_source(connection_id)
            reset_prompt_cache(connection_id)
        except Exception as error:
            yield _sse({"event": "error", "message": str(error)})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
