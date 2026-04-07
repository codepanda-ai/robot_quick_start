# Shared constants used across agents, orchestrator, and the mock LLM client.

# ─── Session control keywords ─────────────────────────────────────────────────

RESET_KEYWORDS = {
    "start over", "reset", "cancel", "restart", "new plan", "plan my weekend",
}

SAME_AS_LAST_TIME_KEYWORDS = {
    "same as last time", "same", "same as before", "repeat", "again",
    "same preferences", "use last",
}

# ─── Intent classification ────────────────────────────────────────────────────

GREETING_KEYWORDS = {
    "hi", "hello", "hey", "yo", "sup", "howdy", "good morning", "good afternoon", "good evening",
}

ACTIVITY_KEYWORDS = {
    "hiking": "hiking", "hike": "hiking", "trail": "hiking", "walk": "hiking", "mountain": "hiking",
    "beach": "beach", "swim": "beach", "ocean": "beach", "sea": "beach",
    "dinner": "dining", "dining": "dining", "food": "dining", "eat": "dining", "restaurant": "dining",
    "dim sum": "dining", "brunch": "dining", "lunch": "dining",
    "movie": "indoor", "film": "indoor", "board game": "indoor", "cafe": "indoor", "indoor": "indoor",
    "bar": "nightlife", "club": "nightlife", "nightlife": "nightlife", "pub": "nightlife", "drink": "nightlife",
}

# ─── Preference extraction ────────────────────────────────────────────────────

# Ordered list of fields that must all be collected before triggering suggestions.
PREFERENCE_FIELD_ORDER = ["activity", "budget", "vibe", "location", "availability"]

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

FOLLOW_UP_QUESTIONS = {
    "activity":     "What kind of activity sounds fun this weekend? 🎯 (e.g. hiking, dining, movies, beach, nightlife)",
    "budget":       "What's your budget like? 💰 (low / medium / high)",
    "vibe":         "What vibe are you going for? ✨ (chill, adventurous, or social)",
    "location":     "Any location preference? 📍 (e.g. downtown, nature, suburbs, nearby)",
    "availability": "When are you free? 🗓️ (e.g. Saturday morning, Sunday afternoon, or all weekend)",
}
