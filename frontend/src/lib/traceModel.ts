// The trace view is a PURE FUNCTION of the TraceEvent stream (docs/trace-view.md §5).
// `deriveView` folds the ordered events into everything the UI renders: per-agent status/IO,
// the influence edges (messages/conflicts/revisions), the round counter, and the final plan.
// No component holds business logic — they all read the object this returns.

import { AGENT_ORDER } from "./agentMeta";
import type { HealthPlan, TraceEvent } from "./types";

export type AgentStatus = "idle" | "running" | "done" | "conflict";

export interface AgentView {
  name: string;
  status: AgentStatus;
  round: number;
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  tools: string[];
  lastSummary: string;
}

export type EdgeKind = "message" | "conflict" | "revision";

export interface EdgeView {
  id: string;
  source: string;
  target: string;
  kind: EdgeKind;
  label: string;
  intent?: string;
  round: number;
  seq: number;
  active: boolean; // the most recent influence edge — animated while the run is live
}

export type RunStatus = "idle" | "running" | "complete" | "error";

export interface TraceView {
  runId?: string;
  runStatus: RunStatus;
  round: number;
  maxRounds?: number;
  agents: Record<string, AgentView>;
  agentOrder: string[];
  edges: EdgeView[];
  finalPlan: HealthPlan | null;
}

function freshAgents(): Record<string, AgentView> {
  const agents: Record<string, AgentView> = {};
  for (const name of AGENT_ORDER) {
    agents[name] = { name, status: "idle", round: 0, tools: [], lastSummary: "" };
  }
  return agents;
}

/** Fold the (seq-ordered) event stream into the renderable view. Safe to call on every event. */
export function deriveView(events: TraceEvent[]): TraceView {
  let agents = freshAgents();
  const edges = new Map<string, EdgeView>();
  let runId: string | undefined;
  let runStatus: RunStatus = "idle";
  let round = 0;
  let maxRounds: number | undefined;
  let finalPlan: HealthPlan | null = null;
  let activeEdgeId: string | undefined;

  const at = (name?: string | null): AgentView | undefined =>
    name && agents[name] ? agents[name] : undefined;

  const upsertEdge = (e: EdgeView) => {
    edges.set(e.id, e);
    activeEdgeId = e.id;
  };

  for (const ev of events) {
    round = Math.max(round, ev.round ?? 0);
    const a = at(ev.agent);
    const p = (ev.payload ?? {}) as Record<string, unknown>;

    switch (ev.type) {
      case "RUN_STARTED":
        runId = ev.run_id;
        runStatus = "running";
        agents = freshAgents(); // reset (also handles replay over a prior run)
        finalPlan = null;
        activeEdgeId = undefined;
        edges.clear();
        if (typeof p.max_refinement_rounds === "number") maxRounds = p.max_refinement_rounds;
        break;

      case "AGENT_STARTED":
        if (a) {
          a.status = "running";
          a.round = ev.round;
        }
        break;

      case "AGENT_INPUT":
        if (a) a.input = p;
        break;

      case "TOOL_CALLED": {
        const tool = typeof p.tool === "string" ? p.tool : undefined;
        if (a && tool && !a.tools.includes(tool)) a.tools.push(tool);
        break;
      }

      case "AGENT_OUTPUT":
        if (a) {
          a.output = p;
          a.lastSummary = ev.summary;
          if (a.status !== "conflict") a.status = "done";
        }
        break;

      case "AGENT_COMPLETED":
        if (a && a.status === "running") a.status = "done";
        break;

      case "MESSAGE_SENT": {
        const source = (p.sender as string) ?? ev.agent ?? "";
        const target = (p.recipient as string) ?? "";
        const intent = (p.intent as string) ?? "message";
        if (source && target) {
          upsertEdge({
            id: `message:${source}->${target}`,
            source, target, kind: "message", intent, label: intent,
            round: ev.round, seq: ev.seq, active: false,
          });
        }
        break;
      }

      case "CONFLICT_RAISED": {
        const source = ev.agent ?? "critic";
        const targets = (p.target_agents as string[]) ?? [];
        const label = (p.type as string) ?? "conflict";
        for (const target of targets) {
          const ta = at(target);
          if (ta) ta.status = "conflict";
          upsertEdge({
            id: `conflict:${source}->${target}`,
            source, target, kind: "conflict", label,
            round: ev.round, seq: ev.seq, active: false,
          });
        }
        break;
      }

      case "REVISION_REQUESTED": {
        const source = (p.raised_by as string) ?? ev.agent ?? "";
        const target = (p.target_agent as string) ?? "";
        if (source && target) {
          upsertEdge({
            id: `revision:${source}->${target}`,
            source, target, kind: "revision", label: "revision",
            round: ev.round, seq: ev.seq, active: false,
          });
        }
        break;
      }

      case "RUN_COMPLETED": {
        runStatus = "complete";
        const plan = (p.plan ?? p) as HealthPlan;
        finalPlan = plan ?? null;
        const r = at("resolver");
        if (r) r.status = "done";
        activeEdgeId = undefined; // stop animating once the debate is over
        break;
      }

      case "ERROR":
        runStatus = "error";
        break;
    }
  }

  const edgeList = [...edges.values()].map((e) => ({
    ...e,
    active: runStatus === "running" && e.id === activeEdgeId,
  }));

  return {
    runId, runStatus, round, maxRounds, agents,
    agentOrder: AGENT_ORDER, edges: edgeList, finalPlan,
  };
}
