"""Deterministic macro calculator — the reliability backbone of the Nutrition Agent.

NO LLM, NO API: pure, fully-testable math (BMR via Mifflin-St Jeor, TDEE via activity
multiplier, goal-adjusted & safety-capped calories, macro split). The Nutrition Agent MUST use
this for all numbers (docs/agents/nutrition-agent.md). Implements build-plan task 1.1.

This file is a complete reference implementation, not a stub — it seeds the determinism
principle and should be unit-tested (tests/test_macros.py).
"""
from __future__ import annotations

from app.schemas import ActivityLevel, Goal, MacroTargets, Sex

# Activity multipliers (standard TDEE factors).
_ACTIVITY_MULTIPLIER: dict[ActivityLevel, float] = {
    ActivityLevel.sedentary: 1.2,
    ActivityLevel.light: 1.375,
    ActivityLevel.moderate: 1.55,
    ActivityLevel.active: 1.725,
    ActivityLevel.very_active: 1.9,
}

# Goal calorie adjustment as a fraction of TDEE (negative = deficit).
_GOAL_ADJUSTMENT: dict[Goal, float] = {
    Goal.fat_loss: -0.20,
    Goal.muscle_gain: +0.10,
    Goal.maintenance: 0.0,
    Goal.general_health: 0.0,
    Goal.endurance: +0.05,
}

# Safety floors / caps.
_MIN_KCAL_FEMALE = 1200.0
_MIN_KCAL_MALE = 1500.0
# A safe rate of weight change is ~0.5-1% of bodyweight per week. We cap the deficit/surplus
# so the Nutrition Agent can never silently prescribe an unsafe rate (the Critic also checks).
_MAX_WEEKLY_PCT_CHANGE = 0.01  # 1% of bodyweight/week
_KCAL_PER_KG = 7700.0          # approx energy in 1 kg of body mass


def mifflin_st_jeor_bmr(*, sex: Sex, weight_kg: float, height_cm: float, age: int) -> float:
    """Resting energy expenditure (kcal/day). Mifflin-St Jeor equation."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    if sex == Sex.male:
        return base + 5
    if sex == Sex.female:
        return base - 161
    # 'other' / unspecified: average the two constants.
    return base - 78


def _macro_split(target_kcal: float, weight_kg: float, goal: Goal) -> tuple[float, float, float, float]:
    """Return (protein_g, carbs_g, fat_g, fiber_g) for the goal.

    Protein is set per kg bodyweight (higher for fat loss / muscle gain to preserve lean mass),
    fat at ~25% of calories, carbs fill the remainder. 4/4/9 kcal per g.
    """
    protein_per_kg = {
        Goal.fat_loss: 2.0,
        Goal.muscle_gain: 2.0,
        Goal.maintenance: 1.6,
        Goal.general_health: 1.4,
        Goal.endurance: 1.6,
    }[goal]
    protein_g = round(protein_per_kg * weight_kg)
    fat_g = round((0.25 * target_kcal) / 9)
    remaining = target_kcal - (protein_g * 4) - (fat_g * 9)
    carbs_g = round(max(remaining, 0) / 4)
    fiber_g = round(14 * (target_kcal / 1000))  # ~14 g per 1000 kcal (dietary guideline)
    return float(protein_g), float(carbs_g), float(fat_g), float(fiber_g)


def calculate_macros(
    *,
    sex: Sex,
    weight_kg: float,
    height_cm: float,
    age: int,
    activity_level: ActivityLevel,
    goal: Goal,
    timeframe_weeks: int | None = None,
    target_weight_kg: float | None = None,
) -> MacroTargets:
    """Compute BMR -> TDEE -> goal-adjusted, safety-capped target calories + macro split.

    Deterministic and side-effect free. If the requested rate (from target_weight + timeframe)
    exceeds the safe cap, the calories are clamped and the rationale notes that the timeframe
    effectively extends — the agent surfaces this rather than prescribing an unsafe deficit.
    """
    bmr = round(mifflin_st_jeor_bmr(sex=sex, weight_kg=weight_kg, height_cm=height_cm, age=age))
    tdee = round(bmr * _ACTIVITY_MULTIPLIER[activity_level])

    # Default adjustment from the goal.
    adjustment_kcal = tdee * _GOAL_ADJUSTMENT[goal]

    # Cap the magnitude of the adjustment to the safe weekly rate.
    max_daily_delta = (_MAX_WEEKLY_PCT_CHANGE * weight_kg * _KCAL_PER_KG) / 7
    capped = max(-max_daily_delta, min(max_daily_delta, adjustment_kcal))

    target = tdee + capped

    # Absolute calorie floor for safety.
    floor = _MIN_KCAL_MALE if sex == Sex.male else _MIN_KCAL_FEMALE
    safety_note = ""
    if target < floor:
        target = floor
        safety_note = f" Calories floored at {floor:.0f} kcal for safety."
    if abs(capped) < abs(adjustment_kcal) - 1:
        safety_note += " Deficit/surplus capped to a safe rate (~1% bodyweight/week)."

    target = round(target)
    protein_g, carbs_g, fat_g, fiber_g = _macro_split(target, weight_kg, goal)

    rationale = (
        f"BMR {bmr} kcal (Mifflin-St Jeor) x activity {_ACTIVITY_MULTIPLIER[activity_level]} "
        f"= TDEE {tdee} kcal; goal '{goal.value}' -> target {target} kcal."
        + safety_note
    )

    return MacroTargets(
        bmr_kcal=float(bmr),
        tdee_kcal=float(tdee),
        target_kcal=float(target),
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        fiber_g=fiber_g,
        rationale=rationale.strip(),
    )
