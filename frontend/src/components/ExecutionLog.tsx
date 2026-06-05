// Execution log: the raw streamed TraceEvents, append-only, color-coded by type. Clicking a row
// selects its agent for the inspector (docs/trace-view.md §2). Auto-scrolls to the newest event.

import { useEffect, useRef } from "react";
import type { TraceEvent, TraceEventType } from "../lib/types";

const TYPE_COLOR: Record<TraceEventType, string> = {
  RUN_STARTED: "text-slate-200 font-semibold",
  ROUND_STARTED: "text-violet-300 font-semibold",
  AGENT_STARTED: "text-cyan-300",
  AGENT_INPUT: "text-slate-500",
  AGENT_OUTPUT: "text-emerald-300",
  TOOL_CALLED: "text-slate-400",
  MESSAGE_SENT: "text-indigo-300",
  CONFLICT_RAISED: "text-rose-300 font-semibold",
  REVISION_REQUESTED: "text-amber-300",
  AGENT_COMPLETED: "text-emerald-400",
  RUN_COMPLETED: "text-indigo-200 font-semibold",
  ERROR: "text-red-300 font-semibold",
};

const ROW_BG: Partial<Record<TraceEventType, string>> = {
  CONFLICT_RAISED: "bg-rose-500/10",
  REVISION_REQUESTED: "bg-amber-500/10",
  ROUND_STARTED: "bg-violet-500/10",
  RUN_COMPLETED: "bg-indigo-500/10",
  ERROR: "bg-red-500/10",
};

function clock(ts: string): string {
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString(undefined, { hour12: false });
}

export function ExecutionLog({
  events,
  selected,
  onSelect,
}: {
  events: TraceEvent[];
  selected: string | null;
  onSelect: (agent: string | null) => void;
}) {
  const endRef = useRef<HTMLLIElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [events.length]);

  return (
    <ol className="max-h-72 overflow-auto font-mono text-xs">
      {events.map((e) => (
        <li
          key={e.seq}
          onClick={() => onSelect(e.agent ?? null)}
          className={`flex cursor-pointer gap-2 rounded px-1 py-0.5 hover:bg-white/5 ${
            ROW_BG[e.type] ?? ""
          } ${e.agent && e.agent === selected ? "ring-1 ring-indigo-400/50" : ""}`}
        >
          <span className="w-8 shrink-0 text-right text-slate-600">{String(e.seq).padStart(3, "0")}</span>
          <span className="w-16 shrink-0 text-slate-500">{clock(e.timestamp)}</span>
          <span className="w-4 shrink-0 text-slate-500">r{e.round}</span>
          <span className={`w-44 shrink-0 ${TYPE_COLOR[e.type]}`}>{e.type}</span>
          <span className="w-24 shrink-0 truncate text-emerald-300/80">{e.agent ?? ""}</span>
          <span className="flex-1 truncate text-slate-400">{e.summary}</span>
        </li>
      ))}
      <li ref={endRef} />
    </ol>
  );
}
