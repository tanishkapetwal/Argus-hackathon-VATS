"""💰 Budget Agent — spec: docs/agents/budget-agent.md. Build-plan task 3.4.

Costs the diet + workout, compares to budget, and issues targeted, medically-safe
RevisionRequests to Nutrition/Fitness when over budget.

DETERMINISTIC by design (no LLM — see tests/agent_helpers.NoLLM): pricing comes from the
`prices` tool and the cost/overrun math is exact, so the numbers it challenges are facts, not
guesses. Cut suggestions are rule-based and always respect the medical floor
(`min_protein_g_per_kg`) — budget never overrides safety (docs/orchestration.md §6).
"""
from __future__ import annotations

import re

from app.core.agent_names import BUDGET, FITNESS, NUTRITION
from app.core.base_agent import AgentContext, AgentResult, BaseAgent
from app.core.registry import register
from app.schemas import BudgetReport, CostLine, RevisionRequest, TraceEventType

# Amortization horizons: one-time equipment over a year; recurring memberships per ~4.33 wk/mo.
_WEEKS_PER_YEAR = 52.0
_WEEKS_PER_MONTH = 4.33
# A nominal weekly quantity for supplements given as bare strings (≈250 g/week of powder).
_SUPPLEMENT_WEEKLY_QTY = 0.25


def _price_qty(quantity: str) -> float:
    """Map a grocery quantity string to the numeric quantity the price table expects.

    Seeded prices are per-kg (groceries/supplements), per-litre (milk), or per-unit (eggs), so
    we normalise grams→kg / ml→litre and otherwise pass the count through ('12 eggs' → 12).
    """
    m = re.search(r"([\d.]+)", quantity or "")
    value = float(m.group(1)) if m else 1.0
    q = (quantity or "").lower()
    if "kg" in q:
        return value
    if re.search(r"\bg\b|gram", q):
        return value / 1000.0
    if "ml" in q:
        return value / 1000.0
    if re.search(r"\bl\b|litre|liter", q):
        return value
    return value  # count (eggs/pieces) or unknown unit → use the number as-is


