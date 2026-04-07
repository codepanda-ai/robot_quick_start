import logging

from interfaces.tool import ITool
from services.weather_service import WeatherService


logger = logging.getLogger(__name__)


class GetWeatherTool(ITool):
    """Returns mock weather forecast for a given day."""

    def __init__(self, weather_service: WeatherService):
        self._weather_service = weather_service

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
        forecast = self._weather_service.get_forecast(day)
        return forecast.model_dump() if forecast else {}
