# Data models — the typed contracts

Every object that crosses an agent boundary is a **Pydantic v2 model**. This file is the
authoritative schema reference; `backend/app/schemas/` implements it. The reference stubs in
`schemas/` mirror these exactly — keep them in sync.

> **Rule:** agents communicate *only* through these models. No raw strings, no untyped dicts.
> This is what keeps agents decoupled and makes the trace view meaningful.

Field types use Python typing shorthand. `| None` means optional. Enums are listed inline.

## 1. Input — `UserProfile`

What the user submits from the frontend form.

```python
class Sex(str, Enum): male; female; other

class ActivityLevel(str, Enum):
    sedentary; light; moderate; active; very_active   # → TDEE multiplier in macros tool

class Goal(str, Enum):
    fat_loss; muscle_gain; maintenance; general_health; endurance

class UserProfile(BaseModel):
    # body stats
    age: int                      # years
    sex: Sex
    height_cm: float
    weight_kg: float
    activity_level: ActivityLevel

    # objective
    goal: Goal
    target_weight_kg: float | None = None
    timeframe_weeks: int | None = None

    # medical (free-text + structured flags; Medical Risk Agent interprets)
    medical_conditions: list[str] = []     # e.g. ["type 2 diabetes", "knee injury"]
    medications: list[str] = []
    allergies: list[str] = []

    # constraints & preferences
    budget_weekly: float                   # currency-agnostic number
    currency: str = "INR"
    diet_preference: str | None = None     # e.g. "vegetarian", "vegan", "no preference"
    disliked_foods: list[str] = []
    equipment_access: list[str] = []       # e.g. ["dumbbells", "gym membership", "none"]
    days_per_week: int | None = None       # training days available
    session_minutes: int | None = None
    notes: str | None = None
```

## 2. Gate — `MedicalConstraints` (output of Medical Risk Agent)

Hard rules every downstream agent must obey. These are **filters, not suggestions.**

```python
class Severity(str, Enum): info; caution; hard_limit; red_flag

class MedicalFlag(BaseModel):
    condition: str                  # the condition this derives from
    severity: Severity
    rationale: str                  # why it matters
    source: str | None = None       # citation / guideline if from web search

class MedicalConstraints(BaseModel):
    # nutrition limits
    max_added_sugar_g: float | None = None
    max_sodium_mg: float | None = None
    max_saturated_fat_g: float | None = None
    min_protein_g_per_kg: float | None = None
    excluded_foods: list[str] = []          # plus anything from allergies
    required_nutrients: list[str] = []       # e.g. ["iron", "B12"]

    # fitness limits
    forbidden_movements: list[str] = []      # e.g. ["high-impact jumping", "heavy spinal loading"]
    max_intensity: str | None = None         # e.g. "moderate (RPE ≤ 6)"
    requires_warmup: bool = True
    max_heart_rate_pct: float | None = None

    # escalation
    requires_professional: bool = False      # red flag → don't optimize, refer out
    flags: list[MedicalFlag] = []
    required_disclaimers: list[str] = []
```

## 3. Nutrition — `MacroTargets` + `NutritionPlan`

`MacroTargets` comes from the **deterministic** macros tool; `NutritionPlan` wraps it with the
actual diet from the Nutrition Agent.

```python
class MacroTargets(BaseModel):
    bmr_kcal: float                 # Mifflin–St Jeor
    tdee_kcal: float                # bmr × activity multiplier
    target_kcal: float              # goal-adjusted (deficit/surplus, safety-capped)
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None = None
    rationale: str                  # how the numbers were derived (for the trace)

class Meal(BaseModel):
    name: str                       # "Breakfast"
    items: list[FoodItem]
    kcal: float
    protein_g: float; carbs_g: float; fat_g: float

class FoodItem(BaseModel):
    name: str
    quantity: str                   # "150 g", "1 cup"
    kcal: float
    protein_g: float; carbs_g: float; fat_g: float
    fdc_id: int | None = None       # USDA FoodData Central id if sourced from USDA

class NutritionPlan(BaseModel):
    macros: MacroTargets
    daily_meals: list[Meal]         # a representative day (or per-day if it varies)
    weekly_grocery_list: list[FoodItem]   # aggregated quantities for Budget Agent
    supplements: list[str] = []
    satisfies_constraints: bool     # self-check against MedicalConstraints
    constraint_notes: list[str] = []      # how constraints were honored
    assumptions: list[str] = []
```

## 4. Fitness — `FitnessPlan`

```python
class Exercise(BaseModel):
    name: str
    sets: int | None = None
    reps: str | None = None         # "8-12"
    duration_min: int | None = None # for cardio/mobility
    intensity: str | None = None    # "RPE 7", "Zone 2"
    notes: str | None = None

class WorkoutDay(BaseModel):
    day_label: str                  # "Day 1 — Upper"
    focus: str
    exercises: list[Exercise]
    est_kcal_burn: float

class FitnessPlan(BaseModel):
    weekly_schedule: list[WorkoutDay]
    days_per_week: int
    est_weekly_kcal_burn: float     # feeds the calorie handshake with Nutrition
    equipment_needed: list[str]     # feeds the Budget Agent
    progression: str                # how it scales over weeks
    satisfies_constraints: bool
    constraint_notes: list[str] = []
    assumptions: list[str] = []
```

