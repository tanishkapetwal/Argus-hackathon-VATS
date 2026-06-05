# Tech stack — decisions & rationale

All choices below are **decided**. Don't swap them without asking the team. Versions are
minimum targets; pin exact versions in `pyproject.toml` / `package.json` at build time.

## Backend

| Concern | Choice | Version | Why |
|---------|--------|---------|-----|
| Language | Python | 3.11+ | Best agent/LLM ecosystem; Pydantic + LangGraph are first-class. |
| Orchestration | **LangGraph** | ≥0.2 | Stateful graph of agent nodes with explicit edges, conditional routing, and a shared state object — maps directly onto our debate→critic→resolver loop and makes interdependency legible. |
| LLM abstraction | Custom `LLMProvider` interface | — | The team chose *configurable / multi-provider*. Agents depend on an interface, not a vendor. Default impl is Anthropic; OpenAI impl is a drop-in. See [architecture.md](architecture.md) §LLM layer. |
| LLM SDK (default) | `anthropic` | latest | Default provider. Models: `claude-opus-4-8` (strong), `claude-haiku-4-5-20251001` (fast). |
| Structured I/O | **Pydantic v2** | ≥2.5 | Every inter-agent message is a validated model. Also used for LLM structured-output parsing. |
| Web framework | **FastAPI** | ≥0.110 | Async, typed, trivial WebSocket support for the live trace stream. |
| Live streaming | **WebSocket** (FastAPI) | — | The team chose live streaming. Each trace event is pushed to the UI as it happens. |
| HTTP client | `httpx` | ≥0.27 | Async calls to USDA / web search / price APIs. |
| Config | `pydantic-settings` | ≥2.0 | Loads `.env` into a typed `Settings` object. |
| Testing | `pytest` + `pytest-asyncio` | — | Unit tests for tools (esp. deterministic macro math) and agent contracts. |
| Lint/format | `ruff` | — | Single fast tool for lint + format. |

## Frontend

| Concern | Choice | Why |
|---------|--------|-----|
| Framework | **React** | Component model fits the trace view (agent cards, message edges, plan panels). |
| Build tool | **Vite** + **TypeScript** | Fast dev server; types mirror the backend Pydantic schemas. |
| Styling | **Tailwind CSS** | Rapid, consistent UI for a demo. |
| Realtime | Native `WebSocket` | Subscribes to the backend trace stream; updates the graph live. |
| Graph viz | **React Flow** (recommended) or a simple custom SVG/DOM layout | Renders agents as nodes and `MESSAGE_SENT`/`REVISION_REQUESTED` as animated edges. React Flow is the recommended default; a hand-rolled layout is acceptable if simpler. |
| State | React hooks / lightweight store (Zustand optional) | Trace state is mostly an append-only event log + derived view. |

## Real external tools (the "real APIs where feasible" decision)

| Tool | Provider | Used by | Notes |
|------|----------|---------|-------|
| Food / nutrient data | **USDA FoodData Central** (free API key) | Nutrition Agent | Real nutrient lookups for foods in the diet. |
| Web search | **Tavily** (default; pluggable) | Medical Risk, Fitness, Budget (as needed) | Current guidelines, local prices, supplement info. Abstracted behind a `web_search` tool. |
| Grocery / price data | Price API **or seeded fallback** | Budget Agent | Region-specific live pricing can be flaky in a demo — `USE_SEEDED_PRICES=true` forces a deterministic local price table (`data/seed_prices.json`). |
| Macro calculation | **Deterministic Python** (no API, no LLM) | Nutrition Agent | BMR (Mifflin–St Jeor), TDEE (activity multiplier), goal-adjusted calories, macro split. Exact math, fully testable. |

> **Tool design rule:** every tool is a plain Python callable with a typed signature and a
> docstring, registered so an agent can call it. Tools must degrade gracefully (timeout →
> fallback) so a flaky API never breaks a live demo.

## LLM model selection policy

Per-agent model choice is configuration, not hard-coded:

- **Strong model** (`LLM_MODEL_STRONG`) for reasoning-heavy agents: Medical Risk, Critic,
  Resolver, and the planning parts of Nutrition/Fitness.
- **Fast model** (`LLM_MODEL_FAST`) for lighter formatting/summarization steps.
- Because the LLM is behind `LLMProvider`, switching a provider or model is a config change,
  not a code change.

## Why not alternatives (brief)

- **Why LangGraph over a hand-rolled loop?** We still get explicit control, but the graph,
  shared state, and conditional edges make the *interdependency* visually and structurally
  obvious — which is the thing being scored. It also gives clean checkpoints to emit trace
  events from.
- **Why provider-abstracted LLM?** Team decision; avoids vendor lock-in and lets us tune cost
  vs quality per agent. Default stays Claude.
- **Why deterministic macros?** Reliability + reasoning quality (25%). LLMs should reason
  about *what* to eat, not compute BMR arithmetic.
