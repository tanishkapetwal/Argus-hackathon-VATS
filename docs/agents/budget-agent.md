# 💰 Budget Agent

## 1. Identity
- **Registry name:** `budget`
- **Purpose:** Cost the proposed plan (groceries + supplements + gym/equipment), compare to the
  user's weekly budget, and — when over — issue **targeted revision requests** that push
  Nutrition and Fitness toward affordable alternatives without breaking safety.
- **Model tier:** strong for the cut-suggestion reasoning; pricing comes from tools.

## 2. Why this agent exists
A medically-sound, well-programmed plan the user can't afford is a failed recommendation.
Costing is its own skill — mapping a grocery list and equipment needs to real prices, finding
where the money goes, and proposing substitutions that preserve macros and safety. It's also
the agent that creates one of the most visible **interdependency edges**: its
`RevisionRequest`s force Nutrition/Fitness to actually change their outputs.

## 3. Inputs
- `profile.budget_weekly`, `profile.currency`.
- `PlanState.nutrition.weekly_grocery_list` + `supplements`.
- `PlanState.fitness.equipment_needed`.
- `PlanState.constraints` (so suggested cuts never violate medical limits, e.g. don't cut below
  `min_protein_g_per_kg`).

## 4. Outputs
- **`BudgetReport`** ([data-models.md](../data-models.md) §5): `estimated_weekly_cost`,
  itemized `breakdown` (with `source`), `within_budget`, `overrun`, `suggested_cuts`, and
  `revision_requests`.
- **Messages / `RevisionRequest`s:** when over budget, targeted asks like
  `RevisionRequest(target_agent="nutrition", constraint="cut weekly grocery cost by ₹450 while keeping protein ≥ Xg", raised_by="budget")`
  or to `fitness` ("replace gym membership with home equipment, one-time ≤ ₹Y amortized").

## 5. Tools
- **`prices`** — grocery/equipment pricing. Real price API where configured; otherwise a
  **seeded local price table** (`USE_SEEDED_PRICES=true`) for a deterministic demo. Each
  `CostLine.source` records which was used.
- `usda` — to normalize food quantities/units when mapping to prices.
- `web_search` — optional, for current local prices (gym membership, equipment) when a real
  price feed isn't available.

## 6. Behavior / algorithm
1. Price the weekly grocery list and supplements (per-unit × quantity), categorizing each line.
2. Amortize one-time fitness costs (equipment) over a sensible horizon and add recurring costs
   (gym membership) → weekly fitness cost.
3. Sum to `estimated_weekly_cost`; compute `overrun = max(0, estimated − budget)`.
4. If within budget: `within_budget=True`, no revision requests (note any easy savings as info).
5. If over budget: identify the biggest cost drivers and propose **constraint-safe** cuts:
   - cheaper protein sources (eggs/legumes/whey vs premium cuts) that keep macros + medical caps,
   - seasonal/local produce swaps,
   - home/bodyweight workout instead of a gym membership,
   and emit `RevisionRequest`s to the responsible agent(s) with concrete targets.
6. Never suggest a cut that violates `MedicalConstraints` (e.g. dropping protein below the
   minimum). If the budget is infeasible even at the safe minimum, report the minimum-feasible
   cost and the gap (the Resolver will present this honestly).

## 7. Prompt design
- **System prompt intent:** "You are a cost optimizer. Price the plan using the tools, find
  where the money goes, and when it's over budget propose specific, macro-preserving,
  medically-safe substitutions. You do not design diets or workouts yourself — you ask the
  Nutrition/Fitness agents to revise, with concrete targets."
- **Structured output:** returns `BudgetReport` including any `revision_requests`.
- Explicitly: respect medical minimums; prefer the user's preferences when choosing cuts.

## 8. Interdependencies
- **Influenced by:** Nutrition (grocery list), Fitness (equipment), Medical Risk (cut floors).
- **Influences:** Nutrition & Fitness (revision requests → they change their plans), Critic
  (which checks a `BUDGET_OVERRUN` was actually resolved), Resolver (final cost story).

## 9. What is lost if removed
The system could output a plan that's medically sound and effective but unaffordable, with no
feedback loop to fix it. You'd lose one of the clearest cross-agent influence edges (Budget →
Nutrition/Fitness revisions) — a major hit to the 40% interdependency score and to real-world
usefulness.

## 10. Extension ideas
- Real grocery APIs (e.g. BigBasket/Instamart-style) keyed to the user's city.
- Cost-per-gram-of-protein optimization as an explicit objective.
- Budget allocation across weeks (bulk-buy amortization).
- Track price volatility / suggest the best week to buy.
