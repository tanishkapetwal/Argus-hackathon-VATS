// Functional check (no browser): drive a real backend run, then fold the streamed events through
// the SAME deriveView() reducer the UI uses and assert the derived view is correct.
// Bundle with the installed esbuild and run with node — see the npm/Bash invocation.

import { deriveView } from "../src/lib/traceModel";
import type { TraceEvent } from "../src/lib/types";

const BASE = "http://127.0.0.1:8000";
const DEMO = {
  age: 34, sex: "male", height_cm: 178, weight_kg: 92, activity_level: "light",
  goal: "fat_loss", target_weight_kg: 78, timeframe_weeks: 12,
  medical_conditions: ["knee injury", "hypertension"], medications: [], allergies: ["peanuts"],
  budget_weekly: 1500, currency: "INR", diet_preference: "high protein, vegetarian",
  disliked_foods: ["mushroom"], equipment_access: ["dumbbells"],
  days_per_week: 4, session_minutes: 45, notes: "wants visible results fast",
};

function assert(cond: unknown, msg: string) {
  if (!cond) throw new Error("FAIL: " + msg);
  console.log("  ✓ " + msg);
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const start = await fetch(`${BASE}/api/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(DEMO),
  });
  const { run_id } = (await start.json()) as { run_id: string };
  console.log("run_id =", run_id);

  let events: TraceEvent[] = [];
  for (let i = 0; i < 40; i++) {
    const r = await fetch(`${BASE}/api/plan/${run_id}`);
    const data = (await r.json()) as { events: TraceEvent[] };
    events = data.events ?? [];
    if (events.some((e) => e.type === "RUN_COMPLETED")) break;
    await sleep(250);
  }

  const view = deriveView(events);
  console.log(`\nFolded ${events.length} events → view:\n`);

  assert(view.runStatus === "complete", "runStatus is complete");
  assert(view.runId === run_id, "runId threaded through");
  assert(view.round >= 1, `at least one refinement round (round=${view.round})`);
  assert(view.finalPlan !== null, "finalPlan populated from RUN_COMPLETED");

  // every agent reached a terminal state (done/conflict), none stuck idle/running
  for (const name of view.agentOrder) {
    const a = view.agents[name];
    assert(a.status === "done" || a.status === "conflict",
      `${name} terminal status = ${a.status}`);
  }

  // the calorie handshake + a budget revision + a critic conflict all became edges
  const kinds = new Set(view.edges.map((e) => e.kind));
  assert(view.edges.some((e) => e.kind === "message" && e.intent === "calorie_handshake"),
    "calorie_handshake message edge present");
  assert(kinds.has("conflict"), "a conflict edge present (the debate)");
  assert(kinds.has("revision"), "a revision edge present (budget/critic → specialist)");

  // nutrition was inspected with input+output+tools (powers the inspector)
  const nut = view.agents["nutrition"];
  assert(!!nut.input && !!nut.output, "nutrition has input + output for the inspector");
  assert(nut.tools.includes("macros_calc"), "nutrition tools captured (macros_calc)");

  // final plan converged within budget after the refinement round
  assert(view.finalPlan!.budget.within_budget === true, "final plan within budget (converged)");
  assert(view.finalPlan!.agent_contributions.length >= 4, "agent_contributions rendered");

  console.log("\nALL REDUCER CHECKS PASSED");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
