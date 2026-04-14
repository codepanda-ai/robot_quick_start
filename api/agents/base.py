import json
import logging
from abc import abstractmethod
from typing import Optional

from interfaces.agent import IAgent, AgentResult
from interfaces.llm_client import ILLMClient, LLMResponse, ToolCall, FinishReason
from interfaces.models import SessionState
from core.tool_registry import ToolRegistry


logger = logging.getLogger(__name__)


class BaseAgent(IAgent):
    """Template Method base class for agents.

    Runs a turn-based handle loop (up to max_turns):
      1. _build_prompt()     — subclass builds initial LLM messages
      2. llm.chat()          — call the LLM
      3. _execute_tools()    — run any tool calls from the LLM response
      4. If finish_reason is TOOL_USE, append results to messages and repeat from 2
      5. _process_response() — subclass interprets final LLM response into AgentResult
    """

    DEFAULT_MAX_TURNS: int = 10

    def __init__(self, llm_client: ILLMClient, tool_registry: ToolRegistry, max_turns: Optional[int] = None):
        self.llm = llm_client
        self.tools = tool_registry
        self.max_turns = max_turns if max_turns is not None else self.DEFAULT_MAX_TURNS

    def handle(self, user_id: str, message: str, session: SessionState, context: Optional[dict] = None) -> AgentResult:
        messages = self._build_prompt(session, message, context)
        tool_schemas = self._get_tool_schemas()

        for turn in range(self.max_turns):
            response = self.llm.chat(messages, tool_schemas)

            if not response.tool_calls:
                logger.debug("Turn %d: no tool calls, finishing", turn + 1)
                break

            tool_results = self._execute_tools(user_id, response.tool_calls)

            if response.finish_reason != FinishReason.TOOL_USE:
                logger.debug("Turn %d: tools executed, finish_reason=%s, done", turn + 1, response.finish_reason)
                break

            # Append assistant message and tool results for next turn
            logger.debug("Turn %d: tool_use with %d tool(s): %s", turn + 1, len(response.tool_calls),
                         [tc.name for tc in response.tool_calls])
            messages.append({
                "role": "assistant",
                "content": response.content,
                "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}}
                    for tc in response.tool_calls
                ],
            })
            for tc, result in zip(response.tool_calls, tool_results):
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                })
        else:
            logger.warning("max_turns (%d) reached for agent %s", self.max_turns, self.__class__.__name__)

        return self._process_response(session, response, context)

    @abstractmethod
    def _build_prompt(self, session: SessionState, message: str, context: Optional[dict]) -> list[dict]:
        """Build the message list to send to the LLM."""
        ...

    @abstractmethod
    def _process_response(
        self,
        session: SessionState,
        response: LLMResponse,
        context: Optional[dict],
    ) -> AgentResult:
        """Interpret the final LLM response into an AgentResult."""
        ...

    def _get_tool_schemas(self) -> list[dict]:
        return self.tools.get_schemas()

    def _execute_tools(self, user_id: str, tool_calls: list[ToolCall]) -> list[dict]:
        results = []
        for tc in tool_calls:
            args = dict(tc.arguments)
            if "open_id" not in args:
                args["open_id"] = user_id
            result = self.tools.execute(tc.name, **args)
            results.append({"tool": tc.name, "result": result})
        return results
