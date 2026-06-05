"""Builds the LangGraph: nodes = agents, shared PlanState, conditional refinement edge.

Spec: docs/orchestration.md (the graph diagram + conflict routing). Build-plan task 4.2.

Flow:
  medical_risk -> (nutrition <-> fitness handshake) -> budget -> critic
                 -> [conflicts and round < MAX]? loop to targeted specialists : resolver -> END

The conditional edge after `critic` keys on PlanState.open_conflicts and PlanState.round and is
bounded by Settings.max_refinement_rounds (always terminates; Resolver always finalizes).
"""
from __future__ import annotations


def build_graph():  # -> CompiledStateGraph
    """Construct and compile the LangGraph.

    TODO(4.2):
      - from langgraph.graph import StateGraph, END
      - add a node per registered agent (app.core.registry.all_agents); each node wraps the
        agent's run(ctx) and writes its output back into PlanState (its own slice only).
      - edges: medical_risk -> nutrition/fitness -> budget -> critic.
      - conditional edge from critic: route to the agents named in open_conflicts (round += 1)
        while round < settings.max_refinement_rounds, else -> resolver -> END.
      - model nutrition<->fitness so the calorie handshake actually runs and is traced.
    Keep the graph readable; this is where the interdependency is encoded (40% of the score).
    """
    raise NotImplementedError("Implement per docs/orchestration.md + build-plan task 4.2")
