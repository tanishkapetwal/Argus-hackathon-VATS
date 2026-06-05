"""End-to-end orchestration test (build-plan Phase 4): run the whole LangGraph offline.

Uses the `scripted` LLM provider (no API key) on the conflict-forcing demo profile from
frontend/src/App.tsx. Asserts the full run produces a HealthPlan, streams the right trace
events, and shows a VISIBLE refinement round (CONFLICT_RAISED → REVISION_REQUESTED → agent
re-run) that converges — plus a bounded-loop variant that always finalizes with an honest gap.
"""
from __future__ import annotations

import app.core.config as config
from app.core.config import Settings
from app.core.trace import TraceEmitter
from app.orchestration.runner import run_plan
from app.schemas import (
    ActivityLevel,
    Goal,
    HealthPlan,
    Sex,
    TraceEventType,
    UserProfile,
)

# The conflict-forcing demo profile (mirrors frontend/src/App.tsx DEMO_PROFILE).
DEMO_PROFILE = UserProfile(
    age=34, sex=Sex.male, height_cm=178, weight_kg=92, activity_level=ActivityLevel.light,
    goal=Goal.fat_loss, target_weight_kg=78, timeframe_weeks=12,
    medical_conditions=["knee injury", "hypertension"], medications=[], allergies=["peanuts"],
    budget_weekly=1500, currency="INR", diet_preference="high protein, vegetarian",
    disliked_foods=["mushroom"], equipment_access=["dumbbells"],
    days_per_week=4, session_minutes=45, notes="wants visible results fast",
)


def _use_scripted(monkeypatch, *, max_rounds=3):
    """Force the offline scripted provider + seeded prices + no USDA network for the whole graph."""
    monkeypatch.setattr(config, "_settings", Settings(
        llm_provider="scripted", usda_fdc_api_key="", use_seeded_prices=True,
        max_refinement_rounds=max_rounds,
    ))


async def test_end_to_end_run_with_visible_refinement(monkeypatch):
    _use_scripted(monkeypatch, max_rounds=3)
    emitter = TraceEmitter(run_id="e2e")

    plan = await run_plan(DEMO_PROFILE, "e2e", emitter)

    # a final integrated plan emerged
    assert isinstance(plan, HealthPlan)
    assert plan.requires_professional is False

    events = emitter.events
    types = [e.type for e in events]
    assert types[0] == TraceEventType.RUN_STARTED
    assert types[-1] == TraceEventType.RUN_COMPLETED

    # the debate is visible: a conflict was raised, a revision requested, and a new round started
    assert TraceEventType.CONFLICT_RAISED in types
    assert TraceEventType.REVISION_REQUESTED in types
    assert TraceEventType.ROUND_STARTED in types

    # the trigger was the budget overrun on the tight ₹1500 budget
    conflicts = [e for e in events if e.type == TraceEventType.CONFLICT_RAISED]
    assert any("BUDGET_OVERRUN" in e.summary for e in conflicts)

    # nutrition actually RE-RAN in a later round (the agent re-run the prompt asked for)
    nutrition_runs = [e for e in events
                      if e.type == TraceEventType.AGENT_STARTED and e.agent == "nutrition"]
    assert len(nutrition_runs) >= 2
    assert max(e.round for e in nutrition_runs) >= 1

    # the calorie handshake nutrition⇄fitness is present and traced
    messages = [e for e in events if e.type == TraceEventType.MESSAGE_SENT]
    assert any(e.payload.get("intent") == "calorie_handshake" for e in messages)

    # it converged within the bound: the cheaper revised diet fits the budget
    assert plan.budget.within_budget is True
    assert plan.open_tradeoffs == []
    # RUN_COMPLETED carries the full HealthPlan
    completed = events[-1]
    assert completed.payload["plan"]["summary"] == plan.summary


async def test_bounded_loop_always_finalizes_with_honest_gap(monkeypatch):
    # max_refinement_rounds=0 → no refinement allowed; the Resolver must still finalize.
    _use_scripted(monkeypatch, max_rounds=0)
    emitter = TraceEmitter(run_id="bounded")

    plan = await run_plan(DEMO_PROFILE, "bounded", emitter)

    assert isinstance(plan, HealthPlan)
    assert TraceEventType.ROUND_STARTED not in [e.type for e in emitter.events]  # no refinement
    # the unresolved budget overrun is surfaced honestly rather than looping forever
    assert plan.budget.within_budget is False
    assert any("BUDGET_OVERRUN" in t for t in plan.open_tradeoffs)
    assert plan.requires_professional is False


async def test_red_flag_profile_short_circuits_to_referral(monkeypatch):
    # A red-flag condition makes the Resolver refuse to optimize (safety overrides everything).
    _use_scripted(monkeypatch, max_rounds=3)
    profile = DEMO_PROFILE.model_copy(update={
        "medical_conditions": ["chest pain", "uncontrolled hypertension"],
        "budget_weekly": 5000,  # comfortable budget → the referral, not budget, is the story
    })
    emitter = TraceEmitter(run_id="redflag")

    plan = await run_plan(profile, "redflag", emitter)

    assert isinstance(plan, HealthPlan)
    assert plan.requires_professional is True
    assert "professional" in plan.summary.lower()
    assert plan.constraints.requires_professional is True
