// Backend client: start a run, subscribe to the live trace, and replay a finished run.
// Spec: docs/trace-view.md §3. Build-plan task 6.1.

import type { TraceEvent, UserProfile, HealthPlan } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");

/** POST /api/plan — kick off a run, get the run_id back. */
export async function startPlan(profile: UserProfile): Promise<{ run_id: string }> {
  const res = await fetch(`${API_BASE}/api/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });
  if (!res.ok) throw new Error(`startPlan failed: ${res.status}`);
  return res.json();
}

/**
 * Subscribe to WS /ws/trace/{run_id}. Calls `onEvent` for every TraceEvent (ordered by `seq`),
 * and returns a cleanup function. The caller stops when it sees a RUN_COMPLETED event.
 */
export function subscribeTrace(
  runId: string,
  onEvent: (e: TraceEvent) => void,
  onError?: (err: Event) => void,
): () => void {
  const ws = new WebSocket(`${WS_BASE}/ws/trace/${runId}`);
  ws.onmessage = (msg) => {
    try {
      onEvent(JSON.parse(msg.data) as TraceEvent);
    } catch {
      /* ignore malformed frame */
    }
  };
  if (onError) ws.onerror = onError;
  return () => ws.close();
}

/** GET /api/plan/{run_id} — full event log + final plan, for reconnect/replay. */
export async function getRun(
  runId: string,
): Promise<{ events: TraceEvent[]; plan: HealthPlan | null }> {
  const res = await fetch(`${API_BASE}/api/plan/${runId}`);
  if (!res.ok) throw new Error(`getRun failed: ${res.status}`);
  return res.json();
}
