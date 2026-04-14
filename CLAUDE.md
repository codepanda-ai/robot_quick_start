# Weekend Buddy Agent

Feishu/Lark bot that guides users through weekend activity planning.
Python + Flask + Pydantic v2, deployed on Vercel.

## Commands
- Setup: `python3 -m venv myenv` + `source myenv/bin/activate`
- Install: `pip install -r requirements.txt`
- Run locally: `python api/index.py`
- Expose local server: `ngrok http 3000`
- Deploy: auto-deploys to Vercel on git push
- Unit test: `pytest api/tests/test_suggestion_agent.py`
- E2E test: use `/test` skill (browser automation against live Lark)

## Architecture
- Multi-agent orchestration with deterministic state machine (IDLE → GATHERING → SUGGESTING → INVITING → CONFIRMED)
- 5 sub-agents in `api/agents/`, each declares WRITABLE_FIELDS for session mutation
- New agents must be registered in `api/core/agent_factory.py`
- LLM is abstracted via `ILLMClient` interface; currently uses MockLLMClient

## Conventions
- Pydantic v2 syntax only (model_validate, not parse_obj)
- All user interaction goes through Feishu interactive cards (`api/cards/`)
- Data access is gated behind services (`api/services/`)
- Linear conversation flow only — no backtracking in V1
