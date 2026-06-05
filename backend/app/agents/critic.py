"""🔍 Critic Agent — spec: docs/agents/critic-agent.md. Build-plan task 3.5.

The adversary. Reads ALL specialist outputs and raises typed Conflicts (the conflict taxonomy
in docs/orchestration.md §5). Does not fix anything — finds problems and routes them.
Feed it deterministic prechecks (energy balance, macro sums, cost vs budget) so it challenges
facts, not guesses.
"""
from __future__ import annotations

from app.core.base_agent import AgentContext, AgentResult, BaseAgent
from app.core.registry import register
from app.schemas import Critique


@register("critic")
class CriticAgent(BaseAgent):
    tier = "strong"
    tools: list[str] = []
    output_schema = Critique

    async def _run(self, ctx: AgentContext) -> AgentResult:
        # TODO(3.5): run the conflict taxonomy over ctx.state: MEDICAL_VIOLATION,
        # ENERGY_IMBALANCE, BUDGET_OVERRUN, MACRO_INCOHERENCE, RECOVERY_RISK, MISSING_DISCLAIMER.
        # Precompute the numeric checks in code; have the LLM adjudicate gray areas. Each
        # Conflict carries evidence (numbers), severity, target_agents. Empty list + approved=True
        # means proceed to the Resolver.
        raise NotImplementedError("Implement per docs/agents/critic-agent.md")
