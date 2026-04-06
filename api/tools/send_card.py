import json
import logging

from interfaces.tool import ITool


logger = logging.getLogger(__name__)


class SendCardTool(ITool):
    """Sends an interactive card message to a Lark user."""

    def __init__(self, message_api_client):
        self._client = message_api_client

    def name(self) -> str:
        return "send_lark_card"

    def description(self) -> str:
        return "Send an interactive card message to a user in Lark."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "open_id": {"type": "string", "description": "The user's open_id."},
                "card_content": {"type": "object", "description": "The Lark interactive card JSON."},
            },
            "required": ["open_id", "card_content"],
        }

    def execute(self, **kwargs) -> dict:
        open_id = kwargs.get("open_id", "")
        card_content = kwargs.get("card_content", {})
        if not open_id:
            return {"error": "open_id is required"}
        if open_id.startswith("ou_mock_"):
            logger.info("[MOCK] Would send card to %s", open_id)
            return {"status": "mock_sent", "open_id": open_id}
        content = json.dumps(card_content)
        self._client.send("open_id", open_id, "interactive", content)
        logger.info("Sent card to %s", open_id)
        return {"status": "sent", "open_id": open_id}
