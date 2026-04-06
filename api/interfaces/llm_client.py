from abc import ABC, abstractmethod
from typing import Optional
from enum import Enum

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    name: str
    arguments: dict = Field(default_factory=dict)


class FinishReason(str, Enum):
    STOP = "stop"
    TOOL_USE = "tool_use"


class LLMResponse(BaseModel):
    content: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: FinishReason = FinishReason.STOP
    raw: dict = Field(default_factory=dict)


class ILLMClient(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], tools: Optional[list[dict]] = None) -> LLMResponse:
        """Send messages to LLM, optionally with tool definitions. Returns a structured LLMResponse."""
        pass
