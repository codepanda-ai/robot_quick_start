# Feishu AI Weekend Buddy Agent - Implementation Plan

## Context

Build a multi-agent system for a Feishu bot that helps users plan weekend activities end-to-end: capture preferences, suggest activities, find buddies, and confirm plans. The existing codebase is a Flask-based Lark bot starter (echo bot) deployed on Vercel. We're adding an orchestrator pattern with 3 specialized agents, a shared session store, mock LLM clients, and interactive Lark cards.

Assignment: Wati.io Agentic Engineer Candidate Assignment — "Feishu AI Weekend Buddy Agent."

---

## Architecture Overview

```
User Message (Lark)
       |
  Flask Handler (api/index.py)
       |
  EventManager (singleton)          CallbackManager (singleton)
       |                                   |
  OrchestratorAgent  <------- routes both event messages and card actions
   /    |      \      \
Fallback Preference  Suggestion  Invite   <-- all implement IAgent interface
 Agent    Agent       Agent       Agent
   \      |          /          /
    Session Store (shared, injected)
       |
  ISessionStore interface (InMemorySessionStore impl)
```

- **EventManager** (singleton) — handles Lark event subscriptions (messages)
- **CallbackManager** (singleton) — handles Lark interactive card action callbacks
- Agents never call each other. Orchestrator reads `session.phase` and delegates.
- All agents implement `IAgent` interface.
- All LLM calls go through `ILLMClient` interface (mock now, real later).
- LLM responses use a defined `LLMResponse` dataclass.
- Dependency injection throughout: session store, LLM client, message client, tools.

---

## Project Structure (Production-Grade)

```
api/
├── index.py                    # Flask app, route handlers (MODIFY - slim, delegates to core)
├── lark_client.py              # MessageApiClient (MODIFY - add send_card)
├── decrypt.py                  # AES decryption (EXISTING, no changes)
├── utils.py                    # dict_2_obj helper (EXISTING, no changes)
│
├── interfaces/                 # All abstract interfaces
│   ├── __init__.py
│   ├── agent.py                # IAgent interface
│   ├── session_store.py        # ISessionStore interface
│   ├── llm_client.py           # ILLMClient interface + LLMResponse/ToolCall dataclasses
│   └── tool.py                 # ITool interface
│
├── agents/                     # Agent implementations
│   ├── __init__.py
│   ├── base.py                 # BaseAgent — Template Method pattern (handle loop with hooks)
│   ├── fallback.py             # FallbackAgent (greetings, off-topic, unrecognized input)
│   ├── preference.py           # PreferenceAgent
│   ├── suggestion.py           # SuggestionAgent
│   └── invite.py               # InviteAgent
│
├── core/                       # Core infrastructure
│   ├── __init__.py
│   ├── orchestrator.py         # OrchestratorAgent (routes messages to agents)
│   ├── event_manager.py        # EventManager singleton (moved from event.py)
│   ├── event.py                # Event models (MessageReceiveEvent, UrlVerificationEvent)
│   ├── callback_manager.py     # CallbackManager singleton (card action dispatch)
│   ├── session_store.py        # InMemorySessionStore implementation
│   ├── tool_registry.py        # ToolRegistry (registers and executes tools)
│   └── agent_factory.py        # AgentFactory — Factory pattern (centralizes agent DI wiring)
│
├── llm/                        # LLM client implementations
│   ├── __init__.py
│   └── mock_client.py          # MockLLMClient (keyword-matching, no real API)
│
├── tools/                      # Concrete tool implementations
│   ├── __init__.py
│   ├── send_text.py            # SendTextTool
│   ├── send_card.py            # SendCardTool
│   ├── get_weather.py          # GetWeatherTool
│   ├── search_buddies.py       # SearchBuddiesTool
│   └── create_group_chat.py    # CreateGroupChatTool
│
├── cards/                      # Lark interactive card builders
│   ├── __init__.py
│   ├── suggestions.py          # build_suggestions_card()
│   ├── buddies.py              # build_buddy_card()
│   └── confirmation.py         # build_confirmation_card(), build_confirmed_card()
│
├── data/                       # Mock data
│   ├── __init__.py
│   └── mock_data.py            # MOCK_ACTIVITIES, MOCK_BUDDIES, MOCK_WEATHER
│
└── tests/                      # Tests
    ├── __init__.py
    ├── test_session_store.py
    ├── test_agents.py
    ├── test_orchestrator.py
    └── test_tools.py
```

