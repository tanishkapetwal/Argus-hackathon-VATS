"""Contract test: Critic Agent (build-plan 3.5).

Verifies the DETERMINISTIC conflict taxonomy (no LLM — NoLLM): a coherent plan is approved with
zero conflicts; a budget overrun, a forbidden movement, an over-aggressive deficit, and a missing
disclaimer each raise the right typed Conflict; and conflicts targeting specialists become
RevisionRequests (CONFLICT_RAISED → REVISION_REQUESTED).
"""
from __future__ import annotations

from app.agents.critic import CriticAgent
from app.core.agent_names import FITNESS, NUTRITION, RESOLVER, STANDARD_DISCLAIMER
from app.schemas import (
    BudgetReport,
    ConflictType,
    Critique,
    Exercise,
    FitnessPlan,
    MacroTargets,
    Meal,
    MedicalConstraints,
    NutritionPlan,
    PlanState,
    RevisionRequest,
    TraceEventType,
    WorkoutDay,
)
from tests.agent_helpers import NoLLM, event_types, make_ctx, sample_profile


def _clean_state(profile) -> PlanState:
    state = PlanState(run_id="test-run", profile=profile)
    state.constraints = MedicalConstraints(required_disclaimers=[STANDARD_DISCLAIMER])
    state.nutrition = NutritionPlan(
        macros=MacroTargets(bmr_kcal=1700, tdee_kcal=2350, target_kcal=2050,
                            protein_g=160, carbs_g=180, fat_g=60),
        daily_meals=[Meal(name="All day", kcal=2050, protein_g=160, carbs_g=180, fat_g=60)],
        satisfies_constraints=True,
    )
    state.fitness = FitnessPlan(days_per_week=4, est_weekly_kcal_burn=1400.0,
                                satisfies_constraints=True)
    state.budget = BudgetReport(currency="INR", weekly_budget=1500, estimated_weekly_cost=1200,
                                within_budget=True, overrun=0.0)
    return state


async def test_critic_approves_coherent_plan():
    profile = sample_profile()
    ctx, _ = make_ctx(profile, llm=NoLLM(), state=_clean_state(profile), tool_names=[])
    result = await CriticAgent().run(ctx)
    out = result.output
    assert isinstance(out, Critique)
    assert out.conflicts == []
    assert out.approved is True
    assert result.revisions == []


async def test_critic_flags_budget_overrun_and_emits_revision():
    profile = sample_profile()
    state = _clean_state(profile)
    state.budget = BudgetReport(
        currency="INR", weekly_budget=1500, estimated_weekly_cost=2100,
        within_budget=False, overrun=600.0,
        revision_requests=[RevisionRequest(target_agent=NUTRITION, raised_by="budget",
                                           reason="over", constraint="cut cost")],
    )
    ctx, emitter = make_ctx(profile, llm=NoLLM(), state=state, tool_names=[])
    result = await CriticAgent().run(ctx)

    conflict_types = {c.type for c in result.output.conflicts}
    assert ConflictType.BUDGET_OVERRUN in conflict_types
    assert result.output.approved is False
    # the budget conflict targets nutrition → becomes a critic RevisionRequest
    assert any(r.target_agent == NUTRITION and r.raised_by == "critic" for r in result.revisions)
    types = event_types(emitter)
    assert TraceEventType.CONFLICT_RAISED in types
    assert TraceEventType.REVISION_REQUESTED in types


async def test_critic_flags_forbidden_movement():
    profile = sample_profile()
    state = _clean_state(profile)
    state.constraints.forbidden_movements = ["box jumps"]
    state.fitness.weekly_schedule = [
        WorkoutDay(day_label="Mon", focus="Plyo",
                   exercises=[Exercise(name="Box Jumps")])
    ]
    ctx, _ = make_ctx(profile, llm=NoLLM(), state=state, tool_names=[])
    result = await CriticAgent().run(ctx)
    med = [c for c in result.output.conflicts if c.type == ConflictType.MEDICAL_VIOLATION]
    assert med and med[0].target_agents == [FITNESS]


async def test_critic_flags_aggressive_energy_deficit():
    profile = sample_profile()  # weight 80 → safe ≈0.8 kg/week
    state = _clean_state(profile)
    state.nutrition.macros = MacroTargets(bmr_kcal=1700, tdee_kcal=2350, target_kcal=1500,
                                          protein_g=160, carbs_g=120, fat_g=45)
    state.nutrition.daily_meals = [Meal(name="All day", kcal=1500, protein_g=160,
                                        carbs_g=120, fat_g=45)]
    state.fitness.est_weekly_kcal_burn = 2100.0  # ~300 kcal/day extra burn
    ctx, _ = make_ctx(profile, llm=NoLLM(), state=state, tool_names=[])
    result = await CriticAgent().run(ctx)
    assert any(c.type == ConflictType.ENERGY_IMBALANCE for c in result.output.conflicts)


async def test_critic_flags_missing_disclaimer_to_resolver():
    profile = sample_profile()
    state = _clean_state(profile)
    state.constraints.required_disclaimers = []
    ctx, _ = make_ctx(profile, llm=NoLLM(), state=state, tool_names=[])
    result = await CriticAgent().run(ctx)
    miss = [c for c in result.output.conflicts if c.type == ConflictType.MISSING_DISCLAIMER]
    assert miss and miss[0].target_agents == [RESOLVER]
    # resolver-targeted conflicts do NOT become specialist revision requests
    assert all(r.target_agent in (NUTRITION, FITNESS) for r in result.revisions)
