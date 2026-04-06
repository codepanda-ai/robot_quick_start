import json
import logging
import typing as t

from decrypt import AESCipher


logger = logging.getLogger(__name__)


def _is_card_callback_v2(data: dict) -> bool:
    """Lark card.action.trigger uses schema 2.0 with header + event."""
    if data.get("schema") == "2.0":
        return True
    header = data.get("header")
    if isinstance(header, dict) and header.get("event_type") == "card.action.trigger":
        return True
    return False


def _app_verification_token(data: dict) -> str | None:
    """Verification Token is header.token (v2), not event.token (card update c-...)."""
    if _is_card_callback_v2(data):
        header = data.get("header")
        if isinstance(header, dict):
            return header.get("token")
        return None
    return data.get("token")


def _normalize_card_action(data: dict) -> tuple[str, dict]:
    """Returns (open_id, action_dict)."""
    if _is_card_callback_v2(data):
        event = data.get("event") or {}
        operator = event.get("operator") or {}
        open_id = operator.get("open_id", "")
        action = event.get("action") if isinstance(event.get("action"), dict) else {}
        return open_id, action
    open_id = data.get("open_id", "")
    action = data.get("action") if isinstance(data.get("action"), dict) else {}
    return open_id, action


class CallbackManager:
    """Singleton that handles Lark interactive card callbacks and URL verification."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._action_handlers = {}
            cls._instance._default_handler = None
        return cls._instance

    def register(self, action_type: str) -> t.Callable:
        """Decorator to register a handler for a card action type."""
        def decorator(f: t.Callable) -> t.Callable:
            self._action_handlers[action_type] = f
            return f
        return decorator

    def set_default_handler(self, handler: t.Callable) -> None:
        """Set a default handler for unregistered action types."""
        self._default_handler = handler

    @staticmethod
    def _decrypt_data(encrypt_key: str | None, data: dict) -> dict:
        """Decrypt request body when `encrypt` is present (same rules as EventManager)."""
        encrypt_data = data.get("encrypt")
        if not encrypt_data:
            return data
        if not encrypt_key:
            raise Exception("ENCRYPT_KEY is necessary for encrypted payloads")
        cipher = AESCipher(encrypt_key)
        return json.loads(cipher.decrypt_string(encrypt_data))

    def handle(
        self,
        action_data: dict,
        verification_token: str | None,
        encrypt_key: str | None = None,
    ) -> dict:
        """
        Decrypt if needed, then either answer URL verification or dispatch a card action.
        Returns a dict for jsonify() (challenge response or card action result).
        """
        data = self._decrypt_data(encrypt_key, action_data)
        logger.info("callback payload:\n%s", json.dumps(data, indent=2, ensure_ascii=False))

        if data.get("type") == "url_verification":
            if data.get("token") != verification_token:
                logger.warning("URL verification rejected: invalid token")
                return {}
            return {"challenge": data.get("challenge", "")}

        body_token = _app_verification_token(data)
        if body_token != verification_token:
            return {}

        open_id, action = _normalize_card_action(data)
        action_value = action.get("value", {}) if isinstance(action, dict) else {}
        action_type = action_value.get("action", "")

        if not open_id or not action_type:
            logger.warning("Card callback rejected: missing open_id or action type")
            return {}

        handler = self._action_handlers.get(action_type, self._default_handler)
        if handler is None:
            logger.warning("Card callback rejected: no handler for action type '%s'", action_type)
            return {}

        try:
            return handler(open_id=open_id, action_value=action_value)
        except Exception as e:
            logger.error("Card callback handler error for action '%s': %s", action_type, e, exc_info=True)
            return {}