---

## Interfaces

### `api/interfaces/agent.py` — IAgent + AgentResult

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

@dataclass
class AgentResult:
    session_updates: dict = field(default_factory=dict)  # Fields to merge into session
    response: str = ""                                    # Optional text (if not sent via tool)

class IAgent(ABC):
    WRITABLE_FIELDS: set = set()  # Fields this agent is permitted to update

    @abstractmethod
    def handle(self, user_id: str, message: str, session: dict, context: dict = None) -> AgentResult:
        """
        Process a user message given current session state.
        Agents do NOT read/write the session store directly — they receive
        the current session and return an AgentResult with updates.
        The orchestrator applies WRITABLE_FIELDS filtering and writes to the store.
        Args:
            user_id: Lark open_id of the user
            message: Text content of the message
            session: Current session state (read-only — return updates via AgentResult)
            context: Optional dict with extra context (e.g., card action data)
        Returns:
            AgentResult with session_updates and optional response text
        """
        pass

    @abstractmethod
    def agent_name(self) -> str:
        """Return a unique identifier for this agent."""
        pass
```

### `api/interfaces/llm_client.py` — ILLMClient + Response Models

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

@dataclass
class ToolCall:
    name: str
    arguments: dict = field(default_factory=dict)

@dataclass
class LLMResponse:
    content: str                           # Text response from the LLM
    tool_calls: list[ToolCall] = field(default_factory=list)  # Tool calls to execute
    finish_reason: str = "stop"            # "stop" | "tool_use"
    raw: dict = field(default_factory=dict)  # Original API response for debugging

class ILLMClient(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], tools: list[dict] = None) -> LLMResponse:
        """
        Send messages to LLM, optionally with tool definitions.
        Returns a structured LLMResponse.
        """
        pass
```

### `api/interfaces/session_store.py` — ISessionStore

```python
from abc import ABC, abstractmethod

class ISessionStore(ABC):
    @abstractmethod
    def get(self, user_id: str) -> dict:
        """Return session dict for user, or default if none exists."""
        pass

    @abstractmethod
    def update(self, user_id: str, patch: dict) -> dict:
        """Merge patch into session, return updated session."""
        pass

    @abstractmethod
    def clear(self, user_id: str) -> None:
        """Reset session for user."""
        pass
```

### `api/interfaces/tool.py` — ITool

```python
from abc import ABC, abstractmethod

class ITool(ABC):
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    def parameters_schema(self) -> dict:
        """Return JSON Schema for tool arguments."""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> dict:
        """Execute the tool and return a result dict."""
        pass

    def to_llm_schema(self) -> dict:
        """Convert to LLM function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": self.parameters_schema(),
            }
        }
```

---

## Session Store Schema

```python
DEFAULT_SESSION = {
    "phase": "idle",              # idle | gathering | suggesting | inviting | confirmed
    "intent_profile": {},         # {activity, budget, vibe, availability, location}
    "suggestions": [],            # [{id, name, type, reason, ...}]
    "selected_suggestion": None,  # suggestion id string
    "buddy_candidates": [],       # [{id, name, open_id, interests}]
    "selected_buddies": [],       # [buddy_id strings]
    "confirmation_status": None,  # None | pending | confirmed | cancelled
}
```

---

## Orchestrator State Machine

```
phase="idle"       + greeting/off-topic    --> FallbackAgent    (phase stays "idle")
phase="idle"       + activity-related msg  --> PreferenceAgent  (phase="gathering")
phase="gathering"  + text message          --> PreferenceAgent
                     if profile complete   --> auto-chain to SuggestionAgent (phase="suggesting")
phase="suggesting" + card:select_suggestion --> InviteAgent (phase="inviting")
phase="suggesting" + card:reset            --> PreferenceAgent with context=reset
phase="inviting"   + card:select_buddy     --> InviteAgent (add buddy to selected)
phase="inviting"   + card:buddies_confirmed --> InviteAgent (phase stays, status="pending")
phase="inviting"   + card:confirm          --> InviteAgent sends invites (phase="confirmed")
phase="inviting"   + card:cancel           --> SuggestionAgent (back to suggesting)
phase="confirmed"  + any message           --> FallbackAgent ("Plan confirmed! Want to plan another?")
any phase          + "start over"/"reset"  --> PreferenceAgent with context=reset (phase="idle")
```

