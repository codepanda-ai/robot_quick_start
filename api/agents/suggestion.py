import logging
from typing import Optional

from agents.base import BaseAgent
from interfaces.agent import AgentResult
from interfaces.llm_client import ILLMClient, LLMResponse
from interfaces.models import SessionState, Phase, Activity
from core.tool_registry import ToolRegistry
from data.mock_data import MOCK_ACTIVITIES


logger = logging.getLogger(__name__)


class SuggestionAgent(BaseAgent):
    """Suggests activities based on user preferences and sends a suggestions card."""

    WRITABLE_FIELDS: set = {"suggestions", "phase"}

    def __init__(self, llm_client: ILLMClient, tool_registry: ToolRegistry):
        super().__init__(llm_client, tool_registry)

    def agent_name(self) -> str:
        return "suggestion"

    def _build_prompt(self, session: SessionState, message: str, context: Optional[dict]) -> list[dict]:
        return [
            {
                "role": "system",
                "content": (
                    "You are a suggestion agent for a Weekend Buddy bot. "
                    f"User preferences: {session.intent_profile.model_dump_json()}"
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
        # Filter activities based on user preferences
        profile = session.intent_profile
        suggestions = self._filter_activities(profile)

        return AgentResult(
            session_updates={
                "suggestions": suggestions,
                "phase": Phase.SUGGESTING,
            },
            response=response.content,
        )

    def _filter_activities(self, profile) -> list[Activity]:
        """Filter and rank activities based on user preferences."""
        scored = []
        for activity in MOCK_ACTIVITIES:
            score = 0
            if profile.activity and profile.activity.lower() == activity.type.lower():
                score += 3
            if profile.budget and profile.budget == activity.budget:
                score += 1
            if profile.vibe and profile.vibe == activity.vibe:
                score += 1
            scored.append((score, activity))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = [a for _, a in scored[:3]]

        # If no matches at all, return top 3 anyway
        if not top:
            top = MOCK_ACTIVITIES[:3]

        return top
