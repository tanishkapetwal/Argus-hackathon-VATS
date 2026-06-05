// Dry-run of the 90-second demo narrative (build-plan 7.4) against the live backend.
// For each seeded profile it drives a real run, folds the events through deriveView(), prints the
// narrative beats (docs/trace-view.md §4), and asserts the expected story. Run offline with the
// scripted backend. Bundle with esbuild + run with node.

import { DEMO_PROFILES } from "../src/lib/demoProfiles";
import { deriveView } from "../src/lib/traceModel";
import type { TraceEvent, UserProfile } from "../src/lib/types";

const BASE = "http://127.0.0.1:8000";
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
let failures = 0;
function check(cond: unknown, msg: string) {
  console.log(`   ${cond ? "✓" : "✗"} ${msg}`);
  if (!cond) failures++;
}

async function runProfile(profile: UserProfile): Promise<TraceEvent[]> {
  const start = await fetch(`${BASE}/api/plan`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(profile),
  });
  const { run_id } = (await start.json()) as { run_id: string };
  for (let i = 0; i < 60; i++) {
    const data = (await (await fetch(`${BASE}/api/plan/${run_id}`)).json()) as { events: TraceEvent[] };
    if ((data.events ?? []).some((e) => e.type === "RUN_COMPLETED")) return data.events;
    await sleep(200);
  }
  throw new Error("run did not complete in time");
}

async function main() {
  for (const demo of DEMO_PROFILES) {
    const events = await runProfile(demo.profile);
    const view = deriveView(events);
    const plan = view.finalPlan!;
    const summaryOf = (agent: string, round?: number) =>
      events.find((e) => e.type === "AGENT_OUTPUT" && e.agent === agent &&
        (round == null || e.round === round))?.summary ?? "(n/a)";
    const conflicts = events.filter((e) => e.type === "CONFLICT_RAISED").map((e) => e.summary);
    const rounds = events.filter((e) => e.type === "ROUND_STARTED").length;
    const handshakes = view.edges.filter((e) => e.intent === "calorie_handshake").length;

    console.log(`\n══════════ ${demo.label} ══════════`);
    console.log(`  1. 🩺 Medical Risk → ${summaryOf("medical_risk")}`);
    console.log(`     forbidden: [${plan.constraints.forbidden_movements.join(", ") || "none"}]` +
      ` · requires_professional=${plan.requires_professional}`);
    console.log(`  2. 🥗⇄🏋️ Handshake → ${handshakes} calorie_handshake edge(s); ` +
      `diet ${plan.nutrition.macros.target_kcal.toFixed(0)} kcal ↔ ` +
      `${plan.fitness.est_weekly_kcal_burn.toFixed(0)} kcal/wk burn`);
    console.log(`  3. 💰 Budget (round 0) → ${summaryOf("budget", 0)}`);
    console.log(`  4. 🔍 Critic → ${conflicts.length ? conflicts.join(" | ") : "no conflicts — approved"}` +
      ` · refinement rounds: ${rounds}`);
    console.log(`  5. ⚖️ Resolver → ${plan.summary}`);
    if (plan.open_tradeoffs.length) console.log(`     open trade-offs: ${plan.open_tradeoffs.join("; ")}`);
    console.log("     contributions: " +
      plan.agent_contributions.map((c) => c.agent).join(" → "));

    console.log("  assertions:");
    check(view.runStatus === "complete", "run completed");
    if (demo.id === "conflict") {
      check(plan.constraints.forbidden_movements.length > 0, "high-impact movements removed (knee)");
      check(handshakes >= 1, "calorie handshake happened");
      check(conflicts.some((c) => c.includes("BUDGET_OVERRUN")), "budget overrun raised");
      check(rounds >= 1, "a refinement round occurred");
      check(plan.budget.within_budget, "converged within budget");
      check(plan.agent_contributions.length >= 4, "resolver explains each agent's contribution");
    } else if (demo.id === "clean") {
      check(rounds === 0, "no refinement round (fits first time)");
      check(plan.budget.within_budget, "within budget");
      check(conflicts.length === 0, "critic approved with no conflicts");
      check(!plan.requires_professional, "no referral");
    } else if (demo.id === "redflag") {
      check(plan.requires_professional, "escalated to professional referral");
      check(/professional/i.test(plan.summary), "resolver leads with 'consult a professional'");
    }
  }

  console.log(failures === 0 ? "\n✅ NARRATIVE DRY-RUN PASSED" : `\n❌ ${failures} assertion(s) failed`);
  process.exit(failures === 0 ? 0 : 1);
}

main().catch((e) => { console.error(e); process.exit(1); });
