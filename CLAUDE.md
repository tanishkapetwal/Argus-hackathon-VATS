# CLAUDE.md — Health Plan Optimizer

> This file is the entry point for any AI agent (Claude Code or similar) working in
> this repository. Read it first, then follow the links into `docs/` for the full
> specification. **This repo is a *context / specification package*** — it describes
> what to build and how. The implementation is built *from* these specs.

---

## 1. What this project is

**Health Plan Optimizer** is a **Multi-Agent Decision Intelligence System** that takes a
person's health profile (body stats, goals, medical conditions, budget, food/fitness
preferences) and produces a **single, integrated, personalized health plan** —
diet + workout + cost breakdown — that respects their medical constraints and budget.

The key idea (and the thing being evaluated): **no single agent can produce a good plan
alone.** A diet that ignores a knee injury is dangerous; a workout that ignores the diet's
calorie target is incoherent; a plan that ignores the budget is useless. The specialized
agents **constrain, challenge, and revise each other** until a coherent plan emerges.

This was built for the Argusoft Hackathon Two RFP. See [docs/rfp.md](docs/rfp.md) for the
full brief and how every design decision maps to the scoring criteria.

## 2. The agents (at a glance)

| # | Agent | One-line responsibility |
|---|-------|-------------------------|
| 1 | **Medical Risk Agent** | Turns the medical profile into hard constraints + red-flag warnings. Runs first, gates everyone. |
| 2 | **Nutrition Agent** | Diet plan + macro targets (uses a deterministic Macros Calculator tool + USDA food DB). |
| 3 | **Fitness Agent** | Workout plan + estimated calorie burn; aligns energy with the diet. |
| 4 | **Budget Agent** | Costs the diet + workout; checks vs the user's budget; proposes cuts. |
| 5 | **Critic Agent** | Challenges all outputs for conflicts & safety violations; triggers refinement. |
| 6 | **Resolver Agent** | Reconciles conflicts and writes the final integrated plan + rationale. |

Each agent has a full spec in [docs/agents/](docs/agents/). **Read the agent's spec before
implementing it.**

## 3. The interaction pattern (debate → critic → resolver)

```
                 ┌─────────────────────┐
   user profile  │  Medical Risk Agent │  (gate: hard constraints + flags)
   ───────────►  └──────────┬──────────┘
                            │ constraints
              ┌─────────────┴──────────────┐
              ▼                            ▼
     ┌─────────────────┐         ┌──────────────────┐
     │ Nutrition Agent │◄───────►│  Fitness Agent   │  (calorie handshake)
     └────────┬────────┘         └────────┬─────────┘
              │ diet + macros             │ workout + burn
              └─────────────┬─────────────┘
                            ▼
                   ┌──────────────────┐
                   │   Budget Agent   │  (cost vs budget → revision asks)
                   └────────┬─────────┘
                            ▼
                   ┌──────────────────┐
                   │   Critic Agent   │  finds conflicts ──┐
                   └────────┬─────────┘                    │ if conflicts:
                            │ no conflicts                 │ loop back to
                            ▼                              │ specialists
                   ┌──────────────────┐ ◄──────────────────┘ (bounded rounds)
                   │  Resolver Agent  │  final integrated Health Plan
                   └──────────────────┘
```

Full flow, state model, and conflict-resolution rules: [docs/orchestration.md](docs/orchestration.md).

## 4. Tech stack (decided — do not re-litigate without asking)

| Layer | Choice |
|-------|--------|
| Backend language | **Python 3.11+** |
| Orchestration | **LangGraph** (stateful graph of agent nodes) |
| LLM access | **Provider-abstracted** (`LLMProvider` interface; Claude/Anthropic is the default impl) |
| Structured I/O | **Pydantic v2** models for every inter-agent message |
| Backend API | **FastAPI** + **WebSocket** (live trace streaming) |
| Frontend | **React + Vite + TypeScript + Tailwind** |
| Real external tools | **USDA FoodData Central** (nutrition), **web search**, **grocery/price data** (with seeded fallback) |
| Macros calculation | **Deterministic Python tool** (not an LLM) |

