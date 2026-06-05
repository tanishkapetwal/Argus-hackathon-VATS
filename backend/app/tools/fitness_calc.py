"""Deterministic exercise calorie-burn estimator — the Fitness Agent's reliability backbone.

NO LLM: MET-based math (kcal = MET x bodyweight_kg x hours), summed across weekly sessions.
The Fitness Agent uses this so its `est_weekly_kcal_burn` is consistent and defensible — the
same "math is a tool, not the LLM" principle as macros.py (docs/agents/fitness-agent.md §5).
"""
from __future__ import annotations

# Representative MET values by training style (compendium-of-physical-activities ballpark).
MET_BY_STYLE: dict[str, float] = {
    "strength": 5.0,
    "hypertrophy": 5.0,
    "general": 6.0,
    "cardio": 7.0,
    "endurance": 8.0,
    "hiit": 9.0,
}


def met_for(style: str) -> float:
    """MET for a training style; defaults to moderate (6.0) for unknown styles."""
    return MET_BY_STYLE.get(style.strip().lower(), 6.0)


def estimate_weekly_burn(
    *, weight_kg: float, days_per_week: int, session_minutes: int, met: float = 6.0
) -> float:
    """Weekly exercise calorie burn = MET x weight_kg x hours/session x sessions/week."""
    hours_per_session = session_minutes / 60.0
    per_session = met * weight_kg * hours_per_session
    return round(per_session * days_per_week, 1)