@register(BUDGET)
class BudgetAgent(BaseAgent):
    tier = "strong"
    tools = ["prices", "usda", "web_search"]
    output_schema = BudgetReport

    async def _run(self, ctx: AgentContext) -> AgentResult:
        p = ctx.profile
        breakdown: list[CostLine] = []
        notes: list[str] = []

        grocery_cost = await self._price_groceries(ctx, breakdown, notes)
        supplement_cost = await self._price_supplements(ctx, breakdown)
        fitness_cost = await self._price_equipment(ctx, breakdown, notes)

        estimated = round(grocery_cost + supplement_cost + fitness_cost, 2)
        overrun = round(max(0.0, estimated - p.budget_weekly), 2)
        within = estimated <= p.budget_weekly

        await ctx.emit(
            TraceEventType.TOOL_CALLED, agent=self.name, round=ctx.round,
            summary=f"prices: costed {len(breakdown)} item(s) → {p.currency} {estimated:.0f}/week "
                    f"(budget {p.currency} {p.budget_weekly:.0f})",
            payload={"tool": "prices", "estimated_weekly_cost": estimated,
                     "n_lines": len(breakdown)},
        )

        suggested_cuts, revisions = self._propose_cuts(
            ctx, overrun, grocery_cost + supplement_cost, fitness_cost
        )

        report = BudgetReport(
            currency=p.currency,
            weekly_budget=p.budget_weekly,
            estimated_weekly_cost=estimated,
            breakdown=breakdown,
            within_budget=within,
            overrun=overrun,
            suggested_cuts=suggested_cuts,
            revision_requests=revisions,
            notes=notes,
        )
        return AgentResult(output=report, revisions=revisions)

    # ---- pricing helpers ----------------------------------------------------
    async def _price_groceries(
        self, ctx: AgentContext, breakdown: list[CostLine], notes: list[str]
    ) -> float:
        n = ctx.state.nutrition
        if n is None:
            return 0.0
        total = 0.0
        for item in n.weekly_grocery_list:
            qty = _price_qty(item.quantity)
            cost, source = await ctx.tools.prices(item.name, unit_qty=qty)
            if cost == 0.0:
                notes.append(f"No price found for '{item.name}' — excluded from the estimate.")
                continue
            breakdown.append(CostLine(
                item=f"{item.name} ({item.quantity})", category="groceries",
                weekly_cost=cost, source=source,
            ))
            total += cost
        return total

    async def _price_supplements(
        self, ctx: AgentContext, breakdown: list[CostLine]
    ) -> float:
        n = ctx.state.nutrition
        if n is None:
            return 0.0
        total = 0.0
        for supp in n.supplements:
            cost, source = await ctx.tools.prices(supp, unit_qty=_SUPPLEMENT_WEEKLY_QTY)
            if cost == 0.0:
                continue
            breakdown.append(CostLine(
                item=supp, category="supplements", weekly_cost=cost, source=source,
            ))
            total += cost
        return total

    async def _price_equipment(
        self, ctx: AgentContext, breakdown: list[CostLine], notes: list[str]
    ) -> float:
        f = ctx.state.fitness
        if f is None:
            return 0.0
        owned = {a.lower() for a in ctx.profile.equipment_access}
        total = 0.0
        for eq in f.equipment_needed:
            if eq.lower() in owned:
                notes.append(f"'{eq}' already owned — no cost charged.")
                continue
            cost, source = await ctx.tools.prices(eq, unit_qty=1.0)
            if cost == 0.0:
                continue
            recurring = "membership" in eq.lower() or "gym" in eq.lower()
            weekly = cost / _WEEKS_PER_MONTH if recurring else cost / _WEEKS_PER_YEAR
            weekly = round(weekly, 2)
            label = f"{eq} ({'membership/mo' if recurring else 'one-time, amortized/yr'})"
            breakdown.append(CostLine(
                item=label, category="fitness", weekly_cost=weekly, source=source,
            ))
            total += weekly
        return total

    # ---- cut proposals (constraint-safe) ------------------------------------
    def _propose_cuts(
        self, ctx: AgentContext, overrun: float, food_cost: float, fitness_cost: float
    ) -> tuple[list[str], list[RevisionRequest]]:
        if overrun <= 0:
            return [], []
        cur = ctx.profile.currency
        c = ctx.state.constraints
        protein_floor = (
            f" while keeping protein ≥ {c.min_protein_g_per_kg:g} g/kg bodyweight"
            if c is not None and c.min_protein_g_per_kg else " while preserving the protein target"
        )
        cuts: list[str] = []
        revisions: list[RevisionRequest] = []

        # Food is usually the biggest lever; ask Nutrition for cheaper, macro-preserving swaps.
        if food_cost >= fitness_cost and food_cost > 0:
            cuts.append(
                f"Swap premium protein (paneer/whey) for eggs/legumes/tofu to cut ~{cur} "
                f"{overrun:.0f}/week{protein_floor}."
            )
            revisions.append(RevisionRequest(
                target_agent=NUTRITION, raised_by=BUDGET,
                reason=f"Plan is over budget by {cur} {overrun:.0f}/week.",
                constraint=(
                    f"Cut weekly grocery+supplement cost by ~{cur} {overrun:.0f}{protein_floor} "
                    "and do not include any excluded foods."
                ),
            ))
        # If the gym/equipment is a real driver, ask Fitness to go home/bodyweight.
        if fitness_cost > 0 and (fitness_cost > food_cost or fitness_cost >= overrun):
            cuts.append("Replace gym membership / paid equipment with a home/bodyweight program.")
            revisions.append(RevisionRequest(
                target_agent=FITNESS, raised_by=BUDGET,
                reason=f"Equipment/gym cost contributes to the {cur} {overrun:.0f}/week overrun.",
                constraint="Rebuild the program using only owned/bodyweight equipment (no paid "
                           "gym membership), keeping it within the medical limits.",
            ))
        return cuts, revisions

    def _output_summary(self, output: BudgetReport) -> str:
        status = "within budget" if output.within_budget else f"OVER by {output.overrun:.0f}"
        return (f"budget: {output.currency} {output.estimated_weekly_cost:.0f}/week "
                f"vs {output.weekly_budget:.0f} ({status}); "
                f"{len(output.revision_requests)} revision request(s)")
