import logging

from interfaces.agent import IAgent, AgentResult
from interfaces.models import SessionState
from interfaces.session_store import ISessionStore


logger = logging.getLogger(__name__)


class SessionService:
    """Wraps ISessionStore with WRITABLE_FIELDS enforcement and Pydantic model merge."""

    def __init__(self, session_store: ISessionStore):
        self._store = session_store

    def get_session(self, user_id: str) -> SessionState:
        return self._store.get(user_id)

    def apply_agent_result(self, user_id: str, agent: IAgent, result: AgentResult) -> SessionState:
        current = self._store.get(user_id)
        updates = dict(result.session_updates)

        # Enforce WRITABLE_FIELDS
        unauthorized = set(updates.keys()) - agent.WRITABLE_FIELDS
        if unauthorized:
            logger.warning("Agent %s attempted unauthorized fields: %s", agent.agent_name(), unauthorized)
            updates = {k: v for k, v in updates.items() if k in agent.WRITABLE_FIELDS}

        if not updates:
            return current

        # Deep merge nested Pydantic models (IntentProfile)
        if "intent_profile" in updates and isinstance(updates["intent_profile"], dict):
            merged_profile = current.intent_profile.model_copy(
                update={k: v for k, v in updates["intent_profile"].items() if v is not None}
            )
            updates["intent_profile"] = merged_profile

        # Apply updates via model_copy (Pydantic validates the result)
        updated = current.model_copy(update=updates)
        self._store.save(user_id, updated)
        return updated

    def reset_session(self, user_id: str) -> None:
        self._store.clear(user_id)
