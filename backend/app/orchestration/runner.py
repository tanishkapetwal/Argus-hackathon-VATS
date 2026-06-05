"""run_plan() — drives the graph for one request and emits trace events throughout.

Spec: docs/architecture.md §4, docs/orchestration.md §7. Build-plan task 4.3.
"""
from __future__ import annotations

from app.core.trace import TraceEmitter
from app.schemas import HealthPlan, UserProfile


async def run_plan(profile: UserProfile, run_id: str, emitter: TraceEmitter) -> HealthPlan:
    """Initialize PlanState, run the compiled graph, and return the final HealthPlan.

    TODO(4.3):
      - emit RUN_STARTED; build PlanState(run_id, profile).
      - import app.agents (registers all agents), build_graph(), and invoke it with the state.
      - pass an AgentContext into each node carrying profile/state/llm/tools/emit/round, so
        every agent emits its I/O, messages, tool calls, and conflicts.
      - on completion emit RUN_COMPLETED with the HealthPlan payload; return it.
      - the loop is bounded by Settings.max_refinement_rounds; the Resolver always finalizes.
    """
    raise NotImplementedError("Implement per docs/build-plan.md task 4.3")
