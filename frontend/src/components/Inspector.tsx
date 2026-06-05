// Inspector: the selected agent's input, output, tools, round, and the influence edges that
// touch it (docs/trace-view.md §2). Pure render of the derived view — no fetching here.

import { AGENT_META } from "../lib/agentMeta";
import type { TraceView } from "../lib/traceModel";

function Json({ value }: { value: unknown }) {
  return (
    <pre className="max-h-56 overflow-auto rounded-lg border border-white/10 bg-black/30 p-2 font-mono text-[11px] leading-snug text-slate-300">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

const KIND_COLOR: Record<string, string> = {
  message: "text-indigo-300",
  conflict: "text-rose-300",
  revision: "text-amber-300",
};

const STATUS_COLOR: Record<string, string> = {
  idle: "text-slate-400",
  running: "text-cyan-300",
  done: "text-emerald-300",
  conflict: "text-rose-300",
};

export function Inspector({ view, selected }: { view: TraceView; selected: string | null }) {
  if (!selected) {
    return <p className="text-xs text-slate-500">Click an agent node or a log row to inspect it.</p>;
  }
  const agent = view.agents[selected];
  const meta = AGENT_META[selected];
  if (!agent || !meta) return <p className="text-xs text-slate-500">Unknown agent.</p>;

  const incoming = view.edges.filter((e) => e.target === selected);
  const outgoing = view.edges.filter((e) => e.source === selected);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-lg">{meta.icon}</span>
        <div>
          <div className="text-sm font-semibold text-slate-100">{meta.label}</div>
          <div className="text-[11px] text-slate-400">
            <span className={STATUS_COLOR[agent.status]}>{agent.status}</span> · round {agent.round}
          </div>
        </div>
      </div>

      {agent.lastSummary && (
        <p className="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-xs text-slate-300">
          {agent.lastSummary}
        </p>
      )}

      {agent.tools.length > 0 && (
        <div>
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">Tools used</div>
          <div className="flex flex-wrap gap-1">
            {agent.tools.map((t) => (
              <span key={t} className="rounded bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-slate-300">
                {t}
              </span>
            ))}
          </div>
        </div>
      )}

      {(incoming.length > 0 || outgoing.length > 0) && (
        <div>
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">Influence</div>
          <ul className="space-y-0.5 text-[11px] text-slate-300">
            {incoming.map((e) => (
              <li key={e.id}>
                <span className="text-slate-500">←</span> {AGENT_META[e.source]?.label ?? e.source}{" "}
                <span className={KIND_COLOR[e.kind]}>({e.label})</span>
              </li>
            ))}
            {outgoing.map((e) => (
              <li key={e.id}>
                <span className="text-slate-500">→</span> {AGENT_META[e.target]?.label ?? e.target}{" "}
                <span className={KIND_COLOR[e.kind]}>({e.label})</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">Input</div>
        {agent.input ? <Json value={agent.input} /> : <p className="text-[11px] text-slate-500">—</p>}
      </div>
      <div>
        <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">Output</div>
        {agent.output ? <Json value={agent.output} /> : <p className="text-[11px] text-slate-500">—</p>}
      </div>
    </div>
  );
}
