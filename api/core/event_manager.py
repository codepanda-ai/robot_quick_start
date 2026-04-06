import json
import logging
import typing as t

from flask import request
from decrypt import AESCipher
from core.event import MessageReceiveEvent, UrlVerificationEvent, InvalidEventException


logger = logging.getLogger(__name__)


class EventManager(object):
    """Singleton event manager for Lark event subscriptions."""

    _instance = None
    event_callback_map = dict()
    event_type_map = dict()
    _event_list = [MessageReceiveEvent, UrlVerificationEvent]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            for event in cls._event_list:
                cls.event_type_map[event.event_type()] = event
        return cls._instance

    def register(self, event_type: str) -> t.Callable:
        def decorator(f: t.Callable) -> t.Callable:
            self.event_callback_map[event_type] = f
            return f
        return decorator

    def get_handler_with_event(self, token, encrypt_key):
        dict_data = json.loads(request.data)
        dict_data = self._decrypt_data(encrypt_key, dict_data)
        logger.info("callback payload:\n%s", json.dumps(dict_data, indent=2, ensure_ascii=False))
        callback_type = dict_data.get("type")

        if callback_type == "url_verification":
            event = UrlVerificationEvent(dict_data)
            return self.event_callback_map.get(event.event_type()), event

        schema = dict_data.get("schema")
        if schema is None:
            raise InvalidEventException("request is not callback event(v2)")

        event_type = dict_data.get("header").get("event_type")
        event = self.event_type_map.get(event_type)(dict_data, token, encrypt_key)
        return self.event_callback_map.get(event_type), event

    @staticmethod
    def _decrypt_data(encrypt_key, data):
        encrypt_data = data.get("encrypt")
        if not encrypt_key and encrypt_data is None:
            return data
        if not encrypt_key:
            raise Exception("ENCRYPT_KEY is necessary")
        cipher = AESCipher(encrypt_key)
        return json.loads(cipher.decrypt_string(encrypt_data))
