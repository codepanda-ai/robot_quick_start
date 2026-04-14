import json
import logging
from typing import Optional

from agents.base import BaseAgent
from interfaces.agent import AgentResult
from interfaces.llm_client import ILLMClient, LLMResponse
from interfaces.models import SessionState, Phase, Activity
from core.tool_registry import ToolRegistry
from services.activity_service import ActivityService


logger = logging.getLogger(__name__)


class SuggestionAgent(BaseAgent):
    """Suggests activities based on user preferences, weather, and sends a suggestions card."""

    WRITABLE_FIELDS: set = {"suggestions", "phase"}

    def __init__(self, llm_client: ILLMClient, tool_registry: ToolRegistry, activity_service: ActivityService):
        super().__init__(llm_client, tool_registry)
        self._activity_service = activity_service

    def agent_name(self) -> str:
        return "suggestion"

    def _build_prompt(self, session: SessionState, message: str, context: Optional[dict]) -> list[dict]:
        activities = self._activity_service.get_all()
        catalog = [a.model_dump() for a in activities]
        return [
            {
                "role": "system",
                "content": (
                    "You are a suggestion agent for a Weekend Buddy bot. "
                    "Recommend the top 3 activities from the catalog that best match the user's preferences. "
                    "If the user's preferences involve outdoor activities (hiking, beach, etc.), "
                    "call get_weather first to check conditions before ranking. "
                    "Return your final answer as JSON: "
                    '{"suggestions": [{"id": "...", "reason": "..."}]} '
                    f"\n\nUser preferences: {session.intent_profile.model_dump_json()}"
                    f"\n\nActivity catalog: {json.dumps(catalog, default=str)}"
                ),
            },
            {"role": "user", "content": message},
        ]

    def _process_response(
        self,
        session: SessionState,
        response: LLMResponse,
        context: Optional[dict],
    ) -> AgentResult:
        suggestions = self._parse_suggestions(response.content)
        if not suggestions:
            suggestions = self._fallback_suggestions(session.intent_profile)

        return AgentResult(
            session_updates={
                "suggestions": suggestions,
                "phase": Phase.SUGGESTING,
            },
            response=response.content,
        )

    def _parse_suggestions(self, content: str) -> list[Activity]:
        """Parse structured JSON suggestions from LLM response."""
        try:
            parsed = json.loads(content)
            results = []
            for item in parsed["suggestions"][:3]:
                activity = self._activity_service.get_by_id(item["id"])
                if activity:
                    results.append(activity.model_copy(update={"reason": item["reason"]}))
            return results
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning("Failed to parse LLM suggestions, falling back to scoring")
            return []

    def _fallback_suggestions(self, profile) -> list[Activity]:
        """Score-based fallback if LLM output can't be parsed."""
        scored = []
        for activity in self._activity_service.get_all():
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
        if not top:
            top = self._activity_service.get_all()[:3]
        return top
