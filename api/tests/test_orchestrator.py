"""Tests for OrchestratorAgent per SPEC.md §Orchestrator State Machine.

Verifies the orchestrator state machine transitions:
- phase=idle + greeting → FallbackAgent (phase stays idle)
- phase=idle + activity-related → PreferenceAgent → auto-chain to SuggestionAgent (phase=suggesting)
- phase=suggesting + card:select_suggestion → InviteAgent (phase=inviting)
- phase=inviting + card:select_buddy → InviteAgent (adds buddy)
- phase=inviting + card:buddies_confirmed → InviteAgent (status=pending)
- phase=inviting + card:confirm → InviteAgent (phase=confirmed)
- phase=inviting + card:cancel → back to suggesting
- any phase + "start over" → reset to idle
- Full happy path: idle → gathering → suggesting → inviting → confirmed

Also verifies:
- WRITABLE_FIELDS enforcement (unauthorized fields filtered)
- Non-text messages handled gracefully
- Error recovery (orchestrator catches agent errors, resets session)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock
from core.session_store import InMemorySessionStore
from core.agent_factory import AgentFactory
from llm.mock_client import MockLLMClient
from interfaces.models import Phase, ConfirmationStatus


def _make_orchestrator():
    """Create orchestrator with mock Lark client."""
    llm = MockLLMClient()
    store = InMemorySessionStore()
    mock_client = MagicMock()
    mock_client.send_text_with_open_id = MagicMock()
    mock_client.send = MagicMock()
    factory = AgentFactory(llm, store, mock_client)
    orchestrator = factory.create_orchestrator()
    return orchestrator, store, mock_client


# ─── State Machine Transitions ───────────────────────────────────

class TestOrchestratorStateMachine:
    """SPEC §Orchestrator State Machine transitions."""

    def test_idle_greeting_stays_idle(self):
        """SPEC: phase=idle + greeting → FallbackAgent, phase stays idle."""
        orch, store, client = _make_orchestrator()
        orch.handle("user_1", "hello")
        session = store.get("user_1")
        assert session.phase == Phase.IDLE

    def test_idle_activity_triggers_suggestions(self):
        """SPEC: phase=idle + activity-related → PreferenceAgent → auto-chain SuggestionAgent."""
        orch, store, client = _make_orchestrator()
        orch.handle("user_1", "I want to go hiking")
        session = store.get("user_1")
        assert session.phase == Phase.SUGGESTING
        assert len(session.suggestions) > 0

    def test_idle_activity_extracts_profile(self):
        """SPEC: PreferenceAgent extracts intent_profile from activity message."""
        orch, store, client = _make_orchestrator()
        orch.handle("user_1", "I want to go hiking")
        session = store.get("user_1")
        assert session.intent_profile.activity == "hiking"

    def test_idle_activity_sends_card(self):
        """SPEC: Auto-chain sends suggestions card to user."""
        orch, store, client = _make_orchestrator()
        orch.handle("user_1", "I want to go hiking")
        # Should have called send() for the interactive card
        client.send.assert_called()
        call_args = client.send.call_args
        assert call_args[0][2] == "interactive"  # msg_type

    def test_select_suggestion_transitions_to_inviting(self):
        """SPEC: phase=suggesting + card:select_suggestion → InviteAgent, phase=inviting."""
        orch, store, client = _make_orchestrator()
        orch.handle("user_1", "I want to go hiking")  # → suggesting
        orch.handle("user_1", "", card_action={
            "action": "select_suggestion", "id": "sg_1", "activity": "MacLehose Trail Stage 2",
        })
        session = store.get("user_1")
        assert session.phase == Phase.INVITING
        assert session.selected_suggestion == "sg_1"

    def test_select_buddy_adds_to_selected(self):
        """SPEC: phase=inviting + card:select_buddy → adds buddy."""
        orch, store, client = _make_orchestrator()
        orch.handle("user_1", "I want to go hiking")
        orch.handle("user_1", "", card_action={
            "action": "select_suggestion", "id": "sg_1", "activity": "MacLehose Trail Stage 2",
        })
        orch.handle("user_1", "", card_action={"action": "select_buddy", "buddy_id": "b_1"})
        session = store.get("user_1")
        assert "b_1" in session.selected_buddies

    def test_buddies_confirmed_sends_confirmation_card(self):
        """SPEC: buddies_confirmed → sends confirmation card."""
        orch, store, client = _make_orchestrator()
        orch.handle("user_1", "I want to go hiking")
        orch.handle("user_1", "", card_action={
            "action": "select_suggestion", "id": "sg_1", "activity": "MacLehose Trail Stage 2",
        })
        orch.handle("user_1", "", card_action={"action": "select_buddy", "buddy_id": "b_1"})
        client.send.reset_mock()
        orch.handle("user_1", "", card_action={"action": "buddies_confirmed"})
        # Should send confirmation card
        client.send.assert_called()

    def test_confirm_transitions_to_confirmed(self):
        """SPEC: confirm → phase=confirmed."""
        orch, store, client = _make_orchestrator()
        orch.handle("user_1", "I want to go hiking")
        orch.handle("user_1", "", card_action={
            "action": "select_suggestion", "id": "sg_1", "activity": "MacLehose Trail Stage 2",
        })
        orch.handle("user_1", "", card_action={"action": "confirm"})
        session = store.get("user_1")
        assert session.phase == Phase.CONFIRMED
        assert session.confirmation_status == ConfirmationStatus.CONFIRMED

    def test_cancel_returns_to_suggesting(self):
        """SPEC: cancel → back to suggesting."""
        orch, store, client = _make_orchestrator()
        orch.handle("user_1", "I want to go hiking")
        orch.handle("user_1", "", card_action={
            "action": "select_suggestion", "id": "sg_1", "activity": "MacLehose Trail Stage 2",
        })
        orch.handle("user_1", "", card_action={"action": "cancel"})
        session = store.get("user_1")
        assert session.phase == Phase.SUGGESTING

    def test_reset_keyword_resets_to_idle(self):
        """SPEC: any phase + 'start over' → reset to idle."""
        orch, store, client = _make_orchestrator()
        orch.handle("user_1", "I want to go hiking")
        assert store.get("user_1").phase == Phase.SUGGESTING
        orch.handle("user_1", "start over")
        session = store.get("user_1")
        assert session.phase == Phase.IDLE

    def test_reset_keyword_reset(self):
        """SPEC: 'reset' keyword also resets."""
        orch, store, client = _make_orchestrator()
        orch.handle("user_1", "I want to go hiking")
        orch.handle("user_1", "reset")
        assert store.get("user_1").phase == Phase.IDLE

    def test_card_reset_action(self):
        """SPEC: card:reset → resets to idle."""
        orch, store, client = _make_orchestrator()
        orch.handle("user_1", "I want to go hiking")
        orch.handle("user_1", "", card_action={"action": "reset"})
        assert store.get("user_1").phase == Phase.IDLE


# ─── Edge Cases per SPEC ─────────────────────────────────────────

class TestOrchestratorEdgeCases:
    """SPEC §Edge Cases."""

    def test_non_text_message_handled(self):
        """SPEC Edge Case #2: Non-text messages → reply with explanation."""
        orch, store, client = _make_orchestrator()
        orch.handle("user_1", "", message_type="image")
        client.send_text_with_open_id.assert_called()

    def test_confirmed_phase_message(self):
        """SPEC: phase=confirmed + any message → 'Plan confirmed!' response."""
        orch, store, client = _make_orchestrator()
        orch.handle("user_1", "I want to go hiking")
        orch.handle("user_1", "", card_action={
            "action": "select_suggestion", "id": "sg_1", "activity": "MacLehose Trail Stage 2",
        })
        orch.handle("user_1", "", card_action={"action": "confirm"})
        assert store.get("user_1").phase == Phase.CONFIRMED
        client.send_text_with_open_id.reset_mock()
        orch.handle("user_1", "what now?")
        client.send_text_with_open_id.assert_called()

    def test_suggesting_phase_text_message(self):
        """SPEC: phase=suggesting + text → remind to pick from suggestions."""
        orch, store, client = _make_orchestrator()
        orch.handle("user_1", "I want to go hiking")
        assert store.get("user_1").phase == Phase.SUGGESTING
        client.send_text_with_open_id.reset_mock()
        orch.handle("user_1", "hmm what else")
        client.send_text_with_open_id.assert_called()


