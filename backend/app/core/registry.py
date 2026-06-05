"""AgentRegistry — the single seam that makes the system pluggable.

Agents register here; the orchestrator builds the graph from the registry. Adding an agent
must not require editing existing agents (docs/contributing.md §A). Implements build-plan task 0.5.
"""
from __future__ import annotations

from collections.abc import Callable

from app.core.base_agent import BaseAgent

_REGISTRY: dict[str, type[BaseAgent]] = {}


def register(name: str) -> Callable[[type[BaseAgent]], type[BaseAgent]]:
    """Class decorator: `@register("nutrition")` adds the agent to the registry."""
    def _decorator(cls: type[BaseAgent]) -> type[BaseAgent]:
        if name in _REGISTRY:
            raise ValueError(f"Agent {name!r} already registered")
        cls.name = name
        _REGISTRY[name] = cls
        return cls
    return _decorator


def get_agent(name: str) -> BaseAgent:
    """Instantiate a registered agent by name."""
    return _REGISTRY[name]()


def all_agents() -> dict[str, type[BaseAgent]]:
    return dict(_REGISTRY)
