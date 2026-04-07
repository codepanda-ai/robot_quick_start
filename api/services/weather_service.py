from typing import Optional

from interfaces.models import WeatherForecast
from data.mock_data import MOCK_WEATHER


class WeatherService:
    """Single access point for weather forecast data."""

    def __init__(self, forecasts: list[WeatherForecast] = None):
        self._forecasts = forecasts if forecasts is not None else MOCK_WEATHER

    def get_forecast(self, day: str = "Saturday") -> Optional[WeatherForecast]:
        return next(
            (f for f in self._forecasts if f.day.lower() == day.lower()),
            self._forecasts[0] if self._forecasts else None,
        )
