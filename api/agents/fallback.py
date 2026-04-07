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
            {
                "role": "system",
                "content": (
                    "You are a fallback agent for a Weekend Buddy bot. "
                    "Your task is to handle messages that do not map to any active planning step — greetings, small talk, confused input, or out-of-scope requests. "
                    "For greetings, respond warmly and prompt the user to start planning their weekend. "
                    "For off-topic messages, politely redirect the conversation back to weekend activity planning. "
                    "Keep responses short, friendly, and encouraging."
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
        return AgentResult(session_updates={}, response=response.content)