## 5. Budget — `BudgetReport`

```python
class CostLine(BaseModel):
    item: str
    category: str                   # "groceries" | "supplements" | "gym" | "equipment"
    weekly_cost: float
    source: str                     # "usda+price_api" | "seeded" | "web_search"

class BudgetReport(BaseModel):
    currency: str
    weekly_budget: float
    estimated_weekly_cost: float
    breakdown: list[CostLine]
    within_budget: bool
    overrun: float                  # estimated − budget (0 if within)
    suggested_cuts: list[str] = []  # human-readable cut ideas
    revision_requests: list[RevisionRequest] = []   # targeted asks (see §7)
    notes: list[str] = []
```

## 6. Critique — `Conflict` + `Critique`

```python
class ConflictType(str, Enum):
    MEDICAL_VIOLATION; ENERGY_IMBALANCE; BUDGET_OVERRUN
    MACRO_INCOHERENCE; RECOVERY_RISK; MISSING_DISCLAIMER

class Conflict(BaseModel):
    type: ConflictType
    severity: Severity              # reuse Severity enum
    description: str                # what's wrong
    evidence: str                   # the numbers/facts that prove it
    target_agents: list[str]        # who must fix it (agent names)
    suggested_fix: str | None = None

class Critique(BaseModel):
    conflicts: list[Conflict]       # empty list = approved, proceed to Resolver
    overall_assessment: str
    approved: bool                  # True iff no blocking conflicts remain
```

## 7. Revision routing — `RevisionRequest` + `AgentMessage`

```python
class RevisionRequest(BaseModel):
    target_agent: str               # "nutrition" | "fitness" | ...
    reason: str                     # why a revision is needed
    constraint: str                 # the concrete thing to satisfy ("cut weekly cost by ₹400")
    raised_by: str                  # "budget" | "critic"

class AgentMessage(BaseModel):
    """An explicit influence edge between agents — rendered in the trace view."""
    sender: str
    recipient: str                  # agent name, or "all"
    intent: str                     # "calorie_handshake" | "constraint" | "revision" | "info"
    payload: dict                   # small structured payload (e.g. {"target_kcal": 2100})
    text: str                       # human-readable for the trace
```

## 8. Final output — `HealthPlan` (output of Resolver)

The mandated "final recommendation". This is what the user sees.

```python
class AgentContribution(BaseModel):
    agent: str
    summary: str                    # what this agent decided
    changed_due_to: list[str] = []  # which other agents/conflicts changed its output

class HealthPlan(BaseModel):
    profile: UserProfile
    constraints: MedicalConstraints
    nutrition: NutritionPlan
    fitness: FitnessPlan
    budget: BudgetReport

    summary: str                    # the headline recommendation
    rationale: str                  # why this plan, given the trade-offs
    resolved_conflicts: list[Conflict] = []     # what was resolved and how
    open_tradeoffs: list[str] = []  # anything unresolved after max rounds
    agent_contributions: list[AgentContribution]  # "what each agent changed" — demo gold
    requires_professional: bool
    disclaimers: list[str]
    generated_at: datetime
```

## 9. Shared graph state — `PlanState`

Threaded through the LangGraph (see [orchestration.md](orchestration.md) §3).

```python
class PlanState(BaseModel):
    run_id: str
    profile: UserProfile
    constraints: MedicalConstraints | None = None
    nutrition: NutritionPlan | None = None
    fitness: FitnessPlan | None = None
    budget: BudgetReport | None = None
    open_conflicts: list[Conflict] = []
    revision_requests: list[RevisionRequest] = []
    messages: list[AgentMessage] = []          # append-only influence log
    round: int = 0
    final_plan: HealthPlan | None = None
```

## 10. Observability — `TraceEvent`

The event that powers the trace view and the execution log. Full protocol in
[trace-view.md](trace-view.md).

```python
class TraceEventType(str, Enum):
    RUN_STARTED; AGENT_STARTED; AGENT_INPUT; AGENT_OUTPUT
    MESSAGE_SENT; CONFLICT_RAISED; REVISION_REQUESTED
    TOOL_CALLED; AGENT_COMPLETED; ROUND_STARTED; RUN_COMPLETED; ERROR

class TraceEvent(BaseModel):
    run_id: str
    seq: int                        # monotonically increasing per run (ordering)
    type: TraceEventType
    agent: str | None = None        # which agent (if applicable)
    round: int = 0
    timestamp: datetime
    summary: str                    # short human-readable line for the log/UI
    payload: dict = {}              # event-specific structured data (input/output/message/conflict)
    # for MESSAGE_SENT / REVISION_REQUESTED, payload includes sender + recipient → drawn as an edge
```

## Schema-sync checklist (for the builder)

- [ ] Each model above exists in `backend/app/schemas/` with identical field names.
- [ ] Frontend TS types (`frontend/src/lib/types.ts`) mirror `TraceEvent`, `HealthPlan`,
      `UserProfile`, and the plan sub-models.
- [ ] LLM structured-output calls parse into these models (Nutrition/Fitness/Critic/Resolver
      outputs are produced as structured output, validated by Pydantic).
- [ ] `Severity` and agent-name strings are shared constants, not duplicated literals.
