"""Shared fixtures for agent contract tests (Phase 3).

Network-free: a FakeLLM returns canned structured output, a NoLLM asserts the LLM is never
called (for the deterministic Budget/Critic agents), and a fake USDA tool avoids the network.
Trace events are captured with the real TraceEmitter so tests assert on its `.events` buffer.
"""
from __future__ import annotations

from app.core.base_agent import AgentContext, ToolBelt
from app.core.trace import TraceEmitter
from app.llm.base import LLMProvider, LLMResponse
from app.schemas import (
    ActivityLevel,
    FoodItem,
    Goal,
    PlanState,
    Sex,
    TraceEventType,
    UserProfile,
)
from app.tools.fitness_calc import estimate_weekly_burn
from app.tools.macros import calculate_macros
from app.tools.prices import price_of
from app.tools.web_search import web_search


class FakeLLM(LLMProvider):
    """Returns a preset parsed model (and optional text) for every complete() call."""

    def __init__(self, parsed=None, text: str = "", tool_calls=None):
        self.parsed = parsed
        self.text = text
        self.tool_calls = tool_calls or []
        self.calls: list[dict] = []

    async def complete(self, messages, *, tier="strong", tools=None, response_model=None,
                       temperature=0.2, max_tokens=4096) -> LLMResponse:
        self.calls.append({"messages": messages, "tier": tier, "response_model": response_model})
        return LLMResponse(text=self.text, parsed=self.parsed, tool_calls=self.tool_calls)


class NoLLM(LLMProvider):
    """Fails loudly if a supposedly-deterministic agent tries to call the LLM."""

    async def complete(self, *args, **kwargs) -> LLMResponse:  # pragma: no cover - guard
        raise AssertionError("This agent must be deterministic and not call the LLM")


async def fake_usda(name: str, quantity_g: float = 100.0) -> FoodItem:
    """Deterministic stand-in for the USDA tool (no network)."""
    return FoodItem(
        name=name, quantity=f"{quantity_g:g} g",
        kcal=120.0, protein_g=12.0, carbs_g=8.0, fat_g=4.0, fdc_id=999001,
    )


def sample_profile(**overrides) -> UserProfile:
    base = dict(
        age=30, sex=Sex.male, height_cm=180.0, weight_kg=80.0,
        activity_level=ActivityLevel.moderate, goal=Goal.fat_loss,
        target_weight_kg=75.0, timeframe_weeks=12,
        medical_conditions=["knee injury"], medications=[], allergies=["peanuts"],
        budget_weekly=1500.0, currency="INR", diet_preference="vegetarian",
        disliked_foods=[], equipment_access=["dumbbells"], days_per_week=4, session_minutes=45,
    )
    base.update(overrides)
    return UserProfile(**base)


# Tool callables that are deterministic / network-free as-is (seeded prices, no-key web search).
REAL_SAFE_TOOLS = {
    "macros_calc": calculate_macros,
    "fitness_calc": estimate_weekly_burn,
    "prices": price_of,
    "web_search": web_search,
    "usda": fake_usda,  # override the networked one
}


def make_ctx(profile, *, llm, tool_names, state=None, round=0):
    """Build an AgentContext wired to a real TraceEmitter; returns (ctx, emitter)."""
    emitter = TraceEmitter(run_id="test-run")
    state = state or PlanState(run_id="test-run", profile=profile)
    tools = ToolBelt({n: REAL_SAFE_TOOLS[n] for n in tool_names})
    ctx = AgentContext(
        profile=profile, state=state, llm=llm, tools=tools, emit=emitter.emit, round=round
    )
    return ctx, emitter


def event_types(emitter: TraceEmitter) -> list[TraceEventType]:
    return [e.type for e in emitter.events]
