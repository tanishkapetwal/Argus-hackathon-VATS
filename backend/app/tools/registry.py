"""Tool registry + ToolBelt builder (build-plan task 1.5).

Maps tool names (the strings agents declare in `tools = [...]`) to the actual callables, and
builds a per-agent `ToolBelt` granting only the declared tools. The orchestrator uses this to
construct each agent's context; nothing else needs to know how a tool is implemented.
"""
from __future__ import annotations

from collections.abc import Callable

from app.core.base_agent import ToolBelt
from app.tools.fitness_calc import estimate_weekly_burn
from app.tools.macros import calculate_macros
from app.tools.prices import price_of
from app.tools.usda import lookup_food
from app.tools.web_search import web_search

TOOL_REGISTRY: dict[str, Callable] = {
    "macros_calc": calculate_macros,   # deterministic BMR/TDEE/macros
    "fitness_calc": estimate_weekly_burn,  # deterministic MET-based burn
    "usda": lookup_food,               # USDA FoodData Central (graceful fallback)
    "prices": price_of,                # seeded/live price lookup
    "web_search": web_search,          # Tavily-backed search (graceful fallback)
}


def build_toolbelt(names: list[str]) -> ToolBelt:
    """Grant an agent only its declared tools. Raises if a name is unknown."""
    missing = [n for n in names if n not in TOOL_REGISTRY]
    if missing:
        raise KeyError(f"Unknown tool(s): {missing}. Registered: {sorted(TOOL_REGISTRY)}")
    return ToolBelt({n: TOOL_REGISTRY[n] for n in names})
