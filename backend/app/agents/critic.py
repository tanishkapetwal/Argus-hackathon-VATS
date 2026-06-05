"""🔍 Critic Agent — spec: docs/agents/critic-agent.md. Build-plan task 3.5.

The adversary. Reads ALL specialist outputs and raises typed Conflicts (the conflict taxonomy
in docs/orchestration.md §5). Does not fix anything — finds problems and routes them.

DETERMINISTIC by design (no LLM — see tests/agent_helpers.NoLLM): every check is exact math or
a structured lookup over the state, so the Critic challenges facts, not guesses. Each conflict
targeting a re-runnable specialist is also turned into a RevisionRequest, so the trace shows the
CONFLICT_RAISED → REVISION_REQUESTED edge that drives the next refinement round.
"""
from __future__ import annotations

from app.core.agent_names import CRITIC, FITNESS, NUTRITION, RESOLVER
from app.core.base_agent import AgentContext, AgentResult, BaseAgent
from app.core.registry import register
from app.schemas import (
    Conflict,
    ConflictType,
    Critique,
    Goal,
    RevisionRequest,
    Severity,
)

_KCAL_PER_KG = 7700.0
_SAFE_WEEKLY_PCT = 0.01          # 1% bodyweight/week (consistent with tools/macros.py)
_RATE_TOLERANCE = 1.10          # allow a 10% margin before flagging an imbalance
_MACRO_KCAL_TOLERANCE = 0.25    # meals may be ±25% of the calorie target before incoherent
_PROTEIN_SHORTFALL = 0.80       # meals must reach ≥80% of the protein target


