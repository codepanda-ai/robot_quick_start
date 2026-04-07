#!/usr/bin/env python3.8
import json
import logging
import re
from typing import Optional


logger = logging.getLogger(__name__)


class Obj(dict):
    def __init__(self, d):
        for a, b in d.items():
            if isinstance(b, (list, tuple)):
                setattr(self, a, [Obj(x) if isinstance(x, dict) else x for x in b])
            else:
                setattr(self, a, Obj(b) if isinstance(b, dict) else b)


def dict_2_obj(d: dict):
    return Obj(d)


# ─── Lark messaging ──────────────────────────────────────────────────

def send_text(msg_client, user_id: str, text: str) -> None:
    msg_client.send_text_with_open_id(user_id, json.dumps({"text": text}))


def send_card(msg_client, user_id: str, card: dict) -> None:
    msg_client.send("open_id", user_id, "interactive", json.dumps(card))


def build_toast(level: str, message: str) -> dict:
    """Build a Lark callback response that shows a brief toast notification."""
    return {"toast": {"type": level, "content": message}}


# ─── Intent profile ──────────────────────────────────────────────────

def profile_is_complete(profile) -> bool:
    """True when all 5 preference fields have been collected."""
    return all([profile.activity, profile.budget, profile.vibe, profile.location, profile.availability])


# ─── Text classification ─────────────────────────────────────────────

def is_greeting(text: str, greeting_keywords) -> bool:
    """Whole-word match so 'hiking' doesn't trigger on the 'hi' inside it."""
    return any(re.search(r"\b" + re.escape(kw) + r"\b", text) for kw in greeting_keywords)


# ─── Invite preview ──────────────────────────────────────────────────

def generate_invite_preview(invite_agent, activity_name: str, buddies: list) -> str:
    """Ask the LLM (via InviteAgent) to draft the invite message for the preview card."""
    buddy_names = ", ".join(b.name for b in buddies) if buddies else "everyone"
    messages = [
        {
            "role": "system",
            "content": (
                "You are the invite agent for a Weekend Buddy bot. "
                f"Selected activity: {activity_name}. "
                f"Selected buddies: {buddy_names}."
            ),
        },
        {"role": "user", "content": "generate_invite_preview"},
    ]
    try:
        return invite_agent.llm.chat(messages).content
    except Exception as e:
        logger.warning("Failed to generate invite preview: %s", e)
        return f"Hey! You're invited to join **{activity_name}** this weekend. Hope you can make it! 🎉"
