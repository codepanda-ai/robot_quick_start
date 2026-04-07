import logging

from interfaces.agent import IAgent, AgentResult
from interfaces.models import IntentProfile, SessionState
from interfaces.session_store import ISessionStore


logger = logging.getLogger(__name__)


class SessionService:
    """Wraps ISessionStore with WRITABLE_FIELDS enforcement and Pydantic model merge.

    Optionally accepts an IntentProfileService to auto-persist intent_profile updates
    to long-term memory after every agent result that touches the intent_profile.
    """

    def __init__(self, session_store: ISessionStore, intent_profile_service=None):
        self._store = session_store
        self._intent_profile_service = intent_profile_service

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

        # IntentProfile: full model replaces session; dicts are merged (None = leave unchanged)
        if "intent_profile" in updates:
            ip = updates["intent_profile"]
            if isinstance(ip, IntentProfile):
                pass  # replace wholesale, e.g. reset with IntentProfile()
            elif isinstance(ip, dict):
                merged_profile = current.intent_profile.model_copy(
                    update={k: v for k, v in ip.items() if v is not None}
                )
                updates["intent_profile"] = merged_profile

        # Apply updates via model_copy (Pydantic validates the result)
        updated = current.model_copy(update=updates)
        self._store.save(user_id, updated)

        # Auto-persist intent_profile to long-term memory on every write
        if "intent_profile" in updates and self._intent_profile_service:
            self._intent_profile_service.save(user_id, updated.intent_profile)

        return updated

    def reset_session(self, user_id: str) -> None:
        self._store.clear(user_id)
