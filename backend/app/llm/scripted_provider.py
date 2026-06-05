"""Scripted (offline) implementation of LLMProvider — for keyless demos and deterministic runs.

Selected via `LLM_PROVIDER=scripted`. It returns realistic, demo-tuned structured outputs for the
three LLM-backed agents (Medical Risk, Nutrition, Fitness) by dispatching on the requested
`response_model`, so the whole LangGraph runs end-to-end with NO API key. The deterministic
agents (Budget, Critic, Resolver) never call an LLM, so they are unaffected.

This is a legitimate part of the provider abstraction (docs/architecture.md §2: "OpenAIProvider —
optional drop-in … the factory selects the impl from LLM_PROVIDER"). It is tuned for the
conflict-forcing demo profile in frontend/src/App.tsx: round 0's diet is over budget, and when
the Budget agent's RevisionRequest comes back the Nutrition prompt mentions it, so round 1 returns
a cheaper diet — producing one visible refinement round that converges.

The numeric backbone is still real: the Nutrition agent overrides macros with the deterministic
macros_calc result and the Fitness agent overrides burn with fitness_calc, both keyed to the
actual profile. Only the food/exercise *choices* are canned.
"""
from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from app.core.config import Settings
from app.llm.base import LLMProvider, LLMResponse
from app.schemas import (
    Exercise,
    FitnessPlan,
    FoodItem,
    MacroTargets,
    Meal,
    MedicalConstraints,
    MedicalFlag,
    NutritionPlan,
    Severity,
    WorkoutDay,
)

T = TypeVar("T", bound=BaseModel)

# A placeholder MacroTargets; the Nutrition agent overrides this with the real macros_calc result.
_PLACEHOLDER_MACROS = MacroTargets(
    bmr_kcal=0, tdee_kcal=0, target_kcal=0, protein_g=0, carbs_g=0, fat_g=0,
    rationale="placeholder — overridden by the deterministic macros_calc tool",
)


def _demo_meals() -> list[Meal]:
    """Three meals + a snack summing to ~2054 kcal / ~185 g protein (the demo profile's target)."""
    return [
        Meal(name="Breakfast", kcal=520, protein_g=38, carbs_g=60, fat_g=14,
             items=[FoodItem(name="oats", quantity="80 g", kcal=300, protein_g=11,
                             carbs_g=54, fat_g=6),
                    FoodItem(name="milk", quantity="250 ml", kcal=150, protein_g=8,
                             carbs_g=12, fat_g=8),
                    FoodItem(name="banana", quantity="1 piece", kcal=70, protein_g=1,
                             carbs_g=18, fat_g=0)]),
        Meal(name="Lunch", kcal=720, protein_g=60, carbs_g=80, fat_g=18,
             items=[FoodItem(name="lentils", quantity="200 g", kcal=230, protein_g=18,
                             carbs_g=40, fat_g=1),
                    FoodItem(name="tofu", quantity="200 g", kcal=290, protein_g=35,
                             carbs_g=6, fat_g=17),
                    FoodItem(name="rice", quantity="150 g", kcal=200, protein_g=4,
                             carbs_g=44, fat_g=0)]),
        Meal(name="Dinner", kcal=600, protein_g=55, carbs_g=55, fat_g=18,
             items=[FoodItem(name="paneer", quantity="120 g", kcal=320, protein_g=22,
                             carbs_g=4, fat_g=25),
                    FoodItem(name="spinach", quantity="150 g", kcal=35, protein_g=4,
                             carbs_g=5, fat_g=1),
                    FoodItem(name="rice", quantity="120 g", kcal=160, protein_g=3,
                             carbs_g=35, fat_g=0)]),
        Meal(name="Snack", kcal=214, protein_g=32, carbs_g=10, fat_g=5,
             items=[FoodItem(name="greek yogurt", quantity="200 g", kcal=130, protein_g=20,
                             carbs_g=8, fat_g=4)]),
    ]