Rationale + versions: [docs/tech-stack.md](docs/tech-stack.md).

## 5. Repository layout

```
hack2/
├── CLAUDE.md                ← you are here
├── README.md                ← human-facing overview + quickstart
├── .env.example             ← required env vars (copy to .env)
├── docs/
│   ├── rfp.md               ← distilled RFP + scoring map
│   ├── tech-stack.md        ← stack decisions + versions
│   ├── architecture.md      ← system design, layers, module map
│   ├── orchestration.md     ← LangGraph graph, state, debate loop, conflict rules
│   ├── data-models.md       ← every Pydantic schema / message contract
│   ├── trace-view.md        ← trace event schema, WS protocol, UI spec
│   ├── contributing.md      ← HOW TO ADD A NEW AGENT (baton-passing guide)
│   ├── build-plan.md        ← phased, agent-executable build order
│   └── agents/              ← one spec file per agent
├── backend/
│   ├── pyproject.toml
│   └── app/
│       ├── core/            ← BaseAgent, config, registry, trace emitter
│       ├── schemas/         ← Pydantic models (see data-models.md)
│       ├── llm/             ← LLMProvider interface + Anthropic impl
│       ├── tools/           ← macros calc, USDA client, price client, web search
│       ├── agents/          ← the 6 agents
│       ├── orchestration/   ← LangGraph graph + state
│       └── api/             ← FastAPI app + WebSocket trace stream
└── frontend/
    ├── package.json
    └── src/                 ← React trace-view UI
```

## 6. How to work in this repo (rules for the AI builder)

1. **Specs are the source of truth.** Before writing code for X, read its doc in `docs/`.
   If the spec is ambiguous, prefer the choice that maximizes *agent interdependency*
   (that's 40% of the score) and *safety* (medical constraints are hard, never soft).
2. **Every inter-agent message is a Pydantic model** defined in [docs/data-models.md](docs/data-models.md).
   Agents never pass raw strings to each other — only typed, validated objects.
3. **Every agent run emits trace events** (`AGENT_STARTED`, `AGENT_OUTPUT`,
   `MESSAGE_SENT`, `CONFLICT_RAISED`, `REVISION_REQUESTED`, `AGENT_COMPLETED`). The trace
   view is a *mandatory deliverable* — do not bolt it on at the end; emit events from the start.
4. **Agents are pluggable.** New agents register via the agent registry and declare their
   inputs/outputs. Adding one must not require editing existing agents. See
   [docs/contributing.md](docs/contributing.md).
5. **The Macros Calculator is deterministic Python**, never the LLM. The Nutrition Agent
   *calls* it as a tool. LLMs must not do arithmetic that a formula can do exactly.
6. **Medical safety is non-negotiable.** The Medical Risk Agent's hard constraints are
   filters applied to every downstream output, not suggestions. Always include the
   "not medical advice / consult a professional" disclaimer in final output.
7. **Build in the order given by [docs/build-plan.md](docs/build-plan.md).** It is phased so
   the system is runnable (and demoable) at the end of each phase.

## 7. Build & run (target commands — implement to match)

```bash
# Backend
cd backend
cp ../.env.example .env          # fill in keys
pip install -e .
uvicorn app.api.main:app --reload   # serves API + WS on :8000

# Frontend
cd frontend
npm install
npm run dev                          # Vite dev server on :5173
```

A run: user submits a profile in the UI → backend executes the LangGraph → trace events
stream over WebSocket → UI animates the agent debate → final Health Plan is rendered.

## 8. Definition of done (mandatory deliverables — see rfp.md §scoring)

- [ ] ≥3 specialized agents (we have 6) with **distinct** responsibilities
- [ ] Agents **collaborate & influence each other** (constraints, calorie handshake, budget revisions, critic loop)
- [ ] A **final integrated recommendation** (the Health Plan) emerges from collaboration
- [ ] An **Agent Trace View** showing each agent's input, output, and how outputs flowed between agents
- [ ] Clean, modular, documented, **extensible** (new agent in minimal steps) — the "baton" requirement
