"""🏋️ Fitness Agent — spec: docs/agents/fitness-agent.md. Build-plan task 3.3.

Designs the weekly workout within medical limits + available equipment, estimates weekly
calorie burn (via the deterministic fitness_calc tool — never the LLM), and completes the
calorie handshake with Nutrition.

The LLM designs the program (split, exercise selection, progression); the BURN NUMBER comes
from MET-based math (same "math is a tool, not the LLM" principle as macros.py) so the
energy-balance handshake is consistent and defensible. Deterministic code then enforces the
inviolable bit: a forbidden movement that slips into the plan flips satisfies_constraints so the
Critic catches it.
"""
from __future__ import annotations

from app.core.agent_names import FITNESS, NUTRITION
from app.core.base_agent import AgentContext, AgentResult, BaseAgent
from app.core.registry import register
from app.schemas import AgentMessage, FitnessPlan, Goal, TraceEventType

_SYSTEM = (
    "You are an exercise physiologist / strength coach. Design a safe, goal-appropriate weekly "
    "program using ONLY allowed movements and available equipment. You must respect every "
    "medical constraint exactly — never include a forbidden movement, never exceed the intensity "
    "cap, include a warmup when required, and substitute safe alternatives (e.g. swap box jumps "
    "for cycling on a knee flag). Keep training recoverable given the diet's calorie target. "
    "Defer medical judgments to the given constraints (don't re-litigate them) and respond to "
    "Budget's equipment revisions rather than ignoring cost. Provide an honest weekly program; "
    "the calorie-burn number is computed separately by a calculator — don't invent it."
)

# Representative MET by goal -> training style (compendium ballpark; see tools/fitness_calc.py).
_MET_BY_GOAL: dict[Goal, float] = {
    Goal.fat_loss: 6.0,        # circuit / mixed conditioning
    Goal.muscle_gain: 5.0,     # hypertrophy/strength
    Goal.maintenance: 6.0,
    Goal.general_health: 6.0,
    Goal.endurance: 8.0,       # Zone 2 / steady cardio bias
}


def _user_prompt(ctx: AgentContext) -> str:
    p = ctx.profile
    c = ctx.state.constraints
    parts = [
        "Design a weekly workout plan for this person.",
        f"- goal: {p.goal.value}, activity_level: {p.activity_level.value}",
        f"- days_per_week: {p.days_per_week or 'choose a sensible default'}, "
        f"session_minutes: {p.session_minutes or 45}",
        f"- equipment_access: {p.equipment_access or 'bodyweight only'}",
        f"- bodyweight_kg: {p.weight_kg}",
    ]
    if c is not None:
        parts += [
            f"- forbidden_movements (NEVER include): {c.forbidden_movements or 'none'}",
            f"- max_intensity: {c.max_intensity or 'no explicit cap'}, "
            f"max_heart_rate_pct: {c.max_heart_rate_pct}",
            f"- requires_warmup: {c.requires_warmup}",
        ]
    if ctx.state.nutrition is not None:
        m = ctx.state.nutrition.macros
        parts.append(
            f"- Nutrition set a {m.target_kcal:.0f} kcal/day target (TDEE {m.tdee_kcal:.0f}); "
            "size training volume so intake−burn stays at a safe rate for the goal."
        )
    revisions = [r for r in ctx.state.revision_requests if r.target_agent == FITNESS]
    if revisions:
        parts.append("Apply these revision requests:")
        parts += [f"  - {r.constraint} (from {r.raised_by}: {r.reason})" for r in revisions]
    parts.append(
        "Return weekly_schedule (each day: day_label, focus, exercises with sets/reps/intensity), "
        "days_per_week, equipment_needed (for the Budget agent), progression, "
        "satisfies_constraints, and constraint_notes. Do NOT fill est_weekly_kcal_burn — it is "
        "computed deterministically."
    )
    return "\n".join(parts)


