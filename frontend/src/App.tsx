// App shell for the Live Agent Trace View. Layout per docs/trace-view.md §2.
// This is a runnable skeleton with the regions and the event-handling outline; fill in the
// graph/inspector/plan rendering in build-plan Phase 6.

import { useCallback, useRef, useState } from "react";
import { AGENT_ORDER } from "./lib/agentMeta";
import { startPlan, subscribeTrace } from "./lib/api";
import type { HealthPlan, TraceEvent, UserProfile } from "./lib/types";

// A demo profile that FORCES conflicts (great for the live demo — see docs/trace-view.md §4).
const DEMO_PROFILE: UserProfile = {
  age: 34, sex: "male", height_cm: 178, weight_kg: 92, activity_level: "light",
  goal: "fat_loss", target_weight_kg: 78, timeframe_weeks: 12,
  medical_conditions: ["knee injury", "hypertension"], medications: [], allergies: ["peanuts"],
  budget_weekly: 1500, currency: "INR", diet_preference: "high protein, vegetarian",
  disliked_foods: ["mushroom"], equipment_access: ["dumbbells"],
  days_per_week: 4, session_minutes: 45, notes: "wants visible results fast",
};

export default function App() {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [plan, setPlan] = useState<HealthPlan | null>(null);
  const [running, setRunning] = useState(false);
  const cleanupRef = useRef<(() => void) | null>(null);

  const onEvent = useCallback((e: TraceEvent) => {
    setEvents((prev) => [...prev, e].sort((a, b) => a.seq - b.seq)); // guarantee ordering
    if (e.type === "RUN_COMPLETED") {
      setPlan((e.payload as { plan?: HealthPlan }).plan ?? (e.payload as unknown as HealthPlan));
      setRunning(false);
      cleanupRef.current?.();
    }
  }, []);

  async function run() {
    setEvents([]); setPlan(null); setRunning(true);
    const { run_id } = await startPlan(DEMO_PROFILE);
    cleanupRef.current = subscribeTrace(run_id, onEvent);
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="flex items-center justify-between border-b bg-white px-6 py-3">
        <h1 className="text-lg font-semibold">Health Plan Optimizer · Agent Trace</h1>
        <button
          onClick={run}
          disabled={running}
          className="rounded bg-indigo-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {running ? "Running…" : "Run demo plan"}
        </button>
      </header>

      <main className="grid grid-cols-3 gap-4 p-6">
        {/* TODO(6.2): Agent graph (React Flow). Nodes from AGENT_ORDER; edges from MESSAGE_SENT
            / REVISION_REQUESTED; status colors from AGENT_STARTED/COMPLETED/CONFLICT_RAISED. */}
        <section className="col-span-2 rounded border bg-white p-4">
          <h2 className="mb-2 font-medium">Agent graph</h2>
          <ul className="flex flex-wrap gap-2 text-sm">
            {AGENT_ORDER.map((name) => (
              <li key={name} className="rounded border px-3 py-1">{name}</li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-slate-500">
            Replace with a React Flow graph — see docs/trace-view.md §2.
          </p>
        </section>

        {/* TODO(6.3): Inspector — selected agent's input/output/tools for the current round. */}
        <aside className="rounded border bg-white p-4">
          <h2 className="mb-2 font-medium">Inspector</h2>
          <p className="text-xs text-slate-500">Click a node or a log row.</p>
        </aside>
      </main>

      {/* TODO(6.4): Execution log — the raw streamed TraceEvents. */}
      <section className="mx-6 mb-6 rounded border bg-white p-4">
        <h2 className="mb-2 font-medium">Execution log</h2>
        <ol className="max-h-64 overflow-auto font-mono text-xs">
          {events.map((e) => (
            <li key={e.seq} className="py-0.5">
              <span className="text-slate-400">{String(e.seq).padStart(3, "0")}</span>{" "}
              <span className="text-indigo-600">{e.type}</span>{" "}
              {e.agent ? <span className="text-emerald-700">{e.agent}</span> : null}{" "}
              <span className="text-slate-600">{e.summary}</span>
            </li>
          ))}
        </ol>
      </section>

      {/* TODO(6.5): Final plan panel — render the HealthPlan incl. agent_contributions. */}
      {plan && (
        <section className="mx-6 mb-10 rounded border-2 border-indigo-200 bg-white p-4">
          <h2 className="mb-2 font-medium">Final Health Plan</h2>
          <p className="text-sm">{plan.summary}</p>
          <p className="mt-2 text-xs text-amber-700">{plan.disclaimers?.join(" ")}</p>
        </section>
      )}
    </div>
  );
}
