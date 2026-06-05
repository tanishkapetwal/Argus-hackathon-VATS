# Contributing — how to extend the system (the "baton" guide)

The RFP explicitly rewards solutions a **future team can extend** with minimal change. This
guide is the proof: adding an agent, a tool, or a provider should be a small, contained edit.
If you find yourself editing many existing files to add one agent, the abstraction is wrong —
fix it here, not with a workaround.

---

## A. Add a new agent (the main extension path)

Worked example: adding a **Sleep & Recovery Agent**.

1. **Write the spec.** Copy the template in [agents/README.md](agents/README.md) to
   `docs/agents/sleep-recovery-agent.md`. Decide: its one responsibility, inputs, outputs,
   tools, who it influences, who influences it, and what's lost if removed. Add a row to the
   roster table.

2. **Add schemas (if it produces a new output).** In `backend/app/schemas/`, add the Pydantic
   model(s) it emits (e.g. `RecoveryPlan`) and any new `ConflictType` it can raise. Update
   [data-models.md](data-models.md) to match. Add fields to `PlanState` for its output.

3. **Implement the agent.** Create `backend/app/agents/sleep_recovery.py` extending
   `BaseAgent`. Implement `async def run(self, ctx) -> AgentResult`. Declare `name`,
   `input_schema`, `output_schema`, and `tools`. Use `ctx.llm`, `ctx.tools`, and `ctx.emit`.

4. **Register it.** Decorate/register with the `AgentRegistry` (`@register("sleep_recovery")`
   or `registry.add(...)`). The registry is the single seam — nothing else imports the agent
   directly.

5. **Place it in the graph.** In `backend/app/orchestration/graph.py`, add the node and its
   edges (e.g. after Fitness, before Budget). If it can be challenged, make sure the Critic
   knows about its conflict types and the conditional edge can route revisions to it.

6. **Trace/UI is automatic.** Because the UI is a pure function of the `TraceEvent` stream, the
   new agent appears as a node as soon as it emits events. Optionally add a color/icon entry in
   `frontend/src/lib/agentMeta.ts` (one line) — no other UI change needed.

7. **Test.** Add a unit test for any deterministic tool it uses and a contract test asserting
   it emits the right events and produces a valid output model.

That's it — steps touch only: one new spec, one new agent file, registry, graph wiring, and
(optionally) one UI metadata line. No existing agent is modified.

## B. Add a new tool

1. Create `backend/app/tools/<tool>.py` as a typed callable with a docstring and **graceful
   degradation** (timeout → typed fallback). 
2. Register it in the tool registry so agents can declare it.
3. Grant it to an agent by adding the tool name to that agent's declared `tools`.
4. Add a unit test (mock the external call; test the fallback path too).
5. Document any new env vars in `.env.example` and [tech-stack.md](tech-stack.md).

## C. Add or swap an LLM provider

1. Implement the `LLMProvider` interface in `backend/app/llm/<provider>.py` (`complete()` with
   plain / tool-calling / structured-output support).
2. Add it to `get_provider()` in `backend/app/llm/factory.py` keyed by `LLM_PROVIDER`.
3. Add its env vars to `.env.example`.
4. No agent changes — agents depend on the interface and request a tier ("strong"/"fast").

## D. Add a new conflict type / resolution rule

1. Extend `ConflictType` in `schemas/`.
2. Teach the Critic to detect it (prompt + any deterministic precheck) — see
   [agents/critic-agent.md](agents/critic-agent.md).
3. Place it in the Resolver's priority order in [orchestration.md](orchestration.md) §6 and the
   Resolver prompt.

## Conventions

- **Python:** type-hint everything; `ruff` clean; Pydantic v2 models for all boundaries; async
  for any I/O; no bare `except`. Keep agent files thin — push shared behavior into `BaseAgent`.
- **Naming:** agent registry names are lowercase snake_case and are the *same strings* used in
  `target_agents`, messages, and the UI. Define them once as constants; don't scatter literals.
- **Determinism:** if it's math, it's a tool, not the LLM. Cache external lookups.
- **Tracing:** never write business logic in the trace layer; never let an agent skip emitting
  its I/O. The trace is a deliverable, not a debug aid.
- **Safety:** medical constraints are hard. No code path may relax them for cost or goal speed.
- **Docs-in-step:** update the relevant `docs/` file in the same change as the code. The spec
  and the code must never disagree (that's how the baton gets dropped).

## Definition of done for any change

- [ ] Spec/docs updated in the same commit.
- [ ] Typed I/O (Pydantic) at every boundary.
- [ ] Trace events emitted for new agent/tool activity.
- [ ] Tests for deterministic logic + a contract test for new agents.
- [ ] `.env.example` updated for new config.
- [ ] No existing agent modified just to add a new one (if you had to, reconsider the seam).
