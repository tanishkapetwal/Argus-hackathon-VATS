// Live Agent Trace View (build-plan Phase 6/7). Two phases: a conversational intake collects the
// profile, then the multi-agent debate streams in live. The whole debate view is a pure function
// of the backend TraceEvent stream — deriveView() folds it; the panels just render the result.

import { useCallback, useMemo, useRef, useState } from "react";
import { AgentGraph } from "./components/AgentGraph";
import { ChatIntake } from "./components/ChatIntake";
import { ExecutionLog } from "./components/ExecutionLog";
import { FinalPlanPanel } from "./components/FinalPlanPanel";
import { Inspector } from "./components/Inspector";
import { getRun, startPlan, subscribeTrace } from "./lib/api";
import { deriveView } from "./lib/traceModel";
import type { TraceEvent, UserProfile } from "./lib/types";

const STATUS_DOT: Record<string, string> = {
  idle: "bg-slate-500",
  running: "bg-cyan-400 shadow-glow-cyan animate-glow-pulse",
  complete: "bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.7)]",
  error: "bg-rose-500 shadow-glow-rose",
};

export default function App() {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [phase, setPhase] = useState<"intake" | "run">("intake");
  const [replayId, setReplayId] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [, setRunning] = useState(false);
  const cleanupRef = useRef<(() => void) | null>(null);

  const view = useMemo(() => deriveView(events), [events]);

  const onEvent = useCallback((e: TraceEvent) => {
    setEvents((prev) => {
      if (prev.some((x) => x.seq === e.seq)) return prev;
      return [...prev, e].sort((a, b) => a.seq - b.seq);
    });
    if (e.type === "RUN_COMPLETED" || e.type === "ERROR") {
      setRunning(false);
      cleanupRef.current?.();
    }
  }, []);

  const run = useCallback(async (profile: UserProfile) => {
    cleanupRef.current?.();
    setEvents([]);
    setSelected(null);
    setNotice(null);
    setRunning(true);
    setPhase("run");
    try {
      const { run_id } = await startPlan(profile);
      setReplayId(run_id);
      cleanupRef.current = subscribeTrace(run_id, onEvent, () =>
        setNotice("WebSocket error — is the backend running on :8000?"),
      );
    } catch (err) {
      setRunning(false);
      setNotice(`Could not reach the backend: ${(err as Error).message}. Start it on :8000.`);
    }
  }, [onEvent]);

  const replay = useCallback(async () => {
    const id = replayId.trim();
    if (!id) return;
    cleanupRef.current?.();
    setRunning(false);
    setNotice(null);
    setPhase("run");
    try {
      const { events: log } = await getRun(id);
      setEvents([...log].sort((a, b) => a.seq - b.seq));
      setSelected(null);
    } catch (err) {
      setNotice(`Replay failed: ${(err as Error).message}`);
    }
  }, [replayId]);

  const newPlan = () => {
    cleanupRef.current?.();
    setRunning(false);
    setEvents([]);
    setSelected(null);
    setNotice(null);
    setPhase("intake");
  };

  const roundLabel = view.maxRounds != null ? `${view.round}/${view.maxRounds}` : `${view.round}`;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 border-b border-white/10 bg-slate-950/70 px-6 py-3 backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-cyan-500 text-sm shadow-glow">⬡</div>
          <h1 className="neon-text text-lg font-bold tracking-tight">Health Plan Optimizer</h1>
          <span className="hidden text-xs text-slate-500 sm:inline">· multi-agent decision intelligence</span>
          {phase === "run" && (
            <span className="ml-2 flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-xs text-slate-300">
              <span className={`h-2 w-2 rounded-full ${STATUS_DOT[view.runStatus]}`} />
              {view.runStatus}{view.runId ? ` · ${view.runId}` : ""} · round {roundLabel}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {phase === "run" && (
            <button onClick={newPlan} className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 hover:bg-white/10">
              ＋ New plan
            </button>
          )}
          <div className="flex items-center gap-1">
            <input
              value={replayId}
              onChange={(e) => setReplayId(e.target.value)}
              placeholder="run_id"
              className="w-24 rounded-lg border border-white/10 bg-white/5 px-2 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-cyan-400/60 focus:outline-none"
            />
            <button onClick={replay} className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 hover:bg-white/10">
              Replay
            </button>
          </div>
        </div>
      </header>

      {notice && (
        <div className="mx-6 mt-3 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">
          {notice}
        </div>
      )}

      {phase === "intake" ? (
        <main className="flex flex-1 flex-col px-4 pb-4">
          <div className="mx-auto mt-6 max-w-2xl text-center">
            <h2 className="text-2xl font-bold text-slate-100">Let's build your plan</h2>
            <p className="mt-1 text-sm text-slate-400">
              Answer a few questions; then six specialist agents debate, challenge, and reconcile a single plan — live.
            </p>
          </div>
          <div className="mt-2 min-h-0 flex-1">
            <ChatIntake onComplete={run} />
          </div>
        </main>
      ) : (
        <main className="flex-1 space-y-4 p-6">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <section className="glass p-2 lg:col-span-2">
              <h2 className="px-2 py-1 text-sm font-medium text-slate-300">Agent debate graph</h2>
              <div className="h-[560px] w-full overflow-hidden rounded-xl">
                <AgentGraph view={view} selected={selected} onSelect={setSelected} />
              </div>
            </section>
            <aside className="glass p-4">
              <h2 className="mb-2 text-sm font-medium text-slate-300">Inspector</h2>
              <Inspector view={view} selected={selected} />
            </aside>
          </div>

          <section className="glass p-4">
            <h2 className="mb-2 text-sm font-medium text-slate-300">Execution log</h2>
            {events.length === 0 ? (
              <p className="text-xs text-slate-500">Waiting for the first events…</p>
            ) : (
              <ExecutionLog events={events} selected={selected} onSelect={setSelected} />
            )}
          </section>

          {view.finalPlan && (
            <section className="glass border-indigo-400/30 p-4 shadow-glow">
              <h2 className="mb-3 text-base font-semibold text-slate-100">✨ Final Health Plan</h2>
              <FinalPlanPanel plan={view.finalPlan} />
            </section>
          )}
        </main>
      )}
    </div>
  );
}
