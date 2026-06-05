"""Contract test: Budget Agent (build-plan 3.4).

Verifies it is DETERMINISTIC (never calls the LLM — NoLLM), prices the grocery list + supplements
+ equipment from the seeded table, skips already-owned equipment, computes overrun, and emits a
constraint-safe RevisionRequest to nutrition (respecting the protein floor) when over budget.
"""
from __future__ import annotations

from app.agents.budget import BudgetAgent
from app.core.agent_names import BUDGET, NUTRITION
from app.schemas import (
    BudgetReport,
    FitnessPlan,
    FoodItem,
    MacroTargets,
    MedicalConstraints,
    NutritionPlan,
    PlanState,
    TraceEventType,
)
from tests.agent_helpers import NoLLM, event_types, make_ctx, sample_profile


def _grocery(name: str, quantity: str) -> FoodItem:
    return FoodItem(name=name, quantity=quantity, kcal=0, protein_g=0, carbs_g=0, fat_g=0)


def _state(profile, *, groceries, supplements=None, equipment=None) -> PlanState:
    state = PlanState(run_id="test-run", profile=profile)
    state.constraints = MedicalConstraints(min_protein_g_per_kg=1.6)
    state.nutrition = NutritionPlan(
        macros=MacroTargets(bmr_kcal=1700, tdee_kcal=2350, target_kcal=2050,
                            protein_g=160, carbs_g=180, fat_g=60),
        weekly_grocery_list=groceries, supplements=supplements or [],
    )
    state.fitness = FitnessPlan(days_per_week=4, est_weekly_kcal_burn=1440,
                                equipment_needed=equipment or [])
    return state


async def test_budget_over_budget_emits_nutrition_revision():
    profile = sample_profile(budget_weekly=1500.0, equipment_access=["dumbbells"])
    state = _state(
        profile,
        groceries=[_grocery("paneer", "2 kg"), _grocery("tofu", "2 kg"),
                   _grocery("lentils", "1 kg"), _grocery("rice", "2 kg")],
        supplements=["whey protein"],
        equipment=["dumbbells", "gym membership"],  # dumbbells already owned
    )
    ctx, emitter = make_ctx(profile, llm=NoLLM(), state=state,
                            tool_names=["prices", "usda", "web_search"])

    result = await BudgetAgent().run(ctx)
    out = result.output

    assert isinstance(out, BudgetReport)
    # seeded: paneer 2×350 + tofu 2×200 + lentils 120 + rice 2×60 = 1340 groceries
    #         + whey 2000×0.25 = 500 supplements + gym 1500/4.33 ≈ 346.42 fitness
    assert out.estimated_weekly_cost == round(sum(c.weekly_cost for c in out.breakdown), 2)
    assert out.within_budget is False
    assert out.overrun == round(out.estimated_weekly_cost - 1500.0, 2) > 0
    # already-owned dumbbells are NOT charged
    assert not any("dumbbells" in c.item.lower() for c in out.breakdown)
    assert any("dumbbells" in n.lower() and "owned" in n.lower() for n in out.notes)
    # a constraint-safe revision to nutrition, respecting the protein floor
    nut_revs = [r for r in out.revision_requests if r.target_agent == NUTRITION]
    assert nut_revs and nut_revs[0].raised_by == BUDGET
    assert "1.6" in nut_revs[0].constraint  # min_protein_g_per_kg surfaced
    # revisions flow through AgentResult so BaseAgent emits REVISION_REQUESTED
    assert result.revisions == out.revision_requests
    assert TraceEventType.REVISION_REQUESTED in event_types(emitter)
    assert TraceEventType.TOOL_CALLED in event_types(emitter)


async def test_budget_within_budget_no_revisions():
    profile = sample_profile(budget_weekly=1500.0, equipment_access=["dumbbells"])
    state = _state(
        profile,
        groceries=[_grocery("lentils", "1 kg"), _grocery("rice", "1 kg"),
                   _grocery("eggs", "12 eggs"), _grocery("milk", "1 L")],
        equipment=["dumbbells"],  # owned → free
    )
    ctx, _ = make_ctx(profile, llm=NoLLM(), state=state,
                      tool_names=["prices", "usda", "web_search"])

    out = (await BudgetAgent().run(ctx)).output
    assert out.within_budget is True
    assert out.overrun == 0.0
    assert out.revision_requests == []
