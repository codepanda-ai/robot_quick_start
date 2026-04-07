#!/usr/bin/env python3.8

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json
import logging
import requests
from lark_client import MessageApiClient
from core.event_manager import EventManager
from core.event import MessageReceiveEvent, UrlVerificationEvent
from core.callback_manager import CallbackManager
from data.session_store import InMemorySessionStore
from core.agent_factory import AgentFactory
from llm.mock_client import MockLLMClient
from flask import Flask, jsonify, request
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

logging.getLogger().setLevel(logging.INFO)

app = Flask(__name__)

# Load env
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN")
ENCRYPT_KEY = os.getenv("ENCRYPT_KEY")
LARK_HOST = os.getenv("LARK_HOST")

# Init services
message_api_client = MessageApiClient(APP_ID, APP_SECRET, LARK_HOST)
event_manager = EventManager()
callback_manager = CallbackManager()

# Init agent system
llm_client = MockLLMClient()
session_store = InMemorySessionStore()
agent_factory = AgentFactory(llm_client, session_store, message_api_client)
orchestrator = agent_factory.create_orchestrator()

# Dedup recent message IDs
_seen_message_ids: set = set()


@event_manager.register("url_verification")
def request_url_verify_handler(req_data: UrlVerificationEvent):
    if req_data.event.token != VERIFICATION_TOKEN:
        raise Exception("VERIFICATION_TOKEN is invalid")
    return jsonify({"challenge": req_data.event.challenge})


@event_manager.register("im.message.receive_v1")
def message_receive_event_handler(req_data: MessageReceiveEvent):
    sender_id = req_data.event.sender.sender_id
    message = req_data.event.message

    # Dedup
    message_id = message.message_id
    if message_id in _seen_message_ids:
        logging.info("Skipping duplicate message: %s", message_id)
        return jsonify()
    _seen_message_ids.add(message_id)
    # Keep dedup set bounded
    if len(_seen_message_ids) > 1000:
        _seen_message_ids.clear()

    open_id = sender_id.open_id
    message_type = message.message_type

    if message_type != "text":
        orchestrator.handle(open_id, "", message_type=message_type)
        return jsonify()

    # Parse text content
    text_content = message.content
    try:
        content_data = json.loads(text_content)
        text = content_data.get("text", text_content)
    except (json.JSONDecodeError, TypeError):
        text = text_content

    # Strip @mention prefix
    if text.startswith("@_user"):
        parts = text.split(" ", 1)
        text = parts[1] if len(parts) > 1 else ""

    orchestrator.handle(open_id, text.strip())
    return jsonify()


# Card action callback handlers — return orchestrator result so Lark can update cards in-place.
# The dict may contain 'card' (in-place card update) and/or 'toast' (notification).

def _card_handler(open_id: str, action_value: dict) -> dict:
    return orchestrator.handle(open_id, "", card_action=action_value) or {}


@callback_manager.register("select_suggestion")
def handle_select_suggestion(open_id: str, action_value: dict) -> dict:
    return _card_handler(open_id, action_value)


@callback_manager.register("select_buddy")
def handle_select_buddy(open_id: str, action_value: dict) -> dict:
    return _card_handler(open_id, action_value)


@callback_manager.register("buddies_confirmed")
def handle_buddies_confirmed(open_id: str, action_value: dict) -> dict:
    return _card_handler(open_id, action_value)


@callback_manager.register("go_solo")
def handle_go_solo(open_id: str, action_value: dict) -> dict:
    return _card_handler(open_id, action_value)


@callback_manager.register("accept_invite")
def handle_accept_invite(open_id: str, action_value: dict) -> dict:
    return _card_handler(open_id, action_value)


@callback_manager.register("reject_invite")
def handle_reject_invite(open_id: str, action_value: dict) -> dict:
    return _card_handler(open_id, action_value)


@callback_manager.register("confirm")
def handle_confirm(open_id: str, action_value: dict) -> dict:
    return _card_handler(open_id, action_value)


@callback_manager.register("cancel")
def handle_cancel(open_id: str, action_value: dict) -> dict:
    return _card_handler(open_id, action_value)


@callback_manager.register("reset")
def handle_reset(open_id: str, action_value: dict) -> dict:
    return _card_handler(open_id, action_value)


@callback_manager.register("quick_preference")
def handle_quick_preference(open_id: str, action_value: dict) -> dict:
    return _card_handler(open_id, action_value)


@app.errorhandler(Exception)
def msg_error_handler(ex):
    logging.error(ex, exc_info=True)
    response = jsonify(message=str(ex))
    response.status_code = (
        ex.response.status_code if isinstance(ex, requests.HTTPError) else 500
    )
    return response


@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"})


@app.route("/handle-event", methods=["POST"])
def handle_event():
    try:
        event_handler, event = event_manager.get_handler_with_event(VERIFICATION_TOKEN, ENCRYPT_KEY)
        return event_handler(event)
    except Exception as e:
        logging.error("Event error: %s", e, exc_info=True)
        return jsonify(message=str(e)), 500


@app.route("/handle-callback", methods=["POST"])
def handle_callback():
    """Handle Lark interactive card action callbacks."""
    try:
        action_data = json.loads(request.data)
        return jsonify(callback_manager.handle(action_data, VERIFICATION_TOKEN, ENCRYPT_KEY))
    except Exception as e:
        logging.error("Card action error: %s", e, exc_info=True)
        return jsonify(message=str(e)), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)
