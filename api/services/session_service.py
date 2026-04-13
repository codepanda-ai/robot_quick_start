import logging

from interfaces.agent import IAgent, AgentResult
from interfaces.models import IntentProfile, SessionState
from interfaces.session_store import ISessionStore


logger = logging.getLogger(__name__)


class SessionService:
    """Wraps ISessionStore with WRITABLE_FIELDS enforcement and Pydantic model merge.

    Optionally accepts an IntentProfileService to auto-persist intent_profile updates
    to long-term memory after every agent result that touches the intent_profile.

    JSON Schema (matches ``interfaces.models``; enums are string values as serialized by Pydantic)::

        {
          "$schema": "https://json-schema.org/draft/2020-12/schema",
          "$defs": {
            "IntentProfile": {
              "type": "object",
              "properties": {
                "activity": { "type": ["string", "null"] },
                "budget": {
                  "anyOf": [
                    { "type": "null" },
                    { "enum": ["low", "medium", "high"] }
                  ]
                },
                "vibe": {
                  "anyOf": [
                    { "type": "null" },
                    { "enum": ["chill", "adventurous", "social"] }
                  ]
                },
                "availability": { "type": ["string", "null"] },
                "location": { "type": ["string", "null"] }
              },
              "additionalProperties": false
            },
            "Activity": {
              "type": "object",
              "properties": {
                "id": { "type": "string" },
                "name": { "type": "string" },
                "type": { "type": "string" },
                "budget": { "enum": ["low", "medium", "high"] },
                "vibe": { "enum": ["chill", "adventurous", "social"] },
                "reason": { "type": "string" }
              },
              "required": ["id", "name", "type", "budget", "vibe", "reason"],
              "additionalProperties": false
            },
            "Buddy": {
              "type": "object",
              "properties": {
                "id": { "type": "string" },
                "name": { "type": "string" },
                "open_id": { "type": "string" },
                "interests": {
                  "type": "array",
                  "items": { "type": "string" }
                }
              },
              "required": ["id", "name", "open_id", "interests"],
              "additionalProperties": false
            },
            "SessionState": {
              "type": "object",
              "properties": {
                "phase": {
                  "enum": [
                    "idle",
                    "gathering",
                    "suggesting",
                    "inviting",
                    "confirmed"
                  ]
                },
                "intent_profile": { "$ref": "#/$defs/IntentProfile" },
                "suggestions": {
                  "type": "array",
                  "items": { "$ref": "#/$defs/Activity" }
                },
                "selected_suggestion": { "type": ["string", "null"] },
                "buddy_candidates": {
                  "type": "array",
                  "items": { "$ref": "#/$defs/Buddy" }
                },
                "selected_buddies": {
                  "type": "array",
                  "items": { "type": "string" }
                },
                "confirmation_status": {
                  "anyOf": [
                    { "type": "null" },
                    { "enum": ["pending", "confirmed", "cancelled"] }
                  ]
                }
              },
              "required": [
                "phase",
                "intent_profile",
                "suggestions",
                "selected_suggestion",
                "buddy_candidates",
                "selected_buddies",
                "confirmation_status"
              ],
              "additionalProperties": false
            }
          }
        }

    Root document for a stored session is ``SessionState``; ``intent_profile`` is the nested
    ``$ref`` to ``IntentProfile`` above.
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
