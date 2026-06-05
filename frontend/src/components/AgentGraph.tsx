// Agent graph (React Flow). Nodes = agents in a static, demo-stable layout (docs/trace-view.md
// §5). A faint structural backbone anchors the pipeline; the influence edges (messages /
// conflicts / revisions) from the event stream are overlaid and animated when active.

import { useMemo } from "react";
import ReactFlow, {
  Background, Controls, MarkerType,
  type Edge, type Node,
} from "reactflow";
import "reactflow/dist/style.css";

import { AGENT_META } from "../lib/agentMeta";
import type { EdgeView, TraceView } from "../lib/traceModel";
import { AgentNode, type AgentNodeData } from "./AgentNode";

const nodeTypes = { agent: AgentNode };

// Static positions keyed by agent name: gate on top, the nutrition⇄fitness pair side-by-side,
// then budget → critic → resolver down the spine.
const POSITIONS: Record<string, { x: number; y: number }> = {
  medical_risk: { x: 250, y: 0 },
  nutrition: { x: 70, y: 130 },
  fitness: { x: 430, y: 130 },
  budget: { x: 250, y: 270 },
  critic: { x: 250, y: 400 },
  resolver: { x: 250, y: 530 },
};

// The pipeline backbone (constant, faint). Influence edges from the stream take precedence.
const STRUCTURAL: Array<[string, string]> = [
  ["medical_risk", "nutrition"],
  ["medical_risk", "fitness"],
  ["nutrition", "budget"],
  ["fitness", "budget"],
  ["budget", "critic"],
  ["critic", "resolver"],
];

const EDGE_COLOR: Record<EdgeView["kind"], string> = {
  message: "#818cf8", // indigo-400
  conflict: "#fb7185", // rose-400
  revision: "#fbbf24", // amber-400
};

function influenceEdge(e: EdgeView): Edge {
  const color = EDGE_COLOR[e.kind];
  const dashed = e.kind !== "message";
  return {
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.active ? `${e.label} ◂` : e.label,
    animated: e.active,
    style: {
      stroke: color,
      strokeWidth: e.active ? 3 : 1.6,
      strokeDasharray: dashed ? "6 3" : undefined,
      filter: e.active ? `drop-shadow(0 0 6px ${color})` : undefined,
      opacity: e.active ? 1 : 0.75,
    },
    labelStyle: { fill: color, fontSize: 10, fontWeight: 600 },
    labelBgStyle: { fill: "#0b1020", fillOpacity: 0.9 },
    labelBgPadding: [4, 2],
    labelBgBorderRadius: 4,
    markerEnd: { type: MarkerType.ArrowClosed, color, width: 16, height: 16 },
    zIndex: e.active ? 5 : 2,
  };
}

export function AgentGraph({
  view,
  selected,
  onSelect,
}: {
  view: TraceView;
  selected: string | null;
  onSelect: (agent: string) => void;
}) {
  const nodes: Node<AgentNodeData>[] = useMemo(
    () =>
      view.agentOrder.map((name) => ({
        id: name,
        type: "agent",
        position: POSITIONS[name] ?? { x: 0, y: 0 },
        draggable: false,
        data: { view: view.agents[name], meta: AGENT_META[name], selected: selected === name },
      })),
    [view.agents, view.agentOrder, selected],
  );

  const edges: Edge[] = useMemo(() => {
    const influence = view.edges.map(influenceEdge);
    const covered = new Set(view.edges.map((e) => `${e.source}->${e.target}`));
    const backbone: Edge[] = STRUCTURAL.filter(
      ([s, t]) => !covered.has(`${s}->${t}`),
    ).map(([s, t]) => ({
      id: `struct:${s}->${t}`,
      source: s,
      target: t,
      style: { stroke: "rgba(148,163,184,0.28)", strokeWidth: 1.4 },
      markerEnd: { type: MarkerType.ArrowClosed, color: "rgba(148,163,184,0.4)", width: 13, height: 13 },
      zIndex: 0,
    }));
    return [...backbone, ...influence];
  }, [view.edges]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodeClick={(_, node) => onSelect(node.id)}
      fitView
      fitViewOptions={{ padding: 0.2 }}
      proOptions={{ hideAttribution: true }}
      nodesConnectable={false}
      nodesDraggable={false}
      minZoom={0.4}
    >
      <Background gap={18} size={1} color="rgba(148,163,184,0.12)" />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}
