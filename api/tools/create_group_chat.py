import logging

from interfaces.tool import ITool


logger = logging.getLogger(__name__)


class CreateGroupChatTool(ITool):
    """Creates a group chat on Lark (mock implementation)."""

    def __init__(self, message_api_client):
        self._client = message_api_client

    def name(self) -> str:
        return "create_group_chat"

    def description(self) -> str:
        return "Create a group chat with selected buddies for the planned activity."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "chat_name": {"type": "string", "description": "Name of the group chat."},
                "user_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of open_ids to add to the chat.",
                },
            },
            "required": ["chat_name", "user_ids"],
        }

    def execute(self, **kwargs) -> dict:
        chat_name = kwargs.get("chat_name", "Weekend Plan")
        user_ids = kwargs.get("user_ids", [])
        logger.info("Creating group chat '%s' with %d members (mock)", chat_name, len(user_ids))
        return {
            "status": "created",
            "chat_id": "oc_mock_chat_001",
            "chat_name": chat_name,
            "members": user_ids,
        }