def _expensive_plan() -> NutritionPlan:
    """Round-0 diet: premium high-protein veg groceries that blow the ₹1500/week budget."""
    return NutritionPlan(
        macros=_PLACEHOLDER_MACROS,
        daily_meals=_demo_meals(),
        weekly_grocery_list=[
            FoodItem(name="paneer", quantity="2 kg", kcal=0, protein_g=0, carbs_g=0, fat_g=0),
            FoodItem(name="tofu", quantity="2 kg", kcal=0, protein_g=0, carbs_g=0, fat_g=0),
            FoodItem(name="lentils", quantity="1 kg", kcal=0, protein_g=0, carbs_g=0, fat_g=0),
            FoodItem(name="oats", quantity="1 kg", kcal=0, protein_g=0, carbs_g=0, fat_g=0),
            FoodItem(name="spinach", quantity="1 kg", kcal=0, protein_g=0, carbs_g=0, fat_g=0),
        ],
        supplements=["whey protein"],
        satisfies_constraints=True,
        constraint_notes=["High-protein vegetarian; excludes peanuts (allergy) and mushroom."],
        assumptions=["Representative one-day diet; scale portions across the week."],
    )


def _cheaper_plan() -> NutritionPlan:
    """Round-1 diet after Budget's revision: cheaper protein sources, drops the whey supplement."""
    return NutritionPlan(
        macros=_PLACEHOLDER_MACROS,
        daily_meals=_demo_meals(),
        weekly_grocery_list=[
            FoodItem(name="lentils", quantity="2 kg", kcal=0, protein_g=0, carbs_g=0, fat_g=0),
            FoodItem(name="tofu", quantity="1 kg", kcal=0, protein_g=0, carbs_g=0, fat_g=0),
            FoodItem(name="oats", quantity="1 kg", kcal=0, protein_g=0, carbs_g=0, fat_g=0),
            FoodItem(name="rice", quantity="1.5 kg", kcal=0, protein_g=0, carbs_g=0, fat_g=0),
            FoodItem(name="spinach", quantity="0.5 kg", kcal=0, protein_g=0, carbs_g=0, fat_g=0),
            FoodItem(name="milk", quantity="2 L", kcal=0, protein_g=0, carbs_g=0, fat_g=0),
        ],
        supplements=[],
        satisfies_constraints=True,
        constraint_notes=["Swapped paneer/whey for lentils+tofu to fit the budget while keeping "
                          "protein ≥ the medical floor."],
        assumptions=["Cheaper protein sources preserve the protein target."],
    )


# Conditions that escalate to a "consult a professional first" plan (resolver short-circuits).
_RED_FLAG_KEYWORDS = (
    "chest pain", "uncontrolled", "unstable angina", "angina", "recent surgery",
    "post-surgery", "pregnan", "eating disorder", "stroke", "shortness of breath",
)


def _demo_constraints(text: str) -> MedicalConstraints:
    """Build constraints from the conditions named in the prompt (so seeded profiles differ).

    Knee → forbidden high-impact movements; (managed) hypertension → sodium/intensity caps; a
    red-flag symptom → requires_professional (the Resolver then refuses to optimize).
    """
    knee = "knee" in text
    hypertension = "hypertension" in text or "blood pressure" in text
    red_flag = any(k in text for k in _RED_FLAG_KEYWORDS)

    forbidden: list[str] = []
    flags: list[MedicalFlag] = []
    required_nutrients = ["fiber"]
    max_sodium: float | None = None
    max_intensity: str | None = None
    max_hr: float | None = None

    if knee:
        forbidden = ["box jumps", "deep squats", "running", "high-impact plyometrics"]
        flags.append(MedicalFlag(condition="knee injury", severity=Severity.hard_limit,
                                 rationale="Avoid high-impact loading and deep knee flexion."))
    if hypertension:
        max_sodium, max_intensity, max_hr = 1500.0, "moderate (RPE <= 6)", 70.0
        required_nutrients.append("potassium")
        flags.append(MedicalFlag(condition="hypertension", severity=Severity.caution,
                                 rationale="Cap sodium and training intensity; monitor BP."))
    if red_flag:
        flags.append(MedicalFlag(condition="red-flag symptom", severity=Severity.red_flag,
                                 rationale="Needs medical clearance before any plan."))

    return MedicalConstraints(
        max_added_sugar_g=25.0, max_sodium_mg=max_sodium, max_saturated_fat_g=20.0,
        min_protein_g_per_kg=1.6,
        excluded_foods=[], required_nutrients=required_nutrients,
        forbidden_movements=forbidden,
        max_intensity=max_intensity, requires_warmup=True, max_heart_rate_pct=max_hr,
        requires_professional=red_flag,
        flags=flags,
        required_disclaimers=[],  # the Medical Risk agent adds the standard disclaimer
    )


