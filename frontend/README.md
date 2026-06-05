# Frontend — Live Agent Trace View

React + Vite + TypeScript + Tailwind UI that renders the agent debate live. It is a **pure
function of the `TraceEvent` stream** from the backend — no business logic here (so new agents
appear automatically). Spec: [../docs/trace-view.md](../docs/trace-view.md). Build-plan Phase 6.

## Run
```bash
npm install
npm run dev        # http://localhost:5173 (proxies/calls backend on :8000)
```

## Structure
```
src/
├── main.tsx              ← React entry
├── App.tsx              ← layout shell: profile form · agent graph · inspector · log · plan
├── index.css           ← Tailwind directives
└── lib/
    ├── types.ts        ← TS mirror of backend Pydantic schemas (keep in sync!)
    ├── agentMeta.ts    ← per-agent color/icon/order/layout (add 1 line for a new agent)
    └── api.ts          ← POST /api/plan + WebSocket trace subscription + GET replay
```

## How it works
1. User fills the profile form → `POST /api/plan` → `{ run_id }`.
2. Open `WS /ws/trace/{run_id}`; receive `TraceEvent`s in `seq` order.
3. Reduce events into view state (see the event→UI mapping in
   [../docs/trace-view.md](../docs/trace-view.md) §3):
   - nodes light up on `AGENT_STARTED`/`AGENT_COMPLETED`,
   - edges animate on `MESSAGE_SENT` / `REVISION_REQUESTED`,
   - conflict styling on `CONFLICT_RAISED`,
   - the final plan panel reveals on `RUN_COMPLETED`.
4. `GET /api/plan/{run_id}` powers reconnect/replay.

## Conventions
- Mirror backend schema changes in `types.ts` in the same change (docs-in-step rule).
- Keep components dumb; derive everything from the event log. Adding an agent must not require
  editing the reducer — only an `agentMeta` entry.

> NOTE: standard Vite/Tailwind config files (`vite.config.ts`, `tailwind.config.js`,
> `postcss.config.js`, `tsconfig.json`, `index.html`) are included as minimal scaffolds; adjust
> as needed. If you prefer, regenerate the scaffold with `npm create vite@latest` and drop in
> `src/lib/*` + `App.tsx`.
