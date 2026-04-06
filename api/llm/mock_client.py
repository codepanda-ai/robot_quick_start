import json
import logging
import re
from typing import Optional

from interfaces.llm_client import ILLMClient, LLMResponse, ToolCall, FinishReason


logger = logging.getLogger(__name__)

# Keywords used for intent classification and preference extraction
ACTIVITY_KEYWORDS = {
    "hiking": "hiking", "hike": "hiking", "trail": "hiking", "walk": "hiking", "mountain": "hiking",
    "beach": "beach", "swim": "beach", "ocean": "beach", "sea": "beach",
    "dinner": "dining", "dining": "dining", "food": "dining", "eat": "dining", "restaurant": "dining",
    "dim sum": "dining", "brunch": "dining", "lunch": "dining",
    "movie": "indoor", "film": "indoor", "board game": "indoor", "cafe": "indoor", "indoor": "indoor",
    "bar": "nightlife", "club": "nightlife", "nightlife": "nightlife", "pub": "nightlife", "drink": "nightlife",
}

BUDGET_KEYWORDS = {
    "cheap": "low", "budget": "low", "free": "low", "low": "low", "affordable": "low",
    "moderate": "medium", "medium": "medium", "mid": "medium",
    "expensive": "high", "fancy": "high", "high": "high", "luxury": "high", "splurge": "high",
}

VIBE_KEYWORDS = {
    "chill": "chill", "relax": "chill", "calm": "chill", "easy": "chill", "laid back": "chill", "quiet": "chill",
    "adventure": "adventurous", "adventurous": "adventurous", "exciting": "adventurous", "challenge": "adventurous",
    "social": "social", "friends": "social", "group": "social", "party": "social", "fun": "social", "people": "social",
}

LOCATION_KEYWORDS = {
    "downtown": "downtown", "city": "downtown", "central": "downtown", "urban": "downtown",
    "suburb": "suburbs", "suburbs": "suburbs", "outside": "suburbs", "outskirts": "suburbs",
    "nature": "nature", "park": "nature", "forest": "nature", "outdoors": "nature", "outside city": "nature",
    "east": "east side", "west": "west side", "north": "north side", "south": "south side",
    "nearby": "nearby", "local": "nearby", "close": "nearby",
}

GREETING_KEYWORDS = {"hi", "hello", "hey", "yo", "sup", "howdy", "good morning", "good afternoon", "good evening"}

# Sequential question order for preference gathering
FIELD_ORDER = ["activity", "budget", "vibe", "location", "availability"]

FOLLOW_UP_QUESTIONS = {
    "activity": "What kind of activity sounds fun this weekend? 🎯 (e.g. hiking, dining, movies, beach, nightlife)",
    "budget": "What's your budget like? 💰 (low / medium / high)",
    "vibe": "What vibe are you going for? ✨ (chill, adventurous, or social)",
    "location": "Any location preference? 📍 (e.g. downtown, nature, suburbs, nearby)",
    "availability": "When are you free? 🗓️ (e.g. Saturday morning, Sunday afternoon, or all weekend)",
}


