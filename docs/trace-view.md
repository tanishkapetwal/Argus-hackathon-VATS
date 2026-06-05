# Agent Trace View — spec

The Agent Trace View is a **mandatory deliverable**. It must show, for each agent: the
**input it received**, the **output it generated**, and **how its outputs were shared with or
influenced other agents**. It is also the demo's centerpiece (the visible "debate") and a big
part of the 10% innovation score.

Backed by the `TraceEvent` stream (see [data-models.md](data-models.md) §10). The backend
emits events live over WebSocket; the React UI renders them as they arrive.

## 1. What it must convey

1. **Per-agent input** — what each agent saw when it ran (profile slice, upstream outputs,
   any conflicts/revisions routed to it).
2. **Per-agent output** — the structured result it produced (macros, diet, workout, costs,
   critique, final plan).
3. **Influence between agents** — the edges: Medical Risk → constraints → Nutrition/Fitness,
   the Nutrition⇄Fitness calorie handshake, Budget → revision requests, Critic → conflicts →
   specialists, everything → Resolver. This is the part the RFP specifically calls out.
4. **The debate over time** — rounds, conflicts raised, revisions made, and final resolution.

## 2. Layout (recommended)

A single screen, three regions:

```
┌────────────────────────────────────────────────────────────────────────┐
│  Health Plan Optimizer · Run #abc123 · Round 2/3 · ● live                │
├──────────────────────────────┬─────────────────────────────────────────┤
│                              │                                          │
│   AGENT GRAPH (React Flow)   │   INSPECTOR (selected node/event)        │
│                              │                                          │
│   [Medical Risk]──constraints──►[Nutrition]    │  Agent: Nutrition       │
│        │                        ⇅ calories     │  Round: 1               │
│        └──constraints──►[Fitness]              │  INPUT:                  │
│                  │   │                          │   constraints {…}        │
│        [Nutrition][Fitness]──►[Budget]          │   target_kcal 2100       │
│                                  │ revision      │  OUTPUT:                 │
│                                  ▼              │   NutritionPlan {…}      │
│                              [Critic]──conflict──►(back to Nutrition)     │
│                                  │              │  TOOLS USED:             │
│                                  ▼              │   macros_calc, usda      │
│                              [Resolver]         │                          │
│                                                 │                          │
├──────────────────────────────┴─────────────────────────────────────────┤
│  EXECUTION LOG (append-only, streamed)                                    │
│  12:00:01  RUN_STARTED                                                     │
│  12:00:02  AGENT_STARTED  medical_risk                                     │
│  12:00:05  AGENT_OUTPUT   medical_risk → 2 hard limits, 1 caution          │
│  12:00:05  MESSAGE_SENT   medical_risk → nutrition (constraint)            │
│  12:00:18  CONFLICT_RAISED critic: ENERGY_IMBALANCE (nutrition, fitness)   │
│  12:00:18  REVISION_REQUESTED critic → nutrition                           │
│  …                                                                         │
└────────────────────────────────────────────────────────────────────────┘
```

- **Agent graph (top-left):** nodes = agents (colored by status: idle / running / done /
  conflict). Edges = `MESSAGE_SENT` / `REVISION_REQUESTED`, animated when active. Conflict
  edges styled distinctly (e.g. red, back-pointing).
- **Inspector (top-right):** click a node or a log row → shows that agent's input, output,
  tools used, and messages for the current round.
- **Execution log (bottom):** the raw `TraceEvent` stream, human-readable, append-only.
  Doubles as the "execution log" trace-view option the RFP allows.

A **final plan panel** appears (or a tab switches) when `RUN_COMPLETED` arrives, rendering the
`HealthPlan` (diet, workout, budget, rationale, and the "what each agent changed" list).

## 3. Backend protocol (WebSocket)

- Client: `POST /api/plan` with a `UserProfile` → `{ "run_id": "..." }`.
- Client: open `WS /ws/trace/{run_id}`.
- Server: pushes JSON-serialized `TraceEvent`s in `seq` order as they happen. The terminal
  event is `RUN_COMPLETED` whose `payload` contains the full `HealthPlan`.
- Reconnection / replay: `GET /api/plan/{run_id}` returns `{ events: [...], plan: {...} }` so a
  late or reconnecting client can replay the whole run. (Also enables a "replay" button.)

Event ordering is guaranteed by the monotonic `seq`. The UI should buffer and sort by `seq` in
case of out-of-order delivery.

### Minimal event → UI mapping

| TraceEvent.type | UI effect |
|-----------------|-----------|
| `RUN_STARTED` | Reset view, create nodes for all registered agents. |
| `ROUND_STARTED` | Update round indicator. |
| `AGENT_STARTED` | Mark node "running" (pulse). |
| `AGENT_INPUT` | Store input for the inspector. |
| `TOOL_CALLED` | Badge the node with the tool name; log line. |
| `AGENT_OUTPUT` / `AGENT_COMPLETED` | Mark node "done"; store output for inspector. |
| `MESSAGE_SENT` | Animate an edge sender→recipient; log line. |
| `CONFLICT_RAISED` | Mark target node(s) "conflict"; draw a conflict edge; log line. |
| `REVISION_REQUESTED` | Animate a back-edge to the target; increment its round badge. |
| `RUN_COMPLETED` | Mark Resolver "done"; reveal the final plan panel. |
| `ERROR` | Surface a non-blocking error toast + log line. |

## 4. Demo guidance

The most persuasive 90 seconds: pick a profile that *forces* conflicts — e.g. an aggressive
fat-loss goal + a knee injury + a tight budget + a "high protein" preference. Then the trace
visibly shows:

1. Medical Risk removes high-impact movements and caps deficit aggressiveness.
2. Nutrition & Fitness handshake on calories; the deficit gets capped to a safe rate.
3. Budget flags the high-protein groceries as over budget → asks Nutrition to swap to cheaper
   protein.
4. Critic catches the remaining `ENERGY_IMBALANCE` → one refinement round.
5. Resolver reconciles and explains exactly what each agent changed.

Narrate it against the live graph. That single run demonstrates collaboration (40%),
specialization (25%), reasoning (25%), and innovation (10%) in one shot.

## 5. Implementation notes

- Keep the trace UI a **pure function of the event stream** — no business logic in the
  frontend. New agents/events appear automatically as long as the backend emits them.
- Node positions can be a static layout keyed by agent name (deterministic) or React Flow's
  layout. Static is simpler and demo-stable.
- Persist events per run server-side (in-memory dict keyed by `run_id` is fine for the
  hackathon; note where to swap in a store for the "baton" later).
- Color/iconography per agent should match the registry metadata so adding an agent needs no
  UI edit beyond a color entry.
