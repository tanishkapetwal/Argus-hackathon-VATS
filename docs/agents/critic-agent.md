# 🔍 Critic Agent

## 1. Identity
- **Registry name:** `critic`
- **Purpose:** The adversary. It reads **all** specialist outputs together and hunts for
  cross-agent incoherence and safety violations, emitting typed `Conflict`s that route the plan
  back for refinement. It does **not** fix anything itself — it finds problems.
- **Model tier:** strong (this is the highest-leverage reasoning step).

## 2. Why this agent exists
Each specialist optimizes its own slice and can miss interactions: the diet looks fine, the
workout looks fine, but together they imply an unsafe deficit; or Budget asked for a cut that
Nutrition didn't actually apply; or a medical cap got violated by a food swap. The Critic is
what turns six parallel outputs into a **debate** — it's the single biggest contributor to the
40% "challenge/validate each other" criterion. Separating "find problems" (Critic) from "decide"
(Resolver) keeps each sharp and the trace legible.

## 3. Inputs
- `PlanState.constraints`, `.nutrition`, `.fitness`, `.budget` — the full current state.
- `PlanState.messages` and prior `open_conflicts` — to verify whether earlier revision requests
  were actually addressed.
- `PlanState.round`.

## 4. Outputs
- **`Critique`** ([data-models.md](../data-models.md) §6): `conflicts: list[Conflict]`,
  `overall_assessment`, `approved`. An **empty** conflict list + `approved=True` means "proceed
  to Resolver".
- Each `Conflict` names `target_agents` and (optionally) a `suggested_fix`; these become
  `REVISION_REQUESTED` trace edges back to the responsible agents.

## 5. Tools
- None. The Critic reasons over the structured state. (Determinism matters: where a check is
  pure math — e.g. macros summing to calories, intake−burn vs safe rate — compute it exactly in
  code and feed the result to the Critic, so it challenges facts, not guesses.)

## 6. Behavior / algorithm
Run the **conflict taxonomy** from [orchestration.md](../orchestration.md) §5 over the state:

1. **`MEDICAL_VIOLATION`** — does the diet breach any cap (`max_added_sugar_g`,
   `max_sodium_mg`, etc.) or include an `excluded_food`? Does the workout include a
   `forbidden_movement` or exceed `max_intensity`? Are required disclaimers present?
2. **`ENERGY_IMBALANCE`** — compute `target_kcal − (est_weekly_kcal_burn / 7)`; does the implied
   weekly weight change exceed the safe rate for the goal? Surplus during a cut? Deficit during
   a gain?
3. **`BUDGET_OVERRUN`** — is `estimated_weekly_cost > weekly_budget`, especially after Budget
   already asked for a cut that wasn't applied?
4. **`MACRO_INCOHERENCE`** — do the meals' macros actually sum to the targets? Is the protein
   target reachable from the chosen foods?
5. **`RECOVERY_RISK`** — is training volume too high for the diet's energy availability?
6. **`MISSING_DISCLAIMER`** — is a required medical disclaimer or red-flag escalation absent?

For each issue, emit a `Conflict` with `evidence` (the actual numbers), `severity`, and
`target_agents`. If **nothing** is wrong, return an empty list with `approved=True` and a short
explanation of what it verified (this is a meaningful trace event — the Critic explicitly signs
off).

## 7. Prompt design
- **System prompt intent:** "You are a rigorous reviewer whose job is to find what's wrong, not
  to be agreeable. Check the plan for medical violations, energy imbalance, budget overruns,
  macro incoherence, and recovery risk. Cite concrete evidence (numbers) for every conflict and
  name which agent must fix it. If the plan is genuinely sound, approve it and say why — do not
  invent problems."
- **Structured output:** returns `Critique`.
- Feed it the precomputed deterministic checks (energy balance, macro sums, cost vs budget) so
  its conflicts are grounded.

## 8. Interdependencies
- **Influenced by:** every specialist (it reads all of them) and Medical Risk's constraints.
- **Influences:** Nutrition/Fitness/Budget (revision requests in the loop), and the orchestrator's
  conditional edge (conflicts + round → loop or proceed), and Resolver (which conflicts to
  reconcile).

## 9. What is lost if removed
The single most damaging removal for the *quality of collaboration*. Without the Critic, the six
agents are just parallel producers; nobody catches cross-agent contradictions, so unsafe or
incoherent plans ship silently. You lose the entire "challenge/validate" dynamic that the RFP
weights most heavily, and the refinement loop has nothing to trigger it.

## 10. Extension ideas
- Confidence scoring per conflict; only loop on high-confidence/high-severity ones.
- A learned/rule-based pre-filter so the LLM only adjudicates genuine gray areas.
- Track conflict-resolution history to detect oscillation (A fixes → B breaks → A breaks).
