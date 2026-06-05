"""⚖️ Resolver Agent — spec: docs/agents/resolver-agent.md. Build-plan task 3.6.

The judge. Reconciles remaining conflicts by the fixed priority (safety > physiology > budget >
preference) and synthesizes the final HealthPlan incl. the per-agent "what changed and why"
narrative. Always produces a plan (lists unresolved trade-offs rather than looping).
"""
from __future__ import annotations

from app.core.base_agent import AgentContext, AgentResult, BaseAgent
from app.core.registry import register
from app.schemas import HealthPlan


@register("resolver")
class ResolverAgent(BaseAgent):
    tier = "strong"
    tools: list[str] = []
    output_schema = HealthPlan

    async def _run(self, ctx: AgentContext) -> AgentResult:
        # TODO(3.6): if constraints.requires_professional -> return a "consult a professional
        # first" plan (do not optimize). Otherwise resolve each open conflict by the priority in
        # docs/orchestration.md §6, assemble the integrated HealthPlan from the latest specialist
        # outputs, fill agent_contributions + resolved_conflicts + open_tradeoffs, attach all
        # required disclaimers. Emit RUN_COMPLETED with the plan in the payload.
        raise NotImplementedError("Implement per docs/agents/resolver-agent.md")
