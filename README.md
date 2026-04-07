# Weekend Buddy Agent

A Feishu (Lark) bot that helps users navigate the full social friction loop of planning a weekend activity — from choosing what to do, to finding the right people, to sending the invites.

---

## Demo

[▶ Watch the demo](https://drive.google.com/file/d/1LYouf2afoTI-5HCdRU3cV69LYJXewLN5/view?usp=sharing)

---

## The Problem Being Solved and MVP Scope

Planning a weekend often stalls not because people lack ideas, but because of the coordination overhead: picking an activity everyone enjoys, figuring out who to invite, and actually sending the message. **Weekend Buddy Agent** guides a user through the entire loop in a single conversation.

**Core user flow:**
1. Gather user preferences (activity type, budget, vibe, location, availability)
2. Suggest matching activities
3. Find and select buddies
4. Draft invite messages
5. Confirm the plan and send invites

In the MVP, the priorities were **intuitive UX**, **core agent architecture**, and a **functional end-to-end flow**. The V1 design deliberately assumes a **linear conversation flow** — the user moves forward through each step in sequence (preferences → suggestions → buddies → invites) without backtracking. This constraint simplifies both the routing logic and the session state model, at the cost of flexibility. Deliberately de-prioritised: non-linear flows, edge case handling (e.g. repeat card taps), and advanced Feishu integrations.

**Development process:** The project followed a spec-driven approach. Setup of the Feishu bot integration took ~30 minutes using the [Lark echo bot guide](https://open.larksuite.com/document/develop-an-echo-bot/introduction). An engineering requirements spec was then drafted in ~1 hour using Claude Code Plan Mode, after which Claude Code implemented the V1 bot. A further ~30 minutes was spent testing and manually tuning behaviour. Claude Code was also equipped with a Lark/Feishu API integration skill so it could correctly reason about message and card APIs. The full spec is available at `SPEC.md`.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | [Feishu custom bot app](https://open.larksuite.com/document/client-docs/bot-v3/bot-overview) — interactive cards and messaging via the Feishu SDK |
| **Backend** | Python · Flask · [Pydantic v2](https://docs.pydantic.dev/) · [lark-oapi](https://github.com/larksuite/oapi-sdk-python) |
| **Hosting** | [Vercel](https://robot-quick-start.vercel.app/) — serverless deployment |
| **LLM** | `MockLLMClient` (keyword-based simulation, swappable for any real LLM via `ILLMClient`) |
| **State** | In-memory session store and intent profile store (per-process) |

---

## How AI / LLMs Were Utilised

Weekend Buddy uses a **multi-agent architecture** with a central **Orchestrator** and five specialised sub-agents, each encapsulating a distinct responsibility:

| Agent | Responsibility |
|---|---|
| `PreferenceAgent` | Gathers user preferences into an `IntentProfile` via 5 sequential questions |
| `SuggestionAgent` | Suggests relevant activities based on the user's profile, with personalised "why" explanations |
| `BuddyAgent` | Handles potential buddy search and multi-select |
| `InviteAgent` | Drafts the invite message and sends final confirmation |
| `FallbackAgent` | Handles greetings and off-topic messages |

**Key architectural decisions:**

- `index.py`, `EventManager`, and `CallbackManager` handle the Feishu webhook boilerplate and route all events to the Orchestrator. All user interaction and session mutation is centralised there, leaving sub-agents focused purely on intelligence for their task.

- **Orchestrator as a deterministic state machine.** The Orchestrator does not call the LLM — it is pure routing logic. The session moves forward through a fixed sequence of phases (`IDLE → GATHERING → SUGGESTING → INVITING → CONFIRMED`) and the Orchestrator uses the current phase to decide which agent handles each message. This design encodes the V1 assumption of linear conversation flows directly into the architecture: each phase has exactly one valid next step, which makes the system easy to debug and reason about. The trade-off is that mid-flow corrections ("oops, I picked the wrong activity") are not supported without an explicit "start over".

- **BaseAgent pipeline.** Every sub-agent follows the same four-step template method: `_build_prompt → llm.chat → _execute_tools → _process_response`. This is the same pipeline pattern used by frameworks like LangChain and LlamaIndex — it makes sub-agents interchangeable, independently testable, and straightforward to extend.

- **Structured LLM output.** `PreferenceAgent` instructs the LLM to return structured JSON (`{"extracted_preferences": {"activity": "hiking", "budget": "low"}}`), which it then parses and merges field-by-field into the `IntentProfile`. This mirrors the structured output / JSON mode offered by real LLM APIs (OpenAI, Gemini) and is the key pattern for reliable, parseable agent responses.

- **WRITABLE_FIELDS as agent containment.** Each agent declares exactly which session fields it is allowed to mutate — `SuggestionAgent` can only write `suggestions` and `phase`; `BuddyAgent` can only write `buddy_candidates` and `selected_buddies`, and so on. `SessionService` enforces these boundaries at runtime and logs a warning if an agent attempts an unauthorised write. This prevents one agent from accidentally corrupting state owned by another.

- **Two-tier memory design.** `SessionState` is working memory — it tracks the active planning session and is cleared when the user says "start over". `IntentProfile` is long-term memory — it persists across resets in a separate `IntentProfileStore` and is never cleared. This separation means a user can abandon a session and still type *"same as last time"* in a future conversation to restore their preferences and skip straight to suggestions.

- `SessionStore` manages conversational state — tracking where the user is in the planning flow across turns.
- All LLM logic lives in `MockLLMClient`, which simulates a real LLM API (OpenAI, Gemini) using keyword matching to generate text responses and tool calls from natural language input. Because `MockLLMClient` is injected via the `ILLMClient` interface, swapping it for a real LLM in production is a one-line change in `AgentFactory`.
- Like a real LLM API, `MockLLMClient` supports **tool calls** — `get_weather`, `search_buddies`, `send_feishu_message`, and `send_feishu_card` — executed by the agent after each LLM response.
- `AgentFactory` centralises agent creation and tool registration, making the dependency graph explicit and testable.

---

## V2 Improvements

**Agent intelligence**
- *LLM-powered Orchestrator:* Replace the deterministic phase-based router with an LLM-powered `OrchestratorAgent` that dynamically selects which agent to invoke based on user intent. This would unlock mid-flow corrections ("oops, I picked the wrong activity") and non-linear conversations that the current state machine cannot handle.
- *Smarter preference gathering:* Accept free-form input ("something cheap and adventurous on Saturday") and extract multiple fields in one turn, skipping questions that are already answered.
- *Conflict detection:* If the user requests contradictory preferences (e.g. "luxury hiking"), surface a clarification question instead of silently picking the closest match.
- *Persistent conversation history:* Pass full message history to the LLM so agents can reference any previous session — not just the most recent `IntentProfile`.

**Feishu integration**
- Integrate with Feishu Contacts and Calendar to send calendar invites to confirmed attendees alongside the chat message.
- Support group chat mode so the bot can coordinate preferences across multiple participants simultaneously, rather than planning on behalf of a single user.

**Infrastructure**
- Migrate from Flask to FastAPI for better performance and async handling of concurrent requests.
- Replace the in-memory session and preference stores with persistent Redis or a database so data survives server restarts and Vercel cold starts.