The orchestrator uses the MockLLMClient to classify idle-phase messages as greeting/off-topic vs activity-related, determining whether to route to FallbackAgent or PreferenceAgent.

---

## Design Patterns

### 1. Template Method — `BaseAgent.handle()`
The base agent defines the invariant handle loop, with overridable hooks. Agents do NOT access the session store — they receive session state and return `AgentResult`:

```python
class BaseAgent(IAgent):
    def __init__(self, llm_client: ILLMClient, tool_registry: ToolRegistry):
        self.llm = llm_client
        self.tools = tool_registry

    def handle(self, user_id, message, session, context=None) -> AgentResult:
        prompt = self._build_prompt(session, message, context)   # Hook 1: each agent builds its own prompt
        response = self.llm.chat(prompt, self._get_tool_schemas())
        tool_results = self._execute_tools(response.tool_calls)  # Shared: execute any tool calls
        return self._process_response(session, response, tool_results)  # Hook 2: returns AgentResult

    @abstractmethod
    def _build_prompt(self, session, message, context): ...

    @abstractmethod
    def _process_response(self, session, response, tool_results) -> AgentResult: ...

    def _get_tool_schemas(self): ...   # Shared default, can be overridden
    def _execute_tools(self, tool_calls): ...  # Shared
```

Note: `session_store` is NOT injected into agents. The orchestrator owns all session I/O.

### 2. Factory — `AgentFactory`
Centralizes agent creation and DI wiring. `index.py` calls the factory instead of manually constructing agents:

```python
class AgentFactory:
    def __init__(self, llm_client: ILLMClient, session_store: ISessionStore, message_api_client: MessageApiClient):
        self._llm = llm_client
        self._session = session_store
        self._msg_client = message_api_client

    def create_fallback_agent(self) -> IAgent:
        tools = ToolRegistry()
        tools.register(SendTextTool(self._msg_client))
        return FallbackAgent(self._llm, tools)

    def create_preference_agent(self) -> IAgent:
        tools = ToolRegistry()
        tools.register(SendTextTool(self._msg_client))
        return PreferenceAgent(self._llm, tools)  # No session_store

    def create_suggestion_agent(self) -> IAgent:
        tools = ToolRegistry()
        tools.register(SendCardTool(self._msg_client))
        tools.register(GetWeatherTool())
        return SuggestionAgent(self._llm, tools)

    def create_invite_agent(self) -> IAgent:
        tools = ToolRegistry()
        tools.register(SendTextTool(self._msg_client))
        tools.register(SendCardTool(self._msg_client))
        tools.register(SearchBuddiesTool())
        tools.register(CreateGroupChatTool(self._msg_client))
        return InviteAgent(self._llm, tools)

    def create_orchestrator(self) -> OrchestratorAgent:
        return OrchestratorAgent(
            fallback_agent=self.create_fallback_agent(),
            preference_agent=self.create_preference_agent(),
            suggestion_agent=self.create_suggestion_agent(),
            invite_agent=self.create_invite_agent(),
            session_store=self._session,        # Only orchestrator gets session_store
            message_api_client=self._msg_client,
        )
```

### 3. Singleton — EventManager, CallbackManager
Both enforce a single registry instance per process.

### 4. Registry — EventManager, CallbackManager, ToolRegistry
Decorator-based handler registration for extensible dispatch.

### 5. Strategy (implicit via interfaces)
`ILLMClient` and `ISessionStore` are strategy interfaces — the concrete implementation is injected at construction time and can be swapped without changing agent code.

---

## Singletons

### EventManager (`api/core/event_manager.py` — moved from `api/event.py`)
Moved to `core/` to group with CallbackManager. Event models (`MessageReceiveEvent`, `UrlVerificationEvent`, `Event` base class, `InvalidEventException`) move to `api/core/event.py`. The old `api/event.py` is replaced by these two files.

### CallbackManager (`api/core/callback_manager.py`)

```python
class CallbackManager:
    """Singleton that handles Lark interactive card action callbacks."""
    _instance = None
    _action_handlers: dict[str, Callable] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, action_type: str) -> Callable:
        """Decorator to register a handler for a card action type."""
        def decorator(f): ...
        return decorator

    def handle(self, action_data: dict) -> dict:
        """
        Parse card action payload, look up handler, execute.
        Validates token. Extracts open_id and action value.
        """
        pass
```

