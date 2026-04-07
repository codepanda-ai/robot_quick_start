from interfaces.models import Buddy
from data.mock_data import MOCK_BUDDIES


class BuddyService:
    """Single access point for buddy data."""

    def __init__(self, buddies: list[Buddy] = None):
        self._buddies = buddies if buddies is not None else MOCK_BUDDIES

    def get_all(self) -> list[Buddy]:
        return list(self._buddies)

    def get_by_ids(self, buddy_ids: list) -> list[Buddy]:
        return [b for b in self._buddies if b.id in buddy_ids]

    def get_by_activity_type(self, activity_type: str) -> list[Buddy]:
        """Return buddies whose interests include the activity type; falls back to all buddies."""
        matches = [b for b in self._buddies if activity_type.lower() in b.interests]
        return matches if matches else list(self._buddies)
