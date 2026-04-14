import logging
from typing import Optional, Callable

from interfaces.agent import IAgent, AgentResult
from interfaces.models import Phase, SessionState
from services.session_service import SessionService
from services.activity_service import ActivityService
from services.buddy_service import BuddyService
from services.weather_service import WeatherService
from constants import RESET_KEYWORDS, SAME_AS_LAST_TIME_KEYWORDS, ACTIVITY_KEYWORDS, GREETING_KEYWORDS
from cards.suggestions import build_suggestions_card
from cards.buddies import build_buddy_card
from cards.confirmation import build_invite_preview_card, build_confirmed_card
from utils import (
    send_text, send_card, build_toast,
    profile_is_complete, is_greeting,
    generate_invite_preview,
)


logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """Routes messages and card actions to the appropriate agent based on session phase.

    Text messages are routed through a phase-based dispatch table:
        IDLE      → PreferenceAgent (or FallbackAgent for greetings)
        GATHERING → PreferenceAgent → auto-chain to SuggestionAgent when profile is complete
        SUGGESTING / INVITING / CONFIRMED → nudge text only

    Card actions are routed through an action-based dispatch table:
        select_suggestion → BuddyAgent (loads buddy candidates)
        select_buddy      → BuddyAgent (adds buddy to selection)
        buddies_confirmed → BuddyAgent → InviteAgent preview card
        go_solo           → clears buddies → same as buddies_confirmed
        send_invites     → InviteAgent (sends DMs, confirms plan)
        reset → full session reset
        cancel            → BuddyAgent (returns to suggestions)
    """

    def __init__(
        self,
        fallback_agent: IAgent,
        preference_agent: IAgent,
        suggestion_agent: IAgent,
        buddy_agent: IAgent,
        invite_agent: IAgent,
        session_service: SessionService,
        message_api_client,
        activity_service: ActivityService,
        buddy_service: BuddyService,
        weather_service: WeatherService,
        intent_profile_service=None,
    ):
        self._fallback_agent = fallback_agent
        self._preference_agent = preference_agent
        self._suggestion_agent = suggestion_agent
        self._buddy_agent = buddy_agent
        self._invite_agent = invite_agent
        self._session_service = session_service
        self._msg_client = message_api_client
        self._activity_service = activity_service
        self._buddy_service = buddy_service
        self._weather_service = weather_service
        self._intent_profile_service = intent_profile_service

        # ── Phase dispatch table ──────────────────────────────────────
        self._phase_handlers: dict[Phase, Callable] = {
            Phase.IDLE:       self._on_phase_idle,
            Phase.GATHERING:  self._on_phase_gathering,
            Phase.SUGGESTING: lambda uid, msg, ses: send_text(
                self._msg_client, uid,
                "Check out the suggestions above! Pick one you like, or say 'start over' to reset."
            ),
            Phase.INVITING:   lambda uid, msg, ses: send_text(
                self._msg_client, uid,
                "Select your buddies from the card above, or say 'start over' to reset."
            ),
            Phase.CONFIRMED:  lambda uid, msg, ses: send_text(
                self._msg_client, uid,
                "Your plan is confirmed! 🎉 Say 'start over' to plan something new."
            ),
        }

        # ── Card action dispatch table ────────────────────────────────
        self._card_action_handlers: dict[str, Callable] = {
            "select_suggestion": self._on_select_suggestion,
            "select_buddy":      self._on_select_buddy,
            "buddies_confirmed": self._on_buddies_confirmed,
            "go_solo":           self._on_go_solo,
            "send_invites":      self._on_send_invites,
            "reset":             self._on_reset,
            "cancel":            self._on_cancel,
            "quick_preference":  self._on_quick_preference,
        }

    # ─── Main entry point ─────────────────────────────────────────────

    def handle(
        self,
        user_id: str,
        message: str,
        message_type: str = "text",
        card_action: Optional[dict] = None,
    ) -> dict:
        try:
            session = self._session_service.get_session(user_id)

            if card_action:
                return self._handle_card_action(user_id, session, card_action)

            if message_type != "text":
                send_text(self._msg_client, user_id, "I can only process text messages for now. Tell me what you'd like to do this weekend!")
                return {}

            return self._handle_text(user_id, message, session)

        except Exception as e:
            logger.error("Orchestrator error for user %s: %s", user_id, e, exc_info=True)
            send_text(self._msg_client, user_id, "Something went wrong. Let's try again — what would you like to do this weekend?")
            self._session_service.reset_session(user_id)

        return {}

    # ─── Text message routing ─────────────────────────────────────────

    def _handle_text(self, user_id: str, message: str, session: SessionState) -> dict:
        """Apply global keyword overrides, then delegate to the phase handler."""
        text = message.lower().strip()

        if text in RESET_KEYWORDS:
            self._reset_and_greet(user_id)
            return {}

        if text in SAME_AS_LAST_TIME_KEYWORDS:
            return self._on_same_as_last_time(user_id)

        handler = self._phase_handlers.get(session.phase)
        if handler:
            handler(user_id, message, session)
        else:
            self._route(user_id, self._fallback_agent, message, session)

        return {}

    def _on_phase_idle(self, user_id: str, message: str, session: SessionState) -> None:
        text = message.lower().strip()

        if is_greeting(text, GREETING_KEYWORDS):
            self._route(user_id, self._fallback_agent, message, session)
        elif any(kw in text for kw in ACTIVITY_KEYWORDS) or len(text) >= 10:
            self._route(user_id, self._preference_agent, message, session)
            updated = self._session_service.get_session(user_id)
            if profile_is_complete(updated.intent_profile):
                self._chain_to_suggestions(user_id, message, updated)
        else:
            self._route(user_id, self._fallback_agent, message, session)

    def _on_phase_gathering(self, user_id: str, message: str, session: SessionState) -> None:
        self._route(user_id, self._preference_agent, message, session)
        updated = self._session_service.get_session(user_id)
        if profile_is_complete(updated.intent_profile):
            self._chain_to_suggestions(user_id, message, updated)

    def _on_same_as_last_time(self, user_id: str) -> dict:
        """Restore the saved IntentProfile and route based on completeness."""
        if not self._intent_profile_service or not self._intent_profile_service.has_profile(user_id):
            send_text(self._msg_client, user_id, "I don't have any past preferences saved yet! Let's start fresh — what activity sounds good? 🎯")
            return {}

        saved = self._intent_profile_service.get(user_id)
        logger.info("Restoring saved intent profile for %s: %s", user_id, saved.model_dump())

        self._session_service.apply_agent_result(
            user_id,
            self._preference_agent,
            AgentResult(session_updates={"intent_profile": saved.model_dump(), "phase": Phase.GATHERING}),
        )
        updated = self._session_service.get_session(user_id)

        if profile_is_complete(updated.intent_profile):
            summary = f"{saved.activity}, {saved.budget}, {saved.vibe}, {saved.location}, {saved.availability}"
            send_text(self._msg_client, user_id, f"Using your last preferences ({summary}) — finding suggestions... 🔍")
            self._chain_to_suggestions(user_id, "", updated)
        else:
            missing = [f for f in ["activity", "budget", "vibe", "location", "availability"]
                       if not getattr(updated.intent_profile, f)]
            send_text(self._msg_client, user_id, f"Found your last preferences! Just need a couple more details — {', '.join(missing)}.")
            self._route(user_id, self._preference_agent, "", updated)

        return {}

    def _chain_to_suggestions(self, user_id: str, message: str, session: SessionState) -> None:
        """Run SuggestionAgent then send the suggestions card."""
        self._route(user_id, self._suggestion_agent, message, session)
        updated = self._session_service.get_session(user_id)
        weather = self._weather_service.get_forecast()
        if updated.suggestions:
            send_card(self._msg_client, user_id, build_suggestions_card(updated.suggestions, weather))

    # ─── Card action routing ──────────────────────────────────────────

    def _handle_card_action(self, user_id: str, session: SessionState, card_action: dict) -> dict:
        action = card_action.get("action", "")
        handler = self._card_action_handlers.get(action)
        if handler:
            return handler(user_id, session, card_action)
        logger.warning("Unknown card action '%s' for user %s", action, user_id)
        return {}

    def _on_select_suggestion(self, user_id: str, session: SessionState, card_action: dict) -> dict:
        self._route(user_id, self._buddy_agent, "", session, context=card_action)
        updated = self._session_service.get_session(user_id)
        activity_name = card_action.get("activity", "the activity")
        send_card(self._msg_client, user_id, build_buddy_card(updated.buddy_candidates, activity_name))
        return build_toast("info", f"✅ '{activity_name}' selected! Now pick your buddies.")

    def _on_select_buddy(self, user_id: str, session: SessionState, card_action: dict) -> dict:
        self._route(user_id, self._buddy_agent, "", session, context=card_action)
        buddy_id = card_action.get("buddy_id", "")
        buddy = self._buddy_service.get_by_ids([buddy_id])
        buddy_name = buddy[0].name if buddy else buddy_id
        return build_toast("info", f"✅ {buddy_name} added to the invite list!")

    def _on_buddies_confirmed(self, user_id: str, session: SessionState, card_action: dict) -> dict:
        self._route(user_id, self._buddy_agent, "", session, context=card_action)
        updated = self._session_service.get_session(user_id)
        activity = self._activity_service.get_by_id(updated.selected_suggestion)
        activity_name = activity.name if activity else "the activity"
        buddies = self._buddy_service.get_by_ids(updated.selected_buddies)
        preview = generate_invite_preview(self._invite_agent, activity_name, buddies)
        if activity:
            send_card(self._msg_client, user_id, build_invite_preview_card(activity, buddies, preview))
        return build_toast("info", "Buddies locked in! 🎉")

    def _on_go_solo(self, user_id: str, session: SessionState, card_action: dict) -> dict:
        self._session_service.apply_agent_result(
            user_id,
            self._buddy_agent,
            AgentResult(session_updates={"selected_buddies": []}),
        )
        return self._on_buddies_confirmed(user_id, session, {**card_action, "action": "buddies_confirmed"})

    def _on_send_invites(self, user_id: str, session: SessionState, _card_action: dict) -> dict:
        self._route(user_id, self._invite_agent, "", session, context={"action": "send_invites"})
        updated = self._session_service.get_session(user_id)
        activity = self._activity_service.get_by_id(updated.selected_suggestion)
        buddies = self._buddy_service.get_by_ids(updated.selected_buddies)
        if activity:
            send_card(self._msg_client, user_id, build_confirmed_card(activity, buddies))
        return build_toast("success", "🎉 Invites sent! Enjoy your weekend!")

    def _on_cancel(self, user_id: str, session: SessionState, _card_action: dict) -> dict:
        self._route(user_id, self._buddy_agent, "", session, context={"action": "cancel"})
        updated = self._session_service.get_session(user_id)
        weather = self._weather_service.get_forecast()
        if updated.suggestions:
            send_card(self._msg_client, user_id, build_suggestions_card(updated.suggestions, weather))
        return build_toast("info", "Cancelled — pick another activity!")

    def _on_reset(self, user_id: str, _session: SessionState, _card_action: dict) -> dict:
        self._reset_and_greet(user_id)
        return build_toast("info", "Starting fresh! 🔄")

    def _on_quick_preference(self, user_id: str, session: SessionState, card_action: dict) -> dict:
        self._route(user_id, self._preference_agent, card_action.get("activity", ""), session)
        return build_toast("info", "Got it!")

    # ─── Internal transitions ─────────────────────────────────────────

    def _reset_and_greet(self, user_id: str) -> None:
        send_text(self._msg_client, user_id, "Let's start fresh!")
        self._session_service.reset_session(user_id)
        fresh = self._session_service.get_session(user_id)
        self._route(user_id, self._preference_agent, "start over", fresh)

    def _route(
        self,
        user_id: str,
        agent: IAgent,
        message: str,
        session: SessionState,
        context: Optional[dict] = None,
    ) -> AgentResult:
        logger.info("Routing to agent '%s' | message=%r | context=%s", agent.agent_name(), message, context)
        result = agent.handle(user_id, message, session, context)
        logger.info("Agent '%s' result: %s", agent.agent_name(), result)
        self._session_service.apply_agent_result(user_id, agent, result)
        