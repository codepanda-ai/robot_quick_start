from interfaces.llm_client import ILLMClient
from interfaces.session_store import ISessionStore
from interfaces.agent import IAgent
from core.tool_registry import ToolRegistry
from core.session_service import SessionService
from tools.send_text import SendTextTool
from tools.send_card import SendCardTool
from tools.get_weather import GetWeatherTool
from tools.search_buddies import SearchBuddiesTool
from tools.create_group_chat import CreateGroupChatTool
from agents.fallback import FallbackAgent
from agents.preference import PreferenceAgent
from agents.suggestion import SuggestionAgent
from agents.invite import InviteAgent
from agents.confirmation import ConfirmationAgent


class AgentFactory:
    """Centralizes agent creation and dependency injection wiring."""

    def __init__(self, llm_client: ILLMClient, session_store: ISessionStore, message_api_client):
        self._llm = llm_client
        self._session_store = session_store
        self._msg_client = message_api_client

    def create_fallback_agent(self) -> IAgent:
        tools = ToolRegistry()
        tools.register(SendTextTool(self._msg_client))
        return FallbackAgent(self._llm, tools)

    def create_preference_agent(self) -> IAgent:
        tools = ToolRegistry()
        tools.register(SendTextTool(self._msg_client))
        return PreferenceAgent(self._llm, tools)

    def create_suggestion_agent(self) -> IAgent:
        tools = ToolRegistry()
        tools.register(SendCardTool(self._msg_client))
        tools.register(GetWeatherTool())
        return SuggestionAgent(self._llm, tools)

    def create_invite_agent(self) -> IAgent:
        tools = ToolRegistry()
        tools.register(SendTextTool(self._msg_client))
        tools.register(SendCardTool(self._msg_client))
        tools.register(SearchBuddiesTool())
        tools.register(CreateGroupChatTool(self._msg_client))
        return InviteAgent(self._llm, tools)

    def create_confirmation_agent(self) -> IAgent:
        tools = ToolRegistry()
        tools.register(SendTextTool(self._msg_client))
        return ConfirmationAgent(self._llm, tools)

    def create_orchestrator(self):
        from core.orchestrator import OrchestratorAgent
        session_service = SessionService(self._session_store)
        return OrchestratorAgent(
            fallback_agent=self.create_fallback_agent(),
            preference_agent=self.create_preference_agent(),
            suggestion_agent=self.create_suggestion_agent(),
            invite_agent=self.create_invite_agent(),
            confirmation_agent=self.create_confirmation_agent(),
            session_service=session_service,
            message_api_client=self._msg_client,
        )
