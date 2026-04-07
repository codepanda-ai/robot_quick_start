from abc import ABC, abstractmethod

from interfaces.models import IntentProfile


class IIntentProfileStore(ABC):
    @abstractmethod
    def get(self, user_id: str) -> IntentProfile:
        """Return saved IntentProfile for user, or empty IntentProfile() if none exists."""
        pass

    @abstractmethod
    def save(self, user_id: str, profile: IntentProfile) -> None:
        """Persist the IntentProfile for a user (replaces entirely)."""
        pass

    @abstractmethod
    def clear(self, user_id: str) -> None:
        """Remove saved profile for a user."""
        pass
