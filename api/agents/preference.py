import json
import logging
from typing import Optional

from agents.base import BaseAgent
from interfaces.agent import AgentResult
from interfaces.llm_client import ILLMClient, LLMResponse
from interfaces.models import SessionState, Phase
from core.tool_registry import ToolRegistry


logger = logging.getLogger(__name__)


class PreferenceAgent(BaseAgent):
    """Captures user preferences (activity, budget, vibe, availability)."""

    WRITABLE_FIELDS: set = {
        "intent_profile", "phase", "suggestions", "selected_suggestion",
        "buddy_candidates", "selected_buddies", "confirmation_status",
    }

    def __init__(self, llm_client: ILLMClient, tool_registry: ToolRegistry):
        super().__init__(llm_client, tool_registry)

    def agent_name(self) -> str:
        return "preference"

    def _build_prompt(self, session: SessionState, message: str, context: Optional[dict]) -> list[dict]:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a preference extraction agent for a Weekend Buddy bot. "
                    "Extract activity, budget, vibe, and availability from the user's message. "
                    f"Current profile: {session.intent_profile.model_dump_json()}"
                ),
            },
            {"role": "user", "content": message},
        ]
        return messages

    def _process_response(
        self,
        session: SessionState,
        response: LLMResponse,
        tool_results: list[dict],
        context: Optional[dict],
    ) -> AgentResult:
        # Handle reset
        if context and context.get("reset"):
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
                response="Let's start fresh! What would you like to do this weekend?",
            )

        # Try to parse extracted preferences from LLM response
        updates = {}
        try:
            parsed = json.loads(response.content)
            if "extracted_preferences" in parsed:
                updates["intent_profile"] = parsed["extracted_preferences"]
        except (json.JSONDecodeError, TypeError):
            pass

        if updates.get("intent_profile"):
            # Merge with existing profile — check if we have enough to move on
            merged = dict(session.intent_profile.model_dump())
            for k, v in updates["intent_profile"].items():
                if v is not None:
                    merged[k] = v

            updates["intent_profile"] = {k: v for k, v in updates["intent_profile"].items() if v is not None}

            # Profile is "complete" when at least activity is set
            if merged.get("activity"):
                updates["phase"] = Phase.GATHERING
                logger.info("Preference profile has activity, moving to gathering: %s", merged)

            return AgentResult(session_updates=updates, response=response.content)

        # No preferences extracted — follow-up was sent via tool
        return AgentResult(session_updates={"phase": Phase.GATHERING}, response=response.content)