**Card action types registered:**
- `select_suggestion` — user picks an activity from the suggestions card
- `select_buddy` — user picks a buddy
- `buddies_confirmed` — user finishes buddy selection
- `confirm` — user confirms the plan
- `cancel` — user cancels
- `reset` — user starts over
- `quick_preference` — user clicks a quick-select activity button

All handlers call through to `orchestrator.handle()` with the appropriate card_action context.

---

## Implementation Details

### 1. `api/data/mock_data.py`
- 6 activities (hiking, nightlife, dining, beach, indoor) with id, name, type, budget, vibe, reason
- 4 mock buddies with id, name, open_id, interests list
- Mock weather for Saturday/Sunday

### 2. `api/core/session_store.py` — `InMemorySessionStore(ISessionStore)`
- Uses a module-level dict keyed by open_id
- `get()` returns deep copy of `DEFAULT_SESSION` if no session exists
- `update()` does **shallow top-level merge only** — e.g., `update(uid, {"intent_profile": {...}})` replaces the entire `intent_profile` value. Agents are responsible for reading the current value, merging in new fields, and writing back the complete object.
- Thread-safe for single-instance Vercel demo; interface allows Redis swap

### 3. `api/llm/mock_client.py` — `MockLLMClient(ILLMClient)`
- `chat()` returns `LLMResponse` dataclass (not a raw dict)
- Keyword matching on last user message to extract preferences
- Returns structured `ToolCall` objects when tools should be invoked
- Conversational mock responses ("Great choice! Let me find hiking options...")

### 4. `api/core/tool_registry.py` — `ToolRegistry`
- `register(tool: ITool)`, `get(name: str) -> ITool`, `get_schemas() -> list[dict]`, `execute(name, **kwargs) -> dict`
- All tools registered at app startup in `index.py`

### 5. `api/tools/` — Concrete Tools (all implement `ITool`)
Each takes dependencies via constructor:
- `SendTextTool(message_api_client)` — wraps `send_text_with_open_id()`
- `SendCardTool(message_api_client)` — wraps `send()` with `msg_type="interactive"`
- `GetWeatherTool()` — returns from `MOCK_WEATHER`
- `SearchBuddiesTool()` — filters `MOCK_BUDDIES` by activity type
- `CreateGroupChatTool(message_api_client)` — wraps Lark create chat API (mock)

### 6. `api/cards/` — Card Builders
Pure functions returning Lark interactive card dicts:
- `build_suggestions_card(suggestions, weather)` — green header, suggestion divs with "Pick this!" buttons
- `build_buddy_card(buddies, activity_name)` — purple header, buddy buttons, "Done selecting" button
- `build_confirmation_card(activity, buddies)` — orange header, "Confirm" + "Cancel" buttons
- `build_confirmed_card(activity, buddies)` — green header, final summary, no actions

Each button's `value` carries `{"action": "<type>", ...}` for CallbackManager.

### 7. `api/agents/` — Agent Implementations (all implement `IAgent` via Template Method)

**`BaseAgent(IAgent)`** — Template Method pattern:
- Constructor takes `llm_client: ILLMClient`, `tool_registry: ToolRegistry` (NO session_store)
- `handle(user_id, message, session, context)` is the template method: `_build_prompt()` → LLM call → `_execute_tools()` → `_process_response()` → return `AgentResult`
- `_build_prompt()` and `_process_response()` are abstract hooks overridden by each subclass
- `_execute_tools()` and `_get_tool_schemas()` are shared with sensible defaults
- **Field-level write permissions**: Each subclass declares `WRITABLE_FIELDS`. The orchestrator enforces this by filtering `AgentResult.session_updates` before writing to the store.

**`FallbackAgent(BaseAgent)`**:
- `agent_name() -> "fallback"`
- `WRITABLE_FIELDS = set()` (writes nothing — purely conversational)
- Handles greetings ("hi", "hello", "hey"), off-topic messages, and unrecognized input
- `_process_response()`: returns `AgentResult` with empty `session_updates` and a friendly response
- Responses: greeting → "Hey! I'm your Weekend Buddy. Ready to plan something fun? Tell me what you feel like doing!"; off-topic → "I'm best at helping plan weekend activities! What sounds fun — hiking, dining, movies?"
- Tools: `SendTextTool` (to send responses)

