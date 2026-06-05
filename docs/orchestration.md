# Orchestration — the debate → critic → resolver loop

This is the heart of the project and the thing the RFP weights at **40%** (collaboration,
orchestration, interdependency). It describes the LangGraph graph, the shared state, the
inter-agent influence edges, the conflict-resolution rules, and the termination guarantees.

Companion: [architecture.md](architecture.md) (layers), [data-models.md](data-models.md)
(`PlanState`, `Conflict`, `RevisionRequest`, messages).

## 1. Mental model

The agents are not a pipeline that hands a document down a line. They are a **negotiation**:

- The **Medical Risk Agent** sets the rules of the game (hard constraints).
- The **Nutrition** and **Fitness** agents each propose, and must *agree on energy balance*
  with each other.
- The **Budget Agent** is the reality check that can veto both.
- The **Critic Agent** is the adversary that hunts for incoherence and unsafe advice.
- The **Resolver Agent** is the judge that ends the debate with a single coherent plan.

The "decision" (the final Health Plan) **emerges from this interaction** — exactly the
property the RFP rewards. If you implement this as six independent calls stitched together,
you've missed the point and the 40%.

## 2. The graph

Nodes are agents; the shared `PlanState` flows through. Routing:

```
START
  │
  ▼
[medical_risk]  ──── writes MedicalConstraints into state
  │
  ▼
[nutrition] ⇄ [fitness]   ──── calorie handshake (see §4); both read constraints
  │
  ▼
[budget]   ──── costs plan; may attach RevisionRequests
  │
  ▼
[critic]   ──── produces Critique with 0..n Conflicts
  │
  ▼
<conflicts? and round < MAX_REFINEMENT_ROUNDS?>
  │                         │
  │ yes                     │ no
  ▼                         ▼
[route_to_targets]      [resolver] ──► END (final HealthPlan)
  │  (re-run only the
  │   agents named in the
  │   conflicts, round += 1)
  └──────────► back into the relevant specialist nodes
```

> **Implementation note (LangGraph):** model `nutrition`/`fitness` as either two nodes with a
> small internal handshake sub-step or a combined "planning" node that runs both and resolves
> the calorie balance before returning. Either is fine; the handshake must actually happen and
> must be visible in the trace. The conditional edge after `critic` is a LangGraph conditional
> edge keyed on `state.open_conflicts` and `state.round`.

## 3. Shared state (`PlanState`)

A single object the graph threads through every node (full schema in
[data-models.md](data-models.md)). Key fields:

| Field | Meaning |
|-------|---------|
| `profile` | The user input (read-only). |
| `constraints` | `MedicalConstraints` from the Medical Risk Agent. |
| `nutrition` | Latest `NutritionPlan`. |
| `fitness` | Latest `FitnessPlan`. |
| `budget` | Latest `BudgetReport`. |
| `open_conflicts` | List of unresolved `Conflict`s from the Critic. |
| `revision_requests` | Pending `RevisionRequest`s targeted at specific agents. |
| `messages` | Append-only log of `AgentMessage`s (the influence edges). |
| `round` | Current refinement round (0-based). |
| `final_plan` | Set by the Resolver at the end. |

Agents read what they need from state and write their own slice back. They never mutate
another agent's slice — they raise a `Conflict` or send a `RevisionRequest` instead.

## 4. Inter-agent influence edges (the interdependency, made concrete)

These are the edges the trace view renders and the demo narrates. Each is a real data
dependency, not decoration.

| From → To | Carried as | What it does |
|-----------|-----------|--------------|
| Medical Risk → Nutrition | `MedicalConstraints` | e.g. `max_sugar_g`, `max_sodium_mg`, `excluded_foods`, `required_disclaimers`. The Nutrition Agent must satisfy these or the Critic will catch it. |
| Medical Risk → Fitness | `MedicalConstraints` | e.g. `forbidden_movements` (high-impact, heavy spinal load), `max_intensity`, `requires_warmup`. |
| Nutrition ⇄ Fitness | `AgentMessage` (calorie handshake) | Nutrition proposes daily calorie target for the goal; Fitness estimates weekly burn; they reconcile so intake − burn matches the goal's safe rate (e.g. ≤0.75 kg/week loss). Whoever is out of range adjusts. |
| Nutrition → Budget | `NutritionPlan` (food list + quantities) | Budget prices the groceries/supplements. |
| Fitness → Budget | `FitnessPlan` (gym/equipment needs) | Budget prices membership/equipment. |
| Budget → Nutrition / Fitness | `RevisionRequest` | If total weekly cost > budget, Budget asks the relevant agent to cut (cheaper protein sources, home workout instead of gym). |
| Critic → any specialist | `Conflict` + `RevisionRequest` | The Critic detects cross-agent incoherence and routes a fix request to the responsible agent(s). |
| All → Resolver | full state | The Resolver reads everything to synthesize and to write the "what each agent changed" summary. |

