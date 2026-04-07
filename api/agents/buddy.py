import logging
from typing import Optional

from agents.base import BaseAgent
from interfaces.agent import AgentResult
from interfaces.llm_client import ILLMClient, LLMResponse
from interfaces.models import SessionState, Phase, ConfirmationStatus
from core.tool_registry import ToolRegistry
from data.mock_data import MOCK_BUDDIES, MOCK_ACTIVITIES


logger = logging.getLogger(__name__)


class BuddyAgent(BaseAgent):
    """Handles buddy search and selection."""

    WRITABLE_FIELDS: set = {
        "selected_suggestion", "buddy_candidates", "selected_buddies",
        "confirmation_status", "phase",
    }

    def __init__(self, llm_client: ILLMClient, tool_registry: ToolRegistry):
        super().__init__(llm_client, tool_registry)

    def agent_name(self) -> str:
        return "buddy"

    def _build_prompt(self, session: SessionState, message: str, context: Optional[dict]) -> list[dict]:
        return [
            {
                "role": "system",
                "content": (
                    "You are a buddy agent for a Weekend Buddy bot. "
                    "Your task is to identify and rank friends who would be a good fit for the selected activity. "
                    "Prioritise buddies whose listed interests overlap with the activity type. "
                    "A buddy already in the selected list should be shown as confirmed; others should be presented as candidates. "
                    "If no buddies match on interests, return the full contact list as candidates rather than an empty result. "
                    f"Selected activity: {session.selected_suggestion}. "
                    f"Selected buddies: {session.selected_buddies}."
                ),
            },
            {"role": "user", "content": message},
        ]

    def _process_response(
        self,
        session: SessionState,
        response: LLMResponse,
        tool_results: list[dict],
        context: Optional[dict],
    ) -> AgentResult:
        if not context:
            return AgentResult(session_updates={}, response=response.content)

        action = context.get("action", "")

        if action == "select_suggestion":
            return self._handle_select_suggestion(session, context)
        elif action == "select_buddy":
            return self._handle_select_buddy(session, context)
        elif action == "buddies_confirmed":
            return self._handle_buddies_confirmed(session)
        elif action == "confirm":
            return self._handle_confirm(session)
        elif action == "cancel":
            return self._handle_cancel()

        return AgentResult(session_updates={}, response=response.content)

    def _handle_select_suggestion(self, session: SessionState, context: dict) -> AgentResult:
        suggestion_id = context.get("id", "")
        activity_name = context.get("activity", "")

        # Find matching activity type for buddy search
        activity_type = ""
        for activity in MOCK_ACTIVITIES:
            if activity.id == suggestion_id:
                activity_type = activity.type
                break

        # Find matching buddies
        buddies = [b for b in MOCK_BUDDIES if activity_type in b.interests] if activity_type else MOCK_BUDDIES
        if not buddies:
            buddies = MOCK_BUDDIES

        return AgentResult(
            session_updates={
                "selected_suggestion": suggestion_id,
                "buddy_candidates": buddies,
                "phase": Phase.INVITING,
            },
            response=f"Great choice! Let me find buddies for {activity_name}.",
        )

    def _handle_select_buddy(self, session: SessionState, context: dict) -> AgentResult:
        buddy_id = context.get("buddy_id", "")
        current_buddies = list(session.selected_buddies)
        if buddy_id and buddy_id not in current_buddies:
            current_buddies.append(buddy_id)

        return AgentResult(
            session_updates={"selected_buddies": current_buddies},
            response=f"Added buddy {buddy_id} to the invite list!",
        )

    def _handle_buddies_confirmed(self, session: SessionState) -> AgentResult:
        return AgentResult(
            session_updates={"confirmation_status": ConfirmationStatus.PENDING},
            response="Buddies selected! Ready to confirm the plan.",
        )

    def _handle_confirm(self, session: SessionState) -> AgentResult:
        return AgentResult(
            session_updates={
                "confirmation_status": ConfirmationStatus.CONFIRMED,
                "phase": Phase.CONFIRMED,
            },
            response="Plan confirmed! Have an amazing weekend!",
        )

    def _handle_cancel(self) -> AgentResult:
        return AgentResult(
            session_updates={
                "confirmation_status": ConfirmationStatus.CANCELLED,
                "phase": Phase.SUGGESTING,
                "selected_suggestion": None,
                "buddy_candidates": [],
                "selected_buddies": [],
            },
            response="No worries! Let's pick a different activity.",
        )
