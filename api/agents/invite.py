import json
import logging
from typing import Optional

from agents.base import BaseAgent
from interfaces.agent import AgentResult
from interfaces.llm_client import ILLMClient, LLMResponse
from interfaces.models import SessionState, Phase, ConfirmationStatus
from core.tool_registry import ToolRegistry
from services.activity_service import ActivityService
from services.buddy_service import BuddyService


logger = logging.getLogger(__name__)


class InviteAgent(BaseAgent):
    """Handles the invite preview and final send step.

    Handles two card actions:
    - send_invites: sends DM to each selected buddy, sets phase=CONFIRMED
    - reset:  full reset to IDLE
    """

    WRITABLE_FIELDS: set = {
        "phase", "confirmation_status",
        # Reset fields — needed for reset
        "intent_profile", "suggestions", "selected_suggestion",
        "buddy_candidates", "selected_buddies",
    }

    def __init__(self, llm_client: ILLMClient, tool_registry: ToolRegistry,
                 activity_service: ActivityService, buddy_service: BuddyService):
        super().__init__(llm_client, tool_registry)
        self._activity_service = activity_service
        self._buddy_service = buddy_service

    def agent_name(self) -> str:
        return "invite"

    def _build_prompt(self, session: SessionState, message: str, context: Optional[dict]) -> list[dict]:
        action = (context or {}).get("action", "")
        return [
            {
                "role": "system",
                "content": (
                    "You are the invite agent for a Weekend Buddy bot. "
                    "Your task is to draft a warm, concise invite message for the confirmed activity and send it to each selected buddy. "
                    "The message should mention the activity name, feel personal and upbeat, and include a call to action. "
                    "On send_invites: generate the invite message, send it to each buddy via direct message, then confirm the plan. "
                    "On reset: discard the current plan entirely and reset the session so the user can start fresh. "
                    f"Current action: {action}. "
                    f"Selected activity: {session.selected_suggestion}. "
                    f"Selected buddies: {session.selected_buddies}."
                ),
            },
            {"role": "user", "content": message or action},
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

        if action == "send_invites":
            return self._handle_accept(session, response)
        elif action == "reset":
            return self._handle_reject()

        return AgentResult(session_updates={}, response=response.content)

    def _handle_accept(self, session: SessionState, response: LLMResponse) -> AgentResult:
        """Send invite DMs to each selected buddy and confirm the plan."""
        selected_buddy_objs = self._buddy_service.get_by_ids(session.selected_buddies)
        activity_name = self._activity_service.get_name(session.selected_suggestion)

        # Send DM to each buddy via tool
        for buddy in selected_buddy_objs:
            invite_text = self._build_invite_message(buddy.name, activity_name, response.content)
            self.tools.execute("send_lark_text", open_id=buddy.open_id, text=invite_text)

        logger.info("Sent invites to %d buddies for activity '%s'", len(selected_buddy_objs), activity_name)

        return AgentResult(
            session_updates={
                "confirmation_status": ConfirmationStatus.CONFIRMED,
                "phase": Phase.CONFIRMED,
            },
            response="Invites sent! Have an amazing weekend! 🎉",
        )

    def _handle_reset(self) -> AgentResult:
        """Reset the entire session to IDLE."""
        return AgentResult(
            session_updates={
                "phase": Phase.IDLE,
                "intent_profile": {"activity": None, "budget": None, "vibe": None, "availability": None, "location": None},
                "suggestions": [],
                "selected_suggestion": None,
                "buddy_candidates": [],
                "selected_buddies": [],
                "confirmation_status": None,
            },
            response="No problem! Let's start fresh. What would you like to do this weekend?",
        )

    def _build_invite_message(self, buddy_name: str, activity_name: str, llm_content: str) -> str:
        """Use LLM-generated content if available, otherwise fall back to template."""
        if llm_content and llm_content not in ("send_invites", ""):
            return llm_content
        return (
            f"Hey {buddy_name}! 🎉 You're invited to join **{activity_name}** this weekend. "
            f"Let me know if you can make it!"
        )
