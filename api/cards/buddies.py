from typing import Union

from interfaces.models import Buddy


def _as_buddy(b: Union[Buddy, dict]) -> Buddy:
    return Buddy.model_validate(b) if isinstance(b, dict) else b


def build_buddy_card(buddies: list[Buddy], activity_name: str) -> dict:
    """Build a Lark interactive card for selecting buddies to invite."""
    elements = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"Who should join you for **{activity_name}**? Tap to select buddies:",
            },
        },
        {"tag": "hr"},
    ]

    for raw in buddies:
        buddy = _as_buddy(raw)
        interests_str = ", ".join(buddy.interests)
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**{buddy.name}** — Interests: {interests_str}",
            },
        })
        elements.append({
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": f"Invite {buddy.name} 🙋"},
                    "type": "primary",
                    "value": {
                        "action": "select_buddy",
                        "buddy_id": buddy.id,
                    },
                }
            ],
        })

    elements.append({"tag": "hr"})
    elements.append({
        "tag": "action",
        "actions": [
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "Done Selecting ✅"},
                "type": "primary",
                "value": {"action": "buddies_confirmed"},
            },
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "Go Solo 🚶"},
                "type": "default",
                "value": {"action": "buddies_confirmed"},
            },
        ],
    })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "👥 Find Your Buddies"},
            "template": "purple",
        },
        "elements": elements,
    }
