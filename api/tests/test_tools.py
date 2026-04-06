"""Tests for tool contracts per SPEC.md §Tools.

Verifies each tool:
- Implements ITool interface (name, description, parameters_schema, execute, to_llm_schema)
- Returns correct result dict structure
- Handles edge cases (missing params, no matches)

SPEC references:
- SendTextTool: wraps send_text_with_open_id()
- SendCardTool: wraps send() with msg_type="interactive"
- GetWeatherTool: returns from MOCK_WEATHER
- SearchBuddiesTool: filters MOCK_BUDDIES by activity type
- CreateGroupChatTool: wraps Lark create chat API (mock)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock
from tools.send_text import SendTextTool
from tools.send_card import SendCardTool
from tools.get_weather import GetWeatherTool
from tools.search_buddies import SearchBuddiesTool
from tools.create_group_chat import CreateGroupChatTool


# ─── ITool Interface Contract ────────────────────────────────────

class TestIToolContract:
    """All tools must satisfy the ITool interface."""

    def _all_tools(self):
        mock_client = MagicMock()
        return [
            SendTextTool(mock_client),
            SendCardTool(mock_client),
            GetWeatherTool(),
            SearchBuddiesTool(),
            CreateGroupChatTool(mock_client),
        ]

    def test_all_tools_have_name(self):
        for tool in self._all_tools():
            assert isinstance(tool.name(), str)
            assert len(tool.name()) > 0

    def test_all_tools_have_description(self):
        for tool in self._all_tools():
            assert isinstance(tool.description(), str)

    def test_all_tools_have_parameters_schema(self):
        for tool in self._all_tools():
            schema = tool.parameters_schema()
            assert isinstance(schema, dict)
            assert schema.get("type") == "object"

    def test_all_tools_produce_llm_schema(self):
        """SPEC: to_llm_schema() returns LLM function-calling format."""
        for tool in self._all_tools():
            schema = tool.to_llm_schema()
            assert schema["type"] == "function"
            assert "function" in schema
            assert "name" in schema["function"]
            assert "description" in schema["function"]
            assert "parameters" in schema["function"]


# ─── SendTextTool ────────────────────────────────────────────────

class TestSendTextTool:
    """SPEC: wraps send_text_with_open_id()."""

    def test_sends_text_via_client(self):
        client = MagicMock()
        tool = SendTextTool(client)
        result = tool.execute(open_id="ou_123", text="Hello!")
        assert result["status"] == "sent"
        client.send_text_with_open_id.assert_called_once()

    def test_missing_open_id_returns_error(self):
        client = MagicMock()
        tool = SendTextTool(client)
        result = tool.execute(text="Hello!")
        assert "error" in result


# ─── SendCardTool ────────────────────────────────────────────────

class TestSendCardTool:
    """SPEC: wraps send() with msg_type='interactive'."""

    def test_sends_card_via_client(self):
        client = MagicMock()
        tool = SendCardTool(client)
        result = tool.execute(open_id="ou_123", card_content={"header": {}})
        assert result["status"] == "sent"
        client.send.assert_called_once()
        # Verify msg_type is "interactive"
        call_args = client.send.call_args
        assert call_args[0][2] == "interactive"


# ─── GetWeatherTool ──────────────────────────────────────────────

class TestGetWeatherTool:
    """SPEC: Returns from MOCK_WEATHER (Saturday/Sunday)."""

    def test_saturday_weather(self):
        tool = GetWeatherTool()
        result = tool.execute(day="Saturday")
        assert result["day"] == "Saturday"
        assert "temp" in result
        assert "condition" in result
        assert "humidity" in result

    def test_sunday_weather(self):
        tool = GetWeatherTool()
        result = tool.execute(day="Sunday")
        assert result["day"] == "Sunday"

    def test_unknown_day_fallback(self):
        """SPEC: Should not crash on unknown day."""
        tool = GetWeatherTool()
        result = tool.execute(day="Wednesday")
        assert "day" in result


# ─── SearchBuddiesTool ───────────────────────────────────────────

class TestSearchBuddiesTool:
    """SPEC: Filters MOCK_BUDDIES by activity type."""

    def test_hiking_returns_hiking_buddies(self):
        tool = SearchBuddiesTool()
        result = tool.execute(activity_type="hiking")
        buddies = result["buddies"]
        assert len(buddies) > 0
        assert all("hiking" in b["interests"] for b in buddies)

    def test_dining_returns_dining_buddies(self):
        tool = SearchBuddiesTool()
        result = tool.execute(activity_type="dining")
        buddies = result["buddies"]
        assert all("dining" in b["interests"] for b in buddies)

    def test_no_match_returns_all_buddies(self):
        """SPEC Edge Case #9: No matching buddies → return all."""
        tool = SearchBuddiesTool()
        result = tool.execute(activity_type="skydiving")
        assert len(result["buddies"]) > 0

    def test_empty_activity_returns_all_buddies(self):
        tool = SearchBuddiesTool()
        result = tool.execute(activity_type="")
        assert len(result["buddies"]) > 0


# ─── CreateGroupChatTool ─────────────────────────────────────────

class TestCreateGroupChatTool:
    """SPEC: wraps Lark create chat API (mock)."""

    def test_creates_chat(self):
        client = MagicMock()
        tool = CreateGroupChatTool(client)
        result = tool.execute(chat_name="Weekend Hike", user_ids=["ou_1", "ou_2"])
        assert result["status"] == "created"
        assert result["chat_name"] == "Weekend Hike"
        assert len(result["members"]) == 2
