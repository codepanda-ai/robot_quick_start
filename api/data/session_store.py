import threading

from interfaces.models import SessionState
from interfaces.session_store import ISessionStore


class InMemorySessionStore(ISessionStore):
    """Thread-safe in-memory session store. Stores SessionState keyed by user open_id."""

    def __init__(self):
        self._store: dict[str, SessionState] = {}
        self._lock = threading.Lock()

    def get(self, user_id: str) -> SessionState:
        with self._lock:
            if user_id in self._store:
                return self._store[user_id].model_copy(deep=True)
            return SessionState()

    def save(self, user_id: str, state: SessionState) -> None:
        with self._lock:
            self._store[user_id] = state.model_copy(deep=True)

    def clear(self, user_id: str) -> None:
        with self._lock:
            self._store.pop(user_id, None)
