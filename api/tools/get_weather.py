import logging

from interfaces.tool import ITool
from data.mock_data import MOCK_WEATHER


logger = logging.getLogger(__name__)


class GetWeatherTool(ITool):
    """Returns mock weather forecast for a given day."""

    def name(self) -> str:
        return "get_weather"

    def description(self) -> str:
        return "Get the weather forecast for a specific day (Saturday or Sunday)."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "day": {
                    "type": "string",
                    "enum": ["Saturday", "Sunday"],
                    "description": "The day to get the forecast for.",
                },
            },
            "required": ["day"],
        }

    def execute(self, **kwargs) -> dict:
        day = kwargs.get("day", "Saturday")
        for forecast in MOCK_WEATHER:
            if forecast.day.lower() == day.lower():
                return forecast.model_dump()
        return MOCK_WEATHER[0].model_dump()
