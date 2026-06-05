# Health Plan Optimizer

A **Multi-Agent Decision Intelligence System** that builds a personalized, medically-aware,
budget-fit health plan (diet + workout + cost) by having six specialized AI agents
**collaborate, challenge each other, and resolve conflicts** rather than one model guessing.

> Built for **Argusoft Hackathon Two — Multi-Agent Decision Intelligence System**.

---

## Why multiple agents?

A good health plan is a *negotiation between competing concerns*:

- A **medical** condition (diabetes, hypertension, a knee injury) makes some diets and
  workouts unsafe.
- The **diet's** calorie target and the **workout's** energy burn have to add up, or the
  person loses muscle / under-recovers.
- The **budget** can make the "ideal" high-protein diet or boutique gym plan impossible,
  forcing the diet and workout to be rewritten.

No single specialist sees all of this. So we use six agents that **constrain and revise
each other**:

| Agent | What it owns |
|-------|--------------|
| 🩺 **Medical Risk** | Hard safety constraints + red flags (runs first, gates everyone) |
| 🥗 **Nutrition** | Diet plan + macros (deterministic macro calculator + USDA food data) |
| 🏋️ **Fitness** | Workout plan + calorie burn (kept in sync with the diet) |
| 💰 **Budget** | Costs the plan, pushes back when it's too expensive |
| 🔍 **Critic** | Attacks every output for conflicts & unsafe advice |
| ⚖️ **Resolver** | Reconciles the fight and writes the final integrated plan |

The final plan **emerges from their debate**, and the whole debate is visible in a live
**Agent Trace View**.

## What you can see in the demo

1. Enter a profile (age, weight, goal, conditions, budget, preferences).
2. Watch the agents run in a **live trace view**: each agent's input, output, the messages
   they pass, the **conflicts the Critic raises**, and the **revisions** that result.
3. Get a final **Health Plan**: weekly diet, workout split, weekly cost, and a "what each
   agent changed and why" summary.

## Stack

Python · LangGraph · FastAPI + WebSocket · Pydantic · provider-abstracted LLM (Claude
default) · React + Vite + Tailwind · real tools (USDA FoodData Central, web search, price data).

## Quickstart

**1. Backend** (terminal 1):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .

# Option A — offline demo, NO API key (deterministic "scripted" agents):
LLM_PROVIDER=scripted USE_SEEDED_PRICES=true USDA_FDC_API_KEY= \
  uvicorn app.api.main:app --reload

# Option B — real Claude agents (needs a key):
cp ../.env.example .env        # set ANTHROPIC_API_KEY, keep LLM_PROVIDER=anthropic
uvicorn app.api.main:app --reload
```

**2. Frontend** (terminal 2):

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173 (CORS allows any localhost port)
```

Open the URL Vite prints, pick a demo profile, and click **Run plan**.

### Demo profiles

Three seeded profiles (selectable in the UI) each tell a different story:

| Profile | What it demonstrates |
|---------|----------------------|
| **Conflict & refinement** | Aggressive fat-loss + knee injury + hypertension + tight ₹1500 budget → Budget overrun → a refinement round that converges. |
| **Comfortable budget** | Generous budget, no injuries → the plan fits first time; the Critic approves with no loop. |
| **Red flag → referral** | Chest pain + uncontrolled hypertension → the Medical Risk gate escalates and the Resolver returns a "see a professional first" plan. |

The 90-second demo narrative (Medical Risk gate → calorie handshake → budget pushback →
Critic conflict → Resolver synthesis) is in [docs/trace-view.md](docs/trace-view.md) §4 and is
covered end-to-end by `frontend/scripts/demo_narrative.ts`.

## Documentation

This repository is **spec-first** — the design is fully documented so it can be built (and
extended) by AI agents or future teams. Start here:

- **[CLAUDE.md](CLAUDE.md)** — entry point for AI builders
- **[docs/architecture.md](docs/architecture.md)** — system design
- **[docs/orchestration.md](docs/orchestration.md)** — how the agents debate & resolve
- **[docs/agents/](docs/agents/)** — per-agent specs
- **[docs/contributing.md](docs/contributing.md)** — how to add a new agent
- **[docs/build-plan.md](docs/build-plan.md)** — phased build order

## ⚠️ Disclaimer

This system produces **informational fitness/nutrition suggestions, not medical advice**.
It always recommends consulting a qualified professional before acting, and the Medical Risk
Agent escalates red-flag conditions to "see a doctor" rather than planning around them.