@register(FITNESS)
class FitnessAgent(BaseAgent):
    tier = "strong"
    tools = ["fitness_calc", "web_search"]
    output_schema = FitnessPlan

    async def _run(self, ctx: AgentContext) -> AgentResult:
        p = ctx.profile

        # 1) LLM designs the program (split, exercises, progression) within the constraints.
        resp = await ctx.llm.complete(
            [{"role": "system", "content": _SYSTEM},
             {"role": "user", "content": _user_prompt(ctx)}],
            tier=self.tier, response_model=FitnessPlan, max_tokens=4096,
        )
        plan: FitnessPlan | None = resp.parsed
        if plan is None:
            raise RuntimeError("Fitness Agent received no structured plan from the LLM")

        # 2) Deterministic weekly burn — the LLM never computes this.
        days = plan.days_per_week or p.days_per_week or 3
        plan.days_per_week = days
        session = p.session_minutes or 45
        met = _MET_BY_GOAL.get(p.goal, 6.0)
        weekly_burn = ctx.tools.fitness_calc(
            weight_kg=p.weight_kg, days_per_week=days, session_minutes=session, met=met,
        )
        plan.est_weekly_kcal_burn = weekly_burn
        # Spread the weekly burn across the scheduled days so per-day numbers are consistent.
        n_days = len(plan.weekly_schedule) or days
        if plan.weekly_schedule:
            per_day = round(weekly_burn / n_days, 1)
            for day in plan.weekly_schedule:
                day.est_kcal_burn = per_day
        await ctx.emit(
            TraceEventType.TOOL_CALLED, agent=self.name, round=ctx.round,
            summary=f"fitness_calc → {weekly_burn:.0f} kcal/week "
                    f"({days}×{session}min @ MET {met})",
            payload={"tool": "fitness_calc", "weekly_kcal_burn": weekly_burn,
                     "days_per_week": days, "session_minutes": session, "met": met},
        )

        # 3) Deterministic constraint self-check (forbidden movements in the schedule).
        self._check_forbidden_movements(ctx, plan)

        # 4) Calorie handshake → Nutrition (influence edge), carrying the burn + implied rate.
        handshake = AgentMessage(
            sender=FITNESS, recipient=NUTRITION, intent="calorie_handshake",
            payload={"est_weekly_kcal_burn": weekly_burn, "days_per_week": days},
            text=self._handshake_text(ctx, weekly_burn),
        )
        return AgentResult(output=plan, messages=[handshake])

    @staticmethod
    def _check_forbidden_movements(ctx: AgentContext, plan: FitnessPlan) -> None:
        c = ctx.state.constraints
        if c is None or not c.forbidden_movements:
            return
        forbidden = [m.lower() for m in c.forbidden_movements]
        offenders = sorted({
            ex.name for day in plan.weekly_schedule for ex in day.exercises
            if any(f in ex.name.lower() for f in forbidden)
        })
        if offenders:
            plan.satisfies_constraints = False
            plan.constraint_notes.append(
                f"WARNING: schedule includes forbidden movements {offenders} — Critic should "
                "flag this."
            )

    def _handshake_text(self, ctx: AgentContext, weekly_burn: float) -> str:
        base = (
            f"Estimated ~{weekly_burn:.0f} kcal/week training burn across "
            f"{ctx.profile.days_per_week or 3} sessions."
        )
        n = ctx.state.nutrition
        if n is None:
            return base + " Set intake so intake−burn matches the goal's safe rate."
        tdee, target = n.macros.tdee_kcal, n.macros.target_kcal
        # Net daily deficit vs maintenance, including average training burn.
        net_daily_deficit = (tdee - target) + (weekly_burn / 7.0)
        implied_kg_per_week = round(net_daily_deficit * 7.0 / 7700.0, 2)
        return (
            f"{base} With your {target:.0f} kcal target that implies ~{implied_kg_per_week:.2f} "
            f"kg/week change. If that exceeds the goal's safe rate, raise intake rather than "
            "cutting recovery."
        )

    def _output_summary(self, output: FitnessPlan) -> str:
        return (f"fitness: {output.days_per_week}-day split, "
                f"~{output.est_weekly_kcal_burn:.0f} kcal/week burn, "
                f"{len(output.equipment_needed)} equipment item(s)")
