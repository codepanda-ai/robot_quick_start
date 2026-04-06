from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel, Field

from interfaces.models import SessionState


class AgentResult(BaseModel):
    session_updates: dict = Field(default_factory=dict)
    response: str = ""


class IAgent(ABC):
    WRITABLE_FIELDS: set = set()

    @abstractmethod
    def handle(self, user_id: str, message: str, session: SessionState, context: Optional[dict] = None) -> AgentResult:
        """Process a user message given current session state. Returns AgentResult with partial updates."""
        pass

    @abstractmethod
    def agent_name(self) -> str:
        """Return a unique identifier for this agent."""
        pass
