// Per-agent presentation metadata for the trace graph.
// Adding a new agent? Add ONE entry here (docs/contributing.md §A step 6) — the reducer and
// the rest of the UI derive everything from the event stream + this map.

export interface AgentMeta {
  /** registry name — MUST match the backend agent name + the strings in messages/conflicts */
  name: string;
  label: string;
  icon: string;         // emoji or icon key
  color: string;        // tailwind color token, e.g. "rose"
  /** column/row hint for the static graph layout (docs/trace-view.md §5) */
  order: number;
}

export const AGENT_META: Record<string, AgentMeta> = {
  medical_risk: { name: "medical_risk", label: "Medical Risk", icon: "🩺", color: "rose",    order: 0 },
  nutrition:    { name: "nutrition",    label: "Nutrition",    icon: "🥗", color: "emerald", order: 1 },
  fitness:      { name: "fitness",      label: "Fitness",      icon: "🏋️", color: "sky",     order: 2 },
  budget:       { name: "budget",       label: "Budget",       icon: "💰", color: "amber",   order: 3 },
  critic:       { name: "critic",       label: "Critic",       icon: "🔍", color: "violet",  order: 4 },
  resolver:     { name: "resolver",     label: "Resolver",     icon: "⚖️", color: "indigo",  order: 5 },
};

export const AGENT_ORDER = Object.values(AGENT_META)
  .sort((a, b) => a.order - b.order)
  .map((m) => m.name);
