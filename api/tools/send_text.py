import json
import logging

from interfaces.tool import ITool


logger = logging.getLogger(__name__)


class SendTextTool(ITool):
    """Sends a plain text message to a Lark user via open_id."""

    def __init__(self, message_api_client):
        self._client = message_api_client

    def name(self) -> str:
        return "send_lark_text"

    def description(self) -> str:
        return "Send a plain text message to a user in Lark."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "open_id": {"type": "string", "description": "The user's open_id."},
                "text": {"type": "string", "description": "The text message to send."},
            },
            "required": ["text"],
        }

    def execute(self, **kwargs) -> dict:
        open_id = kwargs.get("open_id", "")
        text = kwargs.get("text", "")
        if not open_id:
            return {"error": "open_id is required"}
        content = json.dumps({"text": text})
        self._client.send_text_with_open_id(open_id, content)
        logger.info("Sent text to %s: %s", open_id, text[:80])
        return {"status": "sent", "open_id": open_id}
