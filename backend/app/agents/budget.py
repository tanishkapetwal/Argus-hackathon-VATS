"""💰 Budget Agent — spec: docs/agents/budget-agent.md. Build-plan task 3.4.

Costs the diet + workout, compares to budget, and issues targeted, medically-safe
RevisionRequests to Nutrition/Fitness when over budget.
"""
from __future__ import annotations

from app.core.base_agent import AgentContext, AgentResult, BaseAgent
from app.core.registry import register
from app.schemas import BudgetReport


@register("budget")
class BudgetAgent(BaseAgent):
    tier = "strong"
    tools = ["prices", "usda", "web_search"]
    output_schema = BudgetReport

    async def _run(self, ctx: AgentContext) -> AgentResult:
        # TODO(3.4): price nutrition.weekly_grocery_list + supplements and fitness.equipment_needed
        # via ctx.tools.prices (amortize one-time equipment to weekly). Compute estimated cost +
        # overrun. If over budget, propose constraint-safe cuts (never below
        # constraints.min_protein_g_per_kg) and emit RevisionRequests to the responsible agents.
        raise NotImplementedError("Implement per docs/agents/budget-agent.md")
