"""Single-process guard shared by generation and conversation deletion."""

from threading import RLock

conversation_lock = RLock()
active_conversations: set[str] = set()