**This table is the answer to "how did one agent's output influence another."** Keep it true
in the implementation.

## 5. What the Critic checks (conflict taxonomy)

The Critic is the adversary that makes the system more than the sum of its parts. It emits a
`Conflict` (typed) for any of:

| Conflict type | Example | Routed to |
|---------------|---------|-----------|
| `MEDICAL_VIOLATION` | Diet includes 60g added sugar but constraint caps it at 25g; workout includes box jumps despite a knee flag. | Nutrition / Fitness |
| `ENERGY_IMBALANCE` | Intake − burn implies 1.5 kg/week loss (unsafe) or a surplus during a "cut" goal. | Nutrition + Fitness |
| `BUDGET_OVERRUN` | Plan costs ₹X/week vs budget ₹Y; Budget already asked for a cut and it wasn't applied. | Nutrition / Fitness |
| `MACRO_INCOHERENCE` | Protein target unreachable from the chosen foods; macros don't sum to the calorie target. | Nutrition |
| `RECOVERY_RISK` | Training volume too high for the recovery the diet supports (e.g. aggressive deficit + 6 hard sessions). | Fitness |
| `MISSING_DISCLAIMER` | A required medical disclaimer or "see a professional" escalation is absent. | Resolver |

If the Critic finds **no** conflicts, it says so explicitly (a `Critique` with an empty
conflict list) — that itself is a trace event and a signal to proceed to the Resolver.

## 6. Conflict-resolution rules (priority order)

When conflicts collide, resolve by this fixed priority. **Safety always wins; budget never
overrides safety.**

1. **Medical safety** — `MEDICAL_VIOLATION` and red-flag escalations override everything. A
   plan is never made "affordable" or "effective" by violating a medical constraint.
2. **Energy/physiological soundness** — `ENERGY_IMBALANCE` / `RECOVERY_RISK`: the plan must be
   safe and effective (e.g. cap deficit at a safe rate) before optimizing anything else.
3. **Budget feasibility** — adjust foods/equipment to fit budget *without* breaking 1–2. If
   impossible, present the minimum-feasible cost and the gap (don't silently exceed budget).
4. **User preference & adherence** — among options that satisfy 1–3, prefer the user's stated
   food/fitness preferences and the most sustainable plan.

The Resolver applies this order. The trace shows *which* rule decided each trade-off.

## 7. Termination & guarantees

- The refinement loop is bounded by `MAX_REFINEMENT_ROUNDS` (default 3, from `.env`).
- The Resolver **always** produces a `HealthPlan`, even with unresolved conflicts — it lists
  them as explicit trade-offs/caveats rather than looping forever.
- A red-flag medical condition short-circuits optimization: the Resolver returns a
  "consult a professional first" plan.
- Every node is idempotent w.r.t. trace events keyed by `(run_id, agent, round)` so re-runs in
  the loop don't corrupt the trace.

## 8. Why this scores

- **Interdependency (40%)**: §4's edges are real data dependencies; removing any agent breaks
  specific edges and degrades the plan in a way you can demonstrate live.
- **Specialization (25%)**: each node owns one concern; the Critic/Resolver split keeps
  "find problems" and "decide" as distinct skills.
- **Reasoning quality (25%)**: deterministic energy/macro math + priority-ordered resolution =
  defensible, non-arbitrary decisions.
- **Innovation/demo (10%)**: the visible debate (conflicts raised → revisions → resolution) is
  the showpiece. See [trace-view.md](trace-view.md).
