"""The six specialist/critic/resolver agents.

Each extends BaseAgent, registers via @register(name), owns ONE responsibility, declares its
tools, and contains its prompt(s). Specs: docs/agents/<name>.md. Build-plan Phase 3.

Importing this package registers all agents (so the orchestrator can build the graph from the
registry). Keep imports here in dependency order for readability.
"""
from app.agents import (  # noqa: F401  -- side effect: registers agents
    budget,
    critic,
    fitness,
    medical_risk,
    nutrition,
    resolver,
)
