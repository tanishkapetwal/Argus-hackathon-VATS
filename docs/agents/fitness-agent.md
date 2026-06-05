# 🏋️ Fitness Agent

## 1. Identity
- **Registry name:** `fitness`
- **Purpose:** Design a **weekly workout plan** matched to the user's goal, available
  days/equipment, and medical limits, and estimate its **calorie burn** so the diet and
  training stay in energy balance.
- **Model tier:** strong (program design + safe exercise selection).

## 2. Why this agent exists
Exercise programming is a distinct expertise from nutrition: choosing a split, volume,
intensity, and progression for a goal, while routing around injuries and intensity caps. Its
**energy estimate is a hard input to the Nutrition agent** — without it, the diet's deficit/
surplus is guesswork. Separating it from Nutrition lets both reason deeply and forces the
explicit handshake that makes the plan coherent.

## 3. Inputs
- `profile` (goal, activity_level, `days_per_week`, `session_minutes`, `equipment_access`,
  weight — needed for burn estimates).
- `PlanState.constraints` (Medical Risk): `forbidden_movements`, `max_intensity`,
  `max_heart_rate_pct`, `requires_warmup`.
- From Nutrition via the **calorie handshake**: `target_kcal` / goal rate (so volume matches
  what the diet can recover from).
- Any `RevisionRequest` routed to it (e.g. Budget: "drop the gym, go home-equipment"; Critic:
  `RECOVERY_RISK` / `ENERGY_IMBALANCE`).

## 4. Outputs
- **`FitnessPlan`** ([data-models.md](../data-models.md) §4): weekly schedule (days, focus,
  exercises with sets/reps/intensity), `est_weekly_kcal_burn`, `equipment_needed` (for Budget),
  `progression`, `satisfies_constraints` + notes.
- **Messages:** calorie-handshake `AgentMessage` to/from `nutrition` (intent
  `calorie_handshake`, payload e.g. `{"est_weekly_kcal_burn": 2800}`).

## 5. Tools
- `web_search` — optional, for current exercise guidance or safe alternatives for a flagged
  condition. Degrade to model knowledge if unavailable.
- (Burn estimation uses standard MET-based math; keep it as a small helper so numbers are
  consistent. If you prefer, expose it as a deterministic tool like macros.)

## 6. Behavior / algorithm
1. Choose a training **split** appropriate to `days_per_week` and goal (e.g. full-body 3×,
   upper/lower 4×, push/pull/legs).
2. Select exercises consistent with `equipment_access` and **medical constraints** — never
   include a `forbidden_movement`; respect `max_intensity`/HR caps; include a warmup if required;
   substitute safe alternatives (e.g. swap box jumps → cycling for a knee flag).
3. Set volume/intensity/progression for the goal (hypertrophy rep ranges, Zone 2 for endurance,
   etc.), keeping recovery realistic for what the diet supports.
4. Estimate `est_weekly_kcal_burn` (MET × bodyweight × duration, summed across sessions).
5. **Calorie handshake** with Nutrition: share the burn; if intake−burn is outside the goal's
   safe rate, either adjust volume or message Nutrition to adjust intake. Converge before
   returning.
6. Set `equipment_needed` for Budget. Self-check `satisfies_constraints`.
7. On a `RevisionRequest`: e.g. Budget says "no gym budget" → rebuild with home/bodyweight
   equipment; Critic says `RECOVERY_RISK` → reduce volume/frequency. Explain the change.

## 7. Prompt design
- **System prompt intent:** "You are an exercise physiologist / strength coach. Design a safe,
  goal-appropriate weekly program using only allowed movements and available equipment. You
  must respect every medical constraint exactly and keep training recoverable given the diet's
  calorie target. Provide an honest weekly calorie-burn estimate."
- **Structured output:** returns `FitnessPlan`.
- Explicitly: defer medical limits to the constraints (don't override), and respond to Budget's
  equipment revisions rather than ignoring cost.

## 8. Interdependencies
- **Influenced by:** Medical Risk (movement/intensity limits), Nutrition (calorie handshake),
  Budget (`RevisionRequest` on equipment/gym), Critic (`Conflict` → revision).
- **Influences:** Nutrition (burn → intake), Budget (equipment to price), Resolver (final
  workout).

## 9. What is lost if removed
No workout half of the plan, and — just as important — no calorie-burn input, so the diet's
deficit/surplus becomes unanchored and the energy-balance handshake disappears. The plan would
no longer be a coherent body-composition strategy, just a meal plan.

## 10. Extension ideas
- Periodization across the full `timeframe_weeks` (mesocycles, deloads).
- Wearable integration (real HR/steps to refine burn).
- Form-cue/video links per exercise.
- A mobility/rehab sub-module for flagged injuries.
