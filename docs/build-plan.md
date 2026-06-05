# Build plan — phased, agent-executable

This is the order to build the system. It is phased so the project is **runnable and
demoable at the end of each phase** (de-risks the hackathon timeline). An AI builder should
work top-to-bottom; each task names the doc to read first and the files to create.

Legend: ☐ todo · ◐ in progress · ☑ done. Update as you go (this section answers the RFP's
"what was planned vs executed").

---

## Phase 0 — Scaffolding & contracts (foundation)
> Goal: the skeleton compiles and the types exist. No intelligence yet.

- ☐ **0.1** Backend project: `backend/pyproject.toml`, package layout under `app/`, `ruff`/
  `pytest` config. (Ref: [tech-stack.md](tech-stack.md))
- ☐ **0.2** `Settings` from `.env` via `pydantic-settings` (`app/core/config.py`).
  (Ref: [.env.example](../.env.example))
- ☐ **0.3** Implement **all** Pydantic schemas in `app/schemas/` exactly per
  [data-models.md](data-models.md). This is the contract everything else depends on — do it first.
- ☐ **0.4** `TraceEvent` + `TraceEmitter` (`app/core/trace.py`): create events with monotonic
  `seq`, fan out to subscribers, keep a per-run buffer. (Ref: [trace-view.md](trace-view.md))
- ☐ **0.5** `BaseAgent` + `AgentContext`/`AgentResult` + `AgentRegistry`
  (`app/core/base_agent.py`, `app/core/registry.py`). (Ref: [architecture.md](architecture.md) §3)
- ☐ **0.6** Frontend scaffold: Vite + React + TS + Tailwind; `src/lib/types.ts` mirroring the
  schemas; an empty trace-view shell.

**Phase 0 demo:** `uvicorn` starts; `POST /api/plan` returns a `run_id`; WS connects and
streams a hard-coded `RUN_STARTED`/`RUN_COMPLETED`. Frontend renders the (empty) graph shell.

## Phase 1 — Tools (real capabilities, deterministic first)
> Goal: the trustworthy, testable substrate the agents stand on.

- ☐ **1.1** `tools/macros.py` — deterministic BMR/TDEE/macro split. **Unit-test thoroughly**
  (known inputs → known outputs). This is the reliability backbone. (Ref:
  [nutrition-agent.md](agents/nutrition-agent.md))
- ☐ **1.2** `tools/usda.py` — USDA FoodData Central client (httpx, cached, graceful fallback).
- ☐ **1.3** `tools/prices.py` — price lookup with **seeded fallback** (`data/seed_prices.json`)
  honoring `USE_SEEDED_PRICES`.
- ☐ **1.4** `tools/web_search.py` — Tavily-backed search behind a stable interface; degrade to
  empty + assumption note on failure.
- ☐ **1.5** Tool registry + `ToolBelt` so agents get only their declared tools.

**Phase 1 demo:** a script/test calls each tool and prints results; macros math is verified.

## Phase 2 — LLM layer
- ☐ **2.1** `llm/base.py` — `LLMProvider` interface (plain / tool-calling / structured-output).
- ☐ **2.2** `llm/anthropic_provider.py` — default Claude impl (structured output → Pydantic).
- ☐ **2.3** `llm/factory.py` — `get_provider()` keyed by `LLM_PROVIDER`; tier→model mapping.
- ☐ **2.4** (optional) `llm/openai_provider.py` to prove the abstraction.

**Phase 2 demo:** a smoke test gets a structured Pydantic object back from the default provider.

## Phase 3 — Agents (one at a time, behind the contracts)
> Build in dependency order. After each, you can run the partial graph.

- ☐ **3.1** **Medical Risk Agent** → emits `MedicalConstraints`. (Ref:
  [medical-risk-agent.md](agents/medical-risk-agent.md))
- ☐ **3.2** **Nutrition Agent** → uses `macros_calc` + `usda`; calorie-handshake message stub.
  (Ref: [nutrition-agent.md](agents/nutrition-agent.md))
