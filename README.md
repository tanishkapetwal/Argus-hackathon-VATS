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

```bash
# Backend
cd backend
cp ../.env.example .env       # add your LLM + API keys
pip install -e .
uvicorn app.api.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

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
