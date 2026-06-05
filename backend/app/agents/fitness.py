"""🏋️ Fitness Agent — spec: docs/agents/fitness-agent.md. Build-plan task 3.3.

Designs the weekly workout within medical limits + available equipment, estimates weekly
calorie burn, and completes the calorie handshake with Nutrition.
"""
from __future__ import annotations

from app.core.base_agent import AgentContext, AgentResult, BaseAgent
from app.core.registry import register
from app.schemas import FitnessPlan


@register("fitness")
class FitnessAgent(BaseAgent):
    tier = "strong"
    tools = ["web_search"]
    output_schema = FitnessPlan

    async def _run(self, ctx: AgentContext) -> AgentResult:
        # TODO(3.3): pick a split for profile.days_per_week + goal; select exercises that
        # respect constraints.forbidden_movements / max_intensity / requires_warmup and
        # profile.equipment_access. Estimate est_weekly_kcal_burn (MET-based). Complete the
        # calorie handshake with nutrition (adjust volume or message nutrition to adjust intake
        # so intake-burn matches the goal's safe rate). Set equipment_needed for Budget. Honor
        # RevisionRequests routed to "fitness".
        raise NotImplementedError("Implement per docs/agents/fitness-agent.md")
