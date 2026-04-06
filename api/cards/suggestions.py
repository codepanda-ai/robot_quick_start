from typing import Union, Optional

from interfaces.models import Activity, WeatherForecast


def _as_activity(s: Union[Activity, dict]) -> Activity:
    return Activity.model_validate(s) if isinstance(s, dict) else s


def build_suggestions_card(suggestions: list[Activity], weather: WeatherForecast = None) -> dict:
    """Build a Lark interactive card displaying activity suggestions."""
    elements = []

    # Weather info
    if weather:
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"🌤 **{weather.day} Forecast**: {weather.condition}, {weather.temp}°C, Humidity {weather.humidity}%",
            },
        })
        elements.append({"tag": "hr"})

    # Suggestion items
    for raw in suggestions:
        suggestion = _as_activity(raw)
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**{suggestion.name}**\n{suggestion.reason}\n💰 Budget: {suggestion.budget.value} · ✨ Vibe: {suggestion.vibe.value}",
            },
        })
        elements.append({
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "Pick this! 👈"},
                    "type": "primary",
                    "value": {
                        "action": "select_suggestion",
                        "id": suggestion.id,
                        "activity": suggestion.name,
                    },
                }
            ],
        })
        elements.append({"tag": "hr"})

    # Reset button
    elements.append({
        "tag": "action",
        "actions": [
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "Start Over 🔄"},
                "type": "default",
                "value": {"action": "reset"},
            }
        ],
    })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "🎯 Weekend Suggestions"},
            "template": "green",
        },
        "elements": elements,
    }


def build_selected_suggestions_card(
    suggestions: list[Activity],
    selected_id: str,
    weather: Optional[WeatherForecast] = None,
) -> dict:
    """Re-render the suggestions card in-place after the user picks one.

    The selected suggestion shows a '✅ Your Pick!' label.
    All other suggestion buttons are removed.
    The 'Start Over' button is removed — flow continues automatically.
    Returned as the `card` key of the Lark callback response to update the card in-place.
    """
    elements = []

    if weather:
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"🌤 **{weather.day} Forecast**: {weather.condition}, {weather.temp}°C, Humidity {weather.humidity}%",
            },
        })
        elements.append({"tag": "hr"})

    for raw in suggestions:
        suggestion = _as_activity(raw)
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**{suggestion.name}**\n{suggestion.reason}\n💰 Budget: {suggestion.budget.value} · ✨ Vibe: {suggestion.vibe.value}",
            },
        })
        if suggestion.id == selected_id:
            elements.append({
                "tag": "div",
                "text": {"tag": "plain_text", "content": "✅ Your Pick!"},
            })
        elements.append({"tag": "hr"})

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "🎯 Weekend Suggestions"},
            "template": "green",
        },
        "elements": elements,
    }
