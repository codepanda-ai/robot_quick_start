from typing import Optional

from interfaces.models import Activity
from data.mock_data import MOCK_ACTIVITIES


class ActivityService:
    """Single access point for activity data."""

    def __init__(self, activities: list[Activity] = None):
        self._activities = activities if activities is not None else MOCK_ACTIVITIES

    def get_all(self) -> list[Activity]:
        return list(self._activities)

    def get_by_id(self, activity_id: Optional[str]) -> Optional[Activity]:
        if not activity_id:
            return None
        return next((a for a in self._activities if a.id == activity_id), None)

    def get_name(self, activity_id: Optional[str], fallback: str = "the activity") -> str:
        activity = self.get_by_id(activity_id)
        return activity.name if activity else fallback
