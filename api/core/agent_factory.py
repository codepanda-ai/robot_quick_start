from interfaces.llm_client import ILLMClient
from interfaces.session_store import ISessionStore
from interfaces.agent import IAgent
from core.tool_registry import ToolRegistry
from services.session_service import SessionService
from services.activity_service import ActivityService
from services.buddy_service import BuddyService
from services.weather_service import WeatherService
from services.intent_profile_service import IntentProfileService
from data.intent_profile_store import InMemoryIntentProfileStore
from tools.send_text import SendTextTool
from tools.send_card import SendCardTool
from tools.get_weather import GetWeatherTool
from tools.search_buddies import SearchBuddiesTool
from tools.create_group_chat import CreateGroupChatTool
from agents.fallback import FallbackAgent
from agents.preference import PreferenceAgent
from agents.suggestion import SuggestionAgent
from agents.buddy import BuddyAgent
from agents.invite import InviteAgent


class AgentFactory:
    """Centralizes agent creation and dependency injection wiring."""

    def __init__(self, llm_client: ILLMClient, session_store: ISessionStore, message_api_client):
        self._llm = llm_client
        self._session_store = session_store
        self._msg_client = message_api_client

        # Shared services — single instances reused across all agents
        self._activity_service = ActivityService()
        self._buddy_service = BuddyService()
        self._weather_service = WeatherService()
        self._intent_profile_service = IntentProfileService(InMemoryIntentProfileStore())

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
        tools.register(GetWeatherTool(self._weather_service))
        return SuggestionAgent(self._llm, tools, self._activity_service)

    def create_buddy_agent(self) -> IAgent:
        tools = ToolRegistry()
        tools.register(SendTextTool(self._msg_client))
        tools.register(SendCardTool(self._msg_client))
        tools.register(SearchBuddiesTool(self._buddy_service))
        tools.register(CreateGroupChatTool(self._msg_client))
        return BuddyAgent(self._llm, tools, self._activity_service, self._buddy_service)

    def create_invite_agent(self) -> IAgent:
        tools = ToolRegistry()
        tools.register(SendTextTool(self._msg_client))
        return InviteAgent(self._llm, tools, self._activity_service, self._buddy_service)

    def create_orchestrator(self):
        from core.orchestrator import OrchestratorAgent
        session_service = SessionService(self._session_store, self._intent_profile_service)
        return OrchestratorAgent(
            fallback_agent=self.create_fallback_agent(),
            preference_agent=self.create_preference_agent(),
            suggestion_agent=self.create_suggestion_agent(),
            buddy_agent=self.create_buddy_agent(),
            invite_agent=self.create_invite_agent(),
            session_service=session_service,
            message_api_client=self._msg_client,
            activity_service=self._activity_service,
            buddy_service=self._buddy_service,
            weather_service=self._weather_service,
            intent_profile_service=self._intent_profile_service,
        )
