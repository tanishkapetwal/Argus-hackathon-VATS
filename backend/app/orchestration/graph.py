"""Builds the LangGraph: nodes = agents, shared PlanState, conditional refinement edge.

Spec: docs/orchestration.md (the graph diagram + conflict routing). Build-plan task 4.2.

Flow:
  medical_risk → nutrition → fitness → budget → critic
                 └ (the nutrition→fitness calorie handshake is explicit + sequential, which also
                    avoids LangGraph concurrent-write conflicts on the shared state)
  critic ──[open_conflicts and round < MAX]?── prepare_refinement → ONLY the targeted specialist
         └─ else ──────────────────────────── resolver → END

Each node runs exactly one agent via `agent.run(ctx)` (BaseAgent emits the trace events) and
writes back ONLY that agent's own slice of PlanState; messages/revisions are appended, the
critic replaces `open_conflicts` with its current findings, the resolver sets `final_plan`. The
loop is bounded by Settings.max_refinement_rounds, so it always terminates and reaches the
Resolver, which always finalizes a HealthPlan.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.core.agent_names import BUDGET, CRITIC, FITNESS, MEDICAL_RISK, NUTRITION, RESOLVER
from app.core.base_agent import AgentContext, AgentResult
from app.core.config import get_settings
from app.core.registry import get_agent
from app.core.trace import TraceEmitter
from app.llm.factory import get_provider
from app.schemas import PlanState, TraceEventType
from app.tools.registry import build_toolbelt

# Sequential specialist chain; also the order we re-enter the loop from (earliest target first).
_PIPELINE = [MEDICAL_RISK, NUTRITION, FITNESS, BUDGET, CRITIC]
# Agents the refinement loop may re-run (medical_risk is the gate; resolver is terminal).
_REFINE_TARGETS = [NUTRITION, FITNESS, BUDGET]


def _slice_update(name: str, state: PlanState, result: AgentResult) -> dict:
    """Map an AgentResult back onto ONLY that agent's slice of PlanState (+ append logs)."""
    update: dict = {
        "messages": state.messages + result.messages,
        "revision_requests": state.revision_requests + result.revisions,
    }
    if name == MEDICAL_RISK:
        update["constraints"] = result.output
    elif name == NUTRITION:
        update["nutrition"] = result.output
    elif name == FITNESS:
        update["fitness"] = result.output
    elif name == BUDGET:
        update["budget"] = result.output
    elif name == CRITIC:
        # The critic is the source of truth for what is *currently* open → replace, don't append.
        update["open_conflicts"] = result.conflicts
    elif name == RESOLVER:
        update["final_plan"] = result.output
    return update


def _refine_targets(state: PlanState) -> set[str]:
    return {a for c in state.open_conflicts for a in c.target_agents} & set(_REFINE_TARGETS)


def build_graph(emitter: TraceEmitter):  # -> CompiledStateGraph
    """Construct and compile the LangGraph for one run (closes over its emitter + provider)."""
    settings = get_settings()
    provider = get_provider(settings)

    def _make_node(name: str):
        async def _node(state: PlanState) -> dict:
            agent = get_agent(name)
            ctx = AgentContext(
                profile=state.profile,
                state=state,
                llm=provider,
                tools=build_toolbelt(agent.tools),
                emit=emitter.emit,
                round=state.round,
            )
            result = await agent.run(ctx)
            return _slice_update(name, state, result)
        return _node

    async def _prepare_refinement(state: PlanState) -> dict:
        new_round = state.round + 1
        targets = sorted(_refine_targets(state))
        await emitter.emit(
            TraceEventType.ROUND_STARTED, round=new_round,
            summary=f"Refinement round {new_round}: re-running {', '.join(targets)}",
            payload={"round": new_round, "targets": targets,
                     "conflicts": [c.type.value for c in state.open_conflicts]},
        )
        return {"round": new_round}

    def _route_after_critic(state: PlanState) -> str:
        if state.open_conflicts and _refine_targets(state) \
                and state.round < settings.max_refinement_rounds:
            return "refine"
        return "finalize"

    def _pick_entry(state: PlanState) -> str:
        targets = _refine_targets(state)
        for name in _REFINE_TARGETS:           # earliest targeted specialist in pipeline order
            if name in targets:
                return name
        return BUDGET                          # defensive; guarded by _route_after_critic

    graph = StateGraph(PlanState)
    for name in _PIPELINE:
        graph.add_node(name, _make_node(name))
    graph.add_node(RESOLVER, _make_node(RESOLVER))
    graph.add_node("prepare_refinement", _prepare_refinement)

    graph.add_edge(START, MEDICAL_RISK)
    graph.add_edge(MEDICAL_RISK, NUTRITION)
    graph.add_edge(NUTRITION, FITNESS)        # calorie handshake happens here (sequential)
    graph.add_edge(FITNESS, BUDGET)
    graph.add_edge(BUDGET, CRITIC)
    graph.add_conditional_edges(
        CRITIC, _route_after_critic,
        {"refine": "prepare_refinement", "finalize": RESOLVER},
    )
    graph.add_conditional_edges(
        "prepare_refinement", _pick_entry,
        {NUTRITION: NUTRITION, FITNESS: FITNESS, BUDGET: BUDGET},
    )
    graph.add_edge(RESOLVER, END)
    return graph.compile()
