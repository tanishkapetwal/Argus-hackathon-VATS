"""🥗 Nutrition Agent — spec: docs/agents/nutrition-agent.md. Build-plan task 3.2.

Produces MacroTargets (via the deterministic macros tool — NEVER the LLM) + a constraint- and
budget-aware diet, enriches the grocery list with real USDA nutrient data, and sends the
calorie-handshake message to Fitness.
"""
from __future__ import annotations

import re

from app.core.agent_names import FITNESS, NUTRITION
from app.core.base_agent import AgentContext, AgentResult, BaseAgent
from app.core.registry import register
from app.schemas import AgentMessage, MacroTargets, NutritionPlan, TraceEventType

_SYSTEM = (
    "You are a registered-dietitian-style planner. You receive EXACT macro targets from a "
    "calculator — never recompute or override them. Build a realistic, preference-aware, "
    "constraint-compliant diet that hits those macros using real foods, and aggregate a weekly "
    "grocery list with quantities for the budget agent. Defer medical judgments to the given "
    "constraints (don't re-litigate them) and defer cost judgments to the budget agent (but "
    "respond to its revision requests). If a constraint makes the target impossible, say so in "
    "constraint_notes — do not silently violate it."
)


def _to_grams(quantity: str) -> float:
    """Best-effort grams from a quantity string ('150 g' -> 150, '1.05 kg' -> 1050)."""
    m = re.search(r"([\d.]+)", quantity or "")
    if not m:
        return 100.0
    value = float(m.group(1))
    q = quantity.lower()
    if "kg" in q:
        return value * 1000.0
    if re.search(r"\bg\b|gram", q):
        return value
    return 100.0  # cups/pieces/unknown units → assume a 100 g reference serving


def _user_prompt(ctx: AgentContext, macros: MacroTargets) -> str:
    p = ctx.profile
    c = ctx.state.constraints
    parts = [
        "Design a one-day representative diet that hits these EXACT targets (do not change them):",
        f"- target_kcal: {macros.target_kcal}, protein_g: {macros.protein_g}, "
        f"carbs_g: {macros.carbs_g}, fat_g: {macros.fat_g}, fiber_g: {macros.fiber_g}",
        f"- diet_preference: {p.diet_preference or 'no preference'}",
        f"- disliked_foods: {p.disliked_foods or 'none'}",
    ]
    if c is not None:
        parts += [
            f"- excluded_foods (NEVER include): {c.excluded_foods or 'none'}",
            f"- max_added_sugar_g: {c.max_added_sugar_g}, max_sodium_mg: {c.max_sodium_mg}, "
            f"max_saturated_fat_g: {c.max_saturated_fat_g}",
            f"- min_protein_g_per_kg: {c.min_protein_g_per_kg}, "
            f"required_nutrients: {c.required_nutrients or 'none'}",
        ]
    if ctx.state.fitness is not None:
        parts.append(
            f"- fitness estimates ~{ctx.state.fitness.est_weekly_kcal_burn} kcal/week of training "
            "burn; keep intake appropriate for the goal's safe rate."
        )
    revisions = [r for r in ctx.state.revision_requests if r.target_agent == NUTRITION]
    if revisions:
        parts.append("Apply these revision requests:")
        parts += [f"  - {r.constraint} (from {r.raised_by}: {r.reason})" for r in revisions]
    parts.append(
        "Return daily_meals (with per-item kcal/macros), an aggregated weekly_grocery_list with "
        "quantities, supplements if needed, satisfies_constraints, and constraint_notes."
    )
    return "\n".join(parts)


@register(NUTRITION)
class NutritionAgent(BaseAgent):
    tier = "strong"
    tools = ["macros_calc", "usda"]
    output_schema = NutritionPlan

    async def _run(self, ctx: AgentContext) -> AgentResult:
        p = ctx.profile

        # 1) Deterministic macro targets — the LLM never computes these.
        macros: MacroTargets = ctx.tools.macros_calc(
            sex=p.sex, weight_kg=p.weight_kg, height_cm=p.height_cm, age=p.age,
            activity_level=p.activity_level, goal=p.goal,
            timeframe_weeks=p.timeframe_weeks, target_weight_kg=p.target_weight_kg,
        )
        await ctx.emit(
            TraceEventType.TOOL_CALLED, agent=self.name, round=ctx.round,
            summary=f"macros_calc → {macros.target_kcal:.0f} kcal "
                    f"(P{macros.protein_g:.0f}/C{macros.carbs_g:.0f}/F{macros.fat_g:.0f})",
            payload={"tool": "macros_calc", "result": macros.model_dump(mode="json")},
        )

        # 2) LLM designs the diet against those exact numbers + constraints.
        resp = await ctx.llm.complete(
            [{"role": "system", "content": _SYSTEM},
             {"role": "user", "content": _user_prompt(ctx, macros)}],
            tier=self.tier, response_model=NutritionPlan, max_tokens=4096,
        )
        plan: NutritionPlan | None = resp.parsed
        if plan is None:
            raise RuntimeError("Nutrition Agent received no structured plan from the LLM")
        plan.macros = macros  # deterministic override — numbers are never hallucinated

        # 3) Enrich the grocery list with real USDA nutrient data where available.
        enriched = 0
        for item in plan.weekly_grocery_list:
            food = await ctx.tools.usda(item.name, _to_grams(item.quantity))
            if food.kcal > 0:  # real data (offline/zeroed fallback leaves the LLM's values)
                item.kcal, item.protein_g = food.kcal, food.protein_g
                item.carbs_g, item.fat_g, item.fdc_id = food.carbs_g, food.fat_g, food.fdc_id
                enriched += 1
        if plan.weekly_grocery_list:
            await ctx.emit(
                TraceEventType.TOOL_CALLED, agent=self.name, round=ctx.round,
                summary=f"usda enriched {enriched}/{len(plan.weekly_grocery_list)} grocery items",
                payload={"tool": "usda", "enriched": enriched,
                         "total": len(plan.weekly_grocery_list)},
            )

        # 4) Deterministic constraint self-check (excluded foods in meals).
        self._check_excluded_foods(ctx, plan)

        # 5) Calorie handshake → Fitness (influence edge).
        handshake = AgentMessage(
            sender=NUTRITION, recipient=FITNESS, intent="calorie_handshake",
            payload={"target_kcal": macros.target_kcal, "tdee_kcal": macros.tdee_kcal,
                     "goal": p.goal.value},
            text=f"Target {macros.target_kcal:.0f} kcal/day for {p.goal.value}; "
                 "size training so intake−burn stays at a safe rate.",
        )
        return AgentResult(output=plan, messages=[handshake])

    @staticmethod
    def _check_excluded_foods(ctx: AgentContext, plan: NutritionPlan) -> None:
        c = ctx.state.constraints
        if c is None or not c.excluded_foods:
            return
        excluded = [e.lower() for e in c.excluded_foods]
        offenders = sorted({
            item.name for meal in plan.daily_meals for item in meal.items
            if any(e in item.name.lower() for e in excluded)
        })
        if offenders:
            plan.satisfies_constraints = False
            plan.constraint_notes.append(
                f"WARNING: meals include excluded foods {offenders} — Critic should flag this."
            )

    def _output_summary(self, output: NutritionPlan) -> str:
        m = output.macros
        return (f"nutrition: {m.target_kcal:.0f} kcal diet, {len(output.daily_meals)} meals, "
                f"{len(output.weekly_grocery_list)} grocery items")
