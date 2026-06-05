"""Pydantic v2 models — the typed contracts between agents.

This file mirrors docs/data-models.md exactly. Keep them in sync (docs/contributing.md:
docs-in-step rule). These are real, usable models — Phase 0.3 of the build plan delivers them
so every later phase has a stable contract to build against.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ─────────────────────────────── enums ────────────────────────────────────
class Sex(str, Enum):
    male = "male"
    female = "female"
    other = "other"


class ActivityLevel(str, Enum):
    sedentary = "sedentary"
    light = "light"
    moderate = "moderate"
    active = "active"
    very_active = "very_active"


class Goal(str, Enum):
    fat_loss = "fat_loss"
    muscle_gain = "muscle_gain"
    maintenance = "maintenance"
    general_health = "general_health"
    endurance = "endurance"


class Severity(str, Enum):
    info = "info"
    caution = "caution"
    hard_limit = "hard_limit"
    red_flag = "red_flag"


class ConflictType(str, Enum):
    MEDICAL_VIOLATION = "MEDICAL_VIOLATION"
    ENERGY_IMBALANCE = "ENERGY_IMBALANCE"
    BUDGET_OVERRUN = "BUDGET_OVERRUN"
    MACRO_INCOHERENCE = "MACRO_INCOHERENCE"
    RECOVERY_RISK = "RECOVERY_RISK"
    MISSING_DISCLAIMER = "MISSING_DISCLAIMER"


class TraceEventType(str, Enum):
    RUN_STARTED = "RUN_STARTED"
    ROUND_STARTED = "ROUND_STARTED"
    AGENT_STARTED = "AGENT_STARTED"
    AGENT_INPUT = "AGENT_INPUT"
    AGENT_OUTPUT = "AGENT_OUTPUT"
    TOOL_CALLED = "TOOL_CALLED"
    MESSAGE_SENT = "MESSAGE_SENT"
    CONFLICT_RAISED = "CONFLICT_RAISED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    AGENT_COMPLETED = "AGENT_COMPLETED"
    RUN_COMPLETED = "RUN_COMPLETED"
    ERROR = "ERROR"


# ─────────────────────────────── input ────────────────────────────────────
class UserProfile(BaseModel):
    age: int
    sex: Sex
    height_cm: float
    weight_kg: float
    activity_level: ActivityLevel

    goal: Goal
    target_weight_kg: float | None = None
    timeframe_weeks: int | None = None

    medical_conditions: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)

    budget_weekly: float
    currency: str = "INR"
    diet_preference: str | None = None
    disliked_foods: list[str] = Field(default_factory=list)
    equipment_access: list[str] = Field(default_factory=list)
    days_per_week: int | None = None
    session_minutes: int | None = None
    notes: str | None = None


# ──────────────────────────── medical gate ────────────────────────────────
class MedicalFlag(BaseModel):
    condition: str
    severity: Severity
    rationale: str
    source: str | None = None


class MedicalConstraints(BaseModel):
    max_added_sugar_g: float | None = None
    max_sodium_mg: float | None = None
    max_saturated_fat_g: float | None = None
    min_protein_g_per_kg: float | None = None
    excluded_foods: list[str] = Field(default_factory=list)
    required_nutrients: list[str] = Field(default_factory=list)

    forbidden_movements: list[str] = Field(default_factory=list)
    max_intensity: str | None = None
    requires_warmup: bool = True
    max_heart_rate_pct: float | None = None

    requires_professional: bool = False
    flags: list[MedicalFlag] = Field(default_factory=list)
    required_disclaimers: list[str] = Field(default_factory=list)


# ───────────────────────────── nutrition ──────────────────────────────────
class MacroTargets(BaseModel):
    bmr_kcal: float
    tdee_kcal: float
    target_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None = None
    rationale: str = ""


class FoodItem(BaseModel):
    name: str
    quantity: str
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fdc_id: int | None = None


class Meal(BaseModel):
    name: str
    items: list[FoodItem] = Field(default_factory=list)
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


class NutritionPlan(BaseModel):
    macros: MacroTargets
    daily_meals: list[Meal] = Field(default_factory=list)
    weekly_grocery_list: list[FoodItem] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)
    satisfies_constraints: bool = True
    constraint_notes: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


# ────────────────────────────── fitness ───────────────────────────────────
class Exercise(BaseModel):
    name: str
    sets: int | None = None
    reps: str | None = None
    duration_min: int | None = None
    intensity: str | None = None
    notes: str | None = None


class WorkoutDay(BaseModel):
    day_label: str
    focus: str
    exercises: list[Exercise] = Field(default_factory=list)
    est_kcal_burn: float = 0.0


class FitnessPlan(BaseModel):
    weekly_schedule: list[WorkoutDay] = Field(default_factory=list)
    days_per_week: int
    est_weekly_kcal_burn: float
    equipment_needed: list[str] = Field(default_factory=list)
    progression: str = ""
    satisfies_constraints: bool = True
    constraint_notes: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


# ─────────────────────────────── budget ───────────────────────────────────
class RevisionRequest(BaseModel):
    target_agent: str
    reason: str
    constraint: str
    raised_by: str


class CostLine(BaseModel):
    item: str
    category: str
    weekly_cost: float
    source: str


class BudgetReport(BaseModel):
    currency: str
    weekly_budget: float
    estimated_weekly_cost: float
    breakdown: list[CostLine] = Field(default_factory=list)
    within_budget: bool
    overrun: float = 0.0
    suggested_cuts: list[str] = Field(default_factory=list)
    revision_requests: list[RevisionRequest] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# ────────────────────────────── critique ──────────────────────────────────
class Conflict(BaseModel):
    type: ConflictType
    severity: Severity
    description: str
    evidence: str
    target_agents: list[str] = Field(default_factory=list)
    suggested_fix: str | None = None


class Critique(BaseModel):
    conflicts: list[Conflict] = Field(default_factory=list)
    overall_assessment: str = ""
    approved: bool = True


# ─────────────────────────── messages / edges ─────────────────────────────
class AgentMessage(BaseModel):
    """An explicit influence edge between agents — rendered in the trace view."""
    sender: str
    recipient: str
    intent: str
    payload: dict = Field(default_factory=dict)
    text: str = ""


# ──────────────────────────── final output ────────────────────────────────
class AgentContribution(BaseModel):
    agent: str
    summary: str
    changed_due_to: list[str] = Field(default_factory=list)


class HealthPlan(BaseModel):
    profile: UserProfile
    constraints: MedicalConstraints
    nutrition: NutritionPlan
    fitness: FitnessPlan
    budget: BudgetReport

    summary: str
    rationale: str
    resolved_conflicts: list[Conflict] = Field(default_factory=list)
    open_tradeoffs: list[str] = Field(default_factory=list)
    agent_contributions: list[AgentContribution] = Field(default_factory=list)
    requires_professional: bool = False
    disclaimers: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ────────────────────────── shared graph state ────────────────────────────
class PlanState(BaseModel):
    run_id: str
    profile: UserProfile
    constraints: MedicalConstraints | None = None
    nutrition: NutritionPlan | None = None
    fitness: FitnessPlan | None = None
    budget: BudgetReport | None = None
    open_conflicts: list[Conflict] = Field(default_factory=list)
    revision_requests: list[RevisionRequest] = Field(default_factory=list)
    messages: list[AgentMessage] = Field(default_factory=list)
    round: int = 0
    final_plan: HealthPlan | None = None


# ───────────────────────────── trace event ────────────────────────────────
class TraceEvent(BaseModel):
    run_id: str
    seq: int
    type: TraceEventType
    agent: str | None = None
    round: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    summary: str = ""
    payload: dict = Field(default_factory=dict)
