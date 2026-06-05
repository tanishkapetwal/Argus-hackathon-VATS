# Architecture

How the Health Plan Optimizer is structured. Read this after [CLAUDE.md](../CLAUDE.md) and
before implementing anything. Companion docs: [orchestration.md](orchestration.md) (the graph
& debate loop), [data-models.md](data-models.md) (schemas), [trace-view.md](trace-view.md)
(the UI + event stream).

## 1. System overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (React)                              │
│   Profile form  ─┐                          ┌─►  Live Trace View          │
│                  │                          │    (agent nodes + edges)     │
│                  │                          │                              │
│                  ▼  POST /api/plan          │  WS /ws/trace/{run_id}       │
└──────────────────┼──────────────────────────┼──────────────────────────────┘
                   │                          │ (trace events stream)
┌──────────────────┼──────────────────────────┼──────────────────────────────┐
│                  ▼          BACKEND (FastAPI)│                              │
│            ┌───────────────────────────────────────────┐                   │
│            │              API layer (api/)             │                   │
│            │   POST /api/plan → start run              │                   │
│            │   WS /ws/trace/{run_id} → stream events   │                   │
│            └─────────────────────┬─────────────────────┘                   │
│                                  ▼                                          │
│            ┌───────────────────────────────────────────┐                   │
│            │       Orchestration (orchestration/)      │                   │
│            │   LangGraph: nodes = agents, shared state │                   │
│            │   debate → critic → resolver loop         │                   │
│            └───────┬───────────────────────┬───────────┘                   │
│                    │ runs each agent       │ emits trace events            │
│                    ▼                       ▼                               │
│   ┌────────────────────────────┐  ┌──────────────────────────┐            │
│   │        Agents (agents/)    │  │   TraceEmitter (core/)   │──► WS       │
│   │  BaseAgent + 6 agents      │  └──────────────────────────┘            │
│   └──────┬───────────────┬─────┘                                          │
│          │ call          │ call                                           │
│          ▼               ▼                                                 │
│   ┌─────────────┐  ┌──────────────────────────────────────┐               │
│   │  LLM layer  │  │             Tools (tools/)           │               │
│   │ (llm/)      │  │  macros calc · USDA · prices · search│               │
│   │ LLMProvider │  └──────────────────────────────────────┘               │
│   └─────────────┘                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## 2. Layers (and the module that owns each)

### `core/` — framework primitives
- **`BaseAgent`** — abstract base every agent extends. Defines the contract:
  `async def run(self, ctx: AgentContext) -> AgentResult`. Handles trace emission,
  LLM access, tool access, and structured-output parsing so individual agents stay thin.
- **`AgentRegistry`** — agents register themselves (by `name` + declared input/output
  schemas). The orchestrator builds the graph from the registry. This is the seam that
  makes the system pluggable (see [contributing.md](contributing.md)).
- **`Settings`** — typed config from `.env` (keys, models, `MAX_REFINEMENT_ROUNDS`, etc.).
- **`TraceEmitter`** — single place that creates `TraceEvent`s and fans them out to the
  WebSocket(s) for a run, and to the in-memory/append-only run log. Agents never touch the
  socket directly; they call `ctx.emit(...)`.

### `schemas/` — typed contracts (Pydantic v2)
Every object that crosses an agent boundary. The big ones: `UserProfile`, `MedicalConstraints`,
`NutritionPlan`, `FitnessPlan`, `BudgetReport`, `Critique`, `RevisionRequest`, `HealthPlan`,
`TraceEvent`, and the shared `PlanState`. Full definitions: [data-models.md](data-models.md).

### `llm/` — the provider abstraction
- **`LLMProvider`** (interface): `async def complete(messages, *, model, tools=None,
  response_model=None) -> LLMResponse`. Supports plain completion, tool/function calling,
  and structured output (parse into a Pydantic model).
- **`AnthropicProvider`** — default implementation (Claude).
- **`OpenAIProvider`** — optional drop-in.
- **`get_provider(settings)`** — factory selecting the impl from `LLM_PROVIDER`.
- Agents request a *tier* ("strong"/"fast"), not a specific model, so model choice stays config.

### `tools/` — real capabilities agents can call
- **`macros.py`** — deterministic BMR/TDEE/macro math (pure functions, unit-tested).
- **`usda.py`** — USDA FoodData Central client (food/nutrient lookup, cached).
- **`prices.py`** — grocery/equipment pricing (real API or seeded fallback).
- **`web_search.py`** — web search (Tavily by default), behind a stable interface.
- Each tool: typed signature, docstring, graceful degradation. Tools are registered so an
  agent can declare which tools it may use.

