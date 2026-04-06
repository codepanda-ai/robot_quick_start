from typing import Union

from interfaces.models import Buddy


def _as_buddy(b: Union[Buddy, dict]) -> Buddy:
    return Buddy.model_validate(b) if isinstance(b, dict) else b


def build_buddy_card(buddies: list[Buddy], activity_name: str, selected_buddy_ids: list = None) -> dict:
    """Build a Lark interactive card for selecting buddies to invite.

    Supports multi-select: selected buddies show a greyed '✅ Invited' button,
    unselected buddies keep an active 'Invite' button.
    Includes 'Start Over' to reset the flow.
    """
    selected = set(selected_buddy_ids or [])
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
        if buddy.id in selected:
            elements.append({
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "✅ Invited"},
                        "type": "default",
                        "value": {"action": "select_buddy", "buddy_id": buddy.id},
                    }
                ],
            })
        else:
            elements.append({
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": f"Invite {buddy.name} 🙋"},
                        "type": "primary",
                        "value": {"action": "select_buddy", "buddy_id": buddy.id},
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
                "value": {"action": "go_solo"},
            },
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "Start Over 🔄"},
                "type": "default",
                "value": {"action": "reset"},
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


def build_locked_buddy_card(buddies: list[Buddy], activity_name: str, selected_buddy_ids: list) -> dict:
    """Frozen version of the buddy card — shown after 'Done Selecting' or 'Go Solo'.

    All buttons are removed. A summary line shows who is coming.
    Returned as the `card` key of the Lark callback response to update the card in-place.
    """
    selected = [_as_buddy(b) for b in buddies if _as_buddy(b).id in set(selected_buddy_ids)]
    if selected:
        summary = "Going with: " + ", ".join(b.name for b in selected) + " 🎉"
    else:
        summary = "Going solo! 🚶"

    elements = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**{activity_name}**\n\n{summary}",
            },
        },
        {"tag": "hr"},
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": "_Preparing your invite preview..._",
            },
        },
    ]

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "👥 Buddies Locked In!"},
            "template": "purple",
        },
        "elements": elements,
    }
