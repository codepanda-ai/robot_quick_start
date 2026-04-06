import logging
from typing import Optional

from agents.base import BaseAgent
from interfaces.agent import AgentResult
from interfaces.llm_client import ILLMClient, LLMResponse
from interfaces.models import SessionState
from core.tool_registry import ToolRegistry


logger = logging.getLogger(__name__)


class FallbackAgent(BaseAgent):
    """Handles greetings, off-topic messages, and unrecognized input."""

    WRITABLE_FIELDS: set = set()  # Writes nothing — purely conversational

    def __init__(self, llm_client: ILLMClient, tool_registry: ToolRegistry):
        super().__init__(llm_client, tool_registry)

    def agent_name(self) -> str:
        return "fallback"

    def _build_prompt(self, session: SessionState, message: str, context: Optional[dict]) -> list[dict]:
        return [
            {"role": "system", "content": "You are a fallback handler for a Weekend Buddy bot. Respond to greetings and off-topic messages."},
            {"role": "user", "content": message},
        ]

    def _process_response(
        self,
        session: SessionState,
        response: LLMResponse,
        tool_results: list[dict],
        context: Optional[dict],
    ) -> AgentResult:
        return AgentResult(session_updates={}, response=response.content)
