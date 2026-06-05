# 🥗 Nutrition Agent


## 1. Identity
- **Registry name:** `nutrition`
- **Purpose:** Produce **macro targets** (via a deterministic calculator) and a concrete
  **diet plan** that hits those macros, respects the medical constraints and the user's food
  preferences/budget, and stays in calorie balance with the Fitness plan.
- **Model tier:** strong for the diet design; the macro numbers themselves come from a tool.

## 2. Why this agent exists
Translating a goal + body stats into the right calories and macros, then into real foods a
person will actually eat — within medical limits and a budget — is a specialized skill. Crucially,
**the math must be exact** (no hallucinated BMR), and the food choices must be backed by real
nutrient data (USDA), not vibes. Keeping this separate from Fitness lets each be deep; keeping
the macro math in a tool (not the LLM) makes the numbers trustworthy.

## 3. Inputs
- `profile` (age, sex, height, weight, activity, goal, timeframe, diet_preference,
  disliked_foods, allergies, budget).
- `PlanState.constraints` (Medical Risk) — caps and exclusions it must honor.
- From Fitness via the **calorie handshake**: `est_weekly_kcal_burn` (to set an appropriate
  intake for the goal's safe rate).
- Any `RevisionRequest` routed to it (from Budget or Critic) in later rounds.

## 4. Outputs
- **`NutritionPlan`** ([data-models.md](../data-models.md) §3): `MacroTargets`, daily meals,
  an aggregated `weekly_grocery_list` (for Budget), supplements, `satisfies_constraints` +
  `constraint_notes`.
- **Messages:** calorie-handshake `AgentMessage` to/from `fitness` (intent
  `calorie_handshake`, payload e.g. `{"target_kcal": 2100, "goal_rate_kg_per_week": 0.5}`).
- On a revision round, an updated `NutritionPlan` plus a note of what changed and why.

## 5. Tools
- **`macros_calc`** (deterministic, REQUIRED): computes BMR (Mifflin–St Jeor), TDEE
  (activity multiplier), goal-adjusted `target_kcal` (safety-capped deficit/surplus), and the
  protein/carb/fat/fiber split. The agent **must** use this for all numbers — it may not invent
  them. See [tech-stack.md](../tech-stack.md) and `backend/app/tools/macros.py`.
- **`usda`** — USDA FoodData Central lookups to attach real `kcal`/macros (and `fdc_id`) to the
  foods it chooses.

## 6. Behavior / algorithm
1. Call `macros_calc` with the profile (and the goal). Get `MacroTargets`. If the deficit/
   surplus implied by the goal+timeframe exceeds a safe rate, the tool caps it and the agent
   notes that the timeframe was extended for safety.
2. Reconcile with Fitness's burn (calorie handshake): ensure `target_kcal − burn` matches the
   goal's safe rate. If not, adjust intake (preferred) or send a message asking Fitness to
   adjust volume.
3. Apply **medical constraints**: drop `excluded_foods`/allergens, respect sugar/sodium/sat-fat
   caps and `min_protein_g_per_kg`, ensure `required_nutrients` are covered.
4. Apply **preferences**: honor `diet_preference` (veg/vegan/etc.) and avoid `disliked_foods`.
5. Design meals that hit the macros; use `usda` for real nutrient values; aggregate a weekly
   grocery list with quantities (Budget needs this).
6. Self-check: set `satisfies_constraints` and fill `constraint_notes` (how each constraint was
   met). If a constraint is impossible given budget/preferences, say so (the Critic will raise
   a conflict; don't silently violate).
7. On a `RevisionRequest` (e.g. "cut weekly cost ₹400" from Budget, or `ENERGY_IMBALANCE` from
   Critic): adjust foods (cheaper protein, seasonal produce) or macros minimally, preserving
   constraints, and explain the change.

## 7. Prompt design
- **System prompt intent:** "You are a registered-dietitian-style planner. You receive exact
  macro targets from a calculator — never recompute or override them. Build a realistic,
  preference-aware, constraint-compliant diet that hits those macros using real foods. If a
  medical or budget constraint makes the target impossible, surface it; do not violate it."
- **Structured output:** returns `NutritionPlan`. Food nutrient values come from `usda` tool
  results, not free invention.
- Tell it explicitly: defer medical judgments to the constraints (don't re-litigate them) and
  defer cost judgments to Budget (but respond to its revision requests).

## 8. Interdependencies
- **Influenced by:** Medical Risk (hard limits), Fitness (burn → intake), Budget
  (`RevisionRequest`), Critic (`Conflict` → revision).
- **Influences:** Fitness (handshake), Budget (grocery list to price), Resolver (final diet).

## 9. What is lost if removed
No diet, no macro targets — the plan has no nutrition half, and the calorie handshake that keeps
the workout coherent collapses. You also lose the deterministic-math reliability and the real
USDA-backed food data that make the recommendation defensible (25% reasoning score).

## 10. Extension ideas
- Per-day meal variety / weekly rotation instead of one representative day.
- Recipe generation + step-by-step prep.
- Micronutrient sufficiency scoring against RDAs.
- Swap USDA for a region-specific food database (e.g. Indian food composition tables).