def _demo_fitness() -> FitnessPlan:
    """A knee-safe, hypertension-aware 4-day program (no forbidden moves). Burn is overridden."""
    return FitnessPlan(
        weekly_schedule=[
            WorkoutDay(day_label="Mon", focus="Upper (push)", exercises=[
                Exercise(name="Warm-up: arm circles + band pull-aparts", duration_min=8),
                Exercise(name="Dumbbell Bench Press", sets=3, reps="8-12", intensity="RPE 6"),
                Exercise(name="Seated Dumbbell Shoulder Press", sets=3, reps="10-12"),
            ]),
            WorkoutDay(day_label="Tue", focus="Lower (knee-safe)", exercises=[
                Exercise(name="Warm-up: stationary cycling", duration_min=8),
                Exercise(name="Glute Bridge", sets=3, reps="12-15"),
                Exercise(name="Seated Leg Curl (light)", sets=3, reps="12", intensity="RPE 6"),
            ]),
            WorkoutDay(day_label="Thu", focus="Upper (pull)", exercises=[
                Exercise(name="Lat Pulldown", sets=3, reps="10-12"),
                Exercise(name="Seated Cable Row", sets=3, reps="10-12"),
            ]),
            WorkoutDay(day_label="Sat", focus="Zone 2 conditioning", exercises=[
                Exercise(name="Stationary Cycling (Zone 2)", duration_min=30,
                         intensity="≤70% HRmax"),
            ]),
        ],
        days_per_week=4, est_weekly_kcal_burn=0.0,  # overridden by fitness_calc
        equipment_needed=["dumbbells"],
        progression="Add 1 rep/set weekly; keep all work at RPE ≤ 6 and HR ≤ 70% max.",
        satisfies_constraints=True,
        constraint_notes=["No box jumps/running/deep squats (knee); intensity capped (BP)."],
        assumptions=["Uses owned dumbbells + a stationary bike for low-impact cardio."],
    )


class ScriptedProvider(LLMProvider):
    """Deterministic, offline provider. Dispatches canned structured output by response_model."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings

    async def complete(
        self,
        messages: list[dict],
        *,
        tier: str = "strong",
        tools: list[dict] | None = None,
        response_model: type[T] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        if response_model is None:
            return LLMResponse(text="", parsed=None)

        name = response_model.__name__
        text = " ".join(
            str(m.get("content", "")) for m in messages if m.get("role") == "user"
        ).lower()

        if name == "MedicalConstraints":
            return LLMResponse(text="", parsed=_demo_constraints(text))
        if name == "NutritionPlan":
            # A revision request in the prompt = a refinement round → return the cheaper diet.
            refining = "revision request" in text or "cut weekly" in text
            return LLMResponse(text="", parsed=_cheaper_plan() if refining else _expensive_plan())
        if name == "FitnessPlan":
            return LLMResponse(text="", parsed=_demo_fitness())

        # Unknown schema: no canned answer (the deterministic agents don't call the LLM anyway).
        return LLMResponse(text="", parsed=None)
