// Custom React Flow node for one agent (dark / neon). Status, current round, and tools all come
// from the AgentView the reducer produced (docs/trace-view.md §2 mapping).

import { Handle, Position, type NodeProps } from "reactflow";
import type { AgentMeta } from "../lib/agentMeta";
import type { AgentStatus, AgentView } from "../lib/traceModel";

export interface AgentNodeData {
  view: AgentView;
  meta: AgentMeta;
  selected: boolean;
}

const STATUS_STYLE: Record<AgentStatus, { ring: string; badge: string; label: string }> = {
  idle: {
    ring: "border-white/10",
    badge: "bg-white/5 text-slate-400", label: "idle",
  },
  running: {
    ring: "border-cyan-400/60 shadow-glow-cyan animate-glow-pulse",
    badge: "bg-cyan-400/15 text-cyan-300", label: "running",
  },
  done: {
    ring: "border-emerald-400/50 shadow-[0_0_18px_-6px_rgba(16,185,129,0.6)]",
    badge: "bg-emerald-400/15 text-emerald-300", label: "done",
  },
  conflict: {
    ring: "border-rose-500/70 shadow-glow-rose animate-glow-pulse",
    badge: "bg-rose-500/15 text-rose-300", label: "conflict",
  },
};

const ACCENT: Record<string, string> = {
  rose: "bg-rose-400 shadow-[0_0_10px_2px_rgba(251,113,133,0.7)]",
  emerald: "bg-emerald-400 shadow-[0_0_10px_2px_rgba(52,211,153,0.7)]",
  sky: "bg-sky-400 shadow-[0_0_10px_2px_rgba(56,189,248,0.7)]",
  amber: "bg-amber-400 shadow-[0_0_10px_2px_rgba(251,191,36,0.7)]",
  violet: "bg-violet-400 shadow-[0_0_10px_2px_rgba(167,139,250,0.7)]",
  indigo: "bg-indigo-400 shadow-[0_0_10px_2px_rgba(129,140,248,0.7)]",
};

export function AgentNode({ data }: NodeProps<AgentNodeData>) {
  const { view, meta, selected } = data;
  const s = STATUS_STYLE[view.status];
  return (
    <div
      className={`w-44 rounded-xl border bg-slate-900/70 px-3 py-2.5 backdrop-blur-md transition-all ${s.ring} ${
        selected ? "outline outline-2 outline-offset-2 outline-indigo-400/80" : ""
      }`}
    >
      <Handle type="target" position={Position.Top} className="!h-1.5 !w-1.5 !border-0 !bg-slate-500" />
      <div className="flex items-center gap-2">
        <span className={`h-2 w-2 shrink-0 rounded-full ${ACCENT[meta.color] ?? "bg-slate-400"}`} />
        <span className="text-base leading-none">{meta.icon}</span>
        <span className="truncate text-sm font-semibold text-slate-100">{meta.label}</span>
      </div>
      <div className="mt-2 flex items-center justify-between">
        <span className={`rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${s.badge}`}>
          {s.label}
        </span>
        <span className="font-mono text-[10px] text-slate-500">r{view.round}</span>
      </div>
      {view.tools.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {view.tools.map((t) => (
            <span key={t} className="rounded bg-white/5 px-1 py-0.5 font-mono text-[9px] text-slate-400">
              {t}
            </span>
          ))}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="!h-1.5 !w-1.5 !border-0 !bg-slate-500" />
    </div>
  );
}
