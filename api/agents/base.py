import logging
from abc import abstractmethod
from typing import Optional

from interfaces.agent import IAgent, AgentResult
from interfaces.llm_client import ILLMClient, LLMResponse, ToolCall
from interfaces.models import SessionState
from core.tool_registry import ToolRegistry


logger = logging.getLogger(__name__)


class BaseAgent(IAgent):
    """Template Method base class for agents.

    Defines the invariant handle loop:
      1. _build_prompt()   — subclass builds LLM messages
      2. llm.chat()        — call the LLM
      3. _execute_tools()  — run any tool calls from the LLM response
      4. _process_response() — subclass interprets LLM response into AgentResult
    """

    def __init__(self, llm_client: ILLMClient, tool_registry: ToolRegistry):
        self.llm = llm_client
        self.tools = tool_registry

    def handle(self, user_id: str, message: str, session: SessionState, context: Optional[dict] = None) -> AgentResult:
        prompt = self._build_prompt(session, message, context)
        tool_schemas = self._get_tool_schemas()
        response = self.llm.chat(prompt, tool_schemas)
        tool_results = self._execute_tools(user_id, response.tool_calls)
        return self._process_response(session, response, tool_results, context)

    @abstractmethod
    def _build_prompt(self, session: SessionState, message: str, context: Optional[dict]) -> list[dict]:
        """Build the message list to send to the LLM."""
        ...

    @abstractmethod
    def _process_response(
        self,
        session: SessionState,
        response: LLMResponse,
        tool_results: list[dict],
        context: Optional[dict],
    ) -> AgentResult:
        """Interpret the LLM response and tool results into an AgentResult."""
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
