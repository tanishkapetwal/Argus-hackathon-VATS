"""⚖️ Resolver Agent — spec: docs/agents/resolver-agent.md. Build-plan task 3.6.

The judge. Reconciles remaining conflicts by the fixed priority (safety > physiology > budget >
preference) and synthesizes the final HealthPlan incl. the per-agent "what changed and why"
narrative. Always produces a plan (lists unresolved trade-offs rather than looping).

DETERMINISTIC by design (no LLM — see tests/agent_helpers.NoLLM): it synthesizes from the typed
state so it can NEVER fail to finalize. A red-flag (`requires_professional`) short-circuits
optimization into a "consult a professional first" plan (docs/orchestration.md §6/§7).
"""
from __future__ import annotations

from app.core.agent_names import (
    BUDGET,
    CRITIC,
    FITNESS,
    MEDICAL_RISK,
    NUTRITION,
    RESOLVER,
    STANDARD_DISCLAIMER,
)
from app.core.base_agent import AgentContext, AgentResult, BaseAgent
from app.core.registry import register
from app.schemas import (
    AgentContribution,
    BudgetReport,
    Conflict,
    ConflictType,
    FitnessPlan,
    HealthPlan,
    MacroTargets,
    MedicalConstraints,
    NutritionPlan,
)

# Which resolution rule decides each conflict type (docs/orchestration.md §6, priority order).
_RULE_FOR_CONFLICT: dict[ConflictType, str] = {
    ConflictType.MEDICAL_VIOLATION: "Rule 1 (medical safety): the medical constraint is kept; "
                                    "the offending item must be removed — safety overrides all.",
    ConflictType.MISSING_DISCLAIMER: "Rule 1 (medical safety): required disclaimer attached.",
    ConflictType.ENERGY_IMBALANCE: "Rule 2 (physiology): rate capped to a safe deficit/surplus "
                                   "before optimizing anything else.",
    ConflictType.RECOVERY_RISK: "Rule 2 (physiology): training volume kept recoverable for the "
                                "diet's energy.",
    ConflictType.BUDGET_OVERRUN: "Rule 3 (budget): fit the budget without breaking safety; if "
                                 "impossible, present the minimum-feasible cost and the gap.",
    ConflictType.MACRO_INCOHERENCE: "Rule 4 (preference/adherence): macros re-balanced to the "
                                    "target with preferred foods.",
}


