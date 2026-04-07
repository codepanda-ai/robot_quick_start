import logging

from interfaces.tool import ITool
from services.buddy_service import BuddyService


logger = logging.getLogger(__name__)


class SearchBuddiesTool(ITool):
    """Searches for buddies whose interests match an activity type."""

    def __init__(self, buddy_service: BuddyService):
        self._buddy_service = buddy_service

    def name(self) -> str:
        return "search_buddies"

    def description(self) -> str:
        return "Search for buddies who are interested in a specific activity type."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "activity_type": {
                    "type": "string",
                    "description": "The activity type to match (e.g. hiking, dining, beach).",
                },
            },
            "required": ["activity_type"],
        }

    def execute(self, **kwargs) -> dict:
        activity_type = kwargs.get("activity_type", "")
        buddies = (
            self._buddy_service.get_by_activity_type(activity_type)
            if activity_type
            else self._buddy_service.get_all()
        )
        return {"buddies": [b.model_dump() for b in buddies]}
