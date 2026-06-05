"""Contract test: Fitness Agent (build-plan 3.3).

Verifies it produces a FitnessPlan, overrides est_weekly_kcal_burn with the DETERMINISTIC
fitness_calc result (never the LLM's number), distributes per-day burn, flags forbidden
movements that slip into the schedule, completes the calorie handshake back to nutrition, and
emits the right trace events (incl. TOOL_CALLED for fitness_calc).
"""
from __future__ import annotations

from app.agents.fitness import FitnessAgent
from app.core.agent_names import FITNESS, NUTRITION
from app.schemas import (
    Exercise,
    FitnessPlan,
    MacroTargets,
    MedicalConstraints,
    NutritionPlan,
    PlanState,
    TraceEventType,
    WorkoutDay,
)
from app.tools.fitness_calc import estimate_weekly_burn
from tests.agent_helpers import FakeLLM, event_types, make_ctx, sample_profile


def _macros() -> MacroTargets:
    return MacroTargets(
        bmr_kcal=1700, tdee_kcal=2350, target_kcal=2050,
        protein_g=160, carbs_g=180, fat_g=60, fiber_g=30,
    )


def _state_with_constraints(profile, *, forbidden=None) -> PlanState:
    state = PlanState(run_id="test-run", profile=profile)
    state.constraints = MedicalConstraints(
        forbidden_movements=forbidden or [], max_intensity="moderate (RPE <= 6)",
    )
    state.nutrition = NutritionPlan(macros=_macros())
    return state


def _canned_plan(*, exercise_name="Goblet Squat") -> FitnessPlan:
    # est_weekly_kcal_burn deliberately wrong (9999) to prove the deterministic override.
    return FitnessPlan(
        weekly_schedule=[
            WorkoutDay(day_label="Mon", focus="Full body",
                       exercises=[Exercise(name=exercise_name, sets=3, reps="10")]),
            WorkoutDay(day_label="Wed", focus="Full body",
                       exercises=[Exercise(name="Dumbbell Row", sets=3, reps="10")]),
        ],
        days_per_week=4, est_weekly_kcal_burn=9999.0,
        equipment_needed=["dumbbells"], progression="Add reps weekly.",
    )


async def test_fitness_contract_and_deterministic_burn():
    profile = sample_profile()  # weight 80, days 4, session 45, goal fat_loss
    state = _state_with_constraints(profile)
    ctx, _ = make_ctx(profile, llm=FakeLLM(parsed=_canned_plan()), state=state,
                      tool_names=["fitness_calc", "web_search"])

    result = await FitnessAgent().run(ctx)
    out = result.output

    assert isinstance(out, FitnessPlan)
    # deterministic burn override: MET 6.0 (fat_loss) × 80kg × 0.75h × 4d = 1440 kcal/week
    expected = estimate_weekly_burn(weight_kg=80, days_per_week=4, session_minutes=45, met=6.0)
    assert out.est_weekly_kcal_burn == expected == 1440.0
    # per-day burn spread across the 2 scheduled days
    assert all(d.est_kcal_burn == round(expected / 2, 1) for d in out.weekly_schedule)
    # calorie handshake back to nutrition
    assert len(result.messages) == 1
    msg = result.messages[0]
    assert (msg.sender, msg.recipient, msg.intent) == (FITNESS, NUTRITION, "calorie_handshake")
    assert msg.payload["est_weekly_kcal_burn"] == expected


async def test_fitness_flags_forbidden_movement():
    profile = sample_profile()
    state = _state_with_constraints(profile, forbidden=["box jumps"])
    plan = _canned_plan(exercise_name="Box Jumps")  # a forbidden movement slips in
    ctx, _ = make_ctx(profile, llm=FakeLLM(parsed=plan), state=state,
                      tool_names=["fitness_calc", "web_search"])

    result = await FitnessAgent().run(ctx)
    assert result.output.satisfies_constraints is False
    assert any("forbidden movements" in n.lower() for n in result.output.constraint_notes)


async def test_fitness_emits_trace_events():
    profile = sample_profile()
    state = _state_with_constraints(profile)
    ctx, emitter = make_ctx(profile, llm=FakeLLM(parsed=_canned_plan()), state=state,
                            tool_names=["fitness_calc", "web_search"])

    await FitnessAgent().run(ctx)
    types = event_types(emitter)

    assert types[0] == TraceEventType.AGENT_STARTED
    assert types[-1] == TraceEventType.AGENT_COMPLETED
    for required in (TraceEventType.AGENT_INPUT, TraceEventType.AGENT_OUTPUT,
                     TraceEventType.TOOL_CALLED, TraceEventType.MESSAGE_SENT):
        assert required in types
    assert types.count(TraceEventType.MESSAGE_SENT) == 1  # one handshake edge → nutrition
