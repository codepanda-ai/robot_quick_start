import json
import logging
import re
from typing import Optional

from interfaces.agent import IAgent, AgentResult
from interfaces.models import Phase, SessionState
from core.session_service import SessionService
from cards.suggestions import build_suggestions_card
from cards.buddies import build_buddy_card, build_locked_buddy_card
from cards.confirmation import build_invite_preview_card, build_confirmed_card
from data.mock_data import MOCK_ACTIVITIES, MOCK_BUDDIES, MOCK_WEATHER


logger = logging.getLogger(__name__)

RESET_KEYWORDS = {"start over", "reset", "cancel", "restart", "new plan"}


class OrchestratorAgent:
    """Routes messages and card actions to the appropriate agent based on session phase.

    Card action handlers return a dict that is forwarded directly as the Lark callback
    response body. When the dict contains a 'card' key, Lark updates the original card
    in-place. A 'toast' key shows a brief notification to the user.
    """

    def __init__(
        self,
        fallback_agent: IAgent,
        preference_agent: IAgent,
        suggestion_agent: IAgent,
        invite_agent: IAgent,
        confirmation_agent: IAgent,
        session_service: SessionService,
        message_api_client,
    ):
        self._fallback = fallback_agent
        self._preference = preference_agent
        self._suggestion = suggestion_agent
        self._invite = invite_agent
        self._confirmation = confirmation_agent
        self._session_service = session_service
        self._msg_client = message_api_client

    def handle(self, user_id: str, message: str, message_type: str = "text", card_action: Optional[dict] = None) -> dict:
        """Main entry point.

        Returns a dict suitable for the Lark callback HTTP response.
        For text messages this is always {}.
        For card actions it may contain 'card' (in-place update) and/or 'toast'.
        """
        try:
            session = self._session_service.get_session(user_id)

            if card_action:
                return self._handle_card_action(user_id, session, card_action)

            if message_type != "text":
                self._send_text(user_id, "I can only process text messages for now. Tell me what you'd like to do this weekend!")
                return {}

            # Reset keywords work from any phase
            if message.lower().strip() in RESET_KEYWORDS:
                self._route_to_agent(user_id, self._preference, message, session, context={"reset": True})
                self._send_text(user_id, "Let's start fresh! What would you like to do this weekend?")
                return {}

            # Route by phase
            phase = session.phase
            if phase == Phase.IDLE:
                self._handle_idle(user_id, message, session)
            elif phase == Phase.GATHERING:
                self._handle_gathering(user_id, message, session)
            elif phase == Phase.SUGGESTING:
                self._send_text(user_id, "Check out the suggestions above! Pick one you like, or say 'start over' to reset.")
            elif phase == Phase.INVITING:
                self._send_text(user_id, "Select your buddies from the card above, or say 'start over' to reset.")
            elif phase == Phase.CONFIRMED:
                self._send_text(user_id, "Your plan is confirmed! 🎉 Say 'start over' to plan something new.")
            else:
                self._route_to_agent(user_id, self._fallback, message, session)

        except Exception as e:
            logger.error("Orchestrator error for user %s: %s", user_id, e, exc_info=True)
            self._send_text(user_id, "Something went wrong. Let's try again — what would you like to do this weekend?")
            self._session_service.reset_session(user_id)

        return {}

    # ─── Text message routing ─────────────────────────────────────────

    @staticmethod
    def _profile_is_complete(profile) -> bool:
        """Returns True when all 5 preference fields have been collected."""
        return all([
            profile.activity,
            profile.budget,
            profile.vibe,
            profile.location,
            profile.availability,
        ])

    @staticmethod
    def _is_greeting(text: str, greeting_keywords) -> bool:
        """Whole-word match so 'hiking' doesn't trigger on the 'hi' inside it."""
        return any(re.search(r"\b" + re.escape(kw) + r"\b", text) for kw in greeting_keywords)

    def _handle_idle(self, user_id: str, message: str, session: SessionState):
        from llm.mock_client import ACTIVITY_KEYWORDS, GREETING_KEYWORDS
        text = message.lower().strip()
        if self._is_greeting(text, GREETING_KEYWORDS):
            self._route_to_agent(user_id, self._fallback, message, session)
        elif any(kw in text for kw in ACTIVITY_KEYWORDS) or len(text) >= 10:
            # Route to PreferenceAgent for activity keywords or any substantive sentence
            self._route_to_agent(user_id, self._preference, message, session)
            updated = self._session_service.get_session(user_id)
            if self._profile_is_complete(updated.intent_profile):
                self._auto_chain_to_suggestions(user_id, message, updated)
        else:
            self._route_to_agent(user_id, self._fallback, message, session)

    def _handle_gathering(self, user_id: str, message: str, session: SessionState):
        self._route_to_agent(user_id, self._preference, message, session)
        updated = self._session_service.get_session(user_id)
        if self._profile_is_complete(updated.intent_profile):
            self._auto_chain_to_suggestions(user_id, message, updated)

    def _auto_chain_to_suggestions(self, user_id: str, message: str, session: SessionState):
        self._route_to_agent(user_id, self._suggestion, message, session)
        updated = self._session_service.get_session(user_id)
        weather = MOCK_WEATHER[0] if MOCK_WEATHER else None
        if updated.suggestions:
            self._send_card(user_id, build_suggestions_card(updated.suggestions, weather))

    # ─── Card action routing ──────────────────────────────────────────

    def _handle_card_action(self, user_id: str, session: SessionState, card_action: dict) -> dict:
        """Dispatch card action and return Lark callback response dict."""
        action = card_action.get("action", "")

        if action == "reset":
            return self._on_reset(user_id, session)

        if action == "select_suggestion":
            return self._on_select_suggestion(user_id, session, card_action)

        if action == "select_buddy":
            return self._on_select_buddy(user_id, session, card_action)

        if action in ("buddies_confirmed", "go_solo"):
            return self._on_buddies_done(user_id, session, card_action)

        if action == "accept_invite":
            return self._on_accept_invite(user_id, session)

        if action == "reject_invite":
            return self._on_reject_invite(user_id, session)

        if action == "cancel":
            return self._on_cancel(user_id, session)

        if action == "quick_preference":
            self._route_to_agent(user_id, self._preference, card_action.get("activity", ""), session)
            return {"toast": {"type": "info", "content": "Got it!"}}

        logger.warning("Unknown card action '%s' for user %s", action, user_id)
        return {}

    def _on_reset(self, user_id: str, session: SessionState) -> dict:
        self._route_to_agent(user_id, self._preference, "", session, context={"reset": True})
        self._send_text(user_id, "Let's start fresh! What would you like to do this weekend?")
        return {"toast": {"type": "info", "content": "Starting fresh! 🔄"}}

    def _on_select_suggestion(self, user_id: str, session: SessionState, card_action: dict) -> dict:
        self._route_to_agent(user_id, self._invite, "", session, context=card_action)
        updated = self._session_service.get_session(user_id)

        # Send NEW buddy card as a new message
        weather = MOCK_WEATHER[0] if MOCK_WEATHER else None
        activity_name = card_action.get("activity", "the activity")
        self._send_card(user_id, build_buddy_card(updated.buddy_candidates, activity_name))

        return {"toast": {"type": "info", "content": f"✅ '{activity_name}' selected! Now pick your buddies."}}

    def _on_select_buddy(self, user_id: str, session: SessionState, card_action: dict) -> dict:
        self._route_to_agent(user_id, self._invite, "", session, context=card_action)
        updated = self._session_service.get_session(user_id)

        # Resolve activity name
        activity_name = self._resolve_activity_name(updated.selected_suggestion)

        # Resolve the buddy's name for a personalised toast
        buddy_id = card_action.get("buddy_id", "")
        buddy_name = next((b.name for b in MOCK_BUDDIES if b.id == buddy_id), buddy_id)

        return {"toast": {"type": "info", "content": f"✅ {buddy_name} added to the invite list!"}}

    def _on_buddies_done(self, user_id: str, session: SessionState, card_action: dict) -> dict:
        """Handle 'Done Selecting' and 'Go Solo' — lock the buddy card, then send invite preview."""
        # For go_solo, override buddy selection to empty
        if card_action.get("action") == "go_solo":
            card_action = dict(card_action)
            card_action["action"] = "buddies_confirmed"
            # Clear selected buddies
            self._session_service.apply_agent_result(
                user_id, self._invite,
                AgentResult(session_updates={"selected_buddies": []})
            )

        self._route_to_agent(user_id, self._invite, "", session, context=card_action)
        updated = self._session_service.get_session(user_id)

        activity_name = self._resolve_activity_name(updated.selected_suggestion)
        buddies = self._resolve_buddies(updated.selected_buddies)
        activity = self._resolve_activity(updated.selected_suggestion)

        # Send the invite preview card — single API call, stays within Lark's 3s window.
        invite_preview = self._generate_invite_preview(user_id, activity_name, buddies, updated)
        if activity:
            self._send_card(user_id, build_invite_preview_card(activity, buddies, invite_preview))

        return {"toast": {"type": "info", "content": "Buddies locked in! 🎉"}}

    def _on_accept_invite(self, user_id: str, session: SessionState) -> dict:
        self._route_to_agent(user_id, self._confirmation, "", session, context={"action": "accept_invite"})
        updated = self._session_service.get_session(user_id)

        activity = self._resolve_activity(updated.selected_suggestion)
        buddies = self._resolve_buddies(updated.selected_buddies)
        # Send the confirmed card — single API call, stays well within Lark's 3s window.
        if activity:
            self._send_card(user_id, build_confirmed_card(activity, buddies))

        return {"toast": {"type": "success", "content": "🎉 Invites sent! Enjoy your weekend!"}}

    def _on_reject_invite(self, user_id: str, session: SessionState) -> dict:
        self._route_to_agent(user_id, self._confirmation, "", session, context={"action": "reject_invite"})
        self._send_text(user_id, "No worries! Let's start fresh. What would you like to do this weekend?")
        return {"toast": {"type": "info", "content": "Starting over! 🔄"}}

    def _on_cancel(self, user_id: str, session: SessionState) -> dict:
        self._route_to_agent(user_id, self._invite, "", session, context={"action": "cancel"})
        updated = self._session_service.get_session(user_id)
        weather = MOCK_WEATHER[0] if MOCK_WEATHER else None
        if updated.suggestions:
            self._send_card(user_id, build_suggestions_card(updated.suggestions, weather))
        return {"toast": {"type": "info", "content": "Cancelled — pick another activity!"}}

    # ─── Helpers ─────────────────────────────────────────────────────

    def _route_to_agent(
        self, user_id: str, agent: IAgent, message: str, session: SessionState, context: Optional[dict] = None
    ) -> AgentResult:
        logging.info("Routing to agent %s with message %s and context %s", agent.agent_name(), message, context)
        result = agent.handle(user_id, message, session, context)
        logging.info("Agent %s result: %s", agent.agent_name(), result)
        self._session_service.apply_agent_result(user_id, agent, result)
        return result

    def _send_text(self, user_id: str, text: str):
        content = json.dumps({"text": text})
        self._msg_client.send_text_with_open_id(user_id, content)

    def _send_card(self, user_id: str, card: dict):
        self._msg_client.send("open_id", user_id, "interactive", json.dumps(card))

    def _resolve_activity_name(self, suggestion_id: Optional[str]) -> str:
        for a in MOCK_ACTIVITIES:
            if a.id == suggestion_id:
                return a.name
        return "the activity"

    def _resolve_activity(self, suggestion_id: Optional[str]):
        for a in MOCK_ACTIVITIES:
            if a.id == suggestion_id:
                return a
        return None

    def _resolve_buddies(self, selected_ids: list):
        return [b for b in MOCK_BUDDIES if b.id in selected_ids]

    def _generate_invite_preview(self, user_id: str, activity_name: str, buddies, session: SessionState) -> str:
        """Ask the LLM to generate an invite message preview."""
        from llm.mock_client import MockLLMClient
        # Build a prompt for the confirmation agent's LLM context
        buddy_names = ", ".join(b.name for b in buddies) if buddies else "everyone"
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are the confirmation agent for a Weekend Buddy bot. "
                    f"Selected activity: {activity_name}. "
                    f"Selected buddies: {buddy_names}."
                ),
            },
            {"role": "user", "content": "generate_invite_preview"},
        ]
        try:
            response = self._confirmation.llm.chat(messages)
            return response.content
        except Exception as e:
            logger.warning("Failed to generate invite preview: %s", e)
            return (
                f"Hey! You're invited to join **{activity_name}** this weekend. "
                f"Hope you can make it! 🎉"
            )
