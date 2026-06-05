"""Typed inter-agent contracts (Pydantic v2).

Authoritative spec: docs/data-models.md. These models are the ONLY way agents communicate.
This package re-exports everything for convenient `from app.schemas import X`.
Implements build-plan task 0.3.
"""
from app.schemas.models import (  # noqa: F401
    ActivityLevel,
    AgentContribution,
    AgentMessage,
    BudgetReport,
    Conflict,
    ConflictType,
    CostLine,
    Critique,
    Exercise,
    FitnessPlan,
    FoodItem,
    Goal,
    HealthPlan,
    MacroTargets,
    Meal,
    MedicalConstraints,
    MedicalFlag,
    NutritionPlan,
    PlanState,
    RevisionRequest,
    Severity,
    Sex,
    TraceEvent,
    TraceEventType,
    UserProfile,
    WorkoutDay,
)
