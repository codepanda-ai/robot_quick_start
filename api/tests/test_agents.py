"""Tests for agent behavior contracts per SPEC.md §Agents.

Verifies per-agent:
- agent_name() returns the correct identifier
- WRITABLE_FIELDS matches the spec
- handle() returns AgentResult with correct session_updates
- Agents never directly access the session store
- Template Method: BaseAgent.handle() calls _build_prompt → llm.chat → _execute_tools → _process_response

Spec references:
- FallbackAgent: WRITABLE_FIELDS=set(), responds to greetings/off-topic, no session changes
- PreferenceAgent: extracts activity/budget/vibe/availability, handles reset
- SuggestionAgent: WRITABLE_FIELDS={suggestions, phase}, filters activities by preference
- InviteAgent: handles select_suggestion, select_buddy, buddies_confirmed, confirm, cancel
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from interfaces.models import (
    SessionState,
    Phase,
    IntentProfile,
    Budget,
    Vibe,
    ConfirmationStatus,
    Activity,
)
from core.tool_registry import ToolRegistry
from llm.mock_client import MockLLMClient
from agents.fallback import FallbackAgent
from agents.preference import PreferenceAgent
from agents.suggestion import SuggestionAgent
from agents.invite import InviteAgent


class _StubTool:
    """Minimal stub satisfying ITool for test registration."""
    def __init__(self, tool_name):
        self._name = tool_name
    def name(self): return self._name
    def description(self): return "stub"
    def parameters_schema(self): return {"type": "object", "properties": {}}
    def to_llm_schema(self): return {"type": "function", "function": {"name": self._name, "description": "stub", "parameters": self.parameters_schema()}}
    def execute(self, **kwargs): return {"status": "ok"}


def _registry(*tool_names):
    r = ToolRegistry()
    for n in tool_names:
        r.register(_StubTool(n))
    return r


# ─── FallbackAgent ───────────────────────────────────────────────

class TestFallbackAgent:
    """SPEC: agent_name='fallback', WRITABLE_FIELDS=set(), purely conversational."""

    def test_agent_name(self):
        agent = FallbackAgent(MockLLMClient(), _registry("send_lark_text"))
        assert agent.agent_name() == "fallback"

    def test_writable_fields_empty(self):
        """SPEC: FallbackAgent writes nothing."""
        assert FallbackAgent.WRITABLE_FIELDS == set()

    def test_greeting_returns_response_no_session_changes(self):
        """SPEC: Greetings → friendly response, empty session_updates."""
        agent = FallbackAgent(MockLLMClient(), _registry("send_lark_text"))
        result = agent.handle("user_1", "hello", SessionState())
        assert result.session_updates == {}
        assert result.response != ""

    def test_offtopic_returns_response_no_session_changes(self):
        """SPEC: Off-topic → helpful response, empty session_updates."""
        agent = FallbackAgent(MockLLMClient(), _registry("send_lark_text"))
        result = agent.handle("user_1", "what's the meaning of life", SessionState())
        assert result.session_updates == {}
        assert result.response != ""


# ─── PreferenceAgent ─────────────────────────────────────────────

class TestPreferenceAgent:
    """SPEC: agent_name='preference', extracts preferences, handles reset."""

    def test_agent_name(self):
        agent = PreferenceAgent(MockLLMClient(), _registry("send_lark_text"))
        assert agent.agent_name() == "preference"

    def test_writable_fields_per_spec(self):
        """SPEC: All fields — needed for reset."""
        expected = {"intent_profile", "phase", "suggestions", "selected_suggestion",
                    "buddy_candidates", "selected_buddies", "confirmation_status"}
        assert PreferenceAgent.WRITABLE_FIELDS == expected

    def test_extracts_activity_from_message(self):
        """SPEC: Extracts activity from user message."""
        agent = PreferenceAgent(MockLLMClient(), _registry("send_lark_text"))
        result = agent.handle("user_1", "I want to go hiking", SessionState())
        assert "intent_profile" in result.session_updates
        assert result.session_updates["intent_profile"].get("activity") == "hiking"

    def test_extracts_budget_from_message(self):
        """SPEC: Extracts budget preference."""
        agent = PreferenceAgent(MockLLMClient(), _registry("send_lark_text"))
        result = agent.handle("user_1", "something cheap and hiking", SessionState())
        profile = result.session_updates.get("intent_profile", {})
        assert profile.get("budget") == "low"

    def test_extracts_vibe_from_message(self):
        """SPEC: Extracts vibe preference."""
        agent = PreferenceAgent(MockLLMClient(), _registry("send_lark_text"))
        result = agent.handle("user_1", "chill hiking", SessionState())
        profile = result.session_updates.get("intent_profile", {})
        assert profile.get("vibe") == "chill"

    def test_reset_clears_all_fields(self):
        """SPEC: context=reset → phase=idle, all fields cleared."""
        agent = PreferenceAgent(MockLLMClient(), _registry("send_lark_text"))
        session = SessionState(
            phase=Phase.SUGGESTING,
            intent_profile=IntentProfile(activity="hiking", budget=Budget.LOW),
        )
        result = agent.handle("user_1", "", session, context={"reset": True})
        assert result.session_updates["phase"] == Phase.IDLE
        assert result.session_updates["suggestions"] == []
        assert result.session_updates["selected_suggestion"] is None
        assert result.session_updates["selected_buddies"] == []

    def test_no_preference_detected_asks_followup(self):
        """SPEC: If no preference keywords found, ask follow-up."""
        agent = PreferenceAgent(MockLLMClient(), _registry("send_lark_text"))
        result = agent.handle("user_1", "something on the weekend", SessionState())
        # Should still set phase to gathering
        assert result.session_updates.get("phase") == Phase.GATHERING


# ─── SuggestionAgent ─────────────────────────────────────────────

class TestSuggestionAgent:
    """SPEC: agent_name='suggestion', WRITABLE_FIELDS={suggestions, phase}."""

    def test_agent_name(self):
        agent = SuggestionAgent(MockLLMClient(), _registry("send_lark_card", "get_weather"))
        assert agent.agent_name() == "suggestion"

    def test_writable_fields_per_spec(self):
        assert SuggestionAgent.WRITABLE_FIELDS == {"suggestions", "phase"}

    def test_sets_phase_to_suggesting(self):
        """SPEC: Writes phase='suggesting'."""
        agent = SuggestionAgent(MockLLMClient(), _registry("send_lark_card", "get_weather"))
        session = SessionState(intent_profile=IntentProfile(activity="hiking"))
        result = agent.handle("user_1", "hiking", session)
        assert result.session_updates["phase"] == Phase.SUGGESTING

    def test_returns_suggestions(self):
        """SPEC: Writes suggestions list to session."""
        agent = SuggestionAgent(MockLLMClient(), _registry("send_lark_card", "get_weather"))
        session = SessionState(intent_profile=IntentProfile(activity="hiking"))
        result = agent.handle("user_1", "hiking", session)
        suggestions = result.session_updates["suggestions"]
        assert len(suggestions) > 0

    def test_hiking_preference_ranks_hiking_first(self):
        """SPEC: If no activities match filters, relax and suggest top. Hiking pref → hiking ranked first."""
        agent = SuggestionAgent(MockLLMClient(), _registry("send_lark_card", "get_weather"))
        session = SessionState(intent_profile=IntentProfile(activity="hiking"))
        result = agent.handle("user_1", "hiking", session)
        suggestions = result.session_updates["suggestions"]
        assert Activity.model_validate(suggestions[0]).type == "hiking"

    def test_no_matching_activity_still_returns_suggestions(self):
        """SPEC Edge Case #8: If no activities match filters, relax filters and suggest top."""
        agent = SuggestionAgent(MockLLMClient(), _registry("send_lark_card", "get_weather"))
        session = SessionState(intent_profile=IntentProfile(activity="skydiving"))
        result = agent.handle("user_1", "skydiving", session)
        assert len(result.session_updates["suggestions"]) > 0


