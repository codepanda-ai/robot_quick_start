import json
import logging
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

GREETING_KEYWORDS = {"hi", "hello", "hey", "yo", "sup", "howdy", "good morning", "good afternoon", "good evening"}


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
        elif "preference" in system_context:
            return self._handle_preference(text, messages)
        elif "suggestion" in system_context:
            return self._handle_suggestion(text, messages, tools)
        elif "invite" in system_context:
            return self._handle_invite(text, messages, tools)

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
        if any(g in text for g in GREETING_KEYWORDS):
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
            content="I'm best at helping plan weekend activities! What sounds fun — hiking, dining, movies?",
            tool_calls=[ToolCall(name="send_lark_text", arguments={
                "text": "I'm best at helping plan weekend activities! What sounds fun — hiking, dining, movies?"
            })],
            finish_reason=FinishReason.TOOL_USE,
        )

    def _handle_preference(self, text: str, messages: list[dict]) -> LLMResponse:
        extracted = {}

        # Extract activity
        for keyword, activity in ACTIVITY_KEYWORDS.items():
            if keyword in text:
                extracted["activity"] = activity
                break

        # Extract budget
        for keyword, budget in BUDGET_KEYWORDS.items():
            if keyword in text:
                extracted["budget"] = budget
                break

        # Extract vibe
        for keyword, vibe in VIBE_KEYWORDS.items():
            if keyword in text:
                extracted["vibe"] = vibe
                break

        # Extract availability
        for day in ["saturday", "sunday", "weekend"]:
            if day in text:
                for period in ["morning", "afternoon", "evening"]:
                    if period in text:
                        extracted["availability"] = f"{day.capitalize()} {period}"
                        break
                else:
                    extracted["availability"] = day.capitalize()
                break

        if extracted:
            content = json.dumps({"extracted_preferences": extracted})
            return LLMResponse(content=content, finish_reason=FinishReason.STOP)

        # No preferences found — ask follow-up
        return LLMResponse(
            content="ask_followup",
            tool_calls=[ToolCall(name="send_lark_text", arguments={
                "text": "Sounds interesting! Could you tell me more? What kind of activity are you thinking — "
                        "hiking, dining, beach, movies? And do you have a budget preference?"
            })],
            finish_reason=FinishReason.TOOL_USE,
        )

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
