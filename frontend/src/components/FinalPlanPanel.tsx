// Final plan panel: renders the integrated HealthPlan when RUN_COMPLETED arrives
// (docs/trace-view.md §2) — diet, workout, budget, the resolved/open trade-offs, the per-agent
// "what changed and why" contributions, and the disclaimers.

import { AGENT_META } from "../lib/agentMeta";
import type { HealthPlan } from "../lib/types";

function Card({ title, accent, children }: { title: string; accent: string; children: React.ReactNode }) {
  return (
    <div className="glass-soft p-3">
      <h3 className={`mb-2 text-xs font-semibold uppercase tracking-wide ${accent}`}>{title}</h3>
      {children}
    </div>
  );
}

export function FinalPlanPanel({ plan }: { plan: HealthPlan }) {
  const m = plan.nutrition.macros;
  const b = plan.budget;
  const f = plan.fitness;

  return (
    <div className="space-y-4">
      {plan.requires_professional && (
        <div className="rounded-xl border border-amber-400/40 bg-amber-400/10 px-3 py-2 text-sm font-medium text-amber-200">
          ⚠️ Professional referral required — consult a qualified clinician before starting.
        </div>
      )}

      <div>
        <p className="text-sm font-medium text-slate-100">{plan.summary}</p>
        <p className="mt-1 text-xs text-slate-400">{plan.rationale}</p>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <Card title="🥗 Diet" accent="text-emerald-300">
          <p className="text-sm font-semibold text-slate-100">{m.target_kcal.toFixed(0)} kcal/day</p>
          <p className="text-[11px] text-slate-400">
            P{m.protein_g.toFixed(0)} · C{m.carbs_g.toFixed(0)} · F{m.fat_g.toFixed(0)}
            {m.fiber_g != null ? ` · fiber ${m.fiber_g.toFixed(0)}` : ""}
          </p>
          <ul className="mt-2 space-y-1 text-[11px] text-slate-300">
            {plan.nutrition.daily_meals.map((meal, i) => (
              <li key={i} className="flex justify-between gap-2">
                <span className="truncate">{meal.name}</span>
                <span className="shrink-0 text-slate-500">{meal.kcal.toFixed(0)} kcal</span>
              </li>
            ))}
          </ul>
          {plan.nutrition.supplements.length > 0 && (
            <p className="mt-2 text-[10px] text-slate-500">
              Supplements: {plan.nutrition.supplements.join(", ")}
            </p>
          )}
        </Card>

        <Card title="🏋️ Workout" accent="text-sky-300">
          <p className="text-sm font-semibold text-slate-100">
            {f.days_per_week}-day · ~{f.est_weekly_kcal_burn.toFixed(0)} kcal/wk
          </p>
          <ul className="mt-2 space-y-1 text-[11px] text-slate-300">
            {f.weekly_schedule.map((d, i) => (
              <li key={i} className="flex justify-between gap-2">
                <span className="truncate">
                  <span className="font-medium text-slate-200">{d.day_label}</span> · {d.focus}
                </span>
                <span className="shrink-0 text-slate-500">{d.exercises.length} ex</span>
              </li>
            ))}
          </ul>
          {f.equipment_needed.length > 0 && (
            <p className="mt-2 text-[10px] text-slate-500">Equipment: {f.equipment_needed.join(", ")}</p>
          )}
        </Card>

        <Card title="💰 Budget" accent="text-amber-300">
          <p className="text-sm font-semibold text-slate-100">
            {b.currency} {b.estimated_weekly_cost.toFixed(0)}
            <span className="font-normal text-slate-500"> / {b.weekly_budget.toFixed(0)} wk</span>
          </p>
          <p className={`text-[11px] font-medium ${b.within_budget ? "text-emerald-300" : "text-rose-300"}`}>
            {b.within_budget ? "within budget" : `over by ${b.currency} ${b.overrun.toFixed(0)}`}
          </p>
          <ul className="mt-2 max-h-28 space-y-0.5 overflow-auto text-[11px] text-slate-300">
            {b.breakdown.map((c, i) => (
              <li key={i} className="flex justify-between gap-2">
                <span className="truncate">{c.item}</span>
                <span className="shrink-0 text-slate-500">{c.weekly_cost.toFixed(0)}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      {(plan.resolved_conflicts.length > 0 || plan.open_tradeoffs.length > 0) && (
        <div className="grid gap-3 md:grid-cols-2">
          <Card title="Resolved conflicts" accent="text-violet-300">
            {plan.resolved_conflicts.length === 0 ? (
              <p className="text-[11px] text-slate-500">None — converged cleanly.</p>
            ) : (
              <ul className="space-y-1 text-[11px] text-slate-300">
                {plan.resolved_conflicts.map((c, i) => (
                  <li key={i}>
                    <span className="font-medium text-rose-300">{c.type}</span> — {c.description}
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card title="Open trade-offs" accent="text-rose-300">
            {plan.open_tradeoffs.length === 0 ? (
              <p className="text-[11px] text-slate-500">None.</p>
            ) : (
              <ul className="list-disc space-y-1 pl-4 text-[11px] text-slate-300">
                {plan.open_tradeoffs.map((t, i) => <li key={i}>{t}</li>)}
              </ul>
            )}
          </Card>
        </div>
      )}

      <Card title="What each agent contributed" accent="text-indigo-300">
        <ul className="space-y-1.5 text-[11px]">
          {plan.agent_contributions.map((c, i) => (
            <li key={i} className="flex gap-2">
              <span className="shrink-0">{AGENT_META[c.agent]?.icon ?? "•"}</span>
              <span className="text-slate-300">
                <span className="font-medium text-slate-100">{AGENT_META[c.agent]?.label ?? c.agent}:</span>{" "}
                {c.summary}
                {c.changed_due_to.length > 0 && (
                  <span className="text-slate-500">
                    {" "}← changed due to {c.changed_due_to.map((d) => AGENT_META[d]?.label ?? d).join(", ")}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      </Card>

      {plan.disclaimers.length > 0 && (
        <p className="rounded-lg border border-amber-400/20 bg-amber-400/5 px-3 py-2 text-[11px] text-amber-200/80">
          {plan.disclaimers.join(" ")}
        </p>
      )}
    </div>
  );
}
