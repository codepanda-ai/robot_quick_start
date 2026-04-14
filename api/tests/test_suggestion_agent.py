import json
from unittest.mock import MagicMock

import pytest

from agents.suggestion import SuggestionAgent
from interfaces.llm_client import LLMResponse, ToolCall, FinishReason
from interfaces.models import SessionState, IntentProfile, Phase
from services.activity_service import ActivityService


HIKING_SUGGESTIONS_JSON = json.dumps({"suggestions": [
    {"id": "sg_1", "reason": "Great weather for MacLehose Trail!"},
    {"id": "sg_6", "reason": "Clear skies on the Peak."},
    {"id": "sg_4", "reason": "Beach day is on."},
]})

DINING_SUGGESTIONS_JSON = json.dumps({"suggestions": [
    {"id": "sg_3", "reason": "Perfect spot for a chill brunch."},
    {"id": "sg_2", "reason": "Fun nightlife option nearby."},
    {"id": "sg_5", "reason": "Great social vibe at the cafe."},
]})


@pytest.fixture
def activity_service():
    return ActivityService()


@pytest.fixture
def tool_registry():
    registry = MagicMock()
    registry.get_schemas.return_value = [
        {"type": "function", "function": {"name": "get_weather", "description": "Get weather", "parameters": {}}}
    ]
    registry.execute.return_value = {"day": "Saturday", "temp": 26, "condition": "Sunny", "humidity": 65}
    return registry


class TestSuggestionAgentOutdoor:
    """Outdoor preference (hiking) should trigger a two-turn loop: fetch weather, then rank."""

    def test_outdoor_takes_two_turns(self, activity_service, tool_registry):
        llm = MagicMock()
        llm.chat.side_effect = [
            LLMResponse(
                content="",
                tool_calls=[ToolCall(name="get_weather", arguments={"day": "Saturday"})],
                finish_reason=FinishReason.TOOL_USE,
            ),
            LLMResponse(
                content=HIKING_SUGGESTIONS_JSON,
                finish_reason=FinishReason.STOP,
            ),
        ]

        agent = SuggestionAgent(llm, tool_registry, activity_service)
        session = SessionState(intent_profile=IntentProfile(activity="hiking"))

        result = agent.handle("user_1", "suggest something", session)

        assert llm.chat.call_count == 2
        tool_registry.execute.assert_called_once_with("get_weather", day="Saturday", open_id="user_1")
        assert result.session_updates["phase"] == Phase.SUGGESTING
        suggestions = result.session_updates["suggestions"]
        assert len(suggestions) == 3
        assert [s.id for s in suggestions] == ["sg_1", "sg_6", "sg_4"]
        assert suggestions[0].reason == "Great weather for MacLehose Trail!"


class TestSuggestionAgentIndoor:
    """Indoor preference (dining) should complete in a single turn with no tool calls."""

    def test_indoor_takes_one_turn(self, activity_service, tool_registry):
        llm = MagicMock()
        llm.chat.return_value = LLMResponse(
            content=DINING_SUGGESTIONS_JSON,
            finish_reason=FinishReason.STOP,
        )

        agent = SuggestionAgent(llm, tool_registry, activity_service)
        session = SessionState(intent_profile=IntentProfile(activity="dining"))

        result = agent.handle("user_1", "suggest something", session)

        assert llm.chat.call_count == 1
        tool_registry.execute.assert_not_called()
        assert result.session_updates["phase"] == Phase.SUGGESTING
        suggestions = result.session_updates["suggestions"]
        assert len(suggestions) == 3
        assert [s.id for s in suggestions] == ["sg_3", "sg_2", "sg_5"]
        assert suggestions[0].reason == "Perfect spot for a chill brunch."