**`PreferenceAgent(BaseAgent)`**:
- `agent_name() -> "preference"`
- `_build_prompt()`: includes current `intent_profile` state, asks LLM to extract missing fields
- `_process_response()`: merges newly extracted fields into `intent_profile`, sets `phase="suggesting"` when all required fields present
- `WRITABLE_FIELDS = {"intent_profile", "phase", "suggestions", "selected_suggestion", "buddy_candidates", "selected_buddies", "confirmation_status"}` (all fields — needed for reset)
- Tools: `SendTextTool` (for follow-up questions)

**`SuggestionAgent(BaseAgent)`**:
- `agent_name() -> "suggestion"`
- `WRITABLE_FIELDS = {"suggestions", "phase"}`
- `_build_prompt()`: includes `intent_profile`, asks LLM to select and rank activities
- `_process_response()`: writes `suggestions` to session, triggers `SendCardTool` to send suggestions card
- Tools: `GetWeatherTool`, `SendCardTool`

**`InviteAgent(BaseAgent)`**:
- `agent_name() -> "invite"`
- `WRITABLE_FIELDS = {"selected_suggestion", "buddy_candidates", "selected_buddies", "confirmation_status", "phase"}`
- `_build_prompt()`: includes selected suggestion, buddy candidates, confirmation status
- `_process_response()`: handles buddy search → buddy card → confirmation card → send invites flow
- Tools: `SearchBuddiesTool`, `SendCardTool`, `SendTextTool`, `CreateGroupChatTool`

### 8. `api/core/agent_factory.py` — `AgentFactory` (Factory Pattern)
- Constructor takes shared dependencies: `llm_client`, `session_store`, `message_api_client`
- `create_preference_agent() -> IAgent`: creates PreferenceAgent with SendTextTool
- `create_suggestion_agent() -> IAgent`: creates SuggestionAgent with GetWeatherTool + SendCardTool
- `create_invite_agent() -> IAgent`: creates InviteAgent with all invite tools
- `create_orchestrator() -> OrchestratorAgent`: creates all 3 agents and wires them into orchestrator
- Each agent gets its own `ToolRegistry` with only the tools it needs

### 9. `api/core/orchestrator.py` — `OrchestratorAgent`
- Constructor receives pre-built agents (from factory): `preference_agent: IAgent`, `suggestion_agent: IAgent`, `invite_agent: IAgent`, plus `session_store: ISessionStore` and `message_api_client`
- **Orchestrator owns all session I/O** — it is the single point of reads and writes. Agents receive session state and return `AgentResult`. The orchestrator:
  1. Reads session via `session_store.get(user_id)`
  2. Routes to agent: `result = agent.handle(user_id, message, session, context)`
  3. Enforces `WRITABLE_FIELDS`: filters `result.session_updates` against `agent.WRITABLE_FIELDS`, logs unauthorized attempts
  4. Writes filtered updates via `session_store.update(user_id, filtered_updates)`
- `handle(user_id, message, message_type="text", card_action=None)`:
  - Read `session.phase` to determine routing
  - If card_action: determine target agent based on action type + phase, pass action as `context` to agent
  - If text: route to appropriate agent based on phase
  - Auto-chain: after applying PreferenceAgent result, check if profile is complete → immediately call SuggestionAgent
  - Detect reset keywords ("start over", "cancel", "reset") → route to PreferenceAgent with `context={"reset": True}`

```python
def _apply_agent_result(self, user_id, agent: IAgent, result: AgentResult):
    """Enforce WRITABLE_FIELDS and persist agent's session updates."""
    updates = result.session_updates
    unauthorized = set(updates.keys()) - agent.WRITABLE_FIELDS
    if unauthorized:
        logging.warning("Agent %s attempted unauthorized fields: %s", agent.agent_name(), unauthorized)
        updates = {k: v for k, v in updates.items() if k in agent.WRITABLE_FIELDS}
    self.session_store.update(user_id, updates)
```

- Card action → agent routing:
  - `select_suggestion` → InviteAgent (writes `selected_suggestion`, sets `phase="inviting"`)
  - `select_buddy`, `buddies_confirmed` → InviteAgent (writes buddy state)
  - `confirm`, `cancel` → InviteAgent (writes `confirmation_status`)
  - `reset` → PreferenceAgent (clears profile, sets `phase="idle"`)
  - `quick_preference` → PreferenceAgent (writes activity to `intent_profile`)

