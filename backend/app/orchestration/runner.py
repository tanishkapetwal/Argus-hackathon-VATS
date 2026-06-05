"""run_plan() — drives the graph for one request and emits trace events throughout.

Spec: docs/architecture.md §4, docs/orchestration.md §7. Build-plan task 4.3.
"""
from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.core.trace import TraceEmitter
from app.schemas import HealthPlan, PlanState, TraceEventType, UserProfile

# LangGraph can run more super-steps than the default 25 once the bounded refinement loop kicks
# in (≈5 nodes × up to MAX_REFINEMENT_ROUNDS, plus the first pass and the resolver).
_RECURSION_LIMIT = 60


def _extract(final: Any, key: str) -> Any:
    """Read a field from the graph's final state, whether it's a PlanState or a plain dict."""
    if isinstance(final, dict):
        return final.get(key)
    return getattr(final, key, None)


async def run_plan(profile: UserProfile, run_id: str, emitter: TraceEmitter) -> HealthPlan:
    """Initialize PlanState, run the compiled graph, and return the final HealthPlan.

    Emits RUN_STARTED up front and RUN_COMPLETED (with the HealthPlan in the payload) at the end.
    The refinement loop is bounded by Settings.max_refinement_rounds; the Resolver always
    finalizes, so a HealthPlan is guaranteed even with unresolved trade-offs.
    """
    await emitter.emit(
        TraceEventType.RUN_STARTED, round=0,
        summary=f"Run {run_id} started for a {profile.goal.value} plan",
        payload={"run_id": run_id, "profile": profile.model_dump(mode="json"),
                 "max_refinement_rounds": get_settings().max_refinement_rounds},
    )

    # Importing the agents package registers all six agents in the registry (graph reads it).
    import app.agents  # noqa: F401
    from app.orchestration.graph import build_graph

    state = PlanState(run_id=run_id, profile=profile)
    graph = build_graph(emitter)
    final = await graph.ainvoke(state, config={"recursion_limit": _RECURSION_LIMIT})

    plan = _extract(final, "final_plan")
    if plan is None:
        raise RuntimeError("Graph finished without a final_plan — the Resolver must always set it")
    if not isinstance(plan, HealthPlan):
        plan = HealthPlan.model_validate(plan)

    final_round = _extract(final, "round") or 0
    await emitter.emit(
        TraceEventType.RUN_COMPLETED, round=final_round,
        summary=f"Run {run_id} complete after {final_round} refinement round(s)",
        payload={"plan": plan.model_dump(mode="json")},
    )
    return plan
