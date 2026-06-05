# 🩺 Medical Risk Agent

## 1. Identity
- **Registry name:** `medical_risk`
- **Purpose:** Translate the user's medical profile into **hard, machine-usable safety
  constraints** and escalate red-flag conditions. It is the *gate*: it runs first and its
  output bounds every other agent.
- **Model tier:** strong (safety-critical reasoning).

## 2. Why this agent exists
Nutrition and fitness decisions can be actively harmful with the wrong medical context: a high-
impact workout on a torn ACL, a high-sodium diet with hypertension, an aggressive deficit for
someone with an eating-disorder history or on insulin. No other agent has the clinical framing
to spot these, and you don't want the Nutrition or Fitness agent quietly making medical
judgments inside a prompt. Centralizing safety here makes it auditable and consistent, and
keeps the other agents focused on optimization *within* safe bounds.

## 3. Inputs
- `profile.age, sex, weight_kg, height_cm`
- `profile.medical_conditions`, `profile.medications`, `profile.allergies`
- `profile.goal` (to judge whether the goal itself is unsafe for this person)
- Optionally, current public guidelines via `web_search` (e.g. exercise contraindications for a
  condition), with the source recorded in `MedicalFlag.source`.

## 4. Outputs
- **`MedicalConstraints`** (see [data-models.md](../data-models.md) §2): nutrition limits,
  forbidden movements, intensity caps, required nutrients, `requires_professional`, `flags`,
  `required_disclaimers`.
- **Messages:** `MESSAGE_SENT` to `nutrition` and `fitness` carrying the relevant constraints
  (intent `constraint`). These are the gate edges in the trace.
- Allergies from the profile are merged into `excluded_foods` automatically.

## 5. Tools
- `web_search` — to look up condition-specific contraindications/guidelines when the condition
  is non-trivial. Optional; degrade to model knowledge + a stated assumption if it fails.

## 6. Behavior / algorithm
1. Parse each medical condition, medication, and allergy.
2. For each, derive concrete constraints:
   - **Diet:** caps (added sugar, sodium, saturated fat), minimum protein, excluded foods,
     required nutrients.
   - **Fitness:** forbidden movements, max intensity / HR%, mandatory warmup, mobility needs.
3. Classify severity (`info` → `caution` → `hard_limit` → `red_flag`).
4. If **any red flag** (e.g. uncontrolled hypertension, chest pain, pregnancy complications,
   recent surgery, eating-disorder history with a fat-loss goal), set
   `requires_professional = True` and add an explicit escalation disclaimer. Downstream, the
   Resolver will *refer out rather than optimize*.
5. Always add the standard "informational, not medical advice; consult a professional"
   disclaimer to `required_disclaimers`.
6. Emit constraints into `PlanState.constraints` and send constraint messages to Nutrition and
   Fitness.

## 7. Prompt design
- **System prompt intent:** "You are a cautious clinical-safety reviewer. You do NOT design
  diets or workouts. You convert this person's medical profile into explicit constraints and
  flags. When in doubt, be conservative and escalate. Never relax a limit for convenience,
  cost, or goal speed."
- **Structured output:** the model returns `MedicalConstraints` (validated by Pydantic). Numeric
  limits must be concrete numbers, not prose.
- Include the safety priority rule: medical limits override budget and goal aggressiveness.

## 8. Interdependencies
- **Influences:** Nutrition (diet limits), Fitness (movement/intensity limits), Critic (checks
  others against these constraints), Resolver (red-flag escalation, disclaimers).
- **Influenced by:** only the user profile (it runs first). It does not get revised by others —
  its constraints are inviolable. If a downstream agent *can't* satisfy a constraint, that's a
  `Conflict` the Critic raises and the Resolver presents — the constraint never bends.

## 9. What is lost if removed
The system would happily produce diets and workouts that are unsafe for the user's actual
medical situation, with no one checking. You lose the entire safety floor — the plan might be
optimal on paper and dangerous in practice. This is the agent whose removal is most clearly
catastrophic, which makes it a strong talking point for "what's lost if an agent is removed."

## 10. Extension ideas
- Pull from a structured drug-interaction or contraindication API instead of web search.
- Add a vitals input (BP, HbA1c, resting HR) for sharper, quantitative limits.
- Region/age-specific guideline packs.
