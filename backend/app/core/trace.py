"""TraceEmitter — creates TraceEvents and fans them out to WebSocket subscribers + a per-run
buffer (which doubles as the execution log / replay source).

Spec: docs/trace-view.md, docs/data-models.md §10. Implements build-plan task 0.4.
Agents never touch sockets directly — they call `ctx.emit(...)`, which routes here.
"""
from __future__ import annotations

import asyncio
import itertools
from datetime import UTC, datetime

from app.schemas import TraceEvent, TraceEventType  # defined in schemas/ (build-plan 0.3)


class TraceEmitter:
    """One per run. Thread/async-safe enough for the hackathon (single event loop)."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._seq = itertools.count()
        self._buffer: list[TraceEvent] = []
        self._subscribers: list[asyncio.Queue[TraceEvent]] = []

    async def emit(
        self,
        type: TraceEventType,
        *,
        agent: str | None = None,
        round: int = 0,
        summary: str = "",
        payload: dict | None = None,
    ) -> TraceEvent:
        event = TraceEvent(
            run_id=self.run_id,
            seq=next(self._seq),
            type=type,
            agent=agent,
            round=round,
            timestamp=datetime.now(UTC),
            summary=summary,
            payload=payload or {},
        )
        self._buffer.append(event)
        for q in self._subscribers:
            q.put_nowait(event)
        return event

    def subscribe(self) -> asyncio.Queue[TraceEvent]:
        """A WebSocket handler subscribes to receive live events. Replays the buffer first."""
        q: asyncio.Queue[TraceEvent] = asyncio.Queue()
        for event in self._buffer:  # late subscribers still get the full run
            q.put_nowait(event)
        self._subscribers.append(q)
        return q

    @property
    def events(self) -> list[TraceEvent]:
        """Full ordered event log for GET /api/plan/{run_id} replay."""
        return list(self._buffer)


# Simple in-memory registry of runs. NOTE for the next team: swap for a real store to
# persist runs across restarts (see docs/build-plan.md future extensions).
_RUNS: dict[str, TraceEmitter] = {}


def create_emitter(run_id: str) -> TraceEmitter:
    emitter = TraceEmitter(run_id)
    _RUNS[run_id] = emitter
    return emitter


def get_emitter(run_id: str) -> TraceEmitter | None:
    return _RUNS.get(run_id)
