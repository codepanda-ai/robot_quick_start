import threading

from interfaces.models import IntentProfile
from interfaces.intent_profile_store import IIntentProfileStore


class InMemoryIntentProfileStore(IIntentProfileStore):
    """Thread-safe in-memory store for long-term IntentProfile memory, keyed by user open_id.

    Unlike the session store, this is never cleared on 'start over' — it survives
    across sessions so users can restore their last preferences.
    """

    def __init__(self):
        self._store: dict[str, IntentProfile] = {}
        self._lock = threading.Lock()

    def get(self, user_id: str) -> IntentProfile:
        with self._lock:
            if user_id in self._store:
                return self._store[user_id].model_copy(deep=True)
            return IntentProfile()

    def save(self, user_id: str, profile: IntentProfile) -> None:
        with self._lock:
            self._store[user_id] = profile.model_copy(deep=True)

    def clear(self, user_id: str) -> None:
        with self._lock:
            self._store.pop(user_id, None)
