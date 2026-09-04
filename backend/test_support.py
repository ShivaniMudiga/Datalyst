"""Shared setup for the self-check scripts.

Everything is per-account now, so a script that touches a store has to be
signed in first. One account, reused across runs and across scripts, and the
same account whether the script goes through the API or calls the stores
directly - so what one script sets up, another can still see.
"""

from src.auth import UserStore, current_user

EMAIL = "selfcheck@datalyst.test"
PASSWORD = "selfcheck-password"


def sign_in() -> tuple[str, str]:
    """The test account and a live token, creating the account on first run.

    Also sets the ContextVar, which is what makes ``ConnectionStore()`` and
    ``ChatStore()`` work outside a request.
    """
    users = UserStore()
    user = users.authenticate(EMAIL, PASSWORD) or users.create(EMAIL, PASSWORD)
    current_user.set(user.id)
    return user.id, users.start_session(user)
