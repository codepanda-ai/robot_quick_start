import json
import logging
from typing import Optional

from agents.base import BaseAgent
from interfaces.agent import AgentResult
from interfaces.llm_client import ILLMClient, LLMResponse
from interfaces.models import SessionState, Phase
from core.tool_registry import ToolRegistry


logger = logging.getLogger(__name__)

# All 5 required preference fields — must all be collected before triggering suggestions
ALL_PREFERENCE_FIELDS = ["activity", "budget", "vibe", "location", "availability"]


class PreferenceAgent(BaseAgent):
    """Captures user preferences via 5 sequential questions: activity, budget, vibe, location, availability."""

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
                response="Let's start fresh!",
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
            # Merge with existing profile
            merged = dict(session.intent_profile.model_dump())
            for k, v in updates["intent_profile"].items():
                if v is not None:
                    merged[k] = v

            updates["intent_profile"] = {k: v for k, v in updates["intent_profile"].items() if v is not None}

            # Move to GATHERING as soon as we have at least one field so that
            # short follow-up replies (e.g. "cheap", "chill") keep routing here.
            # _handle_gathering gates the suggestion chain on _profile_is_complete.
            updates["phase"] = Phase.GATHERING

            missing = [f for f in ALL_PREFERENCE_FIELDS if not merged.get(f)]
            if missing:
                logger.info("Collecting preferences — still missing: %s", missing)
            else:
                logger.info("All preference fields collected: %s", merged)

            return AgentResult(session_updates=updates, response=response.content)

        # No preferences extracted — stay in current phase (follow-up question sent via tool)
        return AgentResult(session_updates={}, response=response.content)