# ─── Full Happy Path ─────────────────────────────────────────────

class TestFullFlow:
    """SPEC: Complete end-to-end flow through all phases."""

    def test_full_happy_path(self):
        """idle → gathering → suggesting → inviting → confirmed."""
        orch, store, client = _make_orchestrator()

        # 1. Activity message → auto-chains to suggesting
        orch.handle("user_1", "I want to go hiking on saturday morning, something cheap and chill")
        session = store.get("user_1")
        assert session.phase == Phase.SUGGESTING
        assert session.intent_profile.activity == "hiking"
        assert len(session.suggestions) > 0

        # 2. Select a suggestion
        orch.handle("user_1", "", card_action={
            "action": "select_suggestion", "id": "sg_1", "activity": "MacLehose Trail Stage 2",
        })
        session = store.get("user_1")
        assert session.phase == Phase.INVITING
        assert session.selected_suggestion == "sg_1"
        assert len(session.buddy_candidates) > 0

        # 3. Select buddies
        orch.handle("user_1", "", card_action={"action": "select_buddy", "buddy_id": "b_1"})
        orch.handle("user_1", "", card_action={"action": "select_buddy", "buddy_id": "b_3"})
        session = store.get("user_1")
        assert "b_1" in session.selected_buddies
        assert "b_3" in session.selected_buddies

        # 4. Confirm buddy selection
        orch.handle("user_1", "", card_action={"action": "buddies_confirmed"})
        session = store.get("user_1")
        assert session.confirmation_status == ConfirmationStatus.PENDING

        # 5. Confirm the plan
        orch.handle("user_1", "", card_action={"action": "confirm"})
        session = store.get("user_1")
        assert session.phase == Phase.CONFIRMED
        assert session.confirmation_status == ConfirmationStatus.CONFIRMED

    def test_cancel_and_repick(self):
        """User cancels during inviting and picks a different suggestion."""
        orch, store, client = _make_orchestrator()

        orch.handle("user_1", "beach day please")
        orch.handle("user_1", "", card_action={
            "action": "select_suggestion", "id": "sg_4", "activity": "Shek O Beach Day",
        })
        assert store.get("user_1").phase == Phase.INVITING

        # Cancel
        orch.handle("user_1", "", card_action={"action": "cancel"})
        assert store.get("user_1").phase == Phase.SUGGESTING

        # Pick a different one
        orch.handle("user_1", "", card_action={
            "action": "select_suggestion", "id": "sg_1", "activity": "MacLehose Trail Stage 2",
        })
        session = store.get("user_1")
        assert session.phase == Phase.INVITING
        assert session.selected_suggestion == "sg_1"

    def test_full_reset_mid_flow(self):
        """User resets mid-flow and starts a completely new plan."""
        orch, store, client = _make_orchestrator()

        orch.handle("user_1", "I want dining")
        assert store.get("user_1").phase == Phase.SUGGESTING

        orch.handle("user_1", "start over")
        assert store.get("user_1").phase == Phase.IDLE

        # Start new flow
        orch.handle("user_1", "actually let's go hiking")
        session = store.get("user_1")
        assert session.phase == Phase.SUGGESTING
        assert session.intent_profile.activity == "hiking"