### 10. `api/core/event_manager.py` + `api/core/event.py` — EventManager (moved from `api/event.py`)
- `event_manager.py`: `EventManager` singleton with decorator-based handler registration (same pattern as before)
- `event.py`: Event models (`Event` base, `MessageReceiveEvent`, `UrlVerificationEvent`, `InvalidEventException`)
- Old `api/event.py` is removed; imports in `index.py` updated accordingly

### 11. `api/core/callback_manager.py` — `CallbackManager` (singleton)
- Singleton pattern via `__new__`
- `register(action_type)` decorator for action handlers
- `handle(action_data)` validates token, extracts open_id + action value, dispatches to handler
- Each handler updates session and returns the updated phase for orchestrator routing

### 12. `api/index.py` changes
- Slim entry point — delegates all logic to core
- Uses `AgentFactory` to create orchestrator (no manual agent wiring)
- Registers event handlers with `EventManager`
- Adds `POST /card_action` route that delegates to `CallbackManager`
- `sys.path` entries for subdirectories to support imports

### 13. `api/lark_client.py` changes
- Add `send_card(receive_id_type, receive_id, card_content)` — calls `self.send()` with `msg_type="interactive"` and JSON-serialized card content

---

## Implementation Order

1. **Interfaces**: `api/interfaces/` — agent.py, session_store.py, llm_client.py, tool.py
2. **Data**: `api/data/mock_data.py`
3. **Core infra**: `api/core/session_store.py`, `api/core/tool_registry.py`, `api/core/event_manager.py`, `api/core/event.py`, `api/core/callback_manager.py`
4. **LLM**: `api/llm/mock_client.py`
5. **Tools**: `api/tools/` — all 5 tool implementations
6. **Cards**: `api/cards/` — suggestions, buddies, confirmation builders
7. **Agents**: `api/agents/` — base.py (Template Method), fallback.py, preference.py, suggestion.py, invite.py
8. **Factory + Orchestrator**: `api/core/agent_factory.py`, `api/core/orchestrator.py`
9. **Modify existing**: `api/lark_client.py` (add send_card), `api/index.py` (slim entry point using AgentFactory)
10. **Remove old**: delete `api/event.py` (replaced by `api/core/event_manager.py` + `api/core/event.py`)
11. **Tests**: `api/tests/`

---

## Verification

1. **Unit tests**: `python -m pytest api/tests/` — validates session store, agent logic, orchestrator routing, full flow
2. **Local server**: `python api/index.py` on port 3000 — test with curl simulating Lark webhook payloads
3. **Lark bot**: Deploy to Vercel, configure webhook URL + card action URL, test in Feishu chat
4. **Card actions**: Configure card action URL in Lark app console to `<vercel-url>/card_action`, click buttons through full flow

---

## Error Handling Strategy

All exceptions should be caught and logged at appropriate boundaries. The bot should never crash silently — errors are logged with context, and the user gets a friendly fallback message.

### Layered Error Handling

