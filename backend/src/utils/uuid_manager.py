import uuid


def create_thread_id() -> str:
    """
    Generate a unique thread ID for a new conversation.
    """
    return str(uuid.uuid4())