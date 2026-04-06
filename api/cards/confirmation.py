from interfaces.models import Activity, Buddy


def build_confirmation_card(activity: Activity, buddies: list[Buddy]) -> dict:
    """Build a Lark interactive card for confirming the final plan."""
    buddy_names = ", ".join(b.name for b in buddies) if buddies else "Solo adventure"

    elements = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"**Activity**: {activity.name}\n"
                    f"**Type**: {activity.type}\n"
                    f"**Budget**: {activity.budget.value}\n"
                    f"**Vibe**: {activity.vibe.value}\n"
                    f"**Buddies**: {buddy_names}"
                ),
            },
        },
        {"tag": "hr"},
        {
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "Confirm Plan ✅"},
                    "type": "primary",
                    "value": {"action": "confirm"},
                },
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "Cancel ❌"},
                    "type": "danger",
                    "value": {"action": "cancel"},
                },
            ],
        },
    ]

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "📋 Confirm Your Plan"},
            "template": "orange",
        },
        "elements": elements,
    }


def build_confirmed_card(activity: Activity, buddies: list[Buddy]) -> dict:
    """Build a Lark card showing the finalized confirmed plan."""
    buddy_names = ", ".join(b.name for b in buddies) if buddies else "Solo adventure"

    elements = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"🎉 **Plan Confirmed!**\n\n"
                    f"**Activity**: {activity.name}\n"
                    f"**Type**: {activity.type}\n"
                    f"**Budget**: {activity.budget.value}\n"
                    f"**Vibe**: {activity.vibe.value}\n"
                    f"**Buddies**: {buddy_names}\n\n"
                    f"Have an amazing weekend! 🥳"
                ),
            },
        },
    ]

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "✅ Weekend Plan Locked In!"},
            "template": "green",
        },
        "elements": elements,
    }
