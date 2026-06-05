"""Live end-to-end demo client: POST the conflict-forcing profile, stream the WS trace, print
the final HealthPlan. Run against a uvicorn started with LLM_PROVIDER=scripted (offline).

    .venv/bin/python scripts/demo_run.py
"""
from __future__ import annotations

import asyncio
import json

import httpx
import websockets

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000"

DEMO_PROFILE = {
    "age": 34, "sex": "male", "height_cm": 178, "weight_kg": 92, "activity_level": "light",
    "goal": "fat_loss", "target_weight_kg": 78, "timeframe_weeks": 12,
    "medical_conditions": ["knee injury", "hypertension"], "medications": [],
    "allergies": ["peanuts"], "budget_weekly": 1500, "currency": "INR",
    "diet_preference": "high protein, vegetarian", "disliked_foods": ["mushroom"],
    "equipment_access": ["dumbbells"], "days_per_week": 4, "session_minutes": 45,
    "notes": "wants visible results fast",
}


async def main() -> None:
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE}/api/plan", json=DEMO_PROFILE)
        run_id = resp.json()["run_id"]
    print(f"run_id = {run_id}\n")
    print("──────── STREAMED TRACE (seq · TYPE · agent · round · summary) ────────")

    plan = None
    async with websockets.connect(f"{WS}/ws/trace/{run_id}", max_size=4_000_000) as ws:
        while True:
            event = json.loads(await ws.recv())
            agent = (event.get("agent") or "—").ljust(13)
            print(f"{event['seq']:>3} · {event['type']:<18} · {agent} · r{event['round']} · "
                  f"{event['summary']}")
            if event["type"] == "RUN_COMPLETED":
                plan = event["payload"]["plan"]
                break

    print("\n──────── FINAL HEALTH PLAN ────────")
    print("SUMMARY:  ", plan["summary"])
    print("RATIONALE:", plan["rationale"])
    b = plan["budget"]
    print(f"\nBUDGET:   {b['currency']} {b['estimated_weekly_cost']:.0f}/week vs "
          f"{b['weekly_budget']:.0f} → within_budget={b['within_budget']}")
    m = plan["nutrition"]["macros"]
    print(f"DIET:     {m['target_kcal']:.0f} kcal/day · P{m['protein_g']:.0f}/"
          f"C{m['carbs_g']:.0f}/F{m['fat_g']:.0f}")
    fp = plan["fitness"]
    print(f"FITNESS:  {fp['days_per_week']}-day split · "
          f"~{fp['est_weekly_kcal_burn']:.0f} kcal/week burn")
    print(f"\nRESOLVED CONFLICTS: {len(plan['resolved_conflicts'])}")
    print(f"OPEN TRADE-OFFS:    {plan['open_tradeoffs'] or 'none — converged'}")
    print("\nAGENT CONTRIBUTIONS (who influenced whom):")
    for c in plan["agent_contributions"]:
        due = f"  ← changed_due_to: {', '.join(c['changed_due_to'])}" if c["changed_due_to"] else ""
        print(f"  • {c['agent']:<12} {c['summary']}{due}")
    print(f"\nrequires_professional = {plan['requires_professional']}")
    print("DISCLAIMERS:", " ".join(plan["disclaimers"]))


if __name__ == "__main__":
    asyncio.run(main())
