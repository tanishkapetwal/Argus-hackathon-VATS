"""🩺 Medical Risk Agent — spec: docs/agents/medical-risk-agent.md. Build-plan task 3.1.

Gate agent: runs first, turns the medical profile into hard MedicalConstraints + red-flag
escalation. Its output bounds every downstream agent and is never revised by them.

LLM (strong tier) produces the clinical constraints as structured output; deterministic code
then enforces the inviolable bits: allergies are merged into excluded_foods and the standard
"not medical advice" disclaimer is always present. Constraint messages are sent to nutrition
and fitness — the gate edges in the trace.
"""
from __future__ import annotations

from app.core.agent_names import FITNESS, MEDICAL_RISK, NUTRITION, STANDARD_DISCLAIMER
from app.core.base_agent import AgentContext, AgentResult, BaseAgent
from app.core.registry import register
from app.schemas import AgentMessage, MedicalConstraints

_SYSTEM = (
    "You are a cautious clinical-safety reviewer. You do NOT design diets or workouts. You "
    "convert this person's medical profile into explicit, machine-usable constraints and flags. "
    "Return concrete numbers for any limit (grams, mg, RPE, HR%), not prose. Classify each flag's "
    "severity as info | caution | hard_limit | red_flag. If anything is a genuine red flag "
    "(e.g. uncontrolled hypertension, chest pain, recent surgery, pregnancy complications, an "
    "eating-disorder history with a fat-loss goal), set requires_professional=true. When in "
    "doubt, be conservative and escalate. Medical limits override budget and goal speed — never "
    "relax a limit for convenience."
)


def _user_prompt(profile) -> str:
    return (
        "Derive medical constraints for this person.\n"
        f"- age: {profile.age}, sex: {profile.sex.value}\n"
        f"- height_cm: {profile.height_cm}, weight_kg: {profile.weight_kg}\n"
        f"- goal: {profile.goal.value}\n"
        f"- medical_conditions: {profile.medical_conditions or 'none stated'}\n"
        f"- medications: {profile.medications or 'none stated'}\n"
        f"- allergies: {profile.allergies or 'none stated'}\n"
        "Set diet caps (added sugar, sodium, saturated fat), min protein per kg, excluded foods, "
        "required nutrients; and fitness limits (forbidden_movements, max_intensity, "
        "max_heart_rate_pct, requires_warmup). Add required_disclaimers as needed."
    )


@register(MEDICAL_RISK)
class MedicalRiskAgent(BaseAgent):
    tier = "strong"
    tools = ["web_search"]
    output_schema = MedicalConstraints

    async def _run(self, ctx: AgentContext) -> AgentResult:
        p = ctx.profile
        resp = await ctx.llm.complete(
            [{"role": "system", "content": _SYSTEM},
             {"role": "user", "content": _user_prompt(p)}],
            tier=self.tier, response_model=MedicalConstraints, max_tokens=2048,
        )
        constraints: MedicalConstraints | None = resp.parsed
        if constraints is None:
            raise RuntimeError("Medical Risk Agent received no structured constraints from the LLM")

        # --- inviolable deterministic enforcement (never left to the LLM) ---
        # Allergies are excluded foods, full stop.
        merged = list(dict.fromkeys([*constraints.excluded_foods, *p.allergies]))
        constraints.excluded_foods = merged
        # The standard disclaimer is always present.
        if STANDARD_DISCLAIMER not in constraints.required_disclaimers:
            constraints.required_disclaimers = [
                STANDARD_DISCLAIMER, *constraints.required_disclaimers
            ]

        # --- gate edges: send the relevant slice to each specialist ---
        to_nutrition = AgentMessage(
            sender=MEDICAL_RISK, recipient=NUTRITION, intent="constraint",
            payload={
                "max_added_sugar_g": constraints.max_added_sugar_g,
                "max_sodium_mg": constraints.max_sodium_mg,
                "max_saturated_fat_g": constraints.max_saturated_fat_g,
                "min_protein_g_per_kg": constraints.min_protein_g_per_kg,
                "excluded_foods": constraints.excluded_foods,
                "required_nutrients": constraints.required_nutrients,
            },
            text="Diet must respect these medical caps and exclusions.",
        )
        to_fitness = AgentMessage(
            sender=MEDICAL_RISK, recipient=FITNESS, intent="constraint",
            payload={
                "forbidden_movements": constraints.forbidden_movements,
                "max_intensity": constraints.max_intensity,
                "max_heart_rate_pct": constraints.max_heart_rate_pct,
                "requires_warmup": constraints.requires_warmup,
            },
            text="Workout must avoid forbidden movements and respect intensity limits.",
        )
        return AgentResult(output=constraints, messages=[to_nutrition, to_fitness])

    def _output_summary(self, output: MedicalConstraints) -> str:
        n_hard = sum(1 for f in output.flags if f.severity.value == "hard_limit")
        n_red = sum(1 for f in output.flags if f.severity.value == "red_flag")
        tag = " · RED FLAG → refer out" if output.requires_professional else ""
        return f"medical_risk: {len(output.flags)} flags ({n_hard} hard, {n_red} red){tag}"
