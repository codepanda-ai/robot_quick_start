import json
import logging
from typing import Optional

from interfaces.agent import IAgent, AgentResult
from interfaces.models import Phase, SessionState
from core.session_service import SessionService
from cards.suggestions import build_suggestions_card
from cards.buddies import build_buddy_card
from cards.confirmation import build_confirmation_card, build_confirmed_card
from data.mock_data import MOCK_ACTIVITIES, MOCK_BUDDIES, MOCK_WEATHER


logger = logging.getLogger(__name__)

RESET_KEYWORDS = {"start over", "reset", "cancel", "restart", "new plan"}


class OrchestratorAgent:
    """Routes messages and card actions to the appropriate agent based on session phase."""

    def __init__(
        self,
        fallback_agent: IAgent,
        preference_agent: IAgent,
        suggestion_agent: IAgent,
        invite_agent: IAgent,
        session_service: SessionService,
        message_api_client,
    ):
        self._fallback = fallback_agent
        self._preference = preference_agent
        self._suggestion = suggestion_agent
        self._invite = invite_agent
        self._session_service = session_service
        self._msg_client = message_api_client

    def handle(self, user_id: str, message: str, message_type: str = "text", card_action: Optional[dict] = None):
        """Main entry point — routes to agents based on session phase and input type."""
        try:
            session = self._session_service.get_session(user_id)

            if card_action:
                self._handle_card_action(user_id, session, card_action)
                return

            if message_type != "text":
                self._send_text(user_id, "I can only process text messages for now. Tell me what you'd like to do this weekend!")
                return

            # Check for reset keywords
            if message.lower().strip() in RESET_KEYWORDS:
                self._route_to_agent(user_id, self._preference, message, session, context={"reset": True})
                return

            # Route based on phase
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

    def _handle_idle(self, user_id: str, message: str, session: SessionState):
        """In idle phase, classify as greeting/off-topic vs activity-related."""
        text_lower = message.lower().strip()
        from llm.mock_client import ACTIVITY_KEYWORDS
        has_activity_keyword = any(kw in text_lower for kw in ACTIVITY_KEYWORDS)

        if has_activity_keyword:
            result = self._route_to_agent(user_id, self._preference, message, session)
            # Auto-chain: if profile has activity, immediately trigger suggestions
            updated_session = self._session_service.get_session(user_id)
            if updated_session.intent_profile.activity:
                self._auto_chain_to_suggestions(user_id, message, updated_session)
        else:
            self._route_to_agent(user_id, self._fallback, message, session)

    def _handle_gathering(self, user_id: str, message: str, session: SessionState):
        """In gathering phase, continue extracting preferences."""
        result = self._route_to_agent(user_id, self._preference, message, session)
        # Auto-chain: check if profile is now complete enough for suggestions
        updated_session = self._session_service.get_session(user_id)
        if updated_session.intent_profile.activity:
            self._auto_chain_to_suggestions(user_id, message, updated_session)

    def _auto_chain_to_suggestions(self, user_id: str, message: str, session: SessionState):
        """Auto-chain from preference to suggestion agent, then send card."""
        result = self._route_to_agent(user_id, self._suggestion, message, session)
        updated_session = self._session_service.get_session(user_id)

        # Build and send the suggestions card
        weather = MOCK_WEATHER[0] if MOCK_WEATHER else None
        suggestions = updated_session.suggestions
        if suggestions:
            card = build_suggestions_card(suggestions, weather)
            card_json = json.dumps(card)
            self._msg_client.send("open_id", user_id, "interactive", card_json)

    def _handle_card_action(self, user_id: str, session: SessionState, card_action: dict):
        """Route card actions to the appropriate agent."""
        action = card_action.get("action", "")

        if action == "reset":
            self._route_to_agent(user_id, self._preference, "", session, context={"reset": True})
            self._send_text(user_id, "Let's start fresh! What would you like to do this weekend?")
            return

        if action == "quick_preference":
            context = {"quick_preference": card_action.get("activity", "")}
            self._route_to_agent(user_id, self._preference, card_action.get("activity", ""), session, context=context)
            return

        if action == "select_suggestion":
            result = self._route_to_agent(user_id, self._invite, "", session, context=card_action)
            updated_session = self._session_service.get_session(user_id)
            # Send buddy card
            buddies = updated_session.buddy_candidates
            activity_name = card_action.get("activity", "the activity")
            if buddies:
                card = build_buddy_card(buddies, activity_name)
                card_json = json.dumps(card)
                self._msg_client.send("open_id", user_id, "interactive", card_json)
            return

        if action == "select_buddy":
            self._route_to_agent(user_id, self._invite, "", session, context=card_action)
            buddy_id = card_action.get("buddy_id", "")
            buddy_name = next((b.name for b in MOCK_BUDDIES if b.id == buddy_id), buddy_id)
            self._send_text(user_id, f"Added {buddy_name} to the invite list! ✅")
            return

        if action == "buddies_confirmed":
            self._route_to_agent(user_id, self._invite, "", session, context=card_action)
            updated_session = self._session_service.get_session(user_id)
            # Send confirmation card
            selected_id = updated_session.selected_suggestion
            activity = next((a for a in MOCK_ACTIVITIES if a.id == selected_id), None)
            buddies = [b for b in MOCK_BUDDIES if b.id in updated_session.selected_buddies]
            if activity:
                card = build_confirmation_card(activity, buddies)
                card_json = json.dumps(card)
                self._msg_client.send("open_id", user_id, "interactive", card_json)
            return

        if action == "confirm":
            self._route_to_agent(user_id, self._invite, "", session, context=card_action)
            updated_session = self._session_service.get_session(user_id)
            # Send confirmed card
            selected_id = updated_session.selected_suggestion
            activity = next((a for a in MOCK_ACTIVITIES if a.id == selected_id), None)
            buddies = [b for b in MOCK_BUDDIES if b.id in updated_session.selected_buddies]
            if activity:
                card = build_confirmed_card(activity, buddies)
                card_json = json.dumps(card)
                self._msg_client.send("open_id", user_id, "interactive", card_json)
            return

        if action == "cancel":
            self._route_to_agent(user_id, self._invite, "", session, context=card_action)
            # Re-send suggestions
            updated_session = self._session_service.get_session(user_id)
            weather = MOCK_WEATHER[0] if MOCK_WEATHER else None
            if updated_session.suggestions:
                card = build_suggestions_card(updated_session.suggestions, weather)
                card_json = json.dumps(card)
                self._msg_client.send("open_id", user_id, "interactive", card_json)
            return

        logger.warning("Unknown card action: %s", action)

    def _route_to_agent(
        self, user_id: str, agent: IAgent, message: str, session: SessionState, context: Optional[dict] = None
    ) -> AgentResult:
        """Route to an agent and persist the result."""
        logging.info("Routing to agent %s with message %s and context %s", agent.agent_name(), message, context)
        result = agent.handle(user_id, message, session, context)
        logging.info("Agent %s result: %s", agent.agent_name(), result)
        self._session_service.apply_agent_result(user_id, agent, result)
        return result

    def _send_text(self, user_id: str, text: str):
        """Send a plain text message to the user."""
        content = json.dumps({"text": text})
        self._msg_client.send_text_with_open_id(user_id, content)