### `agents/` — the six specialists
Each extends `BaseAgent`, owns one responsibility, declares its input/output schema and the
tools it uses, and contains its prompt(s). One file per agent; one spec per agent in
[docs/agents/](agents/).

### `orchestration/` — the LangGraph
- **`state.py`** — the `PlanState` (shared graph state; see data-models).
- **`graph.py`** — builds the LangGraph: nodes (agents), edges, and conditional routing for
  the critic refinement loop. Bounded by `MAX_REFINEMENT_ROUNDS`.
- **`runner.py`** — `async def run_plan(profile, run_id, emitter) -> HealthPlan`: drives the
  graph for one request and emits trace events throughout.

### `api/` — FastAPI surface
- **`POST /api/plan`** — accepts a `UserProfile`, creates a `run_id`, kicks off the graph
  (background task), returns the `run_id`.
- **`WS /ws/trace/{run_id}`** — client subscribes; receives the `TraceEvent` stream and the
  final `HealthPlan`. (See [trace-view.md](trace-view.md) for the protocol.)
- **`GET /api/plan/{run_id}`** — fetch the final plan / full trace (for replay & non-WS clients).

## 3. The BaseAgent contract

Every agent receives an `AgentContext` and returns an `AgentResult`:

```python
class AgentContext:
    profile: UserProfile          # original user input (read-only)
    state: PlanState              # shared state: all agents' latest outputs + open conflicts
    llm: LLMProvider              # tiered LLM access
    tools: ToolBelt               # only the tools this agent declared
    emit: Callable[[TraceEvent], Awaitable[None]]   # trace emission
    round: int                    # current refinement round (0 = first pass)

class AgentResult:
    output: BaseModel             # the agent's typed output (e.g. NutritionPlan)
    messages: list[AgentMessage]  # explicit messages/influence directed at other agents
    conflicts: list[Conflict]     # conflicts this agent detected (mainly the Critic)
```

The base class wraps `run()` to automatically emit `AGENT_STARTED` before and
`AGENT_COMPLETED`/`AGENT_OUTPUT` after, and to emit `MESSAGE_SENT` for each message in the
result. Individual agents only implement the domain logic.

## 4. Data & control flow (one request)

1. UI `POST /api/plan` with a `UserProfile`. API returns `run_id`; UI opens the WS.
2. `runner.run_plan` initializes `PlanState` from the profile and starts the graph.
3. **Medical Risk Agent** runs first → writes `MedicalConstraints` into state (gate).
4. **Nutrition** and **Fitness** run, each reading the constraints; they exchange a calorie
   handshake (target calories ↔ estimated burn) via `AgentMessage`s.
5. **Budget Agent** costs the combined plan → may emit `RevisionRequest`s if over budget.
6. **Critic Agent** inspects all outputs → emits `Critique` with zero or more `Conflict`s.
7. **Conditional edge:** if conflicts exist *and* `round < MAX_REFINEMENT_ROUNDS`, route back
   to the relevant specialists with the conflicts attached; otherwise proceed.
8. **Resolver Agent** reconciles remaining conflicts and synthesizes the final `HealthPlan`
   (with a per-agent "what changed and why" summary).
9. Final plan is emitted over the WS and stored for `GET /api/plan/{run_id}`.

Throughout, every step emits `TraceEvent`s so the UI shows the debate live.

## 5. Cross-cutting principles

- **Typed everywhere.** No agent passes a raw string to another agent. If it crosses a
  boundary, it's a Pydantic model. This keeps agents decoupled and the trace meaningful.
- **Observability is built-in.** The trace event stream *is* the execution log. Persist it
  per run for replay and debugging.
- **Determinism where it matters.** Math is code; judgment is the LLM. Cache external lookups.
- **Safety is a hard filter.** `MedicalConstraints` are applied as validation on downstream
  outputs, not as polite suggestions in a prompt.
- **Bounded loops.** The refinement loop always terminates (`MAX_REFINEMENT_ROUNDS`), and the
  Resolver can always produce a plan even with unresolved conflicts (flagging them).

## 6. Failure & edge handling

| Situation | Behavior |
|-----------|----------|
| A tool/API times out | Tool returns a typed fallback (e.g. seeded prices); agent notes the degradation in its output; trace records it. |
| Medical red flag (e.g. chest pain, BP crisis) | Medical Risk Agent sets `requires_professional=true`; Resolver returns a "see a doctor first" plan instead of optimizing. |
| Conflicts unresolved after max rounds | Resolver finalizes the best coherent plan and lists remaining trade-offs explicitly. |
| LLM returns malformed structured output | Provider re-asks once with the schema; on repeat failure the agent emits an error trace event and a safe default. |
| Budget impossible even after cuts | Budget Agent reports the minimum feasible cost; Resolver presents the cheapest plan + the gap. |
