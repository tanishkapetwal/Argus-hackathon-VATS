# Agents

One spec file per agent. Each follows the same template so future teams (and AI builders) can
read them uniformly. **Read an agent's spec before implementing it.**

## The roster

| Agent | File | Role | Runs | Key tools |
|-------|------|------|------|-----------|
| 🩺 Medical Risk | [medical-risk-agent.md](medical-risk-agent.md) | Hard safety constraints + red-flag escalation | First (gate) | web_search |
| 🥗 Nutrition | [nutrition-agent.md](nutrition-agent.md) | Diet plan + macro targets | After Medical Risk | macros_calc (deterministic), usda |
| 🏋️ Fitness | [fitness-agent.md](fitness-agent.md) | Workout plan + calorie burn | After Medical Risk (handshakes with Nutrition) | web_search |
| 💰 Budget | [budget-agent.md](budget-agent.md) | Cost the plan, push back on overruns | After Nutrition+Fitness | prices, usda, web_search |
| 🔍 Critic | [critic-agent.md](critic-agent.md) | Challenge all outputs, raise conflicts | After Budget | — (reasons over state) |
| ⚖️ Resolver | [resolver-agent.md](resolver-agent.md) | Reconcile conflicts, write final plan | Last | — |

Execution order and the influence edges between them are defined in
[../orchestration.md](../orchestration.md). Schemas for every input/output are in
[../data-models.md](../data-models.md).

## Spec template (every agent file follows this)

1. **Identity** — name (registry key), one-line purpose, model tier.
2. **Why this agent exists** — the distinct expertise; why no other agent covers it.
3. **Inputs** — what it reads from `PlanState` / profile / routed conflicts.
4. **Outputs** — the typed model it produces + messages/conflicts it emits.
5. **Tools** — which tools it may call.
6. **Behavior / algorithm** — step-by-step what it does.
7. **Prompt design** — system prompt intent + structured-output contract.
8. **Interdependencies** — who it influences and who influences it (the trace edges).
9. **What is lost if removed** — the RFP demands this answer.
10. **Extension ideas** — for the next team.

## Agent design rules (apply to all)

- **One responsibility.** If two agents would both decide the same thing, the boundary is
  wrong — fix the boundary, don't duplicate logic.
- **Typed I/O only.** Produce a Pydantic model; never hand another agent a raw string.
- **Self-check against constraints.** Nutrition/Fitness must set `satisfies_constraints` and
  explain how — the Critic verifies, but agents shouldn't knowingly ship violations.
- **Emit trace events.** Use `ctx.emit(...)` for inputs, outputs, messages, tool calls,
  conflicts. The `BaseAgent` wrapper handles start/complete automatically.
- **Degrade gracefully.** If a tool fails, proceed with a stated assumption and note it.
- **Stay in your lane in prompts.** Each system prompt should explicitly scope the agent and
  tell it to defer out-of-scope concerns to the relevant agent (raise a message, don't decide).