- ☐ **3.3** **Fitness Agent** → workout + burn; complete the calorie handshake with Nutrition.
  (Ref: [fitness-agent.md](agents/fitness-agent.md))
- ☐ **3.4** **Budget Agent** → prices plan, emits `RevisionRequest`s. (Ref:
  [budget-agent.md](agents/budget-agent.md))
- ☐ **3.5** **Critic Agent** → conflict taxonomy + deterministic prechecks → `Critique`. (Ref:
  [critic-agent.md](agents/critic-agent.md))
- ☐ **3.6** **Resolver Agent** → priority-ordered reconciliation → `HealthPlan`. (Ref:
  [resolver-agent.md](agents/resolver-agent.md))

Each agent: register it, ensure it emits `AGENT_INPUT`/`AGENT_OUTPUT`/`MESSAGE_SENT`, write a
contract test.

## Phase 4 — Orchestration (the debate loop)
- ☐ **4.1** `orchestration/state.py` — `PlanState`.
- ☐ **4.2** `orchestration/graph.py` — LangGraph: nodes, gate, calorie handshake, Budget,
  Critic, **conditional refinement edge** (conflicts + round < `MAX_REFINEMENT_ROUNDS`),
  Resolver. (Ref: [orchestration.md](orchestration.md))
- ☐ **4.3** `orchestration/runner.py` — `run_plan(profile, run_id, emitter)`; wires trace
  emission throughout; bounded loop; always finalizes.

**Phase 4 demo:** end-to-end run from a profile → final `HealthPlan` in the logs, with a visible
refinement round on a conflict-forcing profile.

## Phase 5 — API + live trace
- ☐ **5.1** `api/main.py` — FastAPI app, CORS for the frontend.
- ☐ **5.2** `POST /api/plan` (start run, background task), `GET /api/plan/{run_id}` (replay),
  `WS /ws/trace/{run_id}` (stream). (Ref: [trace-view.md](trace-view.md) §3)

## Phase 6 — Frontend trace view (the showpiece)
- ☐ **6.1** Profile form → `POST /api/plan`, open WS.
- ☐ **6.2** Agent graph (React Flow): nodes per agent, animated `MESSAGE_SENT`/conflict edges,
  status colors.
- ☐ **6.3** Inspector panel: selected agent's input/output/tools/round.
- ☐ **6.4** Execution log (streamed `TraceEvent`s).
- ☐ **6.5** Final plan panel: render `HealthPlan` incl. `agent_contributions` and disclaimers.
- ☐ **6.6** Replay via `GET /api/plan/{run_id}`.

## Phase 7 — Polish & demo readiness
- ☐ **7.1** Seed 2–3 demo profiles, including a conflict-forcing one (aggressive fat-loss +
  knee injury + tight budget + high-protein preference). (Ref: [trace-view.md](trace-view.md) §4)
- ☐ **7.2** README quickstart verified on a clean machine.
- ☐ **7.3** Error/empty/loading states; disclaimer always visible.
- ☐ **7.4** Dry-run the 90-second demo narrative against the live graph.

---

## Status (fill in during the hackathon)
- **Planned:** all of the above.
- **Executed:** _track here._
- **Cut / deferred:** _track here._

## Future extensions (for the next team / the "baton")
- Add a **Sleep & Recovery Agent** (worked example in [contributing.md](contributing.md)).
- Persist runs to a real store (swap the in-memory trace buffer).
- Multiple plan variants + user choice; PDF/calendar export; wearable data.
- Region-specific food/price databases; structured drug-interaction API for Medical Risk.
- Auth + saved profiles + progress tracking over weeks.

## Suggested first command to the AI builder
> "Read `CLAUDE.md`, then `docs/data-models.md` and `docs/architecture.md`. Execute
> [build-plan.md](build-plan.md) starting at Phase 0. Do not skip the schemas (0.3) or the
> deterministic macros tool + its tests (1.1). Keep every inter-agent boundary typed and emit
> trace events from the first agent onward."
