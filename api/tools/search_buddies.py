import logging

from interfaces.tool import ITool
from data.mock_data import MOCK_BUDDIES


logger = logging.getLogger(__name__)


class SearchBuddiesTool(ITool):
    """Searches for buddies whose interests match an activity type."""

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
        if not activity_type:
            buddies = MOCK_BUDDIES
        else:
            buddies = [b for b in MOCK_BUDDIES if activity_type.lower() in b.interests]
            if not buddies:
                buddies = MOCK_BUDDIES
                logger.info("No exact buddy match for '%s', returning all buddies", activity_type)
        return {"buddies": [b.model_dump() for b in buddies]}