| Layer | What to catch | Logging | User-facing response |
|---|---|---|---|
| **Flask route handler** (`index.py`) | All unhandled exceptions | `logging.exception("Unhandled error processing event for user %s", open_id)` | Return `jsonify()` with 200 (Lark retries on non-200) |
| **Orchestrator** | Agent errors, routing errors | `logging.error("Agent %s failed for user %s: %s", agent_name, user_id, e)` | Send text: "Something went wrong. Let's try again — what would you like to do this weekend?" + reset session to idle |
| **BaseAgent.handle()** | LLM call failures, tool execution errors | `logging.error("Tool %s failed: %s", tool_name, e, exc_info=True)` | Return session unchanged (orchestrator handles fallback) |
| **Tool.execute()** | HTTP errors (Lark API), data errors | `logging.warning("Tool %s execution error: %s", self.name(), e)` | Return `{"error": str(e)}` dict (agent decides how to handle) |
| **CallbackManager** | Invalid token, missing handler, malformed payload | `logging.warning("Card callback rejected: %s", reason)` | Return 200 silently (don't leak info on invalid requests) |
| **Session Store** | KeyError, deep copy failures | `logging.error("Session store error for %s: %s", user_id, e)` | Return default session (graceful degradation) |

### Guidelines
- Use `logging.exception()` (includes traceback) for unexpected errors
- Use `logging.error()` for expected-but-problematic errors (agent failure, API timeout)
- Use `logging.warning()` for recoverable issues (invalid card action, missing session)
- Include `user_id` and `agent_name` in all log messages for traceability
- Never expose internal error details to the user — always send a friendly fallback message
- Always return HTTP 200 to Lark webhooks (non-200 triggers retries which can cause duplicate processing)

---

## Edge Cases to Handle

| # | Edge Case | Where | Handling |
|---|---|---|---|
| 1 | **Duplicate Lark events** | `index.py` | Deduplicate by `message_id` — keep a set of recently seen IDs (TTL ~60s). Return 200 but skip processing. |
| 2 | **Non-text messages** | `index.py` | Reply "I can only process text messages for now." (already partially handled) |
| 3 | **@mention prefix in group chats** | `index.py` | Strip `@_user_X` prefix from message content before passing to orchestrator |
| 4 | **Cold start / session loss** | Orchestrator | If a card action arrives but session is `idle` (lost), send "Let's start fresh!" and reset to preference gathering |
| 5 | **Stale card button clicks** | Orchestrator | Validate `selected_suggestion` ID exists in current `suggestions` list. If not, send "That option is no longer available" |
| 6 | **Minimum viable profile** | Orchestrator | Profile is "complete" when at least `activity` is set. Other fields (`budget`, `vibe`, `availability`) get sensible defaults if missing |
| 7 | **User changes mind mid-flow** | Orchestrator | Detect reset keywords ("start over", "cancel", "reset") in any phase and clear session |
| 8 | **No matching activities** | SuggestionAgent | If no activities match filters, relax filters and suggest top activities with a "closest matches" note |
| 9 | **No matching buddies** | InviteAgent | Offer to proceed solo or show all buddies regardless of interest match |
| 10 | **Unrecognized input to MockLLM** | MockLLMClient | Return a generic helpful response asking the user to clarify, never crash or return empty |

---

## Key Design Decisions

- **Production-grade directory structure** — `interfaces/`, `agents/`, `core/`, `llm/`, `tools/`, `cards/`, `data/`, `tests/` mirrors how a real multi-agent system would be organized
- **All agents implement `IAgent`** — enforces uniform `handle()` contract; orchestrator routes via the interface, doesn't know about concrete implementations
- **Orchestrator owns all session I/O** — agents receive session state and return `AgentResult`; orchestrator applies `WRITABLE_FIELDS` filtering and persists. Single point of control for all reads and writes.
- **Template Method in BaseAgent** — `handle()` defines the invariant loop; subclasses override `_build_prompt()` and `_process_response()` hooks. New agents only need to implement these two methods.
- **AgentFactory** — centralizes agent creation and DI wiring. `index.py` stays slim. Adding a new agent = one new factory method + one line in `create_orchestrator()`.
- **EventManager + CallbackManager co-located in `core/`** — both are singletons for Lark event dispatch; grouping them reflects their shared responsibility.
- **`LLMResponse` + `ToolCall` dataclasses** — all LLM responses have a defined structure; no raw dict parsing in agent code
- **Singleton pattern** — `EventManager` and `CallbackManager` both use `__new__`-based singleton to ensure one registry per process
- **Strategy via interfaces** — `ILLMClient` and `ISessionStore` are implicit strategy interfaces; swapping `MockLLMClient` → `OpenAILLMClient` requires zero agent code changes
- **Dependency injection everywhere** — session store, LLM client, message client, tools all injected via constructors; every component is independently testable and swappable
- **WRITABLE_FIELDS enforcement** — each agent declares which session fields it can update; orchestrator filters unauthorized writes and logs warnings
- **Shallow merge in session store** — `update()` does top-level merge only; agents are responsible for reading, merging, and writing back nested fields like `intent_profile`
- **`phase` as orchestrator routing key** — single top-level session field; agents don't know about routing, only about their own domain
- **Auto-chaining** — orchestrator calls SuggestionAgent immediately when PreferenceAgent completes profile (avoids extra round-trip)
- **FallbackAgent** — dedicated agent for greetings and off-topic; prevents PreferenceAgent from awkwardly extracting preferences from "hello"
