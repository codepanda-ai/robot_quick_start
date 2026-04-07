from interfaces.models import IntentProfile
from interfaces.intent_profile_store import IIntentProfileStore


class IntentProfileService:
    """Manages long-term IntentProfile memory across sessions.

    The profile is saved incrementally — after each answered question — so even
    a partial run is remembered. It is never cleared on 'start over'.
    """

    def __init__(self, store: IIntentProfileStore):
        self._store = store

    def get(self, user_id: str) -> IntentProfile:
        return self._store.get(user_id)

    def save(self, user_id: str, profile: IntentProfile) -> None:
        self._store.save(user_id, profile)

    def has_profile(self, user_id: str) -> bool:
        """True if the user has at least one non-None field saved."""
        profile = self._store.get(user_id)
        return any(v is not None for v in profile.model_dump().values())
