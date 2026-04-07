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
    """Suggests activities based on user preferences and sends a suggestions card."""

    WRITABLE_FIELDS: set = {"suggestions", "phase"}

    def __init__(self, llm_client: ILLMClient, tool_registry: ToolRegistry, activity_service: ActivityService):
        super().__init__(llm_client, tool_registry)
        self._activity_service = activity_service

    def agent_name(self) -> str:
        return "suggestion"

    def _build_prompt(self, session: SessionState, message: str, context: Optional[dict]) -> list[dict]:
        return [
            {
                "role": "system",
                "content": (
                    "You are a suggestion agent for a Weekend Buddy bot. "
                    "Your task is to recommend the top 3 weekend activities that best match the user's preferences. "
                    "Score each candidate activity against the user's activity type, budget, and vibe. "
                    "For each recommendation, include a personalised explanation of why it suits this specific user — "
                    "referencing their stated preferences by name (e.g. 'matches your chill vibe', 'fits your low budget'). "
                    "Rank results by match score, highest first. "
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
        """Filter and rank activities based on user preferences, with personalised reasons."""
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

        # If no matches at all, return top 3 anyway
        if not top:
            top = self._activity_service.get_all()[:3]

        # Attach personalised "why" reason to each suggestion
        return [a.model_copy(update={"reason": self._personalize_reason(a, profile)}) for a in top]

    def _personalize_reason(self, activity: Activity, profile) -> str:
        """Build a personalised explanation of why this activity suits the user's profile."""
        reasons = []

        if profile.activity and profile.activity.lower() == activity.type.lower():
            reasons.append(f"matches your interest in **{profile.activity}**")
        elif activity.type:
            reasons.append(f"a great **{activity.type}** option")

        if profile.budget and profile.budget == activity.budget:
            budget_label = {"low": "budget-friendly", "medium": "mid-range", "high": "premium"}.get(
                str(profile.budget.value if hasattr(profile.budget, "value") else profile.budget), "fits your budget"
            )
            reasons.append(f"{budget_label} ✅")
        elif activity.budget:
            budget_val = activity.budget.value if hasattr(activity.budget, "value") else str(activity.budget)
            reasons.append(f"**{budget_val}** budget tier")

        if profile.vibe and profile.vibe == activity.vibe:
            vibe_val = profile.vibe.value if hasattr(profile.vibe, "value") else str(profile.vibe)
            reasons.append(f"fits your **{vibe_val}** vibe")

        if profile.location:
            reasons.append(f"available near **{profile.location}**")

        if profile.availability:
            reasons.append(f"perfect for **{profile.availability}**")

        if not reasons:
            return activity.reason or "A solid pick for the weekend!"

        return "🎯 Why for you: " + ", ".join(reasons) + "."