class MockLLMClient(ILLMClient):
    """Mock LLM client that uses keyword matching to simulate LLM behavior."""

    def chat(self, messages: list[dict], tools: Optional[list[dict]] = None) -> LLMResponse:
        last_message = self._get_last_user_message(messages)
        if not last_message:
            return LLMResponse(content="I didn't catch that. What would you like to do this weekend?")

        text = last_message.lower().strip()

        # Check system message for agent context
        system_context = self._get_system_context(messages)

        if "fallback" in system_context:
            return self._handle_fallback(text)
        elif "preference extraction agent" in system_context:
            return self._handle_preference(text, messages)
        elif "suggestion agent" in system_context:
            return self._handle_suggestion(text, messages, tools)
        elif "invite agent" in system_context:
            return self._handle_invite(text, messages, tools)
        elif "confirmation agent" in system_context:
            return self._handle_confirmation(text, system_context)

        # Default: try to classify
        return self._handle_fallback(text)

    def _get_last_user_message(self, messages: list[dict]) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    def _get_system_context(self, messages: list[dict]) -> str:
        for msg in messages:
            if msg.get("role") == "system":
                return msg.get("content", "").lower()
        return ""

    def _handle_fallback(self, text: str) -> LLMResponse:
        if any(re.search(r"\b" + re.escape(g) + r"\b", text) for g in GREETING_KEYWORDS):
            return LLMResponse(
                content="Hey! I'm your Weekend Buddy 🎉 Ready to plan something fun? "
                        "Tell me what you feel like doing — hiking, dining, movies, or anything else!",
                tool_calls=[ToolCall(name="send_lark_text", arguments={
                    "text": "Hey! I'm your Weekend Buddy 🎉 Ready to plan something fun? "
                            "Tell me what you feel like doing — hiking, dining, movies, or anything else!"
                })],
                finish_reason=FinishReason.TOOL_USE,
            )
        return LLMResponse(
            content="I'm best at helping plan weekend activities! What sounds fun — hiking, dining, board games?",
            tool_calls=[ToolCall(name="send_lark_text", arguments={
                "text": "I'm best at helping plan weekend activities! What sounds fun — hiking, dining, board games?"
            })],
            finish_reason=FinishReason.TOOL_USE,
        )

    def _handle_preference(self, text: str, messages: list[dict]) -> LLMResponse:
        # Parse the current profile state from system context
        system_context = self._get_system_context(messages)
        current_profile = self._parse_profile_from_context(system_context)

        # Determine which field we're currently asking for (next missing field in order)
        next_field = None
        for field in FIELD_ORDER:
            if not current_profile.get(field):
                next_field = field
                break

        # Try to extract the value for the current expected field from user text
        extracted = {}
        if next_field == "activity":
            for keyword, activity in ACTIVITY_KEYWORDS.items():
                if keyword in text:
                    extracted["activity"] = activity
                    break
        elif next_field == "budget":
            for keyword, budget in BUDGET_KEYWORDS.items():
                if keyword in text:
                    extracted["budget"] = budget
                    break
            # Also try to catch anything from activity keywords in case user answers activity here
            if not extracted:
                for keyword, activity in ACTIVITY_KEYWORDS.items():
                    if keyword in text:
                        extracted["activity"] = activity
                        break
        elif next_field == "vibe":
            for keyword, vibe in VIBE_KEYWORDS.items():
                if keyword in text:
                    extracted["vibe"] = vibe
                    break
        elif next_field == "location":
            for keyword, location in LOCATION_KEYWORDS.items():
                if keyword in text:
                    extracted["location"] = location
                    break
            # Generic fallback: treat any short answer as a location name
            if not extracted and text.strip() and len(text.strip()) < 40:
                extracted["location"] = text.strip().title()
        elif next_field == "availability":
            for day in ["saturday", "sunday", "weekend", "both days"]:
                if day in text:
                    for period in ["morning", "afternoon", "evening", "night", "all day"]:
                        if period in text:
                            extracted["availability"] = f"{day.capitalize()} {period}"
                            break
                    else:
                        extracted["availability"] = day.capitalize()
                    break
            # Fallback: treat any short answer as availability
            if not extracted and text.strip() and len(text.strip()) < 40:
                extracted["availability"] = text.strip().capitalize()

        if extracted:
            # Merge extracted into current profile to determine what's still missing
            merged = dict(current_profile)
            merged.update(extracted)

            # Find the next unanswered field after what we just extracted
            next_missing = None
            for field in FIELD_ORDER:
                if not merged.get(field):
                    next_missing = field
                    break

            content = json.dumps({"extracted_preferences": extracted})

            if next_missing:
                # Ask the next question
                question = FOLLOW_UP_QUESTIONS[next_missing]
                return LLMResponse(
                    content=content,
                    tool_calls=[ToolCall(name="send_lark_text", arguments={"text": question})],
                    finish_reason=FinishReason.TOOL_USE,
                )
            else:
                # All fields collected — no more questions
                return LLMResponse(content=content, finish_reason=FinishReason.STOP)

        # Nothing extracted — ask (or re-ask) for the current field
        if next_field:
            question = FOLLOW_UP_QUESTIONS[next_field]
        else:
            question = FOLLOW_UP_QUESTIONS["activity"]

        return LLMResponse(
            content="ask_followup",
            tool_calls=[ToolCall(name="send_lark_text", arguments={"text": question})],
            finish_reason=FinishReason.TOOL_USE,
        )

    def _parse_profile_from_context(self, system_context: str) -> dict:
        """Extract the current intent profile JSON from the system prompt."""
        try:
            # System prompt contains: "Current profile: {...}"
            marker = "current profile:"
            idx = system_context.find(marker)
            if idx == -1:
                return {}
            json_str = system_context[idx + len(marker):].strip()
            # Find the end of the JSON object
            depth = 0
            end = 0
            for i, ch in enumerate(json_str):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            profile = json.loads(json_str[:end])
            return {k: v for k, v in profile.items() if v is not None}
        except Exception:
            return {}

    def _handle_suggestion(self, text: str, messages: list[dict], tools: Optional[list[dict]]) -> LLMResponse:
        tool_calls = []

        # Always call weather tool first
        if tools and any(t["function"]["name"] == "get_weather" for t in tools):
            tool_calls.append(ToolCall(name="get_weather", arguments={"day": "Saturday"}))

        # Then send the card
        tool_calls.append(ToolCall(name="send_lark_card", arguments={"card_type": "suggestions"}))

        return LLMResponse(
            content="Here are some suggestions based on your preferences!",
            tool_calls=tool_calls,
            finish_reason=FinishReason.TOOL_USE,
        )

    def _handle_confirmation(self, text: str, system_context: str) -> LLMResponse:
        """Generate an invite message preview for the ConfirmationAgent."""
        # Extract activity name and buddy names from system context heuristically
        # In production this would be a real LLM call with the full context
        activity_name = "this activity"
        if "selected activity:" in system_context:
            parts = system_context.split("selected activity:")
            if len(parts) > 1:
                activity_name = parts[1].split(".")[0].strip()

        preview = (
            f"Hey! 🎉 You're invited to join **{activity_name}** this weekend. "
            f"It's going to be a great time — hope you can make it! Let me know ASAP. 🙌"
        )
        return LLMResponse(content=preview, finish_reason=FinishReason.STOP)

    def _handle_invite(self, text: str, messages: list[dict], tools: Optional[list[dict]]) -> LLMResponse:
        tool_calls = []

        # Search for buddies
        if tools and any(t["function"]["name"] == "search_buddies" for t in tools):
            tool_calls.append(ToolCall(name="search_buddies", arguments={}))

        tool_calls.append(ToolCall(name="send_lark_card", arguments={"card_type": "buddies"}))

        return LLMResponse(
            content="Let me find some buddies who'd enjoy this activity!",
            tool_calls=tool_calls,
            finish_reason=FinishReason.TOOL_USE,
        )
