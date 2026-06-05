"""Contract test: Resolver Agent (build-plan 3.6).

Verifies it is DETERMINISTIC (no LLM — NoLLM) and ALWAYS finalizes a HealthPlan: a clean state
yields a coherent plan with no open trade-offs; surviving conflicts become labelled trade-offs
resolved by the priority order; a red flag short-circuits into a "consult a professional" plan;
and agent_contributions capture who influenced whom.
"""
from __future__ import annotations

from app.agents.resolver import ResolverAgent
from app.core.agent_names import BUDGET, FITNESS, MEDICAL_RISK, NUTRITION, STANDARD_DISCLAIMER
from app.schemas import (
    AgentMessage,
    BudgetReport,
    Conflict,
    ConflictType,
    FitnessPlan,
    HealthPlan,
    MacroTargets,
    MedicalConstraints,
    MedicalFlag,
    NutritionPlan,
    PlanState,
    RevisionRequest,
    Severity,
)
from tests.agent_helpers import NoLLM, make_ctx, sample_profile


def _state(profile, *, requires_pro=False, open_conflicts=None, within_budget=True) -> PlanState:
    state = PlanState(run_id="test-run", profile=profile)
    state.constraints = MedicalConstraints(
        required_disclaimers=[STANDARD_DISCLAIMER], requires_professional=requires_pro,
        forbidden_movements=["box jumps"], excluded_foods=["peanuts"],
        flags=[MedicalFlag(condition="hypertension", severity=Severity.red_flag,
                           rationale="elevated BP")] if requires_pro else [],
    )
    state.nutrition = NutritionPlan(
        macros=MacroTargets(bmr_kcal=1800, tdee_kcal=2569, target_kcal=2054,
                            protein_g=184, carbs_g=180, fat_g=57),
    )
    state.fitness = FitnessPlan(days_per_week=4, est_weekly_kcal_burn=1656.0)
    state.budget = BudgetReport(
        currency="INR", weekly_budget=1500,
        estimated_weekly_cost=1300 if within_budget else 2100,
        within_budget=within_budget, overrun=0.0 if within_budget else 600.0,
    )
    # influence edges: medical→nutrition constraint, fitness→nutrition handshake, budget→nutrition
    state.messages = [
        AgentMessage(sender=MEDICAL_RISK, recipient=NUTRITION, intent="constraint"),
        AgentMessage(sender=FITNESS, recipient=NUTRITION, intent="calorie_handshake"),
    ]
    state.revision_requests = [
        RevisionRequest(target_agent=NUTRITION, raised_by=BUDGET, reason="over", constraint="cut"),
    ]
    state.open_conflicts = open_conflicts or []
    return state


async def test_resolver_finalizes_clean_plan():
    profile = sample_profile()
    ctx, _ = make_ctx(profile, llm=NoLLM(), state=_state(profile), tool_names=[])
    plan = (await ResolverAgent().run(ctx)).output

    assert isinstance(plan, HealthPlan)
    assert plan.requires_professional is False
    assert plan.resolved_conflicts == []
    assert plan.open_tradeoffs == []
    assert STANDARD_DISCLAIMER in plan.disclaimers
    # all upstream agents represented in the "what changed and why" narrative
    agents = {c.agent for c in plan.agent_contributions}
    assert {MEDICAL_RISK, NUTRITION, FITNESS, BUDGET}.issubset(agents)
    # nutrition's contribution records who influenced it (medical, fitness, budget)
    nut = next(c for c in plan.agent_contributions if c.agent == NUTRITION)
    assert {MEDICAL_RISK, FITNESS, BUDGET}.issubset(set(nut.changed_due_to))


async def test_resolver_surfaces_unresolved_budget_tradeoff():
    profile = sample_profile()
    conflict = Conflict(
        type=ConflictType.BUDGET_OVERRUN, severity=Severity.caution,
        description="over budget", evidence="2100 vs 1500", target_agents=[NUTRITION],
    )
    state = _state(profile, open_conflicts=[conflict], within_budget=False)
    ctx, _ = make_ctx(profile, llm=NoLLM(), state=state, tool_names=[])
    plan = (await ResolverAgent().run(ctx)).output

    assert plan.resolved_conflicts == [conflict]
    assert plan.open_tradeoffs and "BUDGET_OVERRUN" in plan.open_tradeoffs[0]
    assert "gap" in plan.open_tradeoffs[0].lower()
    assert plan.requires_professional is False  # still finalizes


async def test_resolver_red_flag_refers_out_without_optimizing():
    profile = sample_profile()
    ctx, _ = make_ctx(profile, llm=NoLLM(), state=_state(profile, requires_pro=True),
                      tool_names=[])
    plan = (await ResolverAgent().run(ctx)).output

    assert plan.requires_professional is True
    assert "professional" in plan.summary.lower()
    assert STANDARD_DISCLAIMER in plan.disclaimers
