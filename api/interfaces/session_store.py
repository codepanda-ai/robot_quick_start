from abc import ABC, abstractmethod

from interfaces.models import SessionState


class ISessionStore(ABC):
    @abstractmethod
    def get(self, user_id: str) -> SessionState:
        """Return SessionState for user, or default if none exists."""
        pass

    @abstractmethod
    def save(self, user_id: str, state: SessionState) -> None:
        """Persist the full SessionState for a user (replaces entirely)."""
        pass

    @abstractmethod
    def clear(self, user_id: str) -> None:
        """Reset session for user."""
        pass