@register(RESOLVER)
class ResolverAgent(BaseAgent):
    tier = "strong"
    tools: list[str] = []
    output_schema = HealthPlan

    async def _run(self, ctx: AgentContext) -> AgentResult:
        p = ctx.profile
        s = ctx.state
        constraints = s.constraints or MedicalConstraints()
        nutrition = s.nutrition or NutritionPlan(
            macros=MacroTargets(bmr_kcal=0, tdee_kcal=0, target_kcal=0,
                                protein_g=0, carbs_g=0, fat_g=0)
        )
        fitness = s.fitness or FitnessPlan(days_per_week=0, est_weekly_kcal_burn=0)
        budget = s.budget or BudgetReport(
            currency=p.currency, weekly_budget=p.budget_weekly,
            estimated_weekly_cost=0, within_budget=True,
        )
        disclaimers = self._disclaimers(constraints)
        contributions = self._contributions(ctx, constraints, nutrition, fitness, budget)

        # Red flag short-circuits optimization (safety overrides everything).
        if constraints.requires_professional:
            plan = self._referral_plan(p, constraints, nutrition, fitness, budget,
                                       disclaimers, contributions)
            return AgentResult(output=plan)

        resolved, tradeoffs = self._reconcile(s.open_conflicts, budget)
        summary, rationale = self._narrative(ctx, nutrition, fitness, budget, resolved, tradeoffs)

        plan = HealthPlan(
            profile=p, constraints=constraints, nutrition=nutrition, fitness=fitness,
            budget=budget, summary=summary, rationale=rationale,
            resolved_conflicts=resolved, open_tradeoffs=tradeoffs,
            agent_contributions=contributions, requires_professional=False,
            disclaimers=disclaimers,
        )
        return AgentResult(output=plan)

    # ---- conflict reconciliation (priority-ordered) -------------------------
    def _reconcile(
        self, open_conflicts: list[Conflict], budget: BudgetReport
    ) -> tuple[list[Conflict], list[str]]:
        """Adjudicate every still-open conflict by the priority order; surface honest trade-offs.

        Conflicts reaching the Resolver survived all refinement rounds, so each becomes a clearly
        labelled trade-off explaining which rule decided it (the trace's payoff).
        """
        resolved = list(open_conflicts)
        tradeoffs: list[str] = []
        for c in open_conflicts:
            rule = _RULE_FOR_CONFLICT.get(c.type, "Resolved by the standard priority order.")
            note = f"[{c.type.value}] {rule}"
            if c.type == ConflictType.BUDGET_OVERRUN and not budget.within_budget:
                note += (f" Minimum-feasible cost {budget.currency} "
                         f"{budget.estimated_weekly_cost:.0f}/week leaves a "
                         f"{budget.currency} {budget.overrun:.0f}/week gap above budget.")
            tradeoffs.append(note)
        return resolved, tradeoffs

    # ---- per-agent contributions ("what changed and why") -------------------
    def _contributions(
        self, ctx: AgentContext, constraints: MedicalConstraints, nutrition: NutritionPlan,
        fitness: FitnessPlan, budget: BudgetReport,
    ) -> list[AgentContribution]:
        m = nutrition.macros
        status = "within budget" if budget.within_budget else f"over by {budget.overrun:.0f}"
        return [
            AgentContribution(
                agent=MEDICAL_RISK,
                summary=f"Set the rules of the game: {len(constraints.flags)} flag(s), "
                        f"{len(constraints.forbidden_movements)} forbidden movement(s), diet caps "
                        f"and {len(constraints.excluded_foods)} excluded food(s).",
                changed_due_to=[],
            ),
            AgentContribution(
                agent=NUTRITION,
                summary=f"{m.target_kcal:.0f} kcal/day, {m.protein_g:.0f} g protein across "
                        f"{len(nutrition.daily_meals)} meal(s).",
                changed_due_to=self._changed_by(ctx, NUTRITION),
            ),
            AgentContribution(
                agent=FITNESS,
                summary=f"{fitness.days_per_week}-day program, "
                        f"~{fitness.est_weekly_kcal_burn:.0f} kcal/week burn.",
                changed_due_to=self._changed_by(ctx, FITNESS),
            ),
            AgentContribution(
                agent=BUDGET,
                summary=f"{budget.currency} {budget.estimated_weekly_cost:.0f}/week ({status}); "
                        f"{len(budget.revision_requests)} revision request(s).",
                changed_due_to=[NUTRITION, FITNESS],
            ),
            AgentContribution(
                agent=CRITIC,
                summary=f"Adjudicated the plan; {len(ctx.state.open_conflicts)} conflict(s) open "
                        "at finalization.",
                changed_due_to=[NUTRITION, FITNESS, BUDGET],
            ),
        ]

    @staticmethod
    def _changed_by(ctx: AgentContext, agent: str) -> list[str]:
        """Who influenced this agent: revision raisers + handshake/constraint message senders."""
        sources = {r.raised_by for r in ctx.state.revision_requests if r.target_agent == agent}
        for msg in ctx.state.messages:
            if msg.recipient == agent and msg.intent in ("calorie_handshake", "constraint"):
                sources.add(msg.sender)
        return sorted(sources)

    # ---- narrative ----------------------------------------------------------
    def _narrative(self, ctx, nutrition, fitness, budget, resolved, tradeoffs):
        p = ctx.profile
        m = nutrition.macros
        budget_clause = (
            f"within the {budget.currency} {budget.weekly_budget:.0f}/week budget"
            if budget.within_budget
            else f"at {budget.currency} {budget.estimated_weekly_cost:.0f}/week "
                 f"({budget.currency} {budget.overrun:.0f} over budget)"
        )
        summary = (
            f"Integrated {p.goal.value.replace('_', ' ')} plan: a {m.target_kcal:.0f} kcal/day "
            f"diet and a {fitness.days_per_week}-day workout (~{fitness.est_weekly_kcal_burn:.0f} "
            f"kcal/week burn), costed {budget_clause}."
        )
        if not resolved:
            rationale = (
                "All specialist outputs were mutually consistent after refinement: the diet meets "
                "the medical caps, the calorie handshake keeps the deficit/surplus in the safe "
                "range, and the cost fits the budget. No conflicts remained for the Resolver."
            )
        else:
            rationale = (
                f"Reconciled {len(resolved)} remaining conflict(s) by the fixed priority "
                "(safety > physiology > budget > preference): "
                + " ".join(tradeoffs)
            )
        return summary, rationale

    # ---- red-flag referral plan --------------------------------------------
    def _referral_plan(
        self, p, constraints, nutrition, fitness, budget, disclaimers, contributions
    ) -> HealthPlan:
        flags = ", ".join(f.condition for f in constraints.flags) or "a flagged condition"
        summary = (
            f"⚠️ Consult a qualified healthcare professional before starting this plan. Your "
            f"profile shows {flags} that requires medical clearance first. The diet/workout below "
            "are general, conservative references only — not a prescription."
        )
        rationale = (
            "A red-flag medical condition short-circuits optimization (safety overrides "
            "everything): the system does not tune an aggressive plan around a serious risk. "
            "Seek professional clearance, then this plan can be refined safely."
        )
        return HealthPlan(
            profile=p, constraints=constraints, nutrition=nutrition, fitness=fitness,
            budget=budget, summary=summary, rationale=rationale,
            resolved_conflicts=[], open_tradeoffs=["Optimization deferred pending professional "
                                                   "clearance."],
            agent_contributions=contributions, requires_professional=True,
            disclaimers=disclaimers,
        )

    @staticmethod
    def _disclaimers(constraints: MedicalConstraints) -> list[str]:
        out = list(constraints.required_disclaimers)
        if STANDARD_DISCLAIMER not in out:
            out.insert(0, STANDARD_DISCLAIMER)
        return out

    def _output_summary(self, output: HealthPlan) -> str:
        tag = " · REFERRAL" if output.requires_professional else ""
        return (f"resolver: final HealthPlan{tag} — {len(output.resolved_conflicts)} resolved, "
                f"{len(output.open_tradeoffs)} open trade-off(s)")