@register(CRITIC)
class CriticAgent(BaseAgent):
    tier = "strong"
    tools: list[str] = []
    output_schema = Critique

    async def _run(self, ctx: AgentContext) -> AgentResult:
        conflicts: list[Conflict] = []
        conflicts += self._check_medical(ctx)
        conflicts += self._check_energy(ctx)
        conflicts += self._check_budget(ctx)
        conflicts += self._check_macros(ctx)
        conflicts += self._check_recovery(ctx)
        conflicts += self._check_disclaimer(ctx)

        critique = Critique(
            conflicts=conflicts,
            approved=not conflicts,
            overall_assessment=self._assessment(ctx, conflicts),
        )
        revisions = self._to_revisions(conflicts)
        return AgentResult(output=critique, conflicts=conflicts, revisions=revisions)

    # ---- 1. MEDICAL_VIOLATION ----------------------------------------------
    def _check_medical(self, ctx: AgentContext) -> list[Conflict]:
        c, n, f = ctx.state.constraints, ctx.state.nutrition, ctx.state.fitness
        out: list[Conflict] = []
        if c is not None and n is not None and c.excluded_foods:
            excluded = [e.lower() for e in c.excluded_foods]
            offenders = sorted({
                item.name for meal in n.daily_meals for item in meal.items
                if any(e in item.name.lower() for e in excluded)
            })
            if offenders or not n.satisfies_constraints:
                out.append(Conflict(
                    type=ConflictType.MEDICAL_VIOLATION, severity=Severity.hard_limit,
                    description="Diet includes medically excluded foods or fails its constraint "
                                "self-check.",
                    evidence=f"excluded_foods={c.excluded_foods}; "
                             f"offenders={offenders or 'flagged'}",
                    target_agents=[NUTRITION],
                    suggested_fix="Remove the excluded foods and substitute compliant ones.",
                ))
        if c is not None and f is not None and c.forbidden_movements:
            forbidden = [m.lower() for m in c.forbidden_movements]
            offenders = sorted({
                ex.name for day in f.weekly_schedule for ex in day.exercises
                if any(m in ex.name.lower() for m in forbidden)
            })
            if offenders or not f.satisfies_constraints:
                out.append(Conflict(
                    type=ConflictType.MEDICAL_VIOLATION, severity=Severity.hard_limit,
                    description="Workout includes a forbidden movement or fails its constraint "
                                "self-check.",
                    evidence=f"forbidden_movements={c.forbidden_movements}; "
                             f"offenders={offenders or 'flagged'}",
                    target_agents=[FITNESS],
                    suggested_fix="Replace forbidden movements with safe alternatives.",
                ))
        return out

    # ---- 2. ENERGY_IMBALANCE -----------------------------------------------
    def _check_energy(self, ctx: AgentContext) -> list[Conflict]:
        n, f = ctx.state.nutrition, ctx.state.fitness
        if n is None or f is None:
            return []
        weight = ctx.profile.weight_kg
        safe_weekly_kg = _SAFE_WEEKLY_PCT * weight
        burn_per_day = f.est_weekly_kcal_burn / 7.0
        net = n.macros.target_kcal - burn_per_day
        deficit = n.macros.tdee_kcal - net                 # >0 = net loss, <0 = net gain
        implied_kg = round(deficit * 7.0 / _KCAL_PER_KG, 2)  # +loss / -gain per week
        goal = ctx.profile.goal
        limit = round(safe_weekly_kg * _RATE_TOLERANCE, 2)

        def conflict(desc: str) -> Conflict:
            return Conflict(
                type=ConflictType.ENERGY_IMBALANCE, severity=Severity.caution,
                description=desc,
                evidence=f"target {n.macros.target_kcal:.0f} kcal − burn {burn_per_day:.0f}/day vs "
                         f"TDEE {n.macros.tdee_kcal:.0f} ⇒ {implied_kg:+.2f} kg/week "
                         f"(safe ≤ {safe_weekly_kg:.2f}).",
                target_agents=[NUTRITION, FITNESS],
                suggested_fix="Adjust intake (preferred) or training volume so the implied rate is "
                              "within the safe range for the goal.",
            )

        if goal == Goal.fat_loss:
            if implied_kg > limit:
                return [conflict(f"Fat-loss deficit too aggressive ({implied_kg:+.2f} kg/week).")]
            if implied_kg < 0:
                return [conflict("Energy surplus during a fat-loss goal (no deficit).")]
        elif goal == Goal.muscle_gain:
            if implied_kg > 0:
                return [conflict(f"Energy deficit during a muscle-gain goal ({implied_kg:+.2f} "
                                 "kg/week loss).")]
        elif goal in (Goal.maintenance, Goal.general_health):
            if abs(implied_kg) > limit:
                return [conflict(f"Energy balance drifts from maintenance ({implied_kg:+.2f} "
                                 "kg/week).")]
        return []

    # ---- 3. BUDGET_OVERRUN -------------------------------------------------
    def _check_budget(self, ctx: AgentContext) -> list[Conflict]:
        b = ctx.state.budget
        if b is None or b.within_budget:
            return []
        targets = sorted({r.target_agent for r in b.revision_requests}) or [NUTRITION]
        return [Conflict(
            type=ConflictType.BUDGET_OVERRUN, severity=Severity.caution,
            description=f"Plan exceeds the weekly budget by {b.currency} {b.overrun:.0f}.",
            evidence=f"estimated {b.currency} {b.estimated_weekly_cost:.0f} vs budget "
                     f"{b.currency} {b.weekly_budget:.0f}.",
            target_agents=targets,
            suggested_fix="Apply Budget's revision requests (cheaper protein / home workout) "
                          "without breaking medical floors.",
        )]

    # ---- 4. MACRO_INCOHERENCE ----------------------------------------------
    def _check_macros(self, ctx: AgentContext) -> list[Conflict]:
        n = ctx.state.nutrition
        if n is None or not n.daily_meals:
            return []
        total_kcal = sum(m.kcal for m in n.daily_meals)
        total_protein = sum(m.protein_g for m in n.daily_meals)
        target_kcal = n.macros.target_kcal
        target_protein = n.macros.protein_g
        if target_kcal > 0 and abs(total_kcal - target_kcal) / target_kcal > _MACRO_KCAL_TOLERANCE:
            return [Conflict(
                type=ConflictType.MACRO_INCOHERENCE, severity=Severity.caution,
                description="Meal calories do not sum to the calorie target.",
                evidence=f"meals total {total_kcal:.0f} kcal vs target {target_kcal:.0f}.",
                target_agents=[NUTRITION],
                suggested_fix="Re-balance portions so the meals sum to the target calories.",
            )]
        if target_protein > 0 and total_protein < _PROTEIN_SHORTFALL * target_protein:
            return [Conflict(
                type=ConflictType.MACRO_INCOHERENCE, severity=Severity.caution,
                description="Protein target is not reachable from the chosen meals.",
                evidence=f"meals provide {total_protein:.0f} g protein vs target "
                         f"{target_protein:.0f} g.",
                target_agents=[NUTRITION],
                suggested_fix="Add higher-protein foods to reach the protein target.",
            )]
        return []

    # ---- 5. RECOVERY_RISK --------------------------------------------------
    def _check_recovery(self, ctx: AgentContext) -> list[Conflict]:
        n, f = ctx.state.nutrition, ctx.state.fitness
        if n is None or f is None:
            return []
        # High frequency on a meaningful deficit during fat loss → under-recovery risk.
        aggressive_deficit = n.macros.target_kcal < n.macros.tdee_kcal * 0.85
        if ctx.profile.goal == Goal.fat_loss and f.days_per_week >= 6 and aggressive_deficit:
            return [Conflict(
                type=ConflictType.RECOVERY_RISK, severity=Severity.caution,
                description="Training frequency is high for the recovery the diet supports.",
                evidence=f"{f.days_per_week} sessions/week on a "
                         f"{n.macros.target_kcal:.0f}/{n.macros.tdee_kcal:.0f} kcal deficit.",
                target_agents=[FITNESS],
                suggested_fix="Reduce session frequency/volume or raise intake to aid recovery.",
            )]
        return []

    # ---- 6. MISSING_DISCLAIMER ---------------------------------------------
    def _check_disclaimer(self, ctx: AgentContext) -> list[Conflict]:
        c = ctx.state.constraints
        if c is not None and not c.required_disclaimers:
            return [Conflict(
                type=ConflictType.MISSING_DISCLAIMER, severity=Severity.caution,
                description="No required medical disclaimer is attached.",
                evidence="constraints.required_disclaimers is empty.",
                target_agents=[RESOLVER],
                suggested_fix="Attach the standard 'not medical advice' disclaimer.",
            )]
        return []

    # ---- routing + summary --------------------------------------------------
    @staticmethod
    def _to_revisions(conflicts: list[Conflict]) -> list[RevisionRequest]:
        """Turn each conflict targeting a re-runnable specialist into a RevisionRequest."""
        seen: set[tuple[str, str]] = set()
        revisions: list[RevisionRequest] = []
        for c in conflicts:
            for target in c.target_agents:
                if target not in (NUTRITION, FITNESS):
                    continue
                key = (target, c.type.value)
                if key in seen:
                    continue
                seen.add(key)
                revisions.append(RevisionRequest(
                    target_agent=target, raised_by=CRITIC,
                    reason=f"{c.type.value}: {c.description}",
                    constraint=c.suggested_fix or c.description,
                ))
        return revisions

    def _assessment(self, ctx: AgentContext, conflicts: list[Conflict]) -> str:
        if not conflicts:
            checks = ["medical compliance", "energy balance", "budget", "macro coherence"]
            return (f"Verified {', '.join(checks)} over round {ctx.round}. No conflicts found — "
                    "approved for the Resolver.")
        kinds = ", ".join(sorted({c.type.value for c in conflicts}))
        return f"Found {len(conflicts)} conflict(s) [{kinds}] — routing back for refinement."

    def _output_summary(self, output: Critique) -> str:
        if output.approved:
            return "critic: no conflicts — approved"
        kinds = ", ".join(c.type.value for c in output.conflicts)
        return f"critic: {len(output.conflicts)} conflict(s) — {kinds}"
