"""BaseAgent contract — every agent extends this.

Defines the interface and the automatic trace-emission wrapper so individual agents stay thin
(they implement only `_run`). Spec: docs/architecture.md §3, docs/agents/, docs/trace-view.md §3.
Implements build-plan.md task 0.5 and the per-agent tracing required by Phase 3.

`run()` wraps `_run()` and emits, in order: AGENT_STARTED, AGENT_INPUT, then (after the agent
returns) AGENT_OUTPUT, one MESSAGE_SENT per emitted message, one CONFLICT_RAISED per conflict,
one REVISION_REQUESTED per revision, and AGENT_COMPLETED. On an unexpected error it emits ERROR
and re-raises. Agents emit TOOL_CALLED themselves when they invoke a tool.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.schemas import TraceEventType

if TYPE_CHECKING:
    from app.llm.base import LLMProvider
    from app.schemas import (
        AgentMessage,
        Conflict,
        PlanState,
        RevisionRequest,
        UserProfile,
    )

# ctx.emit mirrors TraceEmitter.emit: (type, *, agent, round, summary, payload) -> TraceEvent.
EmitFn = Callable[..., Awaitable[object]]


@dataclass
class AgentContext:
    """Everything an agent needs to do its job. Passed to `BaseAgent.run`."""
    profile: UserProfile
    state: PlanState
    llm: LLMProvider
    tools: ToolBelt
    emit: EmitFn
    round: int = 0


@dataclass
class AgentResult:
    """What an agent returns. `output` is the agent's typed product."""
    output: BaseModel
    messages: list[AgentMessage] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    revisions: list[RevisionRequest] = field(default_factory=list)


class ToolBelt:
    """Holds the subset of tools an agent declared it may use. See docs/contributing.md §B."""

    def __init__(self, tools: dict[str, Callable]) -> None:
        self._tools = tools

    def __getattr__(self, name: str) -> Callable:
        try:
            return self._tools[name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise AttributeError(f"Tool {name!r} not granted to this agent") from exc

    def __contains__(self, name: str) -> bool:
        return name in self._tools


def _to_json(model: BaseModel) -> dict:
    return model.model_dump(mode="json")


class BaseAgent(ABC):
    """Abstract base for all specialist/critic/resolver agents.

    Subclasses set `name` (via @register), `tier`, `tools`, `output_schema`, and implement
    `_run`. The public `run` wraps `_run` to emit the trace events uniformly for every agent.
    """
    name: str = "base"
    tier: str = "strong"
    tools: list[str] = []
    output_schema: type[BaseModel] | None = None

    async def run(self, ctx: AgentContext) -> AgentResult:
        name, rnd = self.name, ctx.round
        await ctx.emit(
            TraceEventType.AGENT_STARTED, agent=name, round=rnd,
            summary=f"{name} started (round {rnd})",
        )
        await ctx.emit(
            TraceEventType.AGENT_INPUT, agent=name, round=rnd,
            summary=f"{name} received input", payload=self._input_view(ctx),
        )
        try:
            result = await self._run(ctx)
        except Exception as exc:
            await ctx.emit(
                TraceEventType.ERROR, agent=name, round=rnd,
                summary=f"{name} error: {exc}", payload={"error": str(exc)},
            )
            raise

        await ctx.emit(
            TraceEventType.AGENT_OUTPUT, agent=name, round=rnd,
            summary=self._output_summary(result.output), payload=_to_json(result.output),
        )
        for msg in result.messages:
            await ctx.emit(
                TraceEventType.MESSAGE_SENT, agent=name, round=rnd,
                summary=f"{msg.sender} → {msg.recipient}: {msg.intent}",
                payload={
                    "sender": msg.sender, "recipient": msg.recipient,
                    "intent": msg.intent, "payload": msg.payload, "text": msg.text,
                },
            )
        for conflict in result.conflicts:
            await ctx.emit(
                TraceEventType.CONFLICT_RAISED, agent=name, round=rnd,
                summary=f"{conflict.type.value}: {conflict.description}",
                payload=_to_json(conflict),
            )
        for rev in result.revisions:
            await ctx.emit(
                TraceEventType.REVISION_REQUESTED, agent=name, round=rnd,
                summary=f"{rev.raised_by} → {rev.target_agent}: {rev.constraint}",
                payload=_to_json(rev),
            )
        await ctx.emit(
            TraceEventType.AGENT_COMPLETED, agent=name, round=rnd, summary=f"{name} completed",
        )
        return result

    # ---- overridable hooks (sensible defaults; agents may specialize) -------------------
    def _input_view(self, ctx: AgentContext) -> dict:
        """Compact view of what this agent saw — powers the trace-view inspector."""
        s, p = ctx.state, ctx.profile
        view: dict = {
            "round": ctx.round,
            "profile": {
                "age": p.age, "sex": p.sex.value, "goal": p.goal.value,
                "weight_kg": p.weight_kg, "budget_weekly": p.budget_weekly,
                "currency": p.currency,
            },
        }
        if s.constraints is not None:
            view["constraints"] = _to_json(s.constraints)
        if s.nutrition is not None:
            view["nutrition_macros"] = _to_json(s.nutrition.macros)
        if s.fitness is not None:
            view["fitness_burn_weekly"] = s.fitness.est_weekly_kcal_burn
        if s.budget is not None:
            view["budget"] = {
                "estimated_weekly_cost": s.budget.estimated_weekly_cost,
                "within_budget": s.budget.within_budget,
            }
        mine = [_to_json(r) for r in s.revision_requests if r.target_agent == self.name]
        if mine:
            view["revision_requests"] = mine
        return view

    def _output_summary(self, output: BaseModel) -> str:
        return f"{self.name} produced {type(output).__name__}"

    @abstractmethod
    async def _run(self, ctx: AgentContext) -> AgentResult:
        """Domain logic. Implement per the agent's spec in docs/agents/<name>.md."""
        raise NotImplementedError
