from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# --- Enums ---

class Phase(str, Enum):
    IDLE = "idle"
    GATHERING = "gathering"
    SUGGESTING = "suggesting"
    INVITING = "inviting"
    CONFIRMED = "confirmed"


class Budget(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Vibe(str, Enum):
    CHILL = "chill"
    ADVENTUROUS = "adventurous"
    SOCIAL = "social"


class ConfirmationStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


# --- Domain Models ---

class IntentProfile(BaseModel):
    activity: Optional[str] = None
    budget: Optional[Budget] = None
    vibe: Optional[Vibe] = None
    availability: Optional[str] = None
    location: Optional[str] = None


class Activity(BaseModel):
    id: str
    name: str
    type: str
    budget: Budget
    vibe: Vibe
    reason: str


class Buddy(BaseModel):
    id: str
    name: str
    open_id: str
    interests: list[str] = Field(default_factory=list)


class WeatherForecast(BaseModel):
    day: str
    temp: int
    condition: str
    humidity: int


# --- Session State ---

class SessionState(BaseModel):
    phase: Phase = Phase.IDLE
    intent_profile: IntentProfile = Field(default_factory=IntentProfile)
    suggestions: list[Activity] = Field(default_factory=list)
    selected_suggestion: Optional[str] = None
    buddy_candidates: list[Buddy] = Field(default_factory=list)
    selected_buddies: list[str] = Field(default_factory=list)
    confirmation_status: Optional[ConfirmationStatus] = None


# --- Card Action ---

class CardAction(BaseModel):
    action: str
    id: Optional[str] = None
    buddy_id: Optional[str] = None
    activity: Optional[str] = None