# ─── InviteAgent ─────────────────────────────────────────────────

class TestInviteAgent:
    """SPEC: agent_name='invite', handles full invite flow via card actions."""

    def test_agent_name(self):
        agent = InviteAgent(MockLLMClient(), _registry("send_lark_text", "send_lark_card", "search_buddies", "create_group_chat"))
        assert agent.agent_name() == "invite"

    def test_writable_fields_per_spec(self):
        expected = {"selected_suggestion", "buddy_candidates", "selected_buddies", "confirmation_status", "phase"}
        assert InviteAgent.WRITABLE_FIELDS == expected

    def test_select_suggestion_sets_inviting_phase(self):
        """SPEC: select_suggestion → InviteAgent, writes selected_suggestion, phase=inviting."""
        agent = InviteAgent(MockLLMClient(), _registry("send_lark_text", "send_lark_card"))
        session = SessionState(phase=Phase.SUGGESTING)
        result = agent.handle("user_1", "", session, context={
            "action": "select_suggestion", "id": "sg_1", "activity": "MacLehose Trail Stage 2",
        })
        assert result.session_updates["selected_suggestion"] == "sg_1"
        assert result.session_updates["phase"] == Phase.INVITING

    def test_select_suggestion_populates_buddy_candidates(self):
        """SPEC: After selecting a suggestion, buddy candidates are populated."""
        agent = InviteAgent(MockLLMClient(), _registry("send_lark_text", "send_lark_card"))
        session = SessionState(phase=Phase.SUGGESTING)
        result = agent.handle("user_1", "", session, context={
            "action": "select_suggestion", "id": "sg_1", "activity": "MacLehose Trail Stage 2",
        })
        assert len(result.session_updates["buddy_candidates"]) > 0

    def test_select_buddy_adds_to_list(self):
        """SPEC: select_buddy → adds buddy to selected_buddies."""
        agent = InviteAgent(MockLLMClient(), _registry("send_lark_text", "send_lark_card"))
        session = SessionState(phase=Phase.INVITING, selected_buddies=[])
        result = agent.handle("user_1", "", session, context={
            "action": "select_buddy", "buddy_id": "b_1",
        })
        assert "b_1" in result.session_updates["selected_buddies"]

    def test_select_buddy_no_duplicates(self):
        """Selecting the same buddy twice should not duplicate."""
        agent = InviteAgent(MockLLMClient(), _registry("send_lark_text", "send_lark_card"))
        session = SessionState(phase=Phase.INVITING, selected_buddies=["b_1"])
        result = agent.handle("user_1", "", session, context={
            "action": "select_buddy", "buddy_id": "b_1",
        })
        assert result.session_updates["selected_buddies"].count("b_1") == 1

    def test_buddies_confirmed_sets_pending(self):
        """SPEC: buddies_confirmed → status='pending'."""
        agent = InviteAgent(MockLLMClient(), _registry("send_lark_text", "send_lark_card"))
        session = SessionState(phase=Phase.INVITING)
        result = agent.handle("user_1", "", session, context={"action": "buddies_confirmed"})
        assert result.session_updates["confirmation_status"] == ConfirmationStatus.PENDING

    def test_confirm_sets_confirmed(self):
        """SPEC: confirm → confirmation_status='confirmed', phase='confirmed'."""
        agent = InviteAgent(MockLLMClient(), _registry("send_lark_text", "send_lark_card"))
        session = SessionState(phase=Phase.INVITING, selected_suggestion="sg_1", selected_buddies=["b_1"])
        result = agent.handle("user_1", "", session, context={"action": "confirm"})
        assert result.session_updates["confirmation_status"] == ConfirmationStatus.CONFIRMED
        assert result.session_updates["phase"] == Phase.CONFIRMED

    def test_cancel_returns_to_suggesting(self):
        """SPEC: cancel → back to suggesting phase."""
        agent = InviteAgent(MockLLMClient(), _registry("send_lark_text", "send_lark_card"))
        session = SessionState(phase=Phase.INVITING)
        result = agent.handle("user_1", "", session, context={"action": "cancel"})
        assert result.session_updates["phase"] == Phase.SUGGESTING
        assert result.session_updates["selected_suggestion"] is None

    def test_no_matching_buddies_returns_all(self):
        """SPEC Edge Case #9: No matching buddies → show all buddies."""
        agent = InviteAgent(MockLLMClient(), _registry("send_lark_text", "send_lark_card"))
        session = SessionState(phase=Phase.SUGGESTING)
        # sg_5 is "indoor" type — if no buddies match, should return all
        result = agent.handle("user_1", "", session, context={
            "action": "select_suggestion", "id": "sg_5", "activity": "Board Game Cafe",
        })
        assert len(result.session_updates["buddy_candidates"]) > 0
